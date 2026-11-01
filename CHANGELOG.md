# Changelog

## 0.1.13 — unreleased

### Documentation

- **The Google example now uses `gemini-3.8-flash`.** The README and the
  `tolvyn.Google` docstring named `gemini-1.5-flash`, which Google no longer serves.
- **The `tolvyn.DeepSeek` docstring now uses `deepseek-flash`**, DeepSeek's current
  model name. `deepseek-chat` and `deepseek-reasoner` still work.

## 0.1.12 — 2026-11-01

### Anthropic

- **`tolvyn.Anthropic` and `tolvyn.AsyncAnthropic` now work with `anthropic` 1.x and
  later.** Those releases use `httpx2` instead of `httpx`; the fail-open client is
  now built from whichever of the two the installed `anthropic` uses, so a client
  with a fallback key no longer fails at construction.
- **The `anthropic<1` limit added in 0.1.11 is removed.** Any `anthropic` from 0.20
  up is supported. Tested on 0.125.0, 1.17.0 and 2.3.0, including fail-open.

## 0.1.11 — 2026-10-26

### Fail-open: changed behaviour

- **Fail-open now fires only when TOLVYN is unreachable**: the connection was
  refused, DNS failed, the TLS handshake failed, or connecting timed out
  (`httpx.ConnectError`, `httpx.ConnectTimeout`), or TOLVYN answered 503 with
  `X-Tolvyn-Unavailable: 1`.
- **It no longer fires on a provider's 503.** A plain 503 through the proxy is the
  provider's own and is returned to you; retrying it direct only moved the call out
  of TOLVYN's metering.
- **It no longer fires on read/write timeouts, resets or protocol errors.** Those
  can happen after TOLVYN forwarded the request, and the direct retry was a second,
  unmetered provider call.
- Enforcement responses (kill switch 451, budget/quota 429) never fail open.

### Fail-open: fixes

- The direct request no longer carries any `X-Tolvyn-*` header, set on the client
  or per request (`X-Tolvyn-User` and `X-Tolvyn-End-Customer` can be personal data).
  Reported by Maram Sai Harsha Vardhan Reddy. (BE-507)
- The direct request now sends the provider's Host, not the proxy's. (BE-511)
- The discarded 503 response is closed before the retry. (BE-514)

### Dependencies

- `anthropic` is pinned below 1.0. anthropic 1.x moved to `httpx2`, and
  `tolvyn.Anthropic` / `AsyncAnthropic` raised `TypeError` at construction
  whenever a fallback key was set. (BE-515)
