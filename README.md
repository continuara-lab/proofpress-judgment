<p align="center">
  <img src="assets/logo.svg" alt="Proofpress logo" width="88" height="88">
</p>

# Proofpress

**Your judgment. Built into your agents.**

Everything is recorded. Your agent still repeats the same mistakes.
Proofpress helps carry your guidance and agent experience into later work—as
judgments you can review, reuse and update.

**The open-source judgment layer for agents.**
[Website](https://proofpress.dev) · [Quick start](#quick-start) ·
[Import past sessions](#import-past-sessions) · [Enforcement](#enforce-judgments) · [Docs](#documentation)

## What is a judgment?

A choice worth carrying forward, with its reasons and boundaries. For example:

> **Cache search results. Recheck file access.**
> **Why:** Older results are acceptable. Exposing private files is not.
> **When:** Public results and previews.
> **Excludes:** Private content and access checks.

A judgment can shape one task or guide a project over time. Keep the choice,
the tradeoff behind it and the conditions that would change it. A judgment can also
carry its task-matching criteria, context, action constraints, plan/delivery checks
and what to do when a check fails. Both you and
an agent can propose judgments. If search starts powering urgent alerts, the
tradeoff changes. **Cache public results. Keep urgent alerts live.**

## Quick start

Run your agent's command from the project where you work. Requires macOS or
Linux and Git. The installer sets up Python, Proofpress, the project's
`.judgment/` store and the guidance for your agent. [Installation details](docs/INSTALL.md)

### Codex

```sh
curl -fsSL https://raw.githubusercontent.com/continuara-lab/proofpress-judgment/main/install.sh | bash -s -- --agents codex
```

### Claude Code

```sh
curl -fsSL https://raw.githubusercontent.com/continuara-lab/proofpress-judgment/main/install.sh | bash -s -- --agents claude-code
```

### Cursor

```sh
curl -fsSL https://raw.githubusercontent.com/continuara-lab/proofpress-judgment/main/install.sh | bash -s -- --agents cursor
```

The installer shows the project policy. Use it as shown or customize what the
agent may propose. Start a fresh session in the project and give your agent a task. The project
instructions tell it when to look up approved judgments and propose new ones.
[Commands for other agents](docs/AGENTS.md#install-by-agent)

When your agent proposes a judgment, review it in your terminal:

```sh
proofpress review
```

Choose a candidate from the numbered inbox. Read it, edit it if needed, then approve
or reject it. **You approve before reuse.** Capture is agent guidance, not an
automatic listener for every message.

## How it works

An agent proposes a judgment from work in a session. You review it once. Later
sessions can look up the current approved version when the scope and conditions
match. With enforcement connected, Proofpress reads the checks declared inside
that judgment: provide context before planning, check relevant actions, and review
actual artifacts before delivery. No separate workflow configuration is required.
You can record outcomes and revise or withdraw guidance as conditions change.
[Architecture and storage](docs/ARCHITECTURE.md)

### From reviewed judgment to behavior

| Stage | What happens | Boundary |
| --- | --- | --- |
| **Review** | You inspect the judgment, rationale, conditions and optional behavior together. | Approval covers the exact revision, including its checks. |
| **Before execution** | The project-local judgment inventory is evaluated using known facts and optional task criteria; relevant context is supplied before a declared plan check. | Semantic task matching can be wrong; uncertainty pauses. |
| **During execution** | Only matching action rules run, such as rejecting a direct edit to generated files. | These checks are deterministic; they do not call a model per tool action. |
| **Before delivery** | Declared delivery checks review actual files within the judgment's artifact paths, including new files and deletions. | Failed or uncertain checks keep delivery unapproved; repairs require rechecking. |

Hooks declare **when** to check; verifiers declare **how** to check. They belong to
the judgment. A host connection supplies events and honors the results.
[Architecture](docs/ARCHITECTURE.md) · [Behavior and examples](docs/BEHAVIOR.md)

## Agent Judgment Format (AJF)

AJF is the portable JSON format for a judgment. Version `0.4-draft` adds optional
`applicability.task_criteria` and `behavior`: context, hooks, verifiers, artifact
coverage and failure handling. Existing 0.1–0.3 records remain readable and their
digests are unchanged. Advice-only records do not acquire checks automatically.

Most judgments are one JSON document. Built-in rules and semantic check criteria
need no additional code. This version **does not execute custom verifier scripts**.
Approvals, task sessions and check receipts remain local records; importing JSON
does not import authority.

[Format guide](docs/AJF.md) · [JSON schema](src/judgment_layer/ajf.schema.json) ·
[Judgment with behavior](examples/behavior-judgment.json)

## Import past sessions

Run the command for the agent whose local history you want to import. Each
command previews the last seven days and asks before saving excerpts locally.

**Codex**

```sh
proofpress history project --project . --agent codex
```

**Claude Code**

```sh
proofpress history project --project . --agent claude-code
```

**Cursor**

```sh
proofpress history project --project . --agent cursor
```

To turn the imported excerpts into candidates, use the separate extraction step.

```sh
proofpress consolidate --scope coding --model-assessment --all
proofpress review
```

Extraction sends excerpts to Codex, including when the source is Claude Code or
Cursor. Redaction is best effort. [Supported transcripts and import guide](docs/INTAKE.md)

## Enforce judgments

Start with a judgment that declares its own checks. This prints a synthetic
example to adapt; capture proposes it and human review approves the whole revision:

```sh
proofpress example --behavior > judgment.json
proofpress capture --from judgment.json
proofpress review
```

Connect the project once. No workflow JSON or separate per-judgment binding is
needed for these embedded checks. Preview first, then install with `--confirm`:

```sh
proofpress enforce install --host claude-code
proofpress enforce install --host claude-code --confirm
```

Claude Code receives task context on prompt submission, checks covered actions,
and reviews declared artifacts plus the final response on Stop. Start a new
session and complete the host's trust flow. Protocol fixtures cover this new
path; live-host lifecycle verification is still pending. Stop cannot retract
streamed text or prevent an earlier external side effect.

For Codex or Cursor, `enforce install --host codex|cursor --confirm` installs the
action adapter. Task preparation/session attachment and completion checks still
need explicit integration; see the [CLI example](docs/BEHAVIOR.md#codex-and-cursor).

Run `proofpress doctor` to inspect connections, judgment checks and observed
actions. An installed entry may receive every tool event, but only matching
checks run; normal semantic plan/delivery review is aggregated at task boundaries,
with extra calls for task recognition and retries. Unsupported shell/MCP routes
pause rather than being assumed safe. Arbitrary generator/test/build commands are
not covered yet. Existing explicit bindings/workflow commands remain advanced
compatibility interfaces. [Coverage and recovery](docs/BEHAVIOR.md)

### Optional Jev checks — bring your own key

**Bring your own TypeSafe API key** to use Jev for judgments that need
interpretation of meaning, context or exceptions.

- **Review a candidate.** Assess whether its evidence and scope meet your project's review criteria, then give you an approval recommendation.
- **Check for conflicts.** Assess whether a proposed judgment contradicts approved guidance under overlapping conditions.
- **Apply declared behavior.** Evaluate task criteria and aggregate plan/delivery checks when a reviewed judgment requests them. These inputs can include task text, plans and declared artifact contents.

For example, “cache all search results” needs review if approved guidance
requires urgent alerts to use live data. Jev can assess that overlap and
recommend narrowing the judgment.

You decide which judgments to admit. Local path and condition checks work
without a key.
[Set up Jev](docs/RUNTIME.md#set-up-jev) · [Supported hook checks](docs/RUNTIME.md#what-the-hook-checks) · [Environment template](.env.example)

## Documentation

[Installation](docs/INSTALL.md) · [Agent setup](docs/AGENT-SETUP.md) ·
[CLI reference](docs/CLI.md) · [Architecture](docs/ARCHITECTURE.md) · [AJF](docs/AJF.md) ·
[Local walkthrough](docs/LOCAL-ALPHA.md) · [Evaluation](evals/README.md) · [Contributing](CONTRIBUTING.md) ·
[Security](SECURITY.md) · [License](LICENSE)

For agents: read the installed `proofpress` skill for this project's workspace
and capture settings. Use `--format agent` for compact output; `--json` expands
full records. Agents propose and retrieve; humans control admission and enforcement.

This repository develops the personal CLI. The [public Proofpress repository](https://github.com/chenmingtang830/proofpress)
contains the existing MCP/server implementation and research. Their installation
commands and stores differ. [Repository map](docs/REPOSITORIES.md)
