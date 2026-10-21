"""Sequential System One adapter. Never manages model loading or unloading."""

import json
import math

import requests

from ..models import BaseWordRow
from .base import Outcome

RUBRIC = {
    "L1": "Core everyday vocabulary known and used by almost all Romanian adults.",
    "L2": "Common vocabulary readily understood by most Romanian adults.",
    "L3": "Moderately familiar vocabulary, not universal in everyday use.",
    "L4": "Rare vocabulary: specialized, regional or literary.",
    "L5": "Very obscure or strongly archaic vocabulary.",
}
INSTRUCTIONS = (
    "Rate familiarity of the exact Romanian lexical form to an ordinary adult "
    "Romanian speaker, through its most familiar valid sense across all valid parts of speech. "
    "The inventory_type is historical metadata, not a restriction. Lexical evidence is "
    "source-bounded, not exhaustive. Do not substitute a lemma, another inflection or "
    "a spelling with different diacritics. Lower level means more common. Meaning supplied by a "
    "definition does not imply familiarity. Judge familiarity independently "
    "of offensiveness or suitability. Do not impose population quotas."
)


class D1Scorer:
    def __init__(
        self,
        *,
        model: str,
        base_url: str = "http://127.0.0.1:1234",
        http=None,
        evidence=None,
        form_contract=None,
        min_probability: float = 0.0,
    ):
        if not math.isfinite(min_probability) or not 0 <= min_probability <= 1:
            raise ValueError("min_probability must be finite and in [0,1]")
        self.min_probability = min_probability
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.http = http if http is not None else requests.Session()
        self.evidence = evidence or {}
        self.form_contract = form_contract
        self._identity = None

    def preflight(self) -> dict:
        metadata = self.http.get(self.base_url + "/api/v1/models", timeout=30)
        metadata.raise_for_status()
        matches = [
            m
            for m in json.loads(metadata.text)["models"]
            if m.get("key") == self.model
            and m.get("type") == "decision"
            and len(m.get("loaded_instances", [])) == 1
        ]
        if len(matches) != 1:
            raise ValueError("Require one already loaded decision model instance: " + self.model)
        model = matches[0]
        if (
            not isinstance(model["loaded_instances"][0].get("id"), str)
            or not model["loaded_instances"][0]["id"]
        ):
            raise ValueError("Require an identified loaded decision model instance")
        identity = json.dumps(model, sort_keys=True)
        if self._identity is not None and self._identity != identity:
            raise ValueError("Loaded model identity/configuration changed")
        self._identity = identity
        return model

    def score_batch(self, items: list[BaseWordRow]) -> list[Outcome]:
        if self.form_contract is not None:
            for item in items:
                if (
                    item.word_id not in self.form_contract
                    or self.form_contract[item.word_id].get("word") != item.word
                ):
                    raise ValueError("Exact-form contract identity mismatch")
        outcomes = []
        for item in items:
            model = self.preflight()
            instance = model["loaded_instances"][0]["id"]
            payload = {
                "model": instance,
                "state": {
                    "word": item.word,
                    "inventory_type": item.type,
                    "form_contract": (
                        self.form_contract[item.word_id] if self.form_contract is not None else None
                    ),
                    "evidence": self.evidence.get(item.word_id, {}),
                },
                "questions": {
                    "rarity": {"type": "choice", "instructions": INSTRUCTIONS, "criteria": RUBRIC}
                },
            }
            raw_response = ""
            try:
                result = self.http.post(self.base_url + "/v1/systemone", json=payload, timeout=120)
                raw_response = result.text
                result.raise_for_status()
                answers = json.loads(result.text, object_pairs_hook=_unique_object)["answers"]
                if set(answers) != {"rarity"}:
                    raise ValueError("Expected exactly the rarity answer")
                answer = answers["rarity"]
                distribution = answer["probabilities"]
                if set(distribution) != set(RUBRIC):
                    raise ValueError("Expected exactly L1..L5 probabilities")
                probabilities = tuple(distribution[key] for key in RUBRIC)
                if any(
                    type(p) not in (int, float) or not math.isfinite(p) or not 0 <= p <= 1
                    for p in probabilities
                ):
                    raise ValueError("Probabilities must be finite numbers in [0,1]")
                if not math.isclose(sum(probabilities), 1, abs_tol=1e-6):
                    raise ValueError("Probabilities must sum to 1")
                if answer["choice"] not in RUBRIC:
                    raise ValueError("Unknown choice")
                # Deterministic argmax policy; API confidence is not correctness.
                level = max(range(5), key=probabilities.__getitem__) + 1
                outcomes.append(
                    Outcome(
                        item.word_id,
                        level,
                        probabilities,
                        status=(
                            "scored" if max(probabilities) >= self.min_probability else "unresolved"
                        ),
                        confidence=max(probabilities),
                        request=payload,
                        response=raw_response,
                    )
                )
            except (ValueError, KeyError, TypeError, requests.RequestException) as exc:
                outcomes.append(
                    Outcome(
                        item.word_id,
                        None,
                        status="failed",
                        error=str(exc),
                        request=payload,
                        response=raw_response,
                    )
                )
        return outcomes


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key: " + key)
        result[key] = value
    return result
