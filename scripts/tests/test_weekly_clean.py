#!/usr/bin/python
import importlib.machinery
import importlib.util
import os
from pathlib import Path
import subprocess
import tempfile
import time
import unittest
from unittest.mock import patch
import contextlib
import io

SCRIPT = Path(__file__).resolve().parents[1] / 'local-bin/weekly-clean'
loader = importlib.machinery.SourceFileLoader('weekly_clean', str(SCRIPT))
spec = importlib.util.spec_from_loader(loader.name, loader)
clean = importlib.util.module_from_spec(spec)
loader.exec_module(clean)


class CleanupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.cache = self.root / 'cache'
        self.cache.mkdir()

    def old(self, path, days=40):
        path.write_bytes(b'cached-data')
        age = time.time() - days * clean.DAY
        os.utime(path, (age, age))
        return path

    def test_dry_run_is_read_only_and_counts_old_files(self):
        p = self.old(self.cache / 'old')
        fresh = self.old(self.cache / 'fresh', 1)
        self.assertEqual(clean.old_files(self.cache, 30), (1, 11))
        self.assertTrue(p.exists())
        self.assertTrue(fresh.exists())

    def test_apply_preserves_recently_read_and_fresh_files(self):
        old = self.old(self.cache / 'old')
        recent = self.old(self.cache / 'recently-used')
        os.utime(recent, (time.time(), recent.stat().st_mtime))
        fresh = self.old(self.cache / 'fresh', 1)
        self.assertEqual(clean.old_files(self.cache, 30, True), (1, 11))
        self.assertFalse(old.exists())
        self.assertTrue(recent.exists())
        self.assertTrue(fresh.exists())

    def test_links_and_external_targets_are_untouched(self):
        outside = self.root / 'outside'
        outside.mkdir()
        file = self.old(outside / 'important')
        (self.cache / 'linked-dir').symlink_to(outside, target_is_directory=True)
        (self.cache / 'linked-file').symlink_to(file)
        os.link(file, self.cache / 'hardlink')
        self.assertEqual(clean.old_files(self.cache, 30, True), (0, 0))
        self.assertTrue(file.exists())
        alias = self.root / 'alias'
        alias.symlink_to(self.cache, target_is_directory=True)
        self.assertEqual(clean.old_files(alias, 30, True), (0, 0))

    def test_monthly_interval(self):
        self.assertTrue(clean.month_due(None, 0))
        self.assertFalse(clean.month_due(100, 100 + 29 * clean.DAY))
        self.assertTrue(clean.month_due(100, 100 + 30 * clean.DAY))

    def simulate_run(self, fail=False):
        commands = []
        def fake_run(command, log=None):
            commands.append(list(map(str, command)))
            return not (fail and '--system' in command)
        with patch.object(clean, 'HOME', self.root), patch.object(clean, 'STATE', self.root/'state/weekly-clean'), \
             patch.object(clean, 'trash_roots', return_value=[]), \
             patch.object(clean, 'busy_packages', return_value=False), patch.object(clean, 'run', side_effect=fake_run), \
             patch.object(clean.os, 'geteuid', return_value=1000), patch('sys.argv', ['weekly-clean','--apply']), \
             contextlib.redirect_stdout(io.StringIO()):
            code = clean.main()
        return code, commands

    def trash_entry(self, name, days=40, folder=False):
        root = self.root/'trash'
        (root/'info').mkdir(parents=True, exist_ok=True)
        (root/'files').mkdir(exist_ok=True)
        payload = root/'files'/name
        if folder:
            payload.mkdir()
            (payload/'nested').write_text('discarded')
        else:
            self.old(payload, 100)
        date = clean.dt.datetime.fromtimestamp(time.time()-days*clean.DAY).isoformat(timespec='seconds')
        (root/'info'/(name+'.trashinfo')).write_text('[Trash Info]\nPath=/unused\nDeletionDate='+date+'\n')
        return root, payload

    def test_trash_uses_deletion_date_and_preserves_recently_discarded_old_file(self):
        root, old = self.trash_entry('old')
        _, fresh = self.trash_entry('fresh', days=1)
        self.assertEqual(clean.old_trash(root), (1, 0))
        self.assertTrue(old.exists())
        self.assertEqual(clean.old_trash(root, apply=True), (1, 0))
        self.assertFalse(old.exists())
        self.assertTrue(fresh.exists())
        self.assertTrue((root/'info/fresh.trashinfo').exists())

    def test_trash_folder_cleanup_does_not_follow_external_symlinks(self):
        root, folder = self.trash_entry('folder', folder=True)
        external = self.old(self.root/'keep')
        (folder/'external').symlink_to(external)
        self.assertEqual(clean.old_trash(root, apply=True), (1, 0))
        self.assertFalse(folder.exists())
        self.assertTrue(external.exists())
        self.assertFalse((root/'info/folder.trashinfo').exists())

    def test_trash_invalid_metadata_and_root_symlinks_are_preserved(self):
        root, payload = self.trash_entry('invalid')
        info=root/'info/invalid.trashinfo'
        info.write_text('[Trash Info]\nDeletionDate=not-a-date\n')
        self.assertEqual(clean.old_trash(root, apply=True), (0, 1))
        self.assertTrue(payload.exists())
        info.unlink()
        info.symlink_to(self.old(self.root/'external-meta'))
        self.assertEqual(clean.old_trash(root, apply=True), (0, 1))
        self.assertTrue(payload.exists())
        alias=self.root/'trash-alias'
        alias.symlink_to(root, target_is_directory=True)
        self.assertEqual(clean.old_trash(alias, apply=True), (0, 0))

    def test_monthly_runs_once_after_success(self):
        code, commands = self.simulate_run()
        self.assertEqual(code, 0)
        self.assertTrue(any('--monthly' in cmd for cmd in commands))
        code, commands = self.simulate_run()
        self.assertEqual(code, 0)
        self.assertFalse(any('--monthly' in cmd for cmd in commands))

    def test_failed_monthly_stage_is_retried(self):
        code, commands = self.simulate_run(fail=True)
        self.assertEqual(code, 1)
        self.assertFalse((self.root/'state/weekly-clean/state.json').exists())
        code, commands = self.simulate_run()
        self.assertEqual(code, 0)
        self.assertTrue(any('--monthly' in cmd for cmd in commands))

    def test_real_paccache_preserves_two_versions_and_recent_packages(self):
        names = []
        for version in range(1, 6):
            name = self.cache / f'cleanup-fixture-{version}.0-1-x86_64.pkg.tar.zst'
            self.old(name)
            names.append(name)
        recent = self.old(self.cache / 'cleanup-fixture-0.1-1-x86_64.pkg.tar.zst', 1)
        command = ['paccache', '-r', '-k', '2', '--min-mtime', '7 days ago', '-c', str(self.cache)]
        result = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual([p.exists() for p in names], [False, False, False, True, True])
        self.assertTrue(recent.exists())
        self.assertEqual(subprocess.run(command, capture_output=True).returncode, 0)


if __name__ == '__main__':
    unittest.main()
