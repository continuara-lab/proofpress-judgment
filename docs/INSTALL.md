# Install Proofpress CLI

This repository contains the new local CLI. The repository is public. Supported installer platforms are macOS
and Linux. The runtime is Python; no npm package is needed.

## Install in your project

Run from the project where your agent works:

```sh
curl -fsSL https://raw.githubusercontent.com/continuara-lab/proofpress-judgment/main/install.sh | bash
```

The script installs uv if needed, installs the Python CLI in an isolated tool
environment and enables Codex guidance in the current project. It does not change
your shell profile. Follow any printed PATH instruction, then check:

```sh
proofpress doctor
```

A `.judgment/` folder holds private records, settings and review history. Installed
agent guidance contains this store's absolute path. Start a new agent session in
the project after setup. [First session](AGENT-SETUP.md)

The installer enables manual review and uses `human:<OS username>` as a local
owner label. This is not authenticated identity. It does not install action hooks
or import history. [Hook setup](RUNTIME.md)

## Choose another agent

To choose Claude Code after the default installation, run:

```sh
proofpress onboard --agents claude-code
```

To add agent guidance after installation, preview in that project:

```sh
proofpress onboard --agents cursor codex
```

Confirm in your terminal. `proofpress configure` changes what the agent may
capture. [All agent entry points](AGENTS.md)

## Keep existing Proofpress installations separate

The public Proofpress repository and this CLI both expose a command named
`proofpress`. They use different distributions, APIs and stores. Do not replace
an existing installation merely to try this CLI.

If you already use the public implementation, create a separate virtual
environment in your trial project. Requires uv:

```sh
uv venv --python 3.11 .venv-proofpress-cli
uv pip install --python .venv-proofpress-cli/bin/python "git+https://github.com/continuara-lab/proofpress-judgment.git"
source .venv-proofpress-cli/bin/activate
proofpress onboard
```

Activate that environment when using this CLI. Activation changes which executable
your shell resolves; it does not migrate data. Do not run it against an older
Proofpress store. [Repository map](REPOSITORIES.md)

## Update the CLI

Rerun the installer from your working project:

```sh
curl -fsSL https://raw.githubusercontent.com/continuara-lab/proofpress-judgment/main/install.sh | bash
```

Existing stores retain their records and owner. Refreshed skill files are backed
up under `.judgment/skill-backups/`. For a manually installed environment, update
the package in that environment and use `proofpress onboard --upgrade`.

## Remove the integration

Preview with `proofpress uninstall`; repeat with `--confirm` to remove managed
hooks and unchanged installed skills. Edited skill files and the judgment store
remain. Restart your agent after removal. For uv tool installation, remove the
package with `uv tool uninstall judgment-layer` after removing integration.

## Install from source

If you prefer to inspect the script before running it:

```sh
git clone https://github.com/continuara-lab/proofpress-judgment.git "$HOME/.local/share/proofpress-cli"
```

Then, from your working project, run
`bash "$HOME/.local/share/proofpress-cli/install.sh"`.
For source development and checks, see the [CLI guide](CLI.md).
