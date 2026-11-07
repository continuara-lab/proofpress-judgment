# Enforce specific constraints

**Status: implementation plan, not installed functionality.** The current skill
supplies advice. `context` and `check` manage eligibility; neither intercepts
agent tool calls. Nothing in this release guarantees that a model follows a
judgment.

## Start with one coding constraint

Use the generated-file example: change the source schema and regenerate instead
of patching generated SDK files. Keep the reason and exceptions in AJF. Bind an
explicitly reviewed constraint to a concrete tool boundary separately; a prose
record or `kind: constraint` alone must never become executable policy.

An adapter needs to:

1. **Inspect the action:** derive the real target paths from the pending write or
   patch and determine generated status from repository configuration, not the
   model's assertion.
2. **Check current authority:** resolve the exact reviewed judgment version,
   scope, conditions and executable binding from the selected workspace. Handle
   missing facts, invalid state and withdrawn bindings according to an explicit
   owner policy; never revive old versions or guess permissions.
3. **Apply the constraint:** deny a covered direct edit and explain the source
   change route. A proposed exception is a new candidate for owner review, not
   the agent silently approving its own override.
4. **Record the attempt:** record the checked revision, action target, outcome
   and time. This receipt establishes what the gate checked, not that subsequent
   work was correct.

Lifecycle and enforcement need separate semantics. Withdrawing reusable advice
must not accidentally unlock a previously protected resource; a binding must say
whether withdrawal blocks, asks for reassessment, or explicitly removes a
restriction. That policy must be reviewed too.

## Use real host interception

[Codex hooks](https://learn.chatgpt.com/docs/hooks) and
[Claude Code hooks](https://code.claude.com/docs/en/hooks) have pre-tool blocking
interfaces. Codex requires trust in non-managed hook definitions. A practical
first adapter can cover an exact supported write/patch tool; it must list its
coverage and test denial before claiming enforcement.

Shell writes, alternate tools, symlinks, remote execution, disabled hooks and
same-user changes to the gate can bypass a narrowly scoped adapter. Full coverage
requires control of every relevant write path or enforcement in the execution
service itself. The store check and an external side effect also need a design
for races with withdrawal. These are not solved by attaching `check` to a hook.

## Keep judgment broader than rules

“Don't directly edit this generated file” has a testable action boundary.
“Preserve uncertainty in this research summary” needs assessment of meaning.
The latter can use an evidence-backed review before publication, but a hook
cannot guarantee its substantive correctness. Rules, reviewer findings and
human exceptions should remain inspectable without pretending they are the
same kind of evidence.

Before shipping an adapter, test real host tool events, blocked edits,
non-matching actions, missing facts, stale versions, withdrawn bindings,
malformed events and unavailable stores. Report which routes were actually
intercepted. Compare task quality separately from mechanical gate behavior.
