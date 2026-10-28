#!/usr/bin/env python3
"""Install pinned Whisper Turbo models and a user-local Vulkan build."""
import argparse,hashlib,json,os,runpy,subprocess as sp,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];ASSETS=ROOT/'configs/dictation-compare'
HOME=Path.home();BASE=HOME/'.local/share/dictation-compare';TURBO=BASE/'turbo'
manifest=json.loads((ASSETS/'turbo.json').read_text())
helpers=runpy.run_path(str(ROOT/'scripts/maintenance/prepare-free-dictation.py'))

def checkout(url,path,revision):
 if not path.exists():
  sp.run(['git','clone','--no-checkout','--filter=blob:none',url,str(path)],check=True)
  sp.run(['git','-C',str(path),'checkout','--detach',revision],check=True)
 actual=sp.check_output(['git','-C',str(path),'rev-parse','HEAD'],text=True).strip()
 if actual!=revision:raise RuntimeError('Source revision mismatch; left unchanged: '+str(path))

def main():
 os.umask(0o077);p=argparse.ArgumentParser(description=__doc__);p.add_argument('--keep-source',action='store_true');args=p.parse_args()
 src=BASE/'whisper.cpp-src';headers=BASE/'spirv-headers-src';build=BASE/'whisper.cpp-build';deps=BASE/'build-deps'
 checkout('https://github.com/ggml-org/whisper.cpp.git',src,manifest['whisper_cpp_revision'])
 checkout('https://github.com/KhronosGroup/SPIRV-Headers.git',headers,manifest['spirv_headers_revision'])
 sp.run(['cmake','-S',str(headers),'-B',str(BASE/'spirv-headers-build'),'-DCMAKE_INSTALL_PREFIX='+str(deps)],check=True)
 sp.run(['cmake','--install',str(BASE/'spirv-headers-build')],check=True)
 sp.run(['cmake','-S',str(src),'-B',str(build),'-G','Ninja','-DCMAKE_PREFIX_PATH='+str(deps),'-DCMAKE_CXX_FLAGS=-I'+str(deps/'include'),'-DGGML_VULKAN=ON','-DCMAKE_BUILD_TYPE=Release','-DWHISPER_BUILD_TESTS=OFF'],check=True)
 sp.run(['cmake','--build',str(build),'-j','4'],check=True)
 candidate=build/'bin/whisper-compare.new'
 sp.run(['c++','-O2','-std=c++17','-I'+str(src/'include'),'-I'+str(src/'ggml/include'),str(ROOT/'scripts/maintenance/whisper-compare.cpp'),'-L'+str(build/'bin'),'-Wl,-rpath,'+str(build/'bin'),'-lwhisper','-lggml','-lggml-base','-o',str(candidate)],check=True)
 candidate.replace(build/'bin/whisper-compare')
 final=TURBO/'models/ggml-codeswitch-q5_0.bin';expected=manifest.get('converted_sha256')
 ready=final.exists() and expected and hashlib.file_digest(final.open('rb'),'sha256').hexdigest()==expected
 for item in manifest['files']:
  if ready and not args.keep_source and item['destination'].startswith('codeswitch-source/'):continue
  helpers['download'](item,TURBO/item['destination'])
 if not ready:
  python=HOME/'.local/share/hyprwhspr/venv/bin/python';f16=final.with_name('ggml-codeswitch-f16.bin')
  sp.run([str(python),str(ROOT/'scripts/maintenance/convert-whisper-safetensors.py'),str(TURBO/'codeswitch-source'),str(f16)],check=True)
  sp.run([str(build/'bin/whisper-quantize'),str(f16),str(final),'q5_0'],check=True)
  actual=hashlib.file_digest(final.open('rb'),'sha256').hexdigest()
  if expected and actual!=expected:raise RuntimeError('Converted model checksum mismatch; source files retained')
  f16.unlink()
  if not args.keep_source:(TURBO/'codeswitch-source/model.safetensors').unlink()
 cfg=json.loads((HOME/'.config/hyprwhspr/config.json').read_text());TURBO.mkdir(parents=True,exist_ok=True)
 (TURBO/'prompt.txt').write_text(cfg.get('whisper_prompt',''))
 for name in ['dictation-turbo-engine','dictation-turbo-install']:helpers['link'](ROOT/'scripts/local-bin'/name,HOME/'.local/bin'/name)
 print('Turbo ready. Open vc; choose Whisper Vulkan. No mic, autostart or driver changes.')
if __name__=='__main__':main()
