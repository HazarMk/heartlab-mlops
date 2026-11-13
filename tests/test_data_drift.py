import pandas as pd

from src.drift import drift_p_values
from src.generate_data import load_cleveland, make_drifted_batch


def test_load_cleveland_converts_target_and_missing_markers(tmp_path):
    raw = tmp_path / "cleveland.csv"
    raw.write_text(
        "63,1,1,145,233,1,2,150,0,2.3,3,0,6,0\n"
        "67,1,4,160,286,0,2,108,1,1.5,2,?,3,2\n"
        "55,0,2,130,200,0,0,160,0,0,1,0,7,4\n",
        encoding="utf-8",
    )
    frame = load_cleveland(str(raw))
    assert frame["target"].tolist() == [0, 1, 1]
    assert pd.isna(frame.loc[1, "ca"])


def test_synthetic_drift_batch_is_unlabeled_and_drift_is_scored():
    reference = pd.DataFrame(
        {
            "age": [40, 45, 50, 55, 60], "trestbps": [110, 115, 120, 125, 130],
            "chol": [160, 180, 200, 220, 240], "thalach": [180, 170, 160, 150, 140],
            "oldpeak": [0.0, 0.2, 0.4, 0.6, 0.8], "sex": [0, 1, 0, 1, 0],
            "cp": [1, 2, 3, 4, 1], "fbs": [0, 0, 1, 0, 1], "restecg": [0, 1, 2, 0, 1],
            "exang": [0, 1, 0, 1, 0], "slope": [1, 2, 3, 1, 2],
            "ca": [0, 1, 2, 0, 1], "thal": [3, 6, 7, 3, 6], "target": [0, 1, 0, 1, 0],
        }
    )
    batch = make_drifted_batch(reference, seed=3, n=30)
    assert "target" not in batch.columns
    scores = drift_p_values(reference, batch)
    assert scores["age"]["test"] == "kolmogorov_smirnov"
    assert scores["sex"]["test"] == "chi_square"


