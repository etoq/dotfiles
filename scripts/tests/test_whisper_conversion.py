import importlib.util,json,struct,tempfile,unittest
from pathlib import Path
import numpy as np
spec=importlib.util.spec_from_file_location('convert_whisper',Path(__file__).resolve().parents[1]/'maintenance/convert-whisper-safetensors.py')
converter=importlib.util.module_from_spec(spec);spec.loader.exec_module(converter)

class Conversion(unittest.TestCase):
 def test_actual_whisper_names(self):
  self.assertEqual(converter.mapped('model.decoder.layers.3.encoder_attn.k_proj.weight'),'decoder.blocks.3.cross_attn.key.weight')
  self.assertEqual(converter.mapped('model.encoder.embed_positions.weight'),'encoder.positional_embedding')
  self.assertIsNone(converter.mapped('proj_out.weight'))
  with self.assertRaises(ValueError):converter.mapped('untrusted.weight')
 def test_small_checkpoint_preserves_tensor_values_and_format(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);cfg=dict(vocab_size=1,max_source_positions=2,d_model=2,encoder_attention_heads=1,encoder_layers=1,max_target_positions=2,decoder_attention_heads=1,decoder_layers=1,num_mel_bins=2)
   (root/'config.json').write_text(json.dumps(cfg));(root/'vocab.json').write_text('{"a":0}');np.savez(root/'mel_filters.npz',mel_2=np.ones((2,3),dtype='f4'))
   data=np.array([[1,2],[3,4]],dtype='<f4');name='model.decoder.layers.0.fc1.weight';header=json.dumps({name:dict(dtype='F32',shape=[2,2],data_offsets=[0,16])}).encode()
   (root/'model.safetensors').write_bytes(struct.pack('<Q',len(header))+header+data.tobytes());out=root/'converted.bin';converter.convert(root,out);raw=out.read_bytes()
   self.assertEqual(struct.unpack_from('<i',raw)[0],0x67676d6c)
   self.assertIn(b'decoder.blocks.0.mlp.0.weight',raw);self.assertEqual(raw[-8:],data.astype('<f2').tobytes())
if __name__=='__main__':unittest.main()
