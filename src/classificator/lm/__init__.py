"""LM client and parsing modules — re-exports for convenient top-level imports.

Canonical usage::

    from classificator.lm import LmStudioClient, ScoringContext, CapabilityState
"""

from .client import LmStudioClient, ScoringContext, CapabilityState

__all__ = ["LmStudioClient", "ScoringContext", "CapabilityState"]
