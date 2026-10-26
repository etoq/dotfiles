import { spawn } from 'node:child_process';
import { createInterface } from 'node:readline';
import { fileURLToPath } from 'node:url';
export const server = fileURLToPath(new URL('../src/bridge.mjs', import.meta.url));
export async function clientFor(t, cwd) {
  const child = spawn(process.execPath, [server], { cwd, stdio: ['pipe', 'pipe', 'pipe'] });
  const pending = new Map();
  let serial = 0, errors = '';
  const close = new Promise(resolve => child.once('close', resolve));
  child.stderr.on('data', data => { errors += data; });
  child.stdin.on('error', error => { for (const request of pending.values()) request.reject(error); });
  const lines = createInterface({ input: child.stdout });
  lines.on('line', line => {
    const value = JSON.parse(line), request = pending.get(value.id);
    if (request) { clearTimeout(request.timer); pending.delete(value.id); request.resolve(value); }
  });
  await new Promise((resolve, reject) => { child.once('spawn', resolve); child.once('error', reject); });
  let stopped = false;
  async function stop() {
    if (stopped) return; stopped = true;
    for (const request of pending.values()) clearTimeout(request.timer);
    if (!child.stdin.destroyed) child.stdin.end();
    const timeout = setTimeout(() => child.kill(), 5000);
    await close; clearTimeout(timeout); lines.close();
    if (child.exitCode !== 0) throw new Error(`MCP exited ${child.exitCode}: ${errors}`);
  }
  t.after(stop);
  function request(method, params) {
    const id = ++serial;
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => { pending.delete(id); reject(new Error(`${method} timed out: ${errors}`)); }, 15000);
      pending.set(id, { resolve, reject, timer });
      child.stdin.write(`${JSON.stringify({ jsonrpc: '2.0', id, method, params })}\n`);
    });
  }
  const initialized = await request('initialize', { protocolVersion: '2025-06-18', capabilities: {}, clientInfo: { name: 'test-v2', version: '1' } });
  child.stdin.write(`${JSON.stringify({ jsonrpc: '2.0', method: 'notifications/initialized' })}\n`);
  return { initialized, request, stop, tool: async (name, args) => {
    const response = await request('tools/call', { name, arguments: args });
    if (response.error) throw new Error(`protocol error ${response.error.code}: ${response.error.message}`);
    return response.result;
  } };
}
