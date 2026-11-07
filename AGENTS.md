# Judgment Layer

Build the smallest useful single-person judgment lifecycle. Keep portable AJF
content separate from local review authority and current eligibility.

- Capture and revise create candidates. Do not add admission through editable
  record fields or agent instructions. Manual admission is the only v0 mode.
- Never run real owner review/withdrawal on a user's behalf without explicit
  authorization. Tests may use clearly labeled synthetic owner fixtures only.
- Keep revision content immutable, review bound to exact digests, stale edits
  rejected, and supersession atomic. Do not resurrect old versions after withdrawal.
- Scope/condition matching is conservative and factual inputs are caller-supplied.
  Never describe retrieval or `check` as a non-bypassable action gate.
- Same-OS-user identity is cooperative, not authenticated. Preserve SECURITY.md.
- Keep stores, credentials, private sessions and actual customer traces out of Git.
- Verify with unittest and the synthetic walkthrough. Benchmark benefits are
  unproven; source-level tests are not real-agent task-quality results.
- Preserve upstream provenance and licenses in NOTICE. Do not migrate ADF in place.
