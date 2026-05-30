"""TOLVYN SDK — drop-in replacements for the OpenAI/Anthropic/Google SDKs.

Provider wrappers are imported lazily so that pulling in one provider does not
require the optional dependencies of the others. For example::

    from tolvyn import Anthropic   # does not import google.generativeai
"""

__all__ = ["OpenAI", "AsyncOpenAI", "Anthropic", "AsyncAnthropic", "Google"]
__version__ = "0.1.6"

_LAZY = {
    "OpenAI": "tolvyn._client",
    "AsyncOpenAI": "tolvyn._client",
    "Anthropic": "tolvyn._anthropic",
    "AsyncAnthropic": "tolvyn._anthropic",
    "Google": "tolvyn._google",
}


def __getattr__(name):
    module_path = _LAZY.get(name)
    if module_path is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    import importlib

    module = importlib.import_module(module_path)
    return getattr(module, name)


def __dir__():
    return sorted(__all__)
