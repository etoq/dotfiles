#!/usr/bin/python
"""Unmount this workstation's ESP, check FAT without repairs, always remount."""
import json
import os
from pathlib import Path
import shutil
import subprocess as sp
import sys


def check():
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
        result = sp.run(['fsck.fat', '-n', source])
    finally:
        sp.run(['mount', str(target)], check=True)
        print('EFI mounted again.', flush=True)
    if not target.is_mount():
        raise RuntimeError('EFI remount verification failed')
    print('FAT check exit code:', result.returncode, flush=True)
    if result.returncode != 0:
        raise RuntimeError('FAT check reported a problem; no repairs were requested. Send the output.')
    print('OK: FAT check found no recoverable errors. No reboot or sleep performed.')


if __name__ == '__main__':
    try:
        check()
    except (RuntimeError, OSError, KeyError, sp.CalledProcessError) as error:
        print('STOP:', error, file=sys.stderr)
        sys.exit(1)
