import { FORMATS, MODES, PHASES } from './validation.mjs';
const S = { type: 'string' }, B = { type: 'boolean' }, I = { type: 'integer', minimum: 0 };
const list = items => ({ type: 'array', items });
const obj = (properties, required = []) => ({ type: 'object', properties, required, additionalProperties: false });
const arbitrary = { type: 'object' };
const identity = { sessionId: S, expectedRevision: { ...I, description: 'Revision loaded immediately before this update.' }, operationId: { ...S, description: 'Stable unique operation ID: reuse the same ID and input when retrying.' } };
const observations = list(obj({ kind: { enum: ['prediction', 'terminal-output', 'learner-explanation', 'coach-observation'] }, text: S, source: S }, ['kind', 'text']));
const stateFields = {
  ...identity, topic: S, goal: S, phase: { enum: PHASES }, mode: { enum: MODES }, nextStep: S, currentStep: S,
  route: list(S), secured: list(S), gaps: list(S), notebookPath: S, learnerContext: S,
  routeExtensions: list(obj({ concept: S, dependsOn: list(S), reason: S, addedAt: S }, ['concept'])),
  evidence: { ...arbitrary, description: 'Legacy full replacement; changed data requires replaceEvidence, expectedRevision and replacementReason.' },
  replaceEvidence: B, replacementReason: S, evidenceUpdates: arbitrary, maintenanceReason: S,
  learnerResponse: { ...S, description: 'Exact non-checkpoint learner response; never substitute a summary.' }, observations,
  lessonId: S, lessonStatus: { enum: ['active', 'paused', 'complete'] }, includeState: B,
};
function tool(name, description, properties, required = [], readOnly = false, destructive = false, idempotent = readOnly) {
  return { name, description, inputSchema: obj(properties, required), annotations: { readOnlyHint: readOnly, destructiveHint: destructive, idempotentHint: idempotent, openWorldHint: false } };
}
export const toolCatalog = [
  tool('loom_frame_checkpoint', 'Create a concealed-answer checkpoint. Present only its public card. Bind the session and concept; keep private criteria out of notebooks.', {
    sessionId: S, conceptId: S, evidenceConcept: S, prompt: S, rationale: S,
    format: { enum: FORMATS }, choices: { ...list(obj({ key: S, label: S }, ['key', 'label'])), minItems: 2 },
    expected: { oneOf: [S, list(S)] }, criteria: list(S), criterionIds: list(S), rubricVersion: S, variantId: S, conditions: arbitrary, multiple: B, mix: B,
  }, ['prompt', 'rationale']),
  tool('loom_assess_checkpoint', 'Assess the exact learner answer and persist an event before continuing. Open responses require criterionResults by ID; pass needs an evidenceQuote from the response or observations. Unknown assistance never counts as independent.', {
    ...identity, token: S, response: S, selected: { oneOf: [S, list(S)] }, verdict: { enum: ['accurate', 'needs-repair', 'knowledge-gap'] },
    confidence: { type: 'integer', minimum: 0, maximum: 100 }, confidenceSource: S,
    evidenceConcept: S, conceptId: S, currentStep: S, nextStep: S, securedConnection: { ...S, description: 'Legacy concept label; does not grant mastery.' }, gap: S,
    hintUsed: { ...B, description: 'Legacy explicit report; omitted means unknown, never false.' },
    assistance: obj({ status: { enum: ['unknown', 'none', 'hint', 'explanation', 'solution'] }, reportedBy: S, details: S }, ['status']),
    criterionResults: list(obj({ id: S, result: { enum: ['pass', 'needs-repair', 'not-demonstrated'] }, evidenceQuote: S, note: S }, ['id', 'result'])),
    observations, conditions: { ...arbitrary, description: 'Reported actual conditions, stored separately from the agreed task conditions.' },
    evaluator: S, lessonId: S, note: S, includeState: B,
  }, ['token', 'sessionId', 'nextStep']),
  tool('loom_save_learning_state', 'Save the exact resume point. Omitted fields are preserved. Supply learnerResponse/observations for non-checkpoint answers. Configured notebooks and Current_Stage sync automatically; inspect commitInfo issues.', stateFields, ['sessionId', 'nextStep']),
  tool('loom_patch_learning_state', 'Patch fields or selected evidence records without resending the complete ledger. Full history replacement is forbidden. Reuse operationId for retries.', stateFields, ['sessionId', 'expectedRevision', 'operationId', 'nextStep']),
  tool('loom_load_learning_state', 'Load the saved exact next step and complete evidence. Unreadable neighboring sessions are reported separately. Never restart a saved course from diagnosis.', { sessionId: S }, [], true),
  tool('loom_list_due_reviews', 'List due concepts with stable IDs and provenance. A due date is a scheduling hint; delay and assistance are checked separately when assessed.', { sessionId: S, now: S }, [], true),
  tool('loom_status', 'Read server version, project, revision, resume point and synchronization health without changing progress. An operationId can be checked after a lost reply.', { sessionId: S, operationId: S }, [], true),
  tool('loom_doctor', 'Read-only integrity and compatibility audit: journal, snapshot, backup, Python lock runtime, project rules and notebook/current-stage synchronization.', { sessionId: S }, [], true),
  tool('loom_begin_lesson', 'Start a distinct lesson at the saved next step after the learner requests continuation. This records workflow only, not mastery or approval of a new route.', identity, ['sessionId', 'expectedRevision', 'operationId']),
  tool('loom_approve_route', 'Record actual user consent for the current route version. Supply a reference and exact quote; never invent approval or grade a preference.', { ...identity, reference: S, quotedConsent: S, nextStep: S }, ['sessionId', 'expectedRevision', 'operationId', 'reference', 'quotedConsent']),
  tool('loom_rename_concept', 'Change a display name while keeping the stable concept ID, evidence and old aliases.', { ...identity, conceptId: S, name: S }, ['sessionId', 'expectedRevision', 'operationId', 'conceptId', 'name']),
  tool('loom_sync_learning_records', 'Retry configured Markdown projections from committed events without adding a learner attempt or advancing the revision.', { sessionId: S }, ['sessionId'], false, false, true),
  tool('loom_start_notebook', 'Create or open a notebook in the allowed project directory. Explicit replacement first saves a recoverable copy.', { path: S, title: S, replace: B }, [], false, true),
  tool('loom_add_note', 'Add a useful optional annotation. Configured automatic event records already contain learner attempts; avoid duplicating those manually.', { path: S, kind: { enum: ['learner', 'guide', 'prompt', 'response', 'insight', 'diagram'] }, body: S, title: S }, ['path', 'kind', 'body']),
  tool('loom_show_relation_map', 'Prepare a terminal-readable Mermaid diagram; does not create files.', { source: S, label: S }, ['source', 'label'], true),
  tool('loom_show_text_diagram', 'Prepare a terminal-readable monospace diagram; does not create files.', { source: S, label: S }, ['source', 'label'], true),
];
