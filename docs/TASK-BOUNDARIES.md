# Context-first enforcement

> **Default: judgment-owned behavior.** Use [Behavior](BEHAVIOR.md) and
> `proofpress enforce install`; no workflow configuration or separate binding is
> required. The explicit bindings/workflow configuration below remains an advanced
> compatibility interface. New lifecycle integration is protocol-tested, not live-host verified.

This workflow schedules semantic review before source execution and before delivery.
It adds owner-defined scope criteria, context-first planning, host task attachment,
recoverable pauses, and an exact-file delivery gate. Existing action bindings keep
their behavior. All local authority remains cooperative under the same OS user.

## Mechanism

| Step | Inputs and behavior | Enforcement boundary |
| --- | --- | --- |
| Configure | Human reviews workflow facts, mandatory scopes, optional scope criteria, allowed paths, required artifacts and exception policy | Agents do not confirm policy changes |
| Prepare | Mandatory scopes always stay; Jev assesses each optional scope. Unknown scope pauses. Enumerate eligible admitted judgments in each selected exact scope | No top-k ranking; missing facts on admitted judgments cannot silently omit them |
| Supply context | Return judgments, versions, conditions, task id, context id and plan draft path before planning | Claude prompt hook injects this packet; explicit integrations must call task-prepare |
| Review plan | Agent submits a concrete plan tied to that context id; one aggregate model assessment checks task, plan and judgments | Covered source writes require a passing, current plan |
| Execute/repair | Read-only tools pass. Covered file/patch targets get deterministic task/lifecycle checks plus existing hard bindings | No semantic call on each intermediate write. Unsupported shell/MCP routes pause |
| Review delivery | Read all actual text files in workflow paths, include new files and deletion markers, require declared artifacts, assess together | Model pass/violation/unknown is bound to the exact bundle and start revision |
| Recover | Show paused boundary, reason, checked judgments, review bundle and next actions | Repair remains possible after a valid plan; unknown never silently passes |
| Export | Freshly recheck context, latest review, artifact digest and subsequent write attempts, then write the exact checked local bundle | No unreviewed bundle is exported through task-export |

Jev scope classification and semantic assessment remain probabilistic. Determinism
applies to configured mandatory scope inclusion, exact conditional selection,
version/freshness checks and checkpoint execution. A wrong semantic classification
can still omit an optional scope. Missing facts stay unknown; Jev never manufactures
trusted facts. Scope criteria and facts currently come from owner-reviewed workflow
configuration, not automatically inferred environmental truth.

## Configure a workflow

Create a private JSON file, adapting this example to real reviewed judgments:

```json
{
  "id": "coding",
  "project_root": "/absolute/canonical/project",
  "mandatory_scopes": ["coding/project-architecture"],
  "scope_criteria": {
    "coding/shared-state": "Task introduces or changes state shared across service instances"
  },
  "facts": {"multi_instance": true},
  "paths": ["src/*", "tests/*"],
  "artifacts": ["src/service.py"],
  "allow_exceptions": false
}
```

```sh
proofpress workflow --from workflow.json
# Human reviews and runs:
proofpress workflow --from workflow.json --confirm
```

Configuration lives in the local ledger, outside portable AJF. Preview reports the
provider inputs: request text, criteria, configured facts, judgments, plans and
covered outputs. Use the explicit BYOK env file as with existing model assessment.
No provider configured, provider failure, oversized input or low certainty means
unknown. Two semantic reviews are the normal plan/output budget; scope resolution
adds one assessment per optional criterion. Repair/restart can add calls. Claude
Stop reviews files and final response together; the skill avoids a duplicate
file-only review on that normal path. Requesting both a separate file export and
a native response review adds a separate review boundary.

`paths` define the actual file coverage. `artifacts` are exact required files, not
a model-picked subset or glob. At delivery the engine enumerates *all* current
covered files, checks required files exist, and includes additions plus deletion
markers against the prepare-time file set. It excludes Git/store internals,
rejects covered symlinks and unreadable/oversized artifacts, and never silently
truncates. This is declared-workspace coverage, not proof that all external
business requirements or dependencies were included.

## Claude Code lifecycle

```sh
# Preview; human installs after reviewing workflow, data transfer and host hooks:
proofpress --env-file .judgment/jev.env workflow-hooks install --workflow coding
proofpress --env-file .judgment/jev.env workflow-hooks install --workflow coding --confirm
```

Restart Claude and inspect/trust hooks. The managed entries preserve other hooks:

- `UserPromptSubmit` prepares context from the submitted request, creates a task
  id, explicitly maps the session to it and injects the context packet before
  Claude plans. Each new user prompt starts a new task context; corrections do
  not inherit an old passing plan. To resume a paused task after inspection, submit
  the exact text `proofpress resume task TASK_ID`; only the task already attached
  to that session can resume, and all artifact/freshness checks stay active.
- `PreToolUse` gates source writes on the current plan and retains hard bindings.
  Known Read/Glob/Grep tools stay available. The exact task plan draft can be
  written before plan approval. A narrowly parsed `proofpress` control channel
  permits task-plan/task-status/task-finish-files for the attached task and store;
  owner commands, shell operators/expansion and arbitrary routes do not pass.
- `Stop` reviews actual covered files plus `last_assistant_message`. A violation
  gets one repair continuation; uncertainty or repeated failure returns control
  to the human with a visible pause, never an approval. An unchanged failed
  bundle is not repeatedly sent to the provider.

Requires Claude >=2.1.295 for `onFailure: block` on prompt/pre-tool hooks. Stop
hooks do not support that failure option. A Stop check cannot retract streamed
text, prevent user interruption or authorize prior external effects. Claude's
Stop loop/failure behavior is not an atomic publishing boundary. Use task-export
or an application-owned pre-send/pre-deploy gate for an actual delivery boundary.
Installation and CLI protocol fixtures have been tested, not a live Claude run
with this new lifecycle bridge.

`doctor` reports managed lifecycle entries. `workflow-hooks remove --workflow
coding --confirm` removes only them; uninstall also removes the managed entries.

## Explicit Codex/Cursor and workflow API

Their existing pre-tool adapters can use the same workflow state through explicit
session attachment. Native task-start/completion interception is not implemented
for these hosts. Refresh existing installed hooks to obtain the explicit host
identity added to the managed registration in this PR.

```sh
proofpress --env-file .judgment/jev.env task-prepare --task TASK_ID \
  --workflow coding --description request.txt --format agent
# Read supplied judgments, write the plan to returned plan_path, then:
proofpress --env-file .judgment/jev.env task-plan --task TASK_ID \
  --context CONTEXT_ID --plan PLAN_PATH
proofpress task-attach --task TASK_ID --host codex --session ACTUAL_SESSION_ID
proofpress --env-file .judgment/jev.env task-finish-files --task TASK_ID \
  --evidence test-evidence.txt
proofpress task-status --task TASK_ID
proofpress task-export --task TASK_ID
```

A runner must perform preparation/attachment before execution and honor each result.
An unattached generic host session does not become globally governed just because
a workflow exists; use explicit task bindings or an application-owned runner when
that coverage is required. An attached task's source paths cannot be broadened by
the agent. Unknown tool routes pause conservatively rather than being parsed as
safe shell commands. This prototype does not yet permit arbitrary test/build
shell commands; run them through an owner-controlled integration and provide
evidence. No generic publish/deploy/email interception is claimed.

`task-start`, `task-finish` and `task-check` retain the earlier single-scope API
for caller-supplied plans/artifacts. They are an explicit integration interface,
not an alternative way to satisfy a prepared workflow's context-before-plan gate.
Python workflow/task APIs require the caller's `Store.transaction()`; CLI and
lifecycle entry points supply it.

## Pause and recovery UX

`task-status` distinguishes context clarification, planning, plan review,
execution, delivery pause and a reviewed revision ready for delivery. It shows:

- Which boundary is paused; reading remains available.
- Model-flagged violation versus insufficient certainty, plus deterministic
  freshness reasons. Aggregate review does not invent per-judgment attribution.
- Exact checked judgments and artifact names, and a local review bundle path.
- Repair-and-recheck, provide evidence/context, or request owner review.

Context/facts/judgment changes require preparation and plan review again. A failed
plan leaves only read/planning work available. A failed output check leaves source
repair available when the plan is current, while delivery stays closed. A write
after passing review, even one later refused by the host, requires review again.
Changes made outside hooks are detected when a fresh snapshot differs.

When the workflow explicitly permits exceptions, the human can inspect the review
bundle and approve only that exact task/start/review/artifact revision:

```sh
# Human only; preview first:
proofpress task-exception --task TASK_ID --artifacts REVIEW_BUNDLE.json \
  --reason 'Specific reviewed exception'
proofpress task-exception --task TASK_ID --artifacts REVIEW_BUNDLE.json \
  --reason 'Specific reviewed exception' --confirm
```

This does not edit/admit a judgment or weaken a binding. It cannot override stale
context, withdrawal, a later failed review, changed artifacts or a later write.
Review bundles contain private output bodies in the ignored local workspace;
ledger receipts store digests and assessment metadata. Delivery bundles are also
local, ignored artifacts. No data from real user tasks is checked into Git.

## Practical limits

Known read-only managed hooks bypass store opening/ledger work, but interpreter
startup and broad callback registration remain. This PR does not claim measured
latency improvement. Long-task checkpoints, compaction and handoff need explicit
workflow boundary events; the bridge does not infer all of them from transcripts.
Model verdicts do not establish correctness, relevance completeness or causality.
Same-user edits, disabled/untrusted hooks, unobserved routes, remote agents and
concurrent external effects remain outside the cooperative enforcement boundary.

Official host contract: https://code.claude.com/docs/en/hooks (checked 2026-11-17).
