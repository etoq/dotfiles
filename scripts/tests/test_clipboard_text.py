#!/usr/bin/env python3
"""Regression checks for exact clipboard text, not its flattened menu label."""
import importlib.machinery,importlib.util,struct,unittest
from unittest.mock import patch
from pathlib import Path
loader=importlib.machinery.SourceFileLoader('picker_test',str(Path(__file__).resolve().parents[1]/'local-bin/tiffany-picker'))
spec=importlib.util.spec_from_loader(loader.name,loader);picker=importlib.util.module_from_spec(spec)
with patch("sys.argv", ["picker", "clipboard"]):loader.exec_module(picker)
def field(value):
 b=value.encode('utf-8');return struct.pack('>q',len(b))+b
def record(text,kind=0):return field('test')+bytes([kind])+field(text)
class ClipboardTextTests(unittest.TestCase):
 def test_original_whitespace_and_unicode(self):
  values=['\n  Отступ\n\n\tELF\t\n    main();  \n\n','неразрывный\u00a0пробел','A\r\n\r\n  B\r\n','', '终点 🙂']
  data=struct.pack('>q',len(values))+b''.join(record(t) for t in values)
  actual,images=picker.decode_greenclip(data)
  self.assertEqual(actual,values);self.assertFalse(images)
 def test_images_remain_typed(self):
  actual,images=picker.decode_greenclip(struct.pack('>q',1)+record('hash',1))
  self.assertEqual(actual,['image/png test hash']);self.assertEqual(images,set(actual))
 def test_truncation_rejected(self):
  with self.assertRaises(ValueError):picker.decode_greenclip(struct.pack('>q',1)+record('text')[:-1])
 def test_unknown_variant_rejected(self):
  with self.assertRaises(ValueError):picker.decode_greenclip(struct.pack('>q',1)+record('text',9))
 def test_trailing_bytes_rejected(self):
  with self.assertRaises(ValueError):picker.decode_greenclip(struct.pack('>q',0)+b'extra')
if __name__=='__main__':unittest.main()
