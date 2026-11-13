import numpy as np
import pytest
from fastapi.testclient import TestClient

from app import main

SAMPLE_PATIENT = {
    "age": 63, "sex": 1, "cp": 1, "trestbps": 145, "chol": 233,
    "fbs": 1, "restecg": 2, "thalach": 150, "exang": 0,
    "oldpeak": 2.3, "slope": 3, "ca": None, "thal": None,
}


@pytest.fixture
def client(monkeypatch, tmp_path):
    main.app.dependency_overrides.clear()
    main.app.dependency_overrides[main.require_authenticated_user] = lambda: {"sub": "demo-user"}
    main.app.dependency_overrides[main.require_research_editor] = lambda: {"sub": "demo-user"}
    monkeypatch.setattr(main, "load_model", lambda: None)
    monkeypatch.setenv("RESEARCH_READINESS_DB", str(tmp_path / "readiness.db"))
    main.state.update(model=None, threshold=0.5, version=None)
    with TestClient(main.app) as test_client:
        yield test_client
    main.app.dependency_overrides.clear()
    main.state.update(model=None, threshold=0.5, version=None)


def test_health_reports_degraded_without_model(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["model_loaded"] is False


def test_research_readiness_is_authenticated_and_never_claims_clinical_approval(client):
    response = client.get("/research/readiness")

    assert response.status_code == 200
    payload = response.json()
    assert payload["region"] == "Tunisia"
    assert payload["clinical_use_enabled"] is False
    assert payload["model_status"] == "demonstration_only_not_clinically_validated"
    assert payload["completed_items"] == 0
    assert payload["total_items"] == len(payload["items"])
    assert all(item["status"] == "not_started" for item in payload["items"])
    assert all(item["history"] == [] for item in payload["items"])
    assert any(item["id"] == "ethics-approvals" for item in payload["items"])
    assert any(item["id"] == "independent-validation" for item in payload["items"])


def test_research_readiness_updates_are_persisted_and_audited(client):
    update = {
        "status": "in_progress",
        "owner": "Research lead",
        "due_date": "2026-12-15",
        "notes": "Draft protocol review scheduled.",
    }
    response = client.put("/research/readiness/intended-use", json=update)

    assert response.status_code == 200
    assert response.json()["status"] == "in_progress"
    assert response.json()["owner"] == "Research lead"
    assert response.json()["updated_by"] == "demo-user"

    item = next(
        item
        for item in client.get("/research/readiness").json()["items"]
        if item["id"] == "intended-use"
    )
    assert item["due_date"] == "2026-12-15"
    assert item["notes"] == "Draft protocol review scheduled."
    assert item["history"] == [
        {
            "changed_fields": ["due_date", "notes", "owner", "status"],
            "updated_at": response.json()["updated_at"],
            "updated_by": "demo-user",
        }
    ]
    assert client.get("/research/readiness").json()["completed_items"] == 0


def test_research_readiness_edit_requires_editor_role(monkeypatch, tmp_path):
    main.app.dependency_overrides.clear()
    main.app.dependency_overrides[main.require_authenticated_user] = lambda: {
        "sub": "demo-viewer",
        "realm_access": {"roles": ["research-viewer"]},
    }
    monkeypatch.setattr(main, "load_model", lambda: None)
    monkeypatch.setenv("RESEARCH_READINESS_DB", str(tmp_path / "readiness.db"))
    try:
        with TestClient(main.app) as test_client:
            response = test_client.put(
                "/research/readiness/intended-use",
                json={"status": "in_progress"},
            )
        assert response.status_code == 403
    finally:
        main.app.dependency_overrides.clear()


def test_research_readiness_rejects_unknown_or_empty_updates(client):
    assert client.put("/research/readiness/unknown", json={"status": "complete"}).status_code == 404
    assert client.put("/research/readiness/intended-use", json={}).status_code == 422
    assert client.put(
        "/research/readiness/intended-use", json={"status": "approved"}
    ).status_code == 422
    assert client.put(
        "/research/readiness/intended-use", json={"status": None}
    ).status_code == 422


def test_protected_routes_reject_requests_without_access_token(monkeypatch):
    monkeypatch.setattr(main, "load_model", lambda: None)
    main.state.update(model=None, threshold=0.5, version=None)
    with TestClient(main.app) as test_client:
        assert test_client.post("/predict", json=SAMPLE_PATIENT).status_code == 401
        assert test_client.post(
            "/evaluate", json={"patients": [SAMPLE_PATIENT], "labels": [0]}
        ).status_code == 401
        assert test_client.post("/reload").status_code == 401
        assert test_client.get("/research/readiness").status_code == 401
        assert test_client.put(
            "/research/readiness/intended-use",
            json={"status": "in_progress"},
        ).status_code == 401


def test_openapi_documents_service_unavailable_responses():
    schema = main.app.openapi()

    for path in ("/reload", "/predict", "/evaluate"):
        assert "503" in schema["paths"][path]["post"]["responses"]
    assert "500" in schema["paths"]["/predict"]["post"]["responses"]
    assert "500" in schema["paths"]["/evaluate"]["post"]["responses"]
    assert "403" in schema["paths"]["/research/readiness/{item_id}"]["put"]["responses"]
    assert "503" in schema["paths"]["/research/readiness"]["get"]["responses"]


def test_predict_validates_named_patient_fields(client):
    invalid = {**SAMPLE_PATIENT, "age": 10}
    assert client.post("/predict", json=invalid).status_code == 422
    assert client.post("/predict", json=SAMPLE_PATIENT).status_code == 503


def test_prediction_returns_probability_threshold_and_version(client, monkeypatch):
    class FakeModel:
        def predict_proba(self, rows):
            assert list(rows.columns) == main.FEATURES
            return np.array([[0.25, 0.75]])

    monkeypatch.setitem(main.state, "model", FakeModel())
    monkeypatch.setitem(main.state, "threshold", 0.6)
    monkeypatch.setitem(main.state, "version", "7")
    result = client.post("/predict", json=SAMPLE_PATIENT)
    assert result.status_code == 200
    assert result.json()["prediction"] == 1
    assert result.json()["disease_probability"] == pytest.approx(0.75)
    assert result.json()["model_version"] == "7"


def test_evaluate_returns_binary_classification_metrics(client, monkeypatch):
    class FakeModel:
        def predict_proba(self, rows):
            return np.array([[0.8, 0.2], [0.2, 0.8]])

    monkeypatch.setitem(main.state, "model", FakeModel())
    batch = {"patients": [SAMPLE_PATIENT, SAMPLE_PATIENT], "labels": [0, 1]}
    response = client.post("/evaluate", json=batch)
    assert response.status_code == 200
    assert response.json()["accuracy"] == 1.0
    assert response.json()["precision"] == 1.0
    assert response.json()["recall"] == 1.0


def test_evaluate_rejects_unequal_counts_and_invalid_labels(client):
    assert client.post("/evaluate", json={"patients": [SAMPLE_PATIENT], "labels": []}).status_code == 422
    assert client.post("/evaluate", json={"patients": [SAMPLE_PATIENT], "labels": [3]}).status_code == 422
