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

    def test_localsend_tray_restore_does_not_spawn(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(app.os.environ,
                {'XDG_RUNTIME_DIR': tmp, 'XDG_STATE_HOME': tmp}), \
                patch.object(app, 'managed_windows', side_effect=[[], [{'window': 456}]]), \
                patch.object(app, 'activate_localsend', return_value=True) as native, \
                patch.object(app, 'activate') as activate, patch.object(app.sp, 'Popen') as launch:
            app.open_app('localsend')
            native.assert_called_once_with()
            activate.assert_called_once_with(456)
            launch.assert_not_called()

    def test_tray_parser_selects_open_even_when_quit_is_first(self):
        def item(identifier, label, enabled=True):
            return {'data': [identifier, {'label': {'data': label}, 'enabled': {'data': enabled}}, []]}
        menu = {'data': [3, [0, {}, [item(4, 'Выйти из LocalSend'), item(3, 'Открыть')]]]}
        self.assertEqual(app.tray_open_id(menu), 3)
        menu['data'][1][2] = [item(4, 'Quit LocalSend')]
        self.assertIsNone(app.tray_open_id(menu))
        menu['data'][1][2] = [item(3, 'Open', enabled=False)]
        self.assertIsNone(app.tray_open_id(menu))
        self.assertIsNone(app.tray_open_id({'data': []}))

    def test_localsend_restores_via_tray_event_not_gtk_activate(self):
        menu = '{"data": [3, [0, {}, [{"data": [3, {"label": {"data": "Открыть"}}, []]}]]]}'
        def respond(args, **_):
            if args[-1] == 'list':
                return completed(args, ':1.50 100 localsend eto\n')
            if 'tree' in args:
                return completed(args, '/org/ayatana/NotificationItem/example/Menu\n')
            if 'GetLayout' in args:
                return completed(args, menu)
            self.assertIn('Event', args)
            self.assertEqual(args[-5:], ['3', 'clicked', 's', '', '0'])
            self.assertNotIn('org.freedesktop.Application.Activate', args)
            return completed(args)
        with patch.object(app, 'main_processes', return_value=[100]), \
                patch.object(app, 'run', side_effect=respond) as calls:
            self.assertTrue(app.activate_localsend())
            self.assertEqual(calls.call_count, 4)

    def test_other_desktop_switches_before_waiting_for_map(self):
        with patch.dict(app.os.environ, {'XDG_CURRENT_DESKTOP': 'awesome'}), \
                patch.object(app, 'run', return_value=completed([], '   boolean true\n')) as run:
            app.activate(123)
            self.assertEqual(run.call_count, 1)
            self.assertEqual(run.call_args.args[0][0], 'awesome-client')
            self.assertIn('view_only()', run.call_args.args[0][1])



if __name__ == '__main__':
    unittest.main()
