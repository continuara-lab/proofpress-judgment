# Proofpress matching and enforcement

Status: design discussion, not an implemented runtime or a validated efficacy claim.
Updated November 8, 2026. CLI readability and AJF naming changes are separate.

## Current behavior

The store is SQLite. `Store.context` scans revisions, filters exact scope, then
checks manual admission, exact scalar facts, validity windows and exact-version
dependencies. Missing facts exclude records. `Store.check` rechecks a persisted
receipt against current state, facts and policy. No vector retrieval, filesystem
search, semantic classifier, conflict resolution or tool interception runs here.

The playground supplies a fixed `coding/knowledge-urls` scope and a caller-selected
`surface` fact. It demonstrates lifecycle mechanics, not autonomous discovery of
task applicability. Descriptive limits are prose. A record's `constraint` kind is
not executable policy. The wrapper saves generated code before its receipt check;
it does not block output when that check fails. That is a real release gap.

The resolver also scans revision/event history and audits on transactions. A larger
store will need indexed current-state projections, with consistent invalidation.
This is runtime cost separate from tokens sent to a model.

## Match a judgment's prerequisites, not whole tasks

Two tasks do not need to be equivalent. Ask whether the current action satisfies
the prerequisites of the judgment being reused. For example, a Python SDK task and
a TypeScript SDK task can both satisfy “direct edit to generated source.” Conversely,
two almost identical slug tasks differ when one serves public URLs.

For a declared abstraction, test whether observed task/action facts imply the
judgment's predicates, with no known exception or invalid dependency. Passing a
small shared test set does not establish general semantic or task equivalence.
Only use formal proof claims where the domain, semantics and assumptions are
explicit. Inferred task facts remain fallible even if the downstream solver is exact.

## Split discovery, applicability and execution

| Stage | First implementation | Meaning of success |
| --- | --- | --- |
| Discover candidates | Action/resource indexes; optional semantic retrieval for advice | Worth checking, not eligible or authorized |
| Establish facts | Runtime adapters, repository configuration, typed observations | Facts have sources and an explicit unknown state |
| Check applicability | Approved, versioned predicates plus lifecycle/dependency checks | This judgment applies under these observed facts |
| Supply guidance | Small projection, receipt and inspect-on-demand | Agent received advice; compliance is not established |
| Gate an action | Approved binding, real pre-tool interception, current-state recheck | This covered action passed the configured gate |
| Verify outcome | Deterministic checks where possible; reviewer findings otherwise | Bounded evidence about this output, not universal correctness |

Hard constraints must be routed by a complete registered action/resource index,
not semantic top-k retrieval. Otherwise a retrieval miss silently bypasses a rule.
Use `match`, `no_match`, and `unknown`. For registered protected actions, missing
facts, unresolved conflicting judgments or failed verification should block or
escalate under an explicit owner policy. No matching advice is not permission.

## Use code first; keep models optional

Start with a small, typed predicate vocabulary: exact values, controlled path sets,
repository identity, generated-file configuration and explicit validity. Do not
execute arbitrary code found in judgment prose. A model may propose predicates or
verifiers, but their concrete version and binding need separate owner review.

Jev or another classifier could help with semantic applicability: e.g. whether a
sales sentence implies a buying signal. Its answer is a fallible assessment.
Record model version, evidence, rubric and uncertainty; benchmark before allowing
it to affect routing. Do not let a model response invent a trusted environment
fact, approve a record, resolve authority conflicts or change a gate binding.

TypeSafe describes Jev as unstructured state in and typed probabilistic answers
out. That supports an optional assessment component, not a proof engine or owner
of lifecycle authority. [TypeSafe overview](https://docs.typesafe.ai/concepts/system-one)

## Ship one enforceable coding case first

Recommended first case: direct edits to configured generated files must be denied;
the agent should change the source schema and regenerate. A human-approved generator
path can be a separate explicitly scoped operation, not a prose exception inferred
by the agent.

Bind one admitted judgment revision and digest to a versioned verifier, supported
tool/action set, resource scope, required facts and failure/withdrawal behavior.
Keep that execution binding in local governance, separate from portable AJF text.
Changing the judgment or verifier invalidates the binding until reviewed again.
Withdrawing advice must not silently unlock a protected resource.

A supported host's real pre-tool hook should normalize paths, inspect the pending
action, obtain authoritative facts, recheck the binding, and return a short denial
or pass control to the host's normal permissions. A successful Proofpress check
must not bypass the host's existing authorization. Record action identity, judgment
version, verifier identity and outcome. Never rely on the agent voluntarily calling
`check` or faithfully reporting that a check passed.

Claude Code documents synchronous PreToolUse blocking and configurable behavior
when hooks fail. This is one candidate adapter; installation, host/version support,
timeouts and real intercepted events still need verification.
[Claude Code hooks](https://code.claude.com/docs/en/hooks)

A hook protects only intercepted routes. Shell writes, alternate tools, symlinks,
remote execution and same-user policy edits require explicit coverage or isolation.
For strict guarantees, the execution service must own the protected action and a
well-defined policy snapshot through commit; an external preflight check leaves a
race with withdrawal. A cooperative local plugin is not an adversarial sandbox.

## Test applicability and enforcement separately

Use held-out tasks with paraphrases, different languages/tools, similar-but-wrong
contexts, absent or contradictory facts, expired guidance, revisions, withdrawals
and conflicting rules. Measure missed applicable judgments, incorrect reuse,
unknown/escalation rate, correction recurrence, total model tokens/cost and latency.

For gates, test real tool calls: deny before any side effect, allow unrelated work,
block or escalate malformed/missing facts, invalidate stale bindings, and handle
failure and concurrent withdrawal. Include alternate write routes rather than
claiming generic enforcement from one mocked callback.

Compare maintained memory notes, notes plus the same retrieval/gate, judgment
lifecycle without a gate, and lifecycle plus gate under equal model/budget settings.
This separates representation, matching, review and enforcement effects. A memory
system can implement these too; Proofpress must demonstrate a better maintained
workflow or outcome, not claim JSON alone creates a missing capability.

## Reduce both human and agent cost

Short human output and compact model input are different interfaces. Complete
records remain available for review; reuse carries judgment, rationale, conditions
and a receipt, without replaying source sessions. Future adapters should supply
applicable guidance at the action boundary, avoid repeated agent CLI round trips,
and invalidate caches on relevant lifecycle or fact changes. Runtime checks still
run where required even when nothing new needs to enter the model's context.

The November 8 local formatting check shrank one stored context packet from 2,650
to 719 UTF-8 bytes using the agent projection. This is a single serialization
measurement, not measured tokenizer savings, cheaper agent operation or better
judgment quality. No new model benchmark was run for these changes.
