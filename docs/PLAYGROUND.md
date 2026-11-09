# Playground implementation and verification

On November 8, 2026, the playground exercised three flows:

- Capture human corrections, review them manually, reuse them in applicable coding
  tasks, and invalidate reuse through withdrawal or revision.
- Block a real coding edit with a reviewed pre-tool binding, then approve a revised
  one-file exception and observe the edit pass. Richard completed this manually.
- Assess a synthetic test report before writing. TypeSafe/Jev rejected “All tests
  passed” when no tests ran and released “Tests were not run.” Richard completed
  both cases manually; these are integration results, not an accuracy benchmark.

## Implemented

Concise CLI output, compact agent projections, bold brand colors, AJF 0.2 with
legacy compatibility, capture sessions and corrections, immutable revisions,
manual admission, dependencies and fresh receipts, deterministic assertion
conflicts, optional model conflict assessment, paused reuse, runtime bindings,
and synchronous pre-tool checks.

The playground review displays proposed enforcement and combines approval and
binding in one transaction. Editing creates another candidate and returns to
review. This UI edits statement, rationale and scope; condition/limit editing
remains pending. Core CLI commands remain separate primitives. Pending revisions
preserve current approval; admission of replacements invalidates old binding use.

Model assessment is the general capability. TypeSafe is the first working adapter,
with a configurable model name. Other providers are not yet implemented. BYOK is
optional and explicitly loaded. Provider failure or uncertainty never grants
approval or silently authorizes an action.

## Evidence

[Eleven live Codex scenarios](verification/live-codex-hooks-2026-11-08.json)
cover positive controls, conflicts, withdrawal, revisions, rebinds, generated-file
blocking, and model-assessment denial/release. Every scenario requires a real hook
receipt and the expected filesystem result.

[Claude Code retest](verification/live-claude-hook-2026-11-08.json) records a real
blocked write after login renewal. The full lifecycle sequence was tested in Codex.
Failed login and the initial project-discovery-only trial were not counted as
successful interception.

## Remaining

The harness supplies Codex hooks via invocation-local configuration. Ordinary
installation, project trust/discovery and broad host coverage remain separate.
The twelve-host map is research, not twelve shipped adapters. Shell and unhandled
routes are conservatively denied, not semantically parsed. Complete new-file
content can be assessed; partial edits still require review.

These synthetic integration/usability results do not establish better task quality
or lower total cost than maintained memory notes. Benchmark capture, matching,
governance and enforcement separately. No production or global host configuration
was changed.
