import importlib.machinery,importlib.util,tempfile,unittest,wave
from pathlib import Path
from unittest.mock import Mock,patch
ROOT=Path(__file__).resolve().parents[2]
def load(name,path):
 loader=importlib.machinery.SourceFileLoader(name,str(path));spec=importlib.util.spec_from_loader(name,loader);m=importlib.util.module_from_spec(spec);loader.exec_module(m);return m
live=load('live_voice',ROOT/'scripts/local-bin/dictation-live');paste=load('paste_voice',ROOT/'scripts/local-bin/dictation-paste')
class Live(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
  for name,value in [('RUNTIME',self.root),('locked',lambda:False),('notify',Mock()),('active_window',lambda:'0x123')]:
   p=patch.object(live,name,value);p.start();self.addCleanup(p.stop)
 def test_one_pass_gpu_only(self):
  command=live.engine_command(self.root/'a.wav');self.assertEqual(command[-2:],['vulkan','1']);self.assertIn('ggml-medium-q5_0.bin',command[1])
 def test_rejects_silence_and_too_short(self):
  p=self.root/'a.wav'
  for value,frames,expected in [(0,16000,False),(3000,100,False),(3000,16000,True)]:
   with wave.open(str(p),'wb') as w:w.setnchannels(1);w.setsampwidth(2);w.setframerate(16000);w.writeframes(int(value).to_bytes(2,'little',signed=True)*frames)
   self.assertEqual(live.audible(p),expected)
 def test_toggle_stop_and_cancel(self):
  proc=Mock();proc.poll.return_value=None
  with patch.object(live.sp,'Popen',return_value=proc),patch.object(live.threading,'Thread'):
   s=live.Session();self.assertEqual(s.toggle(),'recording');s.last_press=0;self.assertEqual(s.toggle(),'processing');proc.send_signal.assert_called_once_with(live.signal.SIGINT)
   self.assertEqual(s.target,'0x123');s.cancel();self.assertTrue(s.cancelled.is_set());s.cleanup()
 def test_locked_no_microphone(self):
  with patch.object(live,'locked',return_value=True),patch.object(live.sp,'Popen') as spawn:
   self.assertIn('заблокирован',live.Session().toggle());spawn.assert_not_called()
 def test_busy_no_second_engine_or_recording(self):
  s=live.Session();s.phase='processing'
  with patch.object(live.sp,'Popen') as spawn:self.assertIn('Распознаю',s.toggle());spawn.assert_not_called()
 def test_lock_cancels_active_work(self):
  s=live.Session();s.phase='processing'
  with patch.object(live,'locked',return_value=True),patch.object(s,'cancel') as cancel:s.tick();cancel.assert_called_once()
class Paste(unittest.TestCase):
 def test_terminal_and_normal_chords_are_text_only(self):
  for app,chord in [('Terminal','ctrl+shift+v'),('Telegram','ctrl+v')]:
   with patch.object(paste,'locked',return_value=False),patch.object(paste,'context',return_value={'appName':app,'windowId':'0x1'}),patch.object(paste.sp,'run') as run:
    self.assertEqual(paste.paste('ELF','0x1'),'pasted');self.assertIn('UTF8_STRING',run.call_args_list[0].args[0]);self.assertEqual(run.call_args_list[-1].args[0][-1],chord)
 def test_focus_changed_keeps_clipboard_without_keystroke(self):
  with patch.object(paste,'locked',return_value=False),patch.object(paste,'context',return_value={'windowId':'0x2'}),patch.object(paste.sp,'run') as run:
   self.assertEqual(paste.paste('ELF','0x1'),'clipboard');self.assertEqual(run.call_count,1)
 def test_locked_no_clipboard_or_keys(self):
  with patch.object(paste,'locked',return_value=True),patch.object(paste.sp,'run') as run:self.assertEqual(paste.paste('ELF','0x1'),'locked');run.assert_not_called()
if __name__=='__main__':unittest.main()
