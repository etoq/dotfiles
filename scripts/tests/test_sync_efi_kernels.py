"""Exercise the real copy script against disposable boot/EFI trees."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'system/sync-efi-kernels'


class EFICopy(unittest.TestCase):
    def exercise(self, available):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        boot = root / 'boot'
        target = boot / 'efi/EFI/ARCH'
        target.mkdir(parents=True)
        (boot / 'vmlinuz-linux').write_bytes(b'new kernel')
        (boot / 'initramfs-linux.img').write_bytes(b'new larger boot image')
        (target / 'vmlinuz-linux').write_bytes(b'old kernel')
        (target / 'initramfs-linux.img').write_bytes(b'old image')
        binaries = root / 'bin'
        binaries.mkdir()
        for name, source in {
            'mountpoint': '#!/bin/sh\nexit 0\n',
            'df': '#!/bin/sh\nprintf "Filesystem Size Used Available Capacity Mounted\\nmock 0 0 ' + str(available) + ' 0 target\\n"\n',
        }.items():
            path = binaries / name
            path.write_text(source)
            path.chmod(0o755)
        script = root / 'copy'
        script.write_text(SCRIPT.read_text().replace('/boot', str(boot)))
        result = subprocess.run(['bash', str(script)], env={**os.environ, 'PATH': str(binaries) + ':/usr/bin'}, capture_output=True, text=True)
        return result, boot, target

    def test_insufficient_space_preserves_all_existing_efi_images(self):
        # First image would fit; the second would not. Neither must be replaced.
        result, boot, target = self.exercise(8388618)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('no images replaced', result.stderr)
        self.assertEqual((target / 'vmlinuz-linux').read_bytes(), b'old kernel')
        self.assertEqual((target / 'initramfs-linux.img').read_bytes(), b'old image')
        self.assertFalse(list(target.glob('.*.new')))

    def test_sufficient_space_copies_both_images_without_temporary_leftovers(self):
        result, boot, target = self.exercise(10000000)
        self.assertEqual(result.returncode, 0, result.stderr)
        for name in ('vmlinuz-linux', 'initramfs-linux.img'):
            self.assertEqual((target / name).read_bytes(), (boot / name).read_bytes())
        self.assertFalse(list(target.glob('.*.new')))


if __name__ == '__main__':
    unittest.main()
