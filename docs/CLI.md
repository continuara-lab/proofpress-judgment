# CLI guide

Run these commands from the repository root after installing the package.

## Install from a checkout

Python 3.11 or newer:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -e .
.venv/bin/judgment --help
```

Install dependencies once; normal commands run offline. `--workspace` is a global
option and goes **before** the command. It defaults to `.judgment` in the current
directory. Store files are gitignored. Do not commit private sessions or stores.

## Run the manual loop

The examples are synthetic. Inspect the source JSON, provenance, conditions and
limits before using the explicit manual-review commands. Replace ID and DIGEST
with the values returned by capture. The local identities are self-asserted.

```sh
.venv/bin/judgment init --owner human:me
.venv/bin/judgment capture --from examples/billing.json
.venv/bin/judgment inbox
.venv/bin/judgment show ID --version 1 --format markdown

# Before admission, context contains no usable judgment.
.venv/bin/judgment context --scope support/billing --facts examples/facts.json \
  --actor agent:session-b --purpose 'Route a synthetic dispute'

# Human operator only: bind review to the inspected revision and digest.
.venv/bin/judgment review ID --version 1 --digest DIGEST --admit \
  --reason 'Reviewed source, rationale and scope for this synthetic case' --confirm

.venv/bin/judgment context --scope support/billing --facts examples/facts.json \
  --actor agent:session-b --purpose 'Route a synthetic dispute'

# New candidate; previous admission does not cover its changed contents.
.venv/bin/judgment revise ID --from examples/billing-v2.json \
  --base-digest DIGEST --reason 'Owner narrowed the scope'
.venv/bin/judgment show ID --version 2
```

Review version 2 with its **new digest**, using the same review command. Its
admission atomically supersedes version 1. While version 2 is pending, the old
admitted version remains usable if its conditions still hold. If the old version
is wrong, **withdraw it immediately** rather than wait for replacement review.

```sh
.venv/bin/judgment withdraw ID --version 2 --digest NEW_DIGEST \
  --reason 'This guidance is no longer applicable' --confirm
.venv/bin/judgment explain ID
.venv/bin/judgment audit
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
.venv/bin/judgment check --receipt ctx_RECEIPT_ID --facts examples/facts.json
```

`check` fails after withdrawal, supersession, expiry, invalid dependencies,
changed facts or policy, or when the receipt was empty. It checks stored state,
not caller-edited receipt content. Exit codes: **0** success, **2** invalid input
or rejected operation, **3** receipt no longer usable.

Conditions are conservative exact-scalar equality checks against supplied facts;
scope is exact, not semantic similarity. Missing facts fail closed. The caller
must obtain truthful facts from the actual environment. A model saying a fact is
true does not verify it. `check` and an external tool action are not atomic, and
this release installs **no runtime hooks or action interception**.

## Import TRACE provenance

```sh
.venv/bin/judgment import-trace --session examples/trace-session.json \
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

`judgment policy` displays `.judgment/config.json`. Capture-origin filters are
enforced; prose capture guidance is for the agent to follow. This version does
not extract decisions from free-form chat automatically. A user or an agent must
write an explicit record or invoke the TRACE importer.

Only manual admission is implemented. An `automatic` configuration is rejected,
not silently enabled. Future Owner-policy admission requires a separate design;
it must never be confused with a proposer approving itself.

**Local cooperative trust:** `--confirm` is an explicit operator gesture, not
authentication. Every process under your OS account can invoke the CLI or modify
the files. The owner label and hash chain do not isolate a malicious agent, prove
source truth, or prevent rewriting an entire store. See [security boundaries](../SECURITY.md).

## Plugin and AJF

- [Agent workflow skill](../plugins/judgment-layer/skills/judgment-layer/SKILL.md):
  a portable instruction bundle, not an installed host integration. No client
  configuration is changed by installation of the Python package.
- [AJF specification](AJF.md): portable content is separate from local governance.
- [JSON Schema](../src/judgment_layer/ajf.schema.json): the bundled validation source.
- [Architecture and scope](ARCHITECTURE.md): state, receipts and next boundaries.

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
