# Task-boundary semantic checks

Status: cooperative workflow API and CLI prototype. This is the recommended
scheduling model for new integrations, not a silent migration of installed hooks
or owner-approved bindings.

| Boundary | Check | Model calls on the normal path |
| --- | --- | --- |
| Task start | Assess the concrete plan against all currently eligible judgments in one exact scope | One aggregate assessment |
| Covered write | Match configured paths, validate the bound revision and current task snapshot | None for `task_boundary` |
| Before delivery | Assess the complete supplied artifacts and supporting evidence | One aggregate assessment |
| Release check | Recheck freshness and the exact artifact digest | None |

Unknown results, unavailable providers and insufficient evidence pause the task.
Repair and re-review may require more calls. Two is a normal-path budget, not a
fixed cap or a guarantee of semantic correctness. Large review packets still hit
the existing provider input limit and return unknown; they are not truncated.

## Explicit workflow contract

The workflow owns the task id, trusted facts, task boundaries and delivery.
A host session is not automatically a task. One task snapshot covers one exact
scope in this prototype. All eligible admitted judgments in that scope are
reviewed together; this does not perform semantic retrieval across other scopes.

1. Call `start_task` and honor a false result before doing covered work.
2. Attach `proofpress_task_id` to normalized tool events before calling the shared
   `gate`. Use a human-reviewed `task_boundary` binding for the semantic paths.
3. Call `finish_task` with complete final artifacts and relevant evidence.
4. Call `check_release` immediately before actual delivery, block on false, and
   deliver those exact artifacts. A positive finish result alone is insufficient.

The CLI exposes the same start/finish/check contract. All failed checkpoints
return exit code 3 (invalid input returns 2):

```sh
proofpress --env-file .judgment/jev.env task-start --task TASK_ID \
  --scope coding/generated-files --facts facts.json --plan plan.txt --json

proofpress --env-file .judgment/jev.env task-finish --task TASK_ID \
  --facts facts.json --artifacts artifacts.json --evidence evidence.txt --json

proofpress task-check --task TASK_ID \
  --facts facts.json --artifacts artifacts.json --json
```

`artifacts.json` maps artifact names to complete text content, for example
`{"src/example.py":"complete final file content"}`. It is supplied data, not a
manifest the engine reads from disk. The workflow must collect complete relevant
content and verify that what it delivers matches the checked bundle. Passing a
handpicked subset or model-generated success summary cannot establish coverage.
Evidence is optional input, but missing required evidence should produce unknown.
Plan text is stored in the local ledger; artifact and evidence bodies are sent
to the configured provider but only their digests are persisted by task finish.
Judgment context and model assessment metadata remain in the local ledger.

## Configure a semantic task binding

Use the existing explicit human `bind --from ... --confirm` workflow after
inspecting the exact admitted revision. Set `verifier` to `task_boundary`; the
other binding fields remain `project_root`, `scope`, `judgment_id`, `version`,
`digest` and `paths`. The interactive review menu is not changed in this prototype.

A `task_boundary` binding checks the plan before covered writes and defers
semantic output review to task finish, allowing intermediate partial edits.
Freshness checks remain deterministic on each covered write. Existing
`deny_generated_write`, `require_conditions`, `decision_model_output` and legacy
`semantic_output` bindings retain their behavior. Do not move irreversible
external effects to a task-end review; retain an action gate before those effects.

Raw managed host hooks do not inject `proofpress_task_id` or gate task completion.
They therefore pause covered task-boundary writes until a workflow bridge
supplies the explicit task id. Do not install this verifier into an unmodified
host and assume that end-of-task enforcement has been added.

## Freshness, retry and release

Withdrawal, supersession, conflicts, changed facts, policy changes and a changed
set of eligible judgments invalidate the task snapshot. Restart with the updated
plan/facts. A later start, even if it fails, invalidates the old finish receipt.
A later failed finish supersedes an earlier passing finish. Any covered write
attempt after a passing finish invalidates release and requires re-review, even
if the host later refuses the write. Artifact changes require a new finish.

A correction, new scope, compaction recovery or important handoff should be an
explicit restart/checkpoint chosen by the workflow. This prototype does not infer
these events from a transcript. Receipts describe model assessments of supplied
data; they do not prove completeness, truth, execution or substantive correctness.

## Cost and coverage

Managed `Read`, `Glob` and `Grep` events with object tool inputs now return before
opening the store or auditing the ledger. Unknown tools and malformed events do
not get that shortcut. This intentionally omits read-only runtime receipts.
Interpreter startup and the host callback still occur: the registration remains
broad so shell, MCP and alternate write routes cannot silently bypass coverage.
Unknown routes continue to pause with active bindings. Path matching already
skips nonmatching bindings before model assessment.

This change reduces model-call frequency for the new workflow mode and avoids
ledger work on known reads. It does not claim a measured latency improvement,
native host-level tool filtering, an atomic release, or complete interception of
remote/delegated actions. Same-user local protections remain cooperative.
