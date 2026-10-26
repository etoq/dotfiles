import { createHash } from 'node:crypto';

export const VERSION = '2.0.0';
export const SCHEMA_VERSION = 3;
export const PHASES = ['locate', 'weave', 'build', 'transfer', 'review', 'complete'];
export const MODES = ['guided', 'practice', 'review', 'challenge'];
export const FORMATS = ['choice', 'free-recall', 'prediction', 'debugging', 'transfer', 'verification'];
export function text(value, label) {
  if (typeof value !== 'string' || !value.trim()) throw new Error(`${label} must be a non-empty string`);
  return value.trim();
}
export function optionalText(value, label) {
  return value === undefined || value === null || value === '' ? undefined : text(value, label);
}
export function textList(value, label) {
  if (!Array.isArray(value)) throw new Error(`${label} must be an array`);
  return value.map((entry, i) => text(entry, `${label}[${i}]`));
}
export function object(value, label) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw new Error(`${label} must be an object`);
  return value;
}
export function integer(value, label, minimum = 0) {
  if (!Number.isSafeInteger(value) || value < minimum) throw new Error(`${label} must be an integer >= ${minimum}`);
  return value;
}
export function sessionId(value) {
  const id = text(value, 'sessionId');
  if (!/^[a-z0-9][a-z0-9_-]{0,63}$/i.test(id)) throw new Error('sessionId may contain only letters, numbers, underscores, and hyphens');
  return id;
}
export function canonical(value) {
  if (Array.isArray(value)) return value.map(canonical);
  if (value && typeof value === 'object') return Object.fromEntries(Object.keys(value).sort().filter(k => value[k] !== undefined).map(k => [k, canonical(value[k])]));
  return value;
}
export function hash(value) { return createHash('sha256').update(JSON.stringify(canonical(value))).digest('hex'); }
export function clone(value) { return JSON.parse(JSON.stringify(value)); }
export function validateEvidence(value) {
  object(value, 'evidence');
  for (const [concept, record] of Object.entries(value)) {
    object(record, `evidence.${concept}`);
    for (const key of ['attempts', 'successes', 'newCheckpoints', 'independentSuccesses', 'successfulReviews', 'reviewStreak', 'consecutiveSuccesses']) {
      if (record[key] !== undefined) integer(record[key], `evidence.${concept}.${key}`);
    }
    for (const key of ['lastAttemptAt', 'lastSuccessfulRetrieval', 'reviewAfter']) {
      if (record[key] !== undefined && (typeof record[key] !== 'string' || !Number.isFinite(Date.parse(record[key])))) throw new Error(`evidence.${concept}.${key} must be a date`);
    }
    if (record.history !== undefined && !Array.isArray(record.history)) throw new Error(`evidence.${concept}.history must be an array`);
    for (const [index, attempt] of (record.history ?? []).entries()) {
      object(attempt, `evidence.${concept}.history[${index}]`);
      if (attempt.response !== undefined && typeof attempt.response !== 'string') throw new Error('stored response must be text');
      if (attempt.selected !== undefined) textList(attempt.selected, 'stored selected keys');
      if (attempt.confidence !== undefined && (!Number.isInteger(attempt.confidence) || attempt.confidence < 0 || attempt.confidence > 100)) throw new Error('stored confidence must be from 0 to 100');
    }
    if (record.dimensions !== undefined) object(record.dimensions, `evidence.${concept}.dimensions`);
  }
  return value;
}
export function validateState(value, expectedId) {
  object(value, 'state');
  const version = value.schemaVersion ?? 1;
  if (![1, 2, 3].includes(version)) throw new Error(`unsupported schemaVersion ${version}; refusing to overwrite an unknown format`);
  if (sessionId(value.sessionId) !== expectedId) throw new Error('state sessionId does not match its filename');
  for (const key of ['topic', 'goal', 'nextStep']) text(value[key], key);
  for (const key of ['createdAt', 'updatedAt']) if (typeof value[key] !== 'string' || !Number.isFinite(Date.parse(value[key]))) throw new Error(`state.${key} must be a date`);
  if (!PHASES.includes(value.phase)) throw new Error('invalid state phase');
  if (value.mode !== undefined && !MODES.includes(value.mode)) throw new Error('invalid state mode');
  integer(value.revision ?? 0, 'revision');
  for (const key of ['route', 'secured', 'gaps']) if (value[key] !== undefined) textList(value[key], key);
  if (value.routeExtensions !== undefined && !Array.isArray(value.routeExtensions)) throw new Error('routeExtensions must be an array');
  if (value.concepts !== undefined) for (const [id, entry] of Object.entries(object(value.concepts, 'concepts'))) {
    object(entry, `concepts.${id}`); text(entry.name, 'concept name'); text(entry.evidenceKey, 'concept evidenceKey');
    if (entry.aliases !== undefined) textList(entry.aliases, 'concept aliases');
  }
  if (value.activeLesson !== undefined) {
    object(value.activeLesson, 'activeLesson'); text(value.activeLesson.id, 'activeLesson.id');
    if (!['active', 'paused', 'complete'].includes(value.activeLesson.status)) throw new Error('invalid activeLesson status');
  }
  validateEvidence(value.evidence ?? {});
  return value;
}
export function checkRevision(input, previous) {
  if (input.expectedRevision === undefined) return;
  integer(input.expectedRevision, 'expectedRevision');
  const actual = previous?.revision ?? 0;
  if (input.expectedRevision !== actual) throw new Error(`revision conflict: expected ${input.expectedRevision}, found ${actual}; reload before retrying`);
}

// A small shared JSON Schema validator keeps discovery and execution on one contract.
export function validateSchema(value, schema, path = 'arguments') {
  if (value === undefined) return;
  if (schema.oneOf) {
    const matches = schema.oneOf.filter(option => { try { validateSchema(value, option, path); return true; } catch { return false; } });
    if (matches.length !== 1) throw new Error(`${path} does not match exactly one allowed shape`);
    return;
  }
  if (schema.enum && !schema.enum.includes(value)) throw new Error(`${path} must be one of: ${schema.enum.join(', ')}`);
  if (schema.type === 'object') {
    object(value, path);
    for (const key of schema.required ?? []) if (value[key] === undefined) throw new Error(`${path}.${key} is required`);
    for (const [key, entry] of Object.entries(value)) {
      const property = schema.properties?.[key];
      if (!property && schema.additionalProperties === false) throw new Error(`${path}.${key} is not supported`);
      if (property) validateSchema(entry, property, `${path}.${key}`);
      else if (typeof schema.additionalProperties === 'object') validateSchema(entry, schema.additionalProperties, `${path}.${key}`);
    }
  }
  if (schema.type === 'array') {
    if (!Array.isArray(value)) throw new Error(`${path} must be an array`);
    if (schema.minItems !== undefined && value.length < schema.minItems) throw new Error(`${path} needs at least ${schema.minItems} entries`);
    value.forEach((entry, index) => validateSchema(entry, schema.items ?? {}, `${path}[${index}]`));
  }
  if (schema.type === 'string' && typeof value !== 'string') throw new Error(`${path} must be a string`);
  if (schema.type === 'boolean' && typeof value !== 'boolean') throw new Error(`${path} must be a boolean`);
  if (schema.type === 'integer') integer(value, path, schema.minimum ?? Number.MIN_SAFE_INTEGER);
  if (schema.type === 'number' && (typeof value !== 'number' || !Number.isFinite(value))) throw new Error(`${path} must be a finite number`);
  if (typeof value === 'number' && ((schema.minimum !== undefined && value < schema.minimum) || (schema.maximum !== undefined && value > schema.maximum))) throw new Error(`${path} is outside its allowed range`);
}
