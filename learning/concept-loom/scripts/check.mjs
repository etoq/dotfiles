import { readdirSync, readFileSync } from 'node:fs';
import { join } from 'node:path';
import { spawnSync } from 'node:child_process';
import { VERSION } from '../src/validation.mjs';
for (const folder of ['src', 'scripts']) for (const name of readdirSync(folder).filter(file => file.endsWith('.mjs'))) {
  const result = spawnSync(process.execPath, ['--check', join(folder, name)], { encoding: 'utf8' });
  if (result.error || result.status !== 0) throw new Error(`syntax check failed: ${name}: ${result.error?.message ?? result.stderr}`);
}
const python = spawnSync(process.env.CONCEPT_LOOM_PYTHON ?? (process.platform === 'win32' ? 'python' : 'python3'), ['-c', 'import ast,pathlib,sys;ast.parse(pathlib.Path(sys.argv[1]).read_text())', 'src/lock-holder.py'], { encoding: 'utf8' });
if (python.error || python.status !== 0) throw new Error(`Python lock helper check failed: ${python.error?.message ?? python.stderr}`);
if (JSON.parse(readFileSync('package.json', 'utf8')).version !== VERSION) throw new Error('server and package versions disagree');
process.stdout.write('All JavaScript modules and the Python lock helper passed syntax checks.\n');
