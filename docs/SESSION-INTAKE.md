# Session intake and contextual judgment design

Status: product design plus initial implementation. November 8, 2026.
[Current intake commands](INTAKE.md) implement session-local onboarding, capture
policy, contextual AJF 0.3, observations and explicitly selected Codex import/
extraction. Continuous capture listeners, nightly scheduling and automatic approval
remain design work.

## Paxel reference

Paxel separates local historical analysis from remote-box continuous capture.
Its public uploader discovers host-specific transcript stores, scopes projects,
and describes grouping sessions into work streams before extracting steering and
choices. The remote capture path synchronizes after turns. These are distinct
from interpreting each message as a durable judgment.

The inspected launcher also handles complete-line boundaries, offset/prefix state,
source replacement, remote normalization, and preservation of unrelated hooks.
Its data-handling documentation distinguishes local raw data, excerpts sent for
model analysis, and derived outputs. This audit read public documentation and
script source; it did not install or run Paxel, upload user history, audit the
whole service, or establish rights to copy its implementation.

Sources inspected November 8:
- [Product and workflow](https://paxel.ycombinator.com/)
- [Data-handling detail](https://paxel.ycombinator.com/data-handling)
- [Public launcher](https://paxel.ycombinator.com/upload.sh)

## Three intake units

- Trigger: correction, consequential agent choice/assumption, task completion,
  failure, or review feedback.
- Evidence window: one exchange, several turns, a task loop, or linked sessions.
- Judgment: one independently reviewable candidate, with explicit conditions.

Capture corrections promptly; collect evidence without interrupting every turn.
At task boundaries, extract and deduplicate candidates. Consolidate across sessions
later, preserving all source links. Cross-session generalizations remain candidates.
A task/session identifier groups evidence; it never substitutes for judgment identity.

## One session-local onboarding experience

The proposed onboarding flow presents project scope, capture behavior, manual
review, optional model provider, and optional selected history. It shows changes
before enabling capture/host integration. Defaults: current project, meaningful
human corrections plus consequential agent judgments, task-boundary extraction,
manual admission, no historical ingestion until selected.

Setup must work from the agent session, with a real human confirmation surface.
Agent-generated configuration is a proposal, not policy authorization. Credentials
are entered through local configuration, not pasted into model context. Existing
host hooks are merged without replacement and can be inspected or removed.

Policy separates what to capture, when to extract, what requires review, and what
can execute. A capture failure should not break ordinary agent work. Failure of a
registered protective gate follows its separately reviewed blocking policy.

## History first adapter

Start with Codex history, matching the host used in the playground; reuse the
normalization contract for Claude and Cursor readers later. Do not infer remote
support from local storage discovery.

1. Discover metadata in the selected host's transcript root and preview sources.
2. Filter by explicit project/worktree selection and time range. Distinguish exact
   paths from repo families; forks or equal remotes do not grant cross-project scope.
3. Let the user choose sessions, recent history, all selected history, or none.
4. Parse bounded records locally, preserving speaker, timestamp and source location.
5. Redact known credentials, suppress irrelevant tool/file bodies, and show the
   data boundary before any configured model receives selected excerpts.
6. Normalize into a common event representation and extract contextual candidates.
7. Preview evidence, deduplicate, and send candidates to the ordinary review inbox.

No historical utterance grants present admission or enforcement. Preserve original
attribution separately from today's importer/extractor. Unknown rationale,
alternatives, identity and time remain unknown rather than being invented.
Transcript text is untrusted data, including instructions to change this policy.

Readers need parser versioning, byte/record checkpoints, source fingerprints,
complete-record handling, and explicit handling of truncation, rotation, compaction
and active writes. Do not advance a checkpoint until the bounded result persists.
Deduplicate mirrored/forked histories by source identity and content references;
do not count repeated excerpts as independent evidence. Retain reference mapping
between redacted excerpts and source positions. Quarantine unsupported records
instead of claiming they imported successfully.

Capture scheduling may use turn/task-end hooks, but expensive extraction belongs
in a background queue. Keep collection separate from candidate extraction and from
blocking pre-action assessment. Do not rescan or resummarize all history per turn.
Remote synchronization and a private transcript Git repository are optional future
transport choices, not prerequisites for a local OSS installation.

## AJF next draft

Preserve 0.1/0.2 records and digests. Introduce a new draft for new semantics:

- `context`: goal, situation, known constraints and relevant facts, with evidence
  references. This records the original situation; future applicability still
  belongs in `applicability`.
- `alternatives`: considered options and recorded reasons for rejecting them.
  Missing explanations stay unknown; extraction must not invent private reasoning.
- `expected_outcome`: what the judgment is intended to improve and how it might
  be checked, distinct from a later observed result.
- Outcome observations: append-only records linked to the exact judgment revision,
  source task/usage receipt, observer, time, evidence and uncertainty.

A negative case is first an observation: a particular approach failed in a
particular situation. It can support a candidate judgment about what to avoid,
including conditions and exceptions; one failure does not establish a universal
prohibition. Challenging evidence and counterexamples remain first-class inputs.

Outcomes must distinguish gate behavior, task correctness and repeated-use effect.
One judgment can have many outcomes. Adding an observation does not mutate its
reviewed content, establish causality, auto-admit a replacement, or assert that
retrieved guidance was actually used. Export can bundle linked observations while
keeping content, local authority and observed evidence separately identifiable.

## Implementation sequence and acceptance

1. Session-local onboarding and capture policy preview/configuration.
2. New AJF draft and append-only observations, with historical compatibility tests.
3. Codex history preview/import plus incremental readers and synthetic fixtures.
4. Task-boundary extraction and correction-triggered capture into a review inbox.

Acceptance requires idempotent re-import, safe handling of partial/changed files,
preserved attribution, no imported approval, no accidental scope expansion, no
secret in emitted fixtures, review of selected data transmission, and a clear way
to stop capture. Use synthetic histories first. Measure candidate usefulness,
duplicates, missed corrections, review burden and extraction cost before claiming
benefit over maintained notes.
