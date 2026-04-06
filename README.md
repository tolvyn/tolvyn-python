# tolvyn · PyPI

[![PyPI version](https://img.shields.io/pypi/v/tolvyn.svg)](https://pypi.org/project/tolvyn/)

Drop-in replacement for `openai` and `anthropic`.
One line change. Every AI call metered, attributed, and governed.

## Install

```bash
pip install tolvyn
```

## Quick start

```python
# Before
from openai import OpenAI
client = OpenAI()

# After — one line change
from tolvyn import OpenAI
client = OpenAI(
    tolvyn_api_key="tlv_live_...",
    team="backend",
    service="summariser",
)

# Everything else stays the same
response = client.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": "Hello"}],
)
```

Works the same way for Anthropic:

```python
from tolvyn import Anthropic
client = Anthropic(tolvyn_api_key="tlv_live_...", team="ml", service="classifier")
```

## What you get

- **Cost metering** — every request logged with exact token counts and cost in microdollars
- **Team attribution** — see spend by team and service, not just a total invoice number
- **Budget enforcement** — set hard limits that block requests before they hit your provider
- **Immutable ledger** — hash-chained audit trail, verifiable at any time
- **Drop-in** — no changes to your existing API calls, models, or response handling

## Environment variable mode

```bash
export TOLVYN_API_KEY="tlv_live_..."
export OPENAI_API_KEY="sk-..."     # your real provider key (stored encrypted on TOLVYN)
```

```python
from tolvyn import OpenAI
client = OpenAI()  # picks up TOLVYN_API_KEY automatically
```

Full docs: [docs.tolvyn.io/python-sdk](https://docs.tolvyn.io/python-sdk)
Free trial: [tolvyn.io](https://tolvyn.io)

---

© 2026 TOLVYN. All rights reserved.
