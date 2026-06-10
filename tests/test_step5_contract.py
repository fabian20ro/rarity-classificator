import pytest
from unittest.mock import MagicMock
import csv
from classificator.steps.step5_rebalance import run_step5, Step5Options
from classificator.run_csv_repository import RunCsvRepository
from classificator.lm.client import LmStudioClient, ScoringContext
from classificator.models import ResolvedEndpoint, LmApiFlavor, ScoringOutputMode
from classificator.transitions import LevelTransition

def test_step5_contract_no_zero_level(tmp_path):
    # Setup input CSV with a 0 level
    input_csv = tmp_path / "input.csv"
    with open(input_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["word_id", "word", "type", "final_level"])
        writer.writerow(["1", "apple", "noun", "1"])
        writer.writerow(["2", "banana", "noun", "0"])  # Invalid level
        writer.writerow(["3", "cherry", "noun", "3"])

    repo = RunCsvRepository()
    lm_client = MagicMock(spec=LmStudioClient)
    lm_client.resolve_endpoint.return_value = ResolvedEndpoint(
        endpoint="http://localhost:1234/v1",
        models_endpoint=None,
        flavor=LmApiFlavor.LMSTUDIO_REST,
        source="mock"
    )
    
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    
    options = Step5Options(
        run_slug="test-run",
        model="gpt-4",
        input_csv_path=input_csv,
        output_csv_path=tmp_path / "output.csv",
        skip_preflight=True,
        transitions=[LevelTransition(from_level=3, to_level=2)]
    )
    
    # The current implementation should raise CsvFormatError in _load_dataset
    with pytest.raises(Exception) as excinfo:
        run_step5(options, repo=repo, lm_client=lm_client, output_dir=output_dir)
    
    assert "out of range" in str(excinfo.value)
