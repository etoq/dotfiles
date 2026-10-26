#!/usr/bin/env node
import readline from 'node:readline';
import { composeCheckpoint, assessCheckpoint, consumeCheckpoint, checkpointOperationId } from './checkpoints.mjs';
import { beginNotebook, addNotebookEntry } from './notebook.mjs';
import { prepareMermaid, prepareTextDiagram } from './diagrams.mjs';
import { approveRoute, assertRouteApproved, beginLesson, compactState, findCompletedOperation, listDueReviews, loadLearningState, patchLearningState, recordCheckpointAssessment, renameConcept, saveLearningState, syncLearningRecords } from './progress.mjs';
import { projectConfig } from './paths.mjs';
import { doctor, status } from './diagnostics.mjs';
import { toolCatalog } from './tool-catalog.mjs';
import { hash, VERSION, validateSchema } from './validation.mjs';

const workspace = process.cwd();
const protocolVersion = '2025-06-18';
let initialized = false, ready = false;
const catalog = new Map(toolCatalog.map(tool => [tool.name, tool]));
function textResult(value) { return { content: [{ type: 'text', text: JSON.stringify(value, null, 2) }], structuredContent: value }; }
function stateResult(state, includeState) { return textResult(includeState ? state : compactState(state)); }
function inputDigest(args) { return hash(Object.fromEntries(Object.entries(args).filter(([key]) => !['expectedRevision', 'includeState', 'operationId'].includes(key)))); }
async function invoke(name, args) {
  switch (name) {
    case 'loom_frame_checkpoint': {
      const config = projectConfig(workspace);
      if (config.requireBoundCheckpoints && !args.sessionId) throw new Error('this project requires a bound sessionId for checkpoints');
      if (args.sessionId && config.requireBoundCheckpoints) {
        const { state } = await loadLearningState(workspace, { sessionId: args.sessionId });
        assertRouteApproved(workspace, state);
        if (!args.conceptId && !args.evidenceConcept) throw new Error('this project requires conceptId or evidenceConcept when framing');
      }
      return textResult(composeCheckpoint({ ...args, conditions: args.conditions ?? (config.environment ? { environment: config.environment, provenance: 'project-profile; not a live VM observation' } : {}) }));
    }
    case 'loom_assess_checkpoint': {
      const normalized = { ...args, operationId: args.operationId ?? checkpointOperationId(args.token) };
      const completed = await findCompletedOperation(workspace, args.sessionId, normalized.operationId);
      if (completed) {
        if (completed.event.inputDigest !== inputDigest(normalized)) throw new Error('operationId was already used with different input');
        const attempt = Object.values(completed.event.evidenceUpdates ?? {}).flatMap(update => update.historyAppend ?? [])[0];
        const projections = await syncLearningRecords(workspace, args);
        return textResult({ outcome: attempt?.outcome, attemptId: attempt?.attemptId, conceptId: attempt?.conceptId, replayed: true, operationId: normalized.operationId,
          learningState: args.includeState ? completed.state : compactState(completed.state), projections });
      }
      const assessment = assessCheckpoint(args, { consume: false });
      const state = await recordCheckpointAssessment(workspace, normalized, assessment);
      consumeCheckpoint(args.token);
      return textResult({ ...assessment, attemptId: state.lastCheckpoint.attemptId, conceptId: state.lastCheckpoint.conceptId, independent: state.lastCheckpoint.independent,
        assistance: state.lastCheckpoint.assistance, delayedReview: state.lastCheckpoint.delayedReview, operationId: normalized.operationId,
        learningState: args.includeState ? state : compactState(state) });
    }
    case 'loom_save_learning_state': return stateResult(await saveLearningState(workspace, args), args.includeState);
    case 'loom_patch_learning_state': return stateResult(await patchLearningState(workspace, args), args.includeState);
    case 'loom_approve_route': return stateResult(await approveRoute(workspace, args), false);
    case 'loom_begin_lesson': return stateResult(await beginLesson(workspace, args), false);
    case 'loom_rename_concept': return stateResult(await renameConcept(workspace, args), false);
    case 'loom_load_learning_state': return textResult(await loadLearningState(workspace, args));
    case 'loom_list_due_reviews': return textResult(await listDueReviews(workspace, args));
    case 'loom_status': return textResult(await status(workspace, args));
    case 'loom_doctor': return textResult(await doctor(workspace, args));
    case 'loom_sync_learning_records': return textResult(await syncLearningRecords(workspace, args));
    case 'loom_start_notebook': return textResult({ path: await beginNotebook(workspace, args) });
    case 'loom_add_note': return textResult({ path: await addNotebookEntry(workspace, args) });
    case 'loom_show_relation_map': return textResult(prepareMermaid(args));
    case 'loom_show_text_diagram': return textResult(prepareTextDiagram(args));
    default: throw new Error(`unknown tool: ${name}`);
  }
}
function failure(id, code, message) { return { jsonrpc: '2.0', id, error: { code, message } }; }
function success(id, result) { return { jsonrpc: '2.0', id, result }; }
async function route(message) {
  const { id, method, params = {} } = message;
  // Notifications never execute a request handler and never receive a response.
  if (!Object.hasOwn(message, 'id')) {
    if (method === 'notifications/initialized' && initialized) ready = true;
    return null;
  }
  if (method === 'ping') return success(id, {});
  if (params === null || typeof params !== 'object' || Array.isArray(params)) return failure(id, -32602, 'params must be an object');
  if (method === 'initialize') {
    if (initialized) return failure(id, -32600, 'server is already initialized');
    if (typeof params.protocolVersion !== 'string' || !params.capabilities || typeof params.capabilities !== 'object' || Array.isArray(params.capabilities) || typeof params.clientInfo?.name !== 'string' || typeof params.clientInfo?.version !== 'string') return failure(id, -32602, 'initialize requires protocolVersion, capabilities and clientInfo');
    initialized = true;
    return success(id, { protocolVersion, capabilities: { tools: { listChanged: false } }, serverInfo: { name: 'concept-loom', version: VERSION },
      instructions: 'ConceptLoom protocol: 2. Restore the exact next step. Never reveal checkpoint answers before the learner responds. Begin each resumed lesson with a distinct lesson ID. Explicitly report help; omitted assistance is unknown. Open grading needs evidence-backed criterionResults. Event records and configured projections are automatic; inspect commitInfo and doctor. New routes need real consent. No VM commands are run by this server.' });
  }
  if (!ready) return failure(id, -32002, 'server is not initialized; complete initialize and notifications/initialized first');
  if (method === 'tools/list') return success(id, { tools: toolCatalog });
  if (method === 'tools/call') {
    const tool = catalog.get(params.name);
    if (!tool) return failure(id, -32602, 'unknown tool name');
    const args = params.arguments ?? {};
    try { validateSchema(args, tool.inputSchema); } catch (error) { return failure(id, -32602, error.message); }
    try { return success(id, await invoke(params.name, args)); }
    catch (error) { return success(id, { isError: true, content: [{ type: 'text', text: error instanceof Error ? error.message : String(error) }] }); }
  }
  return failure(id, -32601, `method not found: ${method}`);
}
async function lineReceived(line) {
  if (!line.trim()) return;
  if (Buffer.byteLength(line) > 8 * 1024 * 1024) return process.stdout.write(`${JSON.stringify(failure(null, -32600, 'request exceeds 8 MiB; store large artifacts and pass references'))}\n`);
  let message;
  try { message = JSON.parse(line); } catch { return process.stdout.write(`${JSON.stringify(failure(null, -32700, 'parse error'))}\n`); }
  if (!message || typeof message !== 'object' || Array.isArray(message) || message.jsonrpc !== '2.0' || typeof message.method !== 'string'
    || (Object.hasOwn(message, 'id') && typeof message.id !== 'string' && !Number.isSafeInteger(message.id))) {
    return process.stdout.write(`${JSON.stringify(failure(null, -32600, 'invalid request'))}\n`);
  }
  try { const response = await route(message); if (response) process.stdout.write(`${JSON.stringify(response)}\n`); }
  catch (error) { if (Object.hasOwn(message, 'id')) process.stdout.write(`${JSON.stringify(failure(message.id, -32603, String(error)))}\n`); }
}
const input = readline.createInterface({ input: process.stdin, crlfDelay: Infinity });
let pending = Promise.resolve();
input.on('line', line => { pending = pending.then(() => lineReceived(line)); });
