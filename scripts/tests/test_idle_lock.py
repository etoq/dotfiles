"""Idle locker must not blank the screen before starting the locker."""
from contextlib import redirect_stdout
import io
import importlib.machinery
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

loader = importlib.machinery.SourceFileLoader('idle_lock', str(Path(__file__).resolve().parents[1] / 'local-bin/idle-screen-lock'))
spec = importlib.util.spec_from_loader(loader.name, loader)
idle = importlib.util.module_from_spec(spec)
loader.exec_module(idle)


class IdleLock(unittest.TestCase):
    def test_waits_for_locker_before_display_off(self):
        locker = SimpleNamespace(poll=lambda: None, wait=lambda: 0)
        calls = []
        ready = iter([1, 0])
        def run(args, **kwargs):
            calls.append(args)
            return SimpleNamespace(returncode=next(ready) if args[0] == 'pgrep' else 0)
        with patch.object(idle.sp, 'Popen', return_value=locker), patch.object(idle.sp, 'run', side_effect=run), patch.object(idle.time, 'sleep'):
            self.assertEqual(idle.main(), 0)
        self.assertEqual([c[0] for c in calls], ['pgrep', 'pgrep', 'xset'])
        self.assertEqual(calls[-1], ['xset', 'dpms', 'force', 'off'])

    def test_failed_locker_does_not_power_off(self):
        locker = SimpleNamespace(poll=lambda: 1, wait=lambda: 1)
        with patch.object(idle.sp, 'Popen', return_value=locker), patch.object(idle.sp, 'run') as run:
            self.assertEqual(idle.main(), 1)
        run.assert_not_called()

    def test_user_service_selects_graphical_session_explicitly(self):
        with patch.dict(idle.os.environ, {}, clear=True), patch.object(idle.os, 'getuid', return_value=1000), patch.object(idle.sp, 'check_output', side_effect=['2\n', 'User=1000\nType=x11\n']):
            self.assertEqual(idle.graphical_session(), '2')

    def test_video_exceptions_do_not_include_yandex_or_paused_media(self):
        playing = {'PlaybackStatus': 'Playing', 'Metadata': {}}
        self.assertFalse(idle.is_video_player('chromium.instance1', {'Identity': 'YandexMusic'}, playing))
        self.assertTrue(idle.is_video_player('firefox.instance1', {'Identity': 'Zen'}, playing))
        self.assertFalse(idle.is_video_player('firefox.instance1', {'Identity': 'Zen'}, {'PlaybackStatus': 'Paused'}))
        audio = {'PlaybackStatus': 'Playing', 'Metadata': {'xesam:url': 'file:///music/song.flac'}}
        self.assertFalse(idle.is_video_player('vlc', {'Identity': 'VLC media player'}, audio))
        video = {'PlaybackStatus': 'Playing', 'Metadata': {'xesam:url': 'file:///movies/movie.mp4'}}
        self.assertTrue(idle.is_video_player('vlc', {'Identity': 'VLC media player'}, video))

    def test_video_pause_starts_a_fresh_full_countdown(self):
        clock = {'now': 0.0}
        def wait(timeout):
            clock['now'] += timeout
            return False
        events = SimpleNamespace(wait=wait, close=lambda: None)
        observer = SimpleNamespace(poll=lambda: None if clock['now'] < 14 else 0)
        starts = []
        def start(command):
            starts.append(clock['now'])
            return SimpleNamespace(poll=lambda: None)
        with patch.object(idle.time, 'monotonic', side_effect=lambda: clock['now']), patch.object(idle.sp, 'Popen', side_effect=start), redirect_stdout(io.StringIO()):
            with self.assertRaisesRegex(RuntimeError, 'observer exited'):
                idle.monitor(events, observer, timeout=2, video_check=lambda: clock['now'] < 6)
        # Playback is checked at 0, 5 and 10 seconds; after detecting pause at
        # 10 the entire two-second inactivity interval must still elapse.
        self.assertEqual(len(starts), 1)
        self.assertGreaterEqual(starts[0], 12)


if __name__ == '__main__':
    unittest.main()
