"""Check ESP consolidation decisions without accessing or changing the real ESP."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'maintenance/finish-efi-transition.py'
spec = importlib.util.spec_from_file_location('finish_efi', SCRIPT)
repair = importlib.util.module_from_spec(spec)
spec.loader.exec_module(repair)
ENTRY = ('title Arch\nlinux /vmlinuz-linux\ninitrd /intel-ucode.img\n'
         'initrd /initramfs-linux.img\noptions rootflags=subvol=@ rw\n')
SNAPSHOT = ('title Snapshot\nlinux /vmlinuz-linux\ninitrd /initramfs-linux.img\n'
            'options rootflags=subvol=@snapshots/80/snapshot rw\n')


class Consolidation(unittest.TestCase):
    def fixture(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        efi = root / 'efi'
        entries = efi / 'loader/entries'
        entries.mkdir(parents=True)
        (entries / 'arch.conf').write_text(ENTRY)
        (entries / 'arch-snap-76.conf').write_text(SNAPSHOT)
        for name in repair.NAMES:
            (efi / name).write_bytes(b'old')
            path = efi / 'EFI/ARCH' / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b'current')
        return root, efi

    def test_normal_entry_moves_only_kernel_and_initramfs_paths(self):
        expected = ENTRY.replace('linux /vmlinuz', 'linux /EFI/ARCH/vmlinuz').replace('initrd /initramfs', 'initrd /EFI/ARCH/initramfs')
        self.assertEqual(repair.rewrite_entry(ENTRY), expected)
        self.assertFalse(repair.references(expected))

    def test_ambiguous_entry_is_rejected(self):
        with self.assertRaisesRegex(RuntimeError, 'Unexpected'):
            repair.rewrite_entry(ENTRY + 'initrd /initramfs-linux-lts.img\n')

    def test_preflight_leaves_files_untouched(self):
        root, efi = self.fixture()
        normal, stale, updated = repair.preflight(efi, root / 'snapshots', 'linux /@/boot/vmlinuz-linux\n', 'BOOT /EFI/ARCH/grubx64.efi')
        self.assertEqual(normal.read_text(), ENTRY)
        self.assertEqual(stale.read_text(), SNAPSHOT)
        self.assertIn('/EFI/ARCH/initramfs-linux.img', updated)
        self.assertTrue(all((efi / name).exists() for name in repair.NAMES))

    def test_existing_snapshot_prevents_retirement(self):
        root, efi = self.fixture()
        (root / 'snapshots/80/snapshot').mkdir(parents=True)
        with self.assertRaisesRegex(RuntimeError, 'Snapshot 80 still exists'):
            repair.preflight(efi, root / 'snapshots', '', '')

    def test_grub_direct_efi_and_other_loader_references_are_rejected(self):
        root, efi = self.fixture()
        for grub, nvram in [('linux /vmlinuz-linux', ''), ('', r'HD()/\vmlinuz-linux-lts')]:
            with self.subTest(grub=grub, nvram=nvram), self.assertRaisesRegex(RuntimeError, 'GRUB or a direct UEFI'):
                repair.preflight(efi, root / 'snapshots', grub, nvram)
        (efi / 'unknown.conf').write_text('initrd /initramfs-linux.img\n')
        with self.assertRaisesRegex(RuntimeError, 'Another ESP configuration'):
            repair.preflight(efi, root / 'snapshots', '', '')


if __name__ == '__main__':
    unittest.main()
