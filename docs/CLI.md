# Everyday CLI

Start with `proofpress onboard`, then use `proofpress configure` to choose what
capture means for your project: your judgments, corrections, consequential agent
choices and task-end lessons. Each category creates proposals for manual review.
No automatic listener is installed.

- `proofpress capture-policy` shows the active capture settings.
- `proofpress review-policy` shows when model review runs, what it receives and which criteria it uses.
- `proofpress review-assist ID` requests model advice on the latest pending revision. [Review policy](INTAKE.md#review-policy)
- `proofpress review` opens a numbered inbox; choose a candidate without copying an ID.
- `proofpress review ID` reviews one judgment, with editing and proposed enforcement.
- `proofpress edit ID` opens a concise TOML form in `$VISUAL` / `$EDITOR` / `vi`.
- `proofpress withdraw ID` guides manual withdrawal and explains remaining protection.
- `proofpress doctor` distinguishes configuration, bindings and observed runtime checks.
- `proofpress hooks install --host codex` previews host registration; `--confirm` installs it.
- `proofpress match --scope SCOPE --facts FILE` explains applicability without a model call.
- `proofpress pause --confirm`, `resume --confirm` and `unbind ID --confirm` explicitly change protection.
- `proofpress uninstall --confirm` removes managed integration and retains the store.

For project history, run `history project --project . --agent codex`. Use
`claude-code` or `cursor` for their local sessions. The CLI prompts
before local import. Then `consolidate --scope SCOPE --model-assessment --all`
explicitly sends pending excerpts to Codex and creates candidates. Omit `--all`
for a single batch. Manual review remains required. Model failure stops the run;
completed batches are preserved and retries resume. [Import guide](INTAKE.md)

[End-to-end local trial](LOCAL-ALPHA.md) explains trust, recovery and boundaries.
The explicit commands below remain available for scripts; owner actions require
an exact revision, digest, reason and human confirmation.

# CLI guide

For normal use, start with [agent setup](AGENTS.md). The commands below expose
the full local lifecycle; the examples are synthetic coding guidance.

## Install from a checkout

Python 3.11 or newer:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -e .
.venv/bin/proofpress --help
```

Activate the environment with `source .venv/bin/activate` to use `proofpress` in
the examples below. The uv tool install in the README needs no activation.

Install dependencies once; normal commands run offline. `--workspace` is a global
option and goes **before** the command. It defaults to `.judgment` in the current
directory. Store files are gitignored. Do not commit private sessions or stores.

## Run the manual loop

The examples are synthetic. Inspect the source JSON, provenance, conditions and
limits before using the explicit manual-review commands. Replace ID and DIGEST
with the values returned by capture. The local identities are self-asserted.
Paths under `examples/` assume a source checkout. Without one, `proofpress example`
prints an input you can adapt and the installed skill includes its own example.

If you have not run setup, initialize a store with `proofpress init --owner human:me`.
Skip initialization when setup already created it.

```sh
proofpress capture --from examples/coding.json
proofpress inbox
proofpress show ID --version 1

# Before admission, context contains no usable judgment.
proofpress context --scope coding/generated-files --facts examples/coding-facts.json \
  --actor agent:session-b --purpose 'Plan a synthetic generated-client change'

# Human operator only: bind review to the inspected revision and digest.
proofpress review ID --version 1 --digest DIGEST --admit \
  --reason 'Reviewed source, rationale and scope for this synthetic case' --confirm

proofpress context --scope coding/generated-files --facts examples/coding-facts.json \
  --actor agent:session-b --purpose 'Plan a synthetic generated-client change'

# New candidate; previous admission does not cover its changed contents.
proofpress revise ID --from examples/coding-v2.json \
  --base-digest DIGEST --reason 'Owner narrowed the scope'
proofpress show ID --version 2
```

Review version 2 with its **new digest**, using the same review command. Its
admission atomically supersedes version 1. While version 2 is pending, the old
admitted version remains usable if its conditions still hold. If the old version
is wrong, **withdraw it immediately** rather than wait for replacement review.

```sh
proofpress withdraw ID --version 2 --digest NEW_DIGEST \
  --reason 'This guidance is no longer applicable' --confirm
proofpress explain ID
proofpress audit
```

`review --reject` and `review --request-changes` also require a version, digest,
reason and confirmation. `revise` can replace a pending or changes-requested
candidate without changing its historical content. Rejected or withdrawn records
cannot simply be re-admitted; create and review a new revision.

## Reuse and stale receipts

`context` persists a receipt with the exact revision IDs/digests, scope, facts,
actor, purpose and policy digest. The output is supplied **advice**, not proof
that the model used it. Descriptive limits remain visible; they are not executable
predicates. A `constraint` kind does not install an execution binding.

```sh
proofpress check --receipt ctx_RECEIPT_ID --facts examples/coding-facts.json
```

`check` fails after withdrawal, supersession, expiry, invalid dependencies,
changed facts or policy, or when the receipt was empty. It checks stored state,
not caller-edited receipt content. Exit codes: **0** success, **2** invalid input
or rejected operation, **3** receipt no longer usable.

Conditions are conservative exact-scalar equality checks against supplied facts;
scope is exact, not semantic similarity. Missing facts fail closed. The caller
must obtain truthful facts from the actual environment. A model saying a fact is
true does not verify it. `check` and an external tool action are not atomic, and
it is separate from [host hook enforcement](RUNTIME.md).

## Import a TRACE record

```sh
proofpress import --session examples/trace-session.json \
  --event evt_001 --template examples/trace-template.json --recorded-by agent:importer
```

The bridge accepts one explicit decision from a TRACE 0.5.0/0.5.1 export. The
template supplies local applicability and presentation; the original statement,
rationale, explicit proposer and historical disposition are preserved. Source
digests refer to canonical parsed JSON, not raw file bytes or authenticated
signatures. Source `accepted` still becomes a **local candidate**, not admission.
This is a bounded mapper, not a full TRACE-session/schema validator or a live MCP
connection. See [upstream mechanisms](UPSTREAM.md).

## Defaults and trust

`proofpress policy` displays `.judgment/config.json`. Capture-origin filters are
enforced; prose capture guidance is for the agent to follow. Agents can propose explicit records during a session. To extract candidates
from selected local sessions, use the separate [history workflow](INTAKE.md).

Only manual admission is implemented. An `automatic` configuration is rejected,
not silently enabled. Future Owner-policy admission requires a separate design;
it must never be confused with a proposer approving itself.

**Local cooperative trust:** `--confirm` is an explicit operator gesture, not
authentication. Every process under your OS account can invoke the CLI or modify
the files. The owner label and hash chain do not isolate a malicious agent, prove
source truth, or prevent rewriting an entire store. See [security boundaries](../SECURITY.md).

## Agent setup and AJF

`proofpress setup --all --owner human:me` initializes a manual-only workspace and
installs the [bundled skill](../src/judgment_layer/skill/SKILL.md) into project
skill directories. See [agent setup](AGENTS.md) for individual hosts, dry runs,
existing-file preservation and remote execution. Package installation alone does
not change a host's configuration. No runtime hook is installed.

`proofpress example` prints a synthetic coding input to adapt. `proofpress schema`
prints the bundled complete AJF schema; neither opens or approves a workspace.
The [AJF specification](AJF.md) separates portable content from local governance.
The [architecture](ARCHITECTURE.md) describes state and eligibility.

There is no ADF auto-migration in this release. Existing ADF records and immutable
IDs remain unchanged; an explicit conversion needs human-defined applicability
and must preserve historical disposition without importing authority.

## Validate the implementation

```sh
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python examples/walkthrough.py --synthetic-review-fixture
```

Tests use temporary stores and synthetic manual-owner fixtures. They establish
mechanical lifecycle behavior, not judgment quality or real human approval.
No production traces are included. See [evaluation plan](../evals/README.md) for the
separate, not-yet-run notes comparison.

## Output

Default text stays concise even when piped. `--format agent` returns compact
JSON: context includes the receipt ID, judgment identity, full judgment text,
rationale and applicability. Historical events and source metadata stay in the
store. This is a projection, not a portable AJF record. `--json` (or `--format
json`) returns full data; `show ID` shows readable review details. Scripts that
previously relied on implicit JSON must now request `--json`.
