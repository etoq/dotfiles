#!/usr/bin/python
"""Apply selected desktop packages and install read-only maintenance reporting."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess as sp
import time

REPO = Path(__file__).resolve().parents[2]
REMOVE = ('ntsync-autoload', 'v2ray', 'cronie')


def run(args):
    print('+', ' '.join(map(str, args)), flush=True)
    sp.run(list(map(str, args)), check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    if not args.apply:
        print('Plan: install extra/udiskie and extra/bpftrace; remove only', ', '.join(REMOVE))
        print('ImHex and Bibata are user assets; no driver or VM changes.')
        return
    if os.geteuid() != 0:
        raise SystemExit('Run the --apply step with sudo in your terminal')
    if Path('/sys/class/dmi/id/product_name').read_text().strip() != '20EQS59J07':
        raise RuntimeError('Unexpected machine')
    for process in ('v2ray', 'crond'):
        if sp.run(['pgrep', '-x', process], stdout=sp.DEVNULL).returncode == 0:
            raise RuntimeError('Selected retired program is active: ' + process)
    stage = Path('/var/backups') / time.strftime('desktop-enhancements-%Y%m%d-%H%M%S')
    stage.mkdir(mode=0o700)
    for source in (Path('/var/spool/cron'), Path('/etc/cron.d'), Path('/etc/modules-load.d/ntsync.conf'), Path('/usr/lib/modules-load.d/ntsync.conf')):
        if source.exists():
            dest = stage / source.relative_to('/')
            dest.parent.mkdir(parents=True, exist_ok=True)
            if source.is_dir():
                shutil.copytree(source, dest, symlinks=True)
            else:
                shutil.copy2(source, dest)
    (stage / 'packages-before.txt').write_text(sp.check_output(['pacman', '-Q'], text=True))
    print('Backup:', stage, flush=True)
    run(['pacman', '-S', '--needed', 'extra/udiskie', 'extra/bpftrace'])
    selected = [p for p in REMOVE if sp.run(['pacman', '-Qq', p], stdout=sp.DEVNULL, stderr=sp.DEVNULL).returncode == 0]
    if selected:
        run(['pacman', '-R', '--', *selected])
    for name in ['workstation-health-status.service', 'workstation-health-status.timer']:
        target = Path('/etc/systemd/system') / name
        if target.exists() or target.is_symlink():
            old = stage / 'etc/systemd/system' / name
            old.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(target, old, follow_symlinks=False)
        shutil.copyfile(REPO / 'configs/etc/systemd/system' / name, target)
        target.chmod(0o644)
    helper = Path('/usr/local/libexec/workstation-health-status')
    if helper.exists():
        shutil.copy2(helper, stage / 'health-helper-before')
    shutil.copyfile(REPO / 'scripts/system/workstation-health-status', helper)
    helper.chmod(0o755)
    run(['systemctl', 'daemon-reload'])
    run(['systemd-analyze', 'verify', '/etc/systemd/system/workstation-health-status.service', '/etc/systemd/system/workstation-health-status.timer'])
    run(['systemctl', 'enable', '--now', 'workstation-health-status.timer'])
    trim = sp.check_output(['systemctl', 'show', 'fstrim.service', '-p', 'ExecStart', '--value'], text=True)
    if 'argv[]=/usr/bin/fstrim --verbose / ;' not in trim:
        raise RuntimeError('TRIM command differs from the reviewed root-only service')
    # First real run of the already configured weekly root-only task.
    trimmed = sp.run(['systemctl', 'start', 'fstrim.service'])
    run(['systemctl', 'start', 'workstation-health-status.service'])
    if trimmed.returncode:
        raise RuntimeError('TRIM failed; the status page has the health snapshot')
    run(['pacman', '-Q', 'udiskie', 'bpftrace'])
    sp.run(['bpftrace', '-e', 'BEGIN { printf("bpftrace ready\\n"); exit(); }'], check=True, timeout=30)
    if Path('/run/user/1000/bus').exists():
        run(['runuser', '-u', 'eto', '--', 'env', 'XDG_RUNTIME_DIR=/run/user/1000',
             'DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus',
             'systemctl', '--user', 'start', 'udiskie.service'])
    print('Completed. Selected removals only; no recursive dependency cleanup.')
    print('No driver, VM, sleep, network or reboot changes. Open Control Deck → Состояние.')


if __name__ == '__main__':
    try:
        main()
    except (RuntimeError, OSError, sp.SubprocessError) as error:
        raise SystemExit('STOP: ' + str(error))
