"""Source-bounded exact-form evidence from local DEX snapshots; no model or DB I/O."""

from dataclasses import dataclass, field
from collections import Counter
from html.parser import HTMLParser
import hashlib
import json
from pathlib import Path
import re
from tempfile import TemporaryDirectory

from .dataset import _lexeme, _read_csv, _sha256, _vocabulary, _write_csv
from .local_mentions import validate_local_mentions

POLICY = "local-lexical-evidence-v1"
EVIDENCE_FIELDS = [
    "word_id",
    "word",
    "loc_pos",
    "aligned_pos",
    "alignment",
    "aligned_senses",
    "other_definition_count",
    "all_restricted",
    "all_specialist",
]
SENSE_FIELDS = [
    "word_id",
    "word",
    "heading",
    "pos",
    "sense_id",
    "parent_sense_id",
    "definition",
    "tags",
    "alignment",
    "alignment_reason",
    "number_restriction",
    "source_path",
    "source_sha256",
    "pos_detail",
    "source_entry_id",
    "source_dictionary",
    "variant_id",
    "variant_number_restriction",
    "witness_text",
]


@dataclass
class _Node:
    tag: str
    attrs: dict = field(default_factory=dict)
    children: list = field(default_factory=list)
    parent: object = None

    def has(self, name):
        return name in self.attrs.get("class", "").split()

    def nodes(self):
        for child in self.children:
            if isinstance(child, _Node):
                yield child
                yield from child.nodes()

    def text(self, exclude=()):
        if self.tag in {"script", "style", "sup"} or any(self.has(c) for c in exclude):
            return ""
        return "".join(c.text(exclude) if isinstance(c, _Node) else c for c in self.children)


class _Page(HTMLParser):
    VOID = {
        "area",
        "base",
        "br",
        "col",
        "embed",
        "hr",
        "img",
        "input",
        "link",
        "meta",
        "param",
        "source",
        "track",
        "wbr",
    }

    def __init__(self, html):
        super().__init__(convert_charrefs=True)
        self.root = _Node("root")
        self.current = self.root
        self.feed(html)
        self.close()

    def handle_starttag(self, tag, attrs):
        node = _Node(tag, dict(attrs), parent=self.current)
        self.current.children.append(node)
        if tag not in self.VOID:
            self.current = node

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in self.VOID:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        node = self.current
        while node.parent is not None:
            if node.tag == tag:
                self.current = node.parent
                return
            node = node.parent

    def handle_data(self, data):
        self.current.children.append(data)


def _text(node, exclude=()):
    return " ".join(node.text(exclude).split())


def _pos(text):
    text = _lexeme(text)
    if "substantiv" in text:
        return "N"
    for label, code in [
        ("adjectiv", "A"),
        ("adverb", "D"),
        ("pronume", "P"),
        ("prepoziție", "S"),
        ("conjuncție", "C"),
        ("interjecție", "I"),
        ("numeral", "M"),
        ("verb", "V"),
        ("articol", "T"),
    ]:
        if text.startswith(label):
            return code
    return ""


def _loc(loc_file):
    result = {}
    for line in loc_file.read_text().splitlines():
        fields = line.split()
        if len(fields) < 2:
            continue
        spelling = fields[0].replace("'", "").replace("’", "")
        if fields[1].isdigit():
            match = re.search(r"([A-Z]+)$", spelling)
            if not match:
                raise ValueError("Unknown LOC format")
            code, spelling = match[1], spelling[: match.start()]
        else:
            code = re.sub(r"\d.*", "", fields[1])
        # LOC noun genders collapse to the common POS family, never another spelling.
        code = {"F": "N", "M": "N", "MF": "N", "VT": "V"}.get(code, code)
        result.setdefault(_lexeme(spelling), set()).add(code)
    return result


def _senses(html, target, variants=()):
    page = _Page(html)
    heading = None
    heading_counts = Counter()
    for candidate in page.root.nodes():
        if candidate.has("tree-heading"):
            for pos_node in candidate.nodes():
                if pos_node.has("tree-pos-info"):
                    spelling = _text(pos_node.parent, ("tree-pos-info", "tree-inflected-form"))
                    heading_counts[(_lexeme(spelling), _pos(_text(pos_node)))] += 1
    for node in page.root.nodes():
        if node.has("tree-heading"):
            heading = node
        elif node.has("tree-body") and heading is not None:
            pos_nodes = [n for n in heading.nodes() if n.has("tree-pos-info")]
            headings = []
            for pos_node in pos_nodes:
                block = pos_node.parent
                spelling = _text(block, ("tree-pos-info", "tree-inflected-form"))
                alternatives = [spelling]
                for variant in block.nodes():
                    if variant.has("tree-inflected-form"):
                        alternatives.extend(part.strip() for part in _text(variant).split(","))
                pos = _pos(_text(pos_node))
                pos_text = _lexeme(_text(pos_node))
                numbers = set()
                if target == _lexeme(spelling) and "plural" not in pos_text:
                    numbers.add("singular")
                if (
                    "plural" in pos_text
                    or pos == "N"
                    and target in {_lexeme(w) for w in alternatives[1:] if w}
                ):
                    numbers.add("plural")
                headings.append(
                    (
                        spelling,
                        pos,
                        target in {_lexeme(w) for w in alternatives if w},
                        numbers,
                        _text(pos_node),
                    )
                )
            parents = {}
            for item in node.nodes():
                if not item.has("type-meaning"):
                    continue
                ancestor = item.parent
                inherited, parent_id, excluded, number = [], "", False, None
                while ancestor is not node:
                    if ancestor is None:
                        break
                    excluded |= ancestor.has("type-etymology") or ancestor.has("type-example")
                    if id(ancestor) in parents and not parent_id:
                        parent_id, inherited, number = parents[id(ancestor)]
                    ancestor = ancestor.parent
                if excluded:
                    continue
                # Only this item's own container; nested meanings own their tags/text.
                containers = [
                    n for n in item.children if isinstance(n, _Node) and n.has("meaningContainer")
                ]
                if not containers:
                    continue
                container = containers[0]
                own_tags = [
                    _lexeme(_text(n))
                    for n in container.nodes()
                    if n.has("meaning-tags") and _text(n)
                ]
                own_number = _number_restriction(own_tags)
                if own_number is not None:
                    number = own_number
                tags = sorted(set(inherited + own_tags))
                sense_id = container.attrs.get("id", "")
                parents[id(item)] = (sense_id, tags, number)
                definitions = [n for n in container.nodes() if n.has("tree-def")]
                if definitions:
                    for spelling, pos, matched, numbers, pos_detail in headings:
                        reason = (
                            "heading_mismatch"
                            if not matched
                            else (
                                "number_restriction"
                                if number and number not in numbers
                                else "literal_heading_or_inflection"
                            )
                        )
                        record = dict(
                            heading=spelling,
                            pos=pos,
                            sense_id=sense_id,
                            parent_sense_id=parent_id,
                            definition=_text(definitions[0]),
                            tags=json.dumps(tags, ensure_ascii=False),
                            alignment=(
                                "exact"
                                if reason == "literal_heading_or_inflection"
                                else "unresolved"
                            ),
                            alignment_reason=reason,
                            number_restriction=number or "",
                            pos_detail=pos_detail,
                            source_entry_id="",
                            source_dictionary="",
                            variant_id="",
                            variant_number_restriction="",
                            witness_text="",
                        )
                        yield record
                        if not matched:
                            dictionaries = {
                                n.attrs.get("title", "")
                                for n in container.nodes()
                                if n.has("badge-source")
                            }
                            for variant in variants:
                                if (
                                    variant["status"] != "supported"
                                    or variant["base_heading"] != _lexeme(spelling)
                                    or variant["base_pos"] != pos
                                    or heading_counts[(_lexeme(spelling), pos)] != 1
                                    or variant["source_dictionary"] not in dictionaries
                                ):
                                    continue
                                variant_number = variant["number_restriction"]
                                allowed = variant_number or "singular"
                                valid = not number or number == allowed
                                yield dict(
                                    record,
                                    pos=variant["pos"],
                                    pos_detail=variant["pos_detail"],
                                    tags=json.dumps(
                                        sorted(set(tags + json.loads(variant["tags"]))),
                                        ensure_ascii=False,
                                    ),
                                    alignment="exact" if valid else "unresolved",
                                    alignment_reason="explicit_variant"
                                    if valid
                                    else "number_restriction",
                                    source_entry_id=variant["source_entry_id"],
                                    source_dictionary=variant["source_dictionary"],
                                    variant_id=variant["variant_id"],
                                    variant_number_restriction=variant_number,
                                    witness_text=variant["witness_text"],
                                )
            heading = None


def _number_restriction(tags):
    """Nearest explicit number scope wins; nonexclusive usage is not a restriction."""
    text = re.sub(r"[()]", "", " ".join(tags))
    if not re.search(r"\b(plural|singular)\b", text):
        return None
    if re.search(r"mai ales|adesea|și la", text):
        return ""
    found = set(re.findall(r"\b(plural|singular)\b", text))
    return next(iter(found)) if len(found) == 1 else "unresolved"


VARIANT_FIELDS = [
    "word",
    "base_heading",
    "base_pos",
    "variant",
    "pos",
    "pos_detail",
    "tags",
    "number_restriction",
    "variant_id",
    "source_entry_id",
    "source_dictionary",
    "witness_text",
    "status",
    "reason",
    "source_path",
    "source_sha256",
]


def _parts(node):
    """Keep semantic abbreviation boundaries while ignoring presentation markup."""
    return [
        (
            child if isinstance(child, str) else _text(child),
            "" if isinstance(child, str) else child.attrs.get("data-bs-content", ""),
            "" if isinstance(child, str) else child.tag,
        )
        for child in node.children
    ]


def _numbered_meanings(parts):
    """Only the bounded MDA bracket-header + consecutive numbered-clause format."""
    closing = next((i for i, (text, _, _) in enumerate(parts) if "]" in text), None)
    if closing is None:
        return []
    segments = []
    for text, label, tag in parts[closing + 1 :]:
        if tag == "b" and text.strip().isdigit():
            if int(text.strip()) != len(segments) + 1:
                return []
            segments.append([])
        elif segments:
            segments[-1].append((text, label, tag))
        elif text.strip():
            return []
    result = []
    for index, segment in enumerate(segments, 1):
        tags, definition, begun = [], [], False
        for text, label, tag in segment:
            if label and not begun:
                tags.append(label)
            elif not begun and not text.strip(" ()[]"):
                continue
            else:
                # Freeform examples/relations are not parsed into semantic assertions.
                if label or tag not in {"", "b"}:
                    return []
                if not begun and tags:
                    text = text.lstrip(" )")
                begun = True
                definition.append(text)
        text = " ".join("".join(definition).split()).strip()
        if not text:
            return []
        result.append((index, text, tags))
    return result


def _raw_variant_senses(variant):
    if variant["status"] != "supported":
        return
    for index, definition, own_tags in variant["_raw_meanings"]:
        tags = sorted(set(json.loads(variant["tags"]) + own_tags))
        number = _number_restriction(own_tags) or ""
        variant_number = variant["number_restriction"]
        valid = not number or number == (variant_number or "singular")
        yield dict(
            heading=variant["base_heading"],
            pos=variant["pos"],
            pos_detail=variant["pos_detail"],
            sense_id=f"{variant['source_entry_id']}#meaning-{index}",
            parent_sense_id="",
            definition=definition,
            tags=json.dumps(tags, ensure_ascii=False),
            alignment="exact" if valid else "unresolved",
            alignment_reason="explicit_variant_raw_meaning" if valid else "number_restriction",
            number_restriction=number,
            variant_number_restriction=variant_number,
            variant_id=variant["variant_id"],
            witness_text=variant["witness_text"],
            source_entry_id=variant["source_entry_id"],
            source_dictionary=variant["source_dictionary"],
        )


def _variants(html, target):
    page = _Page(html)
    for entry in page.root.nodes():
        if not entry.has("def"):
            continue
        ancestor = entry.parent
        excluded = False
        while ancestor is not None:
            excluded |= (
                ancestor.has("type-example")
                or ancestor.has("type-etymology")
                or ancestor.tag in {"nav", "script", "style"}
            )
            ancestor = ancestor.parent
        if excluded:
            continue
        wrapper = entry.parent
        while wrapper is not None and not wrapper.has("defWrapper"):
            wrapper = wrapper.parent
        if wrapper is None:
            continue
        parts = _parts(entry)
        if not parts:
            continue
        first = next((text.strip().rstrip(",") for text, _, tag in parts if tag == "b"), "")
        base_pos = ""
        started = False
        for text, label, tag in parts:
            if not started:
                started = tag == "b"
                continue
            if "[" in text:
                break
            if _pos(label):
                base_pos = _pos(label)
                break
            if tag == "i" and re.match(r"vb\.", text.strip()):
                base_pos = "V"
                break
            if tag == "" and text.strip(" ,"):
                break
        if not first.isalpha():
            continue
        dictionary = next(
            (
                n.attrs.get("title", "")
                for n in wrapper.nodes()
                if n.tag == "a" and n.has("ref") and n.attrs.get("href", "").startswith("/sursa/")
            ),
            "",
        )
        entry_id = next(
            (
                n.attrs["href"]
                for n in wrapper.nodes()
                if n.tag == "a" and re.fullmatch(r"/definitie/[^/]+/\d+", n.attrs.get("href", ""))
            ),
            "",
        )
        raw_meanings = (
            _numbered_meanings(parts)
            if any(n.attrs.get("href") == "/sursa/mda2" for n in wrapper.nodes())
            else []
        )
        for index, (_, semantic, _) in enumerate(parts):
            if not _lexeme(semantic).startswith("variantă"):
                continue
            if any(
                _lexeme(label).startswith(("etimologie", "sinonim"))
                for _, label, _ in parts[:index]
            ):
                continue
            clause = []
            seen_variant, trailing_prose = False, False
            for text, label, tag in parts[index + 1 :]:
                if (
                    seen_variant
                    and not tag
                    and re.search(r"[^\W\d_]", text)
                    and not re.fullmatch(r"\s*[IVX]+\.\s*(?:/.*)?", text)
                ):
                    trailing_prose = True
                    break
                seen_variant |= not label and _lexeme(text.strip(" :()[],.")) == target
                match = re.search(r"[/\]–—]", text)
                clause.append(
                    (text[: match.start()] if match else text, label if not match else "", tag)
                )
                if match:
                    break
            words = [
                (text.strip(), label)
                for text, label, _ in clause
                if not label and text.strip(" :()[],.")
            ]
            spelling = words[0][0].strip(" :()[],.") if words else ""
            if _lexeme(spelling) != target:
                continue
            details = [label for _, label, _ in clause if _pos(label)]
            tags = [label for _, label, _ in clause if label and not _pos(label)]
            if len(details) == 1 and _pos(details[0]) == "V":
                words = [
                    (text, label)
                    for text, label in words
                    if not re.fullmatch(r"[IVX]+\.", text.strip())
                ]
            number = _number_restriction(tags + details) or ""
            reason = (
                "unknown_number_restriction"
                if number == "unresolved"
                else "missing_variant_pos"
                if len(details) != 1
                else "missing_source_identity"
                if not dictionary or not entry_id
                else "ambiguous_variant_clause"
                if len(words) != 1 or trailing_prose
                else "explicit_variant"
            )
            yield dict(
                base_heading=_lexeme(first),
                base_pos=base_pos,
                variant=target,
                pos=_pos(details[0]) if len(details) == 1 else "",
                pos_detail=details[0] if len(details) == 1 else "",
                tags=json.dumps(tags, ensure_ascii=False),
                number_restriction=number,
                variant_id=f"{entry_id}#variant-{index}",
                source_entry_id=entry_id,
                source_dictionary=dictionary,
                witness_text=" ".join(text for text, _, _ in clause).strip(),
                status="supported" if reason == "explicit_variant" else "unresolved",
                reason=reason,
                _raw_meanings=raw_meanings,
            )


def _restricted(sense):
    return bool(
        re.search(
            r"\b(învechit|arhaic|regional|rar)(?:ă|e|i)?\b|ieșit din uz",
            " ".join(json.loads(sense["tags"])),
        )
    )


def _specialist(sense):
    return bool(
        re.search(
            r"botanic|zoolog|geolog|mineralog|chimie|medicin|anatom|fizică|"
            r"matematic|tehnic|lingvistic|filozof|astronom|biolog|muzic",
            " ".join(json.loads(sense["tags"])),
        )
    )


def export_local_evidence(vocabulary_csv, loc_file, sources_csv, mentions_csv, output_dir):
    """Write explicit senses and one evidence row per inventory ID, atomically."""
    if output_dir.exists() or output_dir.is_symlink():
        raise FileExistsError(output_dir)
    vocabulary = _vocabulary(vocabulary_csv)
    loc = _loc(loc_file)
    sources = _read_csv(sources_csv, {"word", "path", "sha256", "format"})
    mentions, provenance_paths = validate_local_mentions(mentions_csv, vocabulary_csv, vocabulary)
    by_form = {}
    for row in vocabulary:
        by_form.setdefault(_lexeme(row["word"]), []).append(row)
    senses, ledger, variants_ledger = [], [], []
    for source in sources:
        if (
            set(source) != {"word", "path", "sha256", "format"}
            or _lexeme(source["word"]) not in by_form
            or source["format"] not in {"html", "cache_json"}
        ):
            raise ValueError("Invalid source schema or identity")
        path = Path(source["path"])
        if not path.is_absolute():
            path = sources_csv.parent / path
        raw = path.read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        if digest != source["sha256"]:
            raise ValueError(f"Source hash mismatch: {path}")
        html = raw.decode("utf-8")
        if source["format"] == "cache_json":
            payload = json.loads(html)
            if (
                not isinstance(payload, dict)
                or any(not isinstance(payload.get(k), str) for k in ("original", "status", "html"))
                or _lexeme(payload["original"]) != _lexeme(source["word"])
            ):
                raise ValueError(f"Source cache identity mismatch: {path}")
            html = payload["html"] if payload["status"] == "ok" else ""
        ledger.append(dict(source, path=str(path.resolve())))
        variants = list(_variants(html, _lexeme(source["word"])))
        variants_ledger.extend(
            dict(v, word=source["word"], source_path=str(path.resolve()), source_sha256=digest)
            for v in variants
        )
        source_senses = list(_senses(html, _lexeme(source["word"]), variants))
        for variant in variants:
            if not any(
                s["variant_id"] == variant["variant_id"] and s["alignment"] == "exact"
                for s in source_senses
            ):
                source_senses.extend(_raw_variant_senses(variant))
        for sense in source_senses:
            for row in by_form.get(_lexeme(source["word"]), []):
                senses.append(
                    dict(
                        word_id=row["word_id"],
                        word=row["word"],
                        **sense,
                        source_path=str(path.resolve()),
                        source_sha256=digest,
                    )
                )
    evidence = []
    for row in vocabulary:
        aligned = [
            s
            for s in senses
            if s["word_id"] == row["word_id"]
            and s["alignment"] == "exact"
            and s["definition"]
            and s["pos"]
        ]
        positions = {s["pos"] for s in aligned}
        required = loc.get(_lexeme(row["word"]), set())
        evidence.append(
            dict(
                word_id=row["word_id"],
                word=row["word"],
                loc_pos="|".join(sorted(required)),
                aligned_pos="|".join(sorted(positions)),
                alignment=(
                    "source_bounded" if required and required <= positions else "unresolved"
                ),
                aligned_senses=len(aligned),
                other_definition_count=int(mentions[row["word_id"]]["other_definition_count"]),
                all_restricted=int(bool(aligned) and all(_restricted(s) for s in aligned)),
                all_specialist=int(bool(aligned) and all(_specialist(s) for s in aligned)),
            )
        )
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=output_dir.parent, prefix=".local-evidence-") as temp:
        staged = Path(temp) / "output"
        staged.mkdir()
        _write_csv(staged / "senses.csv", SENSE_FIELDS, senses)
        _write_csv(staged / "variants.csv", VARIANT_FIELDS, variants_ledger)
        _write_csv(staged / "evidence.csv", EVIDENCE_FIELDS, evidence)
        _write_csv(staged / "source-files.csv", ["word", "path", "sha256", "format"], ledger)
        manifest = dict(
            policy=POLICY,
            extraction_revision="explicit-variants-v1",
            senses_schema=2,
            inputs={
                str(p.resolve()): _sha256(p)
                for p in (
                    vocabulary_csv,
                    loc_file,
                    sources_csv,
                    mentions_csv,
                    *provenance_paths,
                )
            },
            implementation={
                str(p.resolve()): _sha256(p)
                for p in (
                    Path(__file__),
                    Path(__file__).with_name("dataset.py"),
                    Path(__file__).with_name("local_mentions.py"),
                    Path(__file__).with_name("definition_frequency.py"),
                )
            },
            artifacts={p.name: _sha256(p) for p in staged.iterdir()},
        )
        (staged / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
        staged.rename(output_dir)
    return dict(rows=len(evidence), senses=len(senses))
