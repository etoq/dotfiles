#!/usr/bin/python
"""Start the authorized emergency 470 rollback outside the broken X11 session."""
import os
from pathlib import Path
import subprocess as sp
import sys

HERE = Path(__file__).resolve().parent


def main():
    if os.geteuid() != 0:
        raise RuntimeError('Use sudo from the visible software-rendered recovery terminal')
    print('Starting verified NVIDIA 470 rollback. A normal reboot follows ONLY after all checks succeed.', flush=True)
    print('Do not power off. The service continues independently of the damaged graphical session.', flush=True)
    state = sp.run(['pacman', '-Q', 'nvidia-470xx-utils'], capture_output=True, text=True)
    mode = '--finish470-unattended' if state.returncode == 0 else '--restore470-unattended'
    sp.run(['systemd-run', '--unit=workstation-nvidia-recovery', '--collect',
            '--property=Type=oneshot', '--property=TimeoutStartSec=1800',
            '--property=ExecStartPost=/usr/bin/systemctl reboot', '--',
            '/usr/bin/python', str(HERE / 'nvidia-transition.py'), mode], check=True)
    print('Live recovery log follows. No package questions remain after the sudo password.', flush=True)
    sp.run(['journalctl', '--follow', '--no-pager', '--unit=workstation-nvidia-recovery.service'])


if __name__ == '__main__':
    try:
        main()
    except (RuntimeError, OSError, sp.CalledProcessError) as error:
        print('STOP:', error, file=sys.stderr)
        sys.exit(1)
