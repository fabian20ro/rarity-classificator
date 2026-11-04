"""Existing chat scorer adapted without changing its prompts or repair behavior."""

from ..lm.client import LmStudioClient, ScoringContext
from ..models import BaseWordRow
from .base import Outcome


class ChatScorer:
    def __init__(self, client: LmStudioClient, context: ScoringContext):
        self.client = client
        self.context = context

    def score_batch(self, items: list[BaseWordRow]) -> list[Outcome]:
        scores = self.client.score_batch_resilient(batch=items, context=self.context)
        by_id = {score.word_id: score for score in scores}
        if len(by_id) != len(scores) or not set(by_id) <= {item.word_id for item in items}:
            raise ValueError("Chat response has duplicate or foreign word IDs")
        return [
            Outcome(item.word_id, score.rarity_level, tag=score.tag, confidence=score.confidence)
            if (score := by_id.get(item.word_id)) is not None
            else Outcome(item.word_id, None, status="failed", error="No valid chat score")
            for item in items
        ]
