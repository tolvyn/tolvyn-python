"""Configuration helpers — reads env vars and ~/.tolvyn/config.json."""
import os


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


def build_tolvyn_headers(
    team: str | None,
    service: str | None,
    feature: str | None,
    agent: str | None,
    user: str | None,
    end_customer: str | None,
) -> dict[str, str]:
    """Return the X-Tolvyn-* attribution headers for non-empty fields."""
    headers: dict[str, str] = {}
    if team:
        headers["X-Tolvyn-Team"] = team
    if service:
        headers["X-Tolvyn-Service"] = service
    if feature:
        headers["X-Tolvyn-Feature"] = feature
    if agent:
        headers["X-Tolvyn-Agent"] = agent
    if user:
        headers["X-Tolvyn-User"] = user
    if end_customer:
        headers["X-Tolvyn-End-Customer"] = end_customer
    return headers
