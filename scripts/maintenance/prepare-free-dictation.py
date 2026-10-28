#!/usr/bin/env python3
"""Replay the pinned local-only dictation comparison; no privileged operations."""
import argparse,hashlib,json,os,shutil,subprocess as sp,tempfile,urllib.request
from pathlib import Path
H=Path.home();ROOT=Path(__file__).resolve().parents[2];ASSETS=ROOT/'configs/dictation-compare';MANIFEST=json.loads((ASSETS/'install.json').read_text())

def valid(path,item):
 if not path.is_file():return False
 if item.get('size_bytes') and path.stat().st_size!=item['size_bytes']:return False
 if item.get('sha256'):
  with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()==item['sha256']
 content=path.read_bytes();return hashlib.sha1(b'blob '+str(len(content)).encode()+b'\0'+content).hexdigest()==item['git_oid']

def download(item,path):
 if valid(path,item):return
 path.parent.mkdir(parents=True,exist_ok=True);part=path.with_suffix(path.suffix+'.part')
 with urllib.request.urlopen(item['url'],timeout=90) as src,part.open('wb') as out:
  while chunk:=src.read(1024*1024):out.write(chunk)
 if not valid(part,item):raise RuntimeError('Checksum mismatch: '+str(path))
 part.rename(path);print('Verified',path,flush=True)

def link(source,dest):
 dest.parent.mkdir(parents=True,exist_ok=True)
 if dest.is_symlink() and dest.resolve()==source.resolve():return
 if dest.exists() or dest.is_symlink():raise RuntimeError('Refusing to overwrite '+str(dest))
 dest.symlink_to(source)

def configure():
 for name in ['handy','hyprwhspr','dictation-control','dictation-paste','dictation-compare','dictation-compare-engine','dictation-compare-install']:
  link(ROOT/'scripts/local-bin'/name,H/'.local/bin'/name)
 for name in ['terms.txt','phrases.json']:link(ASSETS/name,H/'.config/dictation-compare'/name)
 link(ROOT/'configs/systemd/user/hyprwhspr.service',H/'.config/systemd/user/hyprwhspr.service')
 p=H/'.local/share/com.pais.handy/settings_store.json'
 if not p.exists():sp.run([str(H/'.local/bin/handy'),'--list-models','--json'],check=True,stdout=sp.DEVNULL)
 d=json.loads(p.read_text());backup=p.with_name('settings_store.pre-comparison.json')
 if not backup.exists():shutil.copyfile(p,backup)
 d['settings'].update(selected_model='parakeet-tdt-0.6b-v3',onboarding_completed=True,selected_language='ru',overlay_style='none',autostart_enabled=False,always_on_microphone=False,start_hidden=False,post_process_enabled=False,update_checks_enabled=False,app_language='ru',theme='dark',custom_words=(ASSETS/'terms.txt').read_text().splitlines(),transcribe_accelerator='cpu',ort_accelerator='cpu',recording_retention_period='never',auto_submit=False,paste_method='external_script',external_script_path=str(H/'.local/bin/dictation-paste'),clipboard_handling='copy_to_clipboard',shortcut_activation='toggle')
 d['settings']['bindings']['transcribe']['current_binding']='ctrl+alt+shift+f12';p.write_text(json.dumps(d,ensure_ascii=False,indent=2))
 cfg=H/'.config/hyprwhspr/config.json';cfg.parent.mkdir(parents=True,exist_ok=True)
 if not cfg.exists():shutil.copyfile(ASSETS/'hyprwhspr.json',cfg);cfg.chmod(0o600)
 print('Configured. No autostart, recording, network API or driver changes.')

def main():
 os.umask(0o077);parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--configure-only',action='store_true');args=parser.parse_args()
 if not args.configure_only:
  cache=H/'.local/share/dictation-compare/downloads';runtime=MANIFEST['handy'];image=cache/Path(runtime['url']).name;download(runtime,image);image.chmod(0o755)
  destination=H/'.local/opt/handy/0.9.8'
  if not destination.exists():
   destination.parent.mkdir(parents=True,exist_ok=True)
   with tempfile.TemporaryDirectory(dir=destination.parent) as tmp:
    sp.run([str(image),'--appimage-extract'],cwd=tmp,stdout=sp.DEVNULL,check=True);Path(tmp,'squashfs-root').rename(destination)
  src=H/'.local/share/hyprwhspr/src';pin=MANIFEST['hyprwhspr']
  if not src.exists():
   sp.run(['git','clone','--no-checkout',pin['repository'],str(src)],check=True);sp.run(['git','-C',str(src),'checkout','--detach',pin['revision']],check=True)
  actual=sp.check_output(['git','-C',str(src),'rev-parse','HEAD'],text=True).strip()
  if actual!=pin['revision']:raise RuntimeError('Existing hyprwhspr source has another revision; left unchanged.')
  env=H/'.local/share/hyprwhspr/venv'
  if not (env/'bin/python').exists():sp.run(['uv','venv','--python','3.13','--system-site-packages',str(env)],check=True)
  sp.run(['uv','pip','install','--python',str(env/'bin/python'),'-r',str(ASSETS/'requirements.txt')],check=True)
  for item in MANIFEST['models']:download(item,H/item['destination'])
 configure()
if __name__=='__main__':main()
