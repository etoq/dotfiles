#!/usr/bin/env python3
"""Apply the Black Tiffany RE workspace without changing projects or analysis data."""
import argparse
import copy
from datetime import datetime
from pathlib import Path
import os
import re
import shutil
import subprocess
import tempfile
import xml.etree.ElementTree as ET

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--apply', action='store_true')
parser.add_argument('--tool', type=Path, default=Path.home()/'.config/ghidra/ghidra_12.2_DEV/tools/_code_browser.tcd')
args = parser.parse_args()
original = args.tool.read_bytes()
root = ET.fromstring(original)
tool = root.find('TOOL')
if tool is None or tool.get('TOOL_NAME') != 'CodeBrowser':
    raise SystemExit('Expected CodeBrowser tool; nothing changed.')
options = tool.find('OPTIONS')
category = options.find("CATEGORY[@NAME='Decompiler']")
if category is None:
    category = ET.SubElement(options, 'CATEGORY', NAME='Decompiler')
for name, kind, value in (
    ('Analysis.Eliminate unreachable code', 'boolean', 'false'),
    ('Display.Disable printing of type casts', 'boolean', 'false'),
    ('Display.Display Line Numbers', 'boolean', 'true'),
    ('Cache Size (Functions)', 'int', '30'),
):
    state = next((s for s in category if s.get('NAME') == name), None)
    if state is None:
        state = ET.SubElement(category, 'STATE', NAME=name)
    state.set('TYPE', kind)
    state.set('VALUE', value)
    state.set('LAST_REGISTERED', datetime.now().date().isoformat())

# Reuse native provider IDs/state. Keep all floating/hidden providers untouched.
dock = tool.find('ROOT_NODE')
old_layout = dock.find('SPLIT_NODE')
if old_layout is None:
    raise SystemExit('Expected docked workspace; nothing changed.')
providers = list(dock.iter('COMPONENT_INFO'))
def node(names, selected=0):
    result = ET.Element('COMPONENT_NODE', TOP_INFO=str(selected))
    for name in names:
        matches = [p for p in providers if p.get('NAME') == name and p.get('GROUP') != 'disconnected' and (name != 'Defined Strings' or p.get('OWNER') == 'DefinedStringsPlugin')]
        if len(matches) != 1:
            raise SystemExit(f'Expected one docked provider: {name}')
        info = copy.deepcopy(matches[0])
        info.set('ACTIVE', 'true')
        result.append(info)
    return result

def split(orientation, width, height, divider, first, second):
    result = ET.Element('SPLIT_NODE', WIDTH=str(width), HEIGHT=str(height),
                        DIVIDER_LOCATION=str(divider), ORIENTATION=orientation)
    result.extend((first, second))
    return result

sidebar = node(['Functions Window', 'DataTypes Provider', 'Symbol Tree', 'Program Tree'])
code = split('HORIZONTAL', 1550, 740, 450, node(['Listing']), node(['Decompiler']))
bottom = node(['Defined Strings', 'Bookmarks', 'Console'])
main = split('VERTICAL', 1550, 940, 790, code, bottom)
layout = split('HORIZONTAL', 1840, 940, 195, sidebar, main)
# Preserve less-used providers in the dock model, hidden until requested.
used = {p.get('INSTANCE_ID') for p in layout.iter('COMPONENT_INFO')}
for p in old_layout.iter('COMPONENT_INFO'):
    if p.get('INSTANCE_ID') not in used:
        hidden = copy.deepcopy(p)
        hidden.set('ACTIVE', 'false')
        bottom.append(hidden)
dock.remove(old_layout)
dock.insert(0, layout)
for window in list(dock.findall('WINDOW_NODE')):
    for parent in list(window.iter()):
        for child in list(parent):
            if child.tag == 'COMPONENT_INFO' and child.get('INSTANCE_ID') in used:
                parent.remove(child)
    if not list(window.iter('COMPONENT_INFO')):
        dock.remove(window)
dock.set('FOCUSED_OWNER', 'DecompilePlugin')
dock.set('FOCUSED_NAME', 'Decompiler')
dock.set('WIDTH', '1840')
dock.set('HEIGHT', '1000')
dock.set('X_POS', '40')
dock.set('Y_POS', '50')

# Replace only the Decompiler category and the main dock tree, preserving other bytes.
newline = b'\r\n' if b'\r\n' in original else b'\n'
def xml_bytes(element):
    return ET.tostring(element, encoding='utf-8').replace(b'\n', newline)
updated, count = re.subn(rb'<CATEGORY NAME="Decompiler">.*?</CATEGORY>',
                         lambda _: xml_bytes(category), original, count=1, flags=re.S)
if count != 1:
    raise SystemExit('Expected saved Decompiler category; nothing changed.')
updated, count = re.subn(rb'<ROOT_NODE\b.*?</ROOT_NODE>', lambda _: xml_bytes(dock),
                         updated, count=1, flags=re.S)
if count != 1:
    raise SystemExit('Expected one dock root; nothing changed.')
# Keep the narrow Functions pane readable: name and address, full signature in C.
for pref in tool.findall('.//PREFERENCE_STATE'):
    if 'functionwindow.FunctionTableModel:' not in pref.get('NAME', ''):
        continue
    for column in pref.findall('.//COLUMN'):
        name = column.get('NAME', '')
        is_name = 'NameTableColumn.Name' in name or name.endswith('LabelTableColumn')
        is_address = 'AddressTableColumn' in name
        column.set('VISIBLE', 'true' if is_name or is_address else 'false')
        if is_name or is_address:
            column.set('WIDTH', '235' if is_name else '100')
    pattern = rb'<PREFERENCE_STATE NAME="' + re.escape(pref.get('NAME').encode()) + rb'">.*?</PREFERENCE_STATE>'
    updated, count = re.subn(pattern, lambda _: xml_bytes(pref), updated, count=1, flags=re.S)
    if count != 1:
        raise SystemExit('Expected function table settings; nothing changed.')
ET.fromstring(updated)
if not args.apply:
    print(f'Plan: C/assembly side by side, functions/types, strings/bookmarks, casts and line numbers: {args.tool}')
    raise SystemExit()
if subprocess.run(['pgrep', '-f', r'^.*java .*ghidra\.Ghidra ghidra\.GhidraRun'], capture_output=True).returncode == 0:
    raise SystemExit('Close Ghidra first; it can overwrite saved settings.')
backup = Path.home()/'.local/state/ghidra-profile-backups'/datetime.now().strftime('%Y%m%d-%H%M%S')
backup.mkdir(parents=True, mode=0o700)
shutil.copy2(args.tool, backup/args.tool.name)
fd, tmp = tempfile.mkstemp(prefix='.profile-', dir=args.tool.parent)
try:
    with os.fdopen(fd, 'wb') as out:
        out.write(updated)
        out.flush()
        os.fsync(out.fileno())
    shutil.copymode(args.tool, tmp)
    if args.tool.read_bytes() != original:
        raise RuntimeError('Settings changed concurrently; refusing replacement.')
    os.replace(tmp, args.tool)
finally:
    Path(tmp).unlink(missing_ok=True)
print(f'Applied RE workspace. Backup: {backup}')
