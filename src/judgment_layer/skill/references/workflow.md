# Capture and reuse

Use the selected workspace argument from SKILL.md before each CLI command.
Keep temporary input files private and outside version control.

## Propose a judgment

Adapt coding.json or `judgment example` to the actual guidance. Use the real
timestamp, attribution and source references. Rationale describes a recorded
reason; do not fabricate an explanation. `judgment schema` prints the complete
schema. Capture fills in identity and first-version fields:

```sh
judgment --workspace PATH capture --from candidate.json
judgment --workspace PATH show ID --version 1 --format markdown
```

Capture returns the ID, version, digest and proposed state. Tell the human what
changed, why and the conditions they should inspect. Manual owner review happens
separately; an agent never invokes owner commands on real records.

## Supply applicable advice

Write a JSON object of task facts derived from the environment, not invented to
match a record. Example: `{"generated_file": true}`. Use exactly the same scope
as the applicable record, for example `coding/generated-files`.

```sh
judgment --workspace PATH context --scope coding/generated-files --facts facts.json \
  --actor agent:assistant --purpose 'Plan a generated client change'
judgment --workspace PATH check --receipt RECEIPT_ID --facts facts.json
```

The receipt records what was supplied, not whether the agent followed it. Scope
and scalar conditions match exactly; prose limits need interpretation. Empty
context supplies no advice. A failed check means the receipt cannot be reused.

## Revise a judgment

Inspect `show ID` for the latest digest. Prepare new content without the generated
ID, version or revises link; preserve sources and explain the changed conditions.

```sh
judgment --workspace PATH revise ID --from revised.json --base-digest DIGEST \
  --reason 'Explain the new evidence or changed condition'
```

The new version is another candidate. The old admitted version stays active until
the human admits the replacement or withdraws the old version. Ask the owner to
withdraw incorrect guidance promptly. Never silently broaden or auto-admit it.
