"""Pipeline step modules.

Package-level validation: verifies all step entry points are importable and callable.
Run explicitly via _validate_step_modules() or on demand.
"""

import inspect
from .step1_export import run_step1 as _run_step1
from .step2_score import run_step2 as _run_step2
from .step3_compare import run_step3 as _run_step3
from .step4_upload import run_step4 as _run_step4
from .step5_rebalance import run_step5 as _run_step5


_STEPS = (
    ("step1", "export", _run_step1),
    ("step2", "score", _run_step2),
    ("step3", "compare", _run_step3),
    ("step4", "upload", _run_step4),
    ("step5", "rebalance", _run_step5),
)


def _validate_step_modules() -> list[str]:
    """Validate all step modules export callable entry points.

    Returns:
        List of validation error messages (empty if valid).
    """
    errors = []
    if len(_STEPS) != 5:
        errors.append(f"_STEPS must have exactly 5 entries, got {len(_STEPS)}")
    seen_names = set()
    for entry in _STEPS:
        if not isinstance(entry, tuple) or len(entry) != 3:
            errors.append("_STEPS entries must be (name, label, callable) 3-tuples")
            continue
        name, _, func = entry
        if name in seen_names:
            errors.append(f"duplicate step name: {name}")
        else:
            seen_names.add(name)
    for name, _, func in _STEPS:
        try:
            if not inspect.isfunction(func):
                errors.append(f"{name}: expected callable, got {type(func).__name__}")
                continue
            sig = inspect.signature(func)
            params = list(sig.parameters.keys())
            if len(params) < 1 or params[0] != "options":
                errors.append(
                    f"{name}: expected 'options' as first parameter, got {params}"
                )
        except Exception as exc:
            errors.append(f"{name}: validation error ({exc})")
    return errors


def validate_steps() -> None:
    """Raise ValueError with all validation errors found.

    Raises:
        ValueError: With error details if any step validation fails.
    """
    errors = _validate_step_modules()
    if errors:
        raise ValueError(
            f"Step module validation failed:\n  " + "\n  ".join(errors)
        )


__all__ = [
    "_run_step1",
    "_run_step2",
    "_run_step3",
    "_run_step4",
    "_run_step5",
    "_STEPS",
    "_validate_step_modules",
    "validate_steps",
]
