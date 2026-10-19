#!/usr/bin/python
"""Read-only comparison of installer-managed user files; never prints contents."""
import argparse
import filecmp
import json
import os
from pathlib import Path
import re

REPO = Path(__file__).resolve().parents[2]


def targets(repo, home):
    installer = (repo / 'install.sh').read_text()
    for source, target in re.findall(r'\blink "([^"$]+)"\s+"\$HOME/([^"$]+)"', installer):
        yield repo / source, home / target
    for name, directory, destination in [('LOCAL_SCRIPTS', 'scripts/local-bin', '.local/bin'), ('BIN_SCRIPTS', 'scripts/bin', 'bin')]:
        match = re.search(r'\b' + name + r'=\((.*?)\)', installer, re.S)
        if match:
            for script in match[1].split():
                yield repo / directory / script, home / destination / script


def compare(source, target):
    if not source.exists():
        return 'missing_source'
    if not target.exists():
        return 'broken_link' if target.is_symlink() else 'missing_target'
    if target.is_symlink() and target.resolve() == source.resolve():
        return 'linked'
    if source.is_file() and target.is_file():
        return 'same_copy' if filecmp.cmp(source, target, shallow=False) else 'different_copy'
    if source.is_dir() and target.is_dir():
        return 'directory'
    return 'type_mismatch'


def audit(repo, home):
    for source, target in targets(repo, home):
        state = compare(source, target)
        yield {'source': str(source.relative_to(repo)), 'target': str(target), 'state': state}
        if state == 'directory':
            for directory, dirs, files in os.walk(source):
                dirs[:] = [d for d in dirs if d not in ('.git', '__pycache__')]
                for name in files:
                    if name.endswith(('.pyc', '.pyo')):
                        continue
                    path = Path(directory) / name
                    dest = target / path.relative_to(source)
                    child_state = compare(path, dest)
                    if child_state not in ('linked', 'same_copy'):
                        yield {'source': str(path.relative_to(repo)), 'target': str(dest), 'state': child_state}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args()
    results = list(audit(REPO, Path.home()))
    problems = [x for x in results if x['state'] not in ('linked', 'same_copy', 'directory')]
    if args.json:
        print(json.dumps({'files': results, 'problems': problems}, indent=2))
    else:
        print(f'Checked {len(results)} installer mappings; {len(problems)} differences.')
        for item in problems:
            print(f"{item['state']}: {item['target']} <- {item['source']}")
        print('Matching ordinary copies are valid. Extra personal files are preserved and ignored.')
        print('System restore payload: bash restore-system.sh --check; no live changes are made.')
    return bool(problems)


if __name__ == '__main__':
    raise SystemExit(main())
