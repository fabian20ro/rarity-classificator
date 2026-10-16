"""Step2 scoring interface. Transport and persistence stay outside the outcome."""

from dataclasses import dataclass
import math
from typing import Protocol

from ..models import BaseWordRow


@dataclass(frozen=True)
class Outcome:
    word_id: int
    rarity_level: int | None
    probabilities: tuple[float, ...] = ()
    status: str = "scored"
    error: str = ""
    tag: str = "unclassified"
    confidence: float | None = None
    request: dict | None = None
    response: str = ""

    def __post_init__(self):
        if type(self.word_id) is not int or self.word_id <= 0:
            raise ValueError("Outcome requires a positive word ID")
        if self.status not in {"scored", "failed", "unresolved"}:
            raise ValueError("Unknown outcome status")
        if self.rarity_level is not None and (
            type(self.rarity_level) is not int or not 1 <= self.rarity_level <= 5
        ):
            raise ValueError("Rarity level must be 1..5")
        if self.status == "scored" and self.rarity_level is None:
            raise ValueError("Scored outcome requires a level")
        if self.status == "failed" and (self.rarity_level is not None or self.probabilities):
            raise ValueError("Failed outcome cannot carry a prediction")
        if self.probabilities and (
            len(self.probabilities) != 5
            or any(
                type(p) not in (int, float) or not math.isfinite(p) or not 0 <= p <= 1
                for p in self.probabilities
            )
            or not math.isclose(sum(self.probabilities), 1, abs_tol=1e-6)
        ):
            raise ValueError("Outcome requires five normalized probabilities")
        if self.confidence is not None and (
            type(self.confidence) not in (int, float)
            or not math.isfinite(self.confidence)
            or not 0 <= self.confidence <= 1
        ):
            raise ValueError("Invalid confidence")

    @property
    def expected_level(self) -> float | None:
        return (
            sum(i * p for i, p in enumerate(self.probabilities, 1)) if self.probabilities else None
        )


class BatchScorer(Protocol):
    def score_batch(self, items: list[BaseWordRow]) -> list[Outcome]: ...
