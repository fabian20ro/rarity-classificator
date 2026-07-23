"""Tooling commands for the classificator pipeline.

Package-level validation: verifies all tool modules export callable entry points.
Run explicitly via _validate_tool_modules() or on demand.
"""

import inspect
from .build_retry_input import build_retry_input
from .chain_rebalance_target_dist import run_chain_rebalance
from .quality_audit import run_quality_audit
from .rarity_distribution import run_rarity_distribution
from .review_low_confidence import parse_only_levels, run_l1_review_check, run_review_low_confidence


_TOOL_MODULES = (
    ("build_retry_input", build_retry_input),
    ("chain_rebalance_target_dist", run_chain_rebalance),
    ("quality_audit", run_quality_audit),
    ("rarity_distribution", run_rarity_distribution),
    ("review_low_confidence", run_review_low_confidence),
)


def _validate_tool_modules() -> list[str]:
    """Validate all tool modules export callable entry points.

    Returns:
        List of validation error messages (empty if valid).
    """
    errors = []
    for name, func in _TOOL_MODULES:
        if not inspect.isfunction(func):
            errors.append(f"{name}: expected callable, got {type(func).__name__}")
            continue
        sig = inspect.signature(func)
        params = list(sig.parameters.keys())
        if len(params) < 1 or params[0] != "options":
            # Tool modules use varied signatures — only flag if no params at all.
            if len(params) == 0:
                errors.append(f"{name}: expected at least one parameter, got {params}")
    return errors


__all__ = [
    "_TOOL_MODULES",
    "_validate_tool_modules",
    "build_retry_input",
    "run_chain_rebalance",
    "run_quality_audit",
    "run_rarity_distribution",
    "parse_only_levels",
    "run_l1_review_check",
    "run_review_low_confidence",
]
