"""Train a Heart Disease pipeline and promote only on better precision at target recall."""
import json
import os
import argparse
import hashlib
import platform
from pathlib import Path

import mlflow
import mlflow.sklearn
import numpy as np
import pandas as pd
import yaml
from mlflow import MlflowClient
from mlflow.exceptions import MlflowException
from mlflow.models import infer_signature
import sklearn
from sklearn.metrics import (
    accuracy_score, average_precision_score, balanced_accuracy_score,
    brier_score_loss, confusion_matrix, f1_score, precision_score,
    recall_score, roc_auc_score,
)
from sklearn.model_selection import StratifiedKFold, cross_val_predict, cross_validate, train_test_split

try:
    from features import FEATURES, build_pipeline, positive_probabilities, threshold_for_recall
except ImportError:
    from src.features import FEATURES, build_pipeline, positive_probabilities, threshold_for_recall

ALIAS = "champion"
TRUSTED_SKOPS_TYPES = ["numpy.dtype", "sklearn.tree._tree.Tree"]


def evaluate(model, features: pd.DataFrame, labels: pd.Series, threshold: float = 0.5) -> dict:
    """Evaluate at a threshold chosen without using this evaluation batch's labels."""
    probabilities = positive_probabilities(model, features)
    predictions = (probabilities >= threshold).astype(int)
    tn, fp, fn, tp = confusion_matrix(labels, predictions, labels=[0, 1]).ravel()
    return {
        "accuracy": float(accuracy_score(labels, predictions)),
        "balanced_accuracy": float(balanced_accuracy_score(labels, predictions)),
        "precision_at_target_recall": float(precision_score(labels, predictions, zero_division=0)),
        "precision_at_threshold": float(precision_score(labels, predictions, zero_division=0)),
        "recall_at_threshold": float(recall_score(labels, predictions, zero_division=0)),
        "f1": float(f1_score(labels, predictions, zero_division=0)),
        "roc_auc": float(roc_auc_score(labels, probabilities)),
        "average_precision": float(average_precision_score(labels, probabilities)),
        "brier_score": float(brier_score_loss(labels, probabilities)),
        "specificity": float(tn / (tn + fp)) if tn + fp else 0.0,
        "true_positives": int(tp), "false_positives": int(fp),
        "true_negatives": int(tn), "false_negatives": int(fn),
        "rows": int(len(labels)),
        "decision_threshold": float(threshold),
    }


def subgroup_metrics(features: pd.DataFrame, labels: pd.Series, model, threshold: float) -> dict:
    """Exploratory subgroup results; small groups must not be treated as validation."""
    probabilities = positive_probabilities(model, features)
    predictions = (probabilities >= threshold).astype(int)
    groups = {
        "sex_code_0": features["sex"].astype(int) == 0,
        "sex_code_1": features["sex"].astype(int) == 1,
        "age_under_55": features["age"] < 55,
        "age_55_or_over": features["age"] >= 55,
    }
    report = {}
    for name, mask in groups.items():
        if int(mask.sum()) == 0:
            continue
        y_group = labels.loc[mask]
        pred_group = predictions[mask.to_numpy()]
        report[name] = {
            "rows": int(mask.sum()),
            "positive_labels": int(y_group.sum()),
            "precision": float(precision_score(y_group, pred_group, zero_division=0)),
            "recall": float(recall_score(y_group, pred_group, zero_division=0)),
        }
    return report


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_champion(client: MlflowClient, model_name: str):
    try:
        version = client.get_model_version_by_alias(model_name, ALIAS)
    except MlflowException:
        return None, None, None
    model = mlflow.sklearn.load_model(f"models:/{model_name}/{version.version}")
    threshold = float(version.tags.get("decision_threshold", "0.5"))
    return model, version, threshold


def main(data_path: str | None = None, metrics_path: str = "metrics.json") -> None:
    with open("params.yaml", encoding="utf-8") as params_file:
        params = yaml.safe_load(params_file)
    config, target = params["train"], params["data"]["target"]
    target_recall = float(config["target_recall"])
    mlflow.set_tracking_uri(os.getenv("MLFLOW_TRACKING_URI", "sqlite:///mlflow.db"))
    mlflow.set_experiment("heart-disease-classification")

    data_path = data_path or os.getenv("TRAIN_DATA_PATH", "data/raw/heart.csv")
    dataset = pd.read_csv(data_path)
    missing = set(FEATURES + [target]) - set(dataset.columns)
    if missing:
        raise ValueError(f"training data is missing columns: {sorted(missing)}")
    X, y = dataset[FEATURES], dataset[target].astype(int)
    if set(y.unique()) != {0, 1}:
        raise ValueError("training target must contain both binary classes 0 and 1")
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=config["test_size"], random_state=config["random_state"], stratify=y
    )

    def new_pipeline():
        return build_pipeline(
            n_estimators=int(config["n_estimators"]),
            random_state=int(config["random_state"]),
            max_depth=config.get("max_depth"),
        )

    folds = min(int(config.get("cv_folds", 5)), int(y_train.value_counts().min()))
    if folds < 2:
        raise ValueError("at least two examples of each class are required for stratified cross-validation")
    cv = StratifiedKFold(n_splits=folds, shuffle=True, random_state=int(config["random_state"]))
    cv_results = cross_validate(
        new_pipeline(), X_train, y_train, cv=cv,
        scoring={"roc_auc": "roc_auc", "average_precision": "average_precision", "balanced_accuracy": "balanced_accuracy"},
        return_train_score=False,
    )
    # Tune the operating threshold only from out-of-fold training predictions.
    # The stratified holdout below remains untouched until final evaluation.
    oof_probabilities = cross_val_predict(new_pipeline(), X_train, y_train, cv=cv, method="predict_proba")[:, 1]
    decision_threshold = threshold_for_recall(y_train, oof_probabilities, target_recall)
    oof_recall = float(recall_score(y_train, oof_probabilities >= decision_threshold, zero_division=0))

    client = MlflowClient()
    model_name = config["model_name"]
    try:
        champion, champion_version, champion_threshold = load_champion(client, model_name)
    except (MlflowException, OSError, ValueError):
        champion, champion_version, champion_threshold = None, None, None
    champion_metrics = evaluate(champion, X_test, y_test, champion_threshold) if champion else None
    candidate = new_pipeline().fit(X_train, y_train)
    candidate_metrics = evaluate(candidate, X_test, y_test, decision_threshold)
    candidate_metrics["oof_recall_at_threshold"] = oof_recall
    cv_metrics = {
        name: {
            "mean": float(np.mean(cv_results[f"test_{name}"])),
            "std": float(np.std(cv_results[f"test_{name}"])),
        }
        for name in ("roc_auc", "average_precision", "balanced_accuracy")
    }
    candidate_subgroups = subgroup_metrics(X_test, y_test, candidate, decision_threshold)
    dataset_hash = sha256_file(data_path)
    mlflow_cv_metrics = {
        f"candidate_cv_{name}_{stat}": value
        for name, stats in cv_metrics.items()
        for stat, value in stats.items()
    }
    promoted = (
        candidate_metrics["recall_at_threshold"] >= target_recall
        and (champion_metrics is None or candidate_metrics["precision_at_target_recall"] > champion_metrics["precision_at_target_recall"])
    )

    with mlflow.start_run() as run:
        mlflow.log_params({key: value for key, value in config.items() if key != "model_name"})
        mlflow.log_param("target_recall", target_recall)
        mlflow.log_param("training_data", data_path)
        mlflow.log_param("training_rows", int(len(X_train)))
        mlflow.log_param("holdout_rows", int(len(X_test)))
        mlflow.log_param("cross_validation_folds", folds)
        mlflow.log_param("python_version", platform.python_version())
        mlflow.log_param("scikit_learn_version", sklearn.__version__)
        mlflow.set_tag("training_data_sha256", dataset_hash)
        mlflow.log_metrics({f"candidate_{key}": value for key, value in candidate_metrics.items()})
        mlflow.log_metrics(mlflow_cv_metrics)
        if champion_metrics is not None:
            mlflow.log_metrics({f"champion_{key}": value for key, value in champion_metrics.items()})
        mlflow.set_tag("promotion_decision", "promote" if promoted else "keep_champion")
        mlflow.log_artifact("params.yaml")
        mlflow.log_dict(
            {
                "data_sha256": dataset_hash,
                "target_recall": target_recall,
                "threshold_calibration": "stratified out-of-fold predictions on training split",
                "holdout": "stratified holdout, not used for threshold tuning",
                "candidate": candidate_metrics,
                "candidate_cross_validation": cv_metrics,
                "candidate_subgroups_exploratory_only": candidate_subgroups,
                "champion": champion_metrics,
                "promoted": promoted,
            },
            "validation.json",
        )
        mlflow.log_dict(
            {
                "name": model_name,
                "intended_use": "educational research on the UCI Cleveland dataset only",
                "clinical_use": False,
                "training_rows": int(len(X_train)),
                "holdout_rows": int(len(X_test)),
                "data_sha256": dataset_hash,
                "features": FEATURES,
                "target": "binary Cleveland outcome: 0 vs greater than 0",
                "threshold": decision_threshold,
                "cross_validation": cv_metrics,
                "holdout_metrics": candidate_metrics,
                "subgroups_exploratory_only": candidate_subgroups,
                "limitations": [
                    "Small historical dataset; results have high statistical uncertainty.",
                    "Internal holdout is not independent external or Tunisian clinical validation.",
                    "Subgroup results are descriptive and must not be interpreted as fairness evidence.",
                    "Predicted probabilities are not calibrated clinical risk estimates.",
                    "Not validated for diagnosis, screening, treatment, or clinical decisions.",
                ],
            },
            "model_card.json",
        )
        model_info = mlflow.sklearn.log_model(
            candidate,
            name="model",
            input_example=X_test.head(3),
            signature=infer_signature(X_train.head(30), candidate.predict(X_train.head(30))),
            # Both are emitted by this project-owned sklearn preprocessing/tree pipeline.
            skops_trusted_types=TRUSTED_SKOPS_TYPES,
        )

    registered = mlflow.register_model(model_info.model_uri, model_name)
    version = str(registered.version)
    client.set_model_version_tag(model_name, version, "validation_status", "pending")
    client.set_model_version_tag(model_name, version, "decision_threshold", str(candidate_metrics["decision_threshold"]))
    client.set_model_version_tag(model_name, version, "training_data_sha256", dataset_hash)
    client.set_model_version_tag(model_name, version, "clinical_use", "not_validated")
    if promoted:
        client.set_registered_model_alias(model_name, ALIAS, version)
        client.set_model_version_tag(model_name, version, "validation_status", "approved")
        client.set_model_version_tag(model_name, version, "promoted_by", "precision_at_target_recall")
        print(f"Candidate v{version} promoted to @{ALIAS}: {candidate_metrics}")
        final_champion_version = version
    else:
        client.set_model_version_tag(model_name, version, "validation_status", "rejected")
        if champion_version is not None:
            print(
                f"Candidate v{version} rejected; champion v{champion_version.version} kept. "
                f"Candidate precision={candidate_metrics['precision_at_target_recall']:.3f}, "
                f"champion precision={champion_metrics['precision_at_target_recall']:.3f} "
                f"at recall target {target_recall:.2f}"
            )
            final_champion_version = str(champion_version.version)
        else:
            print(f"Candidate v{version} rejected: holdout recall did not reach {target_recall:.2f}; no champion is available.")
            final_champion_version = None

    report = {
        "dataset": "UCI Cleveland Heart Disease",
        "target_recall": target_recall,
        "candidate": candidate_metrics,
        "champion": champion_metrics,
        "promoted": promoted,
        "candidate_version": version,
        "champion_version": final_champion_version,
        "dataset_sha256": dataset_hash,
        "cross_validation": cv_metrics,
        "candidate_subgroups_exploratory_only": candidate_subgroups,
        "clinical_use": False,
    }
    metrics_file = Path(metrics_path)
    metrics_file.parent.mkdir(parents=True, exist_ok=True)
    metrics_file.write_text(json.dumps(report, indent=2), encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-path", default=None)
    parser.add_argument("--metrics-path", default="metrics.json")
    args = parser.parse_args()
    main(args.data_path, args.metrics_path)
