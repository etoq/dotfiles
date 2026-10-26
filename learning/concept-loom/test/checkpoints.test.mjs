import test from "node:test";
import assert from "node:assert/strict";
import { composeCheckpoint, assessCheckpoint, resetCheckpointsForTests } from "../src/checkpoints.mjs";

test.beforeEach(() => resetCheckpointsForTests());

test("frames a checkpoint without leaking its key or rationale", () => {
  const card = composeCheckpoint({
    prompt: "Which shape has three sides?",
    choices: [{ key: "triangle", label: "Triangle" }, { key: "square", label: "Square" }],
    expected: "triangle",
    rationale: "A triangle is defined by its three sides.",
  }, () => 0.5);
  assert.equal(card.choices.length, 2);
  assert.equal("expected" in card, false);
  assert.equal("rationale" in card, false);
});

test("grades an exact multi-selection", () => {
  const card = composeCheckpoint({
    prompt: "Pick primes",
    choices: [{ key: "2", label: "2" }, { key: "3", label: "3" }, { key: "4", label: "4" }],
    expected: ["2", "3"],
    rationale: "Two and three have exactly two positive divisors.",
    multiple: true,
    mix: false,
  });
  const result = assessCheckpoint({ token: card.token, selected: ["3", "2"] });
  assert.equal(result.outcome, "accurate");
});

test("treats an admitted gap separately from a wrong guess", () => {
  const card = composeCheckpoint({
    prompt: "Pick one",
    choices: [{ key: "a", label: "A" }, { key: "b", label: "B" }],
    expected: "a",
    rationale: "A is expected.",
  });
  const result = assessCheckpoint({ token: card.token, selected: "__gap__" });
  assert.equal(result.outcome, "knowledge-gap");
  assert.equal(result.accurate, false);
});

test("checkpoint tokens can only be assessed once", () => {
  const card = composeCheckpoint({
    prompt: "Pick one",
    choices: [{ key: "a", label: "A" }, { key: "b", label: "B" }],
    expected: "a",
    rationale: "A is expected.",
  });
  assessCheckpoint({ token: card.token, selected: "a" });
  assert.throws(() => assessCheckpoint({ token: card.token, selected: "a" }), /unknown or expired/);
});

test("frames and assesses an open transfer checkpoint without leaking criteria", () => {
  const card = composeCheckpoint({
    format: "transfer",
    prompt: "Apply the principle to a new case.",
    criteria: ["Names the relevant constraint", "Justifies the decision"],
    rationale: "Both the constraint and its consequence are needed.",
  });
  assert.equal(card.format, "transfer");
  assert.equal("criteria" in card, false);
  assert.equal("rationale" in card, false);

  const result = assessCheckpoint({
    token: card.token,
    response: "The new case is limited by the same constraint, so the decision follows.",
    verdict: "accurate",
    criterionResults: card.criterionIds.map(id => ({ id, result: 'pass', evidenceQuote: 'same constraint' })),
    confidence: 82,
  });
  assert.equal(result.outcome, "accurate");
  assert.equal(result.confidenceSignal, 'no-specific-signal');
  assert.equal(result.calibration, undefined);
  assert.equal(result.criteria.length, 2);
});

test("detects confident incorrect answers and validates confidence", () => {
  const first = composeCheckpoint({
    prompt: "Pick one",
    choices: [{ key: "a", label: "A" }, { key: "b", label: "B" }],
    expected: "a",
    rationale: "A is expected.",
  });
  const result = assessCheckpoint({ token: first.token, selected: "b", confidence: 90 });
  assert.equal(result.confidenceSignal, 'incorrect-high-confidence');

  const second = composeCheckpoint({
    prompt: "Pick one",
    choices: [{ key: "a", label: "A" }, { key: "b", label: "B" }],
    expected: "a",
    rationale: "A is expected.",
  });
  assert.throws(() => assessCheckpoint({ token: second.token, selected: "a", confidence: 101 }), /0 to 100/);
});

function retryCard(extra = {}) {
  return composeCheckpoint({
    prompt: "Synthetic retry check",
    choices: [{ key: "a", label: "A" }, { key: "b", label: "B" }],
    expected: "a",
    rationale: "Private retry rationale",
    ...extra,
  });
}

test("invalid input does not consume a checkpoint", () => {
  const card = retryCard();
  assert.throws(() => assessCheckpoint({ token: card.token, selected: "missing" }), /does not exist/);
  assert.throws(() => assessCheckpoint({ token: card.token, selected: "a", confidence: 101 }), /0 to 100/);
  assert.equal(assessCheckpoint({ token: card.token, selected: "a" }).outcome, "accurate");
});

test("a preview assessment keeps the token until persistence succeeds", () => {
  const card = retryCard();
  assert.equal(assessCheckpoint({ token: card.token, selected: "a" }, { consume: false }).outcome, "accurate");
  assert.equal(assessCheckpoint({ token: card.token, selected: "a" }).outcome, "accurate");
  assert.throws(() => assessCheckpoint({ token: card.token, selected: "a" }), /unknown or expired/);
});

test("reserved gap keys cannot masquerade as ordinary answers", () => {
  assert.throws(() => retryCard({ choices: [{ key: "__gap__", label: "A" }, { key: "b", label: "B" }], expected: "__gap__" }), /reserved/);
});

test("a bound checkpoint rejects another session without consuming its token", () => {
  const card = retryCard({ sessionId: "first" });
  assert.throws(() => assessCheckpoint({ token: card.token, sessionId: "second", selected: "a" }), /session/);
  assert.equal(assessCheckpoint({ token: card.token, sessionId: "first", selected: "a" }).outcome, "accurate");
});

test("open responses retain the learner's supplied text", () => {
  const card = composeCheckpoint({ format: "prediction", prompt: "Explain this synthetic output", criteria: ["Private criterion"], rationale: "Private rationale" });
  const response = "  first line\nsecond line\n";
  assert.equal(assessCheckpoint({ token: card.token, response, verdict: "accurate", criterionResults: [{ id: card.criterionIds[0], result: 'pass', evidenceQuote: 'first line' }] }).response, response);
});

test('open grading rejects missing criteria and fabricated quotations without consuming the token', () => {
  const card = composeCheckpoint({ format: 'verification', prompt: 'Synthetic', criteria: ['PRIVATE'], rationale: 'PRIVATE' });
  const args = { token: card.token, response: 'actual observation', verdict: 'accurate' };
  assert.throws(() => assessCheckpoint(args), /criterionResults/);
  assert.throws(() => assessCheckpoint({ ...args, criterionResults: [{ id: card.criterionIds[0], result: 'pass', evidenceQuote: 'not supplied' }] }), /evidenceQuote/);
  assert.throws(() => assessCheckpoint({ ...args, criterionResults: [{ id: card.criterionIds[0], result: 'needs-repair' }] }), /every criterion/);
  assert.equal(assessCheckpoint({ ...args, criterionResults: [{ id: card.criterionIds[0], result: 'pass', evidenceQuote: 'actual observation' }] }).outcome, 'accurate');
});

test('typed and duplicate selections cannot be silently discarded', () => {
  const card = retryCard({ multiple: true });
  assert.throws(() => assessCheckpoint({ token: card.token, selected: ['a', 7] }), /string/);
  assert.throws(() => assessCheckpoint({ token: card.token, selected: ['a', 'a'] }), /unique/);
  assert.equal(assessCheckpoint({ token: card.token, selected: ['a'] }).outcome, 'accurate');
});
