# Capture and reuse

Use the selected workspace argument from SKILL.md before each CLI command.
Keep temporary input files private and outside version control.

## Propose a judgment

Adapt coding.json or `proofpress example` to the actual guidance. Use the real
timestamp, attribution and source references. Rationale describes a recorded
reason; do not fabricate an explanation. `proofpress schema` prints the complete
schema. Capture fills in identity and first-version fields:

```sh
proofpress --workspace PATH capture --from candidate.json
proofpress --workspace PATH show ID --version 1
```

Capture returns the ID, version, digest and proposed state. Tell the human what
changed, why and the conditions they should inspect. Manual owner review happens
separately; an agent never invokes owner commands on real records.

## Supply applicable advice

Write a JSON object of task facts derived from the environment, not invented to
match a record. Example: `{"generated_file": true}`. Use exactly the same scope
as the applicable record, for example `coding/generated-files`.

```sh
proofpress --workspace PATH context --scope coding/generated-files --facts facts.json \
  --actor agent:assistant --purpose 'Plan a generated client change' --format agent
proofpress --workspace PATH check --receipt RECEIPT_ID --facts facts.json
```

The receipt records what was supplied, not whether the agent followed it. Scope
and scalar conditions match exactly; prose limits need interpretation. Empty
context supplies no advice. A failed check means the receipt cannot be reused.

## Revise a judgment

Inspect `show ID` for the latest digest. Prepare new content without the generated
ID, version or revises link; preserve sources and explain the changed conditions.

```sh
proofpress --workspace PATH revise ID --from revised.json --base-digest DIGEST \
  --reason 'Explain the new evidence or changed condition'
```

The new version is another candidate. The old admitted version stays active until
the human admits the replacement or withdraws the old version. Ask the owner to
withdraw incorrect guidance promptly. Never silently broaden or auto-admit it.

Default output is concise text, also in pipes. Use `--format agent` for small
JSON results, `show ID` for review, and `--json` only when full records are needed.
Do not repeatedly load the schema or history during reuse.

## Context-first enforcement workflow

When an owner has configured a workflow, get `task-prepare` context before writing
a plan. Submit that plan using the exact context id with `task-plan`. Attach the
actual host session with `task-attach` when using the explicit Codex/Cursor bridge.
Claude lifecycle hooks can supply task context and session attachment automatically.

`task-status` identifies whether context, source execution or delivery is paused.
A failed output check leaves repair writes available when the plan is still valid.
Recheck with `task-finish-files`; `task-export` gates the actual local file bundle.
Never invoke owner workflow changes or confirm an artifact exception on the user's
behalf. CLI/skill guidance alone is not interception; inspect installed hooks and
read the workflow coverage in docs/TASK-BOUNDARIES.md before claiming enforcement.
