from __future__ import annotations

import sys
from dataclasses import replace

from ..constants import (
    MODEL_EUROLLM_22B,
    MODEL_EUROLLM_22B_MLX_4BIT,
    MODEL_GLM_47_FLASH,
    MODEL_GPT_OSS_20B,
    MODEL_MINISTRAL_3_8B,
)
from ..models import LmModelConfig


DEFAULT_FALLBACK = LmModelConfig(model_id="fallback", temperature=0.0, top_k=40, top_p=1.0)

DEFAULTS = {
    MODEL_GPT_OSS_20B.lower(): LmModelConfig(
        model_id=MODEL_GPT_OSS_20B,
        temperature=0.0,
        top_k=40,
        top_p=1.0,
        max_tokens_cap=4096,
        reasoning_effort="low",
    ),
    MODEL_GLM_47_FLASH.lower(): LmModelConfig(
        model_id=MODEL_GLM_47_FLASH,
        temperature=0.0,
        top_k=40,
        top_p=1.0,
        max_tokens_cap=2048,
        reasoning_effort="low",
        enable_thinking=False,
        thinking_type="disabled",
    ),
    MODEL_MINISTRAL_3_8B.lower(): LmModelConfig(
        model_id=MODEL_MINISTRAL_3_8B,
        temperature=0.0,
        top_k=40,
        top_p=1.0,
        max_tokens_cap=3072,
    ),
    MODEL_EUROLLM_22B_MLX_4BIT.lower(): LmModelConfig(
        model_id=MODEL_EUROLLM_22B_MLX_4BIT,
        temperature=0.0,
        top_k=40,
        top_p=1.0,
        max_tokens_cap=3072,
    ),
    MODEL_EUROLLM_22B.lower(): LmModelConfig(
        model_id=MODEL_EUROLLM_22B,
        temperature=0.0,
        top_k=40,
        top_p=1.0,
        max_tokens_cap=3072,
    ),
}

KNOWN_MODELS: frozenset[str] = frozenset(DEFAULTS.keys())

# Cross-check imported MODEL_* constants against DEFAULTS — surfaces silent drift.
_EXPECTED_KEYS = {name.lower() for name in (MODEL_GPT_OSS_20B, MODEL_GLM_47_FLASH, MODEL_MINISTRAL_3_8B, MODEL_EUROLLM_22B_MLX_4BIT, MODEL_EUROLLM_22B)}
if KNOWN_MODELS != _EXPECTED_KEYS:
    missing = ', '.join(sorted(_EXPECTED_KEYS - KNOWN_MODELS))
    extra = ', '.join(sorted(KNOWN_MODELS - _EXPECTED_KEYS))
    raise AssertionError(f"model_profiles drift: unregistered MODEL_* constants: {missing}; unexpected entries: {extra}")


def resolve_model_config(model: str) -> LmModelConfig:
    key = model.strip().lower()
    if not key:
        raise ValueError(
            f"Invalid model ID (empty or whitespace-only): {model!r}"
        )
    cfg = DEFAULTS.get(key, DEFAULT_FALLBACK)
    if cfg is DEFAULT_FALLBACK:
        known = ', '.join(sorted(KNOWN_MODELS))
        print(
            f"Warning: unknown model '{model}' — using default fallback profile "
            f"(temperature=0.0). Known models: {known}. "
            f"Configure an explicit entry in model_profiles.py to pin decoding params.",
            file=sys.stderr,
        )
    return replace(cfg, model_id=model)
