#!/usr/bin/env bash
# Build sdist+wheel, install THE WHEEL into a brand-new venv with nothing else,
# and import it the way a customer does — then make one real call.
#
# WHY THIS EXISTS (BE-488). tolvyn 0.1.8 shipped without declaring httpx, which
# tolvyn/_client.py imports at module scope. It worked by accident while
# `openai` happened to depend on httpx; openai 3.x declares `httpx2` instead, so
# a clean `pip install tolvyn` resolves without it and
# `from tolvyn import OpenAI` raises ModuleNotFoundError — the first line of the
# published Python quickstart.
#
# NOTHING CAUGHT IT, AND THE REASON IS THE POINT: `pytest` runs against a
# development environment where httpx is present (anything that has ever
# installed an older openai has it), and `import tolvyn` SUCCEEDS even without
# it, because tolvyn/__init__.py imports the provider wrappers LAZILY. So the
# two obvious checks — the test suite, and importing the package — both pass
# while the documented line fails. This script does the documented line, in a
# venv that has only the wheel's own dependency closure.
#
# Run before every publish:  bash scripts/verify-wheel.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
rm -rf dist build
python3 -m pip install -q --upgrade build >/dev/null 2>&1 || true
python3 -m build >/dev/null
ls -1 dist/
WHEEL="$(ls dist/*.whl | head -1)"
echo "built: $WHEEL"

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
cp "$WHEEL" "$WORK/"
cd "$WORK"
python3 -m venv .venv
# ONLY THE WHEEL. No openai, no httpx, no anything -- whatever the package
# needs it must declare, which is the whole of what BE-488 was.
./.venv/bin/pip install -q "./$(basename "$WHEEL")"
echo "installed into a fresh venv:"
./.venv/bin/pip list 2>/dev/null | grep -iE "tolvyn|openai|anthropic|httpx" | sed 's/^/  /'

cat > server.py <<'SRV'
import json, threading
from http.server import BaseHTTPRequestHandler, HTTPServer

SEEN = []

class H(BaseHTTPRequestHandler):
    def do_POST(self):
        SEEN.append({k.lower(): v for k, v in self.headers.items()
                     if k.lower().startswith("x-tolvyn")})
        n = int(self.headers.get("Content-Length", 0))
        self.rfile.read(n)
        body = json.dumps({
            "id": "cmpl-1", "object": "chat.completion", "model": "gpt-4o-mini",
            "choices": [{"index": 0, "message": {"role": "assistant", "content": "ok"},
                         "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 5, "completion_tokens": 1, "total_tokens": 6},
        }).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass

def start():
    srv = HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv
SRV

cat > check.py <<'CHK'
import sys
# THE DOCUMENTED LINE. This is what 0.1.8 could not do.
from tolvyn import OpenAI, Anthropic          # noqa: F401
print("  from tolvyn import OpenAI, Anthropic — ok")

from server import start, SEEN
srv = start()
port = srv.server_address[1]

client = OpenAI(
    tolvyn_api_key="tlv_live_test",
    proxy_url=f"http://127.0.0.1:{port}/v1/proxy/openai/v1",
    team="t", service="s", feature="f", user="u", end_customer="e", agent="a",
)
r = client.chat.completions.create(
    model="gpt-4o-mini", messages=[{"role": "user", "content": "Hello"}], max_tokens=5,
)
if r.choices[0].message.content != "ok":
    print("FAIL: no completion"); sys.exit(1)
print("  one real call — ok")

want = {"x-tolvyn-team", "x-tolvyn-service", "x-tolvyn-feature",
        "x-tolvyn-agent", "x-tolvyn-user", "x-tolvyn-end-customer"}
got = set(SEEN[0]) if SEEN else set()
if got != want:
    print(f"FAIL: headers {sorted(got)} != {sorted(want)}"); sys.exit(1)
print("  all six X-Tolvyn-* headers — ok")

# THE VERSION THE PACKAGE REPORTS MUST BE THE VERSION THAT WAS BUILT.
# tolvyn 0.1.9 was PUBLISHED reporting __version__ == "0.1.8": pyproject.toml
# was bumped and tolvyn/__init__.py's literal was not. A customer debugging a
# version-specific problem would have been told the wrong answer by the package
# itself, and nothing checked it. __version__ is now derived from the installed
# metadata, so this assertion is a guard against someone reintroducing a
# literal rather than against a typo. BE-489.
import tolvyn
from importlib.metadata import version as _v
if tolvyn.__version__ != _v("tolvyn"):
    print(f"FAIL: tolvyn.__version__ = {tolvyn.__version__!r} but the installed "
          f"distribution is {_v('tolvyn')!r} — the two have drifted")
    sys.exit(1)
print(f"  __version__ agrees with the distribution ({tolvyn.__version__}) — ok")
CHK

./.venv/bin/python check.py
echo "verify-wheel: the WHEEL imports and calls from a venv containing only its own dependencies"
