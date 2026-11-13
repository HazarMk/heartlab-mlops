"""FastAPI service for the registered UCI Cleveland Heart Disease model."""
import os
import logging
import sqlite3
import time
from contextlib import asynccontextmanager, contextmanager
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Generator, Literal

import mlflow
import mlflow.sklearn
import numpy as np
import pandas as pd
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from mlflow import MlflowClient
from prometheus_client import Counter, Gauge, Histogram, make_asgi_app
from pydantic import BaseModel, Field, model_validator
from sklearn.metrics import accuracy_score, precision_score, recall_score

from app.portal import initialize_portal_database, require_roles, router as portal_router
from app.assistant import router as assistant_router
from src.features import FEATURES, Patient

MODEL_NAME = os.getenv("MODEL_NAME", "heart-disease-classifier")
MODEL_URI = f"models:/{MODEL_NAME}@champion"

PREDICTIONS = Counter("predictions_total", "Predictions by disease decision", ["label"])
LATENCY = Histogram("prediction_latency_seconds", "Latency of /predict")
ERRORS = Counter("prediction_errors_total", "API and prediction errors")
MODEL_LOADED = Gauge("model_loaded", "Whether the champion model is loaded")
MODEL_ACCURACY = Gauge("model_accuracy", "Accuracy on the latest labeled evaluation batch")
MODEL_PRECISION = Gauge("model_precision", "Precision on the latest labeled evaluation batch")
MODEL_RECALL = Gauge("model_recall", "Recall on the latest labeled evaluation batch")
EVALUATED_ROWS = Counter("model_evaluation_rows_total", "Rows evaluated against ground truth")
DISEASE_PROBABILITY = Histogram("disease_probability", "Predicted disease probability")

state = {"model": None, "threshold": 0.5, "version": None}
logger = logging.getLogger(__name__)
def load_model() -> None:
    mlflow.set_tracking_uri(os.getenv("MLFLOW_TRACKING_URI", "sqlite:///mlflow.db"))
    client = MlflowClient()
    version = client.get_model_version_by_alias(MODEL_NAME, "champion")
    model = mlflow.sklearn.load_model(MODEL_URI)
    state.update(
        model=model,
        threshold=float(version.tags.get("decision_threshold", "0.5")),
        version=str(version.version),
    )
    MODEL_LOADED.set(1)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    initialize_portal_database()
    try:
        load_model()
    except Exception as exc:
        MODEL_LOADED.set(0)
        print(f"[warn] champion model is not loaded: {exc}")
    yield


app = FastAPI(title="Heart Disease MLOps API", version="2.0.0", lifespan=lifespan)
app.include_router(portal_router)
app.include_router(assistant_router)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        origin.strip()
        for origin in os.getenv(
            "FRONTEND_ORIGINS", "http://localhost:4200,http://127.0.0.1:4200"
        ).split(",")
        if origin.strip()
    ],
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Content-Type", "Authorization"],
)
app.mount("/metrics", make_asgi_app())


class EvaluationBatch(BaseModel):
    patients: list[Patient] = Field(..., min_length=1, max_length=10000)
    labels: list[int] = Field(..., min_length=1, max_length=10000)

    @model_validator(mode="after")
    def validate_rows(self):
        if len(self.patients) != len(self.labels):
            raise ValueError("patients and labels must have the same number of rows")
        if any(label not in (0, 1) for label in self.labels):
            raise ValueError("labels must be 0 (no disease) or 1 (disease)")
        return self


class ResearchReadinessUpdate(BaseModel):
    status: Literal["not_started", "in_progress", "blocked", "complete"] | None = None
    owner: str | None = Field(default=None, max_length=100)
    due_date: date | None = None
    notes: str | None = Field(default=None, max_length=2000)


RESEARCH_READINESS_ITEMS = [
    {
        "id": "intended-use",
        "title": "Définir l’usage prévu",
        "description": "Préciser la population, le contexte de soins, l’utilisateur, la question clinique et la décision concernée avec une équipe médicale.",
        "status": "not_started",
        "owner": None,
        "due_date": None,
        "notes": None,
        "updated_at": None,
        "updated_by": None,
        "evidence": "Document d’usage prévu validé par les responsables cliniques du projet.",
    },
    {
        "id": "clinical-governance",
        "title": "Constituer l’encadrement clinique et scientifique",
        "description": "Identifier les professionnels de santé, responsables de recherche, méthodologistes et responsables de la gouvernance du projet.",
        "status": "not_started",
        "owner": None,
        "due_date": None,
        "notes": None,
        "updated_at": None,
        "updated_by": None,
        "evidence": "Rôles, responsabilités, supervision humaine et protocole d’escalade documentés.",
    },
    {
        "id": "ethics-approvals",
        "title": "Obtenir les avis et autorisations requis",
        "description": "Faire examiner le protocole de recherche et confirmer les autorisations applicables avant tout accès à des données de patients.",
        "status": "not_started",
        "owner": None,
        "due_date": None,
        "notes": None,
        "updated_at": None,
        "updated_by": None,
        "evidence": "Avis éthique et autorisations institutionnelles et locales applicables.",
    },
    {
        "id": "data-governance",
        "title": "Établir la gouvernance et la protection des données",
        "description": "Documenter la provenance, la base de traitement, le consentement ou autre fondement applicable, la minimisation, la dé-identification, la conservation et les droits d’accès.",
        "status": "not_started",
        "owner": None,
        "due_date": None,
        "notes": None,
        "updated_at": None,
        "updated_by": None,
        "evidence": "Évaluation et documentation approuvées par les responsables compétents en protection des données.",
    },
    {
        "id": "dataset-suitability",
        "title": "Justifier la pertinence des données",
        "description": "Évaluer la qualité, la représentativité, les biais, les données manquantes et l’adéquation des données à la population et à l’usage envisagés.",
        "status": "not_started",
        "owner": None,
        "due_date": None,
        "notes": None,
        "updated_at": None,
        "updated_by": None,
        "evidence": "Protocole de données et rapport de qualité examinés par les équipes de recherche et cliniques.",
    },
    {
        "id": "independent-validation",
        "title": "Valider le modèle de manière indépendante",
        "description": "Évaluer une version figée sur des données indépendantes, pertinentes pour l’usage prévu, avec incertitude, analyses d’erreurs et sous-groupes préspécifiés.",
        "status": "not_started",
        "owner": None,
        "due_date": None,
        "notes": None,
        "updated_at": None,
        "updated_by": None,
        "evidence": "Protocole préenregistré, résultats reproductibles et revue indépendante documentés.",
    },
    {
        "id": "safety-and-human-oversight",
        "title": "Documenter la sécurité et la supervision humaine",
        "description": "Analyser les risques, les modes de défaillance, les limites, la présentation des résultats et la manière dont un professionnel peut les contester ou les ignorer.",
        "status": "not_started",
        "owner": None,
        "due_date": None,
        "notes": None,
        "updated_at": None,
        "updated_by": None,
        "evidence": "Analyse de risques et procédures de supervision revues par les responsables du projet.",
    },
    {
        "id": "regulatory-assessment",
        "title": "Évaluer les obligations réglementaires en Tunisie",
        "description": "Déterminer avec des spécialistes tunisiens compétents les exigences applicables à la recherche, aux données et à un éventuel logiciel à finalité médicale.",
        "status": "not_started",
        "owner": None,
        "due_date": None,
        "notes": None,
        "updated_at": None,
        "updated_by": None,
        "evidence": "Évaluation écrite par les conseillers réglementaires et autorités compétentes.",
    },
    {
        "id": "security-and-audit",
        "title": "Renforcer la sécurité et la traçabilité",
        "description": "Définir les rôles d’accès, la gestion des secrets, les journaux d’audit, les sauvegardes, la réponse aux incidents et les contrôles de sécurité.",
        "status": "not_started",
        "owner": None,
        "due_date": None,
        "notes": None,
        "updated_at": None,
        "updated_by": None,
        "evidence": "Revue de sécurité et procédures opérationnelles approuvées.",
    },
    {
        "id": "post-deployment-monitoring",
        "title": "Prévoir le suivi continu",
        "description": "Définir les indicateurs, les dérives, les événements à surveiller, les responsables, les seuils d’alerte et les critères d’arrêt avant tout déploiement.",
        "status": "not_started",
        "owner": None,
        "due_date": None,
        "notes": None,
        "updated_at": None,
        "updated_by": None,
        "evidence": "Plan de suivi, de réévaluation et de retrait du système documenté.",
    },
]


def readiness_database_path() -> Path:
    return Path(os.getenv("RESEARCH_READINESS_DB", "reports/research_readiness.db"))


def connect_readiness_database() -> sqlite3.Connection:
    database_path = readiness_database_path()
    database_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(database_path, timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS readiness_item_state (
            item_id TEXT PRIMARY KEY,
            status TEXT NOT NULL,
            owner TEXT,
            due_date TEXT,
            notes TEXT,
            updated_at TEXT NOT NULL,
            updated_by TEXT NOT NULL
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS readiness_audit (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_id TEXT NOT NULL,
            changed_fields TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            updated_by TEXT NOT NULL
        )
        """
    )
    return connection


@contextmanager
def readiness_connection() -> Generator[sqlite3.Connection, None, None]:
    connection = connect_readiness_database()
    try:
        with connection:
            yield connection
    finally:
        connection.close()


def patient_frame(patient: Patient) -> pd.DataFrame:
    return pd.DataFrame([patient.to_features()], columns=FEATURES)


@app.get("/health")
def health():
    loaded = state["model"] is not None
    return {
        "status": "ok" if loaded else "degraded",
        "model_loaded": loaded,
        "model_name": MODEL_NAME,
        "model_version": state["version"],
        "decision_threshold": state["threshold"],
    }


@app.get(
    "/research/readiness",
    responses={503: {"description": "Research checklist storage is unavailable."}},
)
def research_readiness(
    _user: dict = Depends(require_roles("researcher", "admin", "research-viewer", "research-editor", "research-admin")),
):
    try:
        with readiness_connection() as connection:
            stored_items = {
                row["item_id"]: dict(row)
                for row in connection.execute("SELECT * FROM readiness_item_state")
            }
            audit_events: dict[str, list[dict[str, str | list[str]]]] = {}
            for item_id in (item["id"] for item in RESEARCH_READINESS_ITEMS):
                rows = connection.execute(
                    """
                    SELECT changed_fields, updated_at, updated_by
                    FROM readiness_audit
                    WHERE item_id = ?
                    ORDER BY id DESC
                    LIMIT 5
                    """,
                    (item_id,),
                )
                audit_events[item_id] = [
                    {
                        "changed_fields": row["changed_fields"].split(","),
                        "updated_at": row["updated_at"],
                        "updated_by": row["updated_by"],
                    }
                    for row in rows
                ]
    except sqlite3.Error as exc:
        logger.exception("Could not load research readiness checklist")
        raise HTTPException(503, "Research checklist storage is unavailable") from exc

    items = []
    for item in RESEARCH_READINESS_ITEMS:
        item_state = stored_items.get(item["id"])
        if item_state:
            item = {
                **item,
                **{
                    key: item_state[key]
                    for key in ("status", "owner", "due_date", "notes", "updated_at", "updated_by")
                },
            }
        item["history"] = audit_events.get(item["id"], [])
        items.append(item)

    return {
        "project_stage": "research_planning",
        "region": "Tunisia",
        "clinical_use_enabled": False,
        "model_status": "demonstration_only_not_clinically_validated",
        "completed_items": sum(item["status"] == "complete" for item in items),
        "total_items": len(items),
        "disclaimer": (
            "Checklist de préparation à la recherche, pas un avis clinique ou "
            "réglementaire. Ne pas utiliser le modèle actuel pour diagnostiquer "
            "des patients ni orienter des soins. Confirmer les exigences avec "
            "les équipes cliniques, éthiques, de protection des données et "
            "réglementaires compétentes en Tunisie. Ne saisis aucune donnée de patient "
            "dans les notes de suivi."
        ),
        "items": items,
    }


@app.put(
    "/research/readiness/{item_id}",
    responses={
        403: {"description": "A research-editor or research-admin role is required."},
        404: {"description": "Research checklist item not found."},
        503: {"description": "Research checklist storage is unavailable."},
    },
)
def update_research_readiness_item(
    item_id: str,
    update: ResearchReadinessUpdate,
    user: dict = Depends(require_roles("researcher", "admin", "research-editor", "research-admin")),
):
    if item_id not in {item["id"] for item in RESEARCH_READINESS_ITEMS}:
        raise HTTPException(404, "Research checklist item not found")

    changed_fields = update.model_fields_set
    if not changed_fields:
        raise HTTPException(422, "Provide at least one checklist field to update")

    values = update.model_dump(exclude_unset=True)
    if "status" in values and values["status"] is None:
        raise HTTPException(422, "Status cannot be null")
    if "owner" in values:
        values["owner"] = values["owner"].strip() or None if values["owner"] else None
    if "notes" in values:
        values["notes"] = values["notes"].strip() or None if values["notes"] else None
    if "due_date" in values and values["due_date"] is not None:
        values["due_date"] = values["due_date"].isoformat()

    now = datetime.now(timezone.utc).isoformat()
    user_id = str(user.get("sub", "unknown"))

    try:
        with readiness_connection() as connection:
            existing = connection.execute(
                "SELECT * FROM readiness_item_state WHERE item_id = ?",
                (item_id,),
            ).fetchone()
            current = dict(existing) if existing else {
                "status": "not_started",
                "owner": None,
                "due_date": None,
                "notes": None,
            }
            current.update(values)
            connection.execute(
                """
                INSERT INTO readiness_item_state
                    (item_id, status, owner, due_date, notes, updated_at, updated_by)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(item_id) DO UPDATE SET
                    status = excluded.status,
                    owner = excluded.owner,
                    due_date = excluded.due_date,
                    notes = excluded.notes,
                    updated_at = excluded.updated_at,
                    updated_by = excluded.updated_by
                """,
                (
                    item_id,
                    current["status"],
                    current["owner"],
                    current["due_date"],
                    current["notes"],
                    now,
                    user_id,
                ),
            )
            connection.execute(
                """
                INSERT INTO readiness_audit (item_id, changed_fields, updated_at, updated_by)
                VALUES (?, ?, ?, ?)
                """,
                (item_id, ",".join(sorted(changed_fields)), now, user_id),
            )
    except sqlite3.Error as exc:
        logger.exception("Could not update research readiness item %s", item_id)
        raise HTTPException(503, "Research checklist storage is unavailable") from exc

    return {
        "item_id": item_id,
        **current,
        "updated_at": now,
        "updated_by": user_id,
    }




@app.post(
    "/reload",
    responses={503: {"description": "Model reload failed or the model registry is unavailable."}},
)
def reload(_user: dict = Depends(require_roles("researcher", "research-admin", "admin"))):
    try:
        load_model()
    except Exception as exc:
        MODEL_LOADED.set(0)
        ERRORS.inc()
        raise HTTPException(503, f"model reload failed: {exc}") from exc
    return {"reloaded": MODEL_NAME, "version": state["version"]}


@app.post(
    "/predict",
    responses={
        500: {"description": "Prediction failed."},
        503: {"description": "The champion model is not loaded."},
    },
)
def predict(
    patient: Patient,
    _user: dict = Depends(require_roles("researcher", "research-viewer", "research-editor", "research-admin")),
):
    if state["model"] is None:
        ERRORS.inc()
        raise HTTPException(503, "model is not loaded")
    started = time.perf_counter()
    try:
        probability = float(state["model"].predict_proba(patient_frame(patient))[0, 1])
    except Exception as exc:
        ERRORS.inc()
        raise HTTPException(500, "prediction failed") from exc
    elapsed = time.perf_counter() - started
    prediction = int(probability >= state["threshold"])
    LATENCY.observe(elapsed)
    DISEASE_PROBABILITY.observe(probability)
    PREDICTIONS.labels(label=str(prediction)).inc()
    return {
        "disease_probability": probability,
        "prediction": prediction,
        "decision": "disease" if prediction else "no_disease",
        "threshold": state["threshold"],
        "model_version": state["version"],
    }


@app.post(
    "/evaluate",
    responses={
        500: {"description": "Model evaluation failed."},
        503: {"description": "The champion model is not loaded."},
    },
)
def evaluate(
    batch: EvaluationBatch,
    _user: dict = Depends(require_roles("researcher", "research-viewer", "research-editor", "research-admin")),
):
    if state["model"] is None:
        ERRORS.inc()
        raise HTTPException(503, "model is not loaded")
    try:
        rows = pd.DataFrame([patient.to_features() for patient in batch.patients], columns=FEATURES)
        probabilities = state["model"].predict_proba(rows)[:, 1]
        predictions = (probabilities >= state["threshold"]).astype(int)
        labels = np.asarray(batch.labels)
        accuracy = float(accuracy_score(labels, predictions))
        precision = float(precision_score(labels, predictions, zero_division=0))
        recall = float(recall_score(labels, predictions, zero_division=0))
    except Exception as exc:
        ERRORS.inc()
        raise HTTPException(500, "model evaluation failed") from exc
    MODEL_ACCURACY.set(accuracy)
    MODEL_PRECISION.set(precision)
    MODEL_RECALL.set(recall)
    EVALUATED_ROWS.inc(len(batch.labels))
    return {"accuracy": accuracy, "precision": precision, "recall": recall, "rows": len(batch.labels)}
