# Judgment Layer

**Your team's judgment. Built into your agents.**

Your agent gets something wrong. You steer it. It acknowledges the correction.
A few days later, it makes the same mistake.

The guidance is in memory. It's in a skill. Why didn't it carry forward?

Remembering a correction doesn't settle when it applies, why it matters, who
approved it, or when it should stop shaping the agent's work.

We're building the missing layer for agent judgments: turn everyday steering
and agent-made judgments into expertise you can inspect, approve, reuse and
revise. The aim is fewer repeated mistakes and less repeated explanation.

**Early prototype · Local CLI + agent skill · Manual approval · Apache-2.0**

## Install in your project

With [uv](https://docs.astral.sh/uv/getting-started/installation/) installed,
run this from the project where your agent works:

```sh
uv tool install --python 3.11 git+https://github.com/continuara-lab/judgment-layer.git && judgment setup --all --owner human:me
```

This installs the Python CLI, creates a private local judgment store, and adds
skill entry points for **12 agents**. Nothing is automatically approved. The
repository is currently private, so installation requires GitHub repository
access. There is no published npm or PyPI package yet.

Restart your agent or reload its skills, then ask:

> Use judgment-layer. When I make a meaningful correction, capture the judgment,
> why it matters and when it applies. Show me what needs review. Before related
> work, retrieve the judgments I've approved.

Entry points cover Codex, Claude Code, Cursor, Devin CLI, Grok Build, Gemini CLI,
Hermes, OpenClaw, Copilot CLI, OpenCode, Windsurf and Cline. These use documented
skill directories; they have **not all been tested in live agent sessions**.
Hermes needs project trust. Remote agents need their own CLI and store setup.
See [agent setup](docs/AGENTS.md) for details or to install for just one agent.

## Make a correction useful next time

“Don't edit generated SDK files. Change the source schema and regenerate.”

An agent can capture that judgment, its source, the reason hand edits get
overwritten, and the condition **this file is generated**. You inspect and
approve the exact version. A later agent can retrieve it for a matching task.
If the conditions change, propose a revision; if the guidance is wrong, withdraw
it. Old versions remain inspectable and withdrawn versions stop being returned.

The same loop applies to familiar work:

| Workflow | Judgment worth carrying forward |
| --- | --- |
| [Coding](examples/coding.json) | Change the source and regenerate; avoid patches the generator will overwrite. |
| [Design](examples/design.json) | Reuse product components; propose exceptions when existing patterns fall short. |
| [Summaries](examples/summary.json) | Preserve uncertainty so tentative findings don't become false facts. |
| [Slide decks](examples/slides.json) | Lead a pitch slide with one supported claim; keep detailed methods available. |

Capture → human review → applicable reuse → revision or withdrawal.

Capture creates a candidate. Approval makes it eligible for local reuse; it
doesn't prove it correct. Agent capture is skill-guided, not automatic extraction
of every correction. Better task outcomes remain to be measured against strong,
maintained memory notes.

## What about enforcement?

**Today:** the CLI manages which judgments can be supplied and rechecks whether
a supplied version is still eligible. The skill asks the agent to follow that
advice. This release installs **no action hooks**.

**Next:** bind specific, testable constraints to tool hooks. A write hook could
check a file's generated status and block a direct edit before it happens. That
requires a real host adapter and action-level checks; remembering the rule or
passing a receipt check does not enforce it. Open-ended design or research
judgments still need assessment. See the [hook plan](docs/HOOKS.md).

## Go deeper

- [CLI guide](docs/CLI.md): inspect, review, reuse, revise and withdraw.
- [AJF format](docs/AJF.md): portable judgment content, separate from approval.
- [Architecture](docs/ARCHITECTURE.md): TRACE provenance + Proofpress lifecycle.
- [Evaluation plan](evals/README.md): compare judgment management with maintained notes.
- [Security boundaries](SECURITY.md): cooperative local trust; not an adversarial gate.

For contributor checks and the synthetic coding walkthrough, see the
[development instructions](docs/CLI.md#validate-the-implementation).
