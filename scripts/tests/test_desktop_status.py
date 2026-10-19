"""Quota warning behavior and lossless read-only health collection."""
import datetime as dt
import importlib.machinery
import importlib.util
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def load(name, path):
    loader = importlib.machinery.SourceFileLoader(name, str(path))
    spec = importlib.util.spec_from_loader(name, loader)
    result = importlib.util.module_from_spec(spec)
    loader.exec_module(result)
    return result


quota = load('quota_test', ROOT / 'local-bin/proton-quota')
health = load('health_test', ROOT / 'system/workstation-health-status')
status = load('status_test', ROOT / 'local-bin/workstation-status')


class DesktopStatus(unittest.TestCase):
    def test_quota_warns_once_then_escalates_without_uploading(self):
        with tempfile.TemporaryDirectory() as folder:
            home = Path(folder)
            plan = home / '.config/workstation-backup/plan.json'
            plan.parent.mkdir(parents=True)
            plan.write_text(json.dumps({'destination': {'connected': True}, 'storage': {'budget_bytes': 1000}}))
            cache = home / 'state/quota.json'
            calls = []
            used = [810]
            def run(args, **kwargs):
                calls.append(args)
                return SimpleNamespace(returncode=0, stdout=json.dumps({'size': used[0]}), stderr='')
            with patch.object(quota, 'HOME', home), patch.object(quota, 'STATE', cache.parent), patch.object(quota, 'CACHE', cache), patch.object(quota.sp, 'run', side_effect=run):
                quota.refresh({})
                quota.refresh(quota.read())
                self.assertEqual(len([c for c in calls if c[0] == 'notify-send']), 1)
                used[0] = 910
                quota.refresh(quota.read())
                self.assertEqual(len([c for c in calls if c[0] == 'notify-send']), 2)
                self.assertEqual(quota.read()['warning_level'], 90)
                for call in calls:
                    if call[0] != 'notify-send':
                        self.assertEqual(call[1:], ['filesystem', 'size', '/my-files', '--json'])

    def test_daily_warning_can_repeat_after_24_hours(self):
        now = dt.datetime.now().astimezone()
        before = {'notified_at': (now - dt.timedelta(hours=25)).isoformat(), 'notified_level': 90}
        self.assertTrue(quota.should_notify(90, before, now))
        self.assertFalse(quota.should_notify(0, before, now))

    def test_refresh_requests_only_readonly_collector(self):
        with patch.object(status, 'os_geteuid', return_value=1000), \
                patch.object(status.Path, 'is_file', return_value=False), \
                patch.object(status.sp, 'run', return_value=SimpleNamespace(returncode=0, stderr='')) as run:
            status.refresh_disk()
        self.assertEqual(run.call_args.args[0], ['/usr/bin/pkexec', '--disable-internal-agent',
                         '/usr/bin/systemctl', 'start', 'workstation-health-status.service'])

    def test_cancelled_refresh_reports_failure_and_closes_temporary_agent(self):
        agent = SimpleNamespace(poll=lambda: None, terminate=lambda: None, wait=lambda **kw: None)
        with patch.object(status, 'os_geteuid', return_value=1000), \
                patch.object(status.Path, 'is_file', return_value=True), \
                patch.object(status.sp, 'Popen', return_value=agent), \
                patch.object(status.time, 'sleep'), \
                patch.object(status.sp, 'run', return_value=SimpleNamespace(returncode=126, stderr='Authentication cancelled')), \
                patch.object(agent, 'terminate') as terminate:
            with self.assertRaisesRegex(RuntimeError, 'Authentication cancelled'):
                status.refresh_disk()
            terminate.assert_called_once()

    def test_readonly_smart_json_is_not_truncated(self):
        data = json.dumps({'padding': 'x' * 6000, 'smart_status': {'passed': True}})
        with patch.object(health.sp, 'run', return_value=SimpleNamespace(returncode=0, stdout=data)):
            result = health.run(['smartctl', '-a', '-j', '/dev/nvme0n1'])
        self.assertTrue(json.loads(result['text'])['smart_status']['passed'])


if __name__ == '__main__':
    unittest.main()
