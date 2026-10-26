#!/usr/bin/env node
import { doctor } from '../src/diagnostics.mjs';
const args = process.argv.slice(2);
const value = flag => { const index = args.indexOf(flag); return index < 0 ? undefined : args[index + 1]; };
const result = await doctor(value('--workspace') ?? process.cwd(), { sessionId: value('--session') });
process.stdout.write(`${JSON.stringify(result, null, 2)}\n`);
process.exitCode = result.healthy ? 0 : 1;
