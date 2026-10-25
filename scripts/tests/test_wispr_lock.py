import importlib.machinery
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

loader = importlib.machinery.SourceFileLoader('wispr_lock', str(Path(__file__).resolve().parents[1] / 'local-bin/wispr-lock'))
spec = importlib.util.spec_from_loader(loader.name, loader)
m = importlib.util.module_from_spec(spec)
loader.exec_module(m)


class LockHooks(unittest.TestCase):
    def test_repeated_pre_hook_preserves_original_state(self):
        with tempfile.TemporaryDirectory() as folder:
            marker = Path(folder) / 'state.json'
            with patch.object(m, 'active', return_value=True), patch.object(m, 'control', return_value=subprocess.CompletedProcess([], 0, '', '')) as control:
                m.before(marker)
                self.assertEqual(control.call_args_list[0].args, ('stop', 'wispr-a11y-guard.timer', 'wispr-a11y-guard.service'))
            with patch.object(m, 'active', return_value=False), patch.object(m, 'control', return_value=subprocess.CompletedProcess([], 0, '', '')):
                m.before(marker)
            self.assertEqual(json.loads(marker.read_text()), {'flow': True, 'guard': True})

    def test_restore_only_previously_running_apps(self):
        with tempfile.TemporaryDirectory() as folder:
            marker = Path(folder) / 'state.json'
            marker.write_text(json.dumps({'flow': False, 'guard': True}))
            with patch.object(m.sp, 'run', return_value=subprocess.CompletedProcess([], 1)), patch.object(m, 'control', return_value=subprocess.CompletedProcess([], 0, '', '')) as control:
                m.after(marker)
            control.assert_called_once_with('start', 'wispr-a11y-guard.timer')
            self.assertFalse(marker.exists())

    def test_active_locker_keeps_flow_stopped(self):
        with tempfile.TemporaryDirectory() as folder:
            marker = Path(folder) / 'state.json'
            marker.write_text(json.dumps({'flow': True, 'guard': True}))
            with patch.object(m.sp, 'run', return_value=subprocess.CompletedProcess([], 0)), patch.object(m, 'control') as control:
                m.after(marker)
            control.assert_not_called()
            self.assertTrue(marker.exists())


if __name__ == '__main__':
    unittest.main()
