import importlib.machinery,importlib.util
from pathlib import Path
import os,queue,sys,tempfile,threading,types,unittest
from unittest.mock import patch
p=Path(__file__).resolve().parents[1]/'local-bin/soniox';loader=importlib.machinery.SourceFileLoader('soniox_test',str(p));spec=importlib.util.spec_from_loader(loader.name,loader);s=importlib.util.module_from_spec(spec);loader.exec_module(s)
class Soniox(unittest.TestCase):
 def test_partial_tokens_do_not_duplicate(self):
  final=[]
  self.assertEqual(s.collect_tokens({'tokens':[{'text':'sys','is_final':False}]},final),'sys')
  self.assertEqual(s.collect_tokens({'tokens':[{'text':'syscall','is_final':True},{'text':' ELF','is_final':False}]},final),'syscall ELF')
  self.assertEqual(s.collect_tokens({'tokens':[{'text':' ELF','is_final':True},{'text':'<end>','is_final':True}]},final),'syscall ELF')
 def test_score(self):
  self.assertEqual(s.score('Ghidra ptrace ELF','Ghidra, ptrace ELF.')['wer_percent'],0)
  self.assertEqual(s.score('Ghidra ptrace ELF','Ghidra other ELF')['wer_percent'],33.3)
 def test_configuration_no_key_in_payload(self):
  config=s.stream_config();self.assertNotIn('api_key',config);self.assertEqual(config['audio_format'],'pcm_s16le');self.assertIn('ptrace',config['context']['terms'])
 def test_key_permissions_and_missing_key(self):
  with tempfile.TemporaryDirectory() as directory,patch.object(s,'KEY',Path(directory)/'api-key'):
   with self.assertRaises(RuntimeError):s.load_key()
 def test_cancel_before_capture_never_starts_mic(self):
  class WS:
   def send(self,x):pass
   def settimeout(self,x):pass
   def close(self):pass
   def recv(self):return ''
  fake=types.SimpleNamespace(create_connection=lambda *a,**k:WS(),WebSocketTimeoutException=TimeoutError)
  with patch.dict(sys.modules,websocket=fake),patch.object(s,'context',return_value={}),patch.object(s,'load_key',return_value='test'),patch.object(s.sp,'Popen') as spawn:
   results=[];session=s.Session(lambda *a:None,lambda *a:results.append(a));session.cancel();session.run();spawn.assert_not_called();self.assertTrue(results)
 def test_complete_stream_and_empty_text_terminator(self):
  import json
  class WS:
   def __init__(self):self.messages=queue.Queue();self.binary=[];self.text=[]
   def send(self,message):
    self.text.append(message)
    if message=='':self.messages.put(json.dumps({'tokens':[{'text':'ptrace','is_final':True}],'finished':True}))
   def send_binary(self,data):self.binary.append(data)
   def settimeout(self,t):pass
   def recv(self):
    try:return self.messages.get(timeout=.05)
    except queue.Empty:raise TimeoutError()
   def close(self):pass
  ws=WS();fake=types.SimpleNamespace(create_connection=lambda *a,**k:ws,WebSocketTimeoutException=TimeoutError)
  reader,writer=os.pipe();os.write(writer,b'\0'*3200)
  class Recorder:
   stdout=os.fdopen(reader,'rb')
   def terminate(self):pass
   def wait(self,timeout=None):pass
  results=[]
  try:
   with patch.dict(sys.modules,websocket=fake),patch.object(s,'context',return_value={}),patch.object(s,'load_key',return_value='test'),patch.object(s.sp,'Popen',return_value=Recorder()),patch.object(s,'atomic_json') as save:
    session=s.Session(lambda *a:None,lambda *a:results.append(a));timer=threading.Timer(.2,session.finish);timer.start();session.run();timer.join()
    self.assertTrue(ws.binary);self.assertEqual(ws.text[-1],'');self.assertEqual(results[0][0]['text'],'ptrace');self.assertIsNone(results[0][1]);save.assert_called_once()
  finally:os.close(writer);Recorder.stdout.close()
if __name__=='__main__':unittest.main()
