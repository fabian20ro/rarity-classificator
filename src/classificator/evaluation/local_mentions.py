"""Validate lineage of frozen outside-own-page dictionary mention counts."""

import json
from pathlib import Path

from .dataset import _read_csv, _sha256
from .definition_frequency import POLICY as CORPUS_POLICY

POLICY = "exact-form-outside-own-page-definitions-v1"
REFERENCES = ("corpus_manifest", "source_ledger", "extractor", "derivation")


def validate_local_mentions(mentions_csv, vocabulary_csv, vocabulary):
    sidecar = mentions_csv.with_suffix(mentions_csv.suffix + ".metadata.json")
    if not sidecar.is_file():
        raise ValueError("Missing mention provenance metadata sidecar")
    metadata = json.loads(sidecar.read_text())
    if (
        not isinstance(metadata, dict)
        or set(metadata)
        != {"schema", "policy", "vocabulary_sha256", "mentions_sha256", *REFERENCES}
        or type(metadata["schema"]) is not int
        or metadata["schema"] != 1
        or metadata["policy"] != POLICY
    ):
        raise ValueError("Invalid mention metadata schema/policy")
    if metadata["vocabulary_sha256"] != _sha256(vocabulary_csv):
        raise ValueError("Mention vocabulary hash mismatch")
    if metadata["mentions_sha256"] != _sha256(mentions_csv):
        raise ValueError("Mention CSV hash mismatch")
    paths = {}
    for name in REFERENCES:
        ref = metadata[name]
        if (
            not isinstance(ref, dict)
            or set(ref) != {"path", "sha256"}
            or not isinstance(ref["path"], str)
            or not ref["path"].strip()
        ):
            raise ValueError("Invalid mention provenance reference")
        path = Path(ref["path"])
        path = path if path.is_absolute() else sidecar.parent / path
        if not path.is_file() or _sha256(path) != ref["sha256"]:
            raise ValueError("Mention provenance reference hash mismatch")
        paths[name] = path
    corpus = json.loads(paths["corpus_manifest"].read_text())
    if (
        not isinstance(corpus, dict)
        or corpus.get("policy") != CORPUS_POLICY
        or not isinstance(corpus.get("artifacts"), dict)
        or corpus["artifacts"].get("source-files.csv")
        != metadata["source_ledger"]["sha256"]
    ):
        raise ValueError("Mention corpus policy or source ledger mismatch")
    derivation = {}
    for row in _read_csv(
        paths["derivation"], {"word_id", "word", "rebus_other_definition_count"}
    ):
        if (
            row["word_id"] in derivation
            or int(row["word_id"]) <= 0
            or not row["word"].strip()
        ):
            raise ValueError("Invalid derivation identity")
        if int(row["rebus_other_definition_count"]) < 0:
            raise ValueError("Negative derivation count")
        derivation[row["word_id"]] = row
    mentions = {}
    identities = {r["word_id"]: r["word"] for r in vocabulary}
    for row in _read_csv(mentions_csv, {"word_id", "word", "other_definition_count"}):
        if (
            set(row) != {"word_id", "word", "other_definition_count"}
            or row["word_id"] in mentions
            or identities.get(row["word_id"]) != row["word"]
        ):
            raise ValueError("Invalid mention schema or identity")
        if int(row["other_definition_count"]) < 0:
            raise ValueError("Negative mention count")
        original = derivation.get(row["word_id"])
        if (
            original is None
            or original["word"] != row["word"]
            or int(original["rebus_other_definition_count"])
            != int(row["other_definition_count"])
        ):
            raise ValueError("Mention count or identity disagrees with derivation")
        mentions[row["word_id"]] = row
    if mentions.keys() != identities.keys():
        raise ValueError("Mentions must cover every inventory ID")
    return mentions, [sidecar, *paths.values()]
