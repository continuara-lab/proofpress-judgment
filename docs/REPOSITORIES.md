# Proofpress repository map

Proofpress has one product direction: **Your judgment. Built into your agents.**
There are currently two implementations. They share ideas, not interchangeable
commands or stores.

| Repository | Use it for | Current entry point |
| --- | --- | --- |
| [`continuara-lab/judgment-layer`](https://github.com/continuara-lab/judgment-layer) | The personal Proofpress CLI: local capture, review, reuse, revision and bound hooks | This README's installer; `proofpress review` |
| [`chenmingtang830/proofpress`](https://github.com/chenmingtang830/proofpress) | The existing Proofpress MCP/server implementation, current integrations and research | That repository's quick start and connection guides |
| [`proofpress.dev`](https://proofpress.dev) | Product narrative, examples and research links | Product overview and currently published setup path |

The public repository's `proofpress quickstart --ui` starts its existing demo.
It does not install this CLI's judgment workflow. This CLI's Python distribution
is named `judgment-layer`, but both implementations expose `proofpress`; use
separate environments while evaluating them. Existing stores are not migrated by
changing a README or installing a different package.

The local CLI is a private alpha. A public website link cannot grant repository
access, and an anonymous curl command cannot download private code. Existing
Apache-2.0 licensing does not itself make a repository publicly readable.

## Recommended transition

Keep the local CLI independent while its daily workflow is being tested. Preserve
existing deployments, integration docs and study URLs in the public repository.

While the CLI remains private, the website should distinguish “Try the existing
demo” from “Request CLI alpha access.” Once the CLI is publicly accessible, its
primary install and GitHub links can point here. Keep evidence links pointing to
the repository that actually contains the studies. In the website source, the
primary GitHub/Docs links and the study URLs currently share `repoUrl`; split
those destinations before changing the primary product link, rather than replacing
every occurrence of the old repository address.

A short notice in the public README can identify the existing implementation and
the new CLI trial without implying migration or archive status. Do not rename or
archive either repository merely to make the branding match.

This is a recommended transition, not a declaration that the website, repository
visibility, deployed services or public README have been changed by this document.
