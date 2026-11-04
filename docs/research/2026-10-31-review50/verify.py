"""Independent stdlib verification: exact joins, metrics, replay and immutable inputs."""
import argparse
import csv
import hashlib
import json
from pathlib import Path


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    return list(csv.DictReader(Path(path).open(encoding="utf-8-sig")))


def verify(output, protected):
    manifest = json.loads((output / "manifest.json").read_text())
    for item in manifest["inputs"].values():
        assert sha(item["path"]) == item["sha256"], item["path"]
    for name, digest in manifest["outputs"].items():
        assert sha(output / name) == digest, name
    guards = json.loads(protected.read_text())
    for path, digest in guards.items():
        assert sha(path) == digest, path
    paths = {name: item["path"] for name, item in manifest["inputs"].items()}
    raw = json.loads(Path(paths["export"]).read_text())
    queue = rows(paths["queue"])
    ids = {r["word_id"] for r in queue}
    assert len(queue) == len(ids) == len(raw["answers"]) == 50
    assert ids == set(raw["answers"])
    assert not ids.intersection(r["word_id"] for r in rows(paths["pilot150"]))
    sources = {m: {r["word_id"]: r for r in rows(paths[m])} for m in ("baseline", "gpt", "qwen")}
    paired = ids & set(sources["qwen"])
    assert len(paired) == 12
    report = json.loads((output / "report.json").read_text())
    recomputed = {}
    for scope, selected in (("review50", ids), ("qwen_paired12", paired)):
        recomputed[scope] = {}
        for method, source in sources.items():
            field = "baseline_level" if method == "baseline" else "rarity_level"
            errors = [abs(int(source[wid][field]) - raw["answers"][wid]["level"]) for wid in selected & set(source)]
            actual = dict(n=len(errors), severe=sum(e >= 2 for e in errors), excess_error_total=sum(max(e - 1, 0) for e in errors), within_one=sum(e <= 1 for e in errors), exact=errors.count(0), mae=sum(errors)/len(errors))
            for key, value in actual.items():
                assert report["metrics"][scope][method][key] == value, (scope, method, key)
            recomputed[scope][method] = actual
    return dict(status="PASS", independent_stdlib=True, protected_files=len(guards), input_hashes_verified=len(paths), frozen_review_ids=50, prior_pilot_separate=150, paired_qwen=12, recomputed=recomputed)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--protected", type=Path, required=True)
    p.add_argument("--receipt", type=Path, required=True)
    a = p.parse_args()
    result = verify(a.output, a.protected)
    if a.receipt.exists():
        raise FileExistsError(a.receipt)
    a.receipt.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({k: v for k, v in result.items() if k != "recomputed"}))
