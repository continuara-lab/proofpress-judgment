# Import sessions and configure capture

## Import a project

From your project, run the command for the agent whose sessions you want.

```sh
proofpress history project --project . --agent codex
proofpress history project --project . --agent claude-code
proofpress history project --project . --agent cursor
```

The CLI previews the project and session count for the last seven days. Change
the window with `--days`. Confirm to store excerpts locally. In scripts, use
`--confirm` to authorize import after reviewing the preview. The global
`--workspace` option selects the destination store if it differs from the
source project.

| Agent | Local source | How the project is selected |
| --- | --- | --- |
| Codex | `~/.codex/sessions` or `$CODEX_HOME/sessions` | Exact working directory from session metadata |
| Claude Code | `~/.claude/projects` or `$CLAUDE_CONFIG_DIR/projects` | Exact working directory from the main transcript |
| Cursor | `~/.cursor/projects/<workspace>/agent-transcripts` | Cursor's workspace folder, shown before confirmation |

Cursor JSONL usually lacks a working directory in each record. Confirm the shown
folder belongs to your project. If discovery misses a transcript, select the
local JSONL file yourself. Cursor must have saved a local transcript.
[Cursor transcript settings and hook fields](https://cursor.com/docs/hooks)

### Import a single session

```sh
proofpress history scan --project . --agent claude-code --previews
proofpress history preview --project . --agent claude-code --session KEY
proofpress history import --project . --agent claude-code --session KEY
```

Use `--file /absolute/session.jsonl` in place of `--session KEY` to choose a file
directly. For Cursor, only choose files you know belong to the specified project.
Use `--root` to override the history root for discovery. The time window uses
file modification time. Scan examines at most 5,000 candidate files.

Import reads user and assistant text from supported local JSONL, skipping tool
calls, tool results and non-text blocks. Files may be up to 32 MiB. Excerpts,
roles, timestamps when available and byte-range references stay in the local
store. Known credential formats are redacted on a best-effort basis. Review
which transcripts you selected before authorizing extraction.

Project import processes available batches. Single-session import reads up to
the configured character budget per invocation, 24,000 by default. Repeated
imports resume from the checkpoint, skip consumed ranges and deduplicate source
references. Partial lines stay pending. Changed prefixes and conflicting
mirrors pause the affected import. A Codex or Claude Code project switch also
pauses the affected import.

## Extract candidate judgments

```sh
proofpress consolidate --scope coding
proofpress consolidate --scope coding --model-assessment --all
proofpress review
```

The first command previews pending batches. `--model-assessment` sends excerpts
through the Codex CLI and requires a working Codex login, regardless of which
agent recorded the session. It follows the capture policy and validates the
model's output shape and source references. It creates proposed hypotheses.
Review their evidence, rationale, scope and conditions before admitting them.

By default one batch is processed. `--all` processes the current pending queue
and stops on error. Reruns skip completed batches. Exact duplicate statements in
the same scope are skipped. Onboarding installs no background job.
[Review-assisted checks](#assist-review)

## Configure capture

Run `proofpress onboard --startup --agents codex` to preview setup. Use
`claude-code` or `cursor` for the other hosts. Setup installs local guidance and
the defaults tell the agent when to propose your judgments, corrections, its own
consequential choices and useful lessons at the end of a task. Capture is agent
guidance. History import is a separate opt-in action.

On the setup screen, choose **Use shown policy** or **Customize capture**.
Customization explains each capture category and previews your choices before
enabling them. Run `proofpress capture-policy` to inspect settings later and
`proofpress configure` to change what the agent may propose. For scripts,
the human can set policy with explicit confirmation.

```sh
proofpress capture-policy --triggers human_correction task_end --confirm
proofpress capture-policy --triggers none --history none --confirm
```

`proofpress capture-policy` prints the active settings. Manual review stays
required. Changing capture policy does not change runtime bindings.
[Agent setup](AGENT-SETUP.md) · [AJF fields](AJF.md)

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

## Review policy

Use `proofpress review-policy` to see the current model timing, input scope and
criteria. Local checks and manual admission apply with every policy.

1. Set up the [TypeSafe configuration](RUNTIME.md#set-up-jev) in `.judgment/jev.env`.
2. To check one candidate, choose **Check evidence** in `proofpress review ID`
   or run `proofpress review-assist ID`.
3. To assess candidates saved through capture or revision, explicitly enable
   project-wide model advice. Put your criteria in a short text file before applying the policy.

```sh
proofpress review-policy --mode on-capture --criteria review-criteria.txt --confirm
```

This sends candidate records and the review criteria to the configured provider
after capture or revision. The default evidence mode sends only the candidate
record, including the evidence summaries you wrote into it. Opt in with
`--evidence referenced-history --confirm` to also send imported excerpts that
the candidate cites. Use `--mode manual --confirm` to restore on-request model
review.

Write criteria for the work, such as requiring benchmark evidence for latency
claims and accepting a maintainer's explicit instruction for repository
conventions. The result applies to the exact candidate and policy versions.
The review screen shows local checks, model advice and your approval separately.
Use `assess ID` when you specifically want a conflict screen against other
approved judgments.
