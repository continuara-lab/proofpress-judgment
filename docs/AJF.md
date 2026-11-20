# Agent Judgment Format (AJF)

AJF is a portable JSON format for a judgment. A record explains **what was
chosen, why, when it applies, and where it came from**. It can also record the
original situation, alternatives and expected outcome.

[JSON schema](../src/judgment_layer/ajf.schema.json) ·
[Contextual capture example](../examples/contextual-judgment.json)

The behavior-capable draft is `0.4-draft`; records without the new fields still default to `0.3-draft`. Start with `proofpress example` or the
contextual example above. `proofpress capture --from FILE` creates a candidate
and supplies its initial ID, version and links. Use `proofpress schema` to print
the schema or `proofpress validate FILE` to validate a complete record.
A revision keeps the same ID, increments the version and links to the exact
prior digest. Proofpress keeps approval and observed outcomes in the project store. Optional
behavior declarations travel with AJF; legacy bindings remain local.

| Field | Meaning |
| --- | --- |
| name, version, description | Human-facing summary; also the generated YAML header |
| judgment | Statement, kind and recorded rationale (nullable when unknown) |
| applicability | Exact scope, scalar equality conditions, descriptive limits, optional validity window; 0.4 adds optional semantic task criteria |
| behavior | Optional context, hook declarations, built-in/semantic verifiers, artifact paths and failure handling |
| provenance | Human/agent origin, recorder, recorded timestamp, capture method, source references |
| evidence | Supporting, challenging or contextual references; not automatically fetched or verified |
| links | Exact-digest prior revision or dependencies |
| context | Original situation, goal, constraints and background facts |
| alternatives | Other options and recorded reasons they were passed over |
| expected_outcome | Intended effect and optional verification approach |
| extensions | Additional metadata with no approval authority |

Kinds: `conditional_guidance`, `case`, `hypothesis`, `constraint`. Origin is
separate: `human_guidance`, `human_judgment`, `agent_judgment`, `agent_assumption`,
`unknown`. A human can record an agent's judgment and an agent can record human
guidance; recorder is not necessarily the person or agent who made the judgment. Unknown origin or missing rationale is
capturable but cannot be admitted under the v0 default. The human must create a
new supported revision rather than invent missing information.

Limits are **prose** and are not evaluated by the resolver. Put conditions that
must control inclusion into `when`. Fields in `when` are literal fact-map keys,
not executable expressions or dot-path access. Equality compares canonical JSON
scalars: `true` is not `1`, and `1` is distinct from `1.0`. All supplied conditions
must match. Expiry is exclusive. Scope is exact. The ordinary `context` resolver does not evaluate prose task criteria. The
behavior task resolver explicitly assesses 0.4 task criteria after checking known
factual conditions; that semantic decision can be wrong and unknown pauses.
There is no automatic generalization.

Local governance events carry admission authority, content digest, policy digest,
owner and reason. They are **not** editable approval fields in AJF. Exporting an
AJF JSON record transports no receiver-local authorization. A historical TRACE
acceptance is provenance only. A local human can separately review their own
recorded judgment; an agent must never invoke owner actions on a real candidate.

JSON is the source of truth. Markdown rendering uses JSON-quoted YAML scalar
values and full JSON; editing the generated Markdown does not update the store.
New AJF semantics are not a new release of ADF or an in-place migration of it.

Version 0.2 uses `provenance.judged_by`. Version 0.1 with `decision_maker`
remains readable and verifiable. New captures default to 0.3. Existing records
and digests are preserved.

Optional `judgment.assertion` has a `key` and a scalar `value`. This provides an
explicit shared subject for deterministic conflict checks; it does not turn prose
into a verifier or grant authority. Contradictory assertions in overlapping scopes
are flagged and pause admission/reuse until resolved. Natural-language conflicts
need separate optional assessment. See [runtime checks](RUNTIME.md).

AJF 0.3 adds contextual fields, alternatives, expected outcomes and judgment
polarity. Outcome observations are separate append-only events. See [intake and
observations](INTAKE.md). Existing 0.1/0.2 digests are never rewritten.

## AJF 0.4: behavior belongs to the judgment

See the [capture JSON example](../examples/behavior-judgment.json) and
[execution guide](BEHAVIOR.md). `behavior` is optional; it does not convert every
captured lesson into a mandatory check. Its supported fields are:

| Field | Meaning |
| --- | --- |
| `context` | Domain context supplied with selected judgments; untrusted advice, not executable instructions |
| `hooks` | Nonempty list of event/check declarations |
| `hooks[].event` | `before_execution`, `before_action`, or `before_delivery` |
| `hooks[].match` | For actions: `direct_file_edit` and project-relative path patterns |
| `hooks[].activation` | Actions use `scope_and_conditions`, independently of task semantic selection |
| `hooks[].verifier` | `builtin` (`deny_action` or `require_conditions`, version 1) for actions; `semantic` with criteria for plan/delivery |
| `artifacts` | Delivery review's `paths` plus exact `required` files; mandatory with a delivery hook |
| `on_violation` | Supported value: `block_and_request_repair` |
| `on_unknown` | Supported value: `pause_for_review` |
| `allow_exceptions` | Optional; false by default. All selected delivery judgments must allow an exact-artifact human exception |

Private integration paths, `.env` files, traversal, unsupported event/verifier
combinations and custom commands are rejected. `limits` remains prose. Artifact
coverage is explicit and bounded, not a whole-trajectory audit.

The local workspace supplies the project boundary; each judgment still carries
its exact scope namespace. Optional `task_criteria` is assessed per admitted
behavior-bearing record, not by top-k retrieval. Known facts come from a human
connection setting or caller-owned integration, never from a model inventing them.

Changes to matching criteria, context or checks change the revision digest and
require a new review. Old AJF records/digests are never rewritten. Neither a JSON
approval field nor a successful verifier can grant admission. Importing a behavior
record creates a candidate. A receiving project reviews it before activation.
