# Mechanisms retained, dependencies bounded

| Source | Mechanism used | Deliberate boundary |
| --- | --- | --- |
| TRACE | Human/agent proposer distinct from recorder; original events and disposition; corrections/revision provenance | One explicit exported decision at a time; no automatic MCP capture or ungated trace-learn recall |
| Proofpress | Candidate/admission separation; exact-revision review; lifecycle events; eligible context; stale-receipt recheck | New small local implementation; no hosted service, multi-tenant auth or full policy engine dependency |
| ADF | Readable summary, basis, applicability, provenance and version links | AJF draft is separate; no transparent conversion of prose conditions or historical acceptance |

Pinned inspected revisions are in NOTICE. The relevant Proofpress functions are
`review_v2`, `auto_admit_v2`, `supersede_v2`, `withdraw_v2`, `context_v2` and the
run/context receipt operations in `src/proofpress/kernel/operations.py`.

Upstream Proofpress has Owner-controlled auto-admission. V0 intentionally does
not transplant its hosted authority/credential machinery into a CLI flag.
Upstream TRACE has learning extraction/recall and hooks; neither grants this
store's admission or guarantees capture completeness. A user must ensure a host
does not inject unadmitted trace-learn content while claiming governed reuse.

TRACE import verifies only the selected bounded mapping, requires explicit
applicability, preserves source/event canonical digests and stores historical
disposition as non-authoritative metadata. It does not load files referenced by
the source or treat a source's claimed human identity as authenticated.
