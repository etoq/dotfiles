import { randomUUID } from 'node:crypto';
import { projectConfig, notebookPath } from './paths.mjs';
import { clone, hash, MODES, object, optionalText, PHASES, sessionId, text, textList, validateEvidence } from './validation.mjs';
import { assessEvidence, observationsFor, registerLegacyConcepts, resolveConcept } from './evidence.mjs';
import { lookupOperation, migrateSession, readSession, sessionNames, transaction, withSessionLock } from './storage.mjs';
import { syncProjections } from './projections.mjs';

export function routeDigest(state) { return hash({ goal: state.goal, route: state.route ?? [], routeExtensions: (state.routeExtensions ?? []).map(({ concept, dependsOn }) => ({ concept, dependsOn: dependsOn ?? [] })) }); }
export function migrateState(state, now = new Date()) {
  if (state.schemaVersion === 3) return state;
  const original = clone(state);
  const next = {
    ...state, schemaVersion: 3, revision: state.revision ?? 0, mode: state.mode ?? 'guided', evidence: state.evidence ?? {},
    route: state.route ?? [], secured: state.secured ?? [], gaps: state.gaps ?? [], routeExtensions: state.routeExtensions ?? [],
    concepts: registerLegacyConcepts(state.evidence), routeVersion: 1, migratedAt: now.toISOString(),
    migration: { sourceSchemaVersion: state.schemaVersion ?? 1, sourceRevision: state.revision ?? 0, sourceDigest: hash(original), provenance: 'existing-state-import; no learner attempts reconstructed' },
  };
  next.routeApproval = { status: 'legacy-context', routeVersion: 1, routeDigest: routeDigest(next), sourceReference: `legacy-session:${state.sessionId}:revision:${state.revision}`, recordedAt: now.toISOString(), note: 'Existing route context retained; this is not a newly collected user approval.' };
  return next;
}
export function assertRouteApproved(base, state) {
  const config = projectConfig(base);
  if (!config.requireRouteApproval || state.phase === 'locate') return;
  const approval = state.routeApproval;
  const valid = approval?.routeDigest === routeDigest(state) && (approval.status === 'approved' || (config.allowLegacyRoute && approval.status === 'legacy-context'));
  if (!valid) throw new Error('route approval is pending; record the real user consent for this route version before teaching');
}
function extensions(value, previous, now) {
  if (!Array.isArray(value)) throw new Error('routeExtensions must be an array');
  return value.map((entry, index) => {
    object(entry, `routeExtensions[${index}]`);
    const concept = text(entry.concept, 'route extension concept');
    return { ...entry, concept, dependsOn: entry.dependsOn === undefined ? [] : textList(entry.dependsOn, 'dependsOn'), addedAt: optionalText(entry.addedAt, 'addedAt') ?? previous?.find(item => item.concept === concept)?.addedAt ?? now.toISOString() };
  });
}
function buildState(base, previous, input, now) {
  const state = { ...(previous ?? {}), schemaVersion: 3, sessionId: sessionId(input.sessionId),
    topic: text(input.topic ?? previous?.topic, 'topic'), goal: text(input.goal ?? previous?.goal, 'goal'),
    phase: input.phase ?? previous?.phase, mode: input.mode ?? previous?.mode ?? 'guided',
    nextStep: text(input.nextStep ?? previous?.nextStep, 'nextStep'),
    createdAt: previous?.createdAt ?? now.toISOString(), updatedAt: now.toISOString(), revision: (previous?.revision ?? 0) + 1,
  };
  if (!PHASES.includes(state.phase)) throw new Error('invalid phase');
  if (!MODES.includes(state.mode)) throw new Error('invalid mode');
  for (const key of ['route', 'secured', 'gaps']) state[key] = input[key] === undefined ? previous?.[key] ?? [] : textList(input[key], key);
  for (const key of ['notebookPath', 'currentStep', 'learnerContext']) if (input[key] !== undefined) state[key] = optionalText(input[key], key);
  if (state.notebookPath) notebookPath(base, state.notebookPath);
  state.routeExtensions = input.routeExtensions === undefined ? previous?.routeExtensions ?? [] : extensions(input.routeExtensions, previous?.routeExtensions, now);
  if (input.evidence !== undefined) {
    validateEvidence(input.evidence);
    if (previous && hash(input.evidence) !== hash(previous.evidence ?? {})) {
      if (input.replaceEvidence !== true || input.expectedRevision === undefined) throw new Error('explicit evidence replacement requires replaceEvidence=true, expectedRevision and replacementReason; use evidenceUpdates for a patch');
      text(input.replacementReason, 'replacementReason');
    }
    state.evidence = clone(input.evidence);
  } else state.evidence = previous?.evidence ?? {};
  if (input.evidenceUpdates !== undefined) {
    object(input.evidenceUpdates, 'evidenceUpdates');
    state.evidence = { ...state.evidence };
    for (const [key, patch] of Object.entries(input.evidenceUpdates)) {
      object(patch, `evidenceUpdates.${key}`);
      if ('history' in patch) throw new Error('attempt history cannot be overwritten by a patch');
      if (Object.keys(patch).some(field => ['attempts', 'successes', 'independentSuccesses', 'successfulReviews', 'dimensions', 'transferPassed'].includes(field))) text(input.maintenanceReason, 'maintenanceReason for changing assessed evidence');
      Object.defineProperty(state.evidence, key, { value: { ...(state.evidence[key] ?? {}), ...patch }, enumerable: true, configurable: true, writable: true });
    }
    validateEvidence(state.evidence);
  }
  state.concepts = registerLegacyConcepts(state.evidence, previous?.concepts);
  const changed = previous && routeDigest(previous) !== routeDigest(state);
  state.routeVersion = previous ? (previous.routeVersion ?? 1) + (changed ? 1 : 0) : 1;
  state.routeApproval = changed || !previous ? { status: 'pending', routeVersion: state.routeVersion, routeDigest: routeDigest(state) } : previous.routeApproval;
  if (projectConfig(base).requireRouteApproval && state.phase === 'build' && state.routeApproval?.status === 'pending') state.phase = 'weave';
  if (input.learnerResponse !== undefined || input.observations !== undefined) {
    if (input.learnerResponse !== undefined) text(input.learnerResponse, 'learnerResponse');
    state.latestLearnerResponse = { text: input.learnerResponse, observations: observationsFor(input.observations), recordedAt: now.toISOString(), provenance: 'learner-response-reported-by-coach' };
  }
  if (input.lessonId !== undefined) state.activeLesson = { id: text(input.lessonId, 'lessonId'), startedAt: previous?.activeLesson?.id === input.lessonId ? previous.activeLesson.startedAt : now.toISOString(), status: input.lessonStatus ?? 'active' };
  else if (input.lessonStatus && state.activeLesson) state.activeLesson = { ...state.activeLesson, status: input.lessonStatus };
  return clone(state);
}
function optionsFor(base, extra = {}) { return { migrate: migrateState, project: (state, events) => syncProjections(base, state, events), ...extra }; }
function resultState(result) {
  return { ...result.state, commitInfo: { eventId: result.event?.eventId, operationId: result.event?.operationId, operationRevision: result.event?.revision, replayed: result.replayed, committed: true, diagnostics: result.diagnostics ?? [], projections: result.projections } };
}
export async function saveLearningState(base, input, options = {}) {
  const result = await transaction(base, sessionId(input.sessionId), input, (previous, now) => buildState(base, previous, input, now), optionsFor(base, { kind: input.learnerResponse !== undefined ? 'learner-response' : 'state-save', ...options }));
  return resultState(result);
}
export async function patchLearningState(base, input) {
  if (input.expectedRevision === undefined) throw new Error('expectedRevision is required for a partial update');
  text(input.operationId, 'operationId');
  const loaded = await readSession(base, input.sessionId);
  if (!loaded.state) throw new Error(`learning session '${input.sessionId}' was not found`);
  return saveLearningState(base, input);
}
export async function recordCheckpointAssessment(base, input, assessment, options = {}) {
  const result = await transaction(base, sessionId(input.sessionId), input, (previous, now) => {
    if (!previous) throw new Error(`learning session '${input.sessionId}' was not found`);
    assertRouteApproved(base, previous);
    if (!['accurate', 'needs-repair', 'knowledge-gap'].includes(assessment.outcome)) throw new Error('invalid assessment outcome');
    const recorded = assessEvidence(previous, input, assessment, now, projectConfig(base).review);
    const gaps = [...previous.gaps];
    if (assessment.outcome === 'knowledge-gap') {
      const gap = optionalText(input.gap, 'gap') ?? recorded.conceptName;
      if (!gaps.includes(gap)) gaps.push(gap);
    }
    return clone({ ...previous, evidence: recorded.evidence, concepts: recorded.concepts, gaps,
      // secured remains a historical compatibility summary, never inferred from one answer.
      currentStep: input.currentStep ?? previous.currentStep, nextStep: text(input.nextStep, 'nextStep'),
      lastCheckpoint: recorded.attempt, updatedAt: now.toISOString(), revision: previous.revision + 1,
    });
  }, optionsFor(base, { kind: 'checkpoint-assessed', provenance: 'learner-response-and-coach-assessment', contentDigest: hash({ outcome: assessment.outcome, format: assessment.format, response: assessment.response, selected: assessment.selected, confidence: assessment.confidence, criterionResults: assessment.criterionResults, taskId: assessment.task?.taskId }), ...options }));
  return resultState(result);
}
export async function loadLearningState(base, input = {}) {
  if (input.sessionId) {
    const loaded = await readSession(base, input.sessionId);
    if (!loaded.state) throw new Error(`learning session '${input.sessionId}' was not found`);
    return { state: loaded.state, diagnostics: loaded.diagnostics };
  }
  const states = [], diagnostics = [];
  const profile = projectConfig(base);
  for (const id of await sessionNames(base)) {
    if (profile.allowedSessionIds && !profile.allowedSessionIds.includes(id)) continue;
    try { const loaded = await readSession(base, id); if (loaded.state) states.push(loaded.state); diagnostics.push(...loaded.diagnostics.map(entry => ({ sessionId: id, ...entry }))); }
    catch (error) { diagnostics.push({ sessionId: id, kind: 'session-unreadable', message: error.message }); }
  }
  states.sort((a, b) => (b.updatedAt ?? '').localeCompare(a.updatedAt ?? ''));
  return { state: states.find(state => state.sessionId === profile.primarySessionId) ?? states[0] ?? null,
    sessions: states.map(({ sessionId, topic, goal, phase, nextStep, updatedAt, revision }) => ({ sessionId, topic, goal, phase, nextStep, updatedAt, revision })), diagnostics };
}
export async function listDueReviews(base, input = {}) {
  const now = input.now ? new Date(text(input.now, 'now')) : new Date();
  if (!Number.isFinite(now.getTime())) throw new Error('now must be an ISO date');
  const all = await loadLearningState(base);
  const due = [], diagnostics = [...all.diagnostics];
  for (const summary of all.sessions) {
    if (input.sessionId && summary.sessionId !== input.sessionId) continue;
    try {
      const { state } = await loadLearningState(base, { sessionId: summary.sessionId });
      const concepts = registerLegacyConcepts(state.evidence, state.concepts);
      for (const [key, evidence] of Object.entries(state.evidence ?? {})) if (Number.isFinite(Date.parse(evidence.reviewAfter)) && Date.parse(evidence.reviewAfter) <= now.getTime()) {
        const identity = Object.entries(concepts).find(([, value]) => value.evidenceKey === key);
        due.push({ sessionId: state.sessionId, conceptId: identity?.[0], concept: identity?.[1].name ?? key, reviewAfter: evidence.reviewAfter, lastFormat: evidence.lastFormat,
          assistance: evidence.assistance ?? { status: evidence.hintUsed === true ? 'hint' : 'unknown', provenance: 'legacy-report; false may have been a default' }, independentSuccesses: evidence.independentSuccesses ?? 0, successfulReviews: evidence.successfulReviews ?? 0,
          everPassedTransfer: evidence.everPassedTransfer === true, legacyTransferPassed: evidence.legacyTransferPassed ?? (evidence.everPassedTransfer === undefined ? evidence.transferPassed : undefined), latestTransferOutcome: evidence.latestTransferOutcome });
      }
    } catch (error) { diagnostics.push({ sessionId: summary.sessionId, kind: 'review-session-unreadable', message: error.message }); }
  }
  due.sort((a, b) => a.reviewAfter.localeCompare(b.reviewAfter));
  return { asOf: now.toISOString(), due, diagnostics };
}
export async function approveRoute(base, input) {
  text(input.reference, 'reference to the real user consent'); text(input.quotedConsent, 'quotedConsent');
  const result = await transaction(base, sessionId(input.sessionId), input, (previous, now) => {
    if (!previous) throw new Error('learning session was not found');
    return { ...previous, phase: 'build', nextStep: text(input.nextStep ?? previous.nextStep, 'nextStep'), routeApproval: {
      status: 'approved', routeVersion: previous.routeVersion, routeDigest: routeDigest(previous), reference: input.reference, quotedConsent: input.quotedConsent,
      recordedAt: now.toISOString(), provenance: 'user-consent-reported-by-client',
    }, revision: previous.revision + 1, updatedAt: now.toISOString() };
  }, optionsFor(base, { kind: 'route-approved', provenance: 'user-consent-reported-by-client' }));
  return resultState(result);
}
export async function beginLesson(base, input) {
  const result = await transaction(base, sessionId(input.sessionId), input, (previous, now) => {
    if (!previous) throw new Error('learning session was not found');
    return { ...previous, activeLesson: { id: randomUUID(), startedAt: now.toISOString(), status: 'active' }, revision: previous.revision + 1, updatedAt: now.toISOString() };
  }, optionsFor(base, { kind: 'lesson-start', provenance: 'workflow-event; no knowledge demonstrated' }));
  return resultState(result);
}
export async function renameConcept(base, input) {
  const result = await transaction(base, sessionId(input.sessionId), input, (previous, now) => {
    if (!previous) throw new Error('learning session was not found');
    const identity = resolveConcept(previous, { conceptId: input.conceptId });
    const name = text(input.name, 'name');
    if (Object.entries(identity.concepts).some(([id, entry]) => id !== identity.id && (entry.name === name || entry.aliases?.includes(name)))) throw new Error('concept name or alias is already in use');
    identity.concepts[identity.id] = { ...identity.entry, name, aliases: [...new Set([...(identity.entry.aliases ?? []), identity.entry.name, name])] };
    return { ...previous, concepts: identity.concepts, revision: previous.revision + 1, updatedAt: now.toISOString() };
  }, optionsFor(base, { kind: 'concept-renamed', provenance: 'metadata-edit; no knowledge demonstrated' }));
  return resultState(result);
}
export async function syncLearningRecords(base, input) {
  return withSessionLock(base, sessionId(input.sessionId), async () => {
    const loaded = await readSession(base, input.sessionId);
    if (!loaded.state) throw new Error('learning session was not found');
    if (loaded.state.schemaVersion !== 3) throw new Error('migrate the historical state before generating records');
    return syncProjections(base, loaded.state, loaded.events);
  });
}
export async function migrateLearningState(base, id) { return migrateSession(base, id, migrateState, (state, events) => syncProjections(base, state, events)); }
export async function findCompletedOperation(base, id, operationId) { return lookupOperation(base, id, operationId); }
export function compactState(state) {
  return { sessionId: state.sessionId, schemaVersion: state.schemaVersion, revision: state.revision, phase: state.phase, routeVersion: state.routeVersion, routeApproval: state.routeApproval?.status,
    currentStep: state.currentStep, nextStep: state.nextStep, activeLesson: state.activeLesson, lastCheckpoint: state.lastCheckpoint ? { attemptId: state.lastCheckpoint.attemptId, conceptId: state.lastCheckpoint.conceptId, outcome: state.lastCheckpoint.outcome, assistance: state.lastCheckpoint.assistance, independent: state.lastCheckpoint.independent, delayedReview: state.lastCheckpoint.delayedReview } : undefined,
    commitInfo: state.commitInfo };
}
