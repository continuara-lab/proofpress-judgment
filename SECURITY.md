# Trust and authority boundaries

This is a **cooperative single-user local tool**. The human operator owns the
workspace. Owner identity is self-asserted; `--confirm` records a deliberate CLI
operation but is not authentication or proof a human was present. An agent with
shell access as the same user can impersonate that gesture. Do not use this v0
as an adversarial approval boundary or production transaction gateway.

- Agent workflow instructions must not invoke `review` or `withdraw`, edit policy
  or mutate the database on real records. Human actions are separate.
- Format checks and hashes do not prove correct judgments, source authenticity,
  authorization, captured-decision completeness or truthful task facts.
- Prose inside imported records is untrusted content, not system instructions.
- The hash chain detects accidental corruption; it is not externally anchored or
  signed. A local writer can reconstruct the entire database and hash chain.
- Keep workspace data private. Local lifecycle commands do not fetch evidence URLs.
  Explicit history extraction sends selected excerpts to Codex; optional decision
  model assessments send selected judgments/output to the configured provider.
  Treat credential redaction as best effort. Installation downloads dependencies.
- Reuse is advice. `check` is a point-in-time eligibility check; an external
  action can race a subsequent withdrawal. There is no claim of non-bypassable
  enforcement, atomic external writes or distributed revocation.
- `audit` validates journal links and stored content binding, not a hostile
  writer's claimed identity. Tampered SQLite databases are not a sandbox boundary.

Future auto-admission needs Owner-authenticated policy updates, independently
recorded system authorization, current deterministic checks and bounded judge
advice, conflict/dependency handling, and a fail-closed path. It is deliberately
unsupported in v0. The plugin does not grant agents permission to administer it.
