#!/usr/bin/env python3
"""Hermetic backup/retention integration tests: real tar, local fake Proton."""
import contextlib
import datetime
import importlib.machinery
import importlib.util
import io
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / 'local-bin/workstation-backup'
REAL_RUN = subprocess.run
REAL_DATETIME = datetime.datetime


def load_backup():
    loader = importlib.machinery.SourceFileLoader('workstation_backup_test', str(SCRIPT))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


class FakeProton:
    remote = '/my-files/test'

    def __init__(self, root, home):
        self.root = root
        root.mkdir()
        self.client = str(home / '.local/bin/proton-drive')
        self.nodes = {}
        self.trashed = set()
        self.deleted = []
        self.events = []
        self.corrupt_download = False
        self.fail_delete = False
        self.wrong_parent = None
        self.used_override = None
        self.foreign = {'uid': 't~foreign', 'type': 'file'}

    def resolve(self, path):
        leaf = path.removeprefix(self.remote + '/').removeprefix('/trash/')
        key, _, filename = leaf.partition('/')
        node = next((n for n in self.nodes.values() if key in (n['uid'], n['name']['value'])), None)
        if node is None:
            raise KeyError(path)
        return node, filename

    def run(self, args, **kwargs):
        if str(args[0]) != self.client:
            return REAL_RUN(args, **kwargs)
        self.events.append(tuple(args[1:]))
        action = args[2]
        result = None
        status = 0
        if action == 'info':
            if args[3] in ('/my-files', self.remote):
                result = {'uid': 't~root', 'type': 'folder', 'isShared': False, 'isSharedByUrl': False}
            else:
                node, _ = self.resolve(args[3])
                result = dict(node)
                if result['name']['value'] == self.wrong_parent:
                    result['parentUid'] = 't~other-parent'
        elif action == 'create-folder':
            name = args[4]
            if name in self.nodes:
                raise AssertionError('Version name was reused')
            uid = 't~' + str(len(self.events))
            self.nodes[name] = {'uid': uid, 'parentUid': 't~root', 'type': 'folder',
                                'name': {'ok': True, 'value': name}, 'isShared': False, 'isSharedByUrl': False}
            (self.root / uid).mkdir()
        elif action == 'upload':
            node, _ = self.resolve(args[-1])
            for name in args[6:-1]:
                shutil.copy2(name, self.root / node['uid'] / Path(name).name)
        elif action == 'download':
            for name in args[3:-1]:
                node, filename = self.resolve(name)
                dest = Path(args[-1]) / filename
                assert not dest.exists(), 'A real CLI download would prompt about this conflict'
                shutil.copy2(self.root / node['uid'] / filename, dest)
                if self.corrupt_download and filename.endswith('.tar.zst'):
                    dest.write_bytes(b'broken archive')
        elif action == 'size':
            size = sum(p.stat().st_size for p in self.root.rglob('*') if p.is_file())
            result = {'size': size if self.used_override is None else self.used_override}
        elif action == 'list':
            result = ([self.foreign] + [n for n in self.nodes.values() if n['uid'] in self.trashed]
                      if args[3] == '/trash' else [n for n in self.nodes.values() if n['uid'] not in self.trashed])
        elif action == 'trash':
            node, _ = self.resolve(args[3])
            self.trashed.add(node['uid'])
        elif action == 'delete':
            node, _ = self.resolve(args[3])
            assert args[3] == '/trash/' + node['uid'] and node['uid'] in self.trashed
            if self.fail_delete:
                status = 1
            else:
                self.deleted.append(node['name']['value'])
                shutil.rmtree(self.root / node['uid'])
                self.trashed.remove(node['uid'])
                del self.nodes[node['name']['value']]
        else:
            raise AssertionError('Unexpected Proton command: ' + str(args))
        return subprocess.CompletedProcess(args, status, json.dumps(result) if result is not None else '')


class BackupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        home = root / 'home'
        home.mkdir()
        (home / 'dotfiles/.git/objects').mkdir(parents=True)
        (home / 'dotfiles/.git/objects/fixture').write_text('Git history is elsewhere')
        (home / 'dotfiles/image.png').write_bytes(b'wallpaper fixture')
        (home / 'dotfiles/config').write_text('configuration fixture')
        (home / 'passwords.kdbx').write_bytes(b'password database fixture, not user data')
        (home / '.config/keepassxc').mkdir(parents=True)
        (home / '.config/keepassxc/config.ini').write_text('configuration fixture')
        self.backup = load_backup()
        self.backup.H = home
        self.backup.STATE = home / 'state'
        self.backup.PLAN = home / 'plan.json'
        plan = {
            'enabled': True, 'sources': ['dotfiles', 'passwords.kdbx', '.config/keepassxc'],
            'keepass_sources': ['passwords.kdbx', '.config/keepassxc'],
            'exclude': ['dotfiles/.git'], 'retention': {'enabled': True},
            'storage': {'budget_bytes': 2000000000, 'reserve_bytes': 100000000, 'max_archive_bytes': 900000000},
            'destination': {'provider': 'proton-drive', 'connected': True, 'remote_directory': '/my-files/test'},
            'encryption': 'Proton Drive client-side end-to-end encryption',
        }
        self.backup.PLAN.write_text(json.dumps(plan))
        self.cloud = FakeProton(root / 'cloud', home)
        self.stack = contextlib.ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.object(self.backup.sp, 'run', side_effect=self.cloud.run))
        self.stack.enter_context(patch.object(self.backup.os, 'geteuid', return_value=1000))
        self.stack.enter_context(contextlib.redirect_stdout(io.StringIO()))

    def run_backup(self, day, *arguments):
        class Clock(REAL_DATETIME):
            @classmethod
            def now(cls, tz=None):
                return cls(2026, 10, day, 12, 0, 0, tzinfo=datetime.timezone.utc)
        with patch.object(self.backup.datetime, 'datetime', Clock), patch('sys.argv', ['backup', *(arguments or ['--run-once'])]):
            self.backup.main()
        return json.loads((self.backup.STATE / 'status.json').read_text())

    def test_verified_replacement_only_retires_own_old_folder(self):
        first = self.run_backup(1)
        latest = self.run_backup(2)
        self.assertEqual(self.cloud.deleted, [first['run_id']])
        self.assertEqual(list(self.cloud.nodes), [latest['run_id']])
        self.assertEqual(latest['retired_versions'], [first['run_id']])
        manifest = json.loads((self.backup.STATE / 'runs' / latest['run_id'] / 'manifest.json').read_text())
        self.assertIn('dotfiles/image.png', manifest['entries'])
        self.assertFalse(any('/.git' in name for name in manifest['entries']))
        self.assertTrue(latest['restore_verified'])
        self.assertEqual(self.cloud.foreign['uid'], 't~foreign')
        self.assertFalse(any('empty-trash' in event for event in self.cloud.events))

    def test_corrupt_download_never_retires_old_backup(self):
        first = self.run_backup(1)
        self.cloud.corrupt_download = True
        with self.assertRaisesRegex(RuntimeError, 'hash mismatch'):
            self.run_backup(2)
        self.assertIn(first['run_id'], self.cloud.nodes)
        self.assertEqual(self.cloud.deleted, [])
        status = json.loads((self.backup.STATE / 'status.json').read_text())
        self.assertEqual(status['last_full_verified_remote'], first['remote'])

    def test_quota_refusal_happens_before_upload(self):
        first = self.run_backup(1)
        self.cloud.used_override = 2000000000
        before = len([e for e in self.cloud.events if e[1] == 'upload'])
        with self.assertRaisesRegex(RuntimeError, 'Not enough budget'):
            self.run_backup(2)
        self.assertEqual(before, len([e for e in self.cloud.events if e[1] == 'upload']))
        self.assertEqual(list(self.cloud.nodes), [first['run_id']])

    def test_archive_limit_refuses_without_upload(self):
        plan = json.loads(self.backup.PLAN.read_text())
        plan['storage']['max_archive_bytes'] = 1
        self.backup.PLAN.write_text(json.dumps(plan))
        with self.assertRaisesRegex(RuntimeError, 'size limit'):
            self.run_backup(1)
        self.assertFalse(self.cloud.nodes)

    def test_folder_identity_mismatch_stops_deletion(self):
        first = self.run_backup(1)
        self.cloud.wrong_parent = first['run_id']
        with self.assertRaisesRegex(RuntimeError, 'identity'):
            self.run_backup(2)
        self.assertEqual(self.cloud.deleted, [])
        self.assertIn(first['run_id'], self.cloud.nodes)

    def test_interrupted_trash_deletion_is_resumed(self):
        first = self.run_backup(1)
        self.cloud.fail_delete = True
        with self.assertRaisesRegex(RuntimeError, 'Proton command failed'):
            self.run_backup(2)
        self.assertTrue(self.cloud.trashed)
        self.cloud.fail_delete = False
        latest = self.run_backup(3)
        self.assertIn(first['run_id'], self.cloud.deleted)
        self.assertEqual(list(self.cloud.nodes), [latest['run_id']])

    def test_daily_job_backs_up_vault_and_keeps_full(self):
        first = self.run_backup(1)
        daily = self.run_backup(2, '--scheduled', 'keepass')
        self.assertEqual(daily['scope'], 'partial')
        self.assertEqual(daily['sources'], ['passwords.kdbx', '.config/keepassxc'])
        self.assertIn(first['run_id'], self.cloud.nodes)
        self.assertEqual(daily['last_full_verified_remote'], first['remote'])

    def test_disabled_schedule_does_not_contact_proton(self):
        plan = json.loads(self.backup.PLAN.read_text())
        plan['enabled'] = False
        self.backup.PLAN.write_text(json.dumps(plan))
        with patch('sys.argv', ['backup', '--scheduled', 'full']):
            self.backup.main()
        self.assertFalse(self.cloud.events)

    def test_fourteen_distinct_daily_versions_and_removed_source_protection(self):
        records = []
        for day in range(1, 17):
            records.append({'id': str(day), 'scope': 'partial', 'manifest': {'sources': ['vault.kdbx']},
                            'result': {'last_success': f'2026-10-{day:02}T19:00:00+05:00'}})
        records.append({'id': '16-new', 'scope': 'partial', 'manifest': {'sources': ['vault.kdbx']},
                        'result': {'last_success': '2026-10-16T20:00:00+05:00'}})
        targets = self.backup.retention_targets(records, {'keepass_sources': ['vault.kdbx']})
        self.assertEqual({old['id'] for old, _ in targets}, {'1', '2', '16'})
        full = [{'id': 'old', 'scope': 'full', 'manifest': {'sources': ['data', 'removed']}},
                {'id': 'new', 'scope': 'full', 'manifest': {'sources': ['data']}}]
        self.assertEqual(self.backup.retention_targets(full, {}), [])


if __name__ == '__main__':
    unittest.main()
