#!/usr/bin/env python3
"""Convert a local HF Whisper Safetensors checkpoint to whisper.cpp F16 GGML.

Tensor mapping and format follow whisper.cpp models/convert-h5-to-ggml.py
(MIT), revision e4836b0083df42686b60206a00afffc5a3435852. NumPy mmap
avoids installing PyTorch/Transformers just to convert an existing checkpoint.
"""
import json, struct, sys
from pathlib import Path
import numpy as np

MAP = {'self_attn.k_proj':'attn.key','self_attn.q_proj':'attn.query',
 'self_attn.v_proj':'attn.value','self_attn.out_proj':'attn.out',
 'self_attn_layer_norm':'attn_ln','encoder_attn.k_proj':'cross_attn.key',
 'encoder_attn.q_proj':'cross_attn.query','encoder_attn.v_proj':'cross_attn.value',
 'encoder_attn.out_proj':'cross_attn.out','encoder_attn_layer_norm':'cross_attn_ln',
 'fc1':'mlp.0','fc2':'mlp.2','final_layer_norm':'mlp_ln'}

def mapped(name):
 if name == 'proj_out.weight':return None
 if not name.startswith('model.'):raise ValueError('Unexpected tensor '+name)
 name=name.removeprefix('model.')
 parts=name.split('.')
 if parts[1]=='layers':return '.'.join([parts[0],'blocks',parts[2],MAP['.'.join(parts[3:-1])],parts[-1]])
 for source,dest in [('encoder.layer_norm','encoder.ln_post'),('decoder.layer_norm','decoder.ln'),
  ('encoder.embed_positions.weight','encoder.positional_embedding'),
  ('decoder.embed_positions.weight','decoder.positional_embedding'),
  ('decoder.embed_tokens.weight','decoder.token_embedding.weight')]:
  if name==source or name.startswith(source+'.'):return dest+name[len(source):]
 return name

def convert(source,destination):
 cfg=json.loads((source/'config.json').read_text());vocab=json.loads((source/'vocab.json').read_text())
 weights=source/'model.safetensors'
 with weights.open('rb') as stream:
  length=struct.unpack('<Q',stream.read(8))[0]
  if length>10_000_000:raise ValueError('Invalid Safetensors header')
  tensors=json.loads(stream.read(length))
 raw=np.memmap(weights,mode='r',dtype=np.uint8,offset=8+length)
 # GPT-2 byte/unicode mapping, as in the upstream converter.
 byte_values=list(range(33,127))+list(range(161,173))+list(range(174,256));codes=byte_values.copy();n=0
 for b in range(256):
  if b not in byte_values:byte_values.append(b);codes.append(256+n);n+=1
 decoder={chr(c):b for b,c in zip(byte_values,codes)}
 filters=np.load(source/'mel_filters.npz')[f"mel_{cfg['num_mel_bins']}"]
 destination.parent.mkdir(parents=True,exist_ok=True);part=destination.with_suffix('.part')
 with part.open('wb') as out:
  out.write(struct.pack('<12i',0x67676d6c,cfg['vocab_size'],cfg['max_source_positions'],cfg['d_model'],
   cfg['encoder_attention_heads'],cfg['encoder_layers'],cfg['max_target_positions'],cfg['d_model'],
   cfg['decoder_attention_heads'],cfg['decoder_layers'],cfg['num_mel_bins'],1))
  out.write(struct.pack('<2i',*filters.shape));out.write(filters.astype('<f4').tobytes())
  out.write(struct.pack('<i',len(vocab)))
  for token,_ in sorted(vocab.items(),key=lambda item:item[1]):
   data=bytes(decoder[c] for c in token);out.write(struct.pack('<i',len(data)));out.write(data)
  count=0
  for source_name,item in tensors.items():
   if source_name=='__metadata__':continue
   name=mapped(source_name)
   if name is None:continue
   dtype={'F32':'<f4','F16':'<f2'}.get(item['dtype'])
   if dtype is None:raise ValueError('Unsupported tensor dtype '+item['dtype'])
   start,end=item['data_offsets'];shape=item['shape']
   if end-start!=int(np.prod(shape))*np.dtype(dtype).itemsize:raise ValueError('Invalid tensor size')
   data=np.frombuffer(raw[start:end],dtype=dtype).reshape(shape).squeeze()
   if name in ('encoder.conv1.bias','encoder.conv2.bias'):data=data.reshape(-1,1)
   f32=data.ndim<2 or name in ('encoder.conv1.bias','encoder.conv2.bias','encoder.positional_embedding','decoder.positional_embedding')
   encoded=name.encode();out.write(struct.pack('<3i',data.ndim,len(encoded),0 if f32 else 1))
   out.write(struct.pack('<'+'i'*data.ndim,*reversed(data.shape)));out.write(encoded)
   out.write(data.astype('<f4' if f32 else '<f2').tobytes());count+=1
 part.rename(destination);print(f'Converted {count} tensors: {destination}')

if __name__=='__main__':convert(Path(sys.argv[1]),Path(sys.argv[2]))
