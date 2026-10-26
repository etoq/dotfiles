#!/usr/bin/env python3
"""Recover the saved encrypted GNOME collection without handling passwords."""
import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import time
import stat
import subprocess as sp
import tempfile

HOME = Path.home()
KEYRINGS = HOME / '.local/share/keyrings'
BASE = HOME / '.local/state/keyring-recovery'
CURRENT = BASE / 'current'
NAME = 'Default_Keyring.keyring'
MAGIC = b'GnomeKeyring\n\r\0\n'
TIMERS = ('workstation-backup-full.timer', 'workstation-backup-keepass.timer', 'proton-quota.timer')
JOBS = ('workstation-backup@full.service', 'workstation-backup@keepass.service')
DAEMON = ('gnome-keyring-daemon.service', 'gnome-keyring-daemon.socket')


def command(args, check=True, timeout=20):
    result = sp.run(list(map(str, args)), capture_output=True, text=True, timeout=timeout)
    if check and result.returncode:
        raise RuntimeError('Command failed: ' + ' '.join(map(str, args)) + '\n' + result.stderr[-500:])
    return result


def systemctl(*args, check=True):
    return command(['systemctl', '--user', *args], check=check, timeout=30)


def running(unit):
    return systemctl('is-active', unit, check=False).stdout.strip() in ('active', 'activating', 'reloading')


def atomic(path, data, mode=0o600):
    fd, temporary = tempfile.mkstemp(prefix='.' + path.name + '-', dir=path.parent)
    try:
        os.fchmod(fd, mode)
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(folder, data):
    atomic(folder / 'state.json', (json.dumps(data, ensure_ascii=False, indent=2) + '\n').encode())


def current():
    folder = Path(CURRENT.read_text().strip())
    if folder.is_symlink() or folder.parent != BASE or folder.stat().st_uid != os.getuid():
        raise RuntimeError('Unexpected recovery directory')
    return folder, json.loads((folder / 'state.json').read_text())


def snapshot(destination):
    if KEYRINGS.is_symlink() or KEYRINGS.stat().st_uid != os.getuid():
        raise RuntimeError('Unexpected keyring directory')
    destination.mkdir(mode=0o700)
    files = {}
    for source in KEYRINGS.iterdir():
        info = source.lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid():
            raise RuntimeError('Unexpected entry in keyring directory: ' + source.name)
        target = destination / source.name
        shutil.copy2(source, target)
        target.chmod(0o600)
        files[source.name] = {'sha256': digest(target), 'mode': stat.S_IMODE(info.st_mode)}
    return files


def graphical_sessions():
    sessions = command(['loginctl', 'show-user', str(os.getuid()), '-p', 'Sessions', '--value']).stdout.split()
    result = []
    for session in sessions:
        text = command(['loginctl', 'show-session', session, '-p', 'Type', '-p', 'User'], check=False).stdout
        props = dict(line.split('=', 1) for line in text.splitlines() if '=' in line)
        if props.get('User') == str(os.getuid()) and props.get('Type') in ('x11', 'wayland'):
            result.append(session)
    return result


def offline_required():
    if graphical_sessions():
        raise RuntimeError('Рабочий стол ещё открыт. Сохрани работу, выйди из сеанса, войди в TTY и повтори команду. Ничего не заменено.')


def resume_daemon(data):
    # Start only the components which were running at preparation time.
    for unit in reversed(DAEMON):
        if data['daemon'].get(unit):
            systemctl('start', unit)


def daemon_identity(pid):
    proc = Path('/proc') / str(pid)
    try:
        if proc.stat().st_uid != os.getuid() or (proc / 'exe').resolve() != Path('/usr/bin/gnome-keyring-daemon'):
            return None
        fields = (proc / 'stat').read_text().rsplit(')', 1)[1].split()
        return None if fields[0] == 'Z' else fields[19]
    except (OSError, IndexError):
        return None


def owned_daemons():
    result = {}
    for proc in Path('/proc').iterdir():
        if proc.name.isdigit():
            identity = daemon_identity(int(proc.name))
            if identity is not None:
                result[int(proc.name)] = identity
    return result


def stop_daemon():
    systemctl('stop', *DAEMON)
    # D-Bus can also have started a daemon directly, outside the systemd unit.
    # Stop only the verified current-user binary, gracefully, with PID pinning.
    for pid, identity in owned_daemons().items():
        try:
            fd = os.pidfd_open(pid)
        except ProcessLookupError:
            continue
        try:
            if daemon_identity(pid) == identity:
                signal.pidfd_send_signal(fd, signal.SIGTERM)
        except ProcessLookupError:
            pass
        finally:
            os.close(fd)
    deadline = time.monotonic() + 8
    while owned_daemons():
        if time.monotonic() >= deadline:
            raise RuntimeError('GNOME Keyring не завершился. Файлы не заменены; принудительное завершение не используется.')
        time.sleep(.1)


def prepare():
    BASE.mkdir(parents=True, exist_ok=True, mode=0o700)
    BASE.chmod(0o700)
    if CURRENT.exists():
        folder, data = current()
        if data['phase'] in ('prepared', 'restored'):
            systemctl('stop', *TIMERS)
            systemctl('stop', 'proton-quota.service')
            if any(running(unit) for unit in JOBS):
                raise RuntimeError('A backup job is still finishing; wait before restoring.')
            print('Already prepared:', folder)
            return
    source = KEYRINGS / (NAME + '.bak')
    if source.is_symlink() or not source.read_bytes().startswith(MAGIC):
        raise RuntimeError('Encrypted GNOME backup was not found or has an unexpected format')
    # Verify bus access before creating a pending recovery record.
    timers = {unit: running(unit) for unit in TIMERS}
    daemon = {unit: running(unit) for unit in DAEMON}
    if any(running(unit) for unit in JOBS):
        raise RuntimeError('A backup job is still running. Wait for it to finish before preparation.')
    folder = BASE / dt.datetime.now().strftime('%Y%m%d-%H%M%S-%f')
    folder.mkdir(mode=0o700)
    files = snapshot(folder / 'original')
    data = {'phase': 'prepared', 'files': files, 'timers': timers, 'daemon': daemon,
            'source_sha256': files[NAME + '.bak']['sha256']}
    save(folder, data)
    atomic(CURRENT, str(folder).encode())
    try:
        systemctl('stop', *TIMERS)
        systemctl('stop', 'proton-quota.service')
        if any(running(unit) for unit in JOBS):
            raise RuntimeError('A backup job started before timers stopped. Wait for it to finish; then repeat prepare.')
    except Exception:
        print('Подготовка сохранена; таймеры оставлены на паузе. Повтори prepare после завершения текущей задачи.')
        raise
    print('Подготовлено. Закрытая резервная копия:', folder)
    print('Рабочая связка ещё НЕ заменена. Сохрани работу и выйди из рабочего стола.')
    print('В TTY: python ~/dotfiles/scripts/maintenance/recover-gnome-keyring.py restore')
    print('После входа обратно: python ~/dotfiles/scripts/maintenance/recover-gnome-keyring.py resume')


def restore_timers(data):
    for unit, was_running in data['timers'].items():
        if was_running:
            systemctl('start', unit)


def restore():
    folder, data = current()
    if data['phase'] == 'restored':
        print('Связка уже восстановлена. Войди в рабочий стол и выполни resume.')
        return
    if data['phase'] != 'prepared':
        raise RuntimeError('No prepared recovery to restore')
    offline_required()
    systemctl('stop', *TIMERS)
    systemctl('stop', 'proton-quota.service')
    if any(running(unit) for unit in JOBS):
        raise RuntimeError('A backup job is still running; wait before restoring keyrings.')
    source = folder / 'original' / (NAME + '.bak')
    if digest(source) != data['source_sha256'] or not source.read_bytes().startswith(MAGIC):
        raise RuntimeError('Saved backup verification failed; no files changed')
    target = KEYRINGS / NAME
    if target.exists() or target.is_symlink():
        raise RuntimeError('Рабочая связка уже существует. Ничего не перезаписываю; нужна повторная проверка.')
    try:
        stop_daemon()
        if not (folder / 'before-restore').exists():
            snapshot(folder / 'before-restore')
        atomic(target, source.read_bytes())
        atomic(KEYRINGS / 'default', b'Default_Keyring')
        KEYRINGS.chmod(0o700)
        if digest(target) != data['source_sha256']:
            raise RuntimeError('Restored file verification failed')
        data['phase'] = 'restored'
        save(folder, data)
    finally:
        resume_daemon(data)
    print('Связка восстановлена и проверена. login.keyring, user.keystore и исходный .bak сохранены.')
    print('Вернись в графический вход и войди. Затем выполни команду resume из инструкции.')


def unlock_collection():
    from gi.repository import Gio, GLib
    bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
    service = 'org.freedesktop.secrets'
    path = '/org/freedesktop/secrets'
    iface = 'org.freedesktop.Secret.Service'
    def call(obj, interface, method, args=None):
        return bus.call_sync(service, obj, interface, method, args, None, Gio.DBusCallFlags.NONE, 10000, None).unpack()
    def prop(obj, interface, name):
        return call(obj, 'org.freedesktop.DBus.Properties', 'Get', GLib.Variant('(ss)', (interface, name)))[0]
    collections = prop(path, iface, 'Collections')
    collection_iface = 'org.freedesktop.Secret.Collection'
    matches = [p for p in collections if prop(p, collection_iface, 'Label') == 'Default Keyring']
    if len(matches) != 1:
        raise RuntimeError('GNOME did not load exactly one restored Default Keyring collection')
    collection = matches[0]
    if call(path, iface, 'ReadAlias', GLib.Variant('(s)', ('default',)))[0] != collection:
        call(path, iface, 'SetAlias', GLib.Variant('(so)', ('default', collection)))
    if prop(collection, collection_iface, 'Locked'):
        unlocked, prompt = call(path, iface, 'Unlock', GLib.Variant('(ao)', ([collection],)))
        if prompt != '/':
            print('В системном окне введи старый пароль Default Keyring. В терминал пароль вводить не нужно.', flush=True)
            loop = GLib.MainLoop()
            outcome = {'dismissed': True}
            def done(*args):
                outcome['dismissed'] = args[5].unpack()[0]
                loop.quit()
            token = bus.signal_subscribe(service, 'org.freedesktop.Secret.Prompt', 'Completed', prompt, None, Gio.DBusSignalFlags.NONE, done, None)
            timer = GLib.timeout_add_seconds(180, lambda: (loop.quit(), False)[1])
            try:
                call(prompt, 'org.freedesktop.Secret.Prompt', 'Prompt', GLib.Variant('(s)', ('',)))
                loop.run()
            finally:
                bus.signal_unsubscribe(token)
                GLib.source_remove(timer)
            if outcome['dismissed']:
                raise RuntimeError('Разблокировка отменена или истекло время. Можно повторить resume.')
    if prop(collection, collection_iface, 'Locked'):
        raise RuntimeError('Связка остаётся заблокированной. Проверь старый пароль и повтори resume.')
    print('Default Keyring разблокирован; секреты не выводились.')


def resume(login=False):
    folder, data = current()
    if data['phase'] not in ('restored', 'complete'):
        raise RuntimeError('Сначала восстанови файл из TTY командой restore')
    unlock_collection()
    cli = HOME / '.local/bin/proton-drive'
    if login:
        # Explicit fallback: only the native login flow handles account secrets.
        if sp.call([str(cli), 'auth', 'login']):
            raise RuntimeError('Proton login did not complete; timers remain paused')
    plan = json.loads((HOME / '.config/workstation-backup/plan.json').read_text())
    destination = plan['destination']['remote_directory']
    result = command([cli, 'filesystem', 'info', destination, '--json'], check=False, timeout=90)
    if result.returncode:
        raise RuntimeError('Proton пока не подтвердил доступ. Таймеры остаются на паузе. Если сессия истекла: повтори эту команду с действием login вместо resume. Связки не удалены.')
    node = json.loads(result.stdout)
    if node.get('type') != 'folder' or (plan['destination'].get('folder_uid') and node.get('uid') != plan['destination']['folder_uid']):
        raise RuntimeError('Backup destination identity does not match; timers remain paused')
    print('Доступ к прежней папке Proton подтверждён чтением метаданных. Загрузка и удаление не запускались.')
    restore_timers(data)
    data['phase'] = 'complete'
    save(folder, data)
    print('Готово. Прежнее расписание резервирования возобновлено; просроченные задания могут запуститься по расписанию.')


def rollback():
    folder, data = current()
    if data['phase'] == 'prepared':
        restore_timers(data)
    elif data['phase'] in ('restored', 'complete'):
        offline_required()
        systemctl('stop', *TIMERS)
        if any(running(unit) for unit in JOBS):
            raise RuntimeError('Wait for the active backup job before rollback')
        try:
            stop_daemon()
            dest = folder / ('before-rollback-' + dt.datetime.now().strftime('%Y%m%d-%H%M%S'))
            KEYRINGS.rename(dest)
            KEYRINGS.mkdir(mode=0o700)
            for source in (folder / 'original').iterdir():
                target = KEYRINGS / source.name
                shutil.copy2(source, target)
                target.chmod(data['files'][source.name]['mode'])
        finally:
            resume_daemon(data)
        # A restored broken keyring must not restart backup jobs automatically.
        print('Предыдущее состояние ключей возвращено. Таймеры остаются на паузе до восстановления доступа.')
    else:
        raise RuntimeError('No pending recovery to roll back')
    data['phase'] = 'rolled-back'
    save(folder, data)
    print('Откат завершён. Резервные копии сохранены.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('prepare', 'restore', 'resume', 'login', 'rollback', 'status'))
    args = parser.parse_args()
    if os.geteuid() == 0:
        raise RuntimeError('Запускай под eto, без sudo: восстанавливается пользовательская связка.')
    if args.action == 'prepare':
        prepare()
    elif args.action == 'restore':
        restore()
    elif args.action in ('resume', 'login'):
        resume(login=args.action == 'login')
    elif args.action == 'rollback':
        rollback()
    else:
        folder, data = current()
        print('Recovery:', folder, 'Phase:', data['phase'])


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        raise SystemExit('STOP: ' + str(error))
