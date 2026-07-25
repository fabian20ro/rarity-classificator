from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class LmApiFlavor(str, Enum):
    OPENAI_COMPAT = "openai_compat"
    LMSTUDIO_REST = "lmstudio_rest"


def _parse_value_to_enum(cls, value: str | None, default_name: str, alias_map: dict[str, str]):
    v = (value or default_name).strip().lower()
    if v in {default_name.lower(), ""}:
        return getattr(cls, default_name.upper())
    # normalize hyphens → underscores in both input and keys for comparison
    normalized_aliases = {k.lower().replace("-", "_") for k in alias_map}
    if v.replace("-", "_") in normalized_aliases:
        target_key = next(k for k in alias_map if k.lower().replace("-", "_") == v.replace("-", "_"))
        resolved_name = alias_map[target_key]
        if not hasattr(cls, resolved_name):
            raise ValueError(f"Invalid {cls.__name__.lower()} alias target: {resolved_name}")
        return getattr(cls, resolved_name)
    raise ValueError(f"Invalid {cls.__name__.lower()} value: {value}")


class UploadMode(str, Enum):
    PARTIAL = "partial"
    FULL_FALLBACK = "full-fallback"

    @classmethod
    def parse(cls, value: str | None) -> "UploadMode":
        return _parse_value_to_enum(
            cls, value, "PARTIAL",
            {"FULL-FALLBACK": "FULL_FALLBACK", "FULL_FALLBACK": "FULL_FALLBACK"}
        )


class Step3MergeStrategy(str, Enum):
    MEDIAN = "median"
    ANY_EXTREMES = "any_extremes"

    @classmethod
    def parse(cls, value: str | None) -> "Step3MergeStrategy":
        return _parse_value_to_enum(
            cls, value, "MEDIAN",
            {
                "ANY-EXTREMES": "ANY_EXTREMES",
                "ANY_EXTREMES": "ANY_EXTREMES",
                "THREE-ANY-EXTREMES": "ANY_EXTREMES",
                "THREE_ANY_EXTREMES": "ANY_EXTREMES",
            }
        )


class ScoringOutputMode(str, Enum):
    SCORE_RESULTS = "score_results"
    SELECTED_WORD_IDS = "selected_word_ids"

    @classmethod
    def parse(cls, value: str | None) -> "ScoringOutputMode":
        return _parse_value_to_enum(
            cls, value, "SCORE_RESULTS", {"SELECTED_WORD_IDS": "SELECTED_WORD_IDS"}
        )


@dataclass(frozen=True)
class BaseWordRow:
    word_id: int
    word: str
    type: str


@dataclass(frozen=True)
class RunCsvRow:
    word_id: int
    word: str
    type: str
    rarity_level: int
    tag: str
    confidence: float
    scored_at: str
    model: str
    run_slug: str


@dataclass(frozen=True)
class ScoreResult:
    word_id: int
    word: str
    type: str
    rarity_level: int
    tag: str
    confidence: float


@dataclass(frozen=True)
class WordLevel:
    word_id: int
    rarity_level: int


@dataclass(frozen=True)
class ResolvedEndpoint:
    endpoint: str
    models_endpoint: str | None
    flavor: LmApiFlavor
    source: str


@dataclass(frozen=True)
class BatchAttempt:
    scores: list[ScoreResult]
    unresolved: list[BaseWordRow]
    last_error: str | None
    connectivity_failure: bool


@dataclass(frozen=True)
class ParsedBatch:
    scores: list[ScoreResult]
    unresolved: list[BaseWordRow]


@dataclass(frozen=True)
class RunBaseline:
    count: int
    min_id: int | None
    max_id: int | None


@dataclass(frozen=True)
class UploadMarkerResult:
    marker_path: Path
    used_companion_file: bool
    marked_rows: int


@dataclass(frozen=True)
class LmModelConfig:
    model_id: str
    temperature: float = 0.0
    top_k: int | None = 40
    top_p: float | None = 1.0
    min_p: float | None = None
    repeat_penalty: float | None = None
    frequency_penalty: float | None = None
    presence_penalty: float | None = None
    max_tokens_cap: int | None = None
    reasoning_effort: str | None = None
    enable_thinking: bool | None = None
    thinking_type: str | None = None

    def has_reasoning_controls(self) -> bool:
        return any(
            [
                self.reasoning_effort is not None,
                self.enable_thinking is not None,
                self.thinking_type is not None,
            ]
        )
