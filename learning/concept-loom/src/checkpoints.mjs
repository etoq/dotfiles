import { randomBytes } from 'node:crypto';
import { FORMATS, clone, hash, object, optionalText, sessionId, text, textList } from './validation.mjs';
import { confidenceSignal } from './reviews.mjs';

const cards = new Map();
const TTL = 6 * 60 * 60 * 1000;
function expire() { for (const [token, card] of cards) if (Date.now() - card.createdAt > TTL) cards.delete(token); }
function mix(items, random) {
  const result = [...items];
  for (let index = result.length - 1; index > 0; index -= 1) { const swap = Math.floor(random() * (index + 1)); [result[index], result[swap]] = [result[swap], result[index]]; }
  return result;
}
export function checkpointOperationId(token) { return `checkpoint:t-${hash(text(token, 'token')).slice(0, 24)}`; }
export function composeCheckpoint(input, random = Math.random) {
  expire();
  const prompt = text(input.prompt, 'prompt');
  const rationale = text(input.rationale, 'rationale');
  const format = input.format ?? 'choice';
  if (!FORMATS.includes(format)) throw new Error(`format must be one of ${FORMATS.join(', ')}`);
  for (const key of ['multiple', 'mix']) if (input[key] !== undefined && typeof input[key] !== 'boolean') throw new Error(`${key} must be a boolean`);
  const token = randomBytes(18).toString('base64url');
  const boundSession = input.sessionId === undefined ? undefined : sessionId(input.sessionId);
  const task = {
    taskId: checkpointOperationId(token).slice('checkpoint:'.length), prompt, format,
    framedAt: new Date().toISOString(), variantId: optionalText(input.variantId, 'variantId'),
    conceptId: optionalText(input.conceptId, 'conceptId'), evidenceConcept: optionalText(input.evidenceConcept, 'evidenceConcept'),
    rubricVersion: optionalText(input.rubricVersion, 'rubricVersion') ?? 'coach-defined-unspecified',
    conditions: input.conditions ? clone(object(input.conditions, 'conditions')) : {},
  };
  const card = { createdAt: Date.now(), sessionId: boundSession, rationale, task };
  if (format === 'choice') {
    if (!Array.isArray(input.choices) || input.choices.length < 2) throw new Error('choices must contain at least two entries');
    const keys = new Set();
    const choices = input.choices.map((entry, index) => {
      object(entry, `choice ${index + 1}`);
      const key = text(entry.key, 'choice key');
      if (key === '__gap__') throw new Error("choice key '__gap__' is reserved");
      if (keys.has(key)) throw new Error(`choice key '${key}' is duplicated`);
      keys.add(key);
      return { key, label: text(entry.label, 'choice label') };
    });
    const expected = new Set(textList(Array.isArray(input.expected) ? input.expected : [input.expected], 'expected'));
    if (!expected.size || [...expected].some(key => !keys.has(key))) throw new Error('expected must name existing choice keys');
    const multiple = input.multiple === true;
    if (!multiple && expected.size !== 1) throw new Error('a single-choice checkpoint needs one expected key');
    card.expected = expected;
    task.multiple = multiple;
    task.choices = input.mix === false ? choices : mix(choices, random);
  } else {
    card.criteria = textList(input.criteria, 'criteria');
    if (!card.criteria.length) throw new Error('criteria must contain at least one entry');
    task.criterionIds = input.criterionIds ? textList(input.criterionIds, 'criterionIds') : card.criteria.map((_, index) => `criterion-${index + 1}`);
    if (task.criterionIds.length !== card.criteria.length || new Set(task.criterionIds).size !== task.criterionIds.length) throw new Error('criterionIds must uniquely match the private criteria');
  }
  cards.set(token, card);
  return { token, ...clone(task), escapeChoice: { key: '__gap__', label: 'I do not know yet' }, instructions: format === 'choice' ? 'Select the fitting keys, or __gap__.' : 'Answer in your own words, or __gap__. Confidence is optional.' };
}
function rubricResults(input, card) {
  if (!Array.isArray(input.criterionResults)) throw new Error('criterionResults must cover every private criterion by its ID');
  const byId = new Map();
  const suppliedTexts = [input.response, ...(input.observations ?? []).map(entry => entry.text)];
  for (const entry of input.criterionResults) {
    object(entry, 'criterion result');
    if (!card.task.criterionIds.includes(entry.id) || byId.has(entry.id)) throw new Error('criterionResults contains an unknown or duplicated ID');
    if (!['pass', 'needs-repair', 'not-demonstrated'].includes(entry.result)) throw new Error('invalid criterion result');
    if (entry.result === 'pass') {
      text(entry.evidenceQuote, 'evidenceQuote');
      if (!suppliedTexts.some(value => typeof value === 'string' && value.includes(entry.evidenceQuote))) throw new Error('evidenceQuote must occur in the supplied response or observations');
    }
    byId.set(entry.id, { id: entry.id, result: entry.result, evidenceQuote: entry.evidenceQuote, note: optionalText(entry.note, 'criterion note') });
  }
  if (byId.size !== card.task.criterionIds.length) throw new Error('criterionResults must cover every criterion');
  return card.task.criterionIds.map(id => byId.get(id));
}
export function assessCheckpoint(input, { consume = true } = {}) {
  expire();
  const token = text(input.token, 'token');
  const card = cards.get(token);
  if (!card) throw new Error('checkpoint token is unknown or expired');
  if (card.sessionId !== undefined && input.sessionId !== card.sessionId) throw new Error('checkpoint belongs to a different learning session');
  if (input.confidence !== undefined && (!Number.isInteger(input.confidence) || input.confidence < 0 || input.confidence > 100)) throw new Error('confidence must be an integer from 0 to 100');
  let outcome, selected, response, criterionResults;
  if (card.task.format === 'choice') {
    selected = textList(Array.isArray(input.selected) ? input.selected : [input.selected], 'selected');
    if (!selected.length || new Set(selected).size !== selected.length) throw new Error('selected must contain unique answer keys');
    const gap = selected.includes('__gap__');
    if (gap && selected.length !== 1) throw new Error('__gap__ cannot be combined with another choice');
    if (!card.task.multiple && selected.length !== 1) throw new Error('this checkpoint accepts one choice');
    const keys = card.task.choices.map(choice => choice.key);
    if (selected.some(key => key !== '__gap__' && !keys.includes(key))) throw new Error('selected key does not exist');
    outcome = gap ? 'knowledge-gap' : selected.length === card.expected.size && selected.every(key => card.expected.has(key)) ? 'accurate' : 'needs-repair';
  } else {
    text(input.response, 'response'); response = input.response;
    const gap = response.trim() === '__gap__';
    outcome = gap ? 'knowledge-gap' : text(input.verdict, 'verdict');
    if (!['accurate', 'needs-repair', 'knowledge-gap'].includes(outcome)) throw new Error('invalid verdict');
    criterionResults = gap ? [] : rubricResults(input, card);
    if (outcome === 'accurate' && criterionResults.some(entry => entry.result !== 'pass')) throw new Error('accurate verdict requires every criterion to pass');
    if (outcome === 'needs-repair' && criterionResults.every(entry => entry.result === 'pass')) throw new Error('needs-repair verdict contradicts all-pass criteria');
  }
  if (consume) cards.delete(token);
  return {
    format: card.task.format, task: clone(card.task), outcome, accurate: outcome === 'accurate',
    selected, response, confidence: input.confidence, confidenceSignal: confidenceSignal(outcome === 'accurate', input.confidence),
    basis: card.task.format === 'choice' ? 'exact-match-to-coach-key' : 'coach-rubric-evaluation',
    criterionResults, rationale: card.rationale,
    ...(card.task.format === 'choice' ? { expected: [...card.expected] } : { criteria: card.criteria }),
  };
}
export function consumeCheckpoint(token) { if (!cards.delete(text(token, 'token'))) throw new Error('checkpoint token is unknown or expired'); }
export function resetCheckpointsForTests() { cards.clear(); }
