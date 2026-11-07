"""Strict shared lexical CSV boundary; estimates and reference labels forbidden."""

import json

from .dataset import _lexeme, _read_csv


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key: " + key)
        result[key] = value
    return result


def missing_definition_pos(value):
    """Conservative POS coverage, preserving noun gender; never exhaustiveness."""

    def covered(required, supplied):
        if required.startswith("substantiv"):
            genders = {g for g in ("masculin", "feminin", "neutru") if g in required}
            return supplied.startswith("substantiv") and all(g in supplied for g in genders)
        return required.split()[0] == supplied.split()[0]

    return sorted(
        p for p in value["valid_pos"] if not any(covered(p, s["pos"]) for s in value["senses"])
    )


def read_lexical_evidence(path, items, *, allow_historical_incomplete=False):
    inventory = {i.word_id: i.word for i in items}
    result = {}
    sense_fields = {
        "pos",
        "definition",
        "number_restriction",
        "grammar",
        "context",
        "context_incomplete",
    }

    def strings(value):
        return isinstance(value, list) and all(isinstance(x, str) and x.strip() for x in value)

    for row in _read_csv(path, {"word_id", "word", "evidence_json"}):
        wid = int(row["word_id"])
        if (
            set(row) != {"word_id", "word", "evidence_json"}
            or wid in result
            or inventory.get(wid) != row["word"]
        ):
            raise ValueError("Evidence schema/identity mismatch")
        value = json.loads(row["evidence_json"], object_pairs_hook=_unique)
        if (
            not isinstance(value, dict)
            or not {"coverage", "valid_pos", "senses"} <= set(value)
            or set(value) - {"coverage", "valid_pos", "senses", "missing_definition_pos"}
            or value["coverage"] != "source_bounded_not_exhaustive"
            or not strings(value["valid_pos"])
            or not value["valid_pos"]
            or not isinstance(value["senses"], list)
        ):
            raise ValueError("Invalid lexical evidence; labels/estimates forbidden")
        for sense in value["senses"]:
            if (
                not isinstance(sense, dict)
                or not sense_fields <= set(sense)
                or set(sense) - sense_fields - {"usage_labels", "form_relation"}
                or any(
                    not isinstance(sense[k], str) or not sense[k].strip()
                    for k in ("pos", "definition")
                )
                or sense["number_restriction"] not in ("", "singular", "plural")
                or type(sense["context_incomplete"]) is not bool
                or (sense["context_incomplete"] and not allow_historical_incomplete)
                or any(not strings(sense[k]) for k in ("grammar", "context"))
                or ("usage_labels" in sense and not strings(sense["usage_labels"]))
            ):
                raise ValueError("Invalid or incomplete sense; labels/estimates forbidden")
            if "form_relation" in sense:
                relation = sense["form_relation"]
                if (
                    not isinstance(relation, dict)
                    or set(relation) != {"exact_form", "source_heading", "relation"}
                    or relation["exact_form"] != row["word"]
                    or not isinstance(relation["source_heading"], str)
                    or not relation["source_heading"].strip()
                    or relation["relation"]
                    not in {"literal_heading", "inflection", "explicit_variant"}
                ):
                    raise ValueError("Invalid form relation")
                same = _lexeme(relation["source_heading"]) == _lexeme(row["word"])
                if (relation["relation"] == "literal_heading" and not same) or (
                    relation["relation"] == "inflection" and same
                ):
                    raise ValueError("Contradictory form relation")
        if "missing_definition_pos" in value and value[
            "missing_definition_pos"
        ] != missing_definition_pos(value):
            raise ValueError("Inconsistent POS coverage")
        result[wid] = value
    if set(result) != set(inventory):
        raise ValueError("Evidence must cover every exact form, including missing senses")
    return result


