"""Audit repairs: no real process signals, fan control or package mutations."""
import importlib.machinery
import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch, Mock

ROOT = Path(__file__).resolve().parents[2]


def load(name, path):
    loader = importlib.machinery.SourceFileLoader(name, str(path))
    spec = importlib.util.spec_from_loader(name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


wispr = load('audit_wispr', ROOT / 'scripts/local-bin/wispr-a11y-guard')
kernel = load('audit_kernel', ROOT / 'scripts/local-bin/verify-kernel-stack')


class Recovery(unittest.TestCase):
    def test_missing_helper_grace_period_and_cooldown(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(wispr, 'app_processes', return_value={123: ('exe', 'start')}), patch.object(wispr, 'helper_identity', return_value=None), patch.object(wispr, 'restart_app', return_value=True) as restart:
            runtime = Path(folder)
            for now in [100, 150, 191, 300]:
                with patch.object(wispr.time, 'monotonic', return_value=now):
                    wispr.app_health({}, runtime, True)
            restart.assert_called_once_with(123, ('exe', 'start'))

    def test_closed_app_is_never_launched(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(wispr, 'app_processes', return_value={}), patch.object(wispr, 'helper_identity', return_value=None), patch.object(wispr, 'restart_app') as restart:
            wispr.app_health({}, Path(folder), True)
            restart.assert_not_called()

    def test_managed_app_restarts_through_systemd(self):
        replies = [subprocess.CompletedProcess([], 0, '123\n', ''),
                   subprocess.CompletedProcess([], 0, b'', b'')]
        with patch.object(wispr, 'app_processes', return_value={123: ('exe', 'start')}), patch.object(wispr.subprocess, 'run', side_effect=replies) as run, patch.object(wispr.subprocess, 'Popen') as spawn:
            self.assertTrue(wispr.restart_app(123, ('exe', 'start')))
            self.assertEqual(run.call_args_list[-1].args[0], ['systemctl', '--user', 'restart', 'wispr-flow.service'])
            spawn.assert_not_called()

    def test_electron_flattened_process_titles_are_not_main(self):
        self.assertFalse(wispr.is_main_args([b'/opt/wispr-flow --type=zygote --no-sandbox']))
        self.assertFalse(wispr.is_main_args([b'/opt/wispr-flow', b'--type=renderer']))
        self.assertTrue(wispr.is_main_args([b'/opt/wispr-flow --hidden --class=Wispr Flow']))

    def test_unmanaged_process_is_never_killed_or_spawned(self):
        reply = subprocess.CompletedProcess([], 0, '999\n', '')
        with patch.object(wispr, 'app_processes', return_value={123: ('exe', 'start')}), patch.object(wispr.subprocess, 'run', return_value=reply) as run, patch.object(wispr.subprocess, 'Popen') as spawn:
            self.assertFalse(wispr.restart_app(123, ('exe', 'start')))
            self.assertEqual(run.call_count, 1)
            spawn.assert_not_called()

    def test_pid_reuse_does_not_signal(self):
        with patch.object(wispr, 'app_processes', return_value={123: ('exe', 'new-start')}), patch.object(wispr.os, 'pidfd_open') as opening:
            self.assertFalse(wispr.restart_app(123, ('exe', 'old-start')))
            opening.assert_not_called()


class KernelPackages(unittest.TestCase):
    def test_only_package_owned_kernel_is_selected(self):
        with tempfile.TemporaryDirectory() as folder:
            pkgbase = Path(folder) / 'usr/lib/modules/current/pkgbase'
            pkgbase.parent.mkdir(parents=True)
            pkgbase.write_text('linux-lts\n')
            stale = pkgbase.parent.parent / 'stale/pkgbase'
            stale.parent.mkdir()
            stale.write_text('linux-lts\n')
            def run(args):
                return subprocess.CompletedProcess(args, 0 if args[-1] == 'linux-lts' else 1,
                                                  'linux-lts ' + str(pkgbase) + '\n', '')
            with patch.object(kernel, 'run', side_effect=run):
                self.assertEqual(kernel.installed_kernels(), [('linux-lts', 'current')])


if __name__ == '__main__':
    unittest.main()
