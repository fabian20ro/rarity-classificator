from __future__ import annotations

from pathlib import Path

DEFAULT_LMSTUDIO_BASE_URL = "http://127.0.0.1:1234"
OPENAI_CHAT_COMPLETIONS_PATH = "/v1/chat/completions"
OPENAI_MODELS_PATH = "/v1/models"
LMSTUDIO_CHAT_PATH = "/api/v1/chat"
LMSTUDIO_MODELS_PATH = "/api/v1/models"

MODEL_GPT_OSS_20B = "openai/gpt-oss-20b"
MODEL_GLM_47_FLASH = "zai-org/glm-4.7-flash"
MODEL_MINISTRAL_3_8B = "ministral-3-8b-instruct-2512-mixed-8-6-bit"
MODEL_EUROLLM_22B_MLX_4BIT = "mlx-community/EuroLLM-22B-Instruct-2512-mlx-4bit"
MODEL_EUROLLM_22B = "eurollm-22b-instruct-2512-mlx"

DEFAULT_BATCH_SIZE = 50
DEFAULT_MAX_RETRIES = 3
DEFAULT_TIMEOUT_SECONDS = 300
DEFAULT_PREFLIGHT_TIMEOUT_SECONDS = 5
DEFAULT_MAX_TOKENS = 8000
MODEL_CRASH_BACKOFF_SECONDS = 10

DEFAULT_OUTLIER_THRESHOLD = 2
DEFAULT_CONFIDENCE_THRESHOLD = 0.55
FALLBACK_RARITY_LEVEL = 4

DEFAULT_REBALANCE_BATCH_SIZE = 600
DEFAULT_REBALANCE_LOWER_RATIO = 1.0 / 3.0
DEFAULT_REBALANCE_TRANSITIONS = "2:1,3:2,4:3"

REBALANCE_FROM_LEVEL_PLACEHOLDER = "{{FROM_LEVEL}}"
REBALANCE_TO_LEVEL_PLACEHOLDER = "{{TO_LEVEL}}"
REBALANCE_OTHER_LEVEL_PLACEHOLDER = "{{OTHER_LEVEL}}"
REBALANCE_TARGET_COUNT_PLACEHOLDER = "{{TARGET_COUNT}}"
REBALANCE_COMMON_LEVEL_PLACEHOLDER = "{{COMMON_LEVEL}}"
REBALANCE_COMMON_COUNT_PLACEHOLDER = "{{COMMON_COUNT}}"
USER_INPUT_PLACEHOLDER = "{{INPUT_JSON}}"

_RE = __import__("re").compile(r"^\{\{[A-Z_]+\}\}$")

# Validate all placeholder constants at import time.
for _name, _value in (
    ("REBALANCE_FROM_LEVEL_PLACEHOLDER", REBALANCE_FROM_LEVEL_PLACEHOLDER),
    ("REBALANCE_TO_LEVEL_PLACEHOLDER", REBALANCE_TO_LEVEL_PLACEHOLDER),
    ("REBALANCE_OTHER_LEVEL_PLACEHOLDER", REBALANCE_OTHER_LEVEL_PLACEHOLDER),
    ("REBALANCE_TARGET_COUNT_PLACEHOLDER", REBALANCE_TARGET_COUNT_PLACEHOLDER),
    ("REBALANCE_COMMON_LEVEL_PLACEHOLDER", REBALANCE_COMMON_LEVEL_PLACEHOLDER),
    ("REBALANCE_COMMON_COUNT_PLACEHOLDER", REBALANCE_COMMON_COUNT_PLACEHOLDER),
    ("USER_INPUT_PLACEHOLDER", USER_INPUT_PLACEHOLDER),
):
    if not _RE.match(_value):
        raise ValueError(
            f"Placeholder '{_name}' has invalid format: "
            f"'{_value}' — expected double-brace uppercase token "
            f"(e.g. '{{{{FROM_LEVEL}}}}')."
        )

_CSV_HEADERS = {
    "base": ["word_id", "word", "type"],
    "run": [
        "word_id",
        "word",
        "type",
        "rarity_level",
        "tag",
        "confidence",
        "scored_at",
        "model",
        "run_slug",
    ],
    "comparison": [
        "word_id",
        "word",
        "type",
        "run_a_level",
        "run_a_confidence",
        "run_b_level",
        "run_b_confidence",
        "run_c_level",
        "run_c_confidence",
        "median_level",
        "spread",
        "is_outlier",
        "reason",
        "merge_strategy",
        "merge_rule",
        "final_level",
    ],
    "outliers": [
        "word_id",
        "word",
        "type",
        "run_a_level",
        "run_b_level",
        "run_c_level",
        "spread",
        "reason",
    ],
    "upload_report": ["word_id", "previous_level", "new_level", "source"],
    "upload_marker": [
        "uploaded_at",
        "uploaded_level",
        "upload_status",
        "upload_batch_id",
    ],
}

CSV_HEADERS = _CSV_HEADERS


def ensure_csv_headers() -> None:
    """Ensure every documented header alias is present, non-empty, and unique."""
    required_keys = (
        "base",
        "run",
        "comparison",
        "outliers",
        "upload_report",
        "upload_marker",
    )
    for key in required_keys:
        columns = _CSV_HEADERS.get(key) or []
        if not columns:
            raise ValueError(f"CSV header group '{key}' is empty or missing")
        if len(columns) != len(set(columns)):
            dupes = [c for c in set(columns) if columns.count(c) > 1]
            raise ValueError(
                f"CSV header group '{key}' contains duplicate columns: "
                f"{', '.join(sorted(dupes))}"
            )


ensure_csv_headers()

# Backward-compatible aliases — all consumers keep importing these names.
BASE_CSV_HEADERS = _CSV_HEADERS["base"]
RUN_CSV_HEADERS = _CSV_HEADERS["run"]
COMPARISON_CSV_HEADERS = _CSV_HEADERS["comparison"]
OUTLIERS_CSV_HEADERS = _CSV_HEADERS["outliers"]
UPLOAD_REPORT_HEADERS = _CSV_HEADERS["upload_report"]
UPLOAD_MARKER_HEADERS = _CSV_HEADERS["upload_marker"]


def ensure_output_dir(root: Path | None = None) -> Path:
    out = (root or Path("build") / "rarity").resolve()
    out.mkdir(parents=True, exist_ok=True)
    return out
