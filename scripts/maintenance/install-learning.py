#!/usr/bin/env python3
"""Restore the portable Linux RE setup. Default: plan only; --apply writes files."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shlex
import shutil
import subprocess
import sys
import tarfile
import tempfile
import tomllib

REPO = Path(__file__).resolve().parents[2]
PRIVATE_MANIFEST = 'DATA-MANIFEST.json'
MAX_DATA = 2 * 1024**3


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def safe_name(name):
    item = PurePosixPath(name)
    if not item.parts or item.is_absolute() or '..' in item.parts or '\\' in name:
        raise ValueError(f'Unsafe backup path: {name}')
    return str(item)


def verify_runtime():
    manifest = json.loads((REPO/'learning/runtime-manifest.json').read_text())
    for rel, expected in manifest['files'].items():
        rel = safe_name(rel)
        target = REPO/rel
        if target.is_symlink() or not target.is_file() or sha(target) != expected:
            raise ValueError(f'Configuration/runtime integrity check failed: {rel}')
    return manifest


def extract_private(archive, destination):
    """Reject links, traversal, duplicates and unchecked payloads before any install."""
    with tarfile.open(archive, 'r:gz') as source:
        entries = source.getmembers()
        seen, total = set(), 0
        for entry in entries:
            name = safe_name(entry.name)
            if name in seen or not (entry.isfile() or entry.isdir()):
                raise ValueError('Duplicate or unsupported backup entry')
            seen.add(name)
            if name != PRIVATE_MANIFEST and PurePosixPath(name).parts[0] not in ('project', 'vault'):
                raise ValueError('Backup contains a path outside project/vault')
            total += entry.size
        if total > MAX_DATA:
            raise ValueError('Backup exceeds the 2 GiB uncompressed limit')
        record = next((entry for entry in entries if entry.name == PRIVATE_MANIFEST and entry.isfile()), None)
        if record is None:
            raise ValueError('Backup data manifest is missing')
        manifest = json.load(source.extractfile(record))
        if manifest.get('schemaVersion') != 1 or manifest.get('sessionId') != 'linux-re':
            raise ValueError('Unsupported backup or subject')
        actual = {safe_name(entry.name): entry for entry in entries if entry.isfile() and entry.name != PRIVATE_MANIFEST}
        if set(actual) != set(manifest['files']):
            raise ValueError('Backup entries differ from their manifest')
        for name, entry in actual.items():
            expected = manifest['files'][name]
            if entry.size != expected['size']:
                raise ValueError(f'Backup size mismatch: {name}')
            target = destination/name
            target.parent.mkdir(parents=True, exist_ok=True)
            with source.extractfile(entry) as stream, target.open('xb') as output:
                shutil.copyfileobj(stream, output)
            if sha(target) != expected['sha256']:
                raise ValueError(f'Backup hash mismatch: {name}')
            target.chmod(expected['mode'] & 0o777)
    return manifest


def reject_symlink_ancestors(path):
    for ancestor in [path, *path.parents]:
        if ancestor.is_symlink():
            raise ValueError(f'Refusing to install through a symlink: {ancestor}')


def write(path, data, mode=0o600):
    reject_symlink_ancestors(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name+'.restore-'+os.urandom(6).hex())
    try:
        with temporary.open('xb') as stream:
            stream.write(data); stream.flush(); os.fsync(stream.fileno())
        temporary.chmod(mode)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def rewrite_mcp(text, bridge):
    parsed = tomllib.loads(text)
    existing = parsed.get('mcp_servers', {}).get('concept-loom')
    assignment = {'command': json.dumps('node'), 'args': json.dumps([str(bridge)], ensure_ascii=False)}
    if existing is None:
        result = text.rstrip()+'\n\n[mcp_servers.concept-loom]\ncommand = "node"\nargs = '+assignment['args']+'\n'
    else:
        command = Path(existing.get('command', '')).name
        arguments = existing.get('args', [])
        if command not in ('node', 'nodejs') or len(arguments) != 1 or not str(arguments[0]).replace('\\','/').endswith('/ConceptLoom/src/bridge.mjs') or existing.get('url'):
            raise ValueError('An unrelated concept-loom registration already exists; refusing to overwrite it')
        lines = text.splitlines(keepends=True)
        pattern = re.compile(r'''^\s*\[mcp_servers\.(?:concept-loom|"concept-loom"|'concept-loom')\]\s*(?:#.*)?$''')
        starts = [i for i, line in enumerate(lines) if pattern.match(line.strip())]
        if len(starts) != 1:
            raise ValueError('Unsupported inline or duplicate MCP table layout')
        start = starts[0]
        finish = next((i for i in range(start+1,len(lines)) if lines[i].lstrip().startswith('[')), len(lines))
        block = lines[start+1:finish]
        for key, value in assignment.items():
            index = next((i for i,line in enumerate(block) if re.match(r'^\s*'+key+r'\s*=',line)), None)
            if index is None:
                block.append(f'{key} = {value}\n'); continue
            stop = index+1
            while True:
                try:
                    tomllib.loads(''.join(block[index:stop])); break
                except tomllib.TOMLDecodeError:
                    stop += 1
                    if stop > len(block):
                        raise ValueError('Could not locate the complete MCP assignment')
            block[index:stop] = [f'{key} = {value}\n']
        result = ''.join(lines[:start+1]+block+lines[finish:])
    updated = tomllib.loads(result)
    expected = json.loads(json.dumps(parsed))
    expected.setdefault('mcp_servers', {}).setdefault('concept-loom', {}).update(command='node', args=[str(bridge)])
    if updated != expected:
        raise ValueError('MCP registration would change unrelated Codex settings')
    return result


def node_json(code, *arguments, cwd):
    result = subprocess.run(['node', '--input-type=module', '-e', code, *map(str,arguments)], cwd=cwd, text=True, capture_output=True, timeout=30)
    if result.returncode:
        raise RuntimeError(result.stderr or result.stdout)
    return json.loads(result.stdout)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--home', type=Path, default=Path.home())
    parser.add_argument('--workspace', type=Path)
    parser.add_argument('--vault', type=Path)
    parser.add_argument('--tools', type=Path)
    parser.add_argument('--codex-config', type=Path)
    parser.add_argument('--data-backup', type=Path)
    args = parser.parse_args()
    if sys.version_info < (3,11):
        raise RuntimeError('Installer requires Python 3.11+ (runtime MCP supports Python 3.10+)')
    verify_runtime()
    home = args.home.expanduser().resolve()
    workspace = (args.workspace or home/'learning/linux-re').expanduser().resolve()
    vault = (args.vault or home/'Documents/obsidian').expanduser().resolve()
    tools = (args.tools or home/'Tools/ConceptLoom').expanduser().resolve()
    config = (args.codex_config or home/'.codex/config.toml').expanduser().resolve()
    for path in (workspace,vault,tools,config):
        reject_symlink_ancestors(path)
    if workspace == vault or workspace.is_relative_to(vault) or vault.is_relative_to(workspace) or tools.is_relative_to(workspace) or workspace.is_relative_to(tools):
        raise ValueError('Runtime, workspace and vault must have separate roots')
    if workspace.is_relative_to(REPO) or vault.is_relative_to(REPO):
        raise ValueError('Keep personal learning data outside the public configuration repository')
    if shutil.which('node') is None:
        raise RuntimeError('Node.js 20+ is required; on Arch install nodejs, npm and python first')
    major = int(subprocess.check_output(['node','-p','process.versions.node.split(".")[0]'],text=True).strip())
    if major < 20:
        raise RuntimeError('Node.js 20+ is required')
    archive = args.data_backup.expanduser().resolve() if args.data_backup else None
    archive_digest = sha(archive) if archive else None
    receipt_path = workspace/'.concept-loom/restore-receipt.json'
    receipt = json.loads(receipt_path.read_text()) if receipt_path.exists() else None
    repeated = bool(archive and receipt and receipt.get('archiveSha256') == archive_digest and receipt.get('workspace') == str(workspace) and receipt.get('vault') == str(vault) and receipt.get('tools') == str(tools))
    if archive and workspace.exists() and any(workspace.iterdir()) and not repeated:
        raise ValueError('Project already contains data: restore into an empty workspace; existing learning history will not be replaced')
    config_old = config.read_text() if config.exists() else ''
    config_new = rewrite_mcp(config_old,tools/'src/bridge.mjs')
    operations = []
    for prefix,target in [(REPO/'learning/concept-loom',tools), (REPO/'configs/concept-loom/skills',workspace/'.codex/skills')]:
        for file in sorted(prefix.rglob('*')):
            if file.is_file():
                operations.append((target/file.relative_to(prefix),file.read_bytes(),file.stat().st_mode & 0o777,'config'))
    operations.append((workspace/'AGENTS.md',(REPO/'configs/concept-loom/AGENTS.md').read_bytes(),0o600,'config'))
    with tempfile.TemporaryDirectory(prefix='learning-restore-') as temporary:
        payload = Path(temporary)
        data = extract_private(archive,payload) if archive and not repeated else None
        profile_source = payload/'project/.concept-loom/project.json'
        profile = json.loads((profile_source if data and profile_source.exists() else REPO/'configs/concept-loom/project.template.json').read_text())
        replacements = {'@VAULT@':str(vault),'@WORKSPACE@':str(workspace),'@TOOLS@':str(tools)}
        if data:
            replacements.update({data['originalVault']:str(vault),data['originalWorkspace']:str(workspace),data.get('originalMcpRoot','@OLD_TOOLS@'):str(tools)})
        def rebase(value):
            if isinstance(value,str):
                for old,new in sorted(replacements.items(),key=lambda item:-len(item[0])):
                    value=value.replace(old,new)
                return value
            if isinstance(value,list):return [rebase(item) for item in value]
            if isinstance(value,dict):return {key:rebase(item) for key,item in value.items()}
            return value
        profile=rebase(profile)
        operations.append((workspace/'.concept-loom/project.json',(json.dumps(profile,ensure_ascii=False,indent=2)+'\n').encode(),0o600,'profile'))
        if data:
            private_project_paths={workspace.joinpath(*PurePosixPath(rel).parts[1:]) for rel in data['files'] if rel.startswith('project/')}
            operations=[operation for operation in operations if operation[0] not in private_project_paths or operation[3]=='profile']
            for rel,entry in data['files'].items():
                if rel=='project/.concept-loom/project.json':continue
                parts = PurePosixPath(rel).parts
                target = (workspace if parts[0]=='project' else vault).joinpath(*parts[1:])
                operations.append((target,(payload/rel).read_bytes(),entry['mode'] & 0o777,'data'))
        # Preflight all collisions before creating any target files.
        fresh_profile = bool(data)
        for name,folder in [('knowledge','01 - Knowledge'),('lab','02 - Lab'),('active','03 - Active')]:
            link=workspace/'notes'/name
            if link.is_symlink():
                if link.resolve()!=vault/folder:raise ValueError(f'Existing note link differs: {link}')
            elif link.exists():raise ValueError(f'Existing note directory is preserved: {link}')
        for target,content,mode,kind in operations:
            reject_symlink_ancestors(target)
            if target.exists() and target.read_bytes()!=content:
                if kind == 'profile' and fresh_profile:
                    continue
                if repeated:
                    continue  # Never rewind an already restored project or its later learning.
                raise ValueError(f'Existing file differs; preserved without overwrite: {target}')
        result = {'apply':args.apply,'workspace':str(workspace),'vault':str(vault),'tools':str(tools),
                  'privateDataProvided':bool(archive),'alreadyRestored':repeated,'mcpRegistration':str(config),
                  'mode':'full-restore' if archive else 'configuration-only','filesPlanned':len(operations)}
        if not args.apply:
            print(json.dumps(result,ensure_ascii=False,indent=2));return
        if repeated:
            # Existing mutable files belong to later user work; a retry must leave them alone.
            if config_new != config_old:
                raise ValueError('Codex registration changed after restore; inspect it before retrying')
        else:
            for target,content,mode,kind in sorted(operations,key=lambda item: item[3]!='data'):
                if not target.exists() or target.read_bytes()!=content:
                    write(target,content,mode)
            for folder in ['01 - Knowledge','02 - Lab','03 - Active']:
                (vault/folder).mkdir(parents=True,exist_ok=True)
            notes = workspace/'notes';notes.mkdir(parents=True,exist_ok=True)
            for name,folder in [('knowledge','01 - Knowledge'),('lab','02 - Lab'),('active','03 - Active')]:
                link = notes/name;relative=os.path.relpath(vault/folder,notes)
                if link.is_symlink():
                    if link.resolve()!=vault/folder:raise ValueError(f'Existing note link differs: {link}')
                elif link.exists():raise ValueError(f'Existing note directory is preserved: {link}')
                else:link.symlink_to(relative,target_is_directory=True)
            if config_new != config_old:
                if config.exists():
                    backup=config.with_name(config.name+'.before-learning-'+datetime.now().strftime('%Y%m%d-%H%M%S'))
                    write(backup,config_old.encode())
                write(config,config_new.encode())
            launcher = '#!/usr/bin/env bash\nset -e\ncd -- '+shlex.quote(str(workspace))+'''\nfor file in .concept-loom/sessions/linux-re.json notes/active/Learning_System.md notes/active/Linux_Malware_Roadmap.md notes/active/English_For_Linux_RE.md; do
  [[ -f "$file" ]] || { printf 'Не хватает файла для продолжения: %s\\nВосстанови личный архив или скопируй свои материалы.\\n' "$file" >&2; exit 2; }
done
command -v codex >/dev/null || { echo 'Установи Codex CLI и войди в свой аккаунт.' >&2; exit 2; }
exec codex "$@"
'''
            write(home/'.local/bin/linux-re',launcher.encode(),0o755)
            if data:
                code = '''import {pathToFileURL} from 'node:url';
const [tools,base,archive]=process.argv.slice(1);
const {readSession,transaction}=await import(pathToFileURL(tools+'/src/storage.mjs'));
const {migrateState}=await import(pathToFileURL(tools+'/src/progress.mjs'));
const {syncProjections}=await import(pathToFileURL(tools+'/src/projections.mjs'));
const before=(await readSession(base,'linux-re')).state;
if(!before)throw new Error('Restored state is missing');
const result=await transaction(base,'linux-re',{sessionId:'linux-re',expectedRevision:before.revision,operationId:'restore:'+archive,notebookPath:'progress/linux-re-notebook.md'},(previous,now)=>({...previous,notebookPath:'progress/linux-re-notebook.md',relocatedAt:now.toISOString(),revision:previous.revision+1}),{kind:'workspace-restored',provenance:'restore-maintenance; no new learner evidence',migrate:migrateState,project:(state,events)=>syncProjections(base,state,events)});
if(JSON.stringify(before.evidence)!==JSON.stringify(result.state.evidence)||before.nextStep!==result.state.nextStep)throw new Error('Learning evidence changed during restore');
if(result.projections?.issues?.length)throw new Error(JSON.stringify(result.projections.issues));
console.log(JSON.stringify({revision:result.state.revision,evidenceConcepts:Object.keys(result.state.evidence).length,learnerAttemptsAdded:0,nextStepPreserved:true}));'''
                result['learning'] = node_json(code,tools,workspace,archive_digest,cwd=workspace)
            result['restoredAt'] = datetime.now(timezone.utc).isoformat()
            result['archiveSha256'] = archive_digest
            write(receipt_path,(json.dumps(result,ensure_ascii=False,indent=2)+'\n').encode())
        if archive:
            check=subprocess.run(['node',str(tools/'scripts/doctor.mjs'),'--workspace',str(workspace),'--session','linux-re'],text=True,capture_output=True,timeout=30)
            health=json.loads(check.stdout)
            if check.returncode or not health.get('healthy'):
                raise RuntimeError(json.dumps(health,ensure_ascii=False))
            result['doctorHealthy']=True
        result['launcher']=str(home/'.local/bin/linux-re')
        result['codexAvailable']=shutil.which('codex') is not None
        print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__':
    try:main()
    except Exception as error:
        print(f'Установка остановлена: {error}',file=sys.stderr);sys.exit(1)
