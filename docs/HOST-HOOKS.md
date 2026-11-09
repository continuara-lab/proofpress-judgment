# Agent hook integration map

This map separates each host’s interface from Proofpress implementation status.
The other-host research was checked November 8, 2026. For installation and live
verification receipts, see [Enforce judgments](RUNTIME.md).

| Host | Before-action interface and integration | Blocking semantics and limits | Proofpress status |
| --- | --- | --- | --- |
| Claude Code | `PreToolUse` command in project settings; JSON stdin/stdout | `permissionDecision: deny`; preserve normal host permissions on pass. Current docs require >=2.1.295 for `onFailure: block`. | Managed project install and handler available. A real Write attempt through the handler was blocked. [Claude receipt](verification/live-claude-hook-2026-11-08.json) |
| Codex | `PreToolUse` in trusted `.codex/hooks.json` / supported config | Deny or exit 2 can block local function tools, shell, apply_patch and MCP. Hosted tools are excluded. Non-managed hooks need trust. Unsupported response fields can fail the hook and continue the call. | Managed project install and apply_patch adapter verified through normal host trust. [Codex receipt](verification/installed-codex-hooks-2026-11-09.json) |
| Cursor | Project/user `hooks.json`; generic `preToolUse` plus dedicated shell/MCP hooks | Pre-tool permission response for covered tools. | Managed project install and four Cursor CLI lifecycle scenarios verified. [Cursor receipt](verification/live-cursor-hooks-2026-11-09.json) |
| Gemini CLI | `BeforeTool` under hooks settings | `decision: deny` or exit 2 prevents execution. `AfterTool` denial happens after side effects and is not a replacement. | Researched; not implemented. |
| Copilot CLI / cloud | `preToolUse` in `.github/hooks/*.json` or supported policy/user config | `permissionDecision: deny`; command errors deny, but documented command-hook timeouts fail open, including admin policy. Cloud environment and lifecycle coverage differ. | Researched; timeout behavior prevents a generic fail-closed promise. |
| Devin CLI / current Devin Desktop | `.devin/hooks.v1.json`, also imports `.claude` hooks; `PreToolUse` | Exit 2 or block response; tool names include `exec`, `edit`, MCP. Other nonzero exit codes do not block. Cloud lifecycle runs through plugins, with differences. | Exact official interface found; adapter not implemented. |
| Grok Build | Settings/plugin `PreToolUse`; official xai-org source documents command/HTTP hooks | Settings hooks and SDK hooks expose different controls. SDK supports allow/deny; do not assume settings-only ask/defer/context works there. grok.com chat is a different surface. | Researched; not implemented. |
| Hermes Agent | Shell `pre_tool_call` in profile config, or plugin registration | Shell exit 2 blocks. Set `fail_closed: true` to block spawn errors, timeouts and invalid output. Passive Gateway event hooks are a different interface. | Researched; prefer shell adapter with fail-closed configuration. |
| OpenClaw | Native plugin `api.on("before_tool_call", ...)` | Can block/request approval. Ordinary `HOOK.md` internal automation hooks are not this typed tool interceptor. Runtime emitters and tool coverage must be checked. | Researched; needs native plugin bridge, not a renamed shell hook. |
| OpenCode | V1 `tool.execute.before`; V2 `ctx.tool.hook("execute.before", ...)` / permission evaluation | Official V1 example throws to block; V2 also exposes permission evaluation effects. Plugin APIs/config differ by generation. | Researched; pin version before building adapter. |
| Cline | Extension executable `PreToolUse` hooks; current SDK plugin `beforeTool` | SDK returns `skip: true` with reason, or requests approval via policy. `hookErrorMode` controls thrown/timeout failures. SDK callbacks have a documented short timeout, relevant for remote semantics. | SDK source docs checked; extension and SDK require separate adapters. |
| Windsurf legacy Cascade | Historical Windsurf hook URL now redirects to Devin Desktop customization docs | Current redirected page could not be fetched during this audit. Do not silently equate older Cascade events/settings with current Devin hooks. | Version-specific verification pending; no enforcement claim. |

## Primary references

- [Claude Code](https://code.claude.com/docs/en/hooks)
- [Codex](https://learn.chatgpt.com/docs/hooks)
- [Cursor](https://cursor.com/docs/hooks)
- [Gemini CLI](https://geminicli.com/docs/hooks/reference/)
- [GitHub Copilot](https://docs.github.com/en/copilot/reference/hooks-reference)
- [Devin configuration](https://docs.devin.ai/cli/extensibility/hooks/overview) and [lifecycle](https://docs.devin.ai/cli/extensibility/hooks/lifecycle-hooks)
- [Grok Build official source](https://github.com/xai-org/grok-build/blob/main/crates/codegen/xai-grok-pager/docs/user-guide/10-hooks.md)
- [Hermes](https://hermes-agent.nousresearch.com/docs/user-guide/features/hooks)
- [OpenClaw](https://docs.openclaw.ai/plugins/hooks)
- [OpenCode V1](https://docs.opencode.ai/docs/plugins/) and [current server plugin API](https://opencode.ai/docs/build/plugins/server)
- [Cline SDK](https://docs.cline.bot/sdk/plugins.md) and [extension source](https://github.com/cline/cline/blob/main/.clinerules/hooks/README.md)
- [Historical Windsurf URL](https://docs.windsurf.com/windsurf/cascade/hooks) redirects; current legacy compatibility unresolved.

## Shared implementation direction

Keep one judgment resolver, conflict state and binding ledger. Each host adapter
normalizes the actual pending action into a typed event, invokes the same verifier,
and converts the result into that host's blocking protocol. Never copy a Claude
response schema into another host without checking its contract.

Configure interception before all relevant tool routes, including shell, patch,
MCP and delegated/remote execution. A post-tool audit cannot undo a side effect.
A local key does not automatically provision the remote environment. A host
retry is a new attempt that must be checked again.

Add per-host fixtures and live tests for protected writes, unrelated actions,
missing facts, conflicts, withdrawal, malformed responses, missing executables and
timeouts. Track protocol-tested and live-host-tested separately. Gemini,
Hermes and OpenClaw still need native adapters.
