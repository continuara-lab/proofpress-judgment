# Judgment Layer

**Your team's judgment. Built into your agents.**

You corrected your agent. It acknowledged. Days later, the same mistake.
Even with the guidance in memory and skills.

Turn steering and agent-made judgments into reviewed, reusable expertise—
with reasons, conditions, and a way to revise or withdraw it.

## Get started

From a checkout, run this in the project you want to connect:

```sh
bash /path/to/judgment-layer/install.sh
```

The installer handles uv, Python and the CLI, then prepares skill entry points
for 12 agents. **Private alpha:** GitHub repository access is required.
[Installation details](docs/INSTALL.md) · [Agent compatibility](docs/AGENTS.md)

Restart your agent, then ask:

> Use judgment-layer. Capture my meaningful corrections for review, and use
> approved judgments before related work.

## Teach it once. Reuse it when it applies.

| Work | Your correction |
| --- | --- |
| [Coding](examples/coding.json) | “Change the schema. Don't patch generated files.” |
| [Design](examples/design.json) | “Use our existing components before adding new ones.” |
| [Sales](examples/sales.json) | “No verified buying signal? Don't invent one in the outbound email.” |
| [Slides](examples/slides.json) | “One claim per pitch slide. Show the evidence.” |

**Capture → review → reuse → revise or withdraw.**

Candidates need your approval. Reuse matches explicit scope and conditions.
The aim: fewer repeated mistakes and less repeated steering. Benefits over
well-maintained memory notes still need to be measured.

## What works today

Local CLI, AJF records, manual review, conditional retrieval and stale-version
checks. Skill entry points cover 12 agents; live sessions aren't verified in all
of them. **No action hooks yet.** [The hook plan](docs/HOOKS.md) explains how
specific constraints could block tool actions.

[CLI guide](docs/CLI.md) · [AJF format](docs/AJF.md) ·
[Architecture](docs/ARCHITECTURE.md) · [Evaluation plan](evals/README.md) ·
[Security](SECURITY.md)

Early prototype · Manual admission · Apache-2.0
