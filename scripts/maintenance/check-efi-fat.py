#!/usr/bin/python
"""Offline FAT check; optional dirty-bit repair rehearsed on a backed-up image."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess as sp
import sys
import time


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def only_dirty_byte_changed(before, after):
    changes = []
    offset = 0
    with Path(before).open('rb') as left, Path(after).open('rb') as right:
        while True:
            a, b = left.read(4 * 1024 ** 2), right.read(4 * 1024 ** 2)
            if len(a) != len(b):
                return False
            if not a:
                break
            if a != b:
                for index, (old, new) in enumerate(zip(a, b)):
                    if old != new:
                        changes.append((offset + index, old, new))
                        if changes != [(65, 1, 0)]:
                            return False
            offset += len(a)
    return changes == [(65, 1, 0)]


def fsck(source, mode):
    result = sp.run(['fsck.fat', mode, str(source)], capture_output=True, text=True,
                    env={**os.environ, 'LC_ALL': 'C'})
    print(result.stdout, end='', flush=True)
    if result.stderr:
        print(result.stderr, end='', file=sys.stderr, flush=True)
    return result


def clear_dirty(source):
    size = int(sp.check_output(['blockdev', '--getsize64', source], text=True))
    if shutil.disk_usage('/var/backups').free < size * 2 + 128 * 1024 ** 2:
        raise RuntimeError('Not enough space for EFI image backup and rehearsal')
    backup = Path('/var/backups') / time.strftime('efi-fat-dirty-%Y%m%d-%H%M%S')
    backup.mkdir(mode=0o700)
    image = backup / 'efi-before.img'
    fd = os.open(image, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with Path(source).open('rb') as original, os.fdopen(fd, 'wb') as saved:
        shutil.copyfileobj(original, saved, 4 * 1024 ** 2)
        saved.flush()
        os.fsync(saved.fileno())
    expected = digest(image)
    if image.stat().st_size != size or digest(source) != expected:
        raise RuntimeError('Raw EFI backup verification failed')
    (backup / 'SHA256SUMS').write_text(expected + '  efi-before.img\n')
    print('Verified complete EFI partition image:', image, flush=True)
    trial = backup / 'rehearsal.img'
    try:
        sp.run(['cp', '--reflink=auto', '--', str(image), str(trial)], check=True)
        trial.chmod(0o600)
        result = fsck(trial, '-a')
        if result.returncode not in (0, 1) or fsck(trial, '-n').returncode != 0:
            raise RuntimeError('Rehearsal did not produce a clean FAT filesystem; real EFI untouched')
        if not only_dirty_byte_changed(image, trial):
            raise RuntimeError('Rehearsal changed more than dirty byte 65; real EFI untouched')
        # A native tool performs the real repair only after its entire effect was verified.
        if Path('/boot/efi').is_mount() or digest(source) != expected:
            raise RuntimeError('EFI mount state or contents changed during rehearsal')
        print('Rehearsal verified: only byte 65 changes 01 -> 00; files remain unchanged.', flush=True)
        result = fsck(source, '-a')
        if result.returncode not in (0, 1) or not only_dirty_byte_changed(image, source):
            raise RuntimeError('Unexpected real repair result; inspect the saved EFI image')
        return fsck(source, '-n')
    finally:
        trial.unlink(missing_ok=True)


def check(repair_dirty=False):
    if os.geteuid() != 0:
        raise RuntimeError('Run with sudo to unmount and inspect the EFI filesystem')
    if not shutil.which('fsck.fat'):
        raise RuntimeError('Install the FAT checker first: sudo pacman -S --needed dosfstools')
    if Path('/sys/class/dmi/id/product_name').read_text().strip() != '20EQS59J07':
        raise RuntimeError('This check is prepared for the ThinkPad P50')
    if Path('/var/lib/pacman/db.lck').exists():
        raise RuntimeError('Package manager is busy')
    target = Path('/boot/efi')
    record = json.loads(sp.check_output(['findmnt', '--json', '--mountpoint', str(target),
                                       '--output', 'SOURCE,FSTYPE'], text=True))['filesystems'][0]
    if record['fstype'] != 'vfat' or Path(record['source']).resolve() != Path('/dev/nvme0n1p1'):
        raise RuntimeError('EFI device or filesystem differs')
    source = record['source']
    sp.run(['sync', '-f', str(target)], check=True)
    sp.run(['umount', str(target)], check=True)
    try:
        if target.is_mount():
            raise RuntimeError('EFI remains mounted; refusing filesystem check')
        print('Checking unmounted EFI without writing repairs:', source, flush=True)
        result = fsck(source, '-n')
        if repair_dirty and result.returncode == 1:
            result = clear_dirty(source)
    finally:
        sp.run(['mount', str(target)], check=True)
        print('EFI mounted again.', flush=True)
    if not target.is_mount():
        raise RuntimeError('EFI remount verification failed')
    print('FAT check exit code:', result.returncode, flush=True)
    if result.returncode != 0:
        raise RuntimeError('FAT check reported a problem. Send the output.')
    print('OK: FAT check found no recoverable errors. No reboot or sleep performed.')


if __name__ == '__main__':
    try:
        parser = argparse.ArgumentParser(description=__doc__)
        parser.add_argument('--clear-dirty', action='store_true', help='Rehearse repair on an image; accept only byte 65 changing 01 to 00')
        check(parser.parse_args().clear_dirty)
    except (RuntimeError, OSError, KeyError, sp.CalledProcessError) as error:
        print('STOP:', error, file=sys.stderr)
        sys.exit(1)
