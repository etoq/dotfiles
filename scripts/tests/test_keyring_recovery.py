"""Recovery on synthetic files only: no real secrets, logouts or D-Bus changes."""
import contextlib
import importlib.machinery
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

p = Path(__file__).resolve().parents[1] / 'maintenance/recover-gnome-keyring.py'
loader = importlib.machinery.SourceFileLoader('keyring_recovery_tested', str(p))
spec = importlib.util.spec_from_loader(loader.name, loader)
m = importlib.util.module_from_spec(spec)
loader.exec_module(m)


class Recovery(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.keys = self.root / 'keyrings'
        self.keys.mkdir()
        (self.keys / (m.NAME + '.bak')).write_bytes(m.MAGIC + b'encrypted-test-data')
        (self.keys / 'login.keyring').write_bytes(b'new-login-preserve-me')
        (self.keys / 'user.keystore').write_bytes(b'new-keystore-preserve-me')
        (self.keys / 'default').write_text('Default_Keyring')
        stack = contextlib.ExitStack()
        self.addCleanup(stack.close)
        for key, value in [('KEYRINGS', self.keys), ('BASE', self.root / 'state'), ('CURRENT', self.root / 'state/current')]:
            stack.enter_context(patch.object(m, key, value))
        stack.enter_context(patch.object(m, 'running', side_effect=lambda unit: unit in (*m.TIMERS, *m.DAEMON)))
        self.ctl = stack.enter_context(patch.object(m, 'systemctl', return_value=subprocess.CompletedProcess([], 0, '', '')))
        stack.enter_context(patch.object(m, 'stop_daemon'))
        stack.enter_context(patch.object(m, 'resume_daemon'))

    def test_prepare_does_not_replace_live_collection(self):
        m.prepare()
        self.assertFalse((self.keys / m.NAME).exists())
        folder, data = m.current()
        self.assertEqual(data['phase'], 'prepared')
        self.assertEqual((folder / 'original' / (m.NAME + '.bak')).read_bytes(), (self.keys / (m.NAME + '.bak')).read_bytes())
        self.assertEqual((folder.stat().st_mode & 0o777), 0o700)
        self.assertEqual((folder / 'original/login.keyring').stat().st_mode & 0o777, 0o600)

    def test_graphical_session_blocks_restoration(self):
        m.prepare()
        with patch.object(m, 'graphical_sessions', return_value=['2']):
            with self.assertRaisesRegex(RuntimeError, 'Рабочий стол'):
                m.restore()
        self.assertFalse((self.keys / m.NAME).exists())

    def test_offline_restore_keeps_new_login_and_backup(self):
        m.prepare()
        with patch.object(m, 'graphical_sessions', return_value=[]):
            m.restore()
        self.assertEqual((self.keys / m.NAME).read_bytes(), (self.keys / (m.NAME + '.bak')).read_bytes())
        self.assertEqual((self.keys / 'login.keyring').read_bytes(), b'new-login-preserve-me')
        self.assertEqual((self.keys / 'user.keystore').read_bytes(), b'new-keystore-preserve-me')
        self.assertEqual((self.keys / m.NAME).stat().st_mode & 0o777, 0o600)
        (self.keys / m.NAME).write_bytes(b'newer live changes')
        m.restore()
        self.assertEqual((self.keys / m.NAME).read_bytes(), b'newer live changes')

    def test_corrupt_backup_is_not_installed(self):
        m.prepare()
        folder, data = m.current()
        (folder / 'original' / (m.NAME + '.bak')).write_bytes(b'broken')
        with patch.object(m, 'graphical_sessions', return_value=[]):
            with self.assertRaisesRegex(RuntimeError, 'verification failed'):
                m.restore()
        self.assertFalse((self.keys / m.NAME).exists())

    def test_existing_target_is_not_overwritten(self):
        m.prepare()
        (self.keys / m.NAME).write_bytes(b'other-data')
        with patch.object(m, 'graphical_sessions', return_value=[]):
            with self.assertRaisesRegex(RuntimeError, 'уже существует'):
                m.restore()
        self.assertEqual((self.keys / m.NAME).read_bytes(), b'other-data')

    def test_offline_rollback_preserves_post_restore_files(self):
        m.prepare()
        with patch.object(m, 'graphical_sessions', return_value=[]):
            m.restore()
            (self.keys / 'later.keyring').write_bytes(b'added-later')
            m.rollback()
        self.assertFalse((self.keys / m.NAME).exists())
        folder, _ = m.current()
        self.assertEqual(next(folder.glob('before-rollback-*/later.keyring')).read_bytes(), b'added-later')
        self.assertTrue((self.keys / (m.NAME + '.bak')).exists())


class DaemonShutdown(unittest.TestCase):
    def test_direct_daemon_is_stopped_gracefully(self):
        with patch.object(m, 'systemctl'), patch.object(m, 'owned_daemons', side_effect=[{123: 'old'}, {}]), patch.object(m, 'daemon_identity', return_value='old'), patch.object(m.os, 'pidfd_open', return_value=99), patch.object(m.os, 'close'), patch.object(m.signal, 'pidfd_send_signal') as signal:
            m.stop_daemon()
            signal.assert_called_once_with(99, m.signal.SIGTERM)

    def test_reused_pid_is_not_signalled(self):
        with patch.object(m, 'systemctl'), patch.object(m, 'owned_daemons', side_effect=[{123: 'old'}, {}]), patch.object(m, 'daemon_identity', return_value='new'), patch.object(m.os, 'pidfd_open', return_value=99), patch.object(m.os, 'close'), patch.object(m.signal, 'pidfd_send_signal') as signal:
            m.stop_daemon()
            signal.assert_not_called()


if __name__ == '__main__':
    unittest.main()
