"""Accepted CSV package → isolated transaction flow, no real connections."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from classificator.automatic_promotion_flow import run_automatic_promotion
from classificator.evaluation.promotion_audit import prepare_promotion_audit
from tests import test_promotion_audit as audit_fixtures
from tests.test_promotion_audit import digest, rows
from tests.test_human_correction_flow import MemoryStore


def fixture(root):
    contract = audit_fixtures.PromotionAuditTests().fixture(root)
    package = root / "package"
    prepare_promotion_audit(contract, package)
    approval = root / "acceptance.json"
    approval.write_text(
        json.dumps(
            dict(
                version="automatic-provisional-acceptance-v1",
                approved_on="2026-11-06",
                package_id=digest(package / "manifest.json"),
                candidate_sha256=digest(package / "candidate.csv"),
                routes=["wordfreq", "fallback"],
                legacy_gate_role="diagnostic",
                population_accuracy="unknown",
                human_priority=True,
            )
        )
    )
    store = MemoryStore(rows(root / "snapshot.csv"))
    for row in rows(root / "snapshot.csv"):
        store.rows[row["word_id"]]["version"] = row["version"]
        store.rows[row["word_id"]]["other_columns_sha256"] = "0" * 64
    store.version_contract = {"kind": "sequence-v1", "epoch": "test-epoch"}
    return approval, package, store


def execute(approval, package, store, out, action):
    return run_automatic_promotion(
        approval,
        package,
        out,
        action=action,
        store=store,
        confirm_package=digest(package / "manifest.json"),
        expected_epoch="test-epoch",
    )


class AutomaticFlowTests(unittest.TestCase):
    def test_acceptance_change_during_read_cannot_be_rebound_to_new_bytes(self):
        from unittest.mock import patch

        with TemporaryDirectory() as temp:
            root = Path(temp)
            approval, package, store = fixture(root)
            read_text = Path.read_text

            def concurrent_edit(path, *args, **kwargs):
                text = read_text(path, *args, **kwargs)
                if path == approval:
                    path.write_text(text + "\n")
                return text

            with patch.object(Path, "read_text", concurrent_edit):
                with self.assertRaises(ValueError):
                    execute(approval, package, store, root / "fail", "apply")
            self.assertEqual(store.transactions, 0)

    def test_cli_default_does_not_read_dsn_or_start_database(self):
        from contextlib import redirect_stdout
        from io import StringIO
        from unittest.mock import patch
        from classificator.automatic_promotion_flow import main

        with TemporaryDirectory() as temp:
            root = Path(temp)
            approval, package, _ = fixture(root)
            with (
                patch.dict("os.environ", {"AUTOMATIC_PROMOTION_DSN": "do-not-use"}),
                patch(
                    "psycopg.connect",
                    side_effect=AssertionError("Offline default connected"),
                ),
                redirect_stdout(StringIO()),
            ):
                self.assertEqual(
                    main(
                        [
                            "--acceptance",
                            str(approval),
                            "--package",
                            str(package),
                            "--output",
                            str(root / "cli"),
                        ]
                    ),
                    0,
                )

    def test_default_preview_replays_accepted_package_without_store_access(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            approval, package, store = fixture(root)
            result = run_automatic_promotion(
                approval, package, root / "preview", store=store
            )
            self.assertEqual(result["status"], "dry_run")
            self.assertTrue(result["policy_accepted"])
            self.assertFalse(result["applied"])
            self.assertFalse(result["quality"]["passed"])
            self.assertEqual(result["route_changes"], {"wordfreq": 1, "fallback": 1})
            self.assertEqual(store.transactions, 0)

    def test_both_routes_commit_once_then_rollback_from_receipt_versions(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            approval, package, store = fixture(root)
            before = store.snapshot()
            applied = execute(approval, package, store, root / "apply", "apply")
            self.assertEqual(applied["status"], "applied")
            self.assertEqual(store.rows["103"]["rarity_level"], "1")
            self.assertEqual(store.rows["104"]["rarity_level"], "4")
            self.assertEqual(store.rows["101"], before[0])
            after = store.snapshot()
            self.assertEqual(
                execute(approval, package, store, root / "retry", "apply")["status"],
                "already_applied",
            )
            self.assertEqual(store.snapshot(), after)
            self.assertEqual(
                execute(approval, package, store, root / "rollback", "rollback")[
                    "status"
                ],
                "rolled_back",
            )
            self.assertEqual(
                [r["rarity_level"] for r in store.snapshot()], ["5", "5", "4", "1", "4"]
            )
            self.assertEqual(
                execute(approval, package, store, root / "retry-rollback", "rollback")[
                    "status"
                ],
                "already_rolled_back",
            )
            with self.assertRaises(ValueError):
                execute(approval, package, store, root / "reapply", "apply")

    def test_omitting_a_delta_from_resealed_manifest_cannot_escape_source_replay(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            approval, package, store = fixture(root)
            manifest = json.loads((package / "manifest.json").read_text())
            del manifest["artifacts"]["fallback-changes.csv"]
            (package / "manifest.json").write_text(json.dumps(manifest))
            accepted = json.loads(approval.read_text())
            accepted["package_id"] = digest(package / "manifest.json")
            approval.write_text(json.dumps(accepted))
            with self.assertRaises(ValueError):
                execute(approval, package, store, root / "fail", "apply")
            self.assertEqual(store.transactions, 0)

    def test_execution_refuses_wrong_scope_confirmation_and_revision_installation(self):
        for defect in ("routes", "candidate", "human", "confirmation", "epoch"):
            with self.subTest(defect=defect), TemporaryDirectory() as temp:
                root = Path(temp)
                approval, package, store = fixture(root)
                data = json.loads(approval.read_text())
                if defect == "routes":
                    data["routes"] = ["fallback"]
                if defect == "candidate":
                    data["candidate_sha256"] = "0" * 64
                if defect == "human":
                    data["human_priority"] = False
                approval.write_text(json.dumps(data))
                before = store.snapshot()
                with self.assertRaises(ValueError):
                    run_automatic_promotion(
                        approval,
                        package,
                        root / "failed",
                        action="apply",
                        store=store,
                        confirm_package=(
                            "wrong"
                            if defect == "confirmation"
                            else digest(package / "manifest.json")
                        ),
                        expected_epoch="wrong" if defect == "epoch" else "test-epoch",
                    )
                self.assertEqual(store.snapshot(), before)
                self.assertEqual(store.receipts, {})

    def test_transaction_failures_leave_no_partial_route_or_durable_receipt(self):
        for fault in ("partial", "side_effect", "receipt", "commit"):
            with self.subTest(fault=fault), TemporaryDirectory() as temp:
                root = Path(temp)
                approval, package, store = fixture(root)
                before = store.snapshot()
                store.fail = fault
                with self.assertRaises((ValueError, RuntimeError)):
                    execute(approval, package, store, root / "failed", "apply")
                self.assertEqual(store.snapshot(), before)
                self.assertEqual(store.receipts, {})
                self.assertFalse((root / "failed/receipt.json").exists())
                store.fail = None
                self.assertEqual(
                    execute(approval, package, store, root / "retry", "apply")[
                        "status"
                    ],
                    "applied",
                )

    def test_lost_ack_recovers_each_action_without_rewriting_rows(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            approval, package, store = fixture(root)
            for action, recovered in (
                ("apply", "already_applied"),
                ("rollback", "already_rolled_back"),
            ):
                store.fail = "lost_commit_ack"
                with self.assertRaises(RuntimeError):
                    execute(approval, package, store, root / action, action)
                after = store.snapshot()
                self.assertFalse((root / action / "receipt.json").exists())
                store.fail = None
                result = execute(
                    approval, package, store, root / f"retry-{action}", action
                )
                self.assertEqual(result["status"], recovered)
                self.assertFalse(result["current_state_verified"])
                self.assertEqual(store.snapshot(), after)

    def test_stale_apply_and_same_score_later_write_block_execution(self):
        for action in ("apply", "rollback"):
            with self.subTest(action=action), TemporaryDirectory() as temp:
                root = Path(temp)
                approval, package, store = fixture(root)
                if action == "rollback":
                    execute(approval, package, store, root / "apply", "apply")
                store.rows["103"]["version"] = "999"
                current = store.snapshot()
                with self.assertRaises(ValueError):
                    execute(approval, package, store, root / "stale", action)
                self.assertEqual(store.snapshot(), current)

    def test_rollback_preserves_unrelated_later_edit_and_human_scores(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            approval, package, store = fixture(root)
            execute(approval, package, store, root / "apply", "apply")
            store.rows["105"].update(rarity_level="2", version="888")
            unrelated = dict(store.rows["105"])
            execute(approval, package, store, root / "rollback", "rollback")
            self.assertEqual(store.rows["105"], unrelated)
            self.assertEqual(store.rows["101"]["rarity_level"], "5")

    def test_post_receipt_non_score_side_effect_rolls_back(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            approval, package, store = fixture(root)
            original = store.save_receipt

            def faulty_receipt(*args, **kwargs):
                original(*args, **kwargs)
                store.rows["105"]["other_columns_sha256"] = "f" * 64

            store.save_receipt = faulty_receipt
            before = store.snapshot()
            with self.assertRaises(ValueError):
                execute(approval, package, store, root / "fail", "apply")
            self.assertEqual(store.snapshot(), before)
            self.assertEqual(store.receipts, {})


if __name__ == "__main__":
    unittest.main()
