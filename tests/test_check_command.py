"""Verification orchestration must preserve failure and complete discovery."""
from pathlib import Path
from subprocess import CompletedProcess
import sys
import unittest
from unittest.mock import patch

import pytest

from scripts.check import main


def test_all_upload_integration_regressions_remain_collectable():
    from tests.test_step4_upload import TestStep4Upload

    expected = {
        "test_partial_upload", "test_partial_upload_prints_unchanged_count",
        "test_full_fallback_print_unchanged_not_printed", "test_full_upload",
        "test_partial_missing_db_word", "test_missing_batch_id_falls_back_to_timestamped_id",
        "test_partial_audit_gate_blocks_upload", "test_partial_audit_pass_allows_upload",
        "test_partial_audit_receives_configured_thresholds",
    }
    assert expected <= set(unittest.defaultTestLoader.getTestCaseNames(TestStep4Upload))


@pytest.mark.parametrize("codes,expected,expected_calls", [
    ([0, 0], 0, 2), ([1], 1, 1), ([0, 5], 5, 2),
])
def test_check_propagates_failure_without_skipping_complete_collection(codes, expected, expected_calls):
    with patch("scripts.check.subprocess.run", side_effect=[
        CompletedProcess([], code) for code in codes
    ]) as run, patch("builtins.print") as mock_print:
        assert main() == expected
    assert run.call_count == expected_calls
    assert run.call_args_list[0].args[0] == [
        sys.executable, "-m", "ruff", "check", "src", "tests", "scripts/check.py",
    ]
    if expected_calls == 2:
        assert run.call_args_list[1].args[0] == [sys.executable, "-m", "pytest", "-q"]
    assert all(call.kwargs["cwd"] == Path(__file__).resolve().parents[1]
               for call in run.call_args_list)
    banners = [str(call.args[0]) for call in mock_print.call_args_list]
    assert banners == [
        "+ " + " ".join(call.args[0]) for call in run.call_args_list
    ]
    assert all(call.kwargs.get("flush") is True
               for call in mock_print.call_args_list)
    assert all(not call.kwargs.get("check") for call in run.call_args_list)
