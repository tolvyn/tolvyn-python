# tolvyn

Drop-in replacement for `openai` and `anthropic`. One line change. Every AI call metered, attributed, and governed.

[![PyPI version](https://img.shields.io/pypi/v/tolvyn.svg)](https://pypi.org/project/tolvyn/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**10,000 free requests forever. No credit card.**

## Install

```bash
pip install tolvyn
```

Python 3.9 or later required.

For Google support:

```bash
pip install "tolvyn[google]"
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

## All three providers

```python
from tolvyn import OpenAI, Anthropic, Google

# OpenAI
oai = OpenAI(
    tolvyn_api_key="tlv_live_...",
    openai_api_key="sk-...",            # optional — enables fail-open fallback
)

# Anthropic
anth = Anthropic(
    tolvyn_api_key="tlv_live_...",
    anthropic_api_key="sk-ant-...",     # optional — enables fail-open fallback
)

# Google (requires the [google] extra)
goog = Google(tolvyn_api_key="tlv_live_...")
model = goog.GenerativeModel("gemini-1.5-flash")
```

## Async

`AsyncOpenAI` and `AsyncAnthropic` mirror the sync classes:

```python
import asyncio
from tolvyn import AsyncOpenAI, AsyncAnthropic

async def main():
    openai_client = AsyncOpenAI(tolvyn_api_key="tlv_live_...")
    anth_client = AsyncAnthropic(tolvyn_api_key="tlv_live_...")

    openai_resp, anth_resp = await asyncio.gather(
        openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": "Hello"}],
        ),
        anth_client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=1024,
            messages=[{"role": "user", "content": "Hello"}],
        ),
    )

asyncio.run(main())
```

There is no `AsyncGoogle` class — Google's SDK uses process-global configuration, so async calls go through the same `Google` instance via `generate_content_async`.

## Attribution headers

Set any combination of these on construction; the SDK sends them as `X-Tolvyn-*` headers automatically:

```python
client = OpenAI(
    tolvyn_api_key="tlv_live_...",
    team="backend",
    service="invoice-summarizer",
    feature="summarize",
    agent="claude-code",
    user="alice@company.com",
    end_customer="acme-corp",
)
```

The TOLVYN proxy strips all six headers before forwarding the request upstream — they never reach OpenAI/Anthropic/Google.

## Fail-open behavior

If TOLVYN's proxy is unreachable, the SDK automatically retries the request directly against the provider (requires `openai_api_key` / `anthropic_api_key` to be set). Disable with `fail_open=False`.

Triggers on: `httpx.ConnectError`, `ConnectTimeout`, `ReadTimeout`, `WriteTimeout`, `RemoteProtocolError`, and HTTP 503 from the proxy.
Does NOT trigger on: 4xx errors (auth failures, rate limits, bad requests).

Requests that fail open bypass the proxy and are not metered for that call.

### Google limitations

The `Google` class accepts `fail_open` for API parity but **fail-open is not yet supported for Google** due to an upstream `google-generativeai` SDK limitation (no httpx transport hook). The SDK emits a `UserWarning` when `fail_open=True` is passed to `Google` so callers know it won't trigger. Pass `fail_open=False` to silence.

`google-generativeai` also uses process-global configuration via `genai.configure()`. Creating a second `Google` instance in the same process overwrites the first's config — the SDK emits a `UserWarning` in that case. Use one `Google` per process.

## Environment variables

| Variable | Required | Description |
|---|---|---|
| `TOLVYN_API_KEY` | Yes (unless `tolvyn_api_key` is passed) | Your TOLVYN API key (`tlv_live_...`) |
| `OPENAI_API_KEY` | For fail-open | Fallback OpenAI key |
| `ANTHROPIC_API_KEY` | For fail-open | Fallback Anthropic key |
| `GOOGLE_API_KEY` | Reserved | Accepted but currently unused (see Google limitations) |
| `TOLVYN_PROXY_URL` | No | Override proxy URL |

```bash
export TOLVYN_API_KEY="tlv_live_..."
export OPENAI_API_KEY="sk-..."
```

```python
from tolvyn import OpenAI
client = OpenAI()   # picks up TOLVYN_API_KEY automatically
```

## API keys

- Production keys start with `tlv_live_`
- Test keys start with `tlv_test_` (use these in CI / staging)
- Get your key at [app.tolvyn.io](https://app.tolvyn.io) → API Keys
- **Provider keys** (OpenAI / Anthropic / Google) go in the dashboard under **Account → Provider Keys** — never in code. They are stored encrypted server-side.

## Changelog

[github.com/tolvyn/tolvyn-cli/releases](https://github.com/tolvyn/tolvyn-cli/releases)

## Links

- Docs: [docs.tolvyn.io/sdks/python](https://docs.tolvyn.io/sdks/python)
- Quickstart: [docs.tolvyn.io/getting-started/quickstart](https://docs.tolvyn.io/getting-started/quickstart)
- Dashboard: [app.tolvyn.io](https://app.tolvyn.io)
- Issues: [github.com/tolvyn/tolvyn-python/issues](https://github.com/tolvyn/tolvyn-python/issues)

## Feedback

[founder@tolvyn.io](mailto:founder@tolvyn.io) — we read every message.

---

© 2026 TOLVYN. MIT licensed.
