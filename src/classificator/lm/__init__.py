"""LM client and parsing modules.

Public API re-exports from :mod:`classificator.lm.client` for convenient top-level imports.

Canonical usage::

    from classificator.lm import LmStudioClient, ScoringContext

The package-level import is the recommended entry point; callers should prefer it
over ``from classificator.lm.client import ...`` so that the public surface remains
stable even if internal module layout changes.
"""

from .client import LmStudioClient, ScoringContext

__all__ = ["LmStudioClient", "ScoringContext"]
