import importlib.machinery
import importlib.util
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[2]
def load(name,path):
 loader=importlib.machinery.SourceFileLoader(name,str(path));spec=importlib.util.spec_from_loader(name,loader);mod=importlib.util.module_from_spec(spec);loader.exec_module(mod);return mod
ctx=load('context_test',ROOT/'scripts/local-bin/wispr-context')
installer=load('context_installer',ROOT/'scripts/maintenance/install-wispr-context.py')
class Context(unittest.TestCase):
 def test_forks_are_telegram(self):
  for name in ['AyuGram','com.ayugram.desktop','TelegramDesktop','64Gram']:
   self.assertEqual(ctx.classify(name)['bundleId'],'Telegram')
 def test_ai_desktop(self):
  self.assertEqual(ctx.classify('chatgpt')['bundleId'],'com.openai.chat')
  self.assertEqual(ctx.classify('Claude')['bundleId'],'com.anthropic.claudefordesktop')
 def test_cli_agent_uses_executable_not_title(self):
  self.assertEqual(ctx.classify('codex-terminal',executables={'kitty','codex'})['codingCliAgent'],'codex')
  self.assertNotIn('codingCliAgent',ctx.classify('kitty',title='codex tutorial'))
 def test_browser_hints_are_conservative(self):
  self.assertEqual(ctx.classify('zen',title='New chat — ChatGPT — Zen Browser')['appName'],'ChatGPT')
  self.assertEqual(ctx.classify('zen',title='ChatGPT tutorial — Wikipedia — Zen Browser')['appName'],'zen')
  self.assertEqual(ctx.classify('zen',title='Claude')['url'],'')
 def test_no_silent_patch_on_unknown_version(self):
  with self.assertRaises(RuntimeError):installer.patch_bundle('unknown version',Path('/tmp/bridge.cjs'))
if __name__=='__main__':unittest.main()
