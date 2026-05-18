"""TOLVYN Google wrapper — thin configuration layer over google-generativeai."""
from __future__ import annotations

import threading
import warnings

import google.generativeai as genai

from tolvyn._config import resolve_tolvyn_key, resolve_fallback_key

# The endpoint host (without scheme) that points google SDK requests at the proxy.
# Google SDK prepends "https://" and appends the API path, so requests land at:
#   https://proxy.tolvyn.io/v1/proxy/google/v1beta/models/...
# The TOLVYN proxy strips /v1/proxy/google and forwards /v1beta/models/... to Google.
_GOOGLE_DEFAULT_ENDPOINT = "proxy.tolvyn.io/v1/proxy/google"
_GOOGLE_DIRECT_ENDPOINT = "generativelanguage.googleapis.com"

# PY-03: track instance count for the multi-instance warning.
_google_instance_count = 0
_google_instance_lock = threading.Lock()


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
        self._fallback_key = resolve_fallback_key(google_api_key, "GOOGLE_API_KEY")

        # PY-01: Fail-open for Google is not yet supported. The google-generativeai
        # SDK does not expose its HTTP transport in a way that lets us inject the
        # same kind of httpx-based retry transport used for OpenAI and Anthropic.
        # Warn the caller honestly rather than silently swallowing the option.
        if fail_open:
            warnings.warn(
                "tolvyn.Google: fail-open is not yet supported for Google due to "
                "google-generativeai SDK limitations. Requests will NOT fall back "
                "to generativelanguage.googleapis.com if the TOLVYN proxy is "
                "unreachable. Pass fail_open=False to silence this warning.",
                UserWarning,
                stacklevel=2,
            )
        self._fail_open = False

        # PY-03: warn on multiple instances — genai.configure() is global.
        global _google_instance_count
        with _google_instance_lock:
            _google_instance_count += 1
            if _google_instance_count > 1:
                warnings.warn(
                    "Multiple tolvyn.Google instances detected. "
                    "genai.configure() is process-global — each new instance "
                    "overwrites the previous configuration. Use a single Google "
                    "instance per process.",
                    UserWarning,
                    stacklevel=2,
                )

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
