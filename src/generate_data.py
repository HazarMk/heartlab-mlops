"""Download/prepare UCI Cleveland Heart Disease data or generate an unlabeled drift batch."""
import argparse
from pathlib import Path

import numpy as np
import pandas as pd

URL = "https://archive.ics.uci.edu/ml/machine-learning-databases/heart-disease/processed.cleveland.data"
FEATURE_COLUMNS = [
    "age", "sex", "cp", "trestbps", "chol", "fbs", "restecg",
    "thalach", "exang", "oldpeak", "slope", "ca", "thal",
]
RAW_COLUMNS = FEATURE_COLUMNS + ["num"]


def load_cleveland(source: str | None = None) -> pd.DataFrame:
    frame = pd.read_csv(source or URL, header=None, names=RAW_COLUMNS, na_values="?")
    if frame.empty or list(frame.columns) != RAW_COLUMNS:
        raise ValueError("Cleveland CSV must contain the 13 expected features and disease column")
    for column in RAW_COLUMNS:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    if frame["num"].isna().any():
        raise ValueError("target column contains missing or invalid values")
    frame["target"] = (frame.pop("num") > 0).astype("int64")
    return frame


def make_drifted_batch(frame: pd.DataFrame, seed: int = 42, n: int = 200) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    batch = frame.drop(columns="target").sample(n, replace=True, random_state=seed).copy()
    batch["age"] = (batch["age"] + 10).clip(upper=110)
    batch["chol"] = (batch["chol"] + rng.normal(40, 10, n)).clip(lower=80, upper=700)
    batch["trestbps"] = (batch["trestbps"] + rng.normal(15, 5, n)).clip(lower=60, upper=260)
    return batch.reset_index(drop=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--drift", action="store_true", help="generate an unlabeled shifted batch")
    parser.add_argument("--source", help="read a local Cleveland-format CSV instead of downloading UCI data")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--rows", type=int, default=200, help="number of rows in a synthetic drift batch")
    args = parser.parse_args()

    frame = load_cleveland(args.source)
    if args.drift:
        output = Path("data/incoming/drifted.csv")
        result = make_drifted_batch(frame, args.seed, args.rows)
    else:
        output = Path("data/raw/heart.csv")
        result = frame
    output.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(output, index=False)
    print(f"Wrote {output}: {result.shape[0]} rows, {result.shape[1]} columns")


if __name__ == "__main__":
    main()
