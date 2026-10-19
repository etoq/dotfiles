"""Validate a dirty FAT32 repair on a disposable filesystem image, never a device."""
import importlib.util
from pathlib import Path
import shutil
import subprocess as sp
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'maintenance/check-efi-fat.py'
spec = importlib.util.spec_from_file_location('efi_check', SCRIPT)
repair = importlib.util.module_from_spec(spec)
spec.loader.exec_module(repair)


class DirtyFlag(unittest.TestCase):
    def test_accepts_only_expected_byte_change(self):
        with tempfile.TemporaryDirectory() as folder:
            before, after = Path(folder) / 'before', Path(folder) / 'after'
            original = bytearray(1024)
            original[65] = 1
            before.write_bytes(original)
            original[65] = 0
            after.write_bytes(original)
            self.assertTrue(repair.only_dirty_byte_changed(before, after))
            original[511] = 1
            after.write_bytes(original)
            self.assertFalse(repair.only_dirty_byte_changed(before, after))
            after.write_bytes(before.read_bytes())
            self.assertFalse(repair.only_dirty_byte_changed(before, after))

    def test_rejects_different_image_size(self):
        with tempfile.TemporaryDirectory() as folder:
            before, after = Path(folder) / 'before', Path(folder) / 'after'
            before.write_bytes(bytes(100))
            after.write_bytes(bytes(101))
            self.assertFalse(repair.only_dirty_byte_changed(before, after))

    @unittest.skipUnless(shutil.which('mkfs.fat') and shutil.which('fsck.fat'), 'dosfstools required')
    def test_native_fsck_reproduces_and_clears_only_dirty_boot_byte(self):
        with tempfile.TemporaryDirectory() as folder:
            image, original = Path(folder) / 'fat.img', Path(folder) / 'dirty.img'
            sp.run(['mkfs.fat', '-F', '32', '-C', str(image), '65536'], check=True, capture_output=True)
            with image.open('r+b') as stream:
                stream.seek(65)
                self.assertEqual(stream.read(1), b'\0')
                stream.seek(65)
                stream.write(b'\1')
            shutil.copyfile(image, original)
            env = {'LC_ALL': 'C', 'PATH': '/usr/bin'}
            check = sp.run(['fsck.fat', '-n', str(image)], capture_output=True, text=True, env=env)
            self.assertEqual(check.returncode, 1, check.stdout)
            self.assertIn('65:01/00', check.stdout)
            fixed = sp.run(['fsck.fat', '-a', str(image)], capture_output=True, text=True, env=env)
            self.assertIn(fixed.returncode, (0, 1), fixed.stdout)
            self.assertTrue(repair.only_dirty_byte_changed(original, image), fixed.stdout)
            final = sp.run(['fsck.fat', '-n', str(image)], capture_output=True, text=True, env=env)
            self.assertEqual(final.returncode, 0, final.stdout)


if __name__ == '__main__':
    unittest.main()
