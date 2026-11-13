"""Heart Disease feature schema, preprocessing pipeline, and recall-constrained metrics."""
import numpy as np
import math

from pydantic import BaseModel, Field, field_validator, model_validator
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.metrics import precision_recall_curve
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

NUMERIC = ["age", "trestbps", "chol", "thalach", "oldpeak"]
CATEGORICAL = ["sex", "cp", "fbs", "restecg", "exang", "slope", "ca", "thal"]
FEATURES = NUMERIC + CATEGORICAL


def build_pipeline(n_estimators: int = 200, random_state: int = 42, max_depth: int | None = None) -> Pipeline:
    preprocessing = ColumnTransformer(
        [
            ("numeric", SimpleImputer(strategy="median"), NUMERIC),
            (
                "categorical",
                Pipeline(
                    [
                        ("imputer", SimpleImputer(strategy="most_frequent")),
                        ("onehot", OneHotEncoder(handle_unknown="ignore")),
                    ]
                ),
                CATEGORICAL,
            ),
        ]
    )
    classifier = RandomForestClassifier(
        n_estimators=n_estimators,
        max_depth=max_depth,
        class_weight="balanced",
        random_state=random_state,
    )
    return Pipeline([("preprocess", preprocessing), ("classifier", classifier)])


class Patient(BaseModel):
    """Named API input. ca and thal may be omitted when they were not measured."""
    age: float = Field(ge=18, le=110)
    sex: int = Field(ge=0, le=1)
    cp: int = Field(ge=1, le=4)
    trestbps: float = Field(ge=60, le=260)
    chol: float = Field(ge=80, le=700)
    fbs: int = Field(ge=0, le=1)
    restecg: int = Field(ge=0, le=2)
    thalach: float = Field(ge=50, le=250)
    exang: int = Field(ge=0, le=1)
    oldpeak: float = Field(ge=0, le=10)
    slope: int = Field(ge=1, le=3)
    ca: float | None = Field(default=None, ge=0, le=3)
    thal: float | None = None

    @model_validator(mode="after")
    def numeric_values_must_be_finite(self):
        for name, value in self.to_features().items():
            if value is not None and not math.isfinite(value):
                raise ValueError(f"{name} must be a finite number")
        return self

    @field_validator("thal")
    @classmethod
    def validate_thal(cls, value):
        if value is not None and value not in (3, 6, 7):
            raise ValueError("thal must be 3, 6, 7, or null")
        return value

    def to_features(self) -> dict:
        return self.model_dump()


def positive_probabilities(model, features) -> np.ndarray:
    classes = list(model.classes_)
    positive_index = classes.index(1)
    return model.predict_proba(features)[:, positive_index]


def threshold_for_recall(y_true, probabilities, target_recall: float = 0.90) -> float:
    if not 0 < target_recall <= 1:
        raise ValueError("target_recall must be in (0, 1]")
    precision, recall, thresholds = precision_recall_curve(y_true, probabilities)
    eligible = np.flatnonzero(recall[:-1] >= target_recall)
    if not len(eligible):
        return 0.0
    best = eligible[np.argmax(precision[eligible])]
    return float(thresholds[best])


def precision_at_recall(y_true, probabilities, target_recall: float = 0.90) -> float:
    threshold = threshold_for_recall(y_true, probabilities, target_recall)
    predictions = np.asarray(probabilities) >= threshold
    actual = np.asarray(y_true, dtype=int)
    true_positives = np.sum(predictions & (actual == 1))
    predicted_positives = np.sum(predictions)
    return float(true_positives / predicted_positives) if predicted_positives else 0.0
