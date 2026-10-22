"""Accounting invariants; no real activity database, input or clock changes."""
import datetime as dt
import importlib.machinery
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

PATH = Path(__file__).resolve().parents[1] / 'local-bin/study'
loader = importlib.machinery.SourceFileLoader('study_test_module', str(PATH))
spec = importlib.util.spec_from_loader(loader.name, loader)
study = importlib.util.module_from_spec(spec)
loader.exec_module(study)


class Accounting(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.state = Path(self.temp.name) / 'private'
        self.patch = patch.object(study, 'STATE', self.state)
        self.patch.start()
        self.addCleanup(self.patch.stop)
        self.db = study.database()
        self.addCleanup(self.db.close)

    def total(self):
        return self.db.execute('SELECT coalesce(sum(end-start),0) FROM intervals').fetchone()[0]

    def test_work_and_rest_are_separate_and_merge_only_contiguous(self):
        study.record(self.db, 100, 105, 'work')
        study.record(self.db, 105, 110, 'work')
        study.record(self.db, 110, 115, 'rest')
        study.record(self.db, 120, 125, 'rest')
        self.assertEqual(self.db.execute('SELECT start,end,kind FROM intervals').fetchall(),
                         [(100, 110, 'work'), (110, 115, 'rest'), (120, 125, 'rest')])

    def test_default_off_and_timer_mode_cannot_write_intervals(self):
        self.assertEqual(study.value(self.db, 'mode'), 'off')
        for kind in ('off', 'timer', 'unknown'):
            study.record(self.db, 0, 50, kind)
        self.assertEqual(self.total(), 0)

    def test_active_sample(self):
        old = (100, 50, 50, 49, True, 'work')
        now = (105, 55, 55, 54, True, 'work')
        self.assertTrue(study.sample(self.db, old, now, 300))
        self.assertEqual(self.total(), 5)

    def test_idle_cutoff_clips_interval(self):
        old = (398, 348, 348, 50, True, 'rest')
        now = (403, 353, 353, 50, True, 'rest')
        study.sample(self.db, old, now, 300)
        self.assertEqual(self.total(), 2)
        study.sample(self.db, now, (408, 358, 358, 50, True, 'rest'), 300)
        self.assertEqual(self.total(), 2)

    def test_locked_inactive_pause_and_mode_switch_do_not_count(self):
        old = (100, 50, 50, 49, True, 'work')
        for unlocked, mode in [(False, 'work'), (True, 'off'), (True, 'rest')]:
            study.sample(self.db, old, (105, 55, 55, 54, unlocked, mode), 300)
        study.sample(self.db, (100, 50, 50, 49, False, 'work'),
                     (105, 55, 55, 54, True, 'work'), 300)
        self.assertEqual(self.total(), 0)

    def test_no_input_no_credit(self):
        study.sample(self.db, (100, 50, 50, None, True, 'work'),
                     (105, 55, 55, None, True, 'work'), 300)
        self.assertEqual(self.total(), 0)

    def test_suspend_and_wall_clock_jumps_never_create_hours(self):
        old = (100, 50, 50, 49, True, 'work')
        for sample in [(3705, 55, 3655, 54, True, 'work'),
                       (105, 55, 3655, 54, True, 'work'),
                       (95, 55, 55, 54, True, 'work'),
                       (110, 55, 55, 54, True, 'work')]:
            self.assertFalse(study.sample(self.db, old, sample, 300))
        self.assertEqual(self.total(), 0)

    def test_report_splits_midnight_and_excludes_future(self):
        midnight = dt.datetime(2026, 10, 22).timestamp()
        study.record(self.db, midnight-3600, midnight+3600, 'work')
        data = study.report(self.db, 'week', midnight+1800)
        self.assertEqual(data['summary_seconds']['day']['work'], 1800)
        self.assertEqual(data['summary_seconds']['week']['work'], 5400)

    def test_month_includes_day_one_on_31st_and_rolling_week_is_separate(self):
        first = dt.datetime(2026, 10, 1).timestamp()
        now = dt.datetime(2026, 10, 31, 12).timestamp()
        study.record(self.db, first, first+3600, 'rest')
        study.record(self.db, now-7200, now-3600, 'work')
        data = study.report(self.db, 'month', now)
        self.assertEqual(len(data['days']), 31)
        self.assertEqual(data['summary_seconds']['month'], {'work': 3600, 'rest': 3600})
        self.assertEqual(data['summary_seconds']['week'], {'work': 3600, 'rest': 0})
        self.assertEqual(data['summary_seconds']['30'], {'work': 3600, 'rest': 0})
        rolling = study.report(self.db, '30', now)
        self.assertEqual(len(rolling['days']), 30)
        self.assertEqual(rolling['summary_seconds']['month'], {'work': 3600, 'rest': 3600})

    def test_duration_validation_and_decimal_hours(self):
        self.assertEqual(study.duration('25'), 1500)
        self.assertEqual(study.duration('1.5h'), 5400)
        self.assertEqual(study.duration('1s'), 1)
        self.assertEqual(study.hours(5400), '1.50 ч')
        for text in ('0', '-1', 'garbage', '8d', '999999999h'):
            with self.assertRaises(ValueError):
                study.duration(text)

    def test_private_storage(self):
        self.assertEqual(self.state.stat().st_mode & 0o777, 0o700)
        self.assertEqual((self.state / 'activity.sqlite3').stat().st_mode & 0o777, 0o600)


if __name__ == '__main__':
    unittest.main()
