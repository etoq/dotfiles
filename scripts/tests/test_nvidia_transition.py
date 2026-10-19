"""Check transition failure paths without executing privileged operations."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / 'maintenance/nvidia-transition.py'
spec = importlib.util.spec_from_file_location('nvidia_transition', SCRIPT)
transition = importlib.util.module_from_spec(spec)
spec.loader.exec_module(transition)


class TransitionSafety(unittest.TestCase):
    def test_sleep_policy_is_reapplied_after_failed_package_transaction(self):
        calls = []

        def run(args):
            calls.append(args)
            if args[0] == 'pacman':
                raise RuntimeError('simulated package failure')

        with self.assertRaisesRegex(RuntimeError, 'simulated package failure'):
            transition.transaction(run, [Path('/test/package')], '/test/policy')
        self.assertEqual(calls, [['pacman', '-U', '--', Path('/test/package')], ['/test/policy']])

    def test_normal_transaction_keeps_pacman_confirmation_and_dependencies(self):
        calls = []
        transition.transaction(calls.append, [Path('/test/package')], '/test/policy')
        self.assertEqual(calls[0], ['pacman', '-U', '--', Path('/test/package')])
        self.assertEqual(calls[1], ['/test/policy'])

    def test_wrong_module_version_stops_before_rebuilding_boot_images(self):
        calls = []
        with patch.object(transition, 'output', return_value='470.256.02'):
            with self.assertRaisesRegex(RuntimeError, 'Wrong installed module version'):
                transition.finish(calls.append, {'kernels': ['test-kernel']}, Path('/test'), '580.178.04')
        self.assertEqual(calls, [['dkms', 'autoinstall', '-k', 'test-kernel']])

    def test_checksum_mismatch_is_rejected_before_package_inspection(self):
        with tempfile.TemporaryDirectory() as folder:
            archive = Path(folder) / 'package'
            archive.write_bytes(b'changed package')
            with patch.object(transition, 'output') as inspect:
                with self.assertRaisesRegex(RuntimeError, 'checksum differs'):
                    transition.verify_archive(archive, {'sha256': '0' * 64})
                inspect.assert_not_called()

    def test_correct_hash_with_wrong_package_identity_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            archive = Path(folder) / 'package'
            archive.write_bytes(b'package')
            with patch.object(transition, 'output', return_value='other-name 1.0'):
                with self.assertRaisesRegex(RuntimeError, 'identity differs'):
                    transition.verify_archive(archive, {'sha256': transition.sha(archive), 'name': 'expected', 'version': '1.0'})

    def test_non_root_action_stops_before_any_machine_or_backup_operations(self):
        with patch.object(transition.os, 'geteuid', return_value=1000), patch.object(transition, 'check_machine') as check:
            with self.assertRaisesRegex(RuntimeError, 'sudo'):
                transition.apply({}, False)
            check.assert_not_called()

    def test_saved_rollback_uses_its_own_assets_without_home_repository(self):
        with tempfile.TemporaryDirectory() as folder:
            saved = Path(folder)
            (saved / 'assets').mkdir()
            with patch.object(transition, 'HERE', saved):
                self.assertEqual(transition.assets()['verify-kernel-stack'], saved / 'assets/verify-kernel-stack')


if __name__ == '__main__':
    unittest.main()
