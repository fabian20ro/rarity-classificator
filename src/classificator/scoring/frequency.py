"""Exact-form frequency baseline with externally chosen, explicit thresholds."""

from collections.abc import Mapping
import math

from ..models import BaseWordRow
from .base import Outcome


class FrequencyScorer:
    """Classify frequency proportions (0..1); thresholds define L1..L4 minima.

    Select thresholds using development labels only; this scorer never fits them.
    Frequency is corpus evidence, not calibrated confidence. Outcomes deliberately
    omit confidence and probabilities and belong in evaluation predictions CSVs.
    """

    def __init__(
        self,
        frequencies: Mapping[int, float | None],
        *,
        thresholds: tuple[float, float, float, float],
    ):
        self.frequencies = dict(frequencies)
        self.thresholds = tuple(thresholds)
        if len(self.thresholds) != 4 or any(
            type(value) not in (int, float) or not math.isfinite(value) or not 0 < value <= 1
            for value in self.thresholds
        ):
            raise ValueError("Require four finite frequency thresholds in (0,1]")
        if any(left <= right for left, right in zip(self.thresholds, self.thresholds[1:])):
            raise ValueError("Frequency thresholds must be strictly descending")
        for word_id, frequency in self.frequencies.items():
            if type(word_id) is not int or word_id <= 0:
                raise ValueError("Frequency keys must be positive integer word IDs")
            if frequency is not None and (
                type(frequency) not in (int, float)
                or not math.isfinite(frequency)
                or not 0 <= frequency <= 1
            ):
                raise ValueError(f"Frequency for word_id {word_id} must be None or finite in [0,1]")

    def score_batch(self, items: list[BaseWordRow]) -> list[Outcome]:
        outcomes = []
        for item in items:
            frequency = self.frequencies.get(item.word_id)
            if frequency is None or frequency == 0:
                outcomes.append(
                    Outcome(
                        item.word_id,
                        None,
                        status="unresolved",
                        error="No observed frequency for this exact form",
                    )
                )
                continue
            level = 1 + sum(frequency < value for value in self.thresholds)
            outcomes.append(Outcome(item.word_id, level))
        return outcomes
