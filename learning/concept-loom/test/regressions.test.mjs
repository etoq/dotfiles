import test from 'node:test';
import assert from 'node:assert/strict';
import { appendFile, mkdir, readFile, readdir, rm, symlink, writeFile } from 'node:fs/promises';
import { join } from 'node:path';
import { fixture, basic, answer } from '../test-support/fixtures.mjs';
import { approveRoute, beginLesson, loadLearningState, listDueReviews, migrateLearningState, patchLearningState, recordCheckpointAssessment, renameConcept, saveLearningState, syncLearningRecords } from '../src/progress.mjs';
import { beginNotebook, resolveNotebookPath } from '../src/notebook.mjs';
import { readJournal } from '../src/storage.mjs';
import { doctor, status } from '../src/diagnostics.mjs';
import { hash } from '../src/validation.mjs';

const input = { sessionId: 'sample', evidenceConcept: 'Concept', nextStep: 'Continue' };
test('unreported assistance stays unknown and never secures recognition', async t => {
  const { base } = await fixture(t);
  const state = await recordCheckpointAssessment(base, { ...input, securedConnection: 'Concept' }, { ...answer, format: 'choice' });
  assert.equal(state.evidence.Concept.independentSuccesses, 0);
  assert.equal(state.evidence.Concept.assistance.status, 'unknown');
  assert.equal(state.evidence.Concept.dimensions.recognition, 'independence-unknown');
  assert.deepEqual(state.secured, []);
  const independent = await recordCheckpointAssessment(base, { ...input, assistance: { status: 'none' } }, answer);
  assert.equal(independent.evidence.Concept.independentSuccesses, 1);
  assert.deepEqual(independent.secured, []);
});
test('a missing concept rejects the assessment without advancing progress', async t => {
  const { base } = await fixture(t);
  await assert.rejects(recordCheckpointAssessment(base, { sessionId: 'sample', nextStep: 'Wrong' }, answer), /conceptId is required/);
  assert.equal((await loadLearningState(base, { sessionId: 'sample' })).state.revision, 1);
});
test('crossing a due date within 352 ms does not become delayed retrieval', async t => {
  const start = '2030-01-01T12:00:00.000Z';
  const { base } = await fixture(t, { state: { evidence: { Concept: { independentSuccesses: 1, lastSuccessfulLessonId: 'old', lastSuccessfulRetrieval: '2029-12-30T12:00:00.000Z', reviewAfter: '2030-01-01T12:00:00.200Z' } } }, now: start });
  await recordCheckpointAssessment(base, { ...input, hintUsed: false, lessonId: 'current' }, answer, { now: start });
  const state = await recordCheckpointAssessment(base, { ...input, hintUsed: false, lessonId: 'current' }, answer, { now: '2030-01-01T12:00:00.352Z' });
  assert.equal(state.evidence.Concept.successfulReviews, 0);
  assert.equal(state.lastCheckpoint.delayedReview, false);
  assert.equal(state.evidence.Concept.reviewStreak, 0);
});
test('sufficient spacing still needs a different lesson and explicit independence', async t => {
  const { base } = await fixture(t);
  const first = await recordCheckpointAssessment(base, { ...input, lessonId: 'first', hintUsed: false }, answer, { now: '2030-01-01T00:00:00.000Z' });
  const same = await recordCheckpointAssessment(base, { ...input, lessonId: 'first', hintUsed: false }, answer, { now: '2030-01-03T00:00:00.000Z' });
  assert.equal(same.lastCheckpoint.delayedReview, false);
  const later = await recordCheckpointAssessment(base, { ...input, lessonId: 'second', hintUsed: false }, answer, { now: '2030-01-05T00:00:00.000Z' });
  assert.equal(later.lastCheckpoint.delayedReview, true);
  assert.equal(later.evidence.Concept.successfulReviews, 1);
  assert.equal(Date.parse(later.evidence.Concept.reviewAfter) - Date.parse(later.updatedAt), 3 * 86400000);
});
test('evidence counter types are rejected before the journal changes', async t => {
  const { base } = await fixture(t);
  await assert.rejects(saveLearningState(base, { ...basic, evidence: { Bad: { attempts: '5' } } }), /integer/);
  assert.equal((await readJournal(base, 'sample')).events.length, 1);
  await assert.rejects(saveLearningState(base, { ...basic, evidence: { Bad: { history: ['not an attempt object'] } } }), /must be an object/);
});
test('unknown future snapshots cannot be downgraded even beside a valid journal', async t => {
  const { base } = await fixture(t);
  const path = join(base, '.concept-loom/sessions/sample.json');
  const original = JSON.parse(await readFile(path, 'utf8'));
  const future = JSON.stringify({ ...original, schemaVersion: 99, unknownFuture: 'keep' });
  await writeFile(path, future);
  await assert.rejects(saveLearningState(base, { ...basic, nextStep: 'No' }), /unsupported schemaVersion/);
  assert.equal(await readFile(path, 'utf8'), future);
});
test('a corrupt neighboring session does not hide valid reviews', async t => {
  const { base } = await fixture(t, { state: { evidence: { Due: { reviewAfter: '2000-01-01T00:00:00.000Z' } } } });
  await writeFile(join(base, '.concept-loom/sessions/unrelated.json'), '{broken');
  const result = await listDueReviews(base);
  assert.equal(result.due.length, 1);
  assert.ok(result.diagnostics.some(entry => entry.sessionId === 'unrelated'));
});
test('a corrupt snapshot is reconstructed from the verified event chain', async t => {
  const { base } = await fixture(t);
  await recordCheckpointAssessment(base, { ...input, hintUsed: false }, answer);
  await writeFile(join(base, '.concept-loom/sessions/sample.json'), '{broken');
  const loaded = await loadLearningState(base, { sessionId: 'sample' });
  assert.equal(loaded.state.evidence.Concept.attempts, 1);
  assert.ok(loaded.diagnostics.some(item => item.kind === 'snapshot-invalid'));
  await migrateLearningState(base, 'sample');
  assert.equal((await doctor(base, { sessionId: 'sample' })).healthy, true);
});
test('a torn uncommitted journal tail is preserved before repair', async t => {
  const { base } = await fixture(t);
  await appendFile(join(base, '.concept-loom/events/sample.jsonl'), '{torn tail');
  assert.equal((await loadLearningState(base, { sessionId: 'sample' })).state.revision, 1);
  await saveLearningState(base, { ...basic, nextStep: 'Recovered' });
  assert.equal((await readJournal(base, 'sample')).events.length, 2);
  const files = await readdir(join(base, '.concept-loom/recovery'));
  assert.equal(files.length, 1);
  assert.equal(await readFile(join(base, '.concept-loom/recovery', files[0]), 'utf8'), '{torn tail');
});
test('corruption inside a journal blocks mutation and leaves the bytes intact', async t => {
  const { base } = await fixture(t);
  const path = join(base, '.concept-loom/events/sample.jsonl');
  await appendFile(path, '{bad}\n');
  const bytes = await readFile(path, 'utf8');
  await assert.rejects(saveLearningState(base, { ...basic, nextStep: 'No' }), /journal corruption/);
  assert.equal(await readFile(path, 'utf8'), bytes);
  assert.equal((await doctor(base, { sessionId: 'sample' })).healthy, false);
});
test('idempotency survives a stale revision and rejects changed input', async t => {
  const { base } = await fixture(t);
  await assert.rejects(recordCheckpointAssessment(base, { ...input, operationId: '' }, answer), /non-empty stable string/);
  await assert.rejects(recordCheckpointAssessment(base, { ...input, operationId: ' ambiguous ' }, answer), /surrounding whitespace/);
  const args = { ...input, hintUsed: false, expectedRevision: 1, operationId: 'answer-1' };
  await recordCheckpointAssessment(base, args, answer);
  const retry = await recordCheckpointAssessment(base, args, answer);
  assert.equal(retry.commitInfo.replayed, true);
  assert.equal(retry.evidence.Concept.attempts, 1);
  await assert.rejects(recordCheckpointAssessment(base, { ...args, nextStep: 'Changed' }, answer), /different input/);
  await assert.rejects(recordCheckpointAssessment(base, args, { ...answer, response: 'Different answer' }), /different assessment/);
});
test('partial evidence updates preserve unrelated records and immutable history', async t => {
  const { base } = await fixture(t, { state: { evidence: { Other: { notes: 'keep' } } } });
  await recordCheckpointAssessment(base, { ...input, hintUsed: false }, answer);
  const patched = await patchLearningState(base, { sessionId: 'sample', expectedRevision: 2, operationId: 'patch-1', nextStep: 'Next', evidenceUpdates: { Concept: { notes: 'Clarified' } } });
  assert.equal(patched.evidence.Other.notes, 'keep');
  assert.equal(patched.evidence.Concept.history[0].response, answer.response);
  await assert.rejects(patchLearningState(base, { sessionId: 'sample', expectedRevision: 3, operationId: 'patch-2', nextStep: 'Next', evidenceUpdates: { Concept: { history: [] } } }), /history cannot be overwritten/);
});
test('failed snapshot writing returns a committed event that can be recovered', async t => {
  const { base } = await fixture(t);
  const args = { ...basic, operationId: 'save-after-journal', nextStep: 'Committed' };
  const state = await saveLearningState(base, args, { fault: point => { if (point === 'after-journal') throw new Error('synthetic disk fault'); } });
  assert.equal(state.commitInfo.committed, true);
  assert.equal(state.commitInfo.diagnostics[0].kind, 'snapshot-pending');
  assert.equal((await loadLearningState(base, { sessionId: 'sample' })).state.nextStep, 'Committed');
  await migrateLearningState(base, 'sample');
  assert.equal((await doctor(base, { sessionId: 'sample' })).healthy, true);
});
test('explicit route approval is tied to its version and real consent reference', async t => {
  const { base } = await fixture(t, { profile: { requireRouteApproval: true } });
  assert.equal((await loadLearningState(base, { sessionId: 'sample' })).state.phase, 'weave');
  await assert.rejects(recordCheckpointAssessment(base, { ...input, hintUsed: false }, answer), /approval is pending/);
  const approved = await approveRoute(base, { sessionId: 'sample', expectedRevision: 1, operationId: 'approve-1', reference: 'synthetic-user-message-1', quotedConsent: 'I approve these two test steps.' });
  assert.equal(approved.routeApproval.status, 'approved');
  await recordCheckpointAssessment(base, { ...input, hintUsed: false }, answer);
  const changed = await saveLearningState(base, { ...basic, route: ['One', 'Two', 'Unapproved extension'], nextStep: 'Ask for approval' });
  assert.equal(changed.routeApproval.status, 'pending');
  await assert.rejects(recordCheckpointAssessment(base, input, answer), /approval is pending/);
});
test('renaming keeps the stable concept ID and existing attempt history', async t => {
  const { base } = await fixture(t);
  const first = await recordCheckpointAssessment(base, { ...input, hintUsed: false }, answer);
  const id = first.evidence.Concept.conceptId;
  await renameConcept(base, { sessionId: 'sample', conceptId: id, name: 'Renamed', operationId: 'rename-1', expectedRevision: 2 });
  const second = await recordCheckpointAssessment(base, { sessionId: 'sample', conceptId: id, hintUsed: false, nextStep: 'Next' }, answer);
  assert.equal(second.concepts[id].name, 'Renamed');
  assert.equal(second.evidence.Concept.history.length, 2);
  assert.equal(Object.keys(second.evidence).length, 1);
});
test('distinct lesson IDs are persisted without marking new knowledge', async t => {
  const { base } = await fixture(t);
  const first = await beginLesson(base, { sessionId: 'sample', expectedRevision: 1, operationId: 'lesson-1' });
  const second = await beginLesson(base, { sessionId: 'sample', expectedRevision: 2, operationId: 'lesson-2' });
  assert.notEqual(first.activeLesson.id, second.activeLesson.id);
  assert.deepEqual(second.evidence, {});
  assert.equal(second.nextStep, basic.nextStep);
});
test('automatic projections preserve old text, one TOC and exact supplied output', async t => {
  const { base, stage } = await fixture(t, { profile: true });
  const state = await recordCheckpointAssessment(base, { ...input, hintUsed: true, observations: [{ kind: 'terminal-output', text: 'ABC\n  DEF\n' }] }, { ...answer, criteria: ['PRIVATE-CRITERION'], rationale: 'PRIVATE-RATIONALE' });
  assert.deepEqual(state.commitInfo.projections.issues, []);
  const current = await readFile(stage, 'utf8');
  assert.equal((current.match(/```table-of-contents/g) ?? []).length, 1);
  assert.match(current, /Preserve this old paragraph and \[\[Existing_Link\]\]/);
  assert.match(current, /Ревизия ConceptLoom: 2/);
  const notebook = await readFile(join(base, 'progress/notebook.md'), 'utf8');
  assert.match(notebook, /ABC\n>   DEF/);
  assert.doesNotMatch(notebook, /PRIVATE-/);
  await syncLearningRecords(base, { sessionId: 'sample' });
  assert.equal(await readFile(join(base, 'progress/notebook.md'), 'utf8'), notebook);
  assert.equal((await doctor(base, { sessionId: 'sample' })).healthy, true);
});
test('a refused stage export leaves the event committed and can be retried', { skip: process.platform === 'win32' }, async t => {
  const { base, stage, temporary } = await fixture(t, { profile: true });
  const outside = join(temporary, 'outside.md');
  await writeFile(outside, 'Untouched'); await rm(stage); await symlink(outside, stage);
  const state = await recordCheckpointAssessment(base, { ...input, hintUsed: false }, answer);
  assert.equal(state.commitInfo.committed, true);
  assert.ok(state.commitInfo.projections.issues.length);
  assert.equal(await readFile(outside, 'utf8'), 'Untouched');
  await rm(stage); await writeFile(stage, '# Restored stage\n');
  assert.deepEqual((await syncLearningRecords(base, { sessionId: 'sample' })).issues, []);
  assert.equal((await loadLearningState(base, { sessionId: 'sample' })).state.revision, 2);
});
test('notebook and data directory symlink escapes are rejected', { skip: process.platform === 'win32' }, async t => {
  const { base, temporary } = await fixture(t);
  const outside = join(temporary, 'outside'); await mkdir(outside);
  await symlink(outside, join(base, 'linked'), 'dir');
  assert.throws(() => resolveNotebookPath(base, 'linked/escape.md'), /inside/);
  await rm(join(base, '.concept-loom'), { recursive: true });
  await symlink(outside, join(base, '.concept-loom'), 'dir');
  await assert.rejects(saveLearningState(base, basic), /symlinks are forbidden/);
  assert.deepEqual(await readdir(outside), []);
});
test('backups have verified content digests and status defaults to compact output', async t => {
  const { base } = await fixture(t);
  await saveLearningState(base, { ...basic, nextStep: 'New' });
  const backup = JSON.parse(await readFile(join(base, '.concept-loom/backups/sample.json'), 'utf8'));
  assert.equal(backup.digest, hash(backup.state));
  const current = await status(base, { sessionId: 'sample' });
  assert.equal(current.serverVersion, '2.0.0');
  assert.equal(current.session.evidence, undefined);
});

test('historical migration preserves evidence verbatim and creates only one labelled baseline', async t => {
  const { base, state } = await fixture(t, { state: { evidence: { Legacy: { attempts: 2, successes: 1, hintUsed: true, transferPassed: true, reviewAfter: '2000-01-01T00:00:00.000Z', status: 'assisted', notes: 'Historical context only' } }, unknownLegacyField: 'kept' } });
  const legacy = { ...state, schemaVersion: 2, unknownLegacyField: 'kept' };
  for (const key of ['integrity', 'commitInfo', 'concepts', 'routeVersion', 'routeApproval']) delete legacy[key];
  await rm(join(base, '.concept-loom/events'), { recursive: true });
  await writeFile(join(base, '.concept-loom/sessions/sample.json'), JSON.stringify(legacy));
  const migrated = await migrateLearningState(base, 'sample');
  assert.deepEqual(migrated.state.evidence, legacy.evidence);
  assert.equal(migrated.state.unknownLegacyField, 'kept');
  assert.equal(migrated.state.nextStep, legacy.nextStep);
  assert.equal(migrated.state.revision, legacy.revision);
  assert.equal(migrated.state.routeApproval.status, 'legacy-context');
  const journal = await readJournal(base, 'sample');
  assert.equal(journal.events.length, 1);
  assert.equal(journal.events[0].kind, 'import-baseline');
  await migrateLearningState(base, 'sample');
  assert.equal((await readJournal(base, 'sample')).events.length, 1);
  const due = (await listDueReviews(base)).due[0];
  assert.equal(due.assistance.status, 'hint');
  assert.equal(due.everPassedTransfer, false);
  assert.equal(due.legacyTransferPassed, true);
  const newAnswer = await recordCheckpointAssessment(base, { sessionId: 'sample', evidenceConcept: 'Legacy', hintUsed: false, nextStep: 'Next' }, answer);
  assert.equal(newAnswer.evidence.Legacy.everPassedTransfer, false);
  assert.equal(newAnswer.evidence.Legacy.legacyTransferPassed, true);
});
