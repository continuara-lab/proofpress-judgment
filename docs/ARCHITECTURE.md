# Small local architecture

One Python package. One SQLite database. Three concepts:

1. **Immutable revision:** validated AJF with an exact canonical JSON digest.
2. **Provenance/governance event:** linked to an exact revision, recorded in a
   hash-linked journal. Source identities are declarations.
3. **Current projection:** derived state (`proposed`, `needs_changes`, `admitted`,
   `rejected`, `superseded`, `withdrawn`), plus read-time scope, conditions, time
   validity and exact-version dependency eligibility.

Every CLI operation opens a transaction, checks stored record/journal integrity,
and serializes with `BEGIN IMMEDIATE`. Review binds a human-inspected digest and
version; admission and predecessor supersession commit together. Revision checks
the expected latest base digest to avoid silently linking a stale edit to a new
base. Withdrawing v2 never resurrects v1.

A pending revision does not itself invalidate a previously admitted revision.
Explicitly withdraw incorrect active guidance. Revisions of pending candidates
replace the pending candidate, not its immutable content. Dependencies never
silently advance to a newer version. A dependency becoming withdrawn, expired,
superseded or inapplicable blocks its consumer at read/check time.

Receipts bind supplied record versions, facts and policy. They record supply,
not actual reliance or real-world outcomes. `check` re-evaluates them and returns
nonzero for empty context. No executable hooks, host authentication, automatic
admission, LLM extraction, cross-project sharing or outcome-learning module ships.

The portable skill is a workflow aid. Initial installation is from a source
checkout; there is no PyPI publication or host marketplace release. SQLite scans
and full integrity verification favor auditability over scale in this small v0.

Next work should follow usage: one host adapter with tested invocation, a
comfortable terminal review flow, bounded ADF import, and a fair memory-notes
experiment. Strong owner/agent isolation requires a different authority boundary,
not another command-line flag.
