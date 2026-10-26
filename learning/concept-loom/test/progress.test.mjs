import test from "node:test";
import assert from "node:assert/strict";
import { mkdtemp, readFile, readdir } from "node:fs/promises";
import { join } from "node:path";
import { tmpdir } from "node:os";
import { listDueReviews, loadLearningState, recordCheckpointAssessment, saveLearningState } from "../src/progress.mjs";

test("persists and restores a learning session", async () => {
  const root = await mkdtemp(join(tmpdir(), "loom-progress-"));
  await saveLearningState(root, {
    sessionId: "ja4-basics",
    topic: "JA4",
    goal: "Understand JA4 fingerprints",
    phase: "build",
    route: ["TLS ClientHello", "JA4 components"],
    secured: ["TLS ClientHello"],
    gaps: [],
    currentStep: "TLS ClientHello",
    nextStep: "Explain JA4 components",
  });

  const restored = await loadLearningState(root, { sessionId: "ja4-basics" });
  assert.equal(restored.state.nextStep, "Explain JA4 components");
  assert.deepEqual(restored.state.secured, ["TLS ClientHello"]);
  const diskState = JSON.parse(await readFile(join(root, ".concept-loom/sessions/ja4-basics.json"), "utf8"));
  assert.equal(diskState.revision, 1);
});

test("returns the latest state and session summaries", async () => {
  const root = await mkdtemp(join(tmpdir(), "loom-progress-"));
  await saveLearningState(root, {
    sessionId: "first",
    topic: "First",
    goal: "Learn first",
    phase: "locate",
    nextStep: "Probe",
  });
  await new Promise((resolveDelay) => setTimeout(resolveDelay, 2));
  await saveLearningState(root, {
    sessionId: "second",
    topic: "Second",
    goal: "Learn second",
    phase: "weave",
    nextStep: "Approve route",
  });

  const restored = await loadLearningState(root);
  assert.equal(restored.state.sessionId, "second");
  assert.equal(restored.sessions.length, 2);
});

test("updates a session atomically and increments its revision", async () => {
  const root = await mkdtemp(join(tmpdir(), "loom-progress-"));
  const base = {
    sessionId: "topic",
    topic: "Topic",
    goal: "Learn topic",
    phase: "build",
    nextStep: "Step one",
  };
  await saveLearningState(root, base);
  const updated = await saveLearningState(root, { ...base, secured: ["Step one"], nextStep: "Step two" });
  assert.equal(updated.revision, 2);
  assert.deepEqual(updated.secured, ["Step one"]);
});

test("records checkpoint outcome before the lesson continues", async () => {
  const root = await mkdtemp(join(tmpdir(), "loom-progress-"));
  await saveLearningState(root, {
    sessionId: "ja4",
    topic: "JA4",
    goal: "Understand JA4",
    phase: "build",
    route: ["TLS", "JA4"],
    nextStep: "Check TLS understanding",
  });

  const updated = await recordCheckpointAssessment(root, {
    sessionId: "ja4",
    currentStep: "TLS",
    nextStep: "Explain JA4 fields",
    securedConnection: "TLS ClientHello structure",
    hintUsed: false,
  }, {
    outcome: "accurate",
    selected: ["client-hello"],
  });

  assert.equal(updated.nextStep, "Explain JA4 fields");
  assert.deepEqual(updated.secured, []);
  assert.equal(updated.lastCheckpoint.outcome, "accurate");
  assert.equal(updated.evidence["TLS ClientHello structure"].dimensions.recognition, "demonstrated");
  assert.equal(updated.evidence["TLS ClientHello structure"].attempts, 1);
  assert.equal(updated.revision, 2);
});

test("tracks transfer evidence, confidence, hints, and delayed review", async () => {
  const root = await mkdtemp(join(tmpdir(), "loom-progress-"));
  await saveLearningState(root, {
    sessionId: "transactions",
    topic: "Transactions",
    goal: "Choose isolation levels",
    phase: "build",
    mode: "practice",
    route: ["Atomicity", "Isolation"],
    routeExtensions: [{ concept: "Write skew", dependsOn: ["Isolation"], reason: "Found during practice" }],
    nextStep: "Try a transfer problem",
  });

  const updated = await recordCheckpointAssessment(root, {
    sessionId: "transactions",
    currentStep: "Isolation",
    nextStep: "Review tomorrow",
    evidenceConcept: "Isolation trade-offs",
    hintUsed: false,
  }, {
    format: "transfer",
    outcome: "accurate",
    response: "Use serializable because the invariant spans rows.",
    confidence: 85,
    calibration: "well-calibrated",
  });

  const evidence = updated.evidence["Isolation trade-offs"];
  assert.equal(updated.mode, "practice");
  assert.equal(updated.routeExtensions[0].concept, "Write skew");
  assert.equal(evidence.dimensions.transfer, "demonstrated");
  assert.equal(evidence.transferPassed, true);
  assert.equal(evidence.lastConfidence, 85);
  assert.match(evidence.reviewAfter, /^\d{4}-\d{2}-\d{2}T/);

  const reviews = await listDueReviews(root, { now: "2100-01-01T00:00:00.000Z" });
  assert.equal(reviews.due.length, 1);
  assert.equal(reviews.due[0].concept, "Isolation trade-offs");
});

async function sampleSession(extra = {}) {
  const root = await mkdtemp(join(tmpdir(), "loom-regression-"));
  const state = await saveLearningState(root, {
    sessionId: "sample", topic: "Sample", goal: "Check persistence", phase: "build",
    nextStep: "First", route: ["First", "Second"], secured: ["Earlier"], gaps: ["Gap"],
    notebookPath: "progress/sample.md", currentStep: "First", learnerContext: "Keep this context",
    ...extra,
  });
  return { root, state };
}

test("omitted fields preserve the approved route and resume context", async () => {
  const { root, state } = await sampleSession();
  const updated = await saveLearningState(root, { sessionId: "sample", topic: state.topic, goal: state.goal, phase: "build", nextStep: "Second" });
  for (const key of ["route", "secured", "gaps", "notebookPath", "currentStep", "learnerContext"]) assert.deepEqual(updated[key], state[key], key);
  const cleared = await saveLearningState(root, { ...updated, route: [], secured: [] });
  assert.deepEqual(cleared.route, []);
  assert.deepEqual(cleared.secured, []);
});

test("stale revisions cannot overwrite a more recent save", async () => {
  const { root, state } = await sampleSession();
  await saveLearningState(root, { ...state, expectedRevision: 1, nextStep: "Newer" });
  await assert.rejects(saveLearningState(root, { ...state, expectedRevision: 1, nextStep: "Stale" }), /revision conflict/i);
  assert.equal((await loadLearningState(root, { sessionId: "sample" })).state.nextStep, "Newer");
});

test("parallel assessments preserve every attempt and revision", async () => {
  const { root } = await sampleSession();
  await Promise.all(Array.from({ length: 25 }, (_, index) => recordCheckpointAssessment(root, {
    sessionId: "sample", evidenceConcept: "Shared", nextStep: `After ${index}`,
  }, { format: "prediction", outcome: "accurate", response: `Response ${index}` })));
  const { state } = await loadLearningState(root, { sessionId: "sample" });
  assert.equal(state.revision, 26);
  assert.equal(state.evidence.Shared.attempts, 25);
  assert.equal(state.evidence.Shared.history.length, 25);
  assert.equal(new Set(state.evidence.Shared.history.map((entry) => entry.response)).size, 25);
  assert.deepEqual((await readdir(join(root, ".concept-loom/sessions"))).sort(), ["sample.json"]);
});

test("a hinted answer is not promoted to independent transfer evidence", async () => {
  const { root } = await sampleSession({ secured: [] });
  const state = await recordCheckpointAssessment(root, {
    sessionId: "sample", evidenceConcept: "Transfer", securedConnection: "Transfer", hintUsed: true, nextStep: "Try without help",
  }, { format: "transfer", outcome: "accurate", response: "Correct after a hint" });
  assert.deepEqual(state.secured, []);
  assert.equal(state.evidence.Transfer.dimensions.transfer, "assisted");
  assert.equal(state.evidence.Transfer.transferPassed, false);
  assert.equal(state.evidence.Transfer.independentSuccesses, 0);
  assert.equal(state.evidence.Transfer.history[0].hintUsed, true);
});

test("immediate successes neither postpone nor lengthen a delayed review", async () => {
  const { root } = await sampleSession();
  const input = { sessionId: "sample", evidenceConcept: "Recall", hintUsed: false, nextStep: "Next" };
  const assessment = { format: "free-recall", outcome: "accurate", response: "Synthetic response" };
  const first = await recordCheckpointAssessment(root, input, assessment);
  for (let index = 0; index < 5; index += 1) await recordCheckpointAssessment(root, input, assessment);
  const { state } = await loadLearningState(root, { sessionId: "sample" });
  assert.equal(state.evidence.Recall.reviewAfter, first.evidence.Recall.reviewAfter);
  assert.equal(state.evidence.Recall.successfulReviews, 0);
});

test("an independently passed due review advances the review interval", async () => {
  const { root } = await sampleSession({ evidence: { Recall: {
    attempts: 1, successes: 1, independentSuccesses: 1, lastSuccessfulLessonId: 'previous-lesson', lastSuccessfulRetrieval: "2000-01-01T00:00:00.000Z", reviewAfter: "2000-01-02T00:00:00.000Z",
  } } });
  const state = await recordCheckpointAssessment(root, { sessionId: "sample", evidenceConcept: "Recall", hintUsed: false, lessonId: 'current-lesson', nextStep: "Review later" }, { format: "free-recall", outcome: "accurate", response: "Recalled later" });
  const record = state.evidence.Recall;
  assert.equal(record.successfulReviews, 1);
  assert.equal(record.reviewStreak, 1);
  assert.equal(Date.parse(record.reviewAfter) - Date.parse(record.lastAttemptAt), 3 * 86400000);
  assert.equal(record.history[0].delayedReview, true);
});

test("attempt history excludes private grading material", async () => {
  const { root } = await sampleSession();
  const state = await recordCheckpointAssessment(root, { sessionId: "sample", evidenceConcept: "History", nextStep: "Continue", note: "A useful observation" }, {
    format: "prediction", outcome: "needs-repair", response: "Learner output\n", criteria: ["PRIVATE-CRITERION"], rationale: "PRIVATE-RATIONALE",
  });
  assert.equal(state.evidence.History.history[0].response, "Learner output\n");
  assert.equal(state.evidence.History.history[0].note, "A useful observation");
  assert.doesNotMatch(JSON.stringify(state), /PRIVATE-CRITERION|PRIVATE-RATIONALE/);
});
