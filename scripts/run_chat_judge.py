"""Run an already available Chat Completions judge; no model loading or DB access."""

import argparse
import json
import os
from pathlib import Path

import requests

from classificator.evaluation.chat_judge import collect_chat_csv


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("vocabulary", "evidence", "output-dir"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--endpoint", required=True)
    parser.add_argument("--options-json", type=Path)
    parser.add_argument("--runtime-json", type=Path)
    parser.add_argument("--api-key-env", help="Name of credential env var; value never persisted")
    args = parser.parse_args()
    http = requests.Session()
    if args.api_key_env:
        http.headers["Authorization"] = "Bearer " + os.environ[args.api_key_env]
    result = collect_chat_csv(
        args.vocabulary,
        args.evidence,
        args.output_dir,
        model=args.model,
        endpoint=args.endpoint,
        http=http,
        options=json.loads(args.options_json.read_text()) if args.options_json else {},
        runtime=json.loads(args.runtime_json.read_text()) if args.runtime_json else {},
    )
    print(result)


if __name__ == "__main__":
    main()
