"""Source-bounded exact-form evidence from local DEX snapshots; no model or DB I/O."""

from dataclasses import dataclass, field
from html.parser import HTMLParser
import hashlib
import json
from pathlib import Path
import re
from tempfile import TemporaryDirectory

from .dataset import _lexeme, _read_csv, _sha256, _vocabulary, _write_csv

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
    "source_path",
    "source_sha256",
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
        return "".join(
            c.text(exclude) if isinstance(c, _Node) else c for c in self.children
        )


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


def _senses(html, target):
    page = _Page(html)
    heading = None
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
                        alternatives.extend(
                            part.strip() for part in _text(variant).split(",")
                        )
                headings.append(
                    (
                        spelling,
                        _pos(_text(pos_node)),
                        target in {_lexeme(w) for w in alternatives if w},
                    )
                )
            parents = {}
            for item in node.nodes():
                if not item.has("type-meaning"):
                    continue
                ancestor = item.parent
                inherited, parent_id, excluded = [], "", False
                while ancestor is not node:
                    if ancestor is None:
                        break
                    excluded |= ancestor.has("type-etymology") or ancestor.has(
                        "type-example"
                    )
                    if id(ancestor) in parents and not parent_id:
                        parent_id, inherited = parents[id(ancestor)]
                    ancestor = ancestor.parent
                if excluded:
                    continue
                # Only this item's own container; nested meanings own their tags/text.
                containers = [
                    n
                    for n in item.children
                    if isinstance(n, _Node) and n.has("meaningContainer")
                ]
                if not containers:
                    continue
                container = containers[0]
                tags = sorted(
                    set(
                        inherited
                        + [
                            _lexeme(_text(n))
                            for n in container.nodes()
                            if n.has("meaning-tags") and _text(n)
                        ]
                    )
                )
                sense_id = container.attrs.get("id", "")
                parents[id(item)] = (sense_id, tags)
                definitions = [n for n in container.nodes() if n.has("tree-def")]
                if definitions:
                    for spelling, pos, matched in headings:
                        yield dict(
                            heading=spelling,
                            pos=pos,
                            sense_id=sense_id,
                            parent_sense_id=parent_id,
                            definition=_text(definitions[0]),
                            tags=json.dumps(tags, ensure_ascii=False),
                            alignment="exact" if matched else "unresolved",
                        )
            heading = None


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


def export_local_evidence(
    vocabulary_csv, loc_file, sources_csv, mentions_csv, output_dir
):
    """Write explicit senses and one evidence row per inventory ID, atomically."""
    if output_dir.exists() or output_dir.is_symlink():
        raise FileExistsError(output_dir)
    vocabulary = _vocabulary(vocabulary_csv)
    loc = _loc(loc_file)
    sources = _read_csv(sources_csv, {"word", "path", "sha256", "format"})
    mention_rows = _read_csv(
        mentions_csv, {"word_id", "word", "other_definition_count"}
    )
    mentions = {}
    identities = {r["word_id"]: r["word"] for r in vocabulary}
    for row in mention_rows:
        if (
            set(row) != {"word_id", "word", "other_definition_count"}
            or row["word_id"] in mentions
            or identities.get(row["word_id"]) != row["word"]
        ):
            raise ValueError("Invalid mention schema or identity")
        count = int(row["other_definition_count"])
        if count < 0:
            raise ValueError("Negative mention count")
        mentions[row["word_id"]] = row
    if mentions.keys() != identities.keys():
        raise ValueError("Mentions must cover every inventory ID")
    by_form = {}
    for row in vocabulary:
        by_form.setdefault(_lexeme(row["word"]), []).append(row)
    senses, ledger = [], []
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
                or any(
                    not isinstance(payload.get(k), str)
                    for k in ("original", "status", "html")
                )
                or _lexeme(payload["original"]) != _lexeme(source["word"])
            ):
                raise ValueError(f"Source cache identity mismatch: {path}")
            html = payload["html"] if payload["status"] == "ok" else ""
        ledger.append(dict(source, path=str(path.resolve())))
        for sense in _senses(html, _lexeme(source["word"])):
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
                    "source_bounded"
                    if required and required <= positions
                    else "unresolved"
                ),
                aligned_senses=len(aligned),
                other_definition_count=int(
                    mentions[row["word_id"]]["other_definition_count"]
                ),
                all_restricted=int(
                    bool(aligned) and all(_restricted(s) for s in aligned)
                ),
                all_specialist=int(
                    bool(aligned) and all(_specialist(s) for s in aligned)
                ),
            )
        )
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=output_dir.parent, prefix=".local-evidence-") as temp:
        staged = Path(temp) / "output"
        staged.mkdir()
        _write_csv(staged / "senses.csv", SENSE_FIELDS, senses)
        _write_csv(staged / "evidence.csv", EVIDENCE_FIELDS, evidence)
        _write_csv(
            staged / "source-files.csv", ["word", "path", "sha256", "format"], ledger
        )
        manifest = dict(
            policy=POLICY,
            inputs={
                str(p.resolve()): _sha256(p)
                for p in (vocabulary_csv, loc_file, sources_csv, mentions_csv)
            },
            implementation={
                str(p.resolve()): _sha256(p)
                for p in (Path(__file__), Path(__file__).with_name("dataset.py"))
            },
            artifacts={p.name: _sha256(p) for p in staged.iterdir()},
        )
        (staged / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
        staged.rename(output_dir)
    return dict(rows=len(evidence), senses=len(senses))
