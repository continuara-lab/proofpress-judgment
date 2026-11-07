# Judgment Layer

**Your team's judgment. Built into your agents.**

Turn everyday guidance into expertise agents can build on. Keep the reasons,
conditions and limits behind each judgment available for review and revision.

Judgment Layer is a local CLI for judgments made by people and agents. Capture a
judgment, review it, supply it to a later task, and revise or withdraw it as your
understanding changes.

**Early prototype · CLI-first · Manual admission · Apache-2.0**

## Carry expertise forward

You tell an agent: “Ask Finance to review unresolved billing disputes.” On another
run, that guidance can help again—but only in the situations it was meant for.
Later, you narrow it: “Finance review is needed only for disputes over $100.”

Judgment Layer keeps the original guidance, its reasons and conditions, and the
review history. You review the new version before it replaces the old one. If
the old guidance is wrong, you can withdraw it immediately.

The aim is less repeated steering in familiar situations, with room to question
old assumptions when circumstances change. Better task outcomes and reduced
steering remain hypotheses to test.

## Follow one judgment through its lifecycle

| Step | What happens |
| --- | --- |
| **Capture** | Save human guidance or an agent's judgment with its source, reasons and conditions. |
| **Review** | Inspect the evidence and limits; accept, reject or request changes to that exact version. |
| **Reuse** | Supply reviewed judgments whose scope and explicit conditions match the task facts. |
| **Revise** | Propose a new version; review it before it replaces the active version. |
| **Withdraw** | Remove a judgment from future reuse while preserving its history. |

A useful review asks: **Should later agents receive this advice, and under which
conditions?** An approval records that choice; it cannot establish that the
reviewer independently assessed the merits. Sources, rationale and limits remain
visible so the judgment can be challenged.

## Try the local walkthrough

Requires Python 3.11 or newer. From a checkout:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -e .
.venv/bin/python examples/walkthrough.py --synthetic-review-fixture
```

The walkthrough uses a temporary store and synthetic owner-review fixtures. It
checks three situations:

- **Valid reuse:** reviewed guidance is supplied when its conditions match.
- **Outside scope:** a similar task with different facts receives no applicable guidance.
- **Changed guidance:** replacement or withdrawal makes old receipts fail a fresh check.

Normal commands run offline after installation. No model, API key or server is
required. The walkthrough verifies lifecycle mechanics; it does not run a live
agent or measure judgment quality.

## Use it in your own workflow

```sh
.venv/bin/judgment init --owner human:me
.venv/bin/judgment capture --from examples/billing.json
.venv/bin/judgment inbox
```

`capture` creates a **candidate**. Follow the [CLI guide](docs/CLI.md) to inspect
it, review its exact version and digest, retrieve applicable guidance, and revise
or withdraw it. Admission means a judgment is approved for local reuse.

Your agent or application calls `context` with the task's scope and facts. The
result includes matching judgments and a receipt of what was supplied. You can
recheck that receipt later with `check`. Supplied guidance is advice; the receipt
does not prove the agent used it or authorize a business action.

For agent-assisted use, the [workflow skill](plugins/judgment-layer/skills/judgment-layer/SKILL.md)
explains candidate capture and reuse. Human review stays separate. Installing the
Python package does not install the skill or change a host's configuration.

## Know the current boundaries

- **Capture is explicit.** Write an AJF record or import a selected TRACE decision. Automatic extraction from chat is future work.
- **Admission is manual.** Every new version needs local review. Source acceptance in TRACE does not grant local approval.
- **Matching is conservative.** Scope and scalar conditions must match supplied facts. Missing facts exclude the judgment; prose limits still need interpretation.
- **Checks are local.** There are no installed action hooks or automatic pauses. A receipt check and an external action can race.
- **Identity is cooperative.** Processes under your OS account can invoke owner commands. The confirmation flag is not authentication.

Read the [security boundaries](SECURITY.md) before connecting real workflows.
Default capture guidance lives in `.judgment/config.json`; `judgment policy`
shows it. Keep private stores and sessions out of Git.

## Explore the format and implementation

AJF—**Agent Judgment Format**—lives in this repository. It describes portable
judgment content. Local governance separately decides which versions may be
reused. The design draws on TRACE's decision provenance and Proofpress's
governance lifecycle.

| Resource | What you will find |
| --- | --- |
| [CLI guide](docs/CLI.md) | Review, reuse, revision, withdrawal, receipts and TRACE import commands |
| [AJF specification](docs/AJF.md) | Judgment fields, provenance, applicability and format boundaries |
| [Complete AJF example](examples/full-judgment.json) | One synthetic record ready for validation |
| [JSON Schema](src/judgment_layer/ajf.schema.json) | The validator's bundled format definition |
| [Architecture](docs/ARCHITECTURE.md) | Local storage, lifecycle events and current eligibility |
| [Upstream mechanisms](docs/UPSTREAM.md) | What comes from TRACE, Proofpress and the earlier ADF draft |
| [Evaluation plan](evals/README.md) | The proposed comparison with strong maintained notes; no results yet |

## Run the tests

```sh
.venv/bin/python -m unittest discover -s tests -v
```

Tests cover manual admission, conditional reuse, immutable revisions,
supersession, withdrawal, stale receipts, dependencies and TRACE import.
