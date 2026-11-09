# Proofpress

**Your team's judgment. Built into your agents.**

You corrected your agent. It acknowledged. Days later, the same mistake—even
with the guidance in memory and skills.

Proofpress turns your guidance and agent experience into judgments you can
review, reuse, revise and enforce on selected actions.

## Start in your project

```sh
bash /path/to/judgment-layer/install.sh
```

The installer handles Python and the CLI, then enables Codex guidance in the
current project. Private alpha: authenticated repository access is required.
[Other installation options](docs/INSTALL.md)

```sh
proofpress configure       # Choose what the agent may propose
proofpress doctor          # Check this project's actual integration state
```

Start a new agent session and ask:

> Use Proofpress. Propose useful judgments from my guidance and your experience.
> Retrieve approved judgments before related work.

Capture is agent guidance; it does not listen to every message in the background.
You approve before reuse. [Connect another agent](docs/AGENTS.md)

## Review once. Reuse when it applies.

| Work | Judgment |
| --- | --- |
| Coding | Change the schema; regenerate the client. |
| Design | Use our existing components before adding new ones. |
| Sales | Verify a buying signal before using it in outbound. |
| Slides | One claim per slide; show the evidence. |

```sh
proofpress inbox
proofpress review ID        # Read, edit, choose enforcement, then approve
proofpress edit ID          # Create a new candidate revision in your editor
```

Review shows the judgment, reasons, situation, conditions, sources and proposed
enforcement together. Approval and the displayed binding commit together.
An edit creates a candidate; it never carries approval forward.

## Bring in project history

```sh
proofpress history project --project /path/to/project --days 7
proofpress consolidate --scope coding --model-assessment --all
proofpress inbox
```

Import asks before saving redacted Codex excerpts locally. Extraction explicitly
sends those excerpts to Codex, follows your capture settings, and creates candidates
for review. Redaction does not guarantee removal of all sensitive information.
Use a narrow scope and inspect conditions before admitting a historical judgment.
[History and capture settings](docs/INTAKE.md)

## Enforce selected actions

Choose **Enforcement** during `proofpress review ID`, then install a project hook:

```sh
proofpress hooks install --host codex             # Preview
proofpress hooks install --host codex --confirm   # Install
```

Restart Codex, trust the project, and review the exact hook in `/hooks`.
Installation does not grant host trust. Claude Code registration is also available
with `--host claude-code`.

Hooks check protected paths before supported tool actions. They can block generated
file edits, check lifecycle and factual conditions, or assess complete new-file
content with a configured decision model. Shell, MCP and unsupported routes pause
while bindings are active. A check passing is separate from task success.

```sh
proofpress doctor
proofpress pause --confirm          # Explicitly suspend enforcement
proofpress resume --confirm
proofpress unbind ID --confirm       # Explicitly remove this protection
proofpress uninstall --confirm       # Remove integration; keep the judgment store
```

Withdrawal or supersession makes old bindings block until you review/rebind or
explicitly unbind. These are cooperative local hooks, not a security boundary
against the same OS user or disabled host hooks. [Runtime and recovery](docs/RUNTIME.md)

## Inspect what applies

```sh
proofpress match --scope coding --facts task-facts.json
```

Reuse checks exact scope, explicit facts, lifecycle, dependencies and conflict
holds. It does not infer general task equivalence from text similarity. Missing
facts exclude a judgment. Optional model assessment can flag nuanced conflicts;
it never approves a candidate.

Human output stays concise with bold brand colors. `--format agent` supplies
compact JSON; `--json` expands full records. `NO_COLOR=1` disables styling.

[CLI guide](docs/CLI.md) · [AJF format](docs/AJF.md) ·
[Local testing](docs/LOCAL-ALPHA.md) · [Security](SECURITY.md) ·
[Evaluation plan](evals/README.md)

Local alpha · Manual admission · Apache-2.0

The Python distribution remains `judgment-layer`; the product command is
`proofpress`. Use an isolated environment alongside older Proofpress installations.
Benefits over well-maintained memory notes remain to be measured.
