# tolvyn (Python SDK)

Drop-in replacement for the `openai` and `anthropic` packages. Add cost metering, team attribution, and budget enforcement to your AI calls in one line.

```bash
pip install tolvyn
```

---

## Quick Start

### OpenAI

```python
# Before
from openai import OpenAI
client = OpenAI()  # uses OPENAI_API_KEY

# After — one line change
from tolvyn import OpenAI
client = OpenAI(
    tolvyn_api_key="tlv_live_...",   # or set TOLVYN_API_KEY env var
    team="backend",
    service="summariser",
)

# Everything else stays the same
response = client.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": "Hello"}],
)
```

### Anthropic

```python
# Before
import anthropic
client = anthropic.Anthropic()

# After
from tolvyn import Anthropic
client = Anthropic(
    tolvyn_api_key="tlv_live_...",
    team="ml-team",
    service="classifier",
)

message = client.messages.create(
    model="claude-sonnet-4-6",
    max_tokens=1024,
    messages=[{"role": "user", "content": "Hello"}],
)
```

### Async

```python
from tolvyn import AsyncOpenAI, AsyncAnthropic

client = AsyncOpenAI(tolvyn_api_key="tlv_live_...", team="backend")
response = await client.chat.completions.create(...)
```

---

## Classes

| Class                   | Extends                    | Provider          |
|-------------------------|----------------------------|-------------------|
| `tolvyn.OpenAI`         | `openai.OpenAI`            | OpenAI            |
| `tolvyn.AsyncOpenAI`    | `openai.AsyncOpenAI`       | OpenAI (async)    |
| `tolvyn.Anthropic`      | `anthropic.Anthropic`      | Anthropic         |
| `tolvyn.AsyncAnthropic` | `anthropic.AsyncAnthropic` | Anthropic (async) |

All classes are strict drop-ins. Every method, attribute, and behaviour of the underlying SDK is preserved.

---

## Parameters

### `tolvyn.OpenAI` / `tolvyn.AsyncOpenAI`

| Parameter        | Type          | Default | Description                                                                                                             |
|------------------|---------------|---------|-------------------------------------------------------------------------------------------------------------------------|
| `tolvyn_api_key` | `str or None` | `None`  | Your TOLVYN API key. Falls back to `TOLVYN_API_KEY` env var. Required.                                                  |
| `proxy_url`      | `str or None` | `None`  | TOLVYN proxy URL. Falls back to `TOLVYN_PROXY_URL` env var, then `http://localhost:8081/v1/proxy/openai`.               |
| `team`           | `str or None` | `None`  | Team name for cost attribution. Sent as `X-Tolvyn-Team` header.                                                         |
| `service`        | `str or None` | `None`  | Service name. Sent as `X-Tolvyn-Service` header.                                                                        |
| `feature`        | `str or None` | `None`  | Feature name. Sent as `X-Tolvyn-Feature` header.                                                                        |
| `agent`          | `str or None` | `None`  | Agent name. Sent as `X-Tolvyn-Agent` header.                                                                            |
| `fail_open`      | `bool`        | `True`  | If `True` and the proxy is unreachable, automatically retry the request directly against OpenAI using `openai_api_key`. |
| `openai_api_key` | `str or None` | `None`  | OpenAI key used only for fail-open fallback. Falls back to `OPENAI_API_KEY` env var.                                    |
| `**kwargs`       |   any         |    —    | All other keyword arguments are passed through to `openai.OpenAI`.                                                      |

### `tolvyn.Anthropic` / `tolvyn.AsyncAnthropic`

| Parameter           | Type          | Default | Description                                                                                                  |
|---------------------|---------------|---------|--------------------------------------------------------------------------------------------------------------|
| `tolvyn_api_key`    | `str or None` | `None`  | Your TOLVYN API key. Falls back to `TOLVYN_API_KEY` env var. Required.                                       |
| `proxy_url`         | `str or None` | `None`  | TOLVYN proxy URL. Falls back to `TOLVYN_PROXY_URL` env var, then `http://localhost:8081/v1/proxy/anthropic`. |
| `team`              | `str or None` | `None`  | Team name for cost attribution. Sent as `X-Tolvyn-Team` header.                                              |
| `service`           | `str or None` | `None`  | Service name. Sent as `X-Tolvyn-Service` header.                                                             |
| `feature`           | `str or None` | `None`  | Feature name. Sent as `X-Tolvyn-Feature` header.                                                             |
| `agent`             | `str or None` | `None`  | Agent name. Sent as `X-Tolvyn-Agent` header.                                                                 |
| `fail_open`         | `bool`        | `True`  | If `True` and the proxy is unreachable, automatically retry the request directly against Anthropic.          |
| `anthropic_api_key` | `str or None` | `None`  | Anthropic key used only for fail-open fallback. Falls back to `ANTHROPIC_API_KEY` env var.                   |
| `**kwargs`          |   any         |    —    | All other keyword arguments are passed through to `anthropic.Anthropic`.                                     |

---

## Tagging

Tags are optional strings that appear in the TOLVYN dashboard, CLI tail output, and usage breakdowns.

```python
client = OpenAI(
    tolvyn_api_key="tlv_live_...",
    team="search-team",        # Maps to a team in TOLVYN → budget applies
    service="semantic-search", # Sub-component (e.g. microservice name)
    feature="query-expansion", # Feature within the service
    agent="reranker-v2",       # Agent name for multi-agent pipelines
)
```

All four tags are independent. You can set any combination. They are sent as HTTP headers on every request to the proxy, which stores them on the `requests` table row.

---

## Fail-open behaviour

By default, `fail_open=True`. When the TOLVYN proxy is unreachable (connection refused, timeout, HTTP 503), the SDK retries the request directly against the AI provider using the fallback key (`openai_api_key` or `anthropic_api_key`).

This means **a proxy outage never breaks your application**. Requests that bypass the proxy are not metered or attributed; they appear in the provider's own billing but not in TOLVYN.

To disable fail-open and hard-fail on proxy errors:

```python
client = OpenAI(tolvyn_api_key="tlv_live_...", fail_open=False)
```

---

## Environment variables

| Variable            | Used by           | Description                                       |
|---------------------|-------------------|---------------------------------------------------|
| `TOLVYN_API_KEY`    | All classes       | TOLVYN API key (alternative to constructor param) |
| `TOLVYN_PROXY_URL`  | All classes       | Proxy URL override                                |
| `OPENAI_API_KEY`    | OpenAI classes    | OpenAI key for fail-open fallback                 |
| `ANTHROPIC_API_KEY` | Anthropic classes | Anthropic key for fail-open fallback              |

---

## Requirements

- Python 3.9+
- `openai >= 1.0.0`
- `anthropic >= 0.20.0`
