"""Prepare the automatic installer offline; never connect, activate login or apply scores."""

import argparse
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from .automatic_promotion_flow import run_automatic_promotion
from .automatic_installation_checks import (
    STATE,
    ROLE,
    FULL_DATA,
    SEQUENCE_STATE,
    deployment_checks,
    automatic_installation_capture_sql as automatic_installation_capture_sql,
)
from .evaluation.dataset import _read_csv, _sha256
from .human_installation import _body, _json, _literal, _read_checks, _assert_checks

VERSION = "automatic-installation-bundle-v1"
SQL_SOURCE = (
    Path(__file__).resolve().parents[2] / "docs/sql/2026-11-06-automatic-promotion-receipts.sql"
)


def _bounded_checks(checks):
    return _read_checks(checks).replace(
        "BEGIN READ ONLY;",
        "BEGIN READ ONLY;\nSET LOCAL statement_timeout='30s';\nSET LOCAL lock_timeout='2s';",
    )


def prepare_automatic_installation(acceptance, package, capture, output):
    """Pinned acceptance/package + read-only state → reviewable, non-executing SQL bundle."""
    acceptance, package, capture, output = map(Path, (acceptance, package, capture, output))
    if output.exists() or output.is_symlink():
        raise FileExistsError(output)
    inputs = {
        str(p.resolve()): _sha256(p)
        for p in (
            acceptance,
            capture,
            SQL_SOURCE,
            Path(__file__),
            Path(__file__).with_name("automatic_installation_checks.py"),
            Path(__file__).with_name("human_correction_postgres.py"),
            Path(__file__).with_name("human_installation.py"),
        )
    }
    observed = json.loads(capture.read_text())
    output.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=output.parent) as temp:
        staged = Path(temp) / "bundle"
        staged.mkdir()
        preview = run_automatic_promotion(acceptance, package, staged / "audit")
        inputs.update(json.loads((staged / "audit/manifest.json").read_text())["inputs"])
        state = observed["state"]
        contract = json.loads((staged / "audit/audit/contract.json").read_text())
        rows = _read_csv(
            Path(contract["inputs"]["snapshot"]["path"]),
            {"word_id", "word", "type", "rarity_level", "version"},
        )
        encoded = "".join(
            str(len(r[k].encode())) + ":" + r[k]
            for r in sorted(rows, key=lambda r: int(r["word_id"]))
            for k in ("word_id", "word", "type", "rarity_level", "version")
        )
        expected = {
            "rows": len(rows),
            "digest": hashlib.sha256(encoded.encode()).hexdigest(),
        }
        if (
            observed.get("version") != "automatic-installation-capture-v1"
            or observed.get("read_only") != "on"
            or state["inventory"] != expected
            or state["revision_valid"] is not True
            or len(state["epoch"]) != 1
            or state["words_owner"] != "postgres"
            or state["schema_owner"] != "postgres"
            or state["engine_version"] != "1.8"
            or state["server_version"] != "17.9"
        ):
            raise ValueError("Incompatible read-only capture or approved snapshot drift")
        if set(state) != set(STATE):
            raise ValueError("Incomplete deployment capture")
        identity = hashlib.sha256(json.dumps(inputs, sort_keys=True).encode()).hexdigest()
        checks, post = deployment_checks(state)
        post["installation_receipt_bound"] = (
            f"(SELECT count(*)=1 AND bool_and(receipt->>'installation_id'={_literal(identity)} AND receipt->>'package_id'={_literal(preview['package_id'])} AND receipt->>'epoch'={_literal(state['epoch'][0])} AND receipt->>'scores_applied'='false' AND receipt->>'executor_login'='false' AND receipt->>'data_before'=receipt->>'data_after' AND receipt->>'data_after'={FULL_DATA} AND receipt->'sequence_before'={SEQUENCE_STATE}) FROM classificator_private.automatic_installation_receipt)"
        )
        grants = f"""CREATE ROLE {ROLE} NOLOGIN BYPASSRLS NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION;
GRANT USAGE ON SCHEMA public, classificator_private TO {ROLE};
GRANT SELECT, UPDATE ON public.words TO {ROLE};
GRANT SELECT ON classificator_private.words_revision_contract TO {ROLE};
GRANT SELECT, INSERT, UPDATE ON classificator_private.automatic_promotion_receipts TO {ROLE};"""
        body = (
            _assert_checks(checks)
            + f"\nbefore_data := {FULL_DATA};\nsequence_before := {SEQUENCE_STATE};\n"
            + _body(SQL_SOURCE)
            + f"""
CREATE TABLE classificator_private.automatic_installation_receipt (
    singleton boolean PRIMARY KEY CHECK(singleton), receipt jsonb NOT NULL
) USING heap;
REVOKE ALL ON classificator_private.automatic_installation_receipt FROM PUBLIC;
{grants}
INSERT INTO classificator_private.automatic_installation_receipt VALUES (true,jsonb_build_object(
    'version','{VERSION}','installation_id',{_literal(identity)},'package_id',{_literal(preview['package_id'])},
    'epoch',{_literal(state['epoch'][0])},'data_before',before_data,'data_after',{FULL_DATA},
    'sequence_before',sequence_before,'scores_applied',false,'executor_login',false,'installed_at',clock_timestamp()));
SET CONSTRAINTS ALL IMMEDIATE;
"""
            + _assert_checks(post)
        )
        tag = "$install_" + hashlib.sha256(body.encode()).hexdigest()[:16] + "$"
        while tag in body:
            tag = tag[:-1] + "x$"
        install = f"""BEGIN;
SET LOCAL lock_timeout='5s';
SET LOCAL statement_timeout='120s';
SET LOCAL standard_conforming_strings=on;
SET LOCAL search_path=pg_catalog;
SET LOCAL row_security=off;
SET LOCAL synchronous_commit=on;
SET LOCAL createrole_self_grant='';
LOCK TABLE public.words, classificator_private.human_correction_receipts,
    classificator_private.words_revision_contract,
    classificator_private.installation_receipt IN SHARE ROW EXCLUSIVE MODE;
DO {tag}
DECLARE before_data text; sequence_before jsonb;
BEGIN
{body}
END;
{tag};
COMMIT;
"""
        (staged / "01-preflight.sql").write_text(_bounded_checks(checks))
        (staged / "02-install.sql").write_text(install)
        (staged / "03-postflight.sql").write_text(_bounded_checks(post))
        report = dict(
            version=VERSION,
            installation_id=identity,
            preflight_checks=list(checks),
            postflight_checks=list(post),
            package_id=preview["package_id"],
            inventory_rows=state["inventory"]["rows"],
            installation_authorized=False,
            scores_applied=False,
            executor_login=False,
        )
        _json(staged / "report.json", report)
        (staged / "README.md").write_text(INSTRUCTIONS)
        for path, digest in inputs.items():
            if _sha256(Path(path)) != digest:
                raise ValueError("Installation input changed")
        _json(
            staged / "manifest.json",
            dict(
                version=VERSION,
                inputs=inputs,
                artifacts={
                    str(p.relative_to(staged)): _sha256(p)
                    for p in sorted(staged.rglob("*"))
                    if p.is_file()
                },
            ),
        )
        staged.rename(output)
    return report


def verify_automatic_installation(root):
    root = Path(root)
    manifest = json.loads((root / "manifest.json").read_text())
    actual = {
        str(p.relative_to(root))
        for p in root.rglob("*")
        if p.is_file() and p != root / "manifest.json"
    }
    if (
        manifest.get("version") != VERSION
        or actual != set(manifest["artifacts"])
        or any(p.is_symlink() for p in root.rglob("*"))
    ):
        raise ValueError("Installation artifact inventory differs from manifest")
    for name, digest in manifest["artifacts"].items():
        if _sha256(root / name) != digest:
            raise ValueError("Installation artifact changed: " + name)
    for name, digest in manifest["inputs"].items():
        if _sha256(Path(name)) != digest:
            raise ValueError("Installation input changed: " + name)
    return dict(valid=True, installation_authorized=False)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("acceptance", "package", "capture", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args(argv)
    print(
        json.dumps(
            prepare_automatic_installation(
                args.acceptance, args.package, args.capture, args.output
            ),
            indent=2,
        )
    )
    return 0


INSTRUCTIONS = """# Automatic installation bundle — not executed

Preparation does not authorize installation, login activation or score application.
Verify with verify_automatic_installation(path); retain the reviewed manifest hash
outside this directory. Hashes detect drift, not a maliciously resealed bundle.
Use the pinned checkout and source inputs. Never edit generated SQL to bypass checks.

After separate installation authorization:
1. Confirm the real endpoint/project out of band. A cloned inventory is not proof
   of deployment identity. Use the existing words/schema owner, not the human role.
2. Run 01-preflight.sql read-only; every check must pass. Save results outside this
   immutable bundle. Confirm private schema is not exposed via Data API; reserve a
   maintenance window. The installer blocks writes to words and the human ledger.
3. Execute 02-install.sql once with a stop-on-error client, e.g.
   psql -X --set=ON_ERROR_STOP=1 --file=02-install.sql. Preconditions are repeated
   under locks in one transaction. Do not execute component SQL separately.
4. Run 03-postflight.sql read-only; every check must pass. Save the private automatic
   installation receipt. Executor stays NOLOGIN, no password is included. No score
   or existing revision is changed; human grants and receipt remain intact.
5. Dedicated credentials/login activation, direct connection checks and score apply
   are later, separately authorized actions. Never use the human executor or grant
   API roles private-schema access. The automatic role has BYPASSRLS with narrow
   table ACLs; row_security=off alone never grants access. Table-level UPDATE is
   required by the existing runtime lock. No sequence, contract-write or human-ledger
   privileges; owner/DDL administrators remain trusted.

Recovery: any SQL error aborts transactional DDL/grants. Close or explicitly roll
back the failed connection; inspect preflight/postflight before retrying. A lost
acknowledgement does not prove failure: matching installation receipt and all
postchecks identify committed success. Do not reinstall on that path. Existing
objects are an error, not silently adopted. No automatic DROP/uninstall provided.
Sequence and external DDL-hook effects are not transactional: inspect them after
failure; never reset the revision sequence to make a check pass. Administrator
reconciliation is required if sequence history regresses. Restore/reload/DDL changes
require renewed review. These checks describe the disabled, pre-application state;
postflight deliberately stops passing after later activation or score application.

No rollback CSV here: installation changes no scores. The accepted score package's
inverse proposals become executable only with a future committed apply receipt and
post-write revisions. Rehearse this exact bundle on an owned OrioleDB before live use.
"""


if __name__ == "__main__":
    raise SystemExit(main())
