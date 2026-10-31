"""Publish an estimate-free annotation pack; predictions stay outside the web root."""

import hashlib
import json
import random
import re
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import urlsplit

from .dataset import _sha256
from .exact_form import RUBRIC_ID


def build_blind_review(forms_json: Path, output_dir: Path, *, version: str, seed: int):
    if output_dir.exists() or output_dir.is_symlink():
        raise FileExistsError(output_dir)
    if not re.fullmatch(r"[a-z0-9-]+", version) or type(seed) is not int:
        raise ValueError("Explicit version and integer seed required")
    payload = json.loads(forms_json.read_text())
    if set(payload) != {"forms"} or not isinstance(payload["forms"], list) or not payload["forms"]:
        raise ValueError("Expected lexical forms only")
    ids = set()
    words = set()
    for form in payload["forms"]:
        if set(form) != {"word_id", "word", "contexts"}:
            raise ValueError("Public forms must not contain scores, strata or frequency")
        if (
            not isinstance(form["word_id"], str)
            or not form["word_id"].isdigit()
            or int(form["word_id"]) <= 0
        ):
            raise ValueError("Invalid form ID")
        if form["word_id"] in ids or form["word"] in words:
            raise ValueError("Duplicate form")
        ids.add(form["word_id"])
        words.add(form["word"])
        if not isinstance(form["word"], str) or not form["word"].strip():
            raise ValueError("Invalid form spelling")
        if not isinstance(form["contexts"], list) or not form["contexts"]:
            raise ValueError("Every card requires relevant lexical contexts")
        context_ids = set()
        for context in form["contexts"]:
            if set(context) != {"context_id", "pos", "meaning", "example", "source"}:
                raise ValueError("Unexpected context fields")
            if any(not isinstance(value, str) or not value.strip() for value in context.values()):
                raise ValueError("Lexical fields must be nonempty text")
            if not context["source"].startswith("https://"):
                raise ValueError("Expected HTTPS dictionary source")
            if (
                not context["context_id"].startswith(form["word_id"] + ":")
                or context["context_id"] in context_ids
            ):
                raise ValueError("Invalid context identity")
            context_ids.add(context["context_id"])
    random.Random(seed).shuffle(payload["forms"])
    data = dict(version=version, rubric=RUBRIC_ID, forms=payload["forms"])
    serialized = json.dumps(data, ensure_ascii=False, sort_keys=True)
    data["pack_sha256"] = hashlib.sha256(serialized.encode()).hexdigest()
    assets = Path(__file__).with_name("assets")
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=output_dir.parent, prefix=".blind-") as temp:
        staged = Path(temp) / "public"
        staged.mkdir()
        serialized = json.dumps(data, ensure_ascii=False, indent=2)
        (staged / "cases.json").write_text(serialized + "\n")
        html = (
            (assets / "blind.html")
            .read_text()
            .replace("__DATA__", serialized.replace("<", "\\u003c"))
        )
        (staged / "index.html").write_text(html)
        for source, target in [("blind.js", "app.js"), ("blind.css", "style.css")]:
            (staged / target).write_bytes((assets / source).read_bytes())
        manifest = dict(
            version=version,
            pack_sha256=data["pack_sha256"],
            files={
                name: _sha256(staged / name)
                for name in ("cases.json", "index.html", "app.js", "style.css")
            },
        )
        (staged / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
        staged.rename(output_dir)
    return dict(count=len(data["forms"]), version=version, pack_sha256=data["pack_sha256"])


def build_risk_review(forms_json: Path, output_dir: Path, *, version: str, seed: int):
    """Publish at most 50 lexical-only cards, including honest missing-context cards.

    Predictions and risk flags stay outside the public pack. A separate UI namespace
    prevents this round from replacing any earlier blind-review answers.
    """
    if output_dir.exists() or output_dir.is_symlink():
        raise FileExistsError(output_dir)
    if not re.fullmatch(r"[a-z0-9-]+", version) or type(seed) is not int:
        raise ValueError("Explicit version and integer seed required")
    payload = json.loads(forms_json.read_text())
    if (
        not isinstance(payload, dict)
        or set(payload) != {"forms"}
        or not isinstance(payload["forms"], list)
        or not 1 <= len(payload["forms"]) <= 50
    ):
        raise ValueError("Require 1..50 lexical forms; never fill the review budget")
    ids, words = set(), set()

    def texts(values):
        return isinstance(values, list) and all(
            isinstance(value, str) and value.strip() for value in values
        )

    for form in payload["forms"]:
        if not isinstance(form, dict) or set(form) != {"word_id", "word", "valid_pos", "contexts"}:
            raise ValueError("Only lexical form fields permitted")
        wid, word = form["word_id"], form["word"]
        if (
            not isinstance(wid, str)
            or not re.fullmatch(r"[1-9][0-9]*", wid)
            or wid in ids
            or not isinstance(word, str)
            or not word.strip()
            or word in words
        ):
            raise ValueError("Invalid or duplicate exact-form identity")
        ids.add(wid)
        words.add(word)
        if (
            not texts(form["valid_pos"])
            or not form["valid_pos"]
            or not isinstance(form["contexts"], list)
        ):
            raise ValueError("Valid POS required; missing contexts must be an empty list")
        context_ids = set()
        for context in form["contexts"]:
            if not isinstance(context, dict) or set(context) != {
                "context_id",
                "pos",
                "meaning",
                "restrictions",
                "source",
            }:
                raise ValueError("Only lexical context fields permitted")
            if any(
                not isinstance(context[k], str) or not context[k].strip()
                for k in ("context_id", "pos", "meaning", "source")
            ) or not texts(context["restrictions"]):
                raise ValueError("Nonempty sense text and explicit restrictions required")
            cid = context["context_id"]
            if not cid.startswith(wid + ":") or cid == wid + ":" or cid in context_ids:
                raise ValueError("Invalid or duplicate context identity")
            context_ids.add(cid)
            source = urlsplit(context["source"])
            if (
                source.scheme != "https"
                or not source.hostname
                or source.username
                or source.password
            ):
                raise ValueError("HTTPS dictionary source required")
    data = dict(version=version, rubric=RUBRIC_ID, mode="risk", forms=payload["forms"])
    random.Random(seed).shuffle(data["forms"])
    serialized = json.dumps(data, ensure_ascii=False, sort_keys=True)
    data["pack_sha256"] = hashlib.sha256(serialized.encode()).hexdigest()
    assets = Path(__file__).with_name("assets")
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=output_dir.parent, prefix=".risk-review-") as temp:
        staged = Path(temp) / "public"
        staged.mkdir()
        serialized = json.dumps(data, ensure_ascii=False, indent=2)
        (staged / "cases.json").write_text(serialized + "\n")
        html = (
            (assets / "blind.html")
            .read_text()
            .replace("Lot independent", "Revizuire · maximum 50 de forme")
            .replace("__DATA__", serialized.replace("<", "\\u003c"))
        )
        (staged / "index.html").write_text(html)
        for source, target in [("blind.js", "app.js"), ("blind.css", "style.css")]:
            (staged / target).write_bytes((assets / source).read_bytes())
        manifest = dict(
            version=version,
            pack_sha256=data["pack_sha256"],
            input_sha256=_sha256(forms_json),
            files={
                name: _sha256(staged / name)
                for name in ("cases.json", "index.html", "app.js", "style.css")
            },
        )
        (staged / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
        staged.rename(output_dir)
    return dict(
        count=len(data["forms"]),
        without_context=sum(not f["contexts"] for f in data["forms"]),
        version=version,
        pack_sha256=data["pack_sha256"],
    )
