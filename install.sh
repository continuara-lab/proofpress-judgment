#!/usr/bin/env bash
# macOS/Linux bootstrap. Run from the project you want to connect.
set -euo pipefail

case "$(uname -s)" in
  Darwin|Linux) ;;
  *) echo 'Use the Python CLI installation on this platform.' >&2; exit 1 ;;
esac
command -v git >/dev/null || { echo 'Install Git first, then rerun this installer.' >&2; exit 1; }
judgment_source="${JUDGMENT_INSTALL_SOURCE:-git+https://github.com/continuara-lab/judgment-layer.git}"
if [[ "$judgment_source" == git+* ]]; then
  if ! GIT_TERMINAL_PROMPT=0 git ls-remote "${judgment_source#git+}" HEAD >/dev/null 2>&1; then
    echo 'Cannot access the package repository. Configure GitHub access and retry; nothing was installed.' >&2
    exit 1
  fi
fi
if command -v uv >/dev/null 2>&1; then
  judgment_uv="$(command -v uv)"
elif [[ -x "${HOME}/.local/bin/uv" ]]; then
  judgment_uv="${HOME}/.local/bin/uv"
else
  command -v curl >/dev/null || { echo 'Install curl first.' >&2; exit 1; }
  judgment_temp="$(mktemp -d)"
  trap 'rm -rf "$judgment_temp"' EXIT
  curl -fsSL https://astral.sh/uv/install.sh -o "$judgment_temp/uv-install.sh"
  UV_INSTALL_DIR="${HOME}/.local/bin" UV_NO_MODIFY_PATH=1 sh "$judgment_temp/uv-install.sh"
  judgment_uv="${HOME}/.local/bin/uv"
fi
"$judgment_uv" tool install --upgrade --python 3.11 "$judgment_source"
judgment_bin="$("$judgment_uv" tool dir --bin)"
if [[ $# -eq 0 ]]; then
  set -- --all --owner "human:$(id -un)"
fi
"$judgment_bin/judgment" setup "$@"
case ":$PATH:" in
  *":$judgment_bin:"*) ;;
  *) printf '\nAdd the CLI to your shell PATH: export PATH="%s:$PATH"\n' "$judgment_bin" ;;
esac
