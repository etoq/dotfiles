#!/usr/bin/env python3
"""Allow LocalSend only from the home LAN; do not reload unrelated firewall tables."""
import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import shutil
import subprocess as sp
import tempfile

CONFIG = Path('/etc/nftables.conf')
BACKUPS = Path('/var/backups')
ANCHOR = '        tcp dport 3427 accept\n'
RULES = [f'iifname "enp0s31f6" ip saddr 192.168.0.0/24 {protocol} dport 53317 accept comment "localsend-home-lan-{protocol}"'
         for protocol in ('tcp', 'udp')]


def candidate(original):
    if original.count(ANCHOR) != 1:
        raise RuntimeError('Unexpected firewall layout; no changes made.')
    missing = [rule for rule in RULES if '        ' + rule + '\n' not in original]
    return original.replace(ANCHOR, ''.join('        ' + rule + '\n' for rule in missing) + ANCHOR)


def nft(*args, text=None):
    return sp.run(['/usr/bin/nft', *args], input=text, text=True, capture_output=True, check=True).stdout


def atomic_write(path, text, mode):
    fd, temporary = tempfile.mkstemp(prefix='.localsend-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as output:
            output.write(text)
            output.flush()
            os.fsync(output.fileno())
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    original = CONFIG.read_text()
    updated = candidate(original)
    if not args.apply:
        print('Planned input rules (Ethernet, home LAN only):\n' + '\n'.join(RULES))
        print('Apply: sudo python ~/dotfiles/scripts/maintenance/finish-localsend-firewall.py --apply')
        return
    if os.geteuid() != 0:
        raise RuntimeError('Run this command with sudo.')
    if CONFIG.is_symlink():
        raise RuntimeError('Unexpected symlink for nftables.conf; no changes made.')
    # Check the saved configuration, without loading it or touching libvirt/Throne tables.
    nft('--check', '--file', '-', text=updated)
    active = json.loads(nft('--json', 'list', 'chain', 'inet', 'filter', 'input'))
    comments = {row.get('rule', {}).get('comment') for row in active['nftables']}
    additions = [rule for rule in RULES if rule.rsplit('"', 2)[1] not in comments]
    batch = ''.join('insert rule inet filter input ' + rule + '\n' for rule in additions)
    if batch:
        nft('--check', '--file', '-', text=batch)
    backup = BACKUPS / ('localsend-firewall-' + datetime.now().strftime('%Y%m%d-%H%M%S-%f'))
    backup.mkdir(mode=0o700)
    shutil.copy2(CONFIG, backup / 'nftables.conf')
    (backup / 'input-before.json').write_text(json.dumps(active, indent=2))
    mode = CONFIG.stat().st_mode & 0o777
    atomic_write(CONFIG, updated, mode)
    try:
        if batch:
            # nft applies a batch as a single transaction; all other chains stay intact.
            nft('--file', '-', text=batch)
    except Exception:
        atomic_write(CONFIG, original, mode)
        raise
    result = nft('list', 'chain', 'inet', 'filter', 'input')
    for line in result.splitlines():
        if 'localsend-home-lan-' in line:
            print(line.strip())
    print('Completed. TCP/UDP 53317 allowed from 192.168.0.0/24 on enp0s31f6.')
    print('Rules saved for the next boot. Backup:', backup)
    print('No firewall reload, network restart, VM changes or reboot performed.')


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, RuntimeError, sp.CalledProcessError) as error:
        print('STOP:', error)
        if isinstance(error, sp.CalledProcessError):
            print(error.stderr.strip())
        raise SystemExit(1)
