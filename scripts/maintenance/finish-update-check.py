#!/usr/bin/env python3
"""Verify updated boot assets and remove the idle dirmngr runtime false alarm."""
import argparse,datetime,hashlib,json,os,pwd,shutil,subprocess as sp
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--apply',action='store_true');a=p.parse_args()
if not a.apply:raise SystemExit('Use sudo python ~/dotfiles/scripts/maintenance/finish-update-check.py --apply')
if os.geteuid()!=0:raise SystemExit('Requires sudo to read initramfs and adjust the system drop-in')
def run(args):
 r=sp.run(args,capture_output=True,text=True,timeout=120)
 if r.returncode:raise RuntimeError(r.stderr.strip() or r.stdout.strip() or 'Failed: '+args[0])
 return r.stdout.strip()
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
print(run(['/home/eto/.local/bin/verify-kernel-stack']),flush=True)
images=[]
for kernel in ['linux','linux-lts']:
 for name in ['vmlinuz-'+kernel,'initramfs-'+kernel+'.img']:
  source=Path('/boot')/name;target=Path('/boot/efi/EFI/ARCH')/name
  if not target.is_file() or sha(source)!=sha(target):raise SystemExit('STOP: EFI copy missing or different: '+name)
  images.append(name);print('OK: EFI copy matches '+name,flush=True)
guard=Path('/etc/systemd/system/dirmngr@etc-pacman.d-gnupg.service.d/90-resource-guard.conf')
backup=None
if guard.exists():
 if guard.is_symlink():raise SystemExit('STOP: unexpected guard symlink')
 before=guard.read_text();after='\n'.join(l for l in before.splitlines() if not l.strip().startswith('RuntimeMaxSec='))+'\n'
 if before!=after:
  backup=Path('/var/backups')/('update-check-'+datetime.datetime.now().strftime('%Y%m%d-%H%M%S'));backup.mkdir(mode=0o700)
  shutil.copy2(guard,backup/'90-resource-guard.conf');temporary=guard.with_suffix('.tmp');temporary.write_text(after);temporary.chmod(0o644);temporary.replace(guard)
  print('Backup:',backup,flush=True)
run(['systemctl','daemon-reload'])
# Clear the timeout caused by the previous guard; do not restart GnuPG or its clients.
run(['systemctl','reset-failed','dirmngr@etc-pacman.d-gnupg.service'])
properties=run(['systemctl','show','dirmngr@etc-pacman.d-gnupg.service','-p','RuntimeMaxUSec','-p','CPUQuotaPerSecUSec'])
if 'RuntimeMaxUSec=infinity' not in properties:raise SystemExit('STOP: another runtime limit remains: '+properties)
print('OK: GnuPG idle runtime limit removed; CPU guard preserved.',flush=True)
uid=int(os.environ.get('SUDO_UID','1000'));group=pwd.getpwuid(uid).pw_gid
out=Path('/run')/f'workstation-update-final-{uid}.json'
if out.is_symlink() or (out.exists() and out.stat().st_uid!=0):raise SystemExit('Unsafe report path')
report={'checked_at':datetime.datetime.now().astimezone().isoformat(),'kernel_stack':'verified','efi_copies':images,'dirmngr':properties,'running_kernel':os.uname().release,'reboot_needed':not (Path('/usr/lib/modules')/os.uname().release/'pkgbase').exists()}
out.write_text(json.dumps(report,indent=2)+'\n');os.chown(out,0,group);out.chmod(0o640)
print('Report:',out)
print('Completed. No reboot, sleep test, driver or encryption change performed.')
print('Save work, then reboot manually into Linux LTS.')
