"""TOLVYN SDK — drop-in replacements for the OpenAI/Anthropic/Google SDKs.

Provider wrappers are imported lazily so that pulling in one provider does not
require the optional dependencies of the others. For example::

    from tolvyn import Anthropic   # does not import google.generativeai
"""

__all__ = [
    "OpenAI", "AsyncOpenAI",
    "Anthropic", "AsyncAnthropic",
    "Google",
    "DeepSeek", "AsyncDeepSeek",
]
# ONE SOURCE: the installed distribution's metadata, which comes from
# pyproject.toml. A literal here is a second copy of the version, and on
# 2026-10-13 the two drifted -- pyproject said 0.1.9, this said 0.1.8, and
# `tolvyn 0.1.9` was PUBLISHED reporting `__version__ == "0.1.8"`. A customer
# debugging a version-specific problem would have been told the wrong answer by
# the package itself. BE-489.
#
# The fallback is for a source tree that was never installed (running tests from
# a checkout without `pip install -e .`), where there is no metadata to read. It
# says "unknown" rather than a number, because a wrong number is worse than an
# admitted absence -- which is the whole lesson of the drift.
try:  # pragma: no cover - trivial, and the except path needs no installed dist
    from importlib.metadata import PackageNotFoundError, version as _pkg_version

    __version__ = _pkg_version("tolvyn")
except Exception:  # PackageNotFoundError, or a Python without the module
    __version__ = "unknown"

_LAZY = {
    "OpenAI": "tolvyn._client",
    "AsyncOpenAI": "tolvyn._client",
    "Anthropic": "tolvyn._anthropic",
    "AsyncAnthropic": "tolvyn._anthropic",
    "Google": "tolvyn._google",
    "DeepSeek": "tolvyn._deepseek",
    "AsyncDeepSeek": "tolvyn._deepseek",
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
