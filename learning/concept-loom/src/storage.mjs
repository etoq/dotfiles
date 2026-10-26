import { randomUUID } from 'node:crypto';
import { constants } from 'node:fs';
import { mkdir, open, readFile, readdir, rename, rm, stat, truncate } from 'node:fs/promises';
import { dirname, join } from 'node:path';
import { spawn } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { allowedSession, dataPath } from './paths.mjs';
import { checkRevision, clone, hash, sessionId, validateState } from './validation.mjs';

const queues = new Map();
const lockHelper = fileURLToPath(new URL('./lock-holder.py', import.meta.url));
export async function readOptional(path) {
  try { return await readFile(path, 'utf8'); } catch (error) { if (error.code === 'ENOENT') return null; throw error; }
}
export async function atomicWrite(path, contents) {
  await mkdir(dirname(path), { recursive: true });
  const temporary = `${path}.${process.pid}.${randomUUID()}.tmp`;
  try {
    const handle = await open(temporary, constants.O_WRONLY | constants.O_CREAT | constants.O_EXCL | (constants.O_NOFOLLOW ?? 0), 0o600);
    try { await handle.writeFile(contents, 'utf8'); await handle.sync(); } finally { await handle.close(); }
    await rename(temporary, path);
    // Persist the directory entry on filesystems that support directory fsync.
    if (process.platform !== 'win32') {
      const directory = await open(dirname(path), constants.O_RDONLY);
      try { await directory.sync(); } finally { await directory.close(); }
    }
  } finally { await rm(temporary, { force: true }); }
}
export async function withSessionLock(base, id, operation) {
  allowedSession(base, id);
  const path = dataPath(base, `locks/${sessionId(id)}.lock`);
  const previous = queues.get(path) ?? Promise.resolve();
  const result = previous.then(async () => {
    await mkdir(dirname(path), { recursive: true });
    dataPath(base, `locks/${id}.lock`);
    const child = spawn(process.env.CONCEPT_LOOM_PYTHON ?? (process.platform === 'win32' ? 'python' : 'python3'), [lockHelper, path, '15'], { stdio: ['pipe', 'pipe', 'pipe'] });
    let errors = '';
    child.stderr.on('data', chunk => { errors += chunk; });
    const exited = new Promise(resolve => child.once('close', resolve));
    try {
      await new Promise((resolve, reject) => {
        let output = '';
        child.once('error', error => reject(new Error(`Python 3 is required for the OS session lock: ${error.message}`)));
        child.stdout.on('data', chunk => { output += chunk; if (output.includes('LOCKED\n')) resolve(); });
        child.once('close', code => reject(new Error(`cannot acquire session lock (${code}): ${errors.trim()}`)));
      });
      return await operation();
    } finally {
      if (!child.stdin.destroyed) child.stdin.end();
      await exited;
    }
  });
  const tail = result.catch(() => {});
  queues.set(path, tail);
  try { return await result; } finally { if (queues.get(path) === tail) queues.delete(path); }
}
function eventDigest(event) { const { digest, ...rest } = event; return hash(rest); }
function patchState(previous, next) {
  const changes = Object.fromEntries(Object.entries(next).filter(([key, value]) => !['evidence', 'integrity'].includes(key) && hash(value) !== hash(previous?.[key] ?? null)));
  const removedFields = Object.keys(previous ?? {}).filter(key => key !== 'integrity' && next[key] === undefined);
  const evidenceUpdates = {};
  for (const [key, value] of Object.entries(next.evidence ?? {})) {
    const before = previous?.evidence?.[key];
    if (hash(value) === hash(before ?? null)) continue;
    const oldHistory = before?.history ?? [];
    const newHistory = value.history ?? [];
    if (Array.isArray(oldHistory) && Array.isArray(newHistory) && newHistory.length >= oldHistory.length && hash(newHistory.slice(0, oldHistory.length)) === hash(oldHistory)) {
      const { history, ...fields } = value;
      Object.defineProperty(evidenceUpdates, key, { value: { fields, historyAppend: newHistory.slice(oldHistory.length), hasHistory: value.history !== undefined }, enumerable: true });
    } else Object.defineProperty(evidenceUpdates, key, { value: { replacement: value }, enumerable: true });
  }
  return { changes, removedFields, evidenceUpdates, evidenceRemoved: Object.keys(previous?.evidence ?? {}).filter(key => !Object.hasOwn(next.evidence ?? {}, key)) };
}
export function applyEvent(previous, event) {
  let state;
  if (event.baseline) state = clone(event.baseline);
  else {
    state = { ...(previous ?? {}), ...event.changes, evidence: { ...(previous?.evidence ?? {}) } };
    for (const key of event.removedFields ?? []) delete state[key];
    for (const key of event.evidenceRemoved ?? []) delete state.evidence[key];
    for (const [key, update] of Object.entries(event.evidenceUpdates ?? {})) {
      const value = update.replacement ?? { ...update.fields, ...(update.hasHistory ? { history: [...(previous?.evidence?.[key]?.history ?? []), ...update.historyAppend] } : {}) };
      Object.defineProperty(state.evidence, key, { value, enumerable: true, configurable: true, writable: true });
    }
  }
  state.integrity = { eventId: event.eventId, digest: event.digest };
  return state;
}
export async function readJournal(base, id) {
  const path = dataPath(base, `events/${sessionId(id)}.jsonl`);
  const raw = await readOptional(path);
  if (raw === null) return { events: [], state: null, raw: '', validBytes: 0, diagnostics: [] };
  const lines = raw.split('\n');
  const events = [];
  let state = null, previousDigest = null, validBytes = 0;
  const diagnostics = [];
  for (let index = 0; index < lines.length; index += 1) {
    const line = lines[index];
    if (!line && index === lines.length - 1) break;
    let event;
    try { event = JSON.parse(line); } catch (error) {
      if (index === lines.length - 1) { diagnostics.push({ kind: 'incomplete-journal-tail', path, repairable: true }); break; }
      throw new Error(`journal corruption at ${path}:${index + 1}: ${error.message}`);
    }
    if (event.schemaVersion !== 1 || event.sessionId !== id || event.previousDigest !== previousDigest || event.digest !== eventDigest(event)) throw new Error(`journal integrity failure at ${path}:${index + 1}`);
    if (events.length && event.revision !== state.revision + 1) throw new Error(`journal revision discontinuity at ${path}:${index + 1}`);
    if (!events.length && !event.baseline && event.revision !== 1) throw new Error('journal must start with revision 1 or an explicit imported baseline');
    if (events.some(prior => prior.eventId === event.eventId || (event.operationId && prior.operationId === event.operationId))) throw new Error('duplicate event or operation ID in journal');
    state = applyEvent(state, event);
    validateState(state, id);
    if (state.revision !== event.revision) throw new Error('journal revision does not match reconstructed state');
    previousDigest = event.digest;
    events.push(event);
    validBytes += Buffer.byteLength(line, 'utf8') + (index < lines.length - 1 ? 1 : 0);
  }
  return { events, state, raw, validBytes, diagnostics };
}
export async function readSession(base, id) {
  allowedSession(base, id);
  const path = dataPath(base, `sessions/${id}.json`);
  const journal = await readJournal(base, id);
  const diagnostics = [...journal.diagnostics];
  let snapshot = null;
  const raw = await readOptional(path);
  if (raw !== null) {
    try { snapshot = validateState(JSON.parse(raw), id); } catch (error) {
      // An unknown future format must never be overwritten, even if an older journal exists.
      if (/unsupported schemaVersion/.test(error.message) || !journal.state) throw error;
      diagnostics.push({ kind: 'snapshot-invalid', path, message: error.message, repairable: true });
    }
  }
  if (journal.state) {
    if (!snapshot || hash(snapshot) !== hash(journal.state)) diagnostics.push({ kind: 'snapshot-out-of-sync', path, repairable: true });
    return { state: journal.state, events: journal.events, diagnostics, journal };
  }
  if (snapshot?.schemaVersion === 3) throw new Error(`schema 3 snapshot has no authoritative event journal: ${path}`);
  if (snapshot) diagnostics.push({ kind: 'legacy-state', schemaVersion: snapshot.schemaVersion ?? 1, repairable: true });
  return { state: snapshot, events: [], diagnostics, journal };
}
async function repairTail(base, id, journal) {
  const path = dataPath(base, `events/${id}.jsonl`);
  if (journal.validBytes < Buffer.byteLength(journal.raw, 'utf8')) {
    const tail = Buffer.from(journal.raw).subarray(journal.validBytes);
    await atomicWrite(dataPath(base, `recovery/${id}-tail-${randomUUID()}.txt`), tail);
    await truncate(path, journal.validBytes);
  }
  if (journal.events.length && journal.raw && !journal.raw.slice(0, journal.validBytes).endsWith('\n')) {
    const handle = await open(path, constants.O_APPEND | constants.O_WRONLY | (constants.O_NOFOLLOW ?? 0));
    try { await handle.writeFile('\n'); await handle.sync(); } finally { await handle.close(); }
  }
}
async function appendEvent(base, id, previous, next, metadata, baseline = false) {
  const event = {
    schemaVersion: 1, eventId: randomUUID(), sessionId: id, revision: next.revision,
    recordedAt: metadata.recordedAt ?? new Date().toISOString(), kind: metadata.kind ?? 'state-save',
    provenance: metadata.provenance ?? 'coach-record', operationId: metadata.operationId,
    inputDigest: metadata.inputDigest, contentDigest: metadata.contentDigest, previousDigest: previous?.integrity?.digest ?? null,
    ...(baseline ? { baseline: next } : patchState(previous, next)),
  };
  event.digest = eventDigest(event);
  const path = dataPath(base, `events/${id}.jsonl`);
  await mkdir(dirname(path), { recursive: true });
  dataPath(base, `events/${id}.jsonl`);
  const handle = await open(path, constants.O_APPEND | constants.O_CREAT | constants.O_WRONLY | (constants.O_NOFOLLOW ?? 0), 0o600);
  try { await handle.writeFile(`${JSON.stringify(event)}\n`); await handle.sync(); } finally { await handle.close(); }
  if (process.platform !== 'win32') {
    const directory = await open(dirname(path), constants.O_RDONLY);
    try { await directory.sync(); } finally { await directory.close(); }
  }
  return { event, state: applyEvent(previous, event) };
}
async function writeSnapshot(base, id, state) {
  const path = dataPath(base, `sessions/${id}.json`);
  const old = await readOptional(path);
  if (old !== null) {
    let parsed;
    try {
      parsed = validateState(JSON.parse(old), id);
    } catch (error) { if (/unsupported schemaVersion/.test(error.message)) throw error; }
    if (parsed) await atomicWrite(dataPath(base, `backups/${id}.json`), `${JSON.stringify({ backupVersion: 1, state: parsed, digest: hash(parsed) }, null, 2)}\n`);
  }
  dataPath(base, `sessions/${id}.json`);
  await atomicWrite(path, `${JSON.stringify(state, null, 2)}\n`);
}
export async function transaction(base, id, input, mutation, options = {}) {
  if (input.operationId !== undefined && (typeof input.operationId !== 'string' || !input.operationId || input.operationId.trim() !== input.operationId)) throw new Error('operationId must be a non-empty stable string without surrounding whitespace');
  return withSessionLock(base, id, async () => {
    const loaded = await readSession(base, id);
    const operationId = input.operationId;
    const payload = Object.fromEntries(Object.entries(input).filter(([key]) => !['expectedRevision', 'includeState', 'operationId'].includes(key)));
    const inputDigest = hash(payload);
    if (operationId) {
      const prior = loaded.events.find(event => event.operationId === operationId);
      if (prior) {
        if (prior.inputDigest !== inputDigest) throw new Error('operationId was already used with different input');
        if (options.contentDigest && prior.contentDigest !== options.contentDigest) throw new Error('operationId was already used with a different assessment');
        const diagnostics = [];
        try {
          if (loaded.journal.raw) await repairTail(base, id, loaded.journal);
          if (loaded.diagnostics.some(entry => entry.kind.startsWith('snapshot-'))) await writeSnapshot(base, id, loaded.state);
        } catch (error) { diagnostics.push({ kind: 'snapshot-pending', message: error.message, committed: true }); }
        const projections = options.project ? await options.project(loaded.state, loaded.events) : undefined;
        return { state: loaded.state, event: prior, replayed: true, diagnostics, projections };
      }
    }
    checkRevision(input, loaded.state);
    const now = options.now ? new Date(options.now) : new Date();
    if (!Number.isFinite(now.getTime())) throw new Error('invalid internal clock');
    let previous = loaded.state;
    if (previous && previous.schemaVersion !== 3) previous = options.migrate(previous, now);
    // Validate the entire proposed change before creating the baseline or touching a journal.
    const proposed = mutation(previous ? clone(previous) : null, now);
    validateState(proposed, id);
    if (loaded.journal.raw) await repairTail(base, id, loaded.journal);
    let events = [...loaded.events];
    if (loaded.state && loaded.state.schemaVersion !== 3) {
      const imported = await appendEvent(base, id, null, previous, { kind: 'import-baseline', provenance: 'historical-state-import', recordedAt: now.toISOString() }, true);
      previous = imported.state; events.push(imported.event);
    }
    options.fault?.('before-journal');
    const committed = await appendEvent(base, id, previous, proposed, { kind: options.kind, provenance: options.provenance, operationId, inputDigest, contentDigest: options.contentDigest, recordedAt: now.toISOString() });
    events.push(committed.event);
    const diagnostics = [];
    try { options.fault?.('after-journal'); await writeSnapshot(base, id, committed.state); } catch (error) { diagnostics.push({ kind: 'snapshot-pending', message: error.message, committed: true }); }
    const projections = options.project ? await options.project(committed.state, events) : undefined;
    return { ...committed, replayed: false, diagnostics, projections };
  });
}
export async function migrateSession(base, id, migrate, project) {
  return withSessionLock(base, id, async () => {
    const loaded = await readSession(base, id);
    if (!loaded.state) throw new Error(`learning session '${id}' was not found`);
    let state = loaded.state, events = loaded.events;
    if (state.schemaVersion !== 3) {
      const next = migrate(clone(state), new Date());
      validateState(next, id);
      const imported = await appendEvent(base, id, null, next, { kind: 'import-baseline', provenance: 'historical-state-import' }, true);
      state = imported.state; events = [imported.event];
    } else if (loaded.journal.raw) await repairTail(base, id, loaded.journal);
    await writeSnapshot(base, id, state);
    return { state, projections: project ? await project(state, events) : undefined };
  });
}
export async function sessionNames(base) {
  const names = new Set();
  for (const [folder, suffix] of [['sessions', '.json'], ['events', '.jsonl']]) {
    const path = dataPath(base, folder);
    try { for (const name of await readdir(path)) if (name.endsWith(suffix)) names.add(name.slice(0, -suffix.length)); } catch (error) { if (error.code !== 'ENOENT') throw error; }
  }
  return [...names].sort();
}
export async function lookupOperation(base, id, operationId) {
  const loaded = await readSession(base, id);
  const event = loaded.events.find(entry => entry.operationId === operationId);
  return event ? { state: loaded.state, event } : null;
}
export async function storageStats(base, id) {
  const result = {};
  for (const [name, path] of [['snapshot', `sessions/${id}.json`], ['journal', `events/${id}.jsonl`], ['backup', `backups/${id}.json`]]) {
    try { const info = await stat(dataPath(base, path)); result[name] = { bytes: info.size, modifiedAt: info.mtime.toISOString() }; } catch (error) { if (error.code !== 'ENOENT') throw error; result[name] = null; }
  }
  return result;
}
