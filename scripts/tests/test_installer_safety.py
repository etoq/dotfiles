"""Exercise file preservation and restoration payload compatibility."""
import importlib.util
import importlib.machinery
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[2]


class InstallerSafety(unittest.TestCase):
    def test_missing_source_preserves_existing_target(self):
        source = (REPO / 'install.sh').read_text()
        link = re.search(r'^link\(\) \{.*?^\}', source, re.S | re.M)[0]
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            (base / 'target').write_text('keep my settings')
            script = 'warn(){ :; }; ok(){ :; }; DOTFILES_DIR=$1; HOME=$1; BACKUP_DIR=$1/backup\n' + link + '\nlink missing "$HOME/target"\n'
            subprocess.run(['bash', '-e', '-c', script, 'test', folder], check=True)
            self.assertEqual((base / 'target').read_text(), 'keep my settings')

    def test_current_sleep_payload_is_idempotent(self):
        loader = importlib.machinery.SourceFileLoader('policy_installer', str(REPO / 'scripts/system/nvidia470-sleep-policy'))
        spec = importlib.util.spec_from_loader('policy_installer', loader)
        policy = importlib.util.module_from_spec(spec)
        loader.exec_module(policy)
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for relative in ['modprobe.d/nvidia.conf', 'modprobe.d/nvidia-power-management.conf', 'modprobe.d/90-nvidia-sleep-policy.conf', 'modprobe.d/nvidia-580xx-utils.conf', 'mkinitcpio.conf.d/95-workstation-nvidia-late.conf', 'systemd/system/systemd-suspend.service.d/60-workstation-nvidia-vram.conf']:
                dest = root / 'etc' / relative
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes((REPO / 'configs/etc' / relative).read_bytes())
            hook = root / 'usr/lib/systemd/system-sleep/nvidia'
            hook.parent.mkdir(parents=True)
            hook.write_text('#!/bin/sh\n')
            hook.chmod(0o755)
            self.assertEqual(policy.enforce_files(root, 'preserve-vram'), [])


if __name__ == '__main__':
    unittest.main()
