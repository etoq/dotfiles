"""Verify callback policy against both package layouts without touching the host."""
import importlib.machinery
import importlib.util
from pathlib import Path
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'system/nvidia470-sleep-policy'
loader = importlib.machinery.SourceFileLoader('nvidia_sleep_policy', str(SCRIPT))
spec = importlib.util.spec_from_loader(loader.name, loader)
policy = importlib.util.module_from_spec(spec)
loader.exec_module(policy)


class CallbackPolicy(unittest.TestCase):
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
