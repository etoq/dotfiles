import { randomUUID } from 'node:crypto';
import { clone, hash, object, optionalText, text, textList } from './validation.mjs';
import { DIMENSIONS, reviewOutcome } from './reviews.mjs';

export function conceptId(name) { return `c-${hash(name).slice(0, 20)}`; }
export function registerLegacyConcepts(evidence, existing = {}) {
  const concepts = { ...existing };
  for (const key of Object.keys(evidence ?? {})) {
    if (Object.values(concepts).some(entry => entry.evidenceKey === key)) continue;
    const id = conceptId(key);
    concepts[id] = { name: key, evidenceKey: key, aliases: [key], origin: 'legacy-ledger' };
  }
  return concepts;
}
export function resolveConcept(state, input) {
  const name = optionalText(input.evidenceConcept, 'evidenceConcept') ?? optionalText(input.securedConnection, 'securedConnection');
  const concepts = registerLegacyConcepts(state.evidence, state.concepts);
  let id = input.conceptId;
  if (id !== undefined) {
    if (typeof id !== 'string' || !/^[a-z0-9][a-z0-9_-]{0,63}$/i.test(id)) throw new Error('invalid conceptId');
    if (!Object.hasOwn(concepts, id) && !name) throw new Error('unknown conceptId; provide an evidenceConcept name');
  } else if (name) id = Object.keys(concepts).find(key => concepts[key].name === name || concepts[key].aliases?.includes(name)) ?? conceptId(name);
  if (!id) throw new Error('evidenceConcept or conceptId is required; an attempt cannot be silently left without history');
  if (!Object.hasOwn(concepts, id)) concepts[id] = { name: name ?? id, evidenceKey: name ?? id, aliases: name ? [name] : [], origin: 'new-record' };
  return { id, entry: concepts[id], concepts };
}
export function assistanceFor(input) {
  if (input.hintUsed !== undefined && typeof input.hintUsed !== 'boolean') throw new Error('hintUsed must be a boolean');
  let assistance = input.assistance ? clone(object(input.assistance, 'assistance')) : undefined;
  const statuses = ['unknown', 'none', 'hint', 'explanation', 'solution'];
  if (assistance && !statuses.includes(assistance.status)) throw new Error(`assistance.status must be one of ${statuses.join(', ')}`);
  if (!assistance) assistance = { status: input.hintUsed === undefined ? 'unknown' : input.hintUsed ? 'hint' : 'none' };
  if (input.hintUsed !== undefined && ((input.hintUsed && ['none', 'unknown'].includes(assistance.status)) || (!input.hintUsed && assistance.status !== 'none'))) throw new Error('hintUsed conflicts with assistance.status');
  const reportProvided = input.assistance !== undefined || input.hintUsed !== undefined;
  return { ...assistance, reportedBy: assistance.reportedBy ?? (reportProvided ? 'coach' : 'not-reported'), reportProvided, provenance: 'client-report; not independently verified by MCP' };
}
export function observationsFor(value = []) {
  if (!Array.isArray(value)) throw new Error('observations must be an array');
  return value.map((entry, index) => {
    object(entry, `observations[${index}]`);
    if (!['prediction', 'terminal-output', 'learner-explanation', 'coach-observation'].includes(entry.kind)) throw new Error('invalid observation kind');
    text(entry.text, 'observation text');
    return { kind: entry.kind, text: entry.text, source: optionalText(entry.source, 'observation source') ?? (entry.kind === 'coach-observation' ? 'coach' : 'learner-reported') };
  });
}
export function assessEvidence(previous, input, assessment, now, policy = {}) {
  const identity = resolveConcept(previous, { ...assessment.task, ...input });
  const key = identity.entry.evidenceKey;
  const earlier = previous.evidence?.[key] ?? {};
  const assistance = assistanceFor(input);
  const independent = assessment.outcome === 'accurate' && assistance.status === 'none';
  const lessonId = text(input.lessonId ?? previous.activeLesson?.id ?? `process-${process.pid}`, 'lessonId');
  const format = assessment.format ?? 'choice';
  const dimension = DIMENSIONS[format];
  if (!dimension) throw new Error('unknown checkpoint format');
  const review = reviewOutcome(earlier, independent, lessonId, now, policy);
  const dimensionResult = independent ? 'demonstrated' : assessment.outcome !== 'accurate' ? 'needs-work' : assistance.status === 'unknown' ? 'independence-unknown' : 'assisted';
  const publicTask = assessment.task ? Object.fromEntries(Object.entries(assessment.task).filter(([key]) => ['taskId', 'prompt', 'format', 'framedAt', 'variantId', 'conceptId', 'evidenceConcept', 'rubricVersion', 'conditions', 'multiple', 'choices', 'criterionIds'].includes(key))) : { format, provenance: 'external-assessment-without-framed-task' };
  const attempt = {
    attemptId: randomUUID(), conceptId: identity.id, assessedAt: now.toISOString(), lessonId,
    task: clone(publicTask),
    format, dimension, outcome: assessment.outcome,
    selected: assessment.selected, response: assessment.response, confidence: assessment.confidence,
    confidenceSignal: assessment.confidenceSignal, confidenceSource: assessment.confidence === undefined ? undefined : input.confidenceSource ?? 'learner-confidence-reported-by-coach', assistance,
    hintUsed: assistance.status === 'unknown' ? null : assistance.status !== 'none',
    independent, delayedReview: review.delayedReview,
    assessment: { evaluator: input.evaluator ?? 'coach', basis: assessment.basis ?? 'coach-reported', verdict: assessment.outcome, criterionResults: assessment.criterionResults ?? [], ruleVersion: '2.0.0' },
    observations: observationsFor(input.observations),
    conditions: { agreed: assessment.task?.conditions ?? {}, reportedActual: input.conditions ? object(input.conditions, 'conditions') : {} },
    currentStep: input.currentStep ?? previous.currentStep,
    note: optionalText(input.note, 'note'),
  };
  const record = {
    ...earlier, conceptId: identity.id,
    attempts: (earlier.attempts ?? 0) + 1,
    successes: (earlier.successes ?? 0) + (assessment.outcome === 'accurate' ? 1 : 0),
    independentSuccesses: (earlier.independentSuccesses ?? 0) + (independent ? 1 : 0),
    successfulReviews: (earlier.successfulReviews ?? 0) + (review.delayedReview ? 1 : 0),
    reviewStreak: review.reviewStreak,
    consecutiveSuccesses: independent ? (earlier.consecutiveSuccesses ?? 0) + 1 : 0,
    dimensions: { ...(earlier.dimensions ?? {}), [dimension]: dimensionResult },
    lastFormat: format, lastOutcome: assessment.outcome, lastConfidence: assessment.confidence,
    lastConfidenceSignal: assessment.confidenceSignal, assistance,
    hintUsed: attempt.hintUsed,
    transferPassed: earlier.transferPassed === true || (format === 'transfer' && independent),
    everPassedTransfer: earlier.everPassedTransfer === true || (format === 'transfer' && independent),
    legacyTransferPassed: earlier.legacyTransferPassed ?? (earlier.everPassedTransfer === undefined ? earlier.transferPassed ?? null : null),
    ...(format === 'transfer' ? { latestTransferOutcome: dimensionResult, latestTransferAt: now.toISOString() } : {}),
    lastAttemptAt: now.toISOString(),
    lastSuccessfulRetrieval: independent ? now.toISOString() : earlier.lastSuccessfulRetrieval,
    lastSuccessfulLessonId: independent ? lessonId : earlier.lastSuccessfulLessonId,
    reviewAfter: review.reviewAfter,
    history: [...(earlier.history ?? []), clone(attempt)],
  };
  const evidence = { ...(previous.evidence ?? {}) };
  Object.defineProperty(evidence, key, { value: record, enumerable: true, writable: true, configurable: true });
  return { evidence, concepts: identity.concepts, attempt: clone(attempt), conceptName: identity.entry.name };
}
