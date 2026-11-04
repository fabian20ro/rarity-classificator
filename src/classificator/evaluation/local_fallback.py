"""Grouped offline validation of one predeclared local lexical fallback."""

import json
from importlib.metadata import version
import math
from statistics import median_low
from pathlib import Path
from tempfile import TemporaryDirectory

from .dataset import _sha256, _write_csv
from .form_frequency_report import REFERENCE_KINDS
from .frequency_cross_validation import _metrics
from .frequency_calibration import _fit
from .full_pilot_baselines import _indexed, _level

EVIDENCE_FIELDS = {
    "word_id",
    "word",
    "loc_pos",
    "aligned_pos",
    "alignment",
    "aligned_senses",
    "other_definition_count",
    "all_restricted",
    "all_specialist",
}
METHODS = ("baseline", "candidate")
VIEWS = {"revised_working": "working_level", "original_round_final": "initial_level"}
TREE_PARAMETERS = dict(
    criterion="absolute_error", max_depth=2, min_samples_leaf=5, random_state=0
)
FEATURES = ["log1p_other_definition_count", "all_restricted", "all_specialist"]


def _summary(rows):
    result = dict(total=len(rows))
    for method in METHODS:
        metrics = _metrics(rows, method)
        confusion = metrics["confusion_human_rows_prediction_columns"]
        predicted5 = sum(row[4] for row in confusion)
        actual5 = sum(confusion[4])
        predicted4 = sum(row[3] for row in confusion)
        actual4 = sum(confusion[3])
        metrics.update(
            precision4=confusion[3][3] / predicted4 if predicted4 else None,
            recall4=confusion[3][3] / actual4 if actual4 else None,
            predicted5=predicted5,
            actual5=actual5,
            true5=confusion[4][4],
            precision5=confusion[4][4] / predicted5 if predicted5 else None,
            recall5=confusion[4][4] / actual5 if actual5 else None,
            false5_on_human1_to3=sum(row[4] for row in confusion[:3]),
            false5_on_human4=confusion[3][4],
            four_five=dict(
                total=sum(sum(row) for row in confusion[3:]),
                exact=confusion[3][3] + confusion[4][4],
                human_rows_4_5_prediction_columns_1_2_3_4_5=confusion[3:],
            ),
        )
        result[method] = metrics
    return result


def _view_summary(rows):
    return dict(
        all=_summary(rows),
        wordfreq_missing=_summary([r for r in rows if not r["wordfreq"]]),
        clarified=_summary([r for r in rows if r["reference_kind"] in REFERENCE_KINDS]),
        opaque=_summary(
            [r for r in rows if r["reference_kind"] == "initial_opaque_form_pos"]
        ),
        human4_or5=_summary([r for r in rows if r["human_level"] >= 4]),
        non_singleton=_summary([r for r in rows if r["group_size"] > 1]),
    )


def _tree_prediction(train_ids, held_out, labels, evidence):
    if evidence[held_out]["alignment"] != "source_bounded":
        return dict(level=4, route="unresolved_four", train_ids=train_ids)
    if len(train_ids) < 10:
        return dict(level=4, route="insufficient_training_four", train_ids=train_ids)
    from sklearn.tree import DecisionTreeRegressor

    def vector(i):
        row = evidence[i]
        return [
            math.log1p(int(row["other_definition_count"])),
            int(row["all_restricted"]),
            int(row["all_specialist"]),
        ]

    model = DecisionTreeRegressor(**TREE_PARAMETERS)
    values = [vector(i) for i in train_ids]
    model.fit(values, [labels[i] for i in train_ids])
    leaf = int(model.apply([vector(held_out)])[0])
    leaves = model.apply(values)
    support = [i for i, node in zip(train_ids, leaves) if node == leaf]
    level = int(median_low(labels[i] for i in support))
    return dict(
        level=level,
        route="lexical_tree",
        train_ids=train_ids,
        held_out_vector=vector(held_out),
        leaf=leaf,
        leaf_train_ids=support,
        leaf_level=level,
        features=FEATURES,
        nodes=dict(
            children_left=model.tree_.children_left.tolist(),
            children_right=model.tree_.children_right.tolist(),
            feature=model.tree_.feature.tolist(),
            threshold=model.tree_.threshold.tolist(),
        ),
    )


def evaluate_local_fallback(
    reference_csv: Path,
    frequency_features_csv: Path,
    evidence_dir: Path,
    first_independent_csv: Path,
    groups_csv: Path,
    output_dir: Path,
):
    """Export complete grouped predictions and diagnostics; never touch DB/model APIs."""
    if output_dir.exists() or output_dir.is_symlink():
        raise FileExistsError(output_dir)
    manifest = json.loads((evidence_dir / "manifest.json").read_text())
    if manifest.get("policy") != "local-lexical-evidence-v1":
        raise ValueError("Unknown evidence policy")
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, dict) or "evidence.csv" not in artifacts:
        raise ValueError("Missing evidence artifact hashes")
    for name, digest in artifacts.items():
        path = Path(name)
        if (
            path.is_absolute()
            or ".." in path.parts
            or not (evidence_dir / path).is_file()
        ):
            raise ValueError("Invalid evidence artifact path")
        if _sha256(evidence_dir / path) != digest:
            raise ValueError("Evidence artifact hash mismatch")
    ref = _indexed(reference_csv, {"initial_level", "working_level", "reference_kind"})
    first = _indexed(first_independent_csv, {"level"})
    frequency = _indexed(frequency_features_csv, {"wordfreq", "rebus"})
    groups = _indexed(groups_csv, {"group"})
    evidence = _indexed(evidence_dir / "evidence.csv", EVIDENCE_FIELDS)
    if len(ref) < 3 or len(first) < 3:
        raise ValueError("At least three labels per view required")
    if not first.keys() <= ref.keys() or not ref.keys() <= frequency.keys():
        raise ValueError("First labels/frequency identities mismatch")
    if groups.keys() != ref.keys() or evidence.keys() != ref.keys():
        raise ValueError("Groups/evidence must cover exactly the reference")
    for collection in (first, groups, evidence, frequency):
        if any(i in ref and r["word"] != ref[i]["word"] for i, r in collection.items()):
            raise ValueError("Input spelling mismatch")
    for row in ref.values():
        if row["reference_kind"] not in REFERENCE_KINDS | {"initial_opaque_form_pos"}:
            raise ValueError("Unknown reference kind")
    for row in frequency.values():
        if set(row) != {"word_id", "word", "wordfreq", "rebus"}:
            raise ValueError("Unexpected frequency fields")
        for source in ("wordfreq", "rebus"):
            value = float(row[source]) if row[source] else None
            if value is not None and (not math.isfinite(value) or not 0 <= value <= 1):
                raise ValueError("Invalid frequency")
            row[source] = value or None
    for row in groups.values():
        if set(row) != {"word_id", "word", "group"} or not row["group"].strip():
            raise ValueError("Invalid groups contract")
        row["group"] = row["group"].strip()
    for ids in (ref, first):
        if len({groups[i]["group"] for i in ids}) < 2:
            raise ValueError("At least two groups per label view required")
    for row in evidence.values():
        if set(row) != EVIDENCE_FIELDS:
            raise ValueError("Unexpected evidence fields")
        if row["alignment"] not in {"source_bounded", "unresolved"}:
            raise ValueError("Unknown alignment")
        for field in ("all_restricted", "all_specialist"):
            if row[field] not in {"0", "1"}:
                raise ValueError("Evidence booleans must be0 or1")
        for field in ("aligned_senses", "other_definition_count"):
            if not row[field].isdigit():
                raise ValueError("Evidence counts must be nonnegative integers")
        loc = set(row["loc_pos"].split("|")) - {""}
        aligned = set(row["aligned_pos"].split("|")) - {""}
        if row["alignment"] == "source_bounded" and (
            not loc or not loc <= aligned or int(row["aligned_senses"]) == 0
        ):
            raise ValueError("Inconsistent source-bounded evidence")
    label_views = {
        view: {i: _level(r[field]) for i, r in ref.items()}
        for view, field in VIEWS.items()
    }
    label_views["first_independent"] = {i: _level(r["level"]) for i, r in first.items()}
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=output_dir.parent, prefix=".local-fallback-") as temp:
        staged = Path(temp) / "output"
        staged.mkdir()
        protocol = dict(
            schema=1,
            experiment="local-lexical-fallback-v1",
            folds="leave-one-group-out",
            parameter_search=False,
            features=FEATURES,
            candidate=dict(
                TREE_PARAMETERS,
                minimum_training_rows=10,
                leaf_prediction="lower median of training leaf labels",
            ),
            baseline="fold-fitted wordfreq thresholds; missing or no fitted model =>4",
            candidate_gate="only wordfreq-missing, source_bounded alignment; unknown =>4",
            training="only eligible missing-wordfreq rows outside the held-out group",
            coverage="integer scores1..5 for every reference row in each label view",
            limitations=[
                "Exploratory protocol after prior pilot inspection, not independent generalization.",
                "Latest labels mix clarified and original opaque form/POS labels.",
                "Known-POS alignment is source-bounded, not exhaustive sense validation.",
                "No source paths, review round/count, assistant prose or ratings used as features.",
                "No deployment, database or D1 access.",
            ],
            runtime={
                name: version(name) for name in ("numpy", "scipy", "scikit-learn")
            },
        )
        (staged / "protocol.json").write_text(json.dumps(protocol, indent=2) + "\n")
        result = dict(protocol=protocol, views={})
        for view, labels in label_views.items():
            directory = staged / view
            (directory / "folds").mkdir(parents=True)
            rows = []
            for i in sorted(labels):
                train_ids = [
                    j
                    for j in sorted(labels)
                    if groups[j]["group"] != groups[i]["group"]
                ]
                tree_ids = [
                    j
                    for j in train_ids
                    if not frequency[j]["wordfreq"]
                    and evidence[j]["alignment"] == "source_bounded"
                ]
                observed_ids = [j for j in train_ids if frequency[j]["wordfreq"]]
                model = (
                    _fit(
                        [
                            (float(frequency[j]["wordfreq"]), labels[j])
                            for j in observed_ids
                        ]
                    )
                    if observed_ids
                    else None
                )
                if model:
                    model["observed_train_ids"] = observed_ids
                    model["objective"] = (
                        "minimum ordinal MAE on observed training labels of declared view"
                    )
                value = (
                    float(frequency[i]["wordfreq"])
                    if frequency[i]["wordfreq"]
                    else None
                )
                direct = (
                    1 + sum(value < t for t in model["thresholds"])
                    if value and model
                    else None
                )
                if direct is not None:
                    tree = dict(
                        level=direct, route="frequency_thresholds", train_ids=[]
                    )
                elif value:
                    tree = dict(level=4, route="no_frequency_model_four", train_ids=[])
                else:
                    tree = _tree_prediction(tree_ids, i, labels, evidence)
                fold = dict(
                    train_ids=train_ids,
                    held_out_ids=[
                        j
                        for j in sorted(labels)
                        if groups[j]["group"] == groups[i]["group"]
                    ],
                    wordfreq=model,
                    tree=tree,
                )
                (directory / "folds" / f"{i}.json").write_text(
                    json.dumps(fold, indent=2) + "\n"
                )
                rows.append(
                    dict(
                        word_id=i,
                        word=ref[i]["word"],
                        human_level=labels[i],
                        reference_kind=ref[i]["reference_kind"],
                        group=groups[i]["group"],
                        group_size=sum(
                            groups[j]["group"] == groups[i]["group"] for j in labels
                        ),
                        wordfreq=frequency[i]["wordfreq"],
                        baseline_level=direct if direct is not None else 4,
                        candidate_level=tree["level"],
                        candidate_route=tree["route"],
                    )
                )
            _write_csv(directory / "predictions.csv", list(rows[0]), rows)
            result["views"][view] = _view_summary(rows)
        (staged / "summary.json").write_text(
            json.dumps(result, indent=2, allow_nan=False) + "\n"
        )
        manifest = dict(
            inputs={
                str(p.resolve()): _sha256(p)
                for p in (
                    reference_csv,
                    frequency_features_csv,
                    evidence_dir / "manifest.json",
                    evidence_dir / "evidence.csv",
                    first_independent_csv,
                    groups_csv,
                )
            },
            implementation={
                str(p.resolve()): _sha256(p)
                for p in (
                    Path(__file__),
                    Path(__file__).with_name("frequency_calibration.py"),
                    Path(__file__).with_name("frequency_cross_validation.py"),
                    Path(__file__).with_name("form_frequency_report.py"),
                    Path(__file__).with_name("full_pilot_baselines.py"),
                    Path(__file__).with_name("dataset.py"),
                )
            },
            artifacts={
                str(p.relative_to(staged)): _sha256(p)
                for p in staged.rglob("*")
                if p.is_file()
            },
        )
        (staged / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
        staged.rename(output_dir)
    return result
