# Install Proofpress

The runtime is Python. uv installs it in an isolated environment; the shell
installer handles those steps for you. No npm package is required.

## Private alpha

Git must already have access to this private repository. Clone it once:

```sh
git clone https://github.com/continuara-lab/judgment-layer.git
```

From the project you want to connect, run `bash /path/to/judgment-layer/install.sh`.
The script installs uv if needed without editing shell profiles, installs the
CLI and prepares all 12 skill entry points. It uses `human:<OS username>` as a
local owner label for new stores, not authentication. Existing owners are kept.
Admission stays manual. The installer
prints PATH instructions if the command directory is not already on your PATH.

For selected agents, pass setup arguments explicitly:

```sh
bash /path/to/judgment-layer/install.sh --agents cursor codex --owner human:me
```

Or, with uv already installed:

```sh
uv tool install --upgrade --python 3.11 git+https://github.com/continuara-lab/judgment-layer.git
proofpress setup --all --owner human:me
```

## Curl distribution

`curl` downloads a script; `bash` runs it. That script can install the same Python
package through uv. This changes onboarding, not the runtime or judgment model.
The script lives at the repository root as `install.sh` and supports piped input.

After the repository becomes publicly readable, this endpoint can be used:

```sh
curl -fsSL https://raw.githubusercontent.com/continuara-lab/judgment-layer/main/install.sh | bash
```

**That anonymous command is not available while the repository is private.**
No public installer endpoint has been published. A separately hosted script can
also provide the curl entry point, but installation still needs package access
until the package itself is public.

For contributor installation and checks, see the [CLI guide](CLI.md).
