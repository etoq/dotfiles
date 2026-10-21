import importlib.machinery
import importlib.util
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
loader = importlib.machinery.SourceFileLoader('workstation_tools', str(ROOT / 'scripts/local-bin/workstation-tools'))
spec = importlib.util.spec_from_loader(loader.name, loader)
tools = importlib.util.module_from_spec(spec)
loader.exec_module(tools)
DOMAIN = '11111111-2222-3333-4444-555555555555'


class VmPolicy(unittest.TestCase):
    def test_running_guest_cannot_be_snapshotted(self):
        with patch.object(tools, 'virsh', return_value='running') as virsh:
            with self.assertRaisesRegex(RuntimeError, 'выключи'):
                tools.snapshot_vm(DOMAIN)
            virsh.assert_called_once_with('domstate', DOMAIN)

    def test_snapshot_is_atomic_and_has_no_force_or_halt(self):
        with patch.object(tools, 'virsh', side_effect=['shut off', 'ok']) as virsh:
            name = tools.snapshot_vm(DOMAIN)
        call = virsh.call_args.args
        self.assertEqual(call[:2], ('snapshot-create-as', DOMAIN))
        self.assertIn('--atomic', call)
        self.assertNotIn('--halt', call)
        self.assertTrue(name.startswith('clean-'))

    def test_revert_needs_confirmation_before_any_command(self):
        with patch.object(tools, 'virsh') as virsh:
            with self.assertRaisesRegex(RuntimeError, 'подтверждения'):
                tools.revert_vm(DOMAIN, 'clean')
            virsh.assert_not_called()

    def test_running_snapshot_is_not_reverted(self):
        with patch.object(tools, 'virsh', side_effect=['shut off', '<domainsnapshot><state>running</state></domainsnapshot>']) as virsh:
            with self.assertRaisesRegex(RuntimeError, 'не снимок выключенной'):
                tools.revert_vm(DOMAIN, 'old', confirmed=True)
            self.assertEqual(virsh.call_count, 2)

    def test_offline_revert_uses_no_force(self):
        with patch.object(tools, 'virsh', side_effect=['shut off', '<domainsnapshot><state>shutoff</state></domainsnapshot>', 'ok']) as virsh:
            tools.revert_vm(DOMAIN, 'snapshot with spaces', confirmed=True)
            virsh.assert_called_with('snapshot-revert', DOMAIN, '--snapshotname', 'snapshot with spaces')


class ReportsAndTrash(unittest.TestCase):
    def test_denied_admin_authentication_cancels_check(self):
        with patch.object(tools.os, 'geteuid', return_value=1000), patch.object(tools.sp, 'run') as run:
            run.return_value.returncode = 1
            with self.assertRaisesRegex(RuntimeError, 'права администратора не получены'):
                tools.authorize_admin()
            run.assert_called_once_with(['/usr/bin/sudo', '-v'])

    def test_admin_read_only_elevates_initramfs_reader(self):
        def capture(args, timeout=30):
            program = str(args[0])
            output = {'pacman': '/usr/lib/modules/TEST/pkgbase', 'dkms': 'nvidia/580, TEST, x86_64: installed',
                      'modinfo': 'TEST SMP', '/usr/bin/sudo': 'usr/lib/modules/TEST/kernel/nvidia.ko'}.get(program, '')
            return {'ok': True, 'code': 0, 'output': output, 'error': ''}
        with patch.object(tools, 'capture', side_effect=capture) as run, patch.object(Path, 'read_text', return_value='linux-lts'), \
             patch.object(Path, 'exists', return_value=True), patch.object(tools.os, 'access', return_value=False), \
             patch.object(tools.os, 'geteuid', return_value=1000), patch.object(tools.os, 'uname') as uname:
            uname.return_value.release = 'TEST'
            checks = tools.kernel_checks(admin=True)
        self.assertEqual(checks[1]['status'], 'ok')
        privileged = [c.args[0] for c in run.call_args_list if c.args[0][0] == '/usr/bin/sudo']
        self.assertEqual(privileged, [['/usr/bin/sudo', '-n', '--', '/usr/bin/lsinitcpio', Path('/boot/initramfs-linux-lts.img')]])

    def test_kernel_check_uses_package_files_and_marks_unreadable_image_unknown(self):
        def capture(args, timeout=30):
            program = str(args[0])
            output = {'pacman': '/usr/lib/modules/TEST/pkgbase', 'dkms': 'nvidia/580, TEST, x86_64: installed',
                      'modinfo': 'TEST SMP'}.get(program, '')
            return {'ok': True, 'code': 0, 'output': output, 'error': ''}
        with patch.object(tools, 'capture', side_effect=capture), patch.object(Path, 'read_text', return_value='linux-lts'), \
             patch.object(Path, 'exists', return_value=True), patch.object(tools.os, 'access', return_value=False), \
             patch.object(tools.os, 'uname') as uname:
            uname.return_value.release = 'TEST'
            checks = tools.kernel_checks()
        self.assertEqual(checks[0]['status'], 'ok')
        self.assertEqual(checks[1]['status'], 'unverified')
        self.assertIn('права администратора', checks[1]['output'])

    def test_journal_deduplicates_sources_and_preserves_message_bytes(self):
        item = {'__CURSOR': 'one', '__REALTIME_TIMESTAMP': '1000000', 'MESSAGE': [104, 105],
                '_TRANSPORT': 'kernel', 'SYSLOG_IDENTIFIER': 'kernel', 'PRIORITY': '3'}
        result = {'ok': True, 'code': 0, 'output': json.dumps(item), 'error': ''}
        with patch.object(tools, 'capture', return_value=result):
            report = tools.collect_errors(10)
        self.assertEqual(len(report['entries']), 1)
        self.assertEqual(report['entries'][0]['message'], 'hi')
        self.assertEqual(report['entries'][0]['scope'], 'kernel')

    def test_invalid_error_period_does_not_run_commands(self):
        with patch.object(tools, 'capture') as capture:
            with self.assertRaises(ValueError):
                tools.collect_errors(0)
            capture.assert_not_called()

    def test_changed_duplicate_is_not_trashed(self):
        with tempfile.TemporaryDirectory() as temp:
            a, b = Path(temp) / 'a', Path(temp) / 'b'
            a.write_bytes(b'original'); b.write_bytes(b'changed')
            group = {'files': [str(a), str(b)], 'sha256': hashlib.sha256(b'original').hexdigest()}
            with patch.object(tools, 'checked') as command:
                with self.assertRaisesRegex(RuntimeError, 'изменилось'):
                    tools.trash_duplicates(group, [b])
                command.assert_not_called()

    def test_never_trashes_every_copy_and_rejects_symlinks(self):
        with tempfile.TemporaryDirectory() as temp:
            a, b = Path(temp) / 'a', Path(temp) / 'b'
            a.write_bytes(b'same'); b.symlink_to(a)
            group = {'files': [str(a), str(b)], 'sha256': hashlib.sha256(b'same').hexdigest()}
            with patch.object(tools, 'checked') as command:
                with self.assertRaises(ValueError):
                    tools.trash_duplicates(group, [a, b])
                with self.assertRaises(OSError):
                    tools.trash_duplicates(group, [b])
                command.assert_not_called()

    def test_report_is_private(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(tools, 'STATE', Path(temp)):
            report = tools.save_report('test', {'sample': 'data'})
            self.assertEqual(report.stat().st_mode & 0o777, 0o600)
            self.assertEqual(json.loads(report.read_text()), {'sample': 'data'})


if __name__ == '__main__':
    unittest.main()
