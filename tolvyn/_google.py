"""TOLVYN Google wrapper — thin configuration layer over google-generativeai."""
from __future__ import annotations

import google.generativeai as genai

from tolvyn._config import resolve_tolvyn_key, resolve_fallback_key

# The endpoint host (without scheme) that points google SDK requests at the proxy.
# Google SDK prepends "https://" and appends the API path, so requests land at:
#   https://proxy.tolvyn.io/v1/proxy/google/v1beta/models/...
# The TOLVYN proxy strips /v1/proxy/google and forwards /v1beta/models/... to Google.
_GOOGLE_DEFAULT_ENDPOINT = "proxy.tolvyn.io/v1/proxy/google"
_GOOGLE_DIRECT_ENDPOINT = "generativelanguage.googleapis.com"


class Google:
    """
    TOLVYN Google wrapper. Configures google.generativeai to route through the TOLVYN proxy.

    Note: google-generativeai uses process-wide global state via genai.configure().
    Instantiating multiple Google clients in the same process overwrites each other's
    configuration. Use a single instance per process.

    Usage::

        from tolvyn import Google
        g = Google(tolvyn_api_key="tlv_live_...")
        model = g.GenerativeModel("gemini-1.5-flash")
        response = model.generate_content("Hello")
    """

    def __init__(
        self,
        tolvyn_api_key: str | None = None,
        proxy_endpoint: str | None = None,
        fail_open: bool = True,
        google_api_key: str | None = None,
    ) -> None:
        self._tolvyn_key = resolve_tolvyn_key(tolvyn_api_key)
        self._endpoint = proxy_endpoint or _GOOGLE_DEFAULT_ENDPOINT
        self._fail_open = fail_open
        self._fallback_key = resolve_fallback_key(google_api_key, "GOOGLE_API_KEY")

        genai.configure(
            api_key=self._tolvyn_key,
            client_options={"api_endpoint": self._endpoint},
            transport="rest",
        )

    def GenerativeModel(self, model_name: str, **kwargs) -> genai.GenerativeModel:
        """Return a GenerativeModel routed through the TOLVYN proxy."""
        return genai.GenerativeModel(model_name, **kwargs)

    def list_models(self, **kwargs):
        return genai.list_models(**kwargs)

    def get_model(self, name: str):
        return genai.get_model(name)
