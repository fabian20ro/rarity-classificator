"""Approved artifacts and a read-only capture produce an offline installation bundle."""

import json
from unittest.mock import patch

from tests.test_automatic_promotion_flow import fixture


def inputs(root):
    approval, package, _ = fixture(root)
    capture = root / "capture.json"
    capture.write_text(
        json.dumps(
            {
                "version": "automatic-installation-capture-v1",
                "read_only": "on",
                "captured_at": "2026-11-07T00:00:00Z",
                "state": {
                    "server_version": "17.9",
                    "engine_version": "1.8",
                    "words_owner": "postgres",
                    "schema_owner": "postgres",
                    "inventory": {"rows": 5, "digest": "placeholder"},
                    "epoch": ["12b74579-3641-4a88-b07b-c024cd9fa281"],
                    "revision_valid": True,
                    "human_receipts": [],
                    "human_installation_receipt": [],
                    "words_security": {"rls": True, "force_rls": False, "acl": []},
                    "policies": [],
                    "triggers": [],
                    "events": [],
                    "schema_acl": [],
                    "private_objects": [],
                    "human_role": [],
                    "human_memberships": [],
                },
            }
        )
    )
    # Independent fixture encoding, checked again against the real server in integration.
    from tests.test_promotion_audit import rows
    import hashlib

    rs = rows(root / "snapshot.csv")
    values = "".join(
        str(len(r[k].encode())) + ":" + r[k]
        for r in sorted(rs, key=lambda r: int(r["word_id"]))
        for k in ("word_id", "word", "type", "rarity_level", "version")
    )
    data = json.loads(capture.read_text())
    data["state"]["inventory"] = {
        "rows": len(rs),
        "digest": hashlib.sha256(values.encode()).hexdigest(),
    }
    capture.write_text(json.dumps(data))
    return approval, package, capture


def test_preparation_is_offline_atomic_and_defaults_to_disabled_executor(tmp_path):
    from classificator.automatic_installation import (
        prepare_automatic_installation,
        verify_automatic_installation,
    )

    args = inputs(tmp_path)
    with patch("psycopg.connect", side_effect=AssertionError("Offline preparation connected")):
        report = prepare_automatic_installation(*args, tmp_path / "bundle")
    assert report["installation_authorized"] is False
    assert report["scores_applied"] is False
    assert report["executor_login"] is False
    assert report["inventory_rows"] == 5
    assert verify_automatic_installation(tmp_path / "bundle")["valid"]
    assert (tmp_path / "bundle/01-preflight.sql").read_text().startswith("BEGIN READ ONLY;")
    assert (tmp_path / "bundle/03-postflight.sql").read_text().startswith("BEGIN READ ONLY;")


def test_capture_drift_or_missing_revision_contract_cannot_prepare_bundle(tmp_path):
    import pytest
    from classificator.automatic_installation import prepare_automatic_installation

    args = inputs(tmp_path)
    original = json.loads(args[2].read_text())
    for index, (key, value) in enumerate(
        [
            ("inventory", {"rows": 5, "digest": "0" * 64}),
            ("revision_valid", False),
            ("epoch", []),
            ("words_owner", "unexpected"),
            ("engine_version", "9.9"),
            ("server_version", "18.0"),
        ]
    ):
        data = json.loads(json.dumps(original))
        data["state"][key] = value
        args[2].write_text(json.dumps(data))
        out = tmp_path / f"refused-{index}"
        with pytest.raises(ValueError):
            prepare_automatic_installation(*args, out)
        assert not out.exists()
    original["read_only"] = "off"
    args[2].write_text(json.dumps(original))
    with pytest.raises(ValueError):
        prepare_automatic_installation(*args, tmp_path / "write-capture")


def test_bundle_documents_uncertain_commit_and_verifier_rejects_tampering(tmp_path):
    import pytest
    from classificator.automatic_installation import (
        prepare_automatic_installation,
        verify_automatic_installation,
    )

    args = inputs(tmp_path)
    out = tmp_path / "bundle"
    prepare_automatic_installation(*args, out)
    guide = (out / "README.md").read_text()
    assert "NOLOGIN" in guide and "acknowledgement" in guide
    assert "03-postflight.sql" in guide and "ON_ERROR_STOP" in guide
    (out / "02-install.sql").write_text("SELECT 1;")
    with pytest.raises(ValueError, match="artifact changed"):
        verify_automatic_installation(out)


def test_extra_artifacts_and_changed_sources_are_not_verified(tmp_path):
    import pytest
    from classificator.automatic_installation import (
        prepare_automatic_installation,
        verify_automatic_installation,
    )

    args = inputs(tmp_path)
    out = tmp_path / "bundle"
    prepare_automatic_installation(*args, out)
    (out / "extra.sql").write_text("SELECT 1;")
    with pytest.raises(ValueError, match="inventory"):
        verify_automatic_installation(out)
    (out / "extra.sql").unlink()
    args[2].write_text(args[2].read_text() + "\n")
    with pytest.raises(ValueError, match="input changed"):
        verify_automatic_installation(out)


def test_replay_is_identical_and_cli_never_consumes_a_production_dsn(tmp_path):
    from contextlib import redirect_stdout
    from io import StringIO
    from classificator.automatic_installation import prepare_automatic_installation, main

    args = inputs(tmp_path)
    first = tmp_path / "first"
    prepare_automatic_installation(*args, first)
    with (
        patch.dict("os.environ", {"AUTOMATIC_PROMOTION_DSN": "must-not-connect"}),
        patch("psycopg.connect", side_effect=AssertionError("Unexpected DB connection")),
        redirect_stdout(StringIO()),
    ):
        assert (
            main(
                [
                    "--acceptance",
                    str(args[0]),
                    "--package",
                    str(args[1]),
                    "--capture",
                    str(args[2]),
                    "--output",
                    str(tmp_path / "second"),
                ]
            )
            == 0
        )
    for name in (
        "01-preflight.sql",
        "02-install.sql",
        "03-postflight.sql",
        "report.json",
        "README.md",
        "manifest.json",
    ):
        assert (first / name).read_bytes() == (tmp_path / "second" / name).read_bytes()
