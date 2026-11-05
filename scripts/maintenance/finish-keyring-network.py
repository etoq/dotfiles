#!/usr/bin/env python3
"""Repair only system pacman GnuPG DNS; verify WKD before allowing updates."""
import argparse,datetime,os,shutil,subprocess as sp
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--apply',action='store_true');a=p.parse_args()
if not a.apply:raise SystemExit('Use sudo python ~/dotfiles/scripts/maintenance/finish-keyring-network.py --apply')
if os.geteuid()!=0:raise SystemExit('Requires sudo')
f=Path('/etc/pacman.d/gnupg/dirmngr.conf')
if f.is_symlink():raise SystemExit('Refusing unexpected config symlink')
b=Path('/var/backups')/('keyring-network-'+datetime.datetime.now().strftime('%Y%m%d-%H%M%S'));b.mkdir(mode=0o700)
old=f.read_text() if f.exists() else '';existed=f.exists()
if existed:shutil.copy2(f,b/'dirmngr.conf')
(b/'config-existed').write_text(str(existed))
print('Backup:',b,flush=True)
sp.run(['systemctl','stop','archlinux-keyring-wkd-sync.service'],check=True)
sp.run(['systemctl','stop','dirmngr@etc-pacman.d-gnupg.service'],check=True)
lines=[l for l in old.splitlines() if l.strip().split(' ',1)[0] not in {'standard-resolver','recursive-resolver','use-tor','no-use-tor'}]
text='\n'.join(lines)+'\n# System package keys: use the configured system DNS, not auto-detected Tor.\nstandard-resolver\nno-use-tor\n'
tmp=f.with_suffix('.review-tmp');tmp.write_text(text);tmp.chmod(0o600);tmp.replace(f)
try:
 r=sp.run(['gpg-connect-agent','--homedir','/etc/pacman.d/gnupg','--dirmngr','WKD_GET --quick allan@archlinux.org','/bye'],capture_output=True,timeout=40)
 if r.returncode or b'OK' not in r.stdout.splitlines() or any(l.startswith(b'ERR ') for l in r.stdout.splitlines()):raise RuntimeError('WKD check failed')
except Exception:
 sp.run(['systemctl','stop','dirmngr@etc-pacman.d-gnupg.service'],capture_output=True)
 if existed:f.write_text(old);f.chmod(0o600)
 else:f.unlink(missing_ok=True)
 raise SystemExit('STOP: WKD did not pass; previous DNS configuration restored. Do not update yet.')
print('OK: system GnuPG downloaded a public Arch WKD key.',flush=True)
sp.run(['systemctl','reset-failed','archlinux-keyring-wkd-sync.service'],check=True)
sp.run(['systemctl','start','--no-block','archlinux-keyring-wkd-sync.service'],check=True)
print('Key refresh started. No keys deleted, no signature checks disabled, no packages upgraded.')
