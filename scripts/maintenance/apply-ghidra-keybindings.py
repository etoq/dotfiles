#!/usr/bin/env python3
"""Install the reviewed Linux CodeBrowser key profile, preserving all other XML."""
import argparse
from datetime import datetime
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import xml.etree.ElementTree as ET

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--apply', action='store_true')
parser.add_argument('--tool', type=Path, default=Path.home() / '.config/ghidra/ghidra_12.2_DEV/tools/_code_browser.tcd')
args = parser.parse_args()
profile = Path(__file__).resolve().parents[2] / 'configs/ghidra/ida-linux.kbxml'
new = ET.parse(profile).getroot()
assert new.tag == 'CATEGORY' and new.get('NAME') == 'Key Bindings'
original = args.tool.read_bytes()
root = ET.fromstring(original)
assert root.find('./TOOL').get('TOOL_NAME') == 'CodeBrowser'
pattern = rb'<CATEGORY NAME="Key Bindings">.*?</CATEGORY>'
newline = b'\r\n' if b'\r\n' in original else b'\n'
replacement = ET.tostring(new, encoding='UTF-8').replace(b'\n', newline)
updated, count = re.subn(pattern, lambda _: replacement, original, flags=re.S)
if count != 1:
    raise SystemExit('Expected exactly one Key Bindings category; nothing changed.')
ET.fromstring(updated)
if not args.apply:
    print(f'Plan: apply {len(new)} bindings to {args.tool}; use --apply.')
elif updated == original:
    print('Key profile already installed.')
else:
    running = subprocess.run(['pgrep', '-f', 'ghidra.GhidraRun|ghidra.Ghidra'], capture_output=True)
    if running.returncode == 0:
        raise SystemExit('Close Ghidra before applying; its saved settings could overwrite this file.')
    backup = Path.home() / '.local/state/ghidra-keybindings-backup' / datetime.now().strftime('%Y%m%d-%H%M%S')
    backup.mkdir(parents=True, mode=0o700)
    shutil.copy2(args.tool, backup / args.tool.name)
    fd, path = tempfile.mkstemp(prefix='.keys-', dir=args.tool.parent)
    try:
        with os.fdopen(fd, 'wb') as out:
            out.write(updated)
            out.flush()
            os.fsync(out.fileno())
        shutil.copymode(args.tool, path)
        if args.tool.read_bytes() != original:
            raise RuntimeError('Tool settings changed concurrently; refusing replacement.')
        os.replace(path, args.tool)
    finally:
        Path(path).unlink(missing_ok=True)
    print(f'Applied {len(new)} bindings. Backup: {backup}')
