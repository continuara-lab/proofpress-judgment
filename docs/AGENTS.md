# Connect your agent

Run setup from the project where the agent works. It creates a manual-only local
store and installs a self-contained skill. It does not edit existing instruction
files, host settings, hook configuration or home directories.

```sh
judgment setup --all --owner human:me
```

For selected agents, use `judgment setup --agents cursor codex --owner human:me`.
For a preview, add `--dry-run`. For structured output, add `--format json`.
For another project, add `--project /path/to/project`.
The global `--workspace` option selects a store inside that project and goes before
`setup`. Existing stores retain their owner, policy, records and approval state.
Repeating setup with identical files is a no-op. Different existing skill files
cause an error before installation; move or preserve them yourself rather than
silently overwriting them.

## Agent entry points

These paths follow the linked host documentation, checked November 7, 2026.
The installer is tested locally. This is **skill-directory compatibility**, not
evidence of successful live sessions in all 12 hosts. No host receives hooks.

Each path below contains `judgment-layer/SKILL.md` plus the same bundled workflow,
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

## Talk to your agent

Ask the agent to use judgment-layer when capturing a meaningful correction or
beginning related work. Skill activation is host-dependent and model-directed;
installation alone does not intercept all steering or guarantee recall.

The agent can propose a candidate and explain what needs review. You inspect it
and run manual review separately using the [CLI guide](CLI.md#run-the-manual-loop).
The same workflow captures the agent's own consequential judgments and assumptions
without passing them off as your expertise. They also need review.

## Install the runtime

This is a Python package, not an npm package. `uv tool install` puts the `judgment`
command in an isolated tool environment. If `judgment` is not found, run
`uv tool update-shell`, then open a new terminal. A checkout can instead use the
[development install](CLI.md#install-from-a-checkout).

For a private repository, Git must already have authenticated access. Setup does
not read tokens or configure credentials. No npm/PyPI package or marketplace
listing has been published. Installation downloads the code and dependencies;
normal local commands work offline.

The selected local store path is bound into the installed skill. Run setup on
each machine rather than committing these generated machine-specific files.
For a remote or cloud agent, install the CLI on its execution machine and select
its own workspace. A local installation does not sync judgments to cloud agents.

## Remove the integration

`setup --dry-run` reports the skill directories. Remove only the `judgment-layer`
directories you installed, preserving any edits you need. This stops future
discovery after the agent reloads; it does not erase advice already in a running
session. Keep or separately delete the `.judgment` store as you choose. Remove
the runtime with `uv tool uninstall judgment-layer`.
