import { existsSync, lstatSync, readFileSync, realpathSync } from 'node:fs';
import { basename, dirname, isAbsolute, join, relative, resolve } from 'node:path';
import { object, sessionId } from './validation.mjs';

export function inside(root, target) {
  const rel = relative(root, target);
  return rel === '' || (rel !== '..' && !rel.startsWith(`..${process.platform === 'win32' ? '\\' : '/'}`) && !isAbsolute(rel));
}
function canonicalTarget(path) {
  let parent = resolve(path);
  const suffix = [];
  while (!existsSync(parent)) {
    // existsSync follows links: explicitly reject dangling links.
    try { if (lstatSync(parent).isSymbolicLink()) throw new Error(`dangling symlink: ${parent}`); } catch (error) { if (error.code !== 'ENOENT') throw error; }
    const next = dirname(parent);
    if (next === parent) throw new Error(`cannot resolve path: ${path}`);
    suffix.unshift(basename(parent)); parent = next;
  }
  return join(realpathSync(parent), ...suffix);
}
export function workspaceRoot(base) { return realpathSync(resolve(base)); }
export function instructionPath(base, requested) {
  const root = workspaceRoot(base), destination = canonicalTarget(resolve(root, requested));
  if (!inside(root, destination)) throw new Error('instruction paths must stay inside the workspace');
  return destination;
}
export function dataPath(base, requested = '') {
  const root = workspaceRoot(base);
  const destination = resolve(root, '.concept-loom', requested);
  if (!inside(join(root, '.concept-loom'), destination)) throw new Error('data path escapes .concept-loom');
  let current = root;
  for (const part of relative(root, destination).split(/[\\/]/).filter(Boolean)) {
    current = join(current, part);
    try { if (lstatSync(current).isSymbolicLink()) throw new Error(`symlinks are forbidden in learning-state storage: ${current}`); } catch (error) { if (error.code !== 'ENOENT') throw error; }
  }
  if (!inside(root, canonicalTarget(destination))) throw new Error('data path must stay inside the workspace');
  return destination;
}
export function projectConfig(base) {
  const path = dataPath(base, 'project.json');
  if (!existsSync(path)) return { schemaVersion: 1, review: { minimumDelayHours: 24 } };
  const config = object(JSON.parse(readFileSync(path, 'utf8')), 'project configuration');
  if (config.schemaVersion !== 1) throw new Error('unsupported project configuration version');
  if (config.primarySessionId !== undefined) sessionId(config.primarySessionId);
  if (config.allowedSessionIds !== undefined && (!Array.isArray(config.allowedSessionIds) || config.allowedSessionIds.some(id => sessionId(id) !== id))) throw new Error('invalid allowedSessionIds');
  if (config.review?.minimumDelayHours !== undefined && (!Number.isFinite(config.review.minimumDelayHours) || config.review.minimumDelayHours < 1)) throw new Error('minimumDelayHours must be at least one hour');
  if (config.review?.intervalDays !== undefined && (!Array.isArray(config.review.intervalDays) || !config.review.intervalDays.length || config.review.intervalDays.some((days, index, values) => !Number.isFinite(days) || days <= 0 || days > 3660 || (index > 0 && days <= values[index - 1])))) throw new Error('intervalDays must be an increasing array of positive day intervals');
  return config;
}
export function allowedSession(base, id) {
  sessionId(id);
  const allowed = projectConfig(base).allowedSessionIds;
  if (allowed && !allowed.includes(id)) throw new Error(`session '${id}' is not allowed by this project's profile`);
  return id;
}
export function notebookPath(base, requested = 'learning-notes.md', purpose = 'notebook') {
  const root = workspaceRoot(base);
  const config = projectConfig(base);
  const destination = resolve(root, requested);
  const real = canonicalTarget(destination);
  if (!destination.endsWith('.md')) throw new Error('notebook path must end with .md');
  if (purpose === 'export') {
    const exports = config.allowedExports ?? [];
    const exact = exports.find(entry => isAbsolute(entry) && resolve(entry) === destination);
    if (!exact || canonicalTarget(exact) !== destination) throw new Error(`export path is not explicitly allowed or contains a redirecting symlink: ${destination}`);
    return destination;
  }
  const roots = (config.notebookRoots ?? ['.']).map(entry => {
    const candidate = canonicalTarget(resolve(root, entry));
    if (!inside(root, candidate)) throw new Error('notebookRoots must stay inside the workspace');
    return candidate;
  });
  if (!inside(root, real) || !roots.some(entry => inside(entry, real))) throw new Error('notebook path must stay inside the allowed working directory');
  const first = relative(root, real).split(/[\\/]/)[0];
  if (['.git', '.codex', '.concept-loom'].includes(first) || basename(real) === 'AGENTS.md') throw new Error('notebook path targets protected project files');
  return real;
}
