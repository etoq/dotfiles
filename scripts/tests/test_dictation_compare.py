import importlib.machinery,importlib.util,json,tempfile,threading,unittest,wave
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[2]
def load(name,path):
 loader=importlib.machinery.SourceFileLoader(name,str(path));spec=importlib.util.spec_from_loader(name,loader);m=importlib.util.module_from_spec(spec);loader.exec_module(m);return m
c=load('voice_comparison',ROOT/'scripts/local-bin/dictation-compare');installer=load('voice_installer',ROOT/'scripts/maintenance/prepare-free-dictation.py')
class Compare(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
  self.asset=patch.object(c,'ASSETS',ROOT/'configs/dictation-compare');self.asset.start();self.addCleanup(self.asset.stop)
 def wav(self,channels=1,frames=1600):
  p=self.root/'sample.wav'
  with wave.open(str(p),'wb')as w:w.setnchannels(channels);w.setsampwidth(2);w.setframerate(16000);w.writeframes(b'\0'*(frames*channels*2))
  return p
 def test_score_terms_and_punctuation(self):
  s=c.score('Проверь Ghidra и ptrace.','проверь ghidra и ptrace');self.assertEqual(s['wer_percent'],0);self.assertEqual(s['terms_correct'],2)
  self.assertEqual(c.score('ptrace','ptraceextra')['terms_correct'],0)
 def test_word_errors(self):self.assertEqual(c.score('раз два три','раз другой три')['wer_percent'],33.3)
 def test_empty_reference_is_not_accuracy(self):self.assertIsNone(c.score('','text')['wer_percent'])
 def test_wav_validation(self):
  c.validate_wav(self.wav())
  with self.assertRaises(ValueError):c.validate_wav(self.wav(channels=2))
  with self.assertRaises(ValueError):c.validate_wav(self.wav(frames=0))
 def test_commands_use_local_engines(self):
  for profile in c.PROFILES:
   argv=c.command(profile,self.root/'sample.wav');self.assertFalse(any('http' in a for a in argv))
  self.assertIn('--repeat',c.command('parakeet',self.root/'sample.wav'))
  self.assertIn('vulkan',c.command('turbo-code-gpu',self.root/'sample.wav'))
  self.assertIn('codeswitch',c.command('turbo-code-gpu',self.root/'sample.wav'))
  self.assertIn('cpu',c.command('turbo-base-cpu',self.root/'sample.wav'))
 def test_selected_profiles_only(self):
  class Proc:
   returncode=0
   def communicate(self,timeout=None):return json.dumps({'text':'ELF','load_ms':10,'transcribe_ms':[30,20]}).encode(),None
  with patch.object(c.sp,'Popen',return_value=Proc()) as launch:
   result=c.run_all(self.wav(),'ELF',self.root/'turbo',profiles=['turbo-base-gpu','turbo-code-gpu'])
   self.assertEqual([r['profile'] for r in result],['turbo-base-gpu','turbo-code-gpu']);self.assertEqual(launch.call_count,2)
 def test_batch_preserves_errors_and_exports(self):
  class Proc:
   returncode=0
   def communicate(self,timeout=None):return json.dumps({'text':'Ghidra','load_ms':10,'transcribe_ms':[30,20]}).encode(),None
  with patch.object(c.sp,'Popen',return_value=Proc()) as launch:
   result=c.run_all(self.wav(),'Ghidra',self.root/'results');self.assertEqual(len(result),4);self.assertEqual(launch.call_count,4)
   self.assertTrue(all(r['wer_percent']==0 for r in result));self.assertTrue((self.root/'results/results.csv').exists())
 def test_cancel_does_not_launch_engine(self):
  event=threading.Event();event.set()
  with patch.object(c.sp,'Popen') as launch:self.assertEqual(c.run_all(self.wav(),'Ghidra',self.root/'results',cancel=event),[]);launch.assert_not_called()
 def test_terminal_interrupt_terminates_engine(self):
  from unittest.mock import Mock
  proc=Mock();proc.communicate.side_effect=[KeyboardInterrupt(),(b'',None)]
  with patch.object(c.sp,'Popen',return_value=proc):
   with self.assertRaises(KeyboardInterrupt):c.run_all(self.wav(),'Ghidra',self.root/'interrupted',profiles=['medium-gpu'])
  proc.terminate.assert_called_once()
 def test_checksum_verification_rejects_changed_file(self):
  import hashlib
  p=self.root/'model';p.write_bytes(b'model');manifest={'sha256':hashlib.sha256(b'model').hexdigest(),'size_bytes':5}
  self.assertTrue(installer.valid(p,manifest));p.write_bytes(b'other');self.assertFalse(installer.valid(p,manifest))
if __name__=='__main__':unittest.main()
