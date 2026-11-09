# Proofpress repository map

**Your judgment. Built into your agents.** Proofpress has one product direction
and two implementations with distinct installation commands and stores.

| Repository | Use it for | Start here |
| --- | --- | --- |
| [Proofpress Judgment](https://github.com/continuara-lab/proofpress-judgment) | Personal CLI: capture, review, reuse, revision and bound hooks | [Quick start](../README.md#quick-start) |
| [Original Proofpress](https://github.com/chenmingtang830/proofpress) | Existing MCP/server integrations, services and research | Its quick start and connection guides |
| [proofpress.dev](https://proofpress.dev) | Product examples and research | Product overview |

Start with **Proofpress Judgment** to try the local judgment workflow with Codex,
Claude Code or Cursor. Existing MCP/server users should continue using their
assigned endpoints and the original repository's instructions.

The original `proofpress quickstart --ui` starts its existing demo. It does not
install this CLI. Both implementations expose `proofpress`, so use separate
environments when evaluating both. The new CLI's Python distribution is still
named `judgment-layer`; the repository and public project name are
`proofpress-judgment`. Changing a package or README does not migrate old stores.

## Website and documentation links

The website's main GitHub, Docs and CLI install links should lead to Proofpress
Judgment. Research-result links should continue leading to the original repository,
where the studies live. Keep product and research repository URLs separate.

The original README should point new CLI users here while retaining its working
installation, integration and research documentation. Existing deployments and
study URLs remain supported; neither repository is archived by this transition.
