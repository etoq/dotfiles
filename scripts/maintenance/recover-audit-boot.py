#!/usr/bin/env python3
"""Restore the previous audit=0 boot policy without touching encryption or AppArmor."""
import argparse
import datetime
import os
from pathlib import Path
import shutil
import subprocess as sp
import tempfile


def command(args, required=True):
    r = sp.run([str(x) for x in args], capture_output=True, text=True, timeout=180)
    if required and r.returncode:
        raise RuntimeError('Command failed: ' + ' '.join(map(str, args)) + '\n' + r.stderr[-1200:])
    return r


def atomic(path, data, mode):
    fd, name = tempfile.mkstemp(prefix='.' + path.name, dir=path.parent)
    try:
        os.fchmod(fd, mode)
        with os.fdopen(fd, 'wb') as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    p = Path('/etc/default/grub')
    original = p.read_bytes()
    if b'audit=1' not in original and b'audit=0' not in original:
        raise RuntimeError('Unexpected GRUB audit policy; no changes made')
    revised = original.replace(b'audit=1', b'audit=0')
    print('Restore audit=0; disable auditd autostart; keep AppArmor, LUKS, NVIDIA and Thinkfan unchanged.', flush=True)
    if not args.apply:
        return
    if os.geteuid() != 0:
        raise RuntimeError('Run --apply with sudo')
    backup = Path('/var/backups') / ('audit-boot-recovery-' + datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f'))
    backup.mkdir(mode=0o700)
    shutil.copy2(p, backup / 'grub.default.before')
    grub = Path('/boot/grub/grub.cfg')
    shutil.copy2(grub, backup / 'grub.cfg.before')
    for unit in ('auditd.service', 'audit-rules.service'):
        result = command(['systemctl', 'is-enabled', unit], required=False)
        (backup / (unit + '.state')).write_text(result.stdout)
    atomic(p, revised, p.stat().st_mode & 0o777)
    try:
        command(['grub-mkconfig', '-o', backup / 'grub.cfg.new'])
        command(['grub-script-check', backup / 'grub.cfg.new'])
    except Exception:
        atomic(p, original, p.stat().st_mode & 0o777)
        raise
    atomic(grub, (backup / 'grub.cfg.new').read_bytes(), grub.stat().st_mode & 0o777)
    for unit in ('auditd.service', 'audit-rules.service'):
        command(['systemctl', 'disable', unit])
    # Do not change AppArmor mode or delete audit rules. Try stopping event
    # generation for this boot; an immutable audit state may require reboot.
    result = command(['auditctl', '-e', '0'], required=False)
    print('Runtime audit disabled.' if result.returncode == 0 else 'Runtime audit could not be disabled; the boot policy is fixed, reboot is required.', flush=True)
    if result.returncode:
        print(result.stderr.strip()[:600], flush=True)
    command(['systemctl', 'reset-failed', 'auditd.service', 'audit-rules.service'])
    print(command(['systemctl', '--failed', '--no-pager']).stdout, flush=True)
    print('Completed. Backup:', backup)
    print('No encryption, AppArmor enforcement, network or driver changes. No reboot performed.')
    print('Save work and reboot normally. Check the new boot journal afterwards.')


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        raise SystemExit('STOP: ' + str(e))
