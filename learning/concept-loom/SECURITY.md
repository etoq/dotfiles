# Security policy

## Reporting a vulnerability

Please report security issues privately through GitHub Security Advisories instead of opening a public issue. Include reproduction steps, affected files, and the expected impact when possible.

## Local data model

Concept Loom runs as a local stdio MCP server. It does not open a network listener. Learning notes and resumable state are written inside the selected learning workspace.

The connected AI client may still read local source materials or use network tools according to that client's permissions. Review the client's permission prompts and avoid placing credentials or unrelated private files in a learning workspace.

## Before publishing a fork

- Do not commit `.env`, `.mcp.json`, `opencode.json`, DeepSeek Harness profile configuration, credentials, private keys, books, courses, or generated learning state.
- Inspect `git diff --cached` before every push.
- If a secret was ever committed, revoke it first; removing it in a later commit is not sufficient.


## Version 2 local boundaries

State storage rejects symlinks. Notebooks are confined to real configured notebook roots. A projection outside the workspace requires an exact canonical export file in the local project profile. A local owner can edit that profile and the underlying data; journal hashes detect corruption, not forgery by that owner. These policies supplement host permissions and do not authorize bypassing a denied path.

Python's OS advisory lock coordinates all cooperating server processes and releases after a crash. Do not run a version-1 writer against a migrated version-3 state. Stop old project-scoped MCP processes during the upgrade, then reconnect clients to discover the version-2 tools.

Keep event journals and backups private like the original learner state. Private checkpoint keys and criteria remain in memory and are excluded from generated records. A model-provided verdict and a user-consent reference retain their client-reported provenance; the server does not certify their truth.
