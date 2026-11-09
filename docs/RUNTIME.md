# Enforce judgments

Enforcement checks a covered tool action before it runs. Start with
`proofpress review ID`, choose **Enforcement**, then inspect the verifier and
protected paths. One approval admits the judgment and binds that check to the
exact revision. [Review and recovery walkthrough](LOCAL-ALPHA.md)

## Install a host hook

Copy the [install command for your agent](../README.md#enforce-judgments).
The installer preserves existing hook entries. To preview the registration
first, run the command without `--confirm`.

| Host | Command value | Configuration | Verification |
| --- | --- | --- | --- |
| Codex | `codex` | `.codex/hooks.json` | [Installed-hook lifecycle](verification/installed-codex-hooks-2026-11-09.json) |
| Claude Code | `claude-code` | `.claude/settings.local.json` | [Live Write denial](verification/live-claude-hook-2026-11-08.json) |
| Cursor | `cursor` | `.cursor/hooks.json` | [Cursor CLI lifecycle](verification/live-cursor-hooks-2026-11-09.json) |

Restart the host in the project and inspect the registered hook. In Codex,
trust the project and review the exact entry in `/hooks`. `proofpress doctor`
shows local configuration, active bindings and the last observed hook check.
[Codex trust flow](https://learn.chatgpt.com/docs/hooks#review-and-trust-hooks) ·
[Claude Code hooks](https://code.claude.com/docs/en/hooks) · [Cursor coverage](CURSOR.md)

## What the hook checks

- **Protected paths.** Block direct edits to matched generated files.
- **Revision and conditions.** Pause on stale or withdrawn bindings, unresolved
  conflicts or unmet conditions.
- **Decision model.** Assess full new-file content before writing. Partial
  edits, violations, uncertainty and provider errors pause this verifier.

With active bindings, unsupported routes such as shell and MCP pause
conservatively. A passed check leaves the host's own tool permissions in effect.
Coverage depends on emitted events, host trust and host failure behavior. The
hook is a cooperative local check. [Security boundaries](../SECURITY.md)

## Recover after a pause

Review the reason and the bound revision. Reject or revise a conflicting
candidate, or review a replacement binding if the previous version was
superseded. A withdrawn or superseded binding keeps protection in place
until you rebind or run `proofpress unbind ID --confirm`.

Use `proofpress pause --confirm` and `proofpress resume --confirm` to change
whether managed hooks check actions. Use `proofpress hooks remove --host HOST
--confirm` to remove only the managed registration. With no bindings, the
managed hook leaves normal host permissions in effect.

## Set up Jev

After onboarding, create `.judgment/jev.env` in your project with the settings
below. The installer sets up the project but keeps provider configuration
opt-in. The workspace's generated `.gitignore` keeps this file out of Git.

```dotenv
PROOFPRESS_DECISION_MODEL_PROVIDER=typesafe
PROOFPRESS_DECISION_MODEL=jev-1.13.0
TYPESAFE_API_KEY=
```

Fill in your TypeSafe key and choose a model available to your account.
Use a dedicated env file because the CLI accepts only decision-model settings.
[Environment template](../.env.example)

For advice on whether evidence supports human admission, see [Review policy](INTAKE.md#review-policy).

### Screen a candidate for conflicts

```sh
proofpress inbox
proofpress --env-file .judgment/jev.env assess JUDGMENT_ID
```

Use the candidate ID from the inbox. This sends the proposed judgment and
overlapping admitted judgments to TypeSafe to look for conflicts. To request
the same check at capture time, use `capture --from candidate.json --decision-model`
with the same global `--env-file` option. Uncertain results and provider errors
are recorded as `unknown`. Review the candidate and result in the CLI.

### Check a covered write

During review, choose **Enforcement** and select the decision-model check for
the paths you want to protect. Approve the binding, then install or refresh
your host hook with the same env file. For example, with Codex:

```sh
proofpress --env-file .judgment/jev.env hooks install --host codex --confirm
```

Restart the host and inspect the updated hook in its trust flow. A covered
new-file write sends the full proposed content and the exact bound judgment
to TypeSafe. Partial edits, violations, uncertain results and provider
failures pause this check. Use this option for content you can send to the
provider.

[TypeSafe Choice API](https://docs.typesafe.ai/primitives/choice) defines the
request and answer format. Prototype cutoffs are probability ≥ 0.95 and
confidence ≥ 0.90. The [live Codex receipt](verification/live-codex-hooks-2026-11-08.json)
records one blocked violating output and one released compliant output with
`jev-1.13.0`.

## Flag conflict before reuse

AJF judgments can include an optional structured assertion:

```json
{"key":"internal-url-separator","value":"_"}
```

Place it in `judgment.assertion` alongside statement, kind and rationale. Different
values for the same key, under overlapping explicit scopes and equality conditions,
flag a deterministic conflict. Free text conflicts require `assess` or
`capture --decision-model`; configuring a key alone does not enable automatic assessment.
Time-window overlap is conservatively overestimated in this version.

A conflicting proposal remains proposed. It cannot be admitted until the conflict
is resolved. Conflict/unknown flags pause context and bound protected actions in
that scope, including old receipts. Reject or revise the candidate, withdraw the
incorrect admitted judgment, or rerun assessment after clarification. Decision model
screens are stale when the compared admitted set changes; rerun assessment before
admission. A clear model result never admits a candidate.

## Bind an execution check

Human operator only: inspect an admitted judgment, then prepare a binding file:

```json
{
  "project_root":"/absolute/canonical/project",
  "scope":"coding/generated-files",
  "judgment_id":"jgm_REPLACE_WITH_REAL_ID",
  "version":1,
  "digest":"sha256:REPLACE_WITH_INSPECTED_DIGEST",
  "verifier":"deny_generated_write",
  "paths":["generated/*"]
}
```

```sh
proofpress bind --from binding.json --confirm
```

This explicit binding command is useful for scripts. The interactive review
flow can admit and bind in one operation. A new binding for the same judgment explicitly replaces its old binding.
Withdrawn or superseded bindings block covered actions until a human rebinds them;
withdrawal never silently removes protection. Binding path patterns are explicit
owner configuration, not a model's claim about generated status.

The alternative verifier `decision_model_output` assesses complete Write content against
the bound judgment and pauses violations or uncertainty. It rejects partial Edit
requests because it cannot assess the full resulting document. This is a model
assessment gate; passing does not establish correctness of meaning.

## Claude Code handler details

The live receipt above verifies one real Write denial through the Claude Code
handler. It used an explicit test registration. For ordinary setup, use the
managed project hook command above. To load a decision-model key for the hook,
pass `--env-file /private/path/.env` before the subcommand when installing.

The handler reads a PreToolUse event from stdin. Write/Edit use absolute target
paths and must stay in the bound project after symlink resolution. Generated-file
checks derive `generated_file=true` from matched owner-configured paths. Other
condition fields remain unknown and block; the model cannot invent them. Read,
Glob and Grep fall through to normal host permissions. Other tool routes, including
Bash and MCP, are denied while bindings are active; they are not parsed as safe.
A pass returns `{}`, preserving host authorization rather than returning allow.

Handler tests invoke the CLI with synthetic native event payloads. These are not
live-host or benchmark results. Same-user edits, disabled hooks, untrusted project
configuration, remote agents and routes that never emit the event remain outside
this cooperative plugin's boundary. Hook checks and subsequent host effects are
not atomic. The playground's draft-release freshness check now precedes writing
solution/test files; that bounded local behavior does not solve generic host races.


## Verified Codex integration

[November 8 receipt](verification/live-codex-hooks-2026-11-08.json) records eleven
real Codex 0.153.4 scenarios: valid binding allows; conflict pauses; rejection of
the conflicting candidate resumes; withdrawal invalidates; admission of a new
revision does not upgrade the old binding; explicit rebinding resumes; a pending
revision preserves the active binding; supersession invalidates it; a generated
file edit is blocked; a decision model violation pauses; compliant content passes.
Every scenario requires both an actual apply_patch hook receipt and the expected
filesystem result. A model merely declining to act cannot pass this verifier.

The adapter maps every Add/Update/Delete/Move patch target to the shared gate.
Moves check both old and new paths. Complete Add File content can be assessed by
the decision model; partial Update/Edit content still pauses rather than claiming
a complete-document assessment. A multi-file patch must pass every target check.

`require_conditions` is a deterministic binding verifier for lifecycle and declared
conditions only. It does not interpret judgment prose or prove output correctness.
It supports an allow-before / deny-after lifecycle control in the live fixture.

To rerun, from the source checkout:

```sh
.venv/bin/python scripts/verify_live_hooks.py --run-live \
  --provider-env /absolute/path/to/private/.env \
  --output /private/path/to/live-verification.json
```

Omit `--provider-env` for nine deterministic scenarios without TypeSafe calls.
The script uses disposable synthetic stores, with synthetic human review actions
explicitly authorized by `--run-live`. It never opens your playground judgment
store. It invokes real Codex model calls and, when selected, real TypeSafe calls.
It persists only a bounded verification summary and hook receipts, not raw traces
or credentials. Failed host startup, missing receipts, wrong verdicts, timeouts,
or unexpected file results fail the run.

For this isolated automation, the script passes the inspected hook definition in
invocation-local `-c hooks.PreToolUse=...` configuration. Its one-invocation hook
trust bypass is limited to that test harness; it does not persist trust or disable
the Codex execution sandbox. The [installed-hook receipt](verification/installed-codex-hooks-2026-11-09.json)
separately verifies the managed registration through the normal trust workflow. The playground's generation-only demo is not automatically
converted into this tool-using harness.

Keys remain in the selected local environment file. No production deployment,
other-host interception or arbitrary-action enforcement was verified by this run.
