'use strict';
// Per-dictation metadata fallback only. No polling, screenshots or text reads.
exports.active = function (original) {
  try {
    const path = require('node:path');
    const script = path.join(require('node:os').homedir(), '.local/bin/wispr-context');
    const raw = require('node:child_process').execFileSync(script, ['--json'], {
      encoding: 'utf8', timeout: 1800, maxBuffer: 16384, stdio: ['ignore', 'pipe', 'ignore']
    });
    const info = JSON.parse(raw);
    if (!info.bundleId) return original;
    delete info.windowId;
    return {...original, ...info, url: info.url || (original && original.url) || ""};
  } catch (_) { return original; }
};
