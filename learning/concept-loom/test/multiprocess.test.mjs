import test from 'node:test';
import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { createInterface } from 'node:readline';
import { fixture, basic, answer } from '../test-support/fixtures.mjs';
import { loadLearningState, recordCheckpointAssessment, saveLearningState } from '../src/progress.mjs';
import { fileURLToPath } from 'node:url';
const progress = new URL('../src/progress.mjs', import.meta.url).href;
const storage = new URL('../src/storage.mjs', import.meta.url).href;
async function worker(t, base, code) {
  const child = spawn(process.execPath, ['--input-type=module', '-e', code], { cwd: base, stdio: ['pipe', 'pipe', 'pipe'] });
  let errors = ''; child.stderr.on('data', chunk => { errors += chunk; });
  const exited = new Promise(resolve => child.once('close', resolve));
  const lines = createInterface({ input: child.stdout });
  const queue = [], waiting = [];
  lines.on('line', value => { if (waiting.length) waiting.shift()(value); else queue.push(value); });
  child.stdin.on('error', () => {});
  await new Promise((resolve, reject) => { child.once('spawn', resolve); child.once('error', reject); });
  const next = () => queue.length ? Promise.resolve(queue.shift()) : new Promise((resolve, reject) => {
    const timeout = setTimeout(() => reject(new Error(`worker timeout: ${errors}`)), 20000);
    waiting.push(value => { clearTimeout(timeout); resolve(value); });
  });
  t.after(async () => { if (child.exitCode === null && child.signalCode === null) child.kill(); await exited; lines.close(); });
  return { child, exited, next };
}
test('six processes preserve all accepted attempts without revision guards', async t => {
  const { base } = await fixture(t, { state: { learnerContext: 'x'.repeat(32768) } });
  const workers = await Promise.all(Array.from({ length: 6 }, async (_, index) => {
    const code = `const {recordCheckpointAssessment}=await import(${JSON.stringify(progress)});console.log('READY');process.stdin.once('data',async()=>{try{const state=await recordCheckpointAssessment(process.cwd(),{sessionId:'sample',evidenceConcept:'Shared',hintUsed:false,operationId:'worker-${index}',nextStep:'Continue'},${JSON.stringify({ ...answer, response: `Response ${index}` })});console.log(JSON.stringify({revision:state.revision}));process.stdin.destroy();}catch(e){console.log(JSON.stringify({error:e.message}));process.stdin.destroy();}});`;
    const instance = await worker(t, base, code); assert.equal(await instance.next(), 'READY'); return instance;
  }));
  workers.forEach(instance => instance.child.stdin.end('go'));
  const replies = await Promise.all(workers.map(instance => instance.next()));
  assert.ok(replies.every(line => !JSON.parse(line).error), replies.join('\n'));
  const { state } = await loadLearningState(base, { sessionId: 'sample' });
  assert.equal(state.revision, 7); assert.equal(state.evidence.Shared.attempts, 6);
  assert.equal(new Set(state.evidence.Shared.history.map(item => item.response)).size, 6);
});
test('cross-process expectedRevision is checked under the same OS lock as the write', async t => {
  const { base } = await fixture(t);
  const workers = await Promise.all(Array.from({ length: 6 }, async (_, index) => {
    const code = `const {recordCheckpointAssessment}=await import(${JSON.stringify(progress)});console.log('READY');process.stdin.once('data',async()=>{try{await recordCheckpointAssessment(process.cwd(),{sessionId:'sample',evidenceConcept:'Shared',hintUsed:false,operationId:'cas-${index}',expectedRevision:1,nextStep:'Continue'},${JSON.stringify(answer)});console.log('ACCEPTED');}catch(e){console.log(e.message.includes('revision conflict')?'CONFLICT':e.message);}process.stdin.destroy();});`;
    const instance = await worker(t, base, code); assert.equal(await instance.next(), 'READY'); return instance;
  }));
  workers.forEach(instance => instance.child.stdin.end('go'));
  const replies = await Promise.all(workers.map(instance => instance.next()));
  assert.equal(replies.filter(value => value === 'ACCEPTED').length, 1);
  assert.equal(replies.filter(value => value === 'CONFLICT').length, 5);
  assert.equal((await loadLearningState(base, { sessionId: 'sample' })).state.evidence.Shared.attempts, 1);
});
test('an OS lock is released when its Node owner crashes', { skip: process.platform === 'win32' }, async t => {
  const { base } = await fixture(t);
  const instance = await worker(t, base, `const {withSessionLock}=await import(${JSON.stringify(storage)});await withSessionLock(process.cwd(),'sample',async()=>{console.log('LOCKED');await new Promise(()=>{});});`);
  assert.equal(await instance.next(), 'LOCKED');
  instance.child.kill('SIGKILL'); await instance.exited;
  const state = await saveLearningState(base, { ...basic, nextStep: 'Lock recovered' });
  assert.equal(state.revision, 2);
});
test('a crash after event fsync preserves the assessment and its idempotency key', async t => {
  const { base } = await fixture(t);
  const args = { sessionId: 'sample', evidenceConcept: 'Crash', hintUsed: false, operationId: 'crash-answer', nextStep: 'Continue' };
  const instance = await worker(t, base, `const {recordCheckpointAssessment}=await import(${JSON.stringify(progress)});await recordCheckpointAssessment(process.cwd(),${JSON.stringify(args)},${JSON.stringify(answer)},{fault(point){if(point==='after-journal')process.exit(19)}});`);
  assert.equal(await instance.exited, 19);
  const { state } = await loadLearningState(base, { sessionId: 'sample' });
  assert.equal(state.evidence.Crash.attempts, 1);
  const replay = await recordCheckpointAssessment(base, args, answer);
  assert.equal(replay.commitInfo.replayed, true);
  assert.equal(replay.evidence.Crash.attempts, 1);
});
