# Cursor hooks

Cursor provides native hooks. Proofpress's adapter translates `preToolUse` events
into the same local judgment checks used by the Codex and Claude Code adapters.
This integration requires a Cursor version that emits the documented generic
`preToolUse` event. IDE, CLI and Tab coverage must be verified separately.

## Enable in a project

```sh
proofpress onboard --agents cursor
proofpress hooks install --host cursor
proofpress hooks install --host cursor --confirm
```

The installer merges one synchronous entry into `.cursor/hooks.json` and preserves
other events and handlers. It sets `failClosed: true` and includes a native denial
fallback if the Proofpress executable cannot start. Reload Cursor and inspect its
hook settings. Review a judgment and its proposed enforcement before expecting
protected actions to be checked. No binding means ordinary actions remain governed
by Cursor's normal permissions.

`proofpress doctor` checks registration and shows the last runtime check. It does
not infer that every Cursor mode emits an event. Remove the managed entry with
`proofpress hooks remove --host cursor --confirm` or use `proofpress uninstall`.

## Covered checks

The adapter recognizes native Write, Edit/StrReplace, Delete and Read file targets.
Relative paths resolve against the event's explicit absolute working directory
or its single declared workspace root when the CLI omits `cwd`. Multiple roots
without `cwd` remain ambiguous and pause.
Ambiguous target/content aliases, missing inputs and unknown action routes pause.
Shell and MCP routes remain unsupported while protection is active; they cannot
be used to bypass a protected file write.

Generated-file protection denies writes to owner-selected generated paths.
Lifecycle/condition checks reject stale or withdrawn bindings. Decision model
checks require complete Write content; partial edits pause. Existing host
permissions still apply. Tab completions and tool routes that do not emit the
registered event are outside this adapter's coverage.

## Validation

Synthetic native-event tests cover schema errors, shell denial, generated-write
denial, revision/rebinding/withdrawal, symlink escape, partial edits, preservation
of existing hooks, uninstall and a missing-executable denial fallback. These are
local adapter tests, not real Cursor task results.

A live CLI runner is available after logging in:

```sh
python scripts/verify_cursor_hooks.py --run-live --output /private/path/receipt.json
```

It creates a disposable synthetic owner workspace and runs four real coding tasks:
generated-write denial; stale-binding denial after revision; successful write after
explicit rebinding; denial after withdrawal. Each must produce a Cursor hook record
and the expected file result. `--force` permits headless writes; `--trust` applies
only to this synthetic workspace. It never opens your project's judgment store.
[Real Cursor CLI verification](verification/live-cursor-hooks-2026-11-09.json)
passed all four scenarios with CLI `2026.11.05-86047df`. Each scenario recorded a
native Write check and the expected file result in a new CLI invocation. The
initial run exposed that CLI events omit `cwd`; the adapter now uses a single
explicit `workspace_roots` entry. These results cover the CLI, not independent IDE
or Tab verification.

The official CLI command is `agent`; this runner defaults to
`~/.local/bin/cursor-agent` so it does not accidentally invoke a different vendor's
`agent` command. Use `--binary PATH` when your installation differs.

[Cursor hook reference](https://cursor.com/docs/hooks) ·
[CLI installation](https://cursor.com/docs/cli/installation) ·
[Headless writes](https://cursor.com/docs/cli/headless)
