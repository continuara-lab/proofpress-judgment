# Project history and capture settings

Onboarding explains capture policy as “what your agent may save as a proposed
judgment,” lists the enabled categories and links to `proofpress configure`.
The defaults cover your judgments, corrections, consequential agent choices and
task-end lessons. Capture is skill guidance, not a background listener.

Import by project:

```sh
proofpress history project --project /path/to/project --days 7
proofpress consolidate --scope coding --model-assessment --all
proofpress review
```

Import asks before storing redacted excerpts locally; errors are displayed with
source keys and reasons. Extraction explicitly sends excerpts to Codex and follows
allowed capture triggers. Each candidate records its trigger and policy digest;
it remains a hypothesis requiring human scope and source review. `--all` processes
the current pending snapshot. Omit it to process a single batch. No scheduler or
automatic approval is installed. Redaction is not complete privacy protection.

The per-session commands below remain advanced tools. [Local trial](LOCAL-ALPHA.md).

# Onboarding, session intake and observations

This iteration implements the first local intake path. It uses existing manual
admission and runtime authority; history never imports an approval.

## Enable from an agent session

```sh
proofpress onboard --project . --agents codex
```

In an interactive terminal, this previews the project, capture choices and manual
review, then asks whether to enable. Noninteractive agent calls return a preview
without modifying files. A human can explicitly confirm the same configuration:

```sh
proofpress onboard --project . --agents codex --owner human:me --confirm
proofpress capture-policy
```

Onboarding installs project-local skill entry points and records default capture
policy: human judgments, human corrections, consequential agent judgments and task boundaries;
manual extraction; selected history only; manual review. These are instructions
for participating agents, not a new background observer or automatic host hook.
No OS scheduler is installed. Existing different skill files are preserved rather
than silently overwritten; an upgrade may require inspecting/moving those files.

`capture-policy --from policy.json --confirm` records a human policy change as a
ledger event. `review: manual` remains required. History can be disabled with `none`.
Policy options can be changed directly in the session CLI without editing JSON:

```sh
proofpress capture-policy --triggers human_correction task_end --confirm
proofpress capture-policy --triggers none --history none --confirm
```

Onboarding accepts the same trigger/history/extraction options. Trigger guidance
can be disabled; explicit capture commands are still available. The policy never enables automatic admission or modifies runtime bindings.

## Select Codex history

```sh
proofpress history scan --project . --root ~/.codex/sessions --days 7
proofpress history preview --project . --file /absolute/selected-session.jsonl
proofpress history import --project . --file /absolute/selected-session.jsonl
```

Scan reads metadata and filters exact project path plus file modification time.
It is capped at 5,000 candidate files. Preview performs no import or network call.
Import accepts regular JSONL files up to 32 MiB; it reads only supported user and
assistant response messages, not tool outputs, hidden reasoning or attachments.
`event_msg` mirrors are skipped to avoid double-counting.

Imported excerpts are stored locally in the gitignored journal, with source roles,
timestamps and byte-range references. Known credential formats are redacted;
this is not a guarantee that arbitrary private information is removed. Inspect
selected data before authorizing extraction. Source paths remain local metadata.

Each import processes at most the configured excerpt budget (default 24,000 text
characters), leaving the rest for a subsequent import. Partial final records are
left pending. Re-import skips consumed ranges and duplicate source references.
Truncated/changed prefixes, conflicting mirrors, project switches and malformed
complete records pause import without advancing its checkpoint. This initial
reader does not automatically repair rotated or rewritten sessions.

## Consolidate selected evidence

```sh
proofpress consolidate --scope coding/my-sdk
proofpress consolidate --scope coding/my-sdk --model-assessment
```

Without the flag this previews the queue. With it, selected redacted excerpts are
sent through the existing Codex CLI login to extract candidate judgments. This
is distinct from the TypeSafe assessment adapter. The extractor's local tool
calls are denied, web search is disabled, output shape and source references are
checked, and every result remains a proposed hypothesis. Extraction does not
create arbitrary scope: you supply it and should narrow it during review.

One batch is processed per invocation, and a committed batch is not reprocessed.
Exact duplicate statements within a scope are skipped; semantic consolidation or
automatic generalization across many sessions is not implemented. Review the
source, rationale and conditions before admission. A failed extraction leaves the
batch pending. In the CLI, model extraction runs outside the database write lock;
the batch is checked again when committing.

This is the first reusable background-work entry point. A future scheduler can
invoke it, but no nightly job is installed by onboarding. A hook can signal task
completion; the worker does extraction. Neither should automatically admit rules.

## Contextual AJF 0.3

New captures default to 0.3-draft; explicit 0.1/0.2 records remain readable and
immutable. New content fields are restricted to the new draft:

- `context`: situation, optional goal, constraints and scalar background facts.
- `alternatives`: options and recorded reasons not chosen; unknown reasons are null.
- `expected_outcome`: intended effect and optional verification approach.
- `judgment.polarity`: `prefer` or `avoid` for negative lessons.

Context describes the original situation. It does not replace executable
applicability. The compact agent projection preserves these fields when present.
See [contextual example](../examples/contextual-judgment.json).

## Append outcomes

`proofpress observe --from observation.json` appends an observation with:
`judgment_id`, `version`, exact `digest`, `kind` (`execution`, `task`, `long_term`),
`result` (`succeeded`, `failed`, `mixed`, `unknown`), `summary`, `observer`,
`observed_at`, and nonempty `evidence_refs`. Optional `usage_receipt` must include
that exact revision. The receipt shows supplied context, not proven reliance.
Optional `idempotency_key` prevents duplicate writes and rejects changed content
under an existing key. `proofpress observations ID` reads the results.

An observation does not change the judgment, admission, model score or runtime
binding. Evidence references are declared sources, not fetched/verified facts;
identity is the same cooperative local identity as other records. Outcome does
not establish causality. Corrections require a new observation or candidate,
not mutation of past results.

## Assist review

```sh
proofpress --env-file /private/provider.env review-assist JUDGMENT_ID
```

This runs deterministic conflict checks and a model assessment against selected
imported source excerpts. The current assessment provider is TypeSafe. Missing
source evidence or unavailable/uncertain provider results should be unknown.
The report is bound to the inspected content digest; it never invokes admission.
Human review is still mandatory. Automatic approval needs a separately designed,
owner-authorized risk policy and evaluation; this release does not implement it.
