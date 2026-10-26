#!/usr/bin/env python3
"""Build a private, checksummed recovery kit without putting learning data in Git."""
import argparse
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile
import time

REPO = Path(__file__).resolve().parents[2]
IGNORED = {'.git','.trash','node_modules','__pycache__','.cache'}
os.umask(0o077)


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream,'sha256').hexdigest()


def copy_file(source,target,allowed_root):
    actual=source.resolve(strict=True)
    if not actual.is_relative_to(allowed_root):
        raise ValueError(f'External symlink needs a separate backup: {source}')
    for attempt in range(3):
        before=actual.stat()
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(actual,target)
        after=actual.stat()
        if (before.st_ino,before.st_size,before.st_mtime_ns)==(after.st_ino,after.st_size,after.st_mtime_ns):
            return
        time.sleep(0.1)
    raise RuntimeError(f'Source changed while copying: {source}')


def copy_tree(source,target,root,extra_exclude=()):
    for current,dirs,files in os.walk(source,followlinks=False):
        directory=Path(current)
        dirs[:]=[name for name in dirs if name not in IGNORED and name not in extra_exclude]
        for name in list(dirs):
            if (directory/name).is_symlink():
                raise ValueError(f'Directory symlink needs an explicit backup decision: {directory/name}')
        for name in files:
            if name.endswith(('.tmp','.pyc')) or name=='restore-receipt.json':continue
            copy_file(directory/name,target/(directory/name).relative_to(source),root)


def runtime_manifest(package):
    files={}
    for folder in ['learning/concept-loom','configs/concept-loom']:
        for path in sorted((package/folder).rglob('*')):
            if path.is_file():files[str(path.relative_to(package))]=digest(path)
    value={'schemaVersion':1,'mcpVersion':json.loads((package/'learning/concept-loom/package.json').read_text())['version'],'files':files}
    (package/'learning/runtime-manifest.json').write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace',type=Path,default=Path.home()/'learning/linux-re')
    parser.add_argument('--vault',type=Path,default=Path.home()/'Documents/obsidian')
    parser.add_argument('--mcp-root',type=Path,default=Path.home()/'Tools/ConceptLoom')
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    workspace=args.workspace.expanduser().resolve(strict=True)
    vault=args.vault.expanduser().resolve(strict=True)
    mcp=args.mcp_root.expanduser().resolve(strict=True)
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    output=(args.output or REPO/'.learning-private'/f'concept-loom-recovery-{stamp}.tar.gz').expanduser().resolve()
    selected=[vault,workspace/'.concept-loom',workspace/'progress',workspace/'materials',workspace/'.codex']
    if any(output.is_relative_to(root) for root in selected):
        raise ValueError('Output must be outside the backed-up data trees')
    if output.exists():raise ValueError('Backup output already exists')
    for directory in [workspace/'.concept-loom',workspace/'.concept-loom/locks']:
        if directory.is_symlink():raise ValueError('State storage must not be a symlink')
    output.parent.mkdir(parents=True,exist_ok=True)
    lock=workspace/'.concept-loom/locks/linux-re.lock';lock.parent.mkdir(exist_ok=True)
    with lock.open('a') as handle, tempfile.TemporaryDirectory(prefix='learning-kit-',dir=output.parent) as temporary:
        fcntl.flock(handle,fcntl.LOCK_EX)
        temp=Path(temporary);package=temp/'concept-loom-recovery';package.mkdir()
        payload=temp/'data';payload.mkdir()
        for relative in ['.concept-loom','progress','materials']:
            copy_tree(workspace/relative,payload/'project'/relative,workspace,extra_exclude=('locks',) if relative=='.concept-loom' else ())
        copy_file(workspace/'AGENTS.md',payload/'project/AGENTS.md',workspace)
        copy_tree(workspace/'.codex/skills/concept-coach',payload/'project/.codex/skills/concept-coach',workspace)
        copy_tree(vault,payload/'vault',vault)
        # Validate the copied immutable journal and snapshot, without rewriting either.
        code='''import{pathToFileURL}from'node:url';const [runtime,base]=process.argv.slice(1);const{readSession}=await import(pathToFileURL(runtime+'/src/storage.mjs'));const s=await readSession(base,'linux-re');if(!s.state||s.diagnostics.length)throw new Error(JSON.stringify(s.diagnostics));console.log(JSON.stringify({revision:s.state.revision,schemaVersion:s.state.schemaVersion,evidenceConcepts:Object.keys(s.state.evidence).length,eventCount:s.events.length}));'''
        checked=subprocess.run(['node','--input-type=module','-e',code,str(mcp),str(payload/'project')],text=True,capture_output=True,timeout=30)
        if checked.returncode:raise RuntimeError(checked.stderr or checked.stdout)
        state_info=json.loads(checked.stdout)
        fcntl.flock(handle,fcntl.LOCK_UN)
        entries={}
        for file in sorted(payload.rglob('*')):
            if file.is_file():
                entries[str(file.relative_to(payload))]={'sha256':digest(file),'size':file.stat().st_size,'mode':file.stat().st_mode & 0o777}
        data={'schemaVersion':1,'sessionId':'linux-re','createdAt':datetime.now(timezone.utc).isoformat(),'originalWorkspace':str(workspace),'originalVault':str(vault),'originalMcpRoot':str(mcp),'state':state_info,'files':entries,
              'excluded':['Codex credentials and chat cache','Git metadata','Obsidian trash','VM disk images','transient locks']}
        (payload/'DATA-MANIFEST.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
        with tarfile.open(package/'private-data.tar.gz','w:gz',compresslevel=6) as archive:
            for file in sorted(payload.rglob('*')):
                if file.is_file():archive.add(file,arcname=str(file.relative_to(payload)),recursive=False)
        # Include the actual current runtime and instructions, not a network clone of an upstream version.
        copy_tree(mcp,package/'learning/concept-loom',mcp)
        config=package/'configs/concept-loom';config.mkdir(parents=True)
        copy_file(workspace/'AGENTS.md',config/'AGENTS.md',workspace)
        copy_tree(workspace/'.codex/skills/concept-coach',config/'skills/concept-coach',workspace)
        profile=json.loads((workspace/'.concept-loom/project.json').read_text())
        def template(value):
            if isinstance(value,str):return value.replace(str(vault),'@VAULT@').replace(str(workspace),'@WORKSPACE@').replace(str(mcp),'@TOOLS@')
            if isinstance(value,list):return [template(item) for item in value]
            if isinstance(value,dict):return {key:template(item) for key,item in value.items()}
            return value
        (config/'project.template.json').write_text(json.dumps(template(profile),ensure_ascii=False,indent=2)+'\n')
        script=package/'scripts/maintenance/install-learning.py';script.parent.mkdir(parents=True)
        shutil.copy2(REPO/'scripts/maintenance/install-learning.py',script)
        runtime_manifest(package)
        restore='''#!/usr/bin/env bash
set -euo pipefail
PACKAGE_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd -- "$PACKAGE_DIR"
sha256sum --check FILES.sha256
exec python3 "$PACKAGE_DIR/scripts/maintenance/install-learning.py" --data-backup "$PACKAGE_DIR/private-data.tar.gz" --apply "$@"
'''
        (package/'restore.sh').write_text(restore);(package/'restore.sh').chmod(0o700)
        instructions='''# Восстановление Linux RE / ConceptLoom

Этот комплект личный: внутри прогресс, заметки и родмапы. Не добавляй его в GitHub.

На новом Arch установи Node.js 20+, Python 3.11+ и Codex CLI. Для Arch: `sudo pacman -S --needed nodejs npm python git`.
Распакуй комплект и выполни `bash restore.sh`. Другой пользователь определяется автоматически по домашней папке.
Для своих путей: `bash restore.sh --workspace /new/project --vault /new/vault --tools /new/Tools/ConceptLoom`.
Существующая история не затирается: при конфликте выбери пустую папку. Повтор успешной установки не откатывает новый прогресс.
После восстановления запусти `~/.local/bin/linux-re`, войди в Codex при необходимости и открой папку vault в Obsidian.
Диски Debian VM, SSH/аккаунты и установка ОС не входят в комплект. Их сохраняют отдельной системной копией.
Проверка целостности: `sha256sum -c FILES.sha256`.
'''
        (package/'RESTORE.md').write_text(instructions)
        sums=[]
        for file in sorted(package.rglob('*')):
            if file.is_file():sums.append(f'{digest(file)}  {file.relative_to(package)}\n')
        (package/'FILES.sha256').write_text(''.join(sums))
        with tarfile.open(output,'w:gz',compresslevel=1) as archive:
            archive.add(package,arcname=package.name)
    checksum=digest(output)
    output.with_name(output.name+'.sha256').write_text(f'{checksum}  {output.name}\n')
    result={'archive':str(output),'sha256':checksum,'bytes':output.stat().st_size,'state':state_info,'privateDataFiles':len(entries),'excludedFromGit':True,'externalCopyVerified':False}
    output.with_name(output.name+'.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__':
    main()
