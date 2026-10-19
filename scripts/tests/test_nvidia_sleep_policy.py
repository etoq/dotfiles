"""Verify callback policy against both package layouts without touching the host."""
import importlib.machinery
import importlib.util
from pathlib import Path
import tempfile
import unittest
import subprocess as sp

SCRIPT = Path(__file__).resolve().parents[1] / 'system/nvidia470-sleep-policy'
loader = importlib.machinery.SourceFileLoader('nvidia_sleep_policy', str(SCRIPT))
spec = importlib.util.spec_from_loader(loader.name, loader)
policy = importlib.util.module_from_spec(spec)
loader.exec_module(policy)


class CallbackPolicy(unittest.TestCase):
    def test_full_vram_roundtrip_restores_callback_and_preserves_other_options(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            config = root / 'etc/modprobe.d/nvidia.conf'
            config.parent.mkdir(parents=True)
            config.write_text('options nvidia NVreg_EnableMSI=0 NVreg_PreserveVideoMemoryAllocations=0 NVreg_TemporaryFilePath=/var/tmp\n')
            hook = root / 'usr/lib/systemd/system-sleep/nvidia'
            hook.parent.mkdir(parents=True)
            hook.write_text('#!/bin/sh\n')
            hook.chmod(0o644)
            policy.enforce_files(root)
            before = config.read_bytes()
            policy.enforce_files(root, 'preserve-vram')
            self.assertIn('NVreg_PreserveVideoMemoryAllocations=1', config.read_text())
            self.assertIn('NVreg_EnableMSI=0', config.read_text())
            self.assertEqual(hook.stat().st_mode & 0o777, 0o755)
            self.assertTrue((root / policy.LATE_PATH).exists())
            self.assertTrue((root / policy.GATE_PATH).exists())
            self.assertEqual(policy.enforce_files(root, 'preserve-vram'), [])
            policy.enforce_files(root, 'callback')
            self.assertEqual(config.read_bytes(), before)
            self.assertEqual(hook.stat().st_mode & 0o777, 0o644)
            self.assertFalse((root / policy.LATE_PATH).exists())
            self.assertFalse((root / policy.GATE_PATH).exists())
            self.assertEqual(policy.enforce_files(root, 'callback'), [])

    def test_late_loading_config_keeps_encryption_and_unrelated_modules(self):
        with tempfile.TemporaryDirectory() as folder:
            config = Path(folder) / 'late.conf'
            config.write_text(policy.LATE_CONFIG)
            source = 'MODULES=(btrfs nvidia nvidia_modeset nvidia_uvm nvidia_drm thinkpad_acpi); HOOKS=(base udev autodetect microcode modconf kms keyboard keymap consolefont block encrypt filesystems fsck); source "$1"; declare -p MODULES HOOKS'
            result = sp.check_output(['bash', '-c', source, 'test', str(config)], text=True)
            modules, hooks = result.splitlines()
            self.assertIn('btrfs', modules)
            self.assertIn('thinkpad_acpi', modules)
            self.assertNotIn('nvidia', modules)
            self.assertNotIn('"kms"', hooks)
            self.assertIn('"encrypt"', hooks)
            self.assertIn('"keyboard"', hooks)

    def test_custom_dropin_is_rejected_before_modprobe_changes(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            collision = root / policy.LATE_PATH
            collision.parent.mkdir(parents=True)
            collision.write_text('# User configuration\n')
            config = root / 'etc/modprobe.d/nvidia.conf'
            config.parent.mkdir(parents=True)
            config.write_text('options nvidia NVreg_PreserveVideoMemoryAllocations=0\n')
            with self.assertRaisesRegex(RuntimeError, 'Custom configuration'):
                policy.enforce_files(root, 'preserve-vram')
            self.assertIn('Allocations=0', config.read_text())
            self.assertEqual(collision.read_text(), '# User configuration\n')

    def test_unknown_profile_never_writes_files(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            with self.assertRaisesRegex(RuntimeError, 'Unknown'):
                policy.enforce_files(root, 'typo')
            self.assertEqual(list(root.iterdir()), [])

    def test_580_override_preserves_vendor_settings_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            vendor = root / 'usr/lib/modprobe.d/nvidia-580xx-utils.conf'
            vendor.parent.mkdir(parents=True)
            original = 'blacklist nouveau\nsoftdep nvidia post: nvidia-uvm\noptions nvidia NVreg_PreserveVideoMemoryAllocations=1\n'
            vendor.write_text(original)
            hook = root / 'usr/lib/systemd/system-sleep/nvidia'
            hook.parent.mkdir(parents=True)
            hook.write_text('#!/bin/sh\n')
            hook.chmod(0o755)
            policy.enforce_files(root)
            self.assertEqual(vendor.read_text(), original)
            override = root / 'etc/modprobe.d' / vendor.name
            self.assertIn(original.replace('Allocations=1', 'Allocations=0'), override.read_text())
            self.assertEqual(hook.stat().st_mode & 0o777, 0o644)
            self.assertEqual(policy.enforce_files(root), [])

    def test_existing_custom_overrides_and_470_options_are_preserved(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            config = root / 'etc/modprobe.d'
            config.mkdir(parents=True)
            existing = config / 'nvidia.conf'
            existing.write_text('options nvidia NVreg_EnableMSI=0 NVreg_PreserveVideoMemoryAllocations=1\n')
            policy.enforce_files(root)
            self.assertEqual(existing.read_text(), 'options nvidia NVreg_EnableMSI=0 NVreg_PreserveVideoMemoryAllocations=0\n')
            self.assertFalse((config / 'nvidia-580xx-utils.conf').exists())


if __name__ == '__main__':
    unittest.main()
