#!/usr/bin/python
"""Install pinned upstream ImHex and the selected Bibata theme as the user."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess as sp
import tarfile
import urllib.request

REPO = Path(__file__).resolve().parents[2]
HOME = Path.home()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    if not args.apply:
        print('User assets: ImHex 1.38.1 and Bibata Modern Classic 2.0.7. Install with --apply.')
        return
    if os.geteuid() == 0:
        raise SystemExit('Run as the desktop user, without sudo')
    records = json.loads((REPO / 'configs/desktop-assets.json').read_text())
    cache = HOME / '.cache/workstation-desktop-assets'
    cache.mkdir(parents=True, exist_ok=True)
    for name, record in records.items():
        archive = cache / record['file']
        if not archive.exists():
            temporary = archive.with_suffix('.part')
            with urllib.request.urlopen(record['url'], timeout=60) as response, temporary.open('wb') as out:
                shutil.copyfileobj(response, out)
            temporary.replace(archive)
        with archive.open('rb') as stream:
            if hashlib.file_digest(stream, 'sha256').hexdigest() != record['sha256']:
                raise RuntimeError('Upstream asset checksum differs: ' + name)
        if name == 'imhex':
            target = HOME / '.local/opt/imhex' / record['version']
            target.mkdir(parents=True, exist_ok=True)
            if not (target / 'squashfs-root/AppRun').is_file():
                archive.chmod(0o755)
                sp.run([str(archive), '--appimage-extract'], cwd=target, stdout=sp.DEVNULL, check=True)
            icons = HOME / '.local/share/icons/hicolor/scalable/apps'
            icons.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(target / 'squashfs-root/imhex.svg', icons / 'imhex.svg')
        else:
            icons = HOME / '.local/share/icons'
            icons.mkdir(parents=True, exist_ok=True)
            with tarfile.open(archive) as bundle:
                members = [m for m in bundle.getmembers() if Path(m.name).parts and Path(m.name).parts[0] == 'Bibata-Modern-Classic']
                if not members:
                    raise RuntimeError('Selected cursor theme is missing')
                bundle.extractall(icons, members=members, filter='data')
        print('Installed verified user asset:', name, record['version'])


if __name__ == '__main__':
    main()
