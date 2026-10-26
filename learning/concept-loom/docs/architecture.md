# Architecture

ConceptLoom protocol: 2. Local server version 2.0.0, state schema 3, journal schema 1, project profile schema 1. Runtime: Node.js 20+ and Python 3.10+; no third-party runtime packages.

## Boundaries

The stdio server provides deterministic records and checks. The AI client supplies explanations, a grading key or rubric, actual user consent and the learner's exact response. The server does not run laboratory commands, change networking, certify mastery or independently establish the truth of a model verdict.

`tool-catalog.mjs` supplies schemas both for discovery and runtime validation. `bridge.mjs` handles initialized JSON-RPC requests, notifications and compact results. Input is processed in order. Unknown tools and schema violations are protocol errors; execution errors are tool results. Initialization uses the supported 2025-06-18 MCP version. See the [MCP lifecycle](https://modelcontextprotocol.io/specification/2025-06-18/basic/lifecycle) and [JSON-RPC notifications](https://www.jsonrpc.org/specification#notification).

## Storage and crash recovery

`storage.mjs` serializes each session within the process and acquires an OS advisory lock through `lock-holder.py` before reading, checking a revision or writing. On POSIX the helper uses `fcntl.flock`; Windows uses `msvcrt.locking`. It holds the lock until its parent closes stdin. OS locks are released after process death; there are no stale-PID lock-stealing heuristics. Python must be available on PATH, or configured with `CONCEPT_LOOM_PYTHON`.

A mutation validates its complete proposed state, appends and fsyncs a hash-chained event, then writes the snapshot atomically. Only after the event is durable does the server consume a checkpoint token. A snapshot/projection failure after commit returns an explicit pending diagnostic rather than pretending the event was rejected. A retry with the same operation ID does not repeat the attempt.

Each event records a UUID, operation ID, input digest, revision, provenance, timestamp, changed fields and evidence updates. A new history entry is appended in the event instead of duplicating the entire history. Event hashes detect accidental alteration; they are not signatures or protection against a malicious local owner rewriting the whole chain.

The authoritative history is `.concept-loom/events/<session>.jsonl`. `.concept-loom/sessions/<session>.json` is a recoverable snapshot. A complete old valid snapshot is retained in a checksummed backup before replacement. A malformed snapshot can be reconstructed from the journal; an unknown future schema is never overwritten. A torn final journal fragment is copied into `recovery/` before repair. Corruption inside the chain blocks writes to that session and is reported. Other healthy sessions remain available. Recovery never silently substitutes an older backup for newer history.

Schema-1/2 import writes one explicit historical baseline at its original revision. It preserves the ledger, route, errors, assistance records and exact resume point. It adds concept identities and format provenance, without fabricating older event history or learner demonstrations. Existing route context is labelled `legacy-context`, not newly approved.

## Project policy and paths

The optional `.concept-loom/project.json` specifies allowed subject sessions, notebook roots, exact export files, review policy, environment and projections. State storage rejects symlinks in all components. Notebook paths are checked against real allowed roots; exports must be exact explicitly allowed canonical files. The Linux RE profile permits only its progress notebook and the existing Obsidian Current_Stage target. It does not grant arbitrary access to the vault. Host permissions still apply; denied writes are reported without changing permissions.

`materials/` stays the original transfer snapshot. `notes/` can remain the user's existing Obsidian links. No materials synchronization or VM action is performed by the server.

## Checkpoint evidence

Private grading keys, private criteria and rationale live only in expiring in-memory cards. The public task records its ID, prompt, variant, format, conditions and rubric version. Successful persistence stores only public task data, exact learner text, selected keys, criterion IDs/results with evidence quotes, reported actual conditions, observations and the coach's verdict. Private grading material is excluded from durable events and Markdown.

Open grading requires all criterion IDs; a passing criterion needs a quotation actually present in the supplied response or observations. This is a consistency check on a coach-provided evaluation, not an independent semantic judge. Assistance is `unknown`, `none`, `hint`, `explanation` or `solution`; omission stays unknown. Permitted references are separate. One successful choice never adds a general secured connection. Recognition, recall, application, transfer and verification remain distinct. Legacy counters and flags are retained with their provenance, without retroactive regrading.

Confidence is stored as supplied. A `confidenceSignal` is a heuristic discussion cue; there is no single-answer `well-calibrated` claim or universal mastery percentage.

Stable concept IDs separate display names from evidence keys. Rename keeps prior aliases and attempts. Full evidence replacement is an explicit revision-checked maintenance operation; routine partial saves preserve omitted fields and use `evidenceUpdates`.

## Review and route policy

Review intervals and the minimum real delay are project heuristics. Interval growth requires explicit independence, a due date, earlier independent evidence, enough elapsed time and a different lesson ID. Crossing a date inside one sitting does not count as delayed retrieval. Due reviews are scheduling suggestions, not a new mandatory workload.

`loom_begin_lesson` creates a distinct sitting without advancing knowledge. Route changes invalidate their previous version's approval. `loom_approve_route` records the actual quote and message reference supplied by the client; it cannot prove that the client represented user consent truthfully. A configured project can continue its labelled historical route while requiring new consent for any change.

## Readable projections

After commit, the same session lock protects repeatable notebook and Current_Stage generation. Invisible event markers prevent duplicate entries. A compact managed Current_Stage block names the source revision and exact next step; its old useful text is retained as historical context, with one original TOC and only the user's existing properties. The notebook receives learner records automatically. The learner does not fill another diary or template.

Projection errors retain the committed event and identify the affected path. `loom_sync_learning_records` retries them without another attempt or revision. Manual annotations outside generated blocks are preserved; edited generated entries are diagnosed rather than silently rewritten.

`loom_status` reports version, project and resume health; `loom_doctor` checks journal/snapshot/backup integrity, runtime, instruction compatibility and projection drift. Both are read-only. Mutation results are compact by default; `includeState=true` explicitly requests a full state.
