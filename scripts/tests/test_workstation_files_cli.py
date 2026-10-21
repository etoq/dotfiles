"""Integration tests invoke the built Rust binary only on disposable fixtures."""
import base64
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

BINARY = Path(__file__).resolve().parents[2] / 'tools/workstation-files/target/release/workstation-files'


@unittest.skipUnless(BINARY.exists(), 'Build the release Rust binary first')
class NativeCli(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.tree = self.root / 'tree'
        self.tree.mkdir()
        self.env = {**os.environ, 'XDG_STATE_HOME': str(self.root / 'state')}

    def run_tool(self, *args, ok=True):
        result = subprocess.run([str(BINARY), *map(str, args)], capture_output=True, text=True, env=self.env, timeout=20)
        if ok:
            self.assertEqual(result.returncode, 0, result.stderr)
            return json.loads(result.stdout)
        self.assertNotEqual(result.returncode, 0)
        return result

    def test_growth_new_deleted_and_zero_length_files(self):
        a = self.tree / 'a'; a.write_bytes(b'abc')
        first = self.run_tool('growth', self.tree)
        self.assertTrue(first['baseline_created'])
        self.assertEqual(first['total'], 3)
        a.unlink(); (self.tree / 'new').write_bytes(b'12345678'); (self.tree / 'empty').touch()
        second = self.run_tool('growth', self.tree)
        self.assertEqual(second['delta'], 5)
        self.assertEqual({v['path']: v['state'] for v in second['changes']}, {'a': 'removed', 'new': 'added', 'empty': 'added'})
        (self.tree / 'new').write_bytes(b'x')
        self.run_tool('growth', self.tree, '--no-save')
        again = self.run_tool('growth', self.tree)
        self.assertEqual(again['delta'], -7)
        self.assertEqual(next((self.root / 'state/workstation-tools/growth').glob('*.json')).stat().st_mode & 0o777, 0o600)

    @unittest.skipIf(os.geteuid() == 0, 'Root bypasses fixture permission restrictions')
    def test_incomplete_scan_preserves_baseline(self):
        (self.tree / 'a').write_bytes(b'abc')
        self.run_tool('growth', self.tree)
        snapshot = next((self.root / 'state/workstation-tools/growth').glob('*.json'))
        before = snapshot.read_bytes()
        blocked = self.tree / 'blocked'; blocked.mkdir(); (blocked / 'file').write_bytes(b'longer'); blocked.chmod(0)
        try:
            result = self.run_tool('growth', self.tree)
            self.assertTrue(result['errors'])
            self.assertFalse(result['saved'])
            self.assertEqual(snapshot.read_bytes(), before)
        finally:
            blocked.chmod(0o700)

    def test_embedded_png_extent_and_exact_extraction(self):
        png = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+a3ioAAAAASUVORK5CYII=')
        source = self.tree / 'blob'; source.write_bytes(b'PREFIX' + png + b'TAIL')
        report = self.run_tool('carve', source)
        match = next(c for c in report['candidates'] if c['kind'] == 'PNG')
        self.assertEqual(match['offset'], 6)
        self.assertEqual(match['suggested_length'], len(png))
        out = self.tree / 'extracted.png'
        self.run_tool('carve', source, '--offset', '0x6', '--length', len(png), '--out', out)
        self.assertEqual(out.read_bytes(), png)
        self.assertEqual(out.stat().st_mode & 0o777, 0o600)
        self.run_tool('carve', source, '--offset', 6, '--length', len(png), '--out', out, ok=False)
        self.assertEqual(out.read_bytes(), png)
        self.assertEqual(source.read_bytes(), b'PREFIX' + png + b'TAIL')

    def test_files_are_not_executed_and_report_formats_work(self):
        marker = self.tree / 'EXECUTED'
        a, b = self.tree / 'sample.sh', self.tree / 'sample2.sh'
        a.write_text('#!/bin/sh\ntouch ' + str(marker) + '\nprintf original_string\n')
        b.write_text('#!/bin/sh\ntouch ' + str(marker) + '\nprintf modified_string\n')
        a.chmod(0o700); b.chmod(0o700)
        kind = self.run_tool('kind', a)
        diff = self.run_tool('bindiff', a, b)
        self.run_tool('carve', a)
        self.assertFalse(marker.exists())
        self.assertTrue(kind['mime']['ok'])
        self.assertGreater(diff['bytes']['changed_bytes'], 0)
        self.assertIn('printf modified_string', diff['strings_added'])

    def test_elf_section_content_change_is_detected(self):
        data = Path('/bin/true').read_bytes()
        a, b = self.tree / 'elf-a', self.tree / 'elf-b'
        a.write_bytes(data); b.write_bytes(data)
        # ELF64 little-endian .text offset is obtained from the system reader, not executed.
        import re
        listing = subprocess.check_output(['readelf', '-SW', str(a)], text=True)
        match = re.search(r'\.text\s+PROGBITS\s+[0-9a-f]+\s+([0-9a-f]+)', listing)
        self.assertIsNotNone(match)
        offset = int(match.group(1), 16)
        modified = bytearray(data); modified[offset] ^= 1; b.write_bytes(modified)
        report = self.run_tool('bindiff', a, b)
        changed = next(row for row in report['section_changes'] if row['name'] == '.text')
        self.assertNotEqual(changed['before']['sha256'], changed['after']['sha256'])

    def test_dangerous_special_files_are_rejected(self):
        self.run_tool('kind', '/dev/zero', ok=False)


if __name__ == '__main__':
    unittest.main()
