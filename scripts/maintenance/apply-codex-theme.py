#!/usr/bin/env python3
"""Install Black Tiffany without replacing private Codex settings."""
import datetime
import os
from pathlib import Path
import re
import shutil
import tempfile
import tomllib


def configure(text):
    block = re.search(r'^\[tui\][ \t]*(?:#.*)?$', text, re.M)
    if block:
        start = block.end()
        following = re.search(r'^\[', text[start:], re.M)
        end = start + following.start() if following else len(text)
        body = text[start:end]
        if re.search(r'^theme\s*=', body, re.M):
            body = re.sub(r'^theme\s*=.*$', 'theme = "black-tiffany"', body, flags=re.M)
        else:
            body = '\ntheme = "black-tiffany"' + body
        result = text[:start] + body + text[end:]
    else:
        result = text.rstrip() + '\n\n[tui]\ntheme = "black-tiffany"\n'
    parsed = tomllib.loads(result)
    if parsed['tui']['theme'] != 'black-tiffany':
        raise ValueError('Theme could not be configured')
    return result


def main():
    home = Path(os.environ.get('CODEX_HOME', Path.home() / '.codex')).expanduser()
    home.mkdir(parents=True, exist_ok=True)
    path = home / 'config.toml'
    target = path.resolve() if path.is_symlink() else path
    old = path.read_text() if path.exists() else ''
    new = configure(old)
    source = Path(__file__).resolve().parents[2] / 'themes/Codex/black-tiffany.tmTheme'
    theme = home / 'themes/black-tiffany.tmTheme'
    theme.parent.mkdir(parents=True, exist_ok=True)
    backup = None
    if new != old or (theme.exists() and not theme.is_symlink()):
        backup = Path.home() / '.local/state/codex-theme' / datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f')
        backup.mkdir(parents=True, mode=0o700)
        if path.exists():
            shutil.copy2(path, backup / 'config.toml')
            (backup / 'config.toml').chmod(0o600)
        if theme.exists() and not theme.is_symlink():
            shutil.copy2(theme, backup / 'previous.tmTheme')
    if not theme.is_symlink() or theme.resolve() != source:
        if theme.exists() or theme.is_symlink():
            theme.unlink()
        theme.symlink_to(source)
    if new != old:
        fd, temporary = tempfile.mkstemp(prefix='.config-theme-', dir=target.parent)
        try:
            os.fchmod(fd, 0o600)
            with os.fdopen(fd, 'w') as f:
                f.write(new)
                f.flush()
                os.fsync(f.fileno())
            os.replace(temporary, target)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
    print('Codex theme: black-tiffany')
    if backup:
        print('Private config backup:', backup)


if __name__ == '__main__':
    main()
