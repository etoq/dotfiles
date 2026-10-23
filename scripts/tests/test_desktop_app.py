"""Window reuse; never touch installed sessions."""
import importlib.machinery
import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

path = Path(__file__).resolve().parents[1] / 'local-bin/desktop-app'
loader = importlib.machinery.SourceFileLoader('desktop_app_test', str(path))
spec = importlib.util.spec_from_loader(loader.name, loader)
app = importlib.util.module_from_spec(spec)
loader.exec_module(app)


def completed(args, output='', code=0):
    return subprocess.CompletedProcess(args, code, output, '')


class Lifecycle(unittest.TestCase):
    def test_repeated_open_of_managed_window_never_launches_app(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(app.os.environ, {'XDG_RUNTIME_DIR': tmp}), \
                patch.object(app, 'managed_windows', return_value=[{'window': 123}]), \
                patch.object(app, 'activate') as activate, patch.object(app.sp, 'Popen') as launch:
            for _ in range(5):
                app.open_app('chatgpt')
            self.assertEqual(activate.call_count, 5)
            activate.assert_called_with(123)
            launch.assert_not_called()

    def test_hidden_window_uses_native_single_instance_activation(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(app.os.environ,
                {'XDG_RUNTIME_DIR': tmp, 'XDG_STATE_HOME': tmp}), \
                patch.object(app, 'managed_windows', side_effect=[[], [{'window': 123}]]), \
                patch.object(app, 'activate') as activate, patch.object(app.sp, 'Popen') as launch:
            app.open_app('discord')
            self.assertEqual(launch.call_args.args[0], ['/usr/bin/discord'])
            self.assertEqual(launch.call_count, 1)
            activate.assert_called_once_with(123)

    def test_other_desktop_switches_before_waiting_for_map(self):
        with patch.dict(app.os.environ, {'XDG_CURRENT_DESKTOP': 'awesome'}), \
                patch.object(app, 'run', return_value=completed([], '   boolean true\n')) as run:
            app.activate(123)
            self.assertEqual(run.call_count, 1)
            self.assertEqual(run.call_args.args[0][0], 'awesome-client')
            self.assertIn('view_only()', run.call_args.args[0][1])



if __name__ == '__main__':
    unittest.main()
