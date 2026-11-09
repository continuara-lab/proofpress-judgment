# Use Proofpress with your agent

## Start from a human terminal

Install from the [README quick start](../README.md#quick-start) in the project where
you work. Codex is the default; Claude Code, Cursor and other skill entry points
are listed in the [compatibility guide](AGENTS.md).

Start a fresh agent session in that project and ask:

> Use Proofpress. Propose useful judgments from my guidance and your work, with
> reasons, sources and conditions. Use approved judgments before related tasks.
> Leave approval to me.

Continue with a real task. When a consequential choice or correction arises,
the agent can propose a record. Open `proofpress review` in a terminal to inspect,
edit, approve or reject it. Use `proofpress configure` to change what it captures.
You can review multiple candidates through the numbered inbox without copying IDs.

## Instructions for agents

These instructions describe the workflow; they do not authorize an agent to
approve judgments, edit owner policy or install trusted hooks.

1. **Find the workspace.** Read the installed `proofpress` skill. Codex uses
   `.agents/skills/proofpress/SKILL.md`; Claude Code uses
   `.claude/skills/proofpress/SKILL.md`. Other hosts use their documented entry
   points. The installed skill supplies the absolute workspace argument. Put it
   before every CLI command. If setup is missing, ask the human to run onboarding.
2. **Read capture settings.** Run `policy --format agent` and
   `capture-policy --format agent`. Follow the selected capture categories.
   Capture meaningful judgments, corrections and lessons; skip routine messages
   and unsupported generalizations. Skill guidance does not install a listener.
3. **Propose with evidence.** Read the installed `references/workflow.md` and AJF
   example once. Adapt them to the actual choice, source and scope; run
   `capture --from FILE --format agent`. Preserve unknown rationale as null.
   Keep temporary files private. Tell the human what was proposed and point to
   `proofpress review`; a proposal is not approved guidance.
4. **Reuse within conditions.** Establish the task's exact scope and known facts.
   Run `context --scope SCOPE --facts FILE --actor agent:NAME --purpose PURPOSE
   --format agent`. Use only the returned admitted judgments within their limits.
   Missing facts do not become true merely because they would produce a match.
5. **Check before continued reliance.** Use `check --receipt ID --facts FILE` when
   rechecking a prior context receipt. Honor stale or inapplicable results. Use
   `match --scope SCOPE --facts FILE --format agent` to explain selection without
   issuing a receipt. Retrieval is advice; it does not authorize a business action.
6. **Propose updates.** New evidence can justify a candidate revision or an outcome
   observation. Preserve provenance and version links. A pending revision leaves
   the admitted version active until human review or withdrawal.

Never run real `review`, `withdraw`, `bind`, `configure`, `hooks`, `pause`, `resume`,
`unbind`, `uninstall` or `--confirm` as the owner. Never write directly to the store.
History extraction and provider-backed assessment require explicit human
permission to send the selected material to a model.

## What runs where

- **Local records:** `.judgment/` is the private project store and is ignored by Git.
- **Capture guidance:** The installed skill tells the agent when to propose and retrieve.
- **Human review:** The terminal provides approval, editing and enforcement choices.
- **Action hooks:** Separate host installation and trust enable checks on covered tools.
- **Model assessment:** Optional configured providers assess nuanced conflicts or output;
  the current decision-model provider is TypeSafe. They do not approve candidates.

Use `proofpress doctor` to distinguish configured integration from an observed
runtime check. [Local alpha walkthrough](LOCAL-ALPHA.md)
