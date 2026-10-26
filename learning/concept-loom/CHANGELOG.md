# Changelog

All notable changes to Concept Loom are documented here.

## 2.0.0 — 2026-10-26

### Changed

- State schema 3 and an authoritative event journal, with one provenance-labelled import baseline for older sessions.
- Runtime now includes Python 3.10+ for OS advisory locks; no third-party runtime packages.
- Mutations return compact receipts by default; `includeState=true` returns the full state.
- Open assessments require complete criterion results with quotations from actual supplied evidence.
- Omitted assistance is unknown; confidence labels no longer claim single-answer calibration; one answer never grants general mastery.

### Added

- Cross-process locking, revision checks under the lock, durable operation IDs and retry across MCP restart.
- Snapshot backups, hash-chain validation, torn-tail preservation and journal-based recovery.
- Explicit project profile, canonical path boundaries and exact-file Obsidian exports.
- Automatic idempotent notebook/current-stage projections with visible pending-write diagnostics.
- Status, doctor, partial updates, versioned route approval, distinct lessons, stable concept rename and projection retry tools.
- Verification checkpoints, public task/conditions, separated observations and evaluator provenance.
- Regression coverage for real concurrent processes, crashes, recovery, paths, unknown help, review-time boundaries, migrations and protocol behavior.

### Fixed

- Remaining cross-process lost updates and subsecond answers counted as delayed reviews.
- Symlink escapes, missing-concept history loss, invalid counter types, future schema downgrades and corrupt neighbors hiding valid reviews.
- JSON-RPC notification responses, invalid IDs and drift between advertised schemas and validation.

## 1.2.0 — 2026-10-26

### Fixed

- Partial saves preserve omitted route, gaps, secured connections, notebook and resume context.
- Validation or persistence errors no longer consume checkpoint tokens; successful assessments remain single-use.
- Per-session update queues and unique temporary files prevent same-process concurrent write collisions and lost attempts.
- Correct hinted answers no longer independently secure connections or pass transfer checks.
- Immediate repetitions no longer lengthen delayed-review intervals.
- Open responses preserve the supplied text, and reserved gap keys cannot masquerade as normal choices.

### Added

- Optional session binding for checkpoints and optional revision checks for state updates.
- Attempt history, independent-success counters and successful due-review counts without private grading material.
- MCP stdio regression coverage for retry, revision, ordering and compatible discovery.

## 1.1.0 — 2026-10-06

### Added

- DeepSeek Harness adapter with native `.dsh/skills` discovery.
- Generated Harness MCP patch for Web and headless profiles.
- Installer coverage for normal and `--skip-mcp` DeepSeek Harness setup.
- Open-response checkpoints for free recall, prediction, debugging, and transfer.
- Confidence calibration and per-concept evidence for recognition, recall, application, and transfer.
- Guided, practice, review, and challenge session modes.
- Delayed review scheduling and due-review discovery across sessions.
- Explicit route extensions for prerequisites discovered during Build.

## 1.0.0 — 2026-10-01

First public release.

### Included

- Portable Concept Coach skill for Codex, Claude Code, and OpenCode.
- Locate → Weave → Build learning workflow.
- Concealed-answer checkpoints with explicit knowledge-gap handling.
- Persistent Markdown notebooks and resumable learning state.
- Save-before-continue behavior after learner responses.
- Terminal-readable text and Mermaid diagrams without image renderers.
- Learning workflows for both supplied source materials and foundational topics.
- Safe workspace installer and bilingual English/Russian documentation.
