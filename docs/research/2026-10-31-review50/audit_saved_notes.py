"""Project saved model notes and evidence provenance; never call a model."""
import argparse
import csv
import hashlib
import json
from pathlib import Path


def run(campaign, comparison, output):
    if output.exists():
        raise FileExistsError(output)
    records = []
    for row in csv.DictReader(comparison.open()):
        for method in ("gpt", "qwen"):
            if not row[method + "_level"]:
                continue
            path = campaign / method / "campaign/records" / (row["word_id"] + ".json")
            saved = json.loads(path.read_text())
            response = json.loads(saved["response"])
            if method == "gpt":
                messages = [e["item"]["text"] for line in response["stdout"].splitlines() if (e := json.loads(line)).get("type") == "item.completed" and e.get("item", {}).get("type") == "agent_message"]
                if len(messages) != 1:
                    raise ValueError("Ambiguous saved response")
                result = json.loads(messages[0])
                evidence = saved["request"]["input"]["evidence"]
            else:
                result = json.loads(response["choices"][0]["message"]["content"])
                evidence = json.loads(saved["request"]["messages"][1]["content"])["evidence"]
            if result["level"] != int(row[method + "_level"]) or result["word"] != row["word"] or str(result["word_id"]) != row["word_id"]:
                raise ValueError("Saved record/CSV mismatch")
            records.append(dict(word_id=row["word_id"], word=row["word"], method=method, level=result["level"], human_level=row["human_level"], severe=row[method + "_severe"], note=result["note"], valid_pos=json.dumps(evidence["valid_pos"], ensure_ascii=False), source_senses=len(evidence["senses"]), record_path=str(path), record_sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
    with output.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(records[0]))
        writer.writeheader()
        writer.writerows(records)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    for flag in ("campaign", "comparison", "output"):
        parser.add_argument("--" + flag, type=Path, required=True)
    args = parser.parse_args()
    run(args.campaign, args.comparison, args.output)
