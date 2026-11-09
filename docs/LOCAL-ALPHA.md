# Try the local workflow

Use an ordinary project in an isolated checkout. Keep real admissions in your own
terminal. Engineering tests only use disposable synthetic owner fixtures.

## Install and configure

Run `bash /path/to/proofpress-judgment/install.sh` in the project. Alternatively install
with `python -m pip install /path/to/proofpress-judgment`, then run `proofpress onboard --startup --agents codex` with your chosen agent.
Onboarding previews what capture means, enabled categories, manual review, optional
project history and hook status. Enter `y` to enable it. Run `proofpress configure`
to choose capture categories and history permissions later.

To refresh previously installed skill files, use `proofpress onboard --upgrade`.
Existing differing files are backed up under `.judgment/skill-backups/` before
replacement. Setup without `--upgrade` preserves differing files by refusing.

`proofpress doctor` reports installed skills, registered hooks, bound revisions,
owner pause state and the last observed hook check. It cannot inspect the host's
in-memory trust state or certify that every future tool emits a hook.

## Capture and review

Ask your agent to propose a judgment from a correction or meaningful choice.
`proofpress inbox` lists candidates. `proofpress review ID` shows the judgment,
reason, situation, scope, conditions, limits, source references and proposed
protection. Choose Edit to open `$VISUAL`, `$EDITOR`, or `vi`; save and close to
create a new immutable candidate and return to review.

Choose Enforcement to select advice only, generated-path protection, lifecycle
and condition checks, or a decision model check. Enter the canonical project root
and protected path patterns. Review the resulting preview before approving.
Approval and binding are one database transaction. Invalid binding configuration
rolls back approval. Explicit automation flags remain available in CLI.md.

Model assessment sends the judgment and complete new-file content to the configured
provider; missing configuration, provider failure, uncertainty or a violation
pauses the action. Partial edits cannot establish complete-document compliance.

## Install hooks

Preview with `proofpress hooks install --host codex`, then repeat with `--confirm`.
This merges a synchronous PreToolUse entry into `.codex/hooks.json`, preserving
other entries and settings. Start Codex in the project, trust the project and
review the exact entry in `/hooks`. Proofpress never writes host trust.
See [Codex's hook trust documentation](https://learn.chatgpt.com/docs/hooks#review-and-trust-hooks).

Claude Code uses `.claude/settings.local.json` with `--host claude-code`; verify
its trust and hook status in that host. Cursor uses `.cursor/hooks.json` with
`--host cursor`. [Host coverage and verification](RUNTIME.md#install-a-host-hook)

For a private decision-model environment file, include `--env-file /path/.env`
before `--workspace` when installing the hook. Registration stores only the path,
not credentials. Environment loading is explicit. Installed hooks use an absolute
Python executable, so keep that environment installed.

Shell, MCP and other unsupported tools pause while any bindings are active. This
strict prototype does not parse arbitrary shell commands as safe, including test
commands. Consider this limitation before enabling protection in daily work.
The host may fail open on timeouts or disabled/untrusted hooks; installation does
not provide an independent sandbox or atomic check-and-effect boundary.

## Reuse, revise and recover

Have your agent request `context` with an exact scope and known facts. Use
`proofpress match --scope SCOPE --facts FILE` to explain exclusions without making
a context receipt or model call. `--format agent` reduces the payload returned to
an agent; `--json` preserves inspectability of the full record.

A proposed revision leaves the admitted version active. Approving a revision
supersedes the old revision; the old binding then pauses covered actions. In
`proofpress review ID`, choose and approve the replacement enforcement to bind
the new digest. No old approval silently follows revised text.

`proofpress withdraw ID --version N --digest DIGEST --reason REASON --confirm`
withdraws an admitted revision. Protection remains, conservatively blocking until
explicitly rebound or removed with `proofpress unbind ID --confirm`.
`proofpress pause --confirm` temporarily disables managed-hook checks;
`proofpress resume --confirm` resumes them. These are owner actions, never
agent self-approval operations.

`proofpress hooks remove --host codex --confirm` removes only the exact managed
registration. `proofpress uninstall --confirm` removes managed registrations and
unchanged installed skill files; edited files and the judgment store remain.
Restart your agent after removing integration. Prior session context is not erased.

## Import a project

`history project --project PATH --agent codex` previews local sessions and
asks before importing. Use `claude-code` or `cursor` for those agents.
[Source locations and supported formats](INTAKE.md) The global `--workspace` selects the destination store;
it can be an isolated sandbox distinct from that source. JSON/agent output and
noninteractive use require explicit `--confirm`. Invalid sessions are reported
with reasons; repeat imports resume checkpoints and avoid duplicate excerpts.

`consolidate --scope SCOPE` previews pending batches. Add `--model-assessment`
to send the next batch to Codex, or add `--all` to process the pending snapshot.
Failures stop processing; previously committed batches remain and reruns resume.
No scheduler or automatic admission is installed. Candidate metadata records the
capture trigger and capture policy digest. Extraction follows allowed triggers;
source support, scope and factual conditions still need human review.

## Measure usefulness

In repeated real sessions, track repeated steering, repeat mistakes, applicable
reuse, missed reuse, inappropriate reuse and time spent reviewing or recovering.
Compare task quality, human time, tokens and latency against maintained memory
notes on held-out tasks. Hook engineering tests do not establish task-quality gains.
