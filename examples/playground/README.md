# Proofpress playground

Review a judgment and its proposed enforcement, then watch a real coding agent's
action get blocked or released. Keys and workspaces stay local and gitignored.

## Install

From this directory:

```sh
./bootstrap.sh
```

The bootstrap installs this repository and the attributed capture source fork in
`.venv`. Real coding runs require a working `codex` login.

## Capture and reuse

```sh
./proofpress install
./proofpress run
./proofpress capture --text 'Your project correction'
./proofpress review
./proofpress run
```

`./proofpress inspect` is concise. `--details` expands a record; `--json` explicitly
requests full data. Code and generated tests in this generation-only walkthrough
are saved, not executed.

## Coding hook

```sh
./hook-demo setup
./hook-demo review
./hook-demo run
./hook-demo inspect
```

Review shows judgment and enforcement together. Choose `A` to approve and bind in
one transaction, or `E` to edit statement, rationale or scope and review a new
candidate. Conditions and limits are displayed but not editable in this view yet.
Edited text never silently becomes executable policy: if no known mapping exists,
explicitly propose a supported enforcement and inspect it before confirmation.

The first task attempts to edit generated code and should be blocked. Run
`./hook-demo revise` to propose the walkthrough's one-file exception, review it,
and run the task again. Approval also binds its exact version; no second bind step
is needed. The legacy `bind` command remains compatible. This exception allows
edits to the whole configured file, not just one field.

## Model assessment

Copy `.env.example` to `.env` and configure your decision model. The first adapter
is TypeSafe; the model name is configurable. Other providers are not implemented.

```sh
./decision-demo setup
./decision-demo review
./decision-demo run
./decision-demo run --valid
```

No tests ran in this synthetic scenario. The first report falsely claims they
passed; the second says they were not run. The configured model assesses the full
new report before writing. Violation, uncertainty or provider failure pauses it.
The judgment and synthetic report are sent to the configured provider. The API
key is not printed or committed. No message is sent to anyone. Existing reports
are preserved; inspect an existing report before repeating the run.

## Boundaries

These demos pass hooks explicitly to an isolated Codex invocation, with a one-time
trust bypass for the inspected test configuration. They do not install hooks
globally. Model assessment is fallible and never grants admission. Local same-user
identity is cooperative; this is not adversarial isolation.

The capture source fork lives under `vendor/provenance-core` with its LICENSE,
NOTICE and fork notes. Wire identifiers remain compatible. Proofpress review and
reuse eligibility live in a separate store; the stores share no transaction.

```sh
.venv/bin/python -m unittest discover -s tests -v
```

Tests use temporary stores and synthetic human fixtures, not your real judgments.
[Results](../../docs/PLAYGROUND.md) · [Runtime](../../docs/RUNTIME.md) ·
[Host research](../../docs/HOST-HOOKS.md).
