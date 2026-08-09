"""LM client and parsing modules — re-exports for convenient top-level imports.

Canonical usage::

    from classificator.lm import LmStudioClient, ScoringContext, CapabilityState
"""

from .client import LmStudioClient, ScoringContext, CapabilityState

__all__ = ["LmStudioClient", "ScoringContext", "CapabilityState"]


def _assert_lm_exports_resolved() -> None:
    """Verify every name in ``__all__`` resolves from this module's namespace
    and is a callable object (class or function).

    Mirrors the parent-package contract check but scoped to ``classificator.lm``.
    Catches drift when a non-callable object, import alias, or typo appears
    in ``__all__`` — the test surface already expects all re-exports to be
    instantiable classes, so this guard enforces that invariant at import time.
    """

    import sys as _sys

    def _is_missing(name: str) -> bool:
        try:
            getattr(_sys.modules[__name__], name)
        except AttributeError:
            return True
        return False

    missing = [name for name in __all__ if _is_missing(name)]
    non_callable = []
    for name in __all__:
        if not _is_missing(name):
            try:
                obj = getattr(_sys.modules[__name__], name)
            except Exception:
                continue
            if not callable(obj):
                non_callable.append((name, type(obj).__name__))

    errors: list[str] = []
    if missing:
        errors.append(f"Unresolved exports in classificator.lm.__all__: {missing}")
    if non_callable:
        errors.append(
            f"Non-callable objects in classificator.lm.__all__: {non_callable}"
        )

    if errors:
        raise ImportError("; ".join(errors))


_assert_lm_exports_resolved()
