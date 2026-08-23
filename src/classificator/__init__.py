"""Romanian rarity classification pipeline.

Re-exports core types and utilities so callers can import directly from the
package namespace instead of navigating deep relative paths.
"""

from .constants import (
    DEFAULT_REBALANCE_TRANSITIONS,
    ensure_output_dir,
)
from .models import Step3MergeStrategy, UploadMode
from .steps.step1_export import Step1Options as _Step1Options
from .steps.step2_score import Step2Options as _Step2Options
from .transitions import LevelTransition, parse_transitions, validate_transition_set
from .word_store import WordStore
from .run_csv_repository import RunCsvRepository
from .steps import _STEPS as _STEPS
import sys as _sys

__all__ = [
    "__version__",
    "DEFAULT_REBALANCE_TRANSITIONS",
    "ensure_output_dir",
    "LevelTransition",
    "parse_transitions",
    "RunCsvRepository",
    "Step1Options",
    "Step2Options",
    "Step3MergeStrategy",
    "UploadMode",
    "validate_transition_set",
    "WordStore",
]

# Aliases for ergonomic top-level access.
Step1Options = _Step1Options
Step2Options = _Step2Options
del _Step1Options, _Step2Options

__version__ = "0.1.0"
