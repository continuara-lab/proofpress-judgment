# Connect your agent

Run the installer from the project where your agent works. It creates a local
judgment store and a self-contained skill. For Codex, Claude Code and Cursor it
also writes startup guidance that the host reads in new sessions.

| Agent | Startup guidance |
| --- | --- |
| Codex | Managed block in `AGENTS.md` or an active `AGENTS.override.md` |
| Claude Code | Project rule in `.claude/rules/proofpress.md` |
| Cursor | Always-apply rule in `.cursor/rules/proofpress.mdc` |

The Codex installer appends a managed block to the project's instructions.
`proofpress uninstall --confirm`
removes the unchanged Proofpress block or rule and retains edited files and the
judgment store. Hosts load project instructions according to their trust settings.

Use `proofpress onboard --startup --agents codex` to preview the same configuration
from an existing installation. `proofpress setup --all --owner human:me` installs
all skill entry points. Use `--dry-run` on `setup` to preview skill files only.
For another project, use `--project /path/to/project`. Pass `--workspace` before
the subcommand to select a store inside that project.

## Agent entry points

These paths follow the linked host documentation, checked November 7, 2026.
The table lists skill-directory compatibility. Install action hooks separately
for Codex, Claude Code or Cursor. [Runtime setup](RUNTIME.md)

Each path below contains `proofpress/SKILL.md` plus the same bundled workflow,
coding example and AJF schema. Shared paths are written once.

| Agent selector | Project skill directory | Host-specific requirement |
| --- | --- | --- |
| [codex](https://developers.openai.com/codex/skills) | `.agents/skills/` | Start a new session or reload skills. |
| [claude-code](https://code.claude.com/docs/en/skills) | `.claude/skills/` | Use Claude Code with local shell access. |
| [cursor](https://cursor.com/docs/skills) | `.agents/skills/` | Use Agent in the configured project. |
| [devin](https://docs.devin.ai/cli/extensibility/skills/overview) | `.agents/skills/` | Covers Devin CLI / Local; Cloud needs separate provisioning. |
| [grok](https://github.com/xai-org/grok-build/blob/main/crates/codegen/xai-grok-pager/docs/user-guide/08-skills.md#skill-locations) | `.agents/skills/` | Covers Grok Build; not the Grok web chat. |
| [gemini](https://geminicli.com/docs/cli/skills/) | `.agents/skills/` | Covers Gemini CLI; reload skills if already running. |
| [hermes](https://hermes-agent.nousresearch.com/docs/user-guide/features/skills) | `.agents/skills/` | Run in a Git project; inspect and trust it with `hermes skills trust`. |
| [openclaw](https://docs.openclaw.ai/skills) | `.agents/skills/` | Run setup in the selected agent's actual workspace. |
| [copilot](https://docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/add-skills) | `.agents/skills/` | Covers Copilot CLI with local shell access. |
| [opencode](https://opencode.ai/docs/skills/) | `.agents/skills/` | Uses its documented compatibility directory. |
| [windsurf](https://docs.windsurf.com/windsurf/cascade/skills) | `.windsurf/skills/` | Reload skills in the project; host version affects discovery. |
| [cline](https://docs.cline.bot/customization/skills) | `.claude/skills/` | Uses its documented compatibility directory; keep the skill enabled. |

Some hosts discover more than one compatibility directory. Setup writes identical
content to the three directories needed by `--all`. If your host displays duplicate
entries, install only for that host in a clean project. Host enablement, trust and
managed policies still apply; setup does not grant tool permissions.

## Install by agent

Run one command in your project. Codex, Claude Code and Cursor load the installed
startup guidance in new sessions. For the other hosts, activate the Proofpress
skill when it applies.

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

### Devin CLI

```sh
curl -fsSL https://raw.githubusercontent.com/continuara-lab/proofpress-judgment/main/install.sh | bash -s -- --agents devin
```

### Grok Build

```sh
curl -fsSL https://raw.githubusercontent.com/continuara-lab/proofpress-judgment/main/install.sh | bash -s -- --agents grok
```

### Gemini CLI

```sh
curl -fsSL https://raw.githubusercontent.com/continuara-lab/proofpress-judgment/main/install.sh | bash -s -- --agents gemini
```

### Hermes

```sh
curl -fsSL https://raw.githubusercontent.com/continuara-lab/proofpress-judgment/main/install.sh | bash -s -- --agents hermes
```

### OpenClaw

```sh
curl -fsSL https://raw.githubusercontent.com/continuara-lab/proofpress-judgment/main/install.sh | bash -s -- --agents openclaw
```

### GitHub Copilot CLI

```sh
curl -fsSL https://raw.githubusercontent.com/continuara-lab/proofpress-judgment/main/install.sh | bash -s -- --agents copilot
```

### OpenCode

```sh
curl -fsSL https://raw.githubusercontent.com/continuara-lab/proofpress-judgment/main/install.sh | bash -s -- --agents opencode
```

### Windsurf

```sh
curl -fsSL https://raw.githubusercontent.com/continuara-lab/proofpress-judgment/main/install.sh | bash -s -- --agents windsurf
```

### Cline

```sh
curl -fsSL https://raw.githubusercontent.com/continuara-lab/proofpress-judgment/main/install.sh | bash -s -- --agents cline
```

## Install the runtime

This is a Python package, not an npm package. `uv tool install` puts the `proofpress`
command in an isolated tool environment. If `proofpress` is not found, run
`uv tool update-shell`, then open a new terminal. A checkout can instead use the
[development install](CLI.md#install-from-a-checkout).

The repository is public. Setup does not read tokens or configure credentials. No npm/PyPI package or marketplace
listing has been published. Installation downloads the code and dependencies;
normal local commands work offline.

The selected local store path is bound into the installed skill. Run setup on
each machine rather than committing these generated machine-specific files.
For a remote or cloud agent, install the CLI on its execution machine and select
its own workspace. A local installation does not sync judgments to cloud agents.

## Remove the integration

Run `proofpress uninstall` to preview removal. Add `--confirm` to remove the
managed integration and retain the judgment store. Start a new agent session.
Remove the CLI with `uv tool uninstall judgment-layer`.
