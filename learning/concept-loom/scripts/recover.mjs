#!/usr/bin/env node
// Recovery replays only a verified journal; it never silently chooses an older backup.
import { migrateLearningState } from '../src/progress.mjs';
import { readJournal } from '../src/storage.mjs';
import { projectConfig } from '../src/paths.mjs';
const args = process.argv.slice(2);
const value = flag => { const index = args.indexOf(flag); return index < 0 ? undefined : args[index + 1]; };
const base = value('--workspace') ?? process.cwd();
const id = value('--session') ?? projectConfig(base).primarySessionId;
if (!id) throw new Error('supply --session');
const journal = await readJournal(base, id);
if (!journal.state) throw new Error('no verified journal exists; inspect preserved backups before restoring historical data');
if (!args.includes('--apply')) process.stdout.write(`${JSON.stringify({ dryRun: true, source: 'verified-event-journal', revision: journal.state.revision, events: journal.events.length, diagnostics: journal.diagnostics }, null, 2)}\n`);
else {
  const result = await migrateLearningState(base, id);
  process.stdout.write(`${JSON.stringify({ recovered: true, revision: result.state.revision, projections: result.projections }, null, 2)}\n`);
}
