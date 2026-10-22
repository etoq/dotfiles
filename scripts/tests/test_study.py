"""Countdown accounting with deterministic clocks and private databases."""
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


class Timers(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.state = Path(self.temp.name) / 'private'
        self.patch = patch.object(study, 'STATE', self.state)
        self.patch.start()
        self.addCleanup(self.patch.stop)
        self.db = study.database()
        self.addCleanup(self.db.close)

    def start(self, kind='work', seconds=60, wall=100, mono=50, boot='test'):
        study.start_timer(self.db, kind, seconds, wall, mono, boot)

    def tick(self, wall, mono, boot='test'):
        with study.transaction(self.db):
            study.advance(self.db, wall, mono, boot)

    def control(self, action, wall, mono):
        study.control(self.db, action, wall, mono, 'test')

    def total(self, kind='work'):
        return self.db.execute('SELECT coalesce(sum(end-start),0) FROM timer_intervals WHERE kind=?',
                               (kind,)).fetchone()[0]

    def test_nothing_is_counted_until_timer_is_started(self):
        self.assertIsNone(study.current_timer(self.db))
        self.tick(90000, 90000)
        self.assertEqual(self.total(), 0)

    def test_work_is_bounded_by_requested_duration(self):
        self.start(seconds=60)
        self.tick(130, 80)
        self.assertEqual(self.total(), 30)
        self.tick(1000, 950)
        self.assertEqual(self.total(), 60)
        self.assertIsNone(study.current_timer(self.db))
        self.tick(2000, 1950)
        self.assertEqual(self.total(), 60)

    def test_pause_and_resume_exclude_pause_time(self):
        self.start()
        self.control('pause', 110, 60)
        self.tick(210, 160)
        self.assertEqual(self.total(), 10)
        self.control('resume', 210, 160)
        self.tick(225, 175)
        self.assertEqual(self.total(), 25)

    def test_cancel_credits_only_elapsed_time(self):
        self.start(seconds=3600)
        self.control('cancel', 120, 70)
        self.tick(1000, 950)
        self.assertEqual(self.total(), 20)
        self.assertIsNone(study.current_timer(self.db))

    def test_rest_and_untracked_timer(self):
        self.start('rest', 10)
        self.tick(110, 60)
        self.start('none', 10, 110, 60)
        self.tick(120, 70)
        self.assertEqual(self.total('rest'), 10)
        self.assertEqual(self.total('work'), 0)
        self.assertEqual(self.db.execute('SELECT count(*) FROM timer_runs').fetchone()[0], 2)
        self.assertEqual(self.db.execute('SELECT count(*) FROM timer_intervals').fetchone()[0], 1)

    def test_only_one_timer_and_repeated_tick_never_double_count(self):
        self.start()
        with self.assertRaises(RuntimeError):
            self.start('rest')
        self.tick(110, 60)
        self.tick(110, 60)
        self.assertEqual(self.total(), 10)

    def test_sleep_does_not_count_and_reboot_interrupts(self):
        self.start()
        self.tick(3710, 60)
        self.assertEqual(self.total(), 10)
        self.assertEqual(study.current_timer(self.db)['elapsed'], 10)
        self.tick(3720, 2, boot='new-boot')
        self.assertIsNone(study.current_timer(self.db))
        self.assertEqual(self.total(), 10)

    def test_clock_change_does_not_invent_time(self):
        self.start()
        self.tick(90000, 55)
        self.assertEqual(self.total(), 5)

    def test_midnight_split(self):
        midnight = dt.datetime(2026, 10, 22).timestamp()
        self.start(seconds=7200, wall=midnight-3600)
        self.tick(midnight+1800, 5450)
        data = study.report(self.db, 'week', midnight+1800)
        self.assertEqual(data['summary_seconds']['day']['work'], 1800)
        self.assertEqual(data['summary_seconds']['week']['work'], 5400)

    def test_month_and_rolling_periods(self):
        first = dt.datetime(2026, 10, 1).timestamp()
        now = dt.datetime(2026, 10, 31, 12).timestamp()
        self.start('rest', 3600, first)
        self.tick(first+3600, 3650)
        self.start('work', 3600, now-3600, 3700)
        self.tick(now, 7300)
        data = study.report(self.db, 'month', now)
        self.assertEqual(len(data['days']), 31)
        self.assertEqual(data['summary_seconds']['month'], {'work': 3600, 'rest': 3600})
        self.assertEqual(data['summary_seconds']['week'], {'work': 3600, 'rest': 0})
        self.assertEqual(len(study.report(self.db, '30', now)['days']), 30)

    def test_old_activity_preserved_but_excluded(self):
        with self.db:
            self.db.execute('CREATE TABLE intervals(start REAL,end REAL,kind TEXT)')
            now = dt.datetime(2026, 10, 22, 12).timestamp()
            self.db.execute("INSERT INTO intervals VALUES (?,?,'work')", (now-1000, now))
        self.assertEqual(study.report(self.db, 'day', now)['summary_seconds']['day']['work'], 0)
        self.assertEqual(self.db.execute('SELECT end-start FROM intervals').fetchone()[0], 1000)

    def test_durations_and_permissions(self):
        self.assertEqual(study.duration('25'), 1500)
        self.assertEqual(study.duration('1.5h'), 5400)
        self.assertEqual(study.hours(5400), '1.50 ч')
        for text in ('0', '-1', 'bad', '999999h'):
            with self.assertRaises(ValueError): study.duration(text)
        self.assertEqual(self.state.stat().st_mode & 0o777, 0o700)
        self.assertEqual((self.state/'activity.sqlite3').stat().st_mode & 0o777, 0o600)

    def test_polybar_only_remaining_time_running_and_paused(self):
        study.start_timer(self.db, 'none', 1500, 100, 50, study.BOOT)
        with patch.object(study.time, 'monotonic', return_value=52):
            self.assertEqual(study.bar_text(), '00:24:58')
        study.control(self.db, 'pause', 102, 52, study.BOOT)
        with patch.object(study.time, 'monotonic', return_value=500):
            self.assertEqual(study.bar_text(), '00:24:58')
        study.control(self.db, 'cancel', 104, 54, study.BOOT)
        self.assertEqual(study.bar_text(), '')
        self.assertEqual(self.total(), 0)

    def test_polybar_does_not_create_a_missing_database(self):
        missing = Path(self.temp.name)/'not-created'
        with patch.object(study, 'STATE', missing):
            self.assertEqual(study.bar_text(), '')
        self.assertFalse(missing.exists())


if __name__ == '__main__':
    unittest.main()
