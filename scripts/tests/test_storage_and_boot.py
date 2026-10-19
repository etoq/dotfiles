"""Check boot edits and sensor readiness without touching host devices."""
import importlib.machinery
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1]


def module(name, path):
    loader = importlib.machinery.SourceFileLoader(name, str(path))
    spec = importlib.util.spec_from_loader(name, loader)
    result = importlib.util.module_from_spec(spec)
    loader.exec_module(result)
    return result


storage = module('storage_boot', SCRIPTS / 'maintenance/finish-storage-and-boot.py')
fan = module('fan_ready', SCRIPTS / 'system/thinkfan-wait-ready')


class StorageEdits(unittest.TestCase):
    def test_unlock_options_preserved_and_idempotent(self):
        original = "GRUB_CMDLINE_LINUX='quiet " + storage.CRYPT + ":some-option rootflags=subvol=@'\n"
        result = storage.boot_options(original)
        self.assertEqual(result, original.replace(':some-option ', ':some-option,allow-discards '))
        self.assertEqual(storage.boot_options(result), result)

    def test_other_encrypted_devices_are_unchanged(self):
        other = storage.CRYPT.replace('cryptroot', 'cryptvms')
        original = storage.CRYPT + ' ' + other + '\n'
        self.assertEqual(storage.boot_options(original), storage.CRYPT + ':allow-discards ' + other + '\n')

    def test_unknown_root_is_rejected(self):
        with self.assertRaisesRegex(RuntimeError, 'absent'):
            storage.boot_options('cryptdevice=UUID=other:cryptroot')

    def test_weekly_mount_policy_preserves_other_filesystems(self):
        original = '# comment\nUUID=' + storage.ROOT_UUID + '\t/\tbtrfs\trw,discard=async,compress=zstd:3\t0 0\n'
        vm = '/dev/mapper/cryptvms /vms ext4 defaults,noatime 0 2\n'
        result = storage.mount_options(original + vm)
        self.assertEqual(result, original.replace('discard=async,', '').replace('compress=zstd:3', 'compress=zstd:3,nodiscard') + vm)
        self.assertEqual(storage.mount_options(result), result)

    def test_absent_root_mount_is_rejected(self):
        with self.assertRaisesRegex(RuntimeError, 'absent'):
            storage.mount_options('/dev/mapper/cryptvms /vms ext4 defaults 0 2\n')


class SensorWait(unittest.TestCase):
    def test_renumbered_hwmon_is_found_by_name(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            device = root / 'hwmon42'
            device.mkdir()
            (device / 'name').write_text('coretemp\n')
            (device / 'temp1_input').write_text('45000\n')
            interface = root / 'fan'
            interface.write_text('status:\t enabled\n')
            config = {'sensors': [{'hwmon': folder, 'name': 'coretemp', 'indices': [1]}], 'fans': [{'tpacpi': str(interface)}]}
            self.assertTrue(fan.ready(config))
            (device / 'name').write_text('other')
            self.assertFalse(fan.ready(config))

    def test_ready_sensors_have_no_fixed_delay(self):
        with patch.object(fan, 'ready', return_value=True):
            self.assertTrue(fan.wait({}, clock=lambda: 0, sleep=lambda _: self.fail('unnecessary delay')))

    def test_missing_sensors_are_bounded(self):
        with patch.object(fan, 'ready', side_effect=OSError('not available')):
            self.assertFalse(fan.wait({}, timeout=1, clock=iter([0, 0, 2]).__next__, sleep=lambda _: None))


if __name__ == '__main__':
    unittest.main()
