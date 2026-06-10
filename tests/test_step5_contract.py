import pytest
from unittest.mock import MagicMock
import csv
from pathlib import Path
from classificator.steps.step5_rebalance import run_step5, Step5Options
from classificator.run_csv_repository import RunCsvRepository
from classificator.lm.client import LmStudioClient, ScoringContext
from classificator.models import ResolvedEndpoint, LmApiFlavor, ScoringOutputMode
from classificator.transitions import LevelTransition

def test_step5_contract_no_zero_level(tmp_path):
    # Setup input CSV with valid levels
    input_csv = tmp_path / "input.csv"
    output_csv = tmp_path / "output.csv"
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    
    with open(input_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["word_id", "word", "type", "final_level"])
        writer.writerow(["1", "apple", "noun", "1"])
        writer.writerow(["2", "banana", "noun", "2"])
        writer.writerow(["3", "cherry", "noun", "3"])
        writer.writerow(["4", "date", "noun", "4"])
        writer.writerow(["5", "elderberry", "noun", "5"])

    repo = RunCsvRepository()
    lm_client = MagicMock(spec=LmStudioClient)
    lm_client.resolve_endpoint.return_value = ResolvedEndpoint(
        endpoint="http://localhost:1234/v1",
        models_endpoint=None,
        flavor=LmApiFlavor.LMSTUDIO_REST,
        source="mock"
    )
    
    options = Step5Options(
        run_slug="test-run",
        model="gpt-4",
        input_csv_path=input_csv,
        output_csv_path=output_csv,
        skip_preflight=True,
        transitions=[LevelTransition(from_level=3, to_level=2)]
    )
    
    # Run step 5
    run_step5(options, repo=repo, lm_client=lm_client, output_dir=output_dir)
    
    # Check output for any 0 in the level column
    with open(output_csv, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            level = int(row["final_level"])
            assert level != 0, f"Found 0 in output: {row}"
