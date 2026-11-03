"""Approved CSV package → separate transactional human correction flow."""

import copy
import json
from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from tests import test_human_acceptance as fixtures
from tests.test_local_evidence import read
from tests.test_conservative_export import sha


class MemoryStore:
    """External transaction boundary; no SQL or live connections."""

    def __init__(self, rows):
        self.rows = {r["word_id"]: dict(r, version="10") for r in rows}
        self.receipts = {}
        self.txid = 20
        self.fail = None
        self.transactions = 0

    @contextmanager
    def transaction(self):
        self.transactions += 1
        self.txid += 1
        saved = copy.deepcopy((self.rows, self.receipts))
        try:
            yield self
            if self.fail == "commit":
                raise RuntimeError("Commit failed")
        except BaseException:
            self.rows, self.receipts = saved
            raise
        if self.fail == "lost_commit_ack":
            raise RuntimeError("Commit response lost")

    def snapshot(self):
        return copy.deepcopy(list(self.rows.values()))

    def receipt(self, package_id):
        return copy.deepcopy(self.receipts.get(package_id))

    def update(self, changes):
        for c in changes:
            row = self.rows[c["live_word_id"]]
            if (row["word"], row["type"], row["rarity_level"], row["version"]) != (
                c["word"],
                c["type"],
                c["expected_level"],
                c["expected_version"],
            ):
                raise ValueError("Concurrent row change")
            row["rarity_level"] = c["target_level"]
            row["version"] = str(self.txid)
            if self.fail == "partial":
                raise RuntimeError("Interrupted batch")
        if self.fail == "side_effect":
            self.rows["104"]["rarity_level"] = "2"
        return [c["live_word_id"] for c in changes]

    def save_receipt(self, package_id, receipt, *, replace=False):
        if self.fail == "receipt":
            raise RuntimeError("Receipt unavailable")
        if (package_id in self.receipts) != replace:
            raise ValueError("Receipt state conflict")
        self.receipts[package_id] = copy.deepcopy(receipt)


class HumanFlowTests(unittest.TestCase):
    def test_revision_receipts_cannot_be_reinterpreted_after_contract_change(self):
        from classificator.human_correction_flow import run_human_corrections

        for action in ("apply", "rollback"):
            for changed in ({"kind": "xmin-v1"}, {"kind": "sequence-v1", "epoch": "other"}):
                with self.subTest(action=action, contract=changed), TemporaryDirectory() as tmp:
                    root = Path(tmp)
                    approval, policy, package, store = self.inputs(root)
                    store.version_contract = {"kind": "sequence-v1", "epoch": "original"}
                    run_human_corrections(
                        approval,
                        policy,
                        root / "apply",
                        action="apply",
                        store=store,
                        confirm_package=package,
                    )
                    after = store.snapshot()
                    store.version_contract = changed
                    with self.assertRaisesRegex(ValueError, "version contract"):
                        run_human_corrections(
                            approval,
                            policy,
                            root / "retry",
                            action=action,
                            store=store,
                            confirm_package=package,
                        )
                    self.assertEqual(store.snapshot(), after)
                    self.assertEqual(store.receipts[package]["state"], "applied")

    def test_explicit_revision_rollback_does_not_depend_on_32_bit_xmin_age(self):
        from classificator.human_correction_flow import run_human_corrections

        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            approval, policy, package, store = self.inputs(root)
            store.version_contract = {"kind": "sequence-v1", "epoch": "original"}
            run_human_corrections(
                approval,
                policy,
                root / "apply",
                action="apply",
                store=store,
                confirm_package=package,
            )
            store.txid += 2**32
            result = run_human_corrections(
                approval,
                policy,
                root / "rollback",
                action="rollback",
                store=store,
                confirm_package=package,
            )
            self.assertEqual(result["status"], "rolled_back")

    def inputs(self, root):
        policy = fixtures.HumanAcceptanceTests().inputs(root)
        config = json.loads(policy.read_text())
        package = Path(config["sources"]["package_manifest"]["path"]).parent
        package_id = json.loads((package / "policy.json").read_text())["package_id"]
        approval = root / "approval.json"
        approval.write_text(
            json.dumps(
                dict(
                    version="human-corrections-flow-v1",
                    approved_on="2026-11-03",
                    policy_sha256=sha(policy),
                    package_id=package_id,
                )
            )
        )
        store = MemoryStore(read(Path(config["sources"]["snapshot"]["path"])))
        return approval, policy, package_id, store

    def test_default_is_offline_preview_with_anchor_failures_reported_not_vetoed(self):
        from classificator.human_correction_flow import run_human_corrections

        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            approval, policy, package_id, store = self.inputs(root)
            result = run_human_corrections(approval, policy, root / "preview", store=store)
            self.assertEqual(result["status"], "dry_run")
            self.assertTrue(result["human_policy_satisfied"])
            self.assertFalse(result["legacy_gate"]["passed"])
            self.assertFalse(result["applied"])
            self.assertEqual(store.transactions, 0)
            self.assertEqual(store.receipts, {})
            self.assertEqual(read(root / "preview/changes.csv")[0]["live_word_id"], "100")

    def test_execution_requires_exact_approval_and_separate_explicit_package_confirmation(self):
        from classificator.human_correction_flow import run_human_corrections

        for defect in (
            "version",
            "policy_hash",
            "package",
            "extra_field",
            "missing_confirmation",
            "wrong_confirmation",
            "action",
        ):
            with self.subTest(defect=defect), TemporaryDirectory() as tmp:
                root = Path(tmp)
                approval, policy, package_id, store = self.inputs(root)
                config = json.loads(approval.read_text())
                confirmation = package_id
                action = "apply"
                if defect == "version":
                    config["version"] = "unknown"
                elif defect == "policy_hash":
                    config["policy_sha256"] = "0" * 64
                elif defect == "package":
                    config["package_id"] = "0" * 64
                elif defect == "extra_field":
                    config["min_jaccard"] = 0
                elif defect == "missing_confirmation":
                    confirmation = None
                elif defect == "wrong_confirmation":
                    confirmation = "another-package"
                else:
                    action = "full-fallback"
                approval.write_text(json.dumps(config))
                with self.assertRaises(ValueError):
                    run_human_corrections(
                        approval,
                        policy,
                        root / "out",
                        action=action,
                        store=store,
                        confirm_package=confirmation,
                    )
                self.assertEqual(store.transactions, 0)

    def test_apply_changes_only_human_ids_and_commits_receipt_then_retry_is_read_only(self):
        from classificator.human_correction_flow import run_human_corrections

        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            approval, policy, package_id, store = self.inputs(root)
            before = copy.deepcopy(store.rows)
            result = run_human_corrections(
                approval,
                policy,
                root / "apply",
                action="apply",
                store=store,
                confirm_package=package_id,
            )
            self.assertEqual(result["status"], "applied")
            self.assertEqual(store.rows["100"]["rarity_level"], "5")
            self.assertEqual({i for i in before if before[i] != store.rows[i]}, {"100"})
            receipt = store.receipts[package_id]
            self.assertEqual(receipt["changed_ids"], ["100"])
            self.assertEqual(receipt["state"], "applied")
            self.assertEqual(receipt["policy_sha256"], sha(policy))
            self.assertEqual(read(root / "apply/live-before.csv")[0]["rarity_level"], "4")
            self.assertEqual(read(root / "apply/live-after.csv")[0]["rarity_level"], "5")
            committed = copy.deepcopy(store.rows)
            recovered = run_human_corrections(
                approval,
                policy,
                root / "retry",
                action="apply",
                store=store,
                confirm_package=package_id,
            )
            self.assertEqual(recovered["status"], "already_applied")
            self.assertEqual(committed, store.rows)
            self.assertEqual(receipt, json.loads((root / "retry/receipt.json").read_text()))

    def test_locked_snapshot_guards_all_reviewed_members_and_keeps_original_l1_reference(self):
        from classificator.human_correction_flow import run_human_corrections

        for defect in (
            "unchanged_human",
            "new_pos",
            "missing_row",
            "identity",
            "l1_drift",
            "unrelated_change",
        ):
            with self.subTest(defect=defect), TemporaryDirectory() as tmp:
                root = Path(tmp)
                approval, policy, package_id, store = self.inputs(root)
                if defect == "unchanged_human":
                    store.rows["101"]["rarity_level"] = "2"
                elif defect == "new_pos":
                    store.rows["105"] = dict(
                        word_id="105", word="ata", type="A", rarity_level="5", version="10"
                    )
                elif defect == "missing_row":
                    del store.rows["101"]
                elif defect == "identity":
                    store.rows["101"]["word"] = "ață"
                elif defect == "l1_drift":
                    store.rows["103"]["rarity_level"] = "4"
                else:
                    store.rows["104"]["rarity_level"] = "3"
                before = copy.deepcopy(store.rows)
                if defect == "unrelated_change":
                    result = run_human_corrections(
                        approval,
                        policy,
                        root / "out",
                        action="apply",
                        store=store,
                        confirm_package=package_id,
                    )
                    self.assertEqual(result["status"], "applied")
                    self.assertEqual(store.rows["104"], before["104"])
                else:
                    with self.assertRaises(ValueError):
                        run_human_corrections(
                            approval,
                            policy,
                            root / "out",
                            action="apply",
                            store=store,
                            confirm_package=package_id,
                        )
                    self.assertEqual(store.rows, before)
                    self.assertEqual(store.receipts, {})
                    self.assertFalse((root / "out/receipt.json").exists())

    def test_failed_batch_receipt_commit_or_trigger_side_effect_never_publishes_confirmation(self):
        from classificator.human_correction_flow import run_human_corrections

        for fault in ("partial", "receipt", "commit", "side_effect"):
            with self.subTest(fault=fault), TemporaryDirectory() as tmp:
                root = Path(tmp)
                approval, policy, package_id, store = self.inputs(root)
                before = copy.deepcopy(store.rows)
                store.fail = fault
                with self.assertRaises((RuntimeError, ValueError)):
                    run_human_corrections(
                        approval,
                        policy,
                        root / "out",
                        action="apply",
                        store=store,
                        confirm_package=package_id,
                    )
                self.assertEqual(store.rows, before)
                self.assertEqual(store.receipts, {})
                self.assertFalse((root / "out/receipt.json").exists())
                self.assertEqual(
                    json.loads((root / "out/attempt.json").read_text())["state"], "unconfirmed"
                )

    def test_lost_commit_acknowledgement_recovers_from_durable_receipt_without_reapplying(self):
        from classificator.human_correction_flow import run_human_corrections

        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            approval, policy, package_id, store = self.inputs(root)
            store.fail = "lost_commit_ack"
            with self.assertRaises(RuntimeError):
                run_human_corrections(
                    approval,
                    policy,
                    root / "lost",
                    action="apply",
                    store=store,
                    confirm_package=package_id,
                )
            self.assertFalse((root / "lost/receipt.json").exists())
            committed = copy.deepcopy(store.rows)
            store.fail = None
            result = run_human_corrections(
                approval,
                policy,
                root / "recovered",
                action="apply",
                store=store,
                confirm_package=package_id,
            )
            self.assertEqual(result["status"], "already_applied")
            self.assertEqual(store.rows, committed)
            self.assertEqual(store.receipts[package_id]["changed_ids"], ["100"])

    def test_rollback_uses_confirmed_receipt_and_restores_only_changed_ids_once(self):
        from classificator.human_correction_flow import run_human_corrections

        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            approval, policy, package_id, store = self.inputs(root)
            run_human_corrections(
                approval,
                policy,
                root / "apply",
                action="apply",
                store=store,
                confirm_package=package_id,
            )
            store.rows["104"]["rarity_level"] = "3"  # Unrelated later edit must survive rollback.
            result = run_human_corrections(
                approval,
                policy,
                root / "rollback",
                action="rollback",
                store=store,
                confirm_package=package_id,
            )
            self.assertEqual(result["status"], "rolled_back")
            self.assertEqual(store.rows["100"]["rarity_level"], "4")
            self.assertEqual(store.rows["101"]["rarity_level"], "5")
            self.assertEqual(store.rows["104"]["rarity_level"], "3")
            self.assertEqual(store.receipts[package_id]["state"], "rolled_back")
            before = copy.deepcopy(store.rows)
            again = run_human_corrections(
                approval,
                policy,
                root / "again",
                action="rollback",
                store=store,
                confirm_package=package_id,
            )
            self.assertEqual(again["status"], "already_rolled_back")
            self.assertEqual(store.rows, before)
            with self.assertRaises(ValueError):
                run_human_corrections(
                    approval,
                    policy,
                    root / "reapply",
                    action="apply",
                    store=store,
                    confirm_package=package_id,
                )

    def test_rollback_refuses_absent_receipt_aba_membership_and_ambiguous_transaction_age(self):
        from classificator.human_correction_flow import run_human_corrections

        for defect in (
            "no_receipt",
            "aba",
            "new_member",
            "wrong_ids",
            "wrong_values",
            "wrong_package",
            "xid_wrap",
            "future_xid",
        ):
            with self.subTest(defect=defect), TemporaryDirectory() as tmp:
                root = Path(tmp)
                approval, policy, package_id, store = self.inputs(root)
                run_human_corrections(
                    approval,
                    policy,
                    root / "apply",
                    action="apply",
                    store=store,
                    confirm_package=package_id,
                )
                if defect == "no_receipt":
                    store.receipts.clear()
                elif defect == "aba":
                    store.rows["100"]["version"] = "999"  # Score still5 after another write.
                elif defect == "new_member":
                    store.rows["105"] = dict(
                        word_id="105", word="ata", type="A", rarity_level="5", version="21"
                    )
                elif defect == "wrong_ids":
                    store.receipts[package_id]["changed_ids"] = []
                elif defect == "wrong_values":
                    store.receipts[package_id]["changes"][0]["target_level"] = "2"
                elif defect == "wrong_package":
                    store.receipts[package_id]["package_id"] = "another-package"
                elif defect == "xid_wrap":
                    store.txid += 2**32
                else:
                    store.receipts[package_id]["apply_txid"] = 99999
                before = copy.deepcopy((store.rows, store.receipts))
                with self.assertRaises(ValueError):
                    run_human_corrections(
                        approval,
                        policy,
                        root / "rollback",
                        action="rollback",
                        store=store,
                        confirm_package=package_id,
                    )
                self.assertEqual((store.rows, store.receipts), before)
                self.assertFalse((root / "rollback/receipt.json").exists())

    def test_input_changed_during_transaction_aborts_before_commit_and_receipt_retains_exact_values(
        self,
    ):
        from classificator.human_correction_flow import run_human_corrections

        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            approval, policy, package_id, store = self.inputs(root)
            original_update = store.update
            before = copy.deepcopy(store.rows)

            def changed_source(changes):
                result = original_update(changes)
                approval.write_text(approval.read_text() + " ")
                return result

            store.update = changed_source  # Fault injection at the external transaction boundary.
            with self.assertRaises(ValueError):
                run_human_corrections(
                    approval,
                    policy,
                    root / "changed",
                    action="apply",
                    store=store,
                    confirm_package=package_id,
                )
            self.assertEqual(store.rows, before)
            self.assertEqual(store.receipts, {})
            store.update = original_update
            run_human_corrections(
                approval,
                policy,
                root / "ok",
                action="apply",
                store=store,
                confirm_package=package_id,
            )
            row = store.receipts[package_id]["changes"][0]
            self.assertEqual(
                (row["word"], row["type"], row["expected_level"], row["target_level"]),
                ("ata", "N", "4", "5"),
            )
            self.assertTrue((root / "ok/manifest.json").exists())

    def test_cli_defaults_to_offline_dry_run_and_does_not_read_database_credentials(self):
        from classificator.human_correction_flow import main
        from unittest.mock import patch

        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            approval, policy, package_id, store = self.inputs(root)
            with (
                patch("psycopg.connect", side_effect=AssertionError("No DB")),
                patch("subprocess.Popen", side_effect=AssertionError("No LLM")),
                patch("socket.socket.connect", side_effect=AssertionError("No network")),
                patch.dict("os.environ", {}, clear=True),
            ):
                result = main(
                    [
                        "--approval",
                        str(approval),
                        "--policy",
                        str(policy),
                        "--output",
                        str(root / "preview"),
                    ]
                )
            self.assertEqual(result, 0)
            self.assertEqual(
                json.loads((root / "preview/result.json").read_text())["status"], "dry_run"
            )

    def test_receipt_side_effects_are_checked_before_commit_for_apply_and_rollback(self):
        from classificator.human_correction_flow import run_human_corrections

        for fault in ("word_after_apply", "receipt_rewrite", "word_after_rollback"):
            with self.subTest(fault=fault), TemporaryDirectory() as tmp:
                root = Path(tmp)
                approval, policy, package, store = self.inputs(root)
                action = "apply"
                if fault == "word_after_rollback":
                    run_human_corrections(
                        approval,
                        policy,
                        root / "apply",
                        action="apply",
                        store=store,
                        confirm_package=package,
                    )
                    action = "rollback"
                before = copy.deepcopy((store.rows, store.receipts))
                save = store.save_receipt

                def receipt_trigger(package_id, receipt, *, replace=False):
                    save(package_id, receipt, replace=replace)
                    if fault == "receipt_rewrite":
                        store.receipts[package_id]["state"] = "rolled_back"
                    else:
                        store.rows["104"]["rarity_level"] = "2"

                store.save_receipt = receipt_trigger
                with self.assertRaises(ValueError):
                    run_human_corrections(
                        approval,
                        policy,
                        root / "failed",
                        action=action,
                        store=store,
                        confirm_package=package,
                    )
                self.assertEqual((store.rows, store.receipts), before)
                self.assertFalse((root / "failed/receipt.json").exists())
