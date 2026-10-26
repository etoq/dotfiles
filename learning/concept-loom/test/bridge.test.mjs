import test from "node:test";
import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { mkdtemp } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { createInterface } from "node:readline";

const server = fileURLToPath(new URL("../src/bridge.mjs", import.meta.url));

async function clientFor(t) {
  const cwd = await mkdtemp(join(tmpdir(), "loom-bridge-"));
  const child = spawn(process.execPath, [server], { cwd, stdio: ["pipe", "pipe", "pipe"] });
  const started = new Promise((resolve, reject) => { child.once("spawn", resolve); child.once("error", reject); });
  const requests = new Map();
  const lines = createInterface({ input: child.stdout });
  let nextId = 0;
  let stderr = "";
  child.stderr.on("data", (data) => { stderr += data; });
  lines.on("line", (line) => {
    const message = JSON.parse(line);
    const pending = requests.get(message.id);
    if (pending) { requests.delete(message.id); clearTimeout(pending.timer); pending.resolve(message); }
  });
  child.on("error", (error) => { for (const request of requests.values()) request.reject(error); });
  t.after(() => {
    for (const request of requests.values()) clearTimeout(request.timer);
    lines.close();
    child.stdin.end();
    child.kill();
  });
  await started;
  function request(method, params) {
    const id = ++nextId;
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => reject(new Error(`request ${method} timed out: ${stderr}`)), 5000);
      requests.set(id, { resolve, reject, timer });
      child.stdin.write(`${JSON.stringify({ jsonrpc: "2.0", id, method, params })}\n`);
    });
  }
  const initialized = await request('initialize', { protocolVersion: '2025-06-18', capabilities: {}, clientInfo: { name: 'test', version: '1' } });
  child.stdin.write(`${JSON.stringify({ jsonrpc: '2.0', method: 'notifications/initialized' })}\n`);
  return { request, initialized, tool: async (name, args) => (await request("tools/call", { name, arguments: args })).result };
}

const session = { sessionId: "sample", topic: "Sample", goal: "Test a fresh MCP process", phase: "build", nextStep: "Answer" };
const frame = { sessionId: "sample", prompt: "Choose", choices: [{ key: "a", label: "A" }, { key: "b", label: "B" }], expected: "a", rationale: "PRIVATE-RATIONALE" };

test("stdio assessment can be retried after persistence fails", async (t) => {
  const client = await clientFor(t);
  const framed = await client.tool("loom_frame_checkpoint", frame);
  assert.doesNotMatch(JSON.stringify(framed), /PRIVATE-RATIONALE/);
  const token = framed.structuredContent.token;
  const input = { token, sessionId: "sample", selected: "a", evidenceConcept: "Choice", nextStep: "Continue" };
  const failed = await client.tool("loom_assess_checkpoint", input);
  assert.equal(failed.isError, true);
  assert.doesNotMatch(JSON.stringify(failed), /PRIVATE-RATIONALE/);
  await client.tool("loom_save_learning_state", session);
  const success = await client.tool("loom_assess_checkpoint", input);
  assert.equal(success.structuredContent.outcome, "accurate");
  assert.equal(success.structuredContent.learningState.revision, 2);
  const reused = await client.tool("loom_assess_checkpoint", input);
  assert.equal(reused.structuredContent.replayed, true);
  assert.equal(reused.structuredContent.learningState.revision, 2);
});

test("pipelined state updates preserve revisions and stale writes are rejected", async (t) => {
  const client = await clientFor(t);
  const first = client.tool("loom_save_learning_state", session);
  const second = client.tool("loom_save_learning_state", { ...session, nextStep: "Second", expectedRevision: 1 });
  assert.equal((await first).structuredContent.revision, 1);
  assert.equal((await second).structuredContent.revision, 2);
  const stale = await client.tool("loom_save_learning_state", { ...session, nextStep: "Stale", expectedRevision: 1 });
  assert.equal(stale.isError, true);
  assert.match(stale.content[0].text, /revision conflict/);
});

test("persistence validation errors do not consume a valid answer", async (t) => {
  const client = await clientFor(t);
  await client.tool("loom_save_learning_state", session);
  const token = (await client.tool("loom_frame_checkpoint", frame)).structuredContent.token;
  const input = { token, sessionId: "sample", selected: "a", evidenceConcept: "Choice" };
  assert.equal((await client.tool("loom_assess_checkpoint", { ...input, nextStep: "" })).isError, true);
  const saved = await client.tool("loom_assess_checkpoint", { ...input, nextStep: "Try another case", includeState: true });
  assert.equal(saved.structuredContent.learningState.evidence.Choice.attempts, 1);
});

test("new schema options remain optional and version metadata agrees", async (t) => {
  const client = await clientFor(t);
  assert.equal(client.initialized.result.serverInfo.version, "2.0.0");
  const catalog = (await client.request("tools/list")).result.tools;
  const save = catalog.find((tool) => tool.name === "loom_save_learning_state");
  assert.equal(save.inputSchema.properties.expectedRevision.type, "integer");
  assert.equal(save.inputSchema.required.includes("expectedRevision"), false);
});
