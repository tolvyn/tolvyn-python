#!/usr/bin/env bash
# The publish path, with the artefact check in it.
#
# PYTHON HAS NO prepublishOnly, which is why this script exists rather than a
# note in a README. npm runs a hook before `npm publish`; twine runs nothing, so
# the only way to make a check unskippable is to make it part of the command
# somebody actually types. BE-488 shipped because the two obvious checks --
# pytest, and `import tolvyn` -- both pass on a package whose documented first
# line does not work.
#
#   bash scripts/publish.sh            # verify, then upload to PyPI
#   bash scripts/publish.sh --dry-run  # verify and build, upload nothing
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

bash scripts/verify-wheel.sh

VERSION="$(python3 - <<'PY'
import re, pathlib
m = re.search(r'^version\s*=\s*"([^"]+)"', pathlib.Path("pyproject.toml").read_text(), re.M)
print(m.group(1))
PY
)"
echo
echo "built and verified: tolvyn $VERSION"
ls -1 dist/

if [ "${1:-}" = "--dry-run" ]; then
  echo "--dry-run: nothing uploaded."
  exit 0
fi

python3 -m pip install -q --upgrade twine >/dev/null 2>&1 || true
# TWINE READS THE TOKEN FROM THE ENVIRONMENT, so the token never reaches a
# shell history or a config file this repository can see.
#   export TWINE_USERNAME=__token__
#   export TWINE_PASSWORD=pypi-...        (a PyPI API token)
python3 -m twine check dist/*
python3 -m twine upload dist/*
echo "uploaded tolvyn $VERSION"
