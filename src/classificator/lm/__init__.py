"""LM client and parsing modules — re-exports for convenient top-level imports.

Canonical usage::

    from classificator.lm import LmStudioClient, ScoringContext, CapabilityState
"""

from .client import LmStudioClient, ScoringContext, CapabilityState

__all__ = ["LmStudioClient", "ScoringContext", "CapabilityState"]


def _assert_lm_exports_resolved() -> None:
    """Verify every name in ``__all__`` resolves from this module's namespace."""

    import sys as _sys

    def _is_missing(name: str) -> bool:
        try:
            getattr(_sys.modules[__name__], name)
        except AttributeError:
            return True
        return False

    missing = [name for name in __all__ if _is_missing(name)]
    if missing:
        raise ImportError(f"Unresolved exports in classificator.lm.__all__: {missing}")


_assert_lm_exports_resolved()
