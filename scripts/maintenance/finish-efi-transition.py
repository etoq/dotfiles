#!/usr/bin/python
"""Consolidate verified duplicate ESP images, then finish the installed NVIDIA 580."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess as sp
import time

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('transition', HERE / 'nvidia-transition.py')
transition = importlib.util.module_from_spec(spec)
spec.loader.exec_module(transition)
NAMES = ('vmlinuz-linux', 'vmlinuz-linux-lts', 'initramfs-linux.img', 'initramfs-linux-lts.img')


def references(text):
    # Exact root-relative paths only; /@/boot/* and /EFI/ARCH/* are distinct paths.
    text = re.sub(r'/{2,}', '/', text)
    return any(re.search(r'(?<![\w/.-])/' + re.escape(name) + r'(?![\w/.-])', text)
               for name in NAMES)


def rewrite_entry(text):
    changed = 0
    result = []
    for line in text.splitlines(keepends=True):
        match = re.fullmatch(r'(\s*(?:linux|initrd)\s+)/(' + '|'.join(map(re.escape, NAMES)) + r')(\s*)', line)
        if match:
            line = match[1] + '/EFI/ARCH/' + match[2] + match[3]
            changed += 1
        result.append(line)
    updated = ''.join(result)
    if changed != 2 or references(updated):
        raise RuntimeError('Unexpected systemd-boot entry; review its paths manually')
    return updated


def preflight(efi, snapshot_root, grub_config, nvram):
    normal = efi / 'loader/entries/arch.conf'
    stale = efi / 'loader/entries/arch-snap-76.conf'
    if 'rootflags=subvol=@ ' not in normal.read_text():
        raise RuntimeError('Normal boot entry rootflags differ')
    updated = rewrite_entry(normal.read_text())
    if stale.exists():
        if 'rootflags=subvol=@snapshots/80/snapshot ' not in stale.read_text():
            raise RuntimeError('Snapshot entry differs from the inspected legacy entry')
        if (snapshot_root / '80/snapshot').exists():
            raise RuntimeError('Snapshot 80 still exists; its boot images must be reviewed separately')
    if references(grub_config) or references(nvram.replace('\\', '/')):
        raise RuntimeError('GRUB or a direct UEFI entry still references root ESP images')
    for pattern in ('*.conf', '*.cfg'):
        for path in efi.rglob(pattern):
            if path not in (normal, stale) and references(path.read_text()):
                raise RuntimeError('Another ESP configuration references the old images: ' + str(path))
    for name in NAMES:
        for path in (efi / name, efi / 'EFI/ARCH' / name):
            if path.is_symlink() or not path.is_file():
                raise RuntimeError('Expected regular EFI image missing: ' + str(path))
    return normal, stale, updated


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    if os.geteuid() != 0:
        raise RuntimeError('Run this EFI repair with sudo to read and validate the boot configuration')
    plan = json.loads((HERE / 'nvidia-transition-plan.json').read_text())
    transition.check_machine(plan)
    transition.installed_matches(plan['forward'])
    transition.verify_backup(plan)
    efi = Path('/boot/efi')
    # Verify the actual GRUB binary's embedded config prefix, not only a potentially
    # unrelated grub.cfg on disk. This workstation loads the encrypted root config.
    prefix = b'(cryptouuid/d0394e8524b444d9883af92a6f2b8ac8)/@/boot/grub'
    if prefix not in (efi / 'EFI/ARCH/grubx64.efi').read_bytes():
        raise RuntimeError('Embedded GRUB config location changed; inspect the boot loader first')
    normal, stale, updated = preflight(efi, Path('/.snapshots'),
        Path('/boot/grub/grub.cfg').read_text(), transition.output(['efibootmgr', '-v']))
    available = shutil.disk_usage(efi).free + sum((efi / name).stat().st_size for name in NAMES)
    # Keep enough room for a future atomic replacement as well as this transition.
    remaining = available
    largest = max((Path('/boot') / name).stat().st_size for name in NAMES)
    for name in NAMES:
        new_size = (Path('/boot') / name).stat().st_size
        if remaining < new_size + 8 * 1024 ** 2:
            raise RuntimeError('Consolidation would still leave too little EFI staging space')
        remaining += (efi / 'EFI/ARCH' / name).stat().st_size - new_size
    if remaining < largest + 8 * 1024 ** 2:
        raise RuntimeError('Consolidation would not leave room for future atomic image replacement')
    print('Validated: GRUB/direct UEFI do not reference the duplicate root images; snapshot 80 is absent.')
    print('After consolidation and 580 images: approximately', remaining // 1024 ** 2, 'MiB free in EFI.')
    if not args.apply:
        print('Check only. No files changed. Use --apply to back up duplicates and finish 580.')
        return
    backup = Path('/var/backups') / time.strftime('efi-consolidation-%Y%m%d-%H%M%S')
    backup.mkdir(mode=0o700)
    # Copy and hash every old file before changing any ESP content.
    paths = [efi / name for name in NAMES] + [normal] + ([stale] if stale.exists() else [])
    records = {}
    for path in paths:
        dest = backup / 'files' / path.relative_to(efi)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, dest)
        if transition.sha(dest) != transition.sha(path):
            raise RuntimeError('Backup verification failed: ' + str(path))
        records[path.relative_to(efi).as_posix()] = transition.sha(dest)
    (backup / 'SHA256SUMS').write_text(''.join(value + '  files/' + key + '\n' for key, value in records.items()))
    transition.output(['sync', '-f', str(backup)])
    temporary = normal.with_name(normal.name + '.new')
    temporary.write_text(updated)
    temporary.replace(normal)
    # The snapshot entry is retired only after proving its referenced snapshot no longer exists.
    if stale.exists():
        stale.unlink()
    for name in NAMES:
        (efi / name).unlink()
    transition.output(['sync', '-f', str(efi)])
    print('Verified old images and loader entries saved in:', backup, flush=True)
    print('GRUB files, UEFI boot order and microcode left unchanged.', flush=True)
    transition.apply(plan, False, resume=True)


if __name__ == '__main__':
    try:
        main()
    except (RuntimeError, OSError, ValueError, KeyError, sp.CalledProcessError) as error:
        print('STOP:', error)
        print('No reboot performed. Do not suspend or reboot until the transition completes.')
        raise SystemExit(1)
