#!/usr/bin/env python3
"""Apply scoped system review fixes, without package upgrades, reboot or VM changes."""
import argparse,datetime,json,os,shutil,subprocess as sp
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--apply',action='store_true');a=p.parse_args()
if not a.apply:raise SystemExit('Use sudo python ~/dotfiles/scripts/maintenance/finish-system-review.py --apply')
if os.geteuid()!=0:raise SystemExit('Requires sudo')
b=Path('/var/backups')/('system-review-'+datetime.datetime.now().strftime('%Y%m%d-%H%M%S'));b.mkdir(mode=0o700)
def run(args,check=True):return sp.run(args,check=check,text=True,capture_output=True)
def write(path,data):
 path=Path(path)
 if path.is_symlink():raise RuntimeError('Refusing symlink '+str(path))
 if path.exists():
  dest=b/path.relative_to('/');dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,dest)
 path.parent.mkdir(parents=True,exist_ok=True);tmp=path.with_suffix(path.suffix+'.review-tmp');tmp.write_text(data);tmp.chmod(0o644);tmp.replace(path)
print('Backup:',b,flush=True)
# Preserve all live network owners: insert only narrow rules in our own chain.
conf=Path('/etc/nftables.conf');before=conf.read_text();anchor='        iifname "lo" accept'
rules=['iifname "enp0s31f6" ip saddr 192.168.0.0/24 tcp dport 22000 accept comment "syncthing-home-tcp"','iifname "enp0s31f6" ip saddr 192.168.0.0/24 udp dport { 22000, 21027 } accept comment "syncthing-home-udp"']
after=before
for rule in rules:
 if rule not in after:after=after.replace(anchor,'        '+rule+'\n'+anchor)
if after!=before:
 if anchor not in before:raise RuntimeError('Unexpected firewall layout')
 candidate=b/'candidate.nft';candidate.write_text(after);run(['nft','-c','-f',str(candidate)])
 live=run(['nft','-j','list','chain','inet','filter','input']).stdout;(b/'firewall-before.json').write_text(live)
 for rule in rules:
  if rule.split('comment ')[1].strip('"') not in live:
   patch=b/('insert-'+str(rules.index(rule))+'.nft');patch.write_text('insert rule inet filter input '+rule+'\n');run(['nft','-f',str(patch)])
 write(conf,after)
# The ineffective option was ignored; remove it without forcing another sound backend.
f=Path('/etc/modprobe.d/audio-fix.conf')
if f.exists():write(f,'\n'.join(x for x in f.read_text().splitlines() if 'driver_selection=' not in x)+'\n')
# Limit a future stalled key refresh; retain signature verification.
write('/etc/systemd/system/dirmngr@etc-pacman.d-gnupg.service.d/90-resource-guard.conf','[Service]\nCPUQuota=25%\n')
run(['systemctl','daemon-reload'])
run(['systemctl','stop','dirmngr@etc-pacman.d-gnupg.service'])
run(['systemctl','reset-failed','archlinux-keyring-wkd-sync.service'],False)
run(['systemctl','start','--no-block','archlinux-keyring-wkd-sync.service'])
# Preserve two versions and all packages newer than seven days.
print(run(['paccache','--remove','--keep','2','--min-mtime','7 days ago']).stdout)
orphans=set(run(['pacman','-Qdtq'],False).stdout.split())
selected=sorted(orphans & {'capa-bin-debug','kimi-desktop-bin-debug','nvidia-580xx-settings-debug'})
if selected:print(run(['pacman','-R','--noconfirm','--',*selected]).stdout)
# Root-only diagnostics, with no hardware, VM or boot changes.
print(run(['/home/eto/.local/bin/workstation-root-audit']).stdout)
print('Completed. No package upgrade, energy profile change, driver change, firewall reload or reboot.')
print('wireless-regdb and firmware are deferred to the final update stage; KVM/CPU mitigations require separate guest validation.')
