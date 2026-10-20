"""Safety checks: real X11 close messages on an isolated display, no live cleanup."""
import ctypes as C
import importlib.machinery
import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / 'local-bin/workstation-away'
loader = importlib.machinery.SourceFileLoader('away', str(SCRIPT))
spec = importlib.util.spec_from_loader(loader.name, loader)
away = importlib.util.module_from_spec(spec)
loader.exec_module(away)


class PolicyTests(unittest.TestCase):
    def test_protected_family_includes_helpers_but_not_all_awesome_children(self):
        processes = {
            10: {'name': 'chrome-helper', 'exe': 'helper', 'parent': 20},
            20: {'name': 'wispr-flow', 'exe': 'wispr-flow', 'parent': 1},
            30: {'name': 'editor', 'exe': 'editor', 'parent': 40},
            40: {'name': 'awesome', 'exe': 'awesome', 'parent': 1},
        }
        self.assertTrue(away.protected(['helper'], 10, processes.get))
        self.assertFalse(away.protected(['editor'], 30, processes.get))
        for name in away.KEEP:
            self.assertTrue(away.protected([name], 0, processes.get), name)

    def test_vm_shutdown_never_powers_off_from_host(self):
        with patch.object(away, 'run') as run:
            away.shutdown_vm('test-uuid')
        run.assert_called_once_with(['virsh', '-c', 'qemu:///system', 'shutdown',
                                     'test-uuid', '--mode', 'agent,acpi'])

    def test_failed_vm_inventory_does_not_close_windows(self):
        with tempfile.TemporaryDirectory() as state, patch.dict(os.environ, {'XDG_STATE_HOME': state}), \
             patch.object(away, 'Desktop') as desktop, \
             patch.object(away, 'list_vms', side_effect=RuntimeError('libvirt unavailable')), \
             patch('sys.argv', ['workstation-away', '--apply']):
            with self.assertRaisesRegex(RuntimeError, 'libvirt unavailable'):
                away.main()
            desktop.return_value.close.assert_not_called()
            desktop.return_value.shutdown.assert_called_once()

    def test_default_is_read_only_and_apply_does_not_retry_close(self):
        window = {'window': 12, 'pid': os.getpid(), 'app': 'unsaved-editor', 'close_supported': True}
        with tempfile.TemporaryDirectory() as state, patch.dict(os.environ, {'XDG_STATE_HOME': state}), \
             patch.object(away, 'Desktop') as desktop, patch.object(away, 'list_vms', return_value=[]), \
             patch.object(away, 'shutdown_vm') as vm, patch.object(away, 'notify'), \
             patch.object(away.time, 'sleep'), patch.object(away.time, 'monotonic', side_effect=[0, 0, 6]), \
             patch.object(away, 'process_info', return_value={'name': 'AyuGram', 'exe': 'AyuGram', 'parent': 0}), \
             patch('sys.argv', ['workstation-away']):
            desktop.return_value.windows.return_value = [window]
            away.main()
            desktop.return_value.close.assert_not_called()
            vm.assert_not_called()
            with patch('sys.argv', ['workstation-away', '--apply']):
                away.main()
            desktop.return_value.close.assert_called_once_with(12)
            report = Path(state) / 'workstation-away/last-run.json'
            self.assertIn('Осталось окно', report.read_text())


@unittest.skipUnless(shutil.which('Xvfb'), 'Xvfb required for isolated X11 test')
class X11Tests(unittest.TestCase):
    def test_close_is_wm_delete_and_unsupported_or_protected_windows_are_spared(self):
        with tempfile.TemporaryDirectory() as temp:
            display_file = Path(temp) / 'display'
            with display_file.open('w') as output:
                server = subprocess.Popen(['Xvfb', '-displayfd', str(output.fileno()), '-screen', '0',
                                           '640x480x24', '-noreset', '-nolisten', 'tcp'],
                                          pass_fds=(output.fileno(),), stderr=subprocess.DEVNULL)
            try:
                for _ in range(100):
                    if display_file.read_text().strip():
                        break
                    time.sleep(.02)
                with patch.dict(os.environ, {'DISPLAY': ':' + display_file.read_text().strip()}):
                    desk = away.Desktop()
                try:
                    x, d = desk.x, desk.display
                    x.XCreateSimpleWindow.argtypes = [C.c_void_p, C.c_ulong, C.c_int, C.c_int,
                        C.c_uint, C.c_uint, C.c_uint, C.c_ulong, C.c_ulong]
                    x.XCreateSimpleWindow.restype = C.c_ulong
                    x.XChangeProperty.argtypes = [C.c_void_p, C.c_ulong, C.c_ulong, C.c_ulong,
                                                  C.c_int, C.c_int, C.c_void_p, C.c_int]
                    x.XPending.argtypes = [C.c_void_p]
                    x.XNextEvent.argtypes = [C.c_void_p, C.POINTER(away.Event)]
                    windows = []
                    for app, supports in [('editor', True), ('legacy', False), ('WisprFlow', True)]:
                        window = x.XCreateSimpleWindow(d, desk.root, 0, 0, 100, 100, 0, 0, 0)
                        windows.append(window)
                        raw = (app + '\0' + app + '\0').encode()
                        x.XChangeProperty(d, window, desk.atom('WM_CLASS'), desk.atom('STRING'), 8, 0, raw, len(raw))
                        pid = (C.c_ulong * 1)(os.getpid())
                        x.XChangeProperty(d, window, desk.atom('_NET_WM_PID'), desk.atom('CARDINAL'), 32, 0, pid, 1)
                        if supports:
                            protocols = (C.c_ulong * 1)(desk.atom('WM_DELETE_WINDOW'))
                            x.XChangeProperty(d, window, desk.atom('WM_PROTOCOLS'), desk.atom('ATOM'), 32, 0, protocols, 1)
                    values = (C.c_ulong * len(windows))(*windows)
                    x.XChangeProperty(d, desk.root, desk.atom('_NET_CLIENT_LIST'), desk.atom('WINDOW'), 32, 0, values, len(windows))
                    x.XSync(d, False)
                    plan = desk.windows()
                    self.assertEqual([w['app'] for w in plan], ['editor', 'legacy'])
                    self.assertTrue(desk.close(windows[0]))
                    self.assertFalse(desk.close(windows[1]))
                    event = away.Event()
                    self.assertGreater(x.XPending(d), 0)
                    x.XNextEvent(d, C.byref(event))
                    self.assertEqual(event.client.type, 33)
                    self.assertEqual(event.client.window, windows[0])
                    self.assertEqual(event.client.data.l[0], desk.atom('WM_DELETE_WINDOW'))
                    # A client may ignore/cancel the request: it remains present, no force fallback.
                    self.assertEqual(len(desk.windows()), 2)
                finally:
                    desk.shutdown()
            finally:
                server.terminate()
                server.wait(timeout=5)


if __name__ == '__main__':
    unittest.main()
