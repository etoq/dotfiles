#!/usr/bin/env python3
"""Build a reversible private Wispr runtime; never change package-owned files."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess as sp
import tempfile

H = Path.home()
SOURCE = Path('/opt/wispr-flow-appimage')
DEST = H / '.local/lib/wispr-context-runtime'
REL = Path('usr/lib/wispr-flow')


def patch_bundle(text, bridge):
    modifications = [
        ('V=()=>y("GetActiveAppInfo",e=>e.ActiveAppInfo?.payload,G,{timeoutOverride:300})',
         'V=()=>y("GetActiveAppInfo",e=>e.ActiveAppInfo?.payload,G,{timeoutOverride:300}).then(e=>require(BRIDGE).active(e))'),
        ('X=()=>y("GetAppInfo",e=>e.AppInfo?.payload,{appName:"unknown",bundleId:"unknown",url:"unknown",windowX:0,windowY:0,windowWidth:0,windowHeight:0})',
         'X=()=>y("GetAppInfo",e=>e.AppInfo?.payload,{appName:"unknown",bundleId:"unknown",url:"unknown",windowX:0,windowY:0,windowWidth:0,windowHeight:0}).then(e=>require(BRIDGE).active(e))')]
    for old, new in modifications:
        if text.count(old) != 1:
            raise RuntimeError('Unsupported Wispr version: patch marker changed; original untouched.')
        text = text.replace(old, new.replace('BRIDGE', json.dumps(str(bridge))))
    return text


def patch_asar(source, destination, bridge):
    with source.open('rb') as stream:
        header = struct.unpack('<4I', stream.read(16))
        tree = json.loads(stream.read(header[3]))
        base = 8 + header[1]
        data = bytearray()
        patched = [False]
        def visit(folder, prefix=''):
            for name, item in folder.get('files', {}).items():
                name = prefix + name
                if 'files' in item:
                    visit(item, name + '/')
                elif 'offset' in item:
                    stream.seek(base + int(item['offset'])); content = stream.read(item['size'])
                    if name == '.webpack/main/index.js':
                        patched[0] = True
                        content = patch_bundle(content.decode(), bridge).encode()
                        if 'integrity' in item:
                            size = item['integrity'].get('blockSize', 4194304)
                            item['integrity'] = {'algorithm': 'SHA256', 'hash': hashlib.sha256(content).hexdigest(), 'blockSize': size,
                                'blocks': [hashlib.sha256(content[i:i+size]).hexdigest() for i in range(0, len(content), size)]}
                    item['offset'] = str(len(data)); item['size'] = len(content); data.extend(content)
        visit(tree)
        if not patched[0]:
            raise RuntimeError('Wispr main bundle not found; refusing to build an unpatched copy.')
        encoded = json.dumps(tree, separators=(',', ':')).encode()
        padded = (len(encoded) + 3) // 4 * 4
        with destination.open('wb') as out:
            out.write(struct.pack('<4I', 4, padded + 8, padded + 4, len(encoded)))
            out.write(encoded); out.write(b'\0' * (padded - len(encoded))); out.write(data)


def main():
    package = SOURCE / REL
    if not (package / 'resources/app.asar').exists():
        raise SystemExit('Packaged Wispr AppImage not found.')
    root = Path(__file__).resolve().parents[2]
    bridge = H / '.local/libexec/wispr-context.cjs'
    bridge.parent.mkdir(parents=True, exist_ok=True)
    if bridge.is_symlink(): bridge.unlink()
    if bridge.exists(): raise SystemExit('Refusing to replace an unrelated bridge file.')
    bridge.symlink_to(root / 'scripts/lib/wispr-context.cjs')
    source = package / 'resources/app.asar'
    try:
        current = json.loads((DEST / 'manifest.json').read_text())
        if current.get('patch') == 1 and current.get('source_bytes') == source.stat().st_size and current.get('source_mtime_ns') == source.stat().st_mtime_ns:
            print('Private context runtime already matches the installed package.')
            return
    except (OSError, ValueError):
        pass
    DEST.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix='.wispr-context-', dir=DEST.parent))
    try:
        app = stage / REL; app.mkdir(parents=True)
        for entry in package.iterdir():
            if entry.name == 'resources':
                resources = app / 'resources'; resources.mkdir()
                for asset in entry.iterdir():
                    if asset.name == 'app.asar': patch_asar(asset, resources / asset.name, bridge)
                    else: (resources / asset.name).symlink_to(asset)
            elif entry.name == 'wispr-flow':
                sp.run(['cp', '--reflink=auto', str(entry), str(app / entry.name)], check=True)
                (app / entry.name).chmod(0o755)
            else: (app / entry.name).symlink_to(entry)
        launcher = Path('/usr/bin/wispr-flow').resolve()
        shutil.copyfile(launcher, stage / 'AppRun'); (stage / 'AppRun').chmod(0o755)
        source = package / 'resources/app.asar'
        (stage / 'manifest.json').write_text(json.dumps({'source_bytes': source.stat().st_size, 'source_mtime_ns': source.stat().st_mtime_ns, 'patch': 1}))
        previous = DEST.with_name(DEST.name + '.previous')
        if previous.exists(): shutil.rmtree(previous)
        if DEST.exists(): DEST.rename(previous)
        stage.rename(DEST)
        print('Installed private context runtime:', DEST)
        print('Rollback: rename its manifest.json; the wrapper uses the original package.')
    finally:
        if stage.exists(): shutil.rmtree(stage)


if __name__ == '__main__': main()
