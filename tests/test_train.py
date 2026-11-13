import numpy as np
import pandas as pd
import pytest
from pydantic import ValidationError

from src.features import FEATURES, Patient, build_pipeline, precision_at_recall, threshold_for_recall
from src.train import evaluate


def sample_patient(**updates):
    values = {
        "age": 63, "sex": 1, "cp": 1, "trestbps": 145, "chol": 233,
        "fbs": 1, "restecg": 2, "thalach": 150, "exang": 0,
        "oldpeak": 2.3, "slope": 3, "ca": 0, "thal": 6,
    }
    values.update(updates)
    return Patient(**values)


def test_patient_accepts_plausible_values_and_missing_rare_fields():
    patient = sample_patient(ca=None, thal=None)
    assert patient.to_features()["thal"] is None


def test_patient_rejects_out_of_range_age_and_invalid_thal():
    with pytest.raises(ValidationError):
        sample_patient(age=12)
    with pytest.raises(ValidationError):
        sample_patient(thal=4)


def test_preprocessing_pipeline_fits_with_missing_values():
    rows = []
    labels = []
    for index in range(40):
        patient = sample_patient(age=40 + index, ca=None if index % 7 == 0 else index % 4)
        rows.append(patient.to_features())
        labels.append(index % 2)
    model = build_pipeline(n_estimators=10, random_state=4).fit(pd.DataFrame(rows, columns=FEATURES), labels)
    assert model.predict_proba(pd.DataFrame(rows[:2], columns=FEATURES)).shape == (2, 2)


def test_precision_at_recall_and_threshold_select_a_valid_operating_point():
    labels = np.array([0, 0, 0, 1, 1, 1])
    probabilities = np.array([0.05, 0.10, 0.35, 0.40, 0.80, 0.90])
    threshold = threshold_for_recall(labels, probabilities, 0.66)
    assert 0 <= threshold <= 1
    score = precision_at_recall(labels, probabilities, 0.66)
    assert score == pytest.approx(1.0)


def test_evaluate_uses_probabilities_and_recall_threshold():
    class FakeModel:
        classes_ = np.array([0, 1])

        def predict_proba(self, features):
            return np.array([[0.9, 0.1], [0.7, 0.3], [0.2, 0.8], [0.1, 0.9]])

    labels = pd.Series([0, 0, 1, 1])
    result = evaluate(FakeModel(), pd.DataFrame({"x": range(4)}), labels, 0.9)
    assert result["precision_at_target_recall"] == pytest.approx(1.0)
    assert result["recall_at_threshold"] >= 0.9
