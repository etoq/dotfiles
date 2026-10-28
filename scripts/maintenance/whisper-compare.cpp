// Local repeated benchmark using the public whisper.cpp API (MIT).
#include "whisper.h"
#include "ggml-backend.h"
#include <chrono>
#include <cstdint>
#include <cstdio>
#include <fstream>
#include <iostream>
#include <iterator>
#include <stdexcept>
#include <string>
#include <vector>
using Clock=std::chrono::steady_clock;
static double ms(Clock::time_point start){return std::chrono::duration<double,std::milli>(Clock::now()-start).count();}
static std::string quote(const std::string &s){
 std::string r="\"";for(unsigned char c:s){if(c=='"'||c=='\\')r+='\\';if(c<32){char b[7];snprintf(b,7,"\\u%04x",c);r+=b;}else r+=c;}return r+'"';
}
static uint32_t u32(const std::vector<unsigned char>&b,size_t n){if(n+4>b.size())throw std::runtime_error("Truncated WAV");return b[n]|b[n+1]<<8|b[n+2]<<16|uint32_t(b[n+3])<<24;}
static uint16_t u16(const std::vector<unsigned char>&b,size_t n){return u32(b,n)&65535;}
int main(int argc,char **argv){
 whisper_context *ctx=nullptr;
 try{
  if(argc!=5)throw std::runtime_error("model wav prompt-file cpu|vulkan required");
  std::ifstream f(argv[2],std::ios::binary);std::vector<unsigned char>b((std::istreambuf_iterator<char>(f)),{});
  if(b.size()<12||std::string(b.begin(),b.begin()+4)!="RIFF"||std::string(b.begin()+8,b.begin()+12)!="WAVE")throw std::runtime_error("Invalid WAV");
  std::vector<float>audio;bool format=false;
  for(size_t p=12;p+8<=b.size();){uint32_t n=u32(b,p+4);size_t a=p+8;if(a+n>b.size())throw std::runtime_error("Invalid WAV chunk");std::string id(b.begin()+p,b.begin()+p+4);
   if(id=="fmt "){if(n<16||u16(b,a)!=1||u16(b,a+2)!=1||u32(b,a+4)!=16000||u16(b,a+14)!=16)throw std::runtime_error("Need PCM16 mono 16kHz");format=true;}
   if(id=="data"){for(size_t i=a;i+1<a+n;i+=2)audio.push_back(static_cast<int16_t>(b[i]|b[i+1]<<8)/32768.0f);}p=a+n+(n%2);
  }
  if(!format||audio.empty())throw std::runtime_error("Empty/unsupported WAV");
  std::ifstream pf(argv[3]);std::string prompt((std::istreambuf_iterator<char>(pf)),{});
  bool gpu=std::string(argv[4])=="vulkan";auto cp=whisper_context_default_params();cp.use_gpu=gpu;cp.flash_attn=true;
  auto start=Clock::now();ctx=whisper_init_from_file_with_params(argv[1],cp);if(!ctx)throw std::runtime_error("Cannot load Whisper");double load=ms(start);
  if(gpu){bool found=false;for(size_t i=0;i<ggml_backend_dev_count();i++)if(ggml_backend_dev_type(ggml_backend_dev_get(i))==GGML_BACKEND_DEVICE_TYPE_GPU)found=true;if(!found)throw std::runtime_error("No GPU backend available; Vulkan test cannot silently fall back to CPU");}
  std::vector<double>times;std::vector<std::string>texts;
  for(int r=0;r<2;r++){
   auto p=whisper_full_default_params(WHISPER_SAMPLING_BEAM_SEARCH);p.n_threads=4;p.language="ru";p.translate=false;p.initial_prompt=prompt.c_str();
   p.no_context=true;p.print_realtime=false;p.print_progress=false;p.print_timestamps=false;p.print_special=false;p.beam_search.beam_size=5;p.beam_search.patience=-1.0f;p.temperature_inc=0;
   start=Clock::now();if(whisper_full(ctx,p,audio.data(),audio.size()))throw std::runtime_error("Transcription failed");times.push_back(ms(start));
   std::string text;for(int i=0;i<whisper_full_n_segments(ctx);i++)text+=whisper_full_get_segment_text(ctx,i);texts.push_back(text);
  }
  whisper_free(ctx);ctx=nullptr;
  std::cout<<"{\"text\":"<<quote(texts.back())<<",\"texts\":["<<quote(texts[0])<<","<<quote(texts[1])<<"],\"load_ms\":"<<load<<",\"transcribe_ms\":["<<times[0]<<","<<times[1]<<"],\"audio_secs\":"<<audio.size()/16000.0<<",\"backend\":"<<quote(gpu?"Vulkan":"CPU")<<",\"decoding\":\"beam_size=5; flash_attn=1; ru; RE prompt; no LLM\"}\n";
 }catch(const std::exception&e){if(ctx)whisper_free(ctx);std::cerr<<e.what()<<'\n';return 1;}
}
