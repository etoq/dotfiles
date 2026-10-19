"""Idle locker must not blank the screen before starting the locker."""
import importlib.machinery
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

loader = importlib.machinery.SourceFileLoader('idle_lock', str(Path(__file__).resolve().parents[1] / 'local-bin/idle-screen-lock'))
spec = importlib.util.spec_from_loader(loader.name, loader)
idle = importlib.util.module_from_spec(spec)
loader.exec_module(idle)


class IdleLock(unittest.TestCase):
    def test_waits_for_locker_before_display_off(self):
        locker = SimpleNamespace(poll=lambda: None, wait=lambda: 0)
        calls = []
        ready = iter([1, 0])
        def run(args, **kwargs):
            calls.append(args)
            return SimpleNamespace(returncode=next(ready) if args[0] == 'pgrep' else 0)
        with patch.object(idle.sp, 'Popen', return_value=locker), patch.object(idle.sp, 'run', side_effect=run), patch.object(idle.time, 'sleep'):
            self.assertEqual(idle.main(), 0)
        self.assertEqual([c[0] for c in calls], ['pgrep', 'pgrep', 'xset'])
        self.assertEqual(calls[-1], ['xset', 'dpms', 'force', 'off'])

    def test_failed_locker_does_not_power_off(self):
        locker = SimpleNamespace(poll=lambda: 1, wait=lambda: 1)
        with patch.object(idle.sp, 'Popen', return_value=locker), patch.object(idle.sp, 'run') as run:
            self.assertEqual(idle.main(), 1)
        run.assert_not_called()

    def test_user_service_selects_graphical_session_explicitly(self):
        with patch.dict(idle.os.environ, {}, clear=True), patch.object(idle.os, 'getuid', return_value=1000), patch.object(idle.sp, 'check_output', side_effect=['2\n', 'User=1000\nType=x11\n']), patch.object(idle.os, 'execvp') as execute:
            idle.watch()
        self.assertIn('--session=2', execute.call_args.args[1])


if __name__ == '__main__':
    unittest.main()
