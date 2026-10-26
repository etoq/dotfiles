#!/usr/bin/env node
import { migrateLearningState, loadLearningState } from '../src/progress.mjs';
import { projectConfig } from '../src/paths.mjs';
const args = process.argv.slice(2);
const value = flag => { const index = args.indexOf(flag); return index < 0 ? undefined : args[index + 1]; };
const base = value('--workspace') ?? process.cwd();
const id = value('--session') ?? projectConfig(base).primarySessionId;
if (!id) throw new Error('supply --session');
const { state } = await loadLearningState(base, { sessionId: id });
const before = { sessionId: id, schemaVersion: state.schemaVersion ?? 1, revision: state.revision, evidenceConcepts: Object.keys(state.evidence ?? {}).length, nextStep: state.nextStep };
if (!args.includes('--apply')) process.stdout.write(`${JSON.stringify({ dryRun: true, before, targetSchemaVersion: 3, effect: 'Import one historical baseline; preserve evidence, approval provenance and exact nextStep. No learner attempt is generated.' }, null, 2)}\n`);
else {
  const result = await migrateLearningState(base, id);
  process.stdout.write(`${JSON.stringify({ applied: true, before, after: { schemaVersion: result.state.schemaVersion, revision: result.state.revision, evidenceConcepts: Object.keys(result.state.evidence).length }, projections: result.projections }, null, 2)}\n`);
  if (result.projections?.issues?.length) process.exitCode = 1;
}
