# Proofpress

**Your judgment. Built into your agents.**

Everything is recorded. Your agent still repeats the same mistakes.
Proofpress helps carry your guidance and agent experience into later work—as
judgments you can review, reuse and update.

**The open-source judgment layer for agents.**
[Website](https://proofpress.dev) · [Quick start](#quick-start) ·
[Agent instructions](docs/AGENT-SETUP.md) · [Documentation](#documentation)

## What is a judgment?

A choice worth carrying forward, with its reasons and boundaries. For example:

> **Cache search results. Recheck file access.**
> **Why:** Older results are acceptable. Exposing private files is not.
> **When:** Public results and previews.
> **Excludes:** Private content and access checks.

The same pattern works for design standards, sales qualification and slide reviews.
Capture your judgments and the agent's own consequential choices. Review what
should guide later work; revise or withdraw it when conditions change. If search
later powers urgent alerts, update the judgment: **Cache public results. Keep
urgent alerts live.**

## Quick start

Requires macOS or Linux and Git. The installer handles Python and the CLI. Already using the older Proofpress CLI?
Use a [separate environment](docs/INSTALL.md#keep-existing-proofpress-installations-separate).

**Run this in the project where you use your agent:**

```sh
curl -fsSL https://raw.githubusercontent.com/continuara-lab/proofpress-judgment/main/install.sh | bash
```

This enables Codex guidance and creates a local `.judgment/` folder for records,
review history and settings. Follow any PATH instruction the installer prints.
Choose an agent below, then start a fresh session in this project.

## Connect your coding agent

| Agent | Enable project guidance | Optional enforcement |
| --- | --- | --- |
| **Codex** | Enabled by the installer | `proofpress hooks install --host codex --confirm`, then review `/hooks` in Codex |
| **Claude Code** | `proofpress onboard --agents claude-code` | `proofpress hooks install --host claude-code --confirm`, then review hooks in Claude Code |
| **Cursor** | `proofpress onboard --agents cursor` | `proofpress hooks install --host cursor --confirm`; [Cursor coverage](docs/CURSOR.md) |

Confirm onboarding in your terminal. Guidance helps agents propose and retrieve
judgments; hooks check supported actions before execution.
[Integration details](docs/AGENTS.md)

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
[Evaluation](evals/README.md) · [Contributing](CONTRIBUTING.md) ·
[Security](SECURITY.md) · [License](LICENSE)

For agents: read the installed `proofpress` skill for this project's workspace
and capture settings. Use `--format agent` for compact output; `--json` expands
full records. Agents propose and retrieve; humans control admission and enforcement.

This repository develops the personal CLI. The [public Proofpress repository](https://github.com/chenmingtang830/proofpress)
contains the existing MCP/server implementation and research. Their installation
commands and stores differ. [Repository map](docs/REPOSITORIES.md)
