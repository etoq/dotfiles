#!/usr/bin/python
"""Machine-specific weekly root TRIM and sensor-based thinkfan startup."""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess as sp
import time

HERE = Path(__file__).resolve().parent
ROOT_UUID = 'c6838094-6e77-4446-bbb1-0a4acfd72b25'
CRYPT = 'cryptdevice=UUID=d0394e85-24b4-44d9-883a-f92a6f2b8ac8:cryptroot'
FAN_OVERRIDE = Path('/etc/systemd/system/thinkfan.service.d/override.conf')
FAN_OLD = '[Service]\nExecStartPre=/usr/bin/sleep 5\n'
FAN_NEW = '[Service]\nExecStartPre=\nExecStartPre=/usr/local/libexec/thinkfan-wait-ready\n'
TRIM_OVERRIDE = Path('/etc/systemd/system/fstrim.service.d/60-workstation-root.conf')
TRIM_NEW = '# Weekly TRIM is restricted to the system Btrfs filesystem.\n[Service]\nExecStart=\nExecStart=/usr/bin/fstrim --verbose /\n'


def output(args):
    return sp.check_output(args, text=True).strip()


def boot_options(text):
    pattern = re.escape(CRYPT) + r'(?P<options>:[A-Za-z0-9_,=-]+)?(?=[\s\x27\x22]|$)'
    count = 0
    def replace(match):
        nonlocal count
        count += 1
        options = (match['options'] or '').lstrip(':').split(',')
        options = [x for x in options if x]
        if 'allow-discards' not in options and 'discard' not in options:
            options.append('allow-discards')
        return CRYPT + ':' + ','.join(options)
    result = re.sub(pattern, replace, text)
    if not count:
        raise RuntimeError('Expected root unlock parameter is absent')
    return result


def mount_options(text):
    lines = []
    found = False
    for line in text.splitlines(keepends=True):
        if line.lstrip().startswith('#') or not line.strip():
            lines.append(line)
            continue
        fields = list(re.finditer(r'\S+', line))
        if len(fields) >= 4 and fields[0][0] == 'UUID=' + ROOT_UUID and fields[2][0] == 'btrfs':
            found |= fields[1][0] == '/'
            old = fields[3]
            opts = [x for x in old[0].split(',') if x != 'discard' and not x.startswith('discard=') and x != 'nodiscard']
            opts.append('nodiscard')
            line = line[:old.start()] + ','.join(opts) + line[old.end():]
        lines.append(line)
    if not found:
        raise RuntimeError('Expected Btrfs root is absent in fstab')
    return ''.join(lines)


def write(path, data, mode):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.workstation-new')
    with temporary.open('xb') as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    temporary.chmod(mode)
    temporary.replace(path)


def restore(stage):
    stage = stage.resolve()
    if stage.parent != Path('/var/backups') or stage.stat().st_uid != 0 or stage.stat().st_mode & 0o077:
        raise RuntimeError('Expected a protected root-owned backup directory')
    manifest = json.loads((stage / 'manifest.json').read_text())
    for item in manifest['files']:
        path = Path(item['path'])
        if item['existed']:
            write(path, (stage / 'files' / path.relative_to('/')).read_bytes(), item['mode'])
        else:
            path.unlink(missing_ok=True)
    if manifest['timer'] == 'disabled':
        sp.run(['systemctl', 'disable', 'fstrim.timer'], check=True)
    sp.run(['systemctl', 'daemon-reload'], check=True)
    print('Previous files restored. No reboot, fan restart or TRIM performed.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_mutually_exclusive_group()
    actions.add_argument('--apply', action='store_true')
    actions.add_argument('--restore', type=Path)
    args = parser.parse_args()
    if os.geteuid() != 0:
        raise RuntimeError('Run with sudo to verify protected boot and encryption settings')
    if args.restore:
        restore(args.restore)
        return
    if Path('/sys/class/dmi/id/product_version').read_text().strip() != 'ThinkPad P50':
        raise RuntimeError('Unexpected machine')
    if output(['findmnt', '-no', 'UUID', '--target', '/']) != ROOT_UUID:
        raise RuntimeError('Unexpected root filesystem')
    status = output(['cryptsetup', 'status', 'cryptroot'])
    if not re.search(r'^\s*device:\s*/dev/nvme0n1p2\s*$', status, re.M):
        raise RuntimeError('Unexpected encrypted root device')
    if int(output(['lsblk', '-bdno', 'DISC-MAX', '/dev/nvme0n1p2'])) <= 0:
        raise RuntimeError('Physical SSD does not advertise discard')
    if 'allow-discards|discard)' not in Path('/usr/lib/initcpio/hooks/encrypt').read_text():
        raise RuntimeError('Initramfs encrypt hook does not support the expected option')
    if not re.search(r'^HOOKS=.*\bencrypt\b', Path('/etc/mkinitcpio.conf').read_text(), re.M):
        raise RuntimeError('Unexpected initramfs unlock mechanism')
    if output(['systemctl', 'is-active', 'thinkfan.service']) != 'active':
        raise RuntimeError('Thinkfan is not currently active')
    if FAN_OVERRIDE.read_text() not in (FAN_OLD, FAN_NEW):
        raise RuntimeError('Thinkfan override contains unreviewed changes')
    if TRIM_OVERRIDE.exists() and TRIM_OVERRIDE.read_text() != TRIM_NEW:
        raise RuntimeError('Custom fstrim override exists')
    timer = sp.run(['systemctl', 'is-enabled', 'fstrim.timer'], capture_output=True, text=True).stdout.strip()
    if timer not in ('enabled', 'disabled'):
        raise RuntimeError('Unexpected fstrim timer state: ' + timer)
    if sp.run(['systemctl', 'is-active', '--quiet', 'fstrim.service']).returncode == 0:
        raise RuntimeError('TRIM is already running')
    helper = HERE.parent / 'system/thinkfan-wait-ready'
    sp.run(['/usr/bin/python', str(helper), '--check'], check=True)
    installed_helper = Path('/usr/local/libexec/thinkfan-wait-ready')
    if installed_helper.exists() and installed_helper.read_bytes() != helper.read_bytes():
        raise RuntimeError('Custom sensor readiness helper already exists')
    changes = {
        Path('/etc/default/grub'): boot_options(Path('/etc/default/grub').read_text()).encode(),
        Path('/etc/fstab'): mount_options(Path('/etc/fstab').read_text()).encode(),
        FAN_OVERRIDE: FAN_NEW.encode(),
        TRIM_OVERRIDE: TRIM_NEW.encode(),
        Path('/usr/local/libexec/thinkfan-wait-ready'): helper.read_bytes(),
    }
    for entry in Path('/boot/efi/loader/entries').glob('*.conf'):
        if CRYPT in entry.read_text():
            changes[entry] = boot_options(entry.read_text()).encode()
    print('Plan: weekly root-only TRIM; no continuous discard; /vms and crypttab unchanged.')
    print('TRIM reveals free-block allocation on the encrypted SSD, not plaintext file contents.')
    print('Thinkfan will wait for configured sensors instead of always sleeping 5 seconds.')
    if not args.apply:
        print('Check only: no changes. Apply with --apply.')
        return
    sp.run(['/home/eto/.local/bin/verify-kernel-stack'], check=True)
    stage = Path('/var/backups') / time.strftime('storage-and-boot-%Y%m%d-%H%M%S')
    stage.mkdir(mode=0o700)
    shutil.copy2(Path(__file__), stage / 'finish-storage-and-boot.py')
    paths = list(changes) + [Path('/boot/grub/grub.cfg'), Path('/boot/grub/grub-btrfs.cfg')]
    manifest = {'timer': timer, 'files': []}
    for path in paths:
        if path.is_symlink():
            raise RuntimeError('Expected regular configuration file: ' + str(path))
        existed = path.exists()
        manifest['files'].append({'path': str(path), 'existed': existed, 'mode': path.stat().st_mode & 0o777 if existed else 0o644})
        if existed:
            backup = stage / 'files' / path.relative_to('/')
            backup.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, backup)
    (stage / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print('Backup:', stage, flush=True)
    try:
        for path, data in changes.items():
            mode = 0o755 if path.name == 'thinkfan-wait-ready' else path.stat().st_mode & 0o777 if path.exists() else 0o644
            write(path, data, mode)
        candidate = stage / 'grub.cfg.new'
        sp.run(['grub-mkconfig', '-o', str(candidate)], check=True)
        sp.run(['grub-script-check', str(candidate)], check=True)
        generated = candidate.read_text()
        if boot_options(generated) != generated:
            raise RuntimeError('Generated GRUB does not include root discard permission')
        write(Path('/boot/grub/grub.cfg'), candidate.read_bytes(), 0o600)
        sp.run(['findmnt', '--verify', '--tab-file', '/etc/fstab'], check=True)
        sp.run(['systemctl', 'daemon-reload'], check=True)
        sp.run(['systemctl', 'enable', 'fstrim.timer'], check=True)
    except BaseException:
        restore(stage)
        raise
    print('Completed. No live encryption refresh, TRIM, fan restart or reboot performed.')
    print('Changes activate on the next normal reboot. Keep using NVIDIA 580 + Linux LTS.')
    print('Rollback: sudo python', stage / 'finish-storage-and-boot.py', '--restore', stage)


if __name__ == '__main__':
    try:
        main()
    except (RuntimeError, OSError, ValueError, sp.CalledProcessError) as error:
        raise SystemExit('STOP: ' + str(error))
