#!/usr/bin/env python3
"""Apply the reviewed eight-point audit plan; root is only needed with --apply."""
import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import pwd
import shutil
import subprocess as sp
import tempfile


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None


def run(args, **kw):
    r = sp.run([str(x) for x in args], text=True, capture_output=True, **kw)
    if r.returncode:
        raise RuntimeError('Command failed: ' + ' '.join(map(str, args)) + '\n' + r.stderr[-1500:])
    return r.stdout


def write(path, content, mode):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix='.' + path.name, dir=path.parent)
    try:
        os.fchmod(fd, mode)
        with os.fdopen(fd, 'wb') as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def restore(backup):
    if os.geteuid() != 0:
        raise RuntimeError('Restore requires sudo')
    backup = backup.resolve()
    if not str(backup).startswith('/var/backups/audit-eight-') or backup.stat().st_uid != 0:
        raise RuntimeError('Not a root-owned audit backup')
    records = json.loads((backup / 'restore-manifest.json').read_text())
    for rec in reversed(records):
        p = Path(rec['path'])
        if not str(p).startswith('/etc/') or p.is_symlink():
            raise RuntimeError('Unexpected restore path')
        if rec['existed']:
            write(p, (backup / p.relative_to('/')).read_bytes(), rec['mode'])
            os.chown(p, rec['uid'], rec['gid'])
        else:
            p.unlink(missing_ok=True)
    for p in (backup / 'reviewed-pacnew/etc').rglob('*.pacnew'):
        dest = Path('/etc') / p.relative_to(backup / 'reviewed-pacnew/etc')
        if not dest.exists():
            write(dest, p.read_bytes(), 0o644)
    write(Path('/boot/grub/grub.cfg'), (backup / 'grub.cfg.before').read_bytes(), 0o600)
    old = json.loads((backup / 'firewall-input-before.json').read_text())
    live = json.loads(run(['nft', '-j', 'list', 'chain', 'inet', 'filter', 'input']))
    def ssh_rules(document):
        return [x['rule'] for x in document['nftables'] if 'rule' in x and any(
            e.get('match', {}).get('right') == 3427 for e in x['rule'].get('expr', []))]
    original, current = ssh_rules(old), ssh_rules(live)
    if len(original) != 1 or len(current) != 1:
        raise RuntimeError('Cannot safely identify SSH rule for rollback')
    rule = original[0]
    rule['handle'] = current[0]['handle']
    run(['nft', '-j', '-f', '-'], input=json.dumps({'nftables': [{'replace': {'rule': rule}}]}))
    run(['sshd', '-t'])
    run(['systemctl', 'daemon-reload'])
    sp.run(['systemctl', 'reset-failed', 'thinkfan.service'], capture_output=True)
    result = sp.run(['systemctl', 'restart', 'thinkfan.service'], capture_output=True)
    if result.returncode:
        print('Original Thinkfan configuration restored but service did not start; check BIOS auto mode.')
    print('Configurations and SSH rule restored. Removed cache/debug packages were not restored.')
    print('Boot audit parameter changes take effect after a normal reboot.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--restore', type=Path)
    args = parser.parse_args()
    if args.restore:
        restore(args.restore)
        return
    uid = int(os.environ.get('SUDO_UID', os.getuid()))
    home = Path(pwd.getpwuid(uid).pw_dir)
    stage = Path((home / '.local/state/workstation-audit-fixes/current').read_text().strip())
    plan = json.loads((stage / 'plan.json').read_text())
    print('Reviewed plan:', stage, flush=True)
    for line in plan['review']:
        print('-', line)
    print('Remove only orphan debug packages:', ', '.join(plan['debug_packages']))
    print('Cache: keep at least 2 versions and all packages modified within 7 days.')
    if not args.apply:
        print('Inspection only. Use --apply with sudo to apply.')
        return
    if os.geteuid() != 0:
        raise RuntimeError('--apply requires sudo')
    ssh_client = os.environ.get('SSH_CONNECTION', '').split()
    if ssh_client:
        import ipaddress
        if ipaddress.ip_address(ssh_client[0]) not in ipaddress.ip_network('192.168.0.0/24'):
            raise RuntimeError('Apply locally or from the home LAN; do not restrict your remote SSH route.')
    if Path('/var/lib/pacman/db.lck').exists():
        raise RuntimeError('Another package transaction is active; wait for completion.')
    # Validate the entire reviewed plan before any mutation.
    for item in plan['files']:
        path = Path(item['path'])
        payload = stage / item['payload']
        if not str(path).startswith('/etc/') or path.is_symlink() or not payload.resolve().is_relative_to(stage.resolve()):
            raise RuntimeError('Unexpected plan path: ' + str(path))
        if sha(path) != item['sha_before'] or sha(payload) != item['sha_after']:
            raise RuntimeError('A reviewed file changed; regenerate the plan: ' + str(path))
    for item in plan['pacnew']:
        p = Path(item['path'])
        if not str(p).startswith('/etc/') or not p.name.endswith('.pacnew') or p.is_symlink() or sha(p) != item['sha_before']:
            raise RuntimeError('Changed pacnew: ' + str(p))
    run(['nft', '--check', '--file', stage / 'payload/etc/nftables.conf'])
    run(['sshd', '-t'])
    run([home / '.local/bin/verify-kernel-stack'])
    backup = Path('/var/backups') / ('audit-eight-' + dt.datetime.now().strftime('%Y%m%d-%H%M%S-%f'))
    backup.mkdir(mode=0o700)
    records = []
    for item in plan['files']:
        p = Path(item['path'])
        rec = {'path': str(p), 'existed': p.exists()}
        if p.exists():
            old = backup / p.relative_to('/')
            old.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, old)
            rec.update(mode=p.stat().st_mode & 0o777, uid=p.stat().st_uid, gid=p.stat().st_gid)
        records.append(rec)
    grub = Path('/boot/grub/grub.cfg')
    shutil.copy2(grub, backup / 'grub.cfg.before')
    (backup / 'restore-manifest.json').write_text(json.dumps(records, indent=2))
    shutil.copy2(__file__, backup / 'finish-audit-eight.py')
    print('Backup:', backup, flush=True)
    print('Rollback: sudo python', backup / 'finish-audit-eight.py', '--restore', backup, flush=True)
    firewall = json.loads(run(['nft', '-j', 'list', 'chain', 'inet', 'filter', 'input']))
    (backup / 'firewall-input-before.json').write_text(json.dumps(firewall, indent=2))
    ssh_rules = [x['rule'] for x in firewall['nftables'] if 'rule' in x and
                 x['rule'].get('chain') == 'input' and any(
                     e.get('match', {}).get('right') == 3427 for e in x['rule'].get('expr', []))]
    if len(ssh_rules) != 1:
        raise RuntimeError('Expected exactly one SSH allow rule; no changes applied.')
    handle = ssh_rules[0]['handle']
    batch = f'replace rule inet filter input handle {handle} iifname "enp0s31f6" ip saddr 192.168.0.0/24 tcp dport 3427 accept comment "ssh-home-lan"\n'
    run(['nft', '--check', '-f', '-'], input=batch)
    for item in plan['files']:
        write(Path(item['path']), (stage / item['payload']).read_bytes(), item['mode'])
    try:
        run(['sshd', '-t'])
        run(['grub-mkconfig', '-o', backup / 'grub.cfg.new'], timeout=180)
        run(['grub-script-check', backup / 'grub.cfg.new'])
    except Exception:
        for rec in reversed(records):
            p = Path(rec['path'])
            if rec['existed']:
                write(p, (backup / p.relative_to('/')).read_bytes(), rec['mode'])
                os.chown(p, rec['uid'], rec['gid'])
            else:
                p.unlink(missing_ok=True)
        raise
    write(grub, (backup / 'grub.cfg.new').read_bytes(), grub.stat().st_mode & 0o777)
    run(['nft', '-f', '-'], input=batch)  # Only replace the SSH input rule.
    run(['systemctl', 'daemon-reload'])
    run(['systemd-analyze', 'verify', 'thinkfan.service'])
    run(['systemctl', 'reset-failed', 'thinkfan.service'])
    run(['systemctl', 'restart', 'thinkfan.service'])
    run(['systemctl', 'is-active', 'thinkfan.service'])
    print('Thinkfan active; sensor retries and bounded restart policy installed.', flush=True)
    # Keep all reviewed incoming files in the backup, including TPM policies
    # intentionally not adopted and the reflector-managed mirrorlist.
    for item in plan['pacnew']:
        p = Path(item['path'])
        dest = backup / 'reviewed-pacnew' / p.relative_to('/')
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(p, dest)
    orphans = set(run(['pacman', '-Qdtq']).splitlines())
    remove = [name for name in plan['debug_packages'] if name in orphans and name.endswith('-debug')]
    if remove:
        print(run(['pacman', '-R', '--noconfirm', '--', *remove]), flush=True)
    print(run(['paccache', '-r', '-k', '2', '--min-mtime', '7 days ago']), flush=True)
    run(['pacman', '-Dk'])
    print(run([home / '.local/bin/verify-kernel-stack']), flush=True)
    print(run(['nft', 'list', 'chain', 'inet', 'filter', 'input']), flush=True)
    print('Completed. Backup:', backup)
    print('No driver update, sleep test, VM/network restart, DNS restart or reboot performed.')
    print('Audit logging audit=1 takes effect after a normal reboot; auditd is already enabled.')


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        raise SystemExit('STOP: ' + str(e))
