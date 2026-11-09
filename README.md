# Proofpress

**Your judgment. Built into your agents.**

Everything is recorded. Your agent still repeats the same mistakes.
Proofpress helps carry your guidance and agent experience into later work—as
judgments you can review, reuse and update.

**This is the local Proofpress CLI, currently in private alpha.**
[Website](https://proofpress.dev) · [Quick start](#quick-start) ·
[Agent instructions](docs/AGENT-SETUP.md) · [Documentation](#documentation)

## What is a judgment?

A choice worth carrying forward, with its reasons and boundaries. For example:

> **Change the schema. Regenerate the client.**
> **Why:** Hand edits to generated files are overwritten.
> **When:** Changing generated clients in this project.

The same pattern works for design standards, sales qualification and slide reviews.
Capture your judgments and the agent's own consequential choices. Review what
should guide later work; revise or withdraw it when conditions change.

## Quick start

Requires macOS or Linux, Git, and access to this private repository.
The installer handles Python and the CLI. Already using the older Proofpress CLI?
Use a [separate environment](docs/INSTALL.md#keep-existing-proofpress-installations-separate).

**Run these in the project where you use your agent:**

```sh
git clone https://github.com/continuara-lab/judgment-layer.git "$HOME/.local/share/proofpress-cli"
bash "$HOME/.local/share/proofpress-cli/install.sh"
```

This enables Codex guidance and creates a local `.judgment/` folder for records,
review history and settings. Follow any PATH instruction the installer prints.
For another agent, see [agent setup](docs/AGENTS.md).

Start a new agent session in the same project and say:

> Use Proofpress. Propose useful judgments from my guidance and your work, with
> reasons, sources and conditions. Use approved judgments before related tasks.
> Leave approval to me.

When your agent proposes a judgment, review it in your terminal:

```sh
proofpress review
```

Choose a candidate from the numbered inbox. Read it, edit it if needed, then approve
or reject it. **You approve before reuse.** Capture is agent guidance, not an
automatic listener for every message.

## The everyday loop

| Step | What you do |
| --- | --- |
| **Capture & review** | Keep a useful judgment, check its basis and choose where it applies. |
| **Reuse** | Supply approved, current judgments to later tasks whose conditions match. |
| **Learn** | Attach outcome observations to the exact version for later inspection. |
| **Update** | Revise or withdraw guidance as evidence and conditions change. |

```sh
proofpress configure     # Choose what the agent may propose
proofpress edit ID       # Edit in your preferred editor; creates a new candidate
proofpress withdraw ID   # Stop an admitted judgment from being reused
proofpress doctor        # Inspect skills, hooks and active bindings
```

Sources, versions and review history stay inspectable. An edit needs fresh review.
Reuse currently matches explicit scopes and factual conditions.
[Full walkthrough](docs/LOCAL-ALPHA.md)

<details>
<summary><strong>Import a project's past Codex sessions</strong></summary>

```sh
proofpress history project --project /path/to/project --days 7
proofpress consolidate --scope coding --model-assessment --all
proofpress review
```

Import asks before storing redacted excerpts locally. Extraction sends those
excerpts to Codex and follows your capture settings. It produces candidates for
review. Redaction may miss sensitive details. [History guide](docs/INTAKE.md)

</details>

<details>
<summary><strong>Enforce a judgment with a hook</strong></summary>

Choose **Enforcement** during review to inspect and approve the proposed protection
together with the judgment. Then install the host hook:

```sh
proofpress hooks install --host codex             # Preview
proofpress hooks install --host codex --confirm   # Install
```

Restart Codex, trust the project and review the hook in `/hooks`. Supported checks
cover protected paths, lifecycle/conditions and optional decision model assessment.
Shell, MCP and unsupported routes pause while bindings are active. These are
cooperative local hooks; host trust and tool coverage matter.
[Enforcement and recovery](docs/RUNTIME.md)

</details>

## Documentation

[Installation](docs/INSTALL.md) · [Agent setup](docs/AGENT-SETUP.md) ·
[CLI reference](docs/CLI.md) · [AJF records](docs/AJF.md) ·
[Evaluation](evals/README.md) · [Security](SECURITY.md) · [License](LICENSE)

For agents: read the installed `proofpress` skill for this project's workspace
and capture settings. Use `--format agent` for compact output; `--json` expands
full records. Agents propose and retrieve; humans control admission and enforcement.

This repository develops the personal CLI. The [public Proofpress repository](https://github.com/chenmingtang830/proofpress)
contains the existing MCP/server implementation and research. Their installation
commands and stores differ. [Repository map](docs/REPOSITORIES.md)
