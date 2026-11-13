"""Detect numeric and categorical data drift for Heart Disease batches."""
import argparse
import json
import shutil
import sys
from pathlib import Path

import pandas as pd
import yaml
from scipy.stats import chi2_contingency, ks_2samp

try:
    from features import CATEGORICAL, FEATURES, NUMERIC
except ImportError:
    from src.features import CATEGORICAL, FEATURES, NUMERIC


def drift_p_values(reference: pd.DataFrame, current: pd.DataFrame) -> dict:
    results = {}
    for column in NUMERIC:
        ref_values = reference[column].dropna()
        cur_values = current[column].dropna()
        results[column] = {
            "test": "kolmogorov_smirnov",
            "p_value": float(ks_2samp(ref_values, cur_values).pvalue),
        }
    for column in CATEGORICAL:
        ref_values = reference[column].fillna("__missing__").astype(str)
        cur_values = current[column].fillna("__missing__").astype(str)
        categories = sorted(set(ref_values) | set(cur_values))
        observed = pd.DataFrame(
            {
                "reference": ref_values.value_counts().reindex(categories, fill_value=0),
                "current": cur_values.value_counts().reindex(categories, fill_value=0),
            }
        ).T
        p_value = float(chi2_contingency(observed, correction=False).pvalue) if len(categories) > 1 else 1.0
        results[column] = {"test": "chi_square", "p_value": p_value}
    return results


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reference", default="data/raw/heart.csv")
    parser.add_argument("--current", default="data/incoming/drifted.csv")
    parser.add_argument("--retrain", action="store_true", help="prepare a labeled batch as the DVC retraining input")
    args = parser.parse_args()

    with open("params.yaml", encoding="utf-8") as params_file:
        params = yaml.safe_load(params_file)
    target = params["data"]["target"]
    config = params["drift"]
    reference = pd.read_csv(args.reference)
    current = pd.read_csv(args.current)
    missing_reference = set(FEATURES) - set(reference.columns)
    missing_current = set(FEATURES) - set(current.columns)
    if missing_reference or missing_current:
        raise ValueError(f"missing Heart Disease features: reference={sorted(missing_reference)}, current={sorted(missing_current)}")
    ref_features = reference[FEATURES]
    cur_features = current[FEATURES]
    if ref_features.empty or cur_features.empty:
        raise ValueError("reference and incoming data must both contain rows")

    results = drift_p_values(ref_features, cur_features)
    drifted = [name for name, result in results.items() if result["p_value"] < config["p_value_threshold"]]
    share = len(drifted) / len(FEATURES)
    report = {"tests": results, "drifted_features": drifted, "drift_share": share}
    Path("reports").mkdir(exist_ok=True)
    Path("reports/drift.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Drifted features: {len(drifted)}/{len(FEATURES)} ({share:.0%}): {drifted}")

    if share < config["share_threshold"]:
        print("No drift threshold reached.")
        return 0
    print("DRIFT DETECTED")
    if args.retrain:
        if target not in current.columns:
            raise ValueError("retraining requires verified ground-truth labels in the incoming batch")
        if set(current[target].dropna().astype(int).unique()) != {0, 1}:
            raise ValueError("labeled incoming batch must contain both target classes 0 and 1")
        destination = Path("data/incoming/heart_labeled.csv")
        destination.parent.mkdir(parents=True, exist_ok=True)
        if Path(args.current).resolve() != destination.resolve():
            shutil.copy2(args.current, destination)
        print("Labeled batch is ready; run `dvc repro retraining/dvc.yaml:retrain` to train and compare the model.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
