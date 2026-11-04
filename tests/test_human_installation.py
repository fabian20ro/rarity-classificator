import hashlib
import json
from pathlib import Path
from unittest.mock import patch

from tests import test_human_correction_flow as fixtures
from tests.test_local_evidence import read


def inputs(tmp_path):
    approval, policy, _, _ = fixtures.HumanFlowTests().inputs(tmp_path)
    rows = read(Path(json.loads(policy.read_text())["sources"]["snapshot"]["path"]))
    capture = tmp_path / "capture"
    capture.mkdir()
    canonical = "".join(
        "\t".join(r[k] for k in ("word_id", "word", "type", "rarity_level")) + "\n"
        for r in sorted(rows, key=lambda r: int(r["word_id"]))
    )
    values = {
        "project.json": {"id": "test-project"},
        "metadata.json": {
            "read_only": "on",
            "server_version": "17.9",
            "current_user": "postgres",
            "table": {"owner": "postgres", "rls": True, "force_rls": False},
            "policies": [],
            "triggers": [],
            "rules": [],
            "ledger_schema": None,
            "ledger_table": None,
        },
        "storage.json": {
            "read_only": "on",
            "access_method": "orioledb",
            "extensions": [{"name": "orioledb", "version": "1.8"}],
        },
        "supplement.json": {"read_only": "on", "event_triggers": []},
        "snapshot.json": {
            "read_only": "on",
            "count": len(rows),
            "fingerprint_sha256": hashlib.sha256(canonical.encode()).hexdigest(),
            "unsafe_delimiters": 0,
            "captured_at": "2026-11-03T04:27:49Z",
        },
    }
    for name, data in values.items():
        (capture / name).write_text(json.dumps(data))
    (capture / "manifest.json").write_text(
        json.dumps(
            {
                "artifacts": {
                    name: hashlib.sha256((capture / name).read_bytes()).hexdigest()
                    for name in values
                }
            }
        )
    )
    return approval, policy, capture / "manifest.json"


def test_offline_bundle_contains_one_atomic_install_and_no_score_application(tmp_path):
    from classificator.human_installation import (
        prepare_human_installation,
        verify_installation_bundle,
    )

    args = inputs(tmp_path)
    out = tmp_path / "bundle"
    with patch("psycopg.connect", side_effect=AssertionError("No DB calls permitted")):
        result = prepare_human_installation(*args, out)
    assert result["installation_authorized"] is False
    assert result["execution_ready"] is False
    assert result["scope"]["correction_rows"] == 1
    sql = (out / "02-install.sql").read_text()
    assert sql.splitlines().count("BEGIN;") == 1
    assert sql.splitlines().count("COMMIT;") == 1
    assert "SET rarity_level" not in sql
    assert "NOLOGIN" in sql and "PASSWORD" not in sql
    assert "ACCESS EXCLUSIVE" in sql
    assert (out / "01-preflight.sql").read_text().startswith("BEGIN READ ONLY;")
    assert (out / "03-postflight.sql").read_text().startswith("BEGIN READ ONLY;")
    assert (out / "preconditions.csv").exists() and (out / "rollback.csv").exists()
    assert verify_installation_bundle(out)["valid"] is True


def test_unlisted_executable_artifact_is_not_a_verified_bundle(tmp_path):
    import pytest
    from classificator.human_installation import (
        prepare_human_installation,
        verify_installation_bundle,
    )

    out = tmp_path / "bundle"
    prepare_human_installation(*inputs(tmp_path), out)
    (out / "00-unexpected.sql").write_text("SELECT 1;")
    with pytest.raises(ValueError, match="inventory"):
        verify_installation_bundle(out)


def test_bundle_exposes_environment_and_privilege_checks_for_review(tmp_path):
    from classificator.human_installation import prepare_human_installation

    result = prepare_human_installation(*inputs(tmp_path), tmp_path / "bundle")
    assert {
        "rls_unchanged",
        "policies_unchanged",
        "word_grants_preserved",
        "ddl_hooks_unchanged",
        "creator_capability",
    } <= set(result["preflight_checks"])
    assert {
        "api_roles_denied",
        "executor_grants",
        "existing_data_preserved",
        "installation_receipt_bound",
        "ledger_grants",
    } <= set(result["postflight_checks"])


def test_install_checks_existing_data_after_the_last_receipt_write(tmp_path):
    from classificator.human_installation import prepare_human_installation

    out = tmp_path / "bundle"
    prepare_human_installation(*inputs(tmp_path), out)
    sql = (out / "02-install.sql").read_text()
    assert sql.index("Installation check failed: existing_data_preserved") > sql.index(
        "INSERT INTO classificator_private.installation_receipt"
    )


def test_changed_capture_or_resealed_inventory_cannot_prepare_installation(tmp_path):
    import pytest
    from classificator.human_installation import prepare_human_installation

    args = inputs(tmp_path)
    snapshot = args[2].parent / "snapshot.json"
    data = json.loads(snapshot.read_text())
    data["count"] += 1
    snapshot.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="hash mismatch"):
        prepare_human_installation(*args, tmp_path / "bundle")
    manifest = json.loads(args[2].read_text())
    manifest["artifacts"]["snapshot.json"] = hashlib.sha256(snapshot.read_bytes()).hexdigest()
    args[2].write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="approved snapshot"):
        prepare_human_installation(*args, tmp_path / "bundle")
    assert not (tmp_path / "bundle").exists()


def test_tampered_sql_is_rejected_and_replay_preserves_every_plan_artifact(tmp_path):
    import pytest
    from classificator.human_installation import (
        prepare_human_installation,
        verify_installation_bundle,
    )

    args = inputs(tmp_path)
    first = tmp_path / "one"
    second = tmp_path / "two"
    prepare_human_installation(*args, first)
    prepare_human_installation(*args, second)
    for name in (
        "01-preflight.sql",
        "02-install.sql",
        "03-postflight.sql",
        "report.json",
        "corrections.csv",
        "rollback.csv",
        "preconditions.csv",
        "references.csv",
    ):
        assert (first / name).read_bytes() == (second / name).read_bytes()
    (first / "02-install.sql").write_text("SELECT 1;")
    with pytest.raises(ValueError, match="artifact changed"):
        verify_installation_bundle(first)
    with pytest.raises(FileExistsError):
        prepare_human_installation(*args, second)
