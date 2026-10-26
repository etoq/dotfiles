import test from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { readFile } from 'node:fs/promises';
import { join } from 'node:path';
import { fixture, basic } from '../test-support/fixtures.mjs';
import { clientFor, server } from '../test-support/mcp-client.mjs';
const frame = { sessionId: 'sample', prompt: 'Synthetic choice', choices: [{ key: 'a', label: 'A' }, { key: 'b', label: 'B' }], expected: 'a', rationale: 'PRIVATE-RATIONALE' };
function raw(cwd, messages) {
  const result = spawnSync(process.execPath, [server], { cwd, input: messages.map(value => JSON.stringify(value)).join('\n') + '\n', encoding: 'utf8', timeout: 10000 });
  assert.equal(result.error, undefined);
  assert.equal(result.status, 0, result.stderr);
  return result.stdout.trim() ? result.stdout.trim().split('\n').map(line => JSON.parse(line)) : [];
}
test('notifications have no response and invalid object IDs are rejected', async t => {
  const { base } = await fixture(t);
  assert.deepEqual(raw(base, [{ jsonrpc: '2.0', method: 'ping' }]), []);
  const [response] = raw(base, [{ jsonrpc: '2.0', id: { invalid: true }, method: 'ping' }]);
  assert.equal(response.error.code, -32600); assert.equal(response.id, null);
});
test('tool requests require initialization and the initialized notification', async t => {
  const { base } = await fixture(t);
  assert.equal(raw(base, [{ jsonrpc: '2.0', id: 1, method: 'tools/list' }])[0].error.code, -32002);
  const response = raw(base, [
    { jsonrpc: '2.0', id: 1, method: 'initialize', params: { protocolVersion: '2025-06-18', capabilities: {}, clientInfo: { name: 'test', version: '1' } } },
    { jsonrpc: '2.0', id: 2, method: 'tools/list' },
  ]);
  assert.equal(response[1].error.code, -32002);
});
test('discovery and execution share required fields and typed arrays', async t => {
  const { base } = await fixture(t);
  const client = await clientFor(t, base);
  const missing = await client.request('tools/call', { name: 'loom_show_text_diagram', arguments: { source: 'a -> b' } });
  assert.equal(missing.error.code, -32602);
  const catalog = (await client.request('tools/list')).result.tools;
  assert.equal(catalog.length, 16);
  assert.equal(catalog.find(tool => tool.name === 'loom_doctor').annotations.readOnlyHint, true);
  const card = (await client.tool('loom_frame_checkpoint', frame)).structuredContent;
  const invalid = await client.request('tools/call', { name: 'loom_assess_checkpoint', arguments: { token: card.token, sessionId: 'sample', nextStep: 'Next', selected: ['a', 7] } });
  assert.equal(invalid.error.code, -32602);
});
test('a completed assessment is replayed after an MCP restart without a new attempt', async t => {
  const { base } = await fixture(t);
  const first = await clientFor(t, base);
  const card = (await first.tool('loom_frame_checkpoint', frame)).structuredContent;
  const args = { token: card.token, sessionId: 'sample', evidenceConcept: 'Concept', selected: 'a', hintUsed: false, expectedRevision: 1, nextStep: 'Continue' };
  const assessed = (await first.tool('loom_assess_checkpoint', args)).structuredContent;
  assert.equal(assessed.learningState.evidence, undefined);
  assert.equal(assessed.learningState.revision, 2);
  await first.stop();
  const second = await clientFor(t, base);
  const retried = (await second.tool('loom_assess_checkpoint', { ...args, includeState: true })).structuredContent;
  assert.equal(retried.replayed, true);
  assert.equal(retried.learningState.evidence.Concept.attempts, 1);
  const status = (await second.tool('loom_status', { sessionId: 'sample', operationId: assessed.operationId })).structuredContent;
  assert.deepEqual(status.operation, { committed: true, revision: 2 });
});
test('open assessments store task, quotations and output but no private grading material', async t => {
  const { base } = await fixture(t);
  const client = await clientFor(t, base);
  const card = (await client.tool('loom_frame_checkpoint', { sessionId: 'sample', format: 'verification', evidenceConcept: 'Verify', prompt: 'Check a synthetic observation', criteria: ['PRIVATE-CRITERION'], rationale: 'PRIVATE-RATIONALE', conditions: { allowedReferences: ['manual'] } })).structuredContent;
  const args = { sessionId: 'sample', token: card.token, nextStep: 'Next', response: '  observed ABC\n', verdict: 'accurate', criterionResults: [{ id: card.criterionIds[0], result: 'pass', evidenceQuote: 'observed ABC' }], observations: [{ kind: 'terminal-output', text: 'ABC\n' }], conditions: { usedReferences: ['manual'] }, includeState: true };
  const state = (await client.tool('loom_assess_checkpoint', args)).structuredContent.learningState;
  const attempt = state.evidence.Verify.history[0];
  assert.equal(attempt.independent, false);
  assert.equal(attempt.assistance.status, 'unknown');
  assert.equal(attempt.response, args.response);
  assert.equal(attempt.task.prompt, card.prompt);
  assert.equal(attempt.conditions.agreed.allowedReferences[0], 'manual');
  assert.equal(attempt.observations[0].text, 'ABC\n');
  assert.doesNotMatch(await readFile(join(base, '.concept-loom/events/sample.jsonl'), 'utf8'), /PRIVATE-/);
});
test('compact mutation responses avoid returning an unrelated large learner context', async t => {
  const { base } = await fixture(t, { state: { learnerContext: 'x'.repeat(262144) } });
  const client = await clientFor(t, base);
  const saved = await client.tool('loom_save_learning_state', { sessionId: 'sample', nextStep: 'Compact', expectedRevision: 1 });
  assert.ok(JSON.stringify(saved).length < 10000);
  const loaded = (await client.tool('loom_load_learning_state', { sessionId: 'sample' })).structuredContent;
  assert.equal(loaded.state.learnerContext.length, 262144);
});
test('a configured project rejects another session without creating it', async t => {
  const { base } = await fixture(t, { profile: true });
  const client = await clientFor(t, base);
  const other = await client.tool('loom_save_learning_state', { ...basic, sessionId: 'english' });
  assert.equal(other.isError, true);
  assert.match(other.content[0].text, /not allowed/);
  const current = (await client.tool('loom_doctor', { sessionId: 'sample' })).structuredContent;
  assert.equal(current.healthy, true);
});
