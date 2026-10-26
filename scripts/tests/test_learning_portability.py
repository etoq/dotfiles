#!/usr/bin/env python3
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile
import tomllib
import unittest

REPO=Path(__file__).resolve().parents[2]
INSTALL=REPO/'scripts/maintenance/install-learning.py'
BACKUP=REPO/'scripts/maintenance/backup-learning.py'
RUNTIME=REPO/'learning/concept-loom'
spec=importlib.util.spec_from_file_location('learning_installer',INSTALL)
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
ROADMAPS={'English_For_Linux_RE.md','Linux_Malware_Roadmap.md','Learning_System.md'}


def run(*args,cwd=None):
    result=subprocess.run([str(arg) for arg in args],cwd=cwd,text=True,capture_output=True,timeout=60)
    if result.returncode:raise AssertionError(result.stdout+'\n'+result.stderr)
    return result


class LearningPortability(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory(prefix='learning-portability-tests-')
        cls.root=Path(cls.temp.name).resolve()
        cls.workspace=cls.root/'original user/learning/linux-re'
        cls.vault=cls.root/'original user/Documents/obsidian'
        cls.workspace.mkdir(parents=True)
        for folder in ['01 - Knowledge','02 - Lab','03 - Active','Attachments','.obsidian']:(cls.vault/folder).mkdir(parents=True)
        shutil.copy2(REPO/'configs/concept-loom/AGENTS.md',cls.workspace/'AGENTS.md')
        shutil.copytree(REPO/'configs/concept-loom/skills',cls.workspace/'.codex/skills')
        (cls.workspace/'.concept-loom').mkdir()
        (cls.workspace/'materials').mkdir()
        profile=json.loads((REPO/'configs/concept-loom/project.template.json').read_text().replace('@VAULT@',str(cls.vault)))
        (cls.workspace/'.concept-loom/project.json').write_text(json.dumps(profile))
        for name in ROADMAPS:
            (cls.workspace/'materials'/name).write_text('PRIVATE-ROADMAP-SENTINEL\n')
            (cls.vault/'03 - Active'/name).write_text('PRIVATE-ROADMAP-SENTINEL\n')
        (cls.vault/'03 - Active/Current_Stage.md').write_text('# Historical current stage\nKeep this context.\n')
        (cls.vault/'01 - Knowledge/Example.md').write_text('Personal concept\n')
        (cls.vault/'Attachments/example.bin').write_bytes(b'\x00\x01data')
        (cls.vault/'.obsidian/app.json').write_text('{"readableLineLength":true}')
        code='''import{pathToFileURL}from'node:url';const[runtime,base]=process.argv.slice(1);const{saveLearningState,approveRoute,recordCheckpointAssessment}=await import(pathToFileURL(runtime+'/src/progress.mjs'));await saveLearningState(base,{sessionId:'linux-re',topic:'Synthetic',goal:'Verify portability',phase:'weave',notebookPath:base+'/progress/linux-re-notebook.md',route:['First'],nextStep:'Exact pending action'});await approveRoute(base,{sessionId:'linux-re',expectedRevision:1,operationId:'fixture-consent',reference:'synthetic-user-message',quotedConsent:'Approve this synthetic test route'});await recordCheckpointAssessment(base,{sessionId:'linux-re',evidenceConcept:'Concept',hintUsed:true,nextStep:'Exact pending action'},{format:'prediction',outcome:'accurate',response:'  preserved learner text\\n'});'''
        run('node','--input-type=module','-e',code,RUNTIME,cls.workspace)
        cls.original=json.loads((cls.workspace/'.concept-loom/sessions/linux-re.json').read_text())
        cls.events=(cls.workspace/'.concept-loom/events/linux-re.jsonl').read_bytes()
        cls.bundle=cls.root/'recovery.tar.gz'
        result=run('python3',BACKUP,'--workspace',cls.workspace,'--vault',cls.vault,'--mcp-root',RUNTIME,'--output',cls.bundle)
        cls.backup=json.loads(result.stdout)
        cls.unpacked=cls.root/'unpacked';cls.unpacked.mkdir()
        with tarfile.open(cls.bundle) as archive:archive.extractall(cls.unpacked,filter='data')
        cls.package=cls.unpacked/'concept-loom-recovery'

    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()

    def test_public_config_contains_no_actual_roadmap_or_learner_state(self):
        manifest=json.loads((REPO/'learning/runtime-manifest.json').read_text())
        for rel in manifest['files']:
            self.assertNotIn(Path(rel).name,ROADMAPS)
            self.assertNotIn('/.concept-loom/events/',rel)
            self.assertNotIn('/.concept-loom/sessions/',rel)
            self.assertNotIn('PRIVATE-ROADMAP-SENTINEL',(REPO/rel).read_text(errors='replace'))
        ignored=run('git','check-ignore','--no-index','.learning-private/example.tar.gz','any/Linux_Malware_Roadmap.md','any/Learning_System.md','any/English_For_Linux_RE.md',cwd=REPO)
        self.assertEqual(len(ignored.stdout.splitlines()),4)

    def test_private_bundle_checksums_and_original_journal_are_preserved(self):
        run('sha256sum','--check','FILES.sha256',cwd=self.package)
        with tarfile.open(self.package/'private-data.tar.gz') as archive:
            self.assertEqual(archive.extractfile('project/.concept-loom/events/linux-re.jsonl').read(),self.events)
            self.assertEqual(archive.extractfile('project/materials/Linux_Malware_Roadmap.md').read(),b'PRIVATE-ROADMAP-SENTINEL\n')
        self.assertEqual(json.loads((self.workspace/'.concept-loom/sessions/linux-re.json').read_text()),self.original)

    def test_restore_to_another_username_with_spaces_and_retry_after_later_progress(self):
        home=self.root/'new user with spaces'
        config=home/'.codex/config.toml';config.parent.mkdir(parents=True)
        config.write_text('model = "keep-model"\n[mcp_servers.other]\nurl = "https://example.invalid/mcp"\n')
        result=run('python3',INSTALL,'--home',home,'--data-backup',self.package/'private-data.tar.gz','--apply')
        restored=json.loads(result.stdout)
        self.assertTrue(restored['doctorHealthy'])
        workspace=home/'learning/linux-re';vault=home/'Documents/obsidian';tools=home/'Tools/ConceptLoom'
        state=json.loads((workspace/'.concept-loom/sessions/linux-re.json').read_text())
        self.assertEqual(state['evidence'],self.original['evidence'])
        self.assertEqual(state['nextStep'],self.original['nextStep'])
        self.assertEqual(state['revision'],self.original['revision']+1)
        self.assertEqual(state['notebookPath'],'progress/linux-re-notebook.md')
        self.assertTrue((workspace/'.concept-loom/events/linux-re.jsonl').read_bytes().startswith(self.events))
        self.assertEqual((workspace/'notes/active').resolve(),vault/'03 - Active')
        profile=json.loads((workspace/'.concept-loom/project.json').read_text())
        self.assertEqual(profile['allowedExports'],[str(vault/'03 - Active/Current_Stage.md')])
        registered=tomllib.loads(config.read_text())
        self.assertEqual(registered['model'],'keep-model')
        self.assertEqual(registered['mcp_servers']['other']['url'],'https://example.invalid/mcp')
        self.assertEqual(registered['mcp_servers']['concept-loom']['args'],[str(tools/'src/bridge.mjs')])
        code='''import{pathToFileURL}from'node:url';const[runtime,base]=process.argv.slice(1);const{saveLearningState}=await import(pathToFileURL(runtime+'/src/progress.mjs'));await saveLearningState(base,{sessionId:'linux-re',nextStep:'New later progress'});'''
        run('node','--input-type=module','-e',code,tools,workspace)
        before=(workspace/'.concept-loom/sessions/linux-re.json').read_bytes()
        again=json.loads(run('python3',INSTALL,'--home',home,'--data-backup',self.package/'private-data.tar.gz','--apply').stdout)
        self.assertTrue(again['alreadyRestored'])
        self.assertEqual((workspace/'.concept-loom/sessions/linux-re.json').read_bytes(),before)

    def test_config_only_does_not_invent_progress(self):
        home=self.root/'configuration-only'
        result=json.loads(run('python3',INSTALL,'--home',home,'--apply').stdout)
        self.assertEqual(result['mode'],'configuration-only')
        self.assertFalse((home/'learning/linux-re/.concept-loom/sessions/linux-re.json').exists())
        launched=subprocess.run([str(home/'.local/bin/linux-re')],text=True,capture_output=True)
        self.assertEqual(launched.returncode,2)
        self.assertIn('Не хватает файла',launched.stderr)

    def test_existing_workspace_is_not_replaced(self):
        home=self.root/'existing-work'
        workspace=home/'learning/linux-re';workspace.mkdir(parents=True)
        (workspace/'keep.txt').write_text('keep')
        result=subprocess.run(['python3',str(INSTALL),'--home',str(home),'--data-backup',str(self.package/'private-data.tar.gz'),'--apply'],text=True,capture_output=True)
        self.assertNotEqual(result.returncode,0)
        self.assertEqual((workspace/'keep.txt').read_text(),'keep')
        self.assertFalse((home/'Tools').exists())

    def test_codex_registration_preserves_unrelated_tables_and_multiline_values(self):
        before='''model = "keep"
[mcp_servers.concept-loom]
command = "node"
args = [
 "/old/user/Tools/ConceptLoom/src/bridge.mjs",
]
startup_timeout_sec = 17
[mcp_servers.concept-loom.env]
LOCAL_TEST = "keep"
[mcp_servers.other]
url = "https://example.invalid"
'''
        after=module.rewrite_mcp(before,Path('/new user/Tools/ConceptLoom/src/bridge.mjs'))
        data=tomllib.loads(after)
        self.assertEqual(data['model'],'keep')
        self.assertEqual(data['mcp_servers']['concept-loom']['env'],{'LOCAL_TEST':'keep'})
        self.assertEqual(data['mcp_servers']['concept-loom']['startup_timeout_sec'],17)
        with self.assertRaises(ValueError):module.rewrite_mcp('[mcp_servers.concept-loom]\nurl="https://unrelated.invalid"\n',Path('/new/ConceptLoom/src/bridge.mjs'))

    def test_archive_traversal_and_symlinks_are_rejected(self):
        for label,name,kind in [('traversal','../outside',tarfile.REGTYPE),('symlink','vault/link',tarfile.SYMTYPE)]:
            archive_path=self.root/(label+'.tar.gz')
            with tarfile.open(archive_path,'w:gz') as archive:
                info=tarfile.TarInfo(name);info.type=kind
                if kind==tarfile.SYMTYPE:info.linkname='/tmp/outside'
                else:info.size=1
                archive.addfile(info,io.BytesIO(b'x') if info.size else None)
            target=self.root/(label+'-extract');target.mkdir()
            with self.assertRaises(ValueError):module.extract_private(archive_path,target)


if __name__=='__main__':unittest.main()
