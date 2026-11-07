# Agent Judgment Format — 0.1-draft

AJF is portable judgment content. The CLI completes `ajf_version`, a generated
`id`, `version: 1` and empty `links` when capturing a candidate. `validate` accepts
complete records only. Revisions receive the same ID, an increasing version and
an exact `revises` link. Capture does not infer reasons, origin or timestamps.

| Field | Meaning |
| --- | --- |
| name, version, description | Human-facing summary; also the generated YAML header |
| judgment | Statement, kind and recorded rationale (nullable when unknown) |
| applicability | Exact scope, scalar equality conditions, descriptive limits, optional validity window |
| provenance | Human/agent origin, recorder, recorded timestamp, capture method, source references |
| evidence | Supporting, challenging or contextual references; not automatically fetched or verified |
| links | Exact-digest prior revision or dependencies |
| extensions | Non-authoritative additional provenance; never interpreted as approval |

Kinds: `conditional_guidance`, `case`, `hypothesis`, `constraint`. Origin is
separate: `human_guidance`, `human_judgment`, `agent_judgment`, `agent_assumption`,
`unknown`. A human can record an agent's judgment and an agent can record human
guidance; recorder is not decision-maker. Unknown origin or missing rationale is
capturable but cannot be admitted under the v0 default. The human must create a
new supported revision rather than invent missing information.

Limits are **prose** and are not evaluated by the resolver. Put conditions that
must control inclusion into `when`. Fields in `when` are literal fact-map keys,
not executable expressions or dot-path access. Equality compares canonical JSON
scalars: `true` is not `1`, and `1` is distinct from `1.0`. All supplied conditions
must match. Expiry is exclusive. Scope is exact. There is no inferred conflict
detection, semantic matching, or automatic generalization.

Local governance events carry admission authority, content digest, policy digest,
owner and reason. They are **not** editable approval fields in AJF. Exporting an
AJF JSON record transports no receiver-local authorization. A historical TRACE
acceptance is provenance only. A local human can separately review their own
recorded judgment; an agent must never invoke owner actions on a real candidate.

JSON is the source of truth. Markdown rendering uses JSON-quoted YAML scalar
values and full JSON; editing the generated Markdown does not update the store.
New AJF semantics are not a new release of ADF or an in-place migration of it.
