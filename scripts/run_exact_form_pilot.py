"""Reproduce the frozen pilot's offline exact-form comparison; no model access.

The 150-form pilot and its reviewed case packs are local research artifacts.
This wrapper only selects lexical fields; human/assistant labels never enter forms.csv.
"""

import argparse
import csv
import hashlib
import json
from pathlib import Path

from classificator.evaluation.exact_form import prepare_exact_forms
from classificator.evaluation.definition_frequency import export_rebus_frequencies
from classificator.evaluation.form_frequency_report import compare_form_frequencies


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pilot", type=Path, required=True)
    parser.add_argument("--loc-file", type=Path, required=True)
    parser.add_argument("--dex-cache", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    pilot = args.pilot.resolve()
    data = pilot / "data"
    reference = data / "evaluations/2026-10-21-fabian-short/working-reference-150.csv"
    inputs = [reference, data / "dataset/vocabulary.csv", data / "frequencies.csv", args.loc_file]
    manifests = [reference.parent / "import-manifest.json", data / "dataset/manifest.json"]
    for path in manifests:
        manifest = json.loads(path.read_text())
        for name, expected in manifest["artifacts"].items():
            if sha(path.parent / name) != expected:
                raise ValueError(f"Frozen artifact changed: {path.parent/name}")
    contexts = []
    for folder in ["review-12", "review-2", "review-consolidated", "review-remaining"]:
        path = pilot / folder / "cases.json"
        inputs.append(path)
        pack = json.loads(path.read_text())
        manifest_path = path.parent / "manifest.json"
        if manifest_path.exists():
            manifest = json.loads(manifest_path.read_text())
            hashes = manifest.get("artifacts", manifest.get("files", {}))
            if hashes["cases.json"] != sha(path):
                raise ValueError(f"Frozen case pack changed: {path}")
        for item in pack["items"]:
            senses = item.get("senses", [item])
            for sense in senses:
                sid = sense.get("id", item.get("sense_id"))
                contexts.append(
                    dict(
                        word_id=item["word_id"],
                        word=item["word"],
                        context_id=item["word_id"] + ":" + sid,
                        pos=item["pos"],
                        meaning=sense["meaning"],
                        example=sense["example"],
                        source=json.dumps(
                            dict(
                                pack=str(path),
                                sources=item["sources"],
                                snapshot=item.get("source_snapshot"),
                                indices=item.get("definition_indices"),
                            ),
                            ensure_ascii=False,
                        ),
                    )
                )
    # Later audits refine earlier wording for the same lexical context. Retain all sources.
    unique = {}
    for context in contexts:
        previous = unique.get(context["context_id"])
        sources = json.loads(previous["source"]) if previous else []
        sources.append(json.loads(context["source"]))
        unique[context["context_id"]] = dict(
            context, source=json.dumps(sources, ensure_ascii=False)
        )
    contexts = list(unique.values())
    args.output.mkdir(parents=True)
    context_path = args.output / "contexts.csv"
    with context_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(contexts[0]))
        writer.writeheader()
        writer.writerows(contexts)
    source_manifest = dict(
        inputs={str(p.resolve()): sha(p) for p in inputs},
        artifacts={"contexts.csv": sha(context_path)},
        context_count=len(contexts),
        script_sha256=sha(Path(__file__)),
    )
    (args.output / "inputs.json").write_text(json.dumps(source_manifest, indent=2) + "\n")
    forms = prepare_exact_forms(
        data / "dataset/vocabulary.csv", args.loc_file, context_path, args.output / "forms"
    )
    print(f"Frozen {forms['count']} forms / {len(contexts)} lexical contexts", flush=True)
    rebus = export_rebus_frequencies(
        data / "dataset/vocabulary.csv", args.dex_cache, args.output / "rebus"
    )
    print(json.dumps(rebus, default=str, indent=2), flush=True)
    result = compare_form_frequencies(
        reference,
        forms["forms"],
        data / "frequencies.csv",
        rebus["frequencies"],
        args.output / "comparison",
    )
    print(json.dumps(result, indent=2), flush=True)


if __name__ == "__main__":
    main()
