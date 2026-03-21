"""Configuration helpers — reads env vars and ~/.tolvyn/config.json."""
import os
import json
from pathlib import Path


def resolve_tolvyn_key(explicit: str | None) -> str:
    """Return the TOLVYN API key, raising ValueError if none found."""
    if explicit:
        return explicit
    env = os.environ.get("TOLVYN_API_KEY")
    if env:
        return env
    raise ValueError(
        "tolvyn_api_key required. "
        "Pass tolvyn_api_key= or set the TOLVYN_API_KEY environment variable."
    )


def resolve_proxy_url(explicit: str | None, default: str) -> str:
    if explicit:
        return explicit
    return os.environ.get("TOLVYN_PROXY_URL", default)


def resolve_fallback_key(explicit: str | None, env_var: str) -> str | None:
    if explicit:
        return explicit
    return os.environ.get(env_var)
