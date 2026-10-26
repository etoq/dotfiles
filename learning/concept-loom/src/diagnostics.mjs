import { readFile } from 'node:fs/promises';
import { spawnSync } from 'node:child_process';
import { dataPath, instructionPath, projectConfig, workspaceRoot } from './paths.mjs';
import { hash, VERSION, SCHEMA_VERSION } from './validation.mjs';
import { readSession, storageStats } from './storage.mjs';
import { compactState, listDueReviews, loadLearningState } from './progress.mjs';
import { inspectProjections } from './projections.mjs';

export async function status(base, input = {}) {
  const profile = projectConfig(base);
  const id = input.sessionId ?? profile.primarySessionId ?? (await loadLearningState(base)).state?.sessionId;
  const loaded = id ? await readSession(base, id) : { state: null, events: [], diagnostics: [] };
  return { serverVersion: VERSION, supportedSchemaVersion: SCHEMA_VERSION, workspace: workspaceRoot(base), profile: profile.name ?? null,
    session: loaded.state ? compactState(loaded.state) : null, eventCount: loaded.events.length, diagnostics: loaded.diagnostics,
    projections: loaded.state ? await inspectProjections(base, loaded.state, loaded.events) : null,
    operation: input.operationId ? loaded.events.find(event => event.operationId === input.operationId) ? { committed: true, revision: loaded.events.find(event => event.operationId === input.operationId).revision } : { committed: false } : undefined,
    environment: profile.environment ?? null, reviewPolicy: profile.review ?? { minimumDelayHours: 24 },
  };
}
export async function doctor(base, input = {}) {
  const issues = [], notes = [];
  let current;
  try { current = await status(base, input); } catch (error) { return { serverVersion: VERSION, healthy: false, issues: [{ kind: 'state-or-profile-error', message: error.message }] }; }
  issues.push(...current.diagnostics);
  if (current.session && current.session.schemaVersion !== SCHEMA_VERSION) issues.push({ kind: 'migration-needed', from: current.session.schemaVersion, to: SCHEMA_VERSION });
  issues.push(...(current.projections?.issues ?? []));
  if (current.session?.routeApproval === 'legacy-context') notes.push('Existing route is retained from historical context; no new consent or mastery was fabricated.');
  const python = spawnSync(process.env.CONCEPT_LOOM_PYTHON ?? (process.platform === 'win32' ? 'python' : 'python3'), ['--version'], { encoding: 'utf8', timeout: 5000 });
  if (python.error || python.status !== 0) issues.push({ kind: 'lock-runtime-unavailable', message: python.error?.message ?? python.stderr });
  const profile = projectConfig(base);
  const instructions = [];
  for (const relative of profile.instructionFiles ?? []) {
    try {
      const path = instructionPath(base, relative);
      const contents = await readFile(path, 'utf8');
      const compatible = contents.includes('ConceptLoom protocol: 2');
      instructions.push({ path, compatible, digest: hash(contents) });
      if (!compatible) issues.push({ kind: 'instruction-version-mismatch', path });
    } catch (error) { issues.push({ kind: 'instruction-file-unreadable', path: relative, message: error.message }); }
  }
  let backup = null;
  if (current.session) {
    try {
      const value = JSON.parse(await readFile(dataPath(base, `backups/${current.session.sessionId}.json`), 'utf8'));
      backup = { valid: value.backupVersion === 1 && value.digest === hash(value.state), revision: value.state?.revision };
      if (!backup.valid) issues.push({ kind: 'backup-integrity-failure' });
    } catch (error) { if (error.code !== 'ENOENT') issues.push({ kind: 'backup-unreadable', message: error.message }); }
  }
  const reviews = await listDueReviews(base, { sessionId: current.session?.sessionId });
  const neighboringErrors = reviews.diagnostics.filter(item => item.kind === 'session-unreadable');
  issues.push(...neighboringErrors);
  return { ...current, healthy: issues.length === 0, issues, notes, python: (python.stdout || python.stderr || '').trim(), instructions, backup,
    storage: current.session ? await storageStats(base, current.session.sessionId) : null, dueReviewCount: reviews.due.length };
}
