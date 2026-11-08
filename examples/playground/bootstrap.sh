#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
python3 -m venv .venv
.venv/bin/python -m pip install --quiet -e ../..
.venv/bin/python -m pip install --quiet -e ./vendor/provenance-core
printf '\nReady. Run ./proofpress install, then ./proofpress run\n'
