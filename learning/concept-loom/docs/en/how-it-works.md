# How ConceptLoom works

ConceptLoom protocol: 2. Server 2.0.0; state schema 3. Requires Node.js 20+ and Python 3.10+, without third-party runtime packages.

## Resume a project

Load the explicit subject session, inspect `loom_status`, its current-stage summary and due reviews, then call `loom_begin_lesson` with the loaded revision and a unique operation ID. It creates a distinct sitting at the saved next step. Imported history is context, not a new diagnosis or mastery demonstration.

The optional project profile controls subject isolation, notebook roots, exact exports, environment and review policy. The Linux RE profile preserves Russian coaching, an Arch host, learner-run Debian experiments, existing Obsidian links and the original materials snapshot. The server never executes VM commands or changes networking.

## Checkpoints and evidence

Frame a checkpoint with its session and concept, public task, rubric version and private key/criteria. Present only the public card before collecting the response. Formats are choice, free recall, prediction, debugging, transfer and verification. They represent different evidence dimensions, not a universal score.

Open assessment requires every public criterion ID in `criterionResults`. A passing result needs an `evidenceQuote` occurring literally in the supplied answer or observations. The code checks completeness and consistency; semantic judgment remains a recorded coach evaluation. It does not become independent truth because an MCP server saved it.

Report assistance explicitly as unknown, none, hint, explanation or solution. Omission stays unknown. Legacy explicit `hintUsed=false` means reported independence; `true` means a hint. Permitted reference use is separate. Preserve exact response text and distinguish prediction, terminal output, learner explanation and coach observation. Keep agreed task conditions separate from reported actual conditions.

Private keys, criteria and rationale remain in expiring in-memory cards and are excluded from durable records. Public task identity, exact answer, evaluator/criterion results, assistance and observations are saved. `confidenceSignal` is a discussion heuristic, not measured calibration. One answer never automatically adds a general secured connection. Stable concept IDs retain history across display-name changes.

## Save and retry

Persistence precedes the next explanation. Use an assessment for a checkpoint; for another response save exact `learnerResponse` or observations with the resume action. Configured projections already record these events, so do not duplicate them manually.

Omitted fields are preserved. `loom_patch_learning_state` requires the loaded revision and a stable operation ID. `evidenceUpdates` changes selected records; full evidence replacement requires explicit revision-checked maintenance intent and a reason. A patch cannot overwrite attempt history.

Use the same operation ID and input after an uncertain outcome. Checkpoints derive their key automatically, including across MCP restarts. `loom_status` can check an operation ID. A new learner attempt requires a new key. Mutation replies are compact; use `includeState=true` or load state when the full ledger is needed.

Inspect `commitInfo`. Once an event is durable, a failed snapshot or Markdown projection is pending work, not a rejected learner response. Retry projections with `loom_sync_learning_records`, without another assessment.

## Approval and reviews

`loom_approve_route` records the route version, actual consent quote and user-message reference supplied by the client. A route change invalidates the prior approval. `legacy-context` retains an imported project's route context without fabricating a new approval.

Review intervals and minimum real delay are configurable practical heuristics. Growth requires reported independence, a due date, earlier independent evidence, sufficient actual elapsed time and a different lesson ID. An immediate answer crossing a due date is not delayed retrieval. Due concepts are suggestions for useful review, not an obligation to retest every note.

## Persistence and recovery

An OS advisory lock protects the complete read/revision-check/write transaction across processes. A Python standard-library helper holds the kernel lock until stdin closes, including after parent death. Set `CONCEPT_LOOM_PYTHON` if Python is not on the default PATH.

The hash-chained event journal is authoritative from its explicit imported baseline onward. JSON state is a recoverable snapshot; checksummed previous snapshots are retained. A torn trailing fragment is preserved before repair. Corruption inside the chain blocks that session's writes and is diagnosed; healthy neighboring sessions remain readable. Unknown future formats are not overwritten. Recovery does not silently discard recent history in favor of an older backup.

After commit, configured notebook and current-stage projections update under the same lock. Event markers prevent duplicates; old useful text, the original TOC and simple note properties remain. Only exact configured real export files can be written outside the workspace. Denied paths are reported without permission bypasses.

`loom_status` and `loom_doctor` are read-only. Preview migration/recovery before adding `--apply`:

```bash
node scripts/doctor.mjs --workspace /path/to/project --session subject
node scripts/migrate.mjs --workspace /path/to/project --session subject
node scripts/migrate.mjs --workspace /path/to/project --session subject --apply
node scripts/recover.mjs --workspace /path/to/project --session subject
```

Back up data and stop old project-scoped writers before migration. The stdio entry point stays unchanged. Restart clients to discover version-2 tools; never run a version-1 writer against migrated schema-3 data. See [architecture](../architecture.md) for invariants and limitations.
