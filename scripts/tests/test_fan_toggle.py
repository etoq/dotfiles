"""Exercise profile transactions in temporary files; never touch the actual fan."""
import contextlib
import importlib.machinery
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import yaml

ROOT = Path(__file__).resolve().parents[2]
loader = importlib.machinery.SourceFileLoader('fan_toggle', str(ROOT / 'scripts/local-bin/fan-toggle'))
spec = importlib.util.spec_from_loader(loader.name, loader)
fan = importlib.util.module_from_spec(spec)
loader.exec_module(fan)


class Transactions(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.profiles = {}
        for name in ('normal', 'silent'):
            path = self.root / f'thinkfan-{name}.conf'
            path.write_bytes((ROOT / 'configs/etc' / path.name).read_bytes())
            self.profiles[name] = path
        self.config = self.root / 'thinkfan.conf'
        self.original = self.profiles['normal'].read_bytes()
        self.config.write_bytes(self.original)
        self.stack = contextlib.ExitStack()
        self.addCleanup(self.stack.close)
        for name, value in [('CONFIG', self.config), ('PROFILES', self.profiles),
                            ('LOCK', self.root / 'lock'), ('BACKUP_ROOT', self.root)]:
            self.stack.enter_context(patch.object(fan, name, value))

    def apply_context(self):
        self.stack.enter_context(patch.object(fan.os, 'geteuid', return_value=0))
        self.stack.enter_context(patch.object(fan, 'verify_root_file'))
        self.stack.enter_context(patch.object(fan, 'check_sensors'))
        self.stack.enter_context(patch.object(fan, 'service_pid', return_value=12))
        self.stack.enter_context(patch.object(fan, 'cursor', return_value='before'))

    def test_both_directions_preserve_backup(self):
        self.apply_context()
        with patch.object(fan, 'confirmed_reload') as reload:
            result = fan.apply()
            self.assertEqual(result['mode'], 'silent')
            self.assertEqual((Path(result['backup']) / 'thinkfan.conf').read_bytes(), self.original)
            self.assertEqual(self.config.read_bytes(), self.profiles['silent'].read_bytes())
            result = fan.apply()
            self.assertEqual(result['mode'], 'normal')
            self.assertEqual(self.config.read_bytes(), self.original)
            self.assertEqual(reload.call_count, 2)

    def test_failed_reload_restores_file_and_reloads_previous(self):
        self.apply_context()
        with patch.object(fan, 'confirmed_reload', side_effect=[RuntimeError('rejected'), None]) as reload:
            with self.assertRaisesRegex(RuntimeError, 'Прежний профиль восстановлен и подтверждён'):
                fan.apply()
            self.assertEqual(reload.call_count, 2)
        self.assertEqual(self.config.read_bytes(), self.original)

    def test_unknown_profile_is_not_overwritten(self):
        self.config.write_text('sensors: []\nfans: []\nlevels: []\n')
        with self.assertRaisesRegex(RuntimeError, 'не совпадает'):
            fan.read_profiles()
        self.assertIn('sensors: []', self.config.read_text())

    def test_profile_comments_do_not_change_identity(self):
        self.config.write_bytes(b'# extra comment\n' + self.original)
        self.assertEqual(fan.read_profiles()[0], 'normal')

    def test_bad_hysteresis_is_rejected(self):
        data = yaml.safe_load(self.profiles['silent'].read_text())
        data['levels'][1][1] = 90
        self.profiles['silent'].write_text(yaml.safe_dump(data))
        with self.assertRaises(RuntimeError):
            fan.read_profiles()


class ReloadConfirmation(unittest.TestCase):
    def check(self, messages):
        output = '\n'.join(json.dumps({'_PID': '12', 'MESSAGE': m}) for m in messages)
        with patch.object(fan, 'service_pid', return_value=12), \
             patch.object(fan, 'cursor', return_value='before'), \
             patch.object(fan, 'command', side_effect=['', output]):
            fan.confirmed_reload(12)

    def test_requires_temperatures_after_reload(self):
        self.check(['Received SIGHUP: reloading config...', 'Temperatures(bias): 50(0) -> Fans: level 0'])

    def test_rejected_reload_is_not_reported_as_success(self):
        with self.assertRaisesRegex(RuntimeError, 'отклонил'):
            self.check(['Received SIGHUP: reloading config...', 'Error reloading config. Keeping old one.',
                        'Temperatures(bias): 50(0) -> Fans: level 0'])


if __name__ == '__main__':
    unittest.main()
