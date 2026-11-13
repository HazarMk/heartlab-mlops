"""Patient and clinician portal primitives.

The local demo stores only synthetic appointment and consent records. Production
deployment still requires an approved database, retention policy, key management,
and operational controls before any real health information is entered.
"""
from __future__ import annotations

import os
import hashlib
import hmac
import json
import base64
import secrets
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Generator, Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field, field_validator, model_validator

from app.oidc import require_authenticated_user as validate_oidc_user


AUTH_MODE = os.getenv("AUTH_MODE", "keycloak").lower()
DATABASE_PATH = Path(os.getenv("PORTAL_DB", "reports/portal.db"))
router = APIRouter(prefix="/portal", tags=["patient and clinician portal"])
bearer = HTTPBearer(auto_error=False)


def connect() -> sqlite3.Connection:
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DATABASE_PATH, timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


@contextmanager
def database() -> Generator[sqlite3.Connection, None, None]:
    connection = connect()
    try:
        with connection:
            yield connection
    finally:
        connection.close()


def initialize_portal_database() -> None:
    with database() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS portal_providers (
                subject TEXT PRIMARY KEY,
                display_name TEXT NOT NULL,
                specialty TEXT NOT NULL DEFAULT '',
                qualifications TEXT NOT NULL DEFAULT '',
                address TEXT NOT NULL DEFAULT '',
                city TEXT NOT NULL DEFAULT '',
                area TEXT NOT NULL DEFAULT '',
                phone TEXT NOT NULL DEFAULT '',
                latitude REAL,
                longitude REAL,
                photo_data TEXT,
                active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS portal_appointments (
                id TEXT PRIMARY KEY,
                patient_subject TEXT NOT NULL,
                provider_subject TEXT NOT NULL REFERENCES portal_providers(subject),
                starts_at TEXT NOT NULL,
                contact_phone TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL CHECK(status IN ('requested','confirmed','cancelled')),
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_appointments_patient
                ON portal_appointments(patient_subject, starts_at);
            CREATE INDEX IF NOT EXISTS idx_appointments_provider
                ON portal_appointments(provider_subject, starts_at);
            CREATE TABLE IF NOT EXISTS portal_consents (
                patient_subject TEXT NOT NULL,
                purpose TEXT NOT NULL,
                granted INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT NOT NULL,
                PRIMARY KEY(patient_subject, purpose)
            );
            CREATE TABLE IF NOT EXISTS portal_audit (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                actor_subject TEXT NOT NULL,
                actor_role TEXT NOT NULL,
                action TEXT NOT NULL,
                resource TEXT NOT NULL,
                resource_id TEXT NOT NULL,
                occurred_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS portal_accounts (
                subject TEXT PRIMARY KEY, email TEXT NOT NULL UNIQUE COLLATE NOCASE,
                display_name TEXT NOT NULL, password_hash TEXT NOT NULL,
                password_salt TEXT NOT NULL, created_at TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'patient'
            );
            CREATE TABLE IF NOT EXISTS portal_sessions (
                token_hash TEXT PRIMARY KEY,
                subject TEXT NOT NULL REFERENCES portal_accounts(subject) ON DELETE CASCADE,
                expires_at TEXT NOT NULL, created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS patient_health_profiles (
                patient_subject TEXT PRIMARY KEY,
                display_name TEXT NOT NULL,
                age INTEGER,
                symptoms_json TEXT NOT NULL DEFAULT '[]',
                symptom_notes TEXT NOT NULL DEFAULT '',
                medications TEXT NOT NULL DEFAULT '',
                cnam_status TEXT NOT NULL DEFAULT 'unknown',
                cnam_pathway TEXT NOT NULL DEFAULT 'unknown',
                updated_at TEXT NOT NULL
            );
            """
        )
        account_columns = {row["name"] for row in connection.execute("PRAGMA table_info(portal_accounts)")}
        if "role" not in account_columns:
            connection.execute("ALTER TABLE portal_accounts ADD COLUMN role TEXT NOT NULL DEFAULT 'patient'")
        provider_columns = {row["name"] for row in connection.execute("PRAGMA table_info(portal_providers)")}
        for name, declaration in {
            "specialty": "TEXT NOT NULL DEFAULT ''",
            "qualifications": "TEXT NOT NULL DEFAULT ''",
            "address": "TEXT NOT NULL DEFAULT ''",
            "city": "TEXT NOT NULL DEFAULT ''",
            "area": "TEXT NOT NULL DEFAULT ''",
            "phone": "TEXT NOT NULL DEFAULT ''",
            "latitude": "REAL",
            "longitude": "REAL",
            "photo_data": "TEXT",
        }.items():
            if name not in provider_columns:
                connection.execute(f"ALTER TABLE portal_providers ADD COLUMN {name} {declaration}")
        appointment_columns = {row["name"] for row in connection.execute("PRAGMA table_info(portal_appointments)")}
        if "contact_phone" not in appointment_columns:
            connection.execute("ALTER TABLE portal_appointments ADD COLUMN contact_phone TEXT NOT NULL DEFAULT ''")
        if AUTH_MODE == "demo":
            connection.execute(
                """INSERT OR IGNORE INTO portal_providers
                   (subject, display_name, active, created_at) VALUES (?, ?, 1, ?)""",
                ("demo-doctor", "Médecin de démonstration", utc_now()),
            )


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def portal_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
) -> dict:
    if AUTH_MODE == "demo":
        role = request.headers.get("x-demo-role", "patient").lower()
        if role not in {"patient", "doctor", "admin", "researcher"}:
            raise HTTPException(403, "Unknown demo role")
        return {"sub": f"demo-{role}", "portal_role": role}
    if AUTH_MODE == "local":
        if credentials is None or credentials.scheme.lower() != "bearer":
            raise HTTPException(401, "Authentication required", headers={"WWW-Authenticate": "Bearer"})
        digest = hashlib.sha256(credentials.credentials.encode()).hexdigest()
        with database() as connection:
            row = connection.execute(
                """SELECT a.subject, a.email, a.display_name, a.role FROM portal_sessions s
                   JOIN portal_accounts a ON a.subject = s.subject
                   WHERE s.token_hash = ? AND s.expires_at > ?""", (digest, utc_now())
            ).fetchone()
        if row is None:
            raise HTTPException(401, "Session expired or invalid", headers={"WWW-Authenticate": "Bearer"})
        return {"sub": row["subject"], "email": row["email"], "name": row["display_name"], "portal_role": row["role"]}
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(401, "Authentication required", headers={"WWW-Authenticate": "Bearer"})
    return validate_oidc_user(credentials)


def require_roles(*allowed: str):
    def dependency(user: dict = Depends(portal_user)) -> dict:
        if user.get("portal_role") in allowed:
            return user
        claims = user.get("realm_access", {})
        roles = claims.get("roles", []) if isinstance(claims, dict) else []
        if isinstance(roles, list) and set(roles).intersection(allowed):
            return user
        raise HTTPException(403, "Your account is not allowed to access this resource")

    return dependency


class AccountInput(BaseModel):
    email: str = Field(min_length=5, max_length=254)
    password: str = Field(min_length=10, max_length=128)
    display_name: str = Field(min_length=2, max_length=120)


def password_digest(password: str, salt: bytes) -> str:
    return hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1).hex()


@router.post("/auth/register", status_code=201)
def register_account(account: AccountInput):
    if AUTH_MODE != "local":
        raise HTTPException(404, "Local registration is disabled")
    email = account.email.strip().lower()
    if "@" not in email or email.startswith("@") or email.endswith("@"):
        raise HTTPException(422, "Enter a valid email address")
    salt = secrets.token_bytes(16)
    subject = f"local-{uuid4()}"
    try:
        with database() as connection:
            connection.execute(
                "INSERT INTO portal_accounts (subject, email, display_name, password_hash, password_salt, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (subject, email, account.display_name.strip(), password_digest(account.password, salt), salt.hex(), utc_now()),
            )
    except sqlite3.IntegrityError as exc:
        raise HTTPException(409, "Un compte existe déjà avec cet e-mail") from exc
    return {"created": True, "email": email, "role": "patient"}


@router.post("/auth/login")
def login_account(account: AccountInput):
    if AUTH_MODE != "local":
        raise HTTPException(404, "Local account login is disabled")
    email = account.email.strip().lower()
    with database() as connection:
        row = connection.execute("SELECT * FROM portal_accounts WHERE email = ? COLLATE NOCASE", (email,)).fetchone()
        if row is None or not hmac.compare_digest(password_digest(account.password, bytes.fromhex(row["password_salt"])), row["password_hash"]):
            raise HTTPException(401, "E-mail ou mot de passe incorrect")
        token = secrets.token_urlsafe(40)
        created = datetime.now(timezone.utc)
        expires = created + timedelta(hours=12)
        connection.execute("INSERT INTO portal_sessions VALUES (?, ?, ?, ?)", (hashlib.sha256(token.encode()).hexdigest(), row["subject"], expires.isoformat(), created.isoformat()))
        return {"access_token": token, "token_type": "bearer", "expires_at": expires.isoformat(), "user": {"sub": row["subject"], "email": row["email"], "name": row["display_name"], "role": row["role"]}}


@router.post("/auth/logout")
def logout_account(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)):
    if AUTH_MODE != "local":
        raise HTTPException(404, "Local account logout is disabled")
    if credentials:
        with database() as connection:
            connection.execute("DELETE FROM portal_sessions WHERE token_hash = ?", (hashlib.sha256(credentials.credentials.encode()).hexdigest(),))
    return {"logged_out": True}


@router.get("/auth/me")
def current_account(user: dict = Depends(portal_user)):
    if AUTH_MODE != "local":
        raise HTTPException(404, "Local account profile is disabled")
    return {
        "sub": user["sub"],
        "email": user.get("email", ""),
        "name": user.get("name", "Patient"),
        "role": user.get("portal_role", "patient"),
    }


def audit(connection: sqlite3.Connection, user: dict, action: str, resource: str, resource_id: str) -> None:
    role = user.get("portal_role")
    if not role:
        access = user.get("realm_access", {})
        roles = access.get("roles", []) if isinstance(access, dict) else []
        role = next((name for name in roles if name in {"patient", "doctor", "admin", "researcher"}), "unknown")
    connection.execute(
        """INSERT INTO portal_audit
           (actor_subject, actor_role, action, resource, resource_id, occurred_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (str(user.get("sub", "unknown")), role, action, resource, resource_id, utc_now()),
    )


class AppointmentCreate(BaseModel):
    provider_subject: str = Field(min_length=1, max_length=160)
    starts_at: datetime
    contact_phone: str = Field(default="", max_length=32)

    @field_validator("starts_at")
    @classmethod
    def require_future_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("starts_at must include a timezone")
        if value <= datetime.now(timezone.utc):
            raise ValueError("Appointment time must be in the future")
        return value.astimezone(timezone.utc)

    @field_validator("contact_phone")
    @classmethod
    def clean_phone(cls, value: str) -> str:
        return value.strip()


class AppointmentUpdate(BaseModel):
    status: Literal["confirmed", "cancelled"]


class ConsentUpdate(BaseModel):
    granted: bool


class PatientHealthProfileUpdate(BaseModel):
    age: int | None = Field(default=None, ge=0, le=120)
    symptoms: list[str] = Field(default_factory=list, max_length=10)
    symptom_notes: str = Field(default="", max_length=1000)
    medications: str = Field(default="", max_length=2000)
    cnam_status: Literal["unknown", "yes", "no"] = "unknown"
    cnam_pathway: Literal["unknown", "public", "private", "reimbursement"] = "unknown"

    @field_validator("symptoms")
    @classmethod
    def allowed_symptoms(cls, values: list[str]) -> list[str]:
        allowed = {"chest_pain", "shortness_of_breath", "palpitations", "fatigue", "dizziness", "other"}
        if len(set(values)) != len(values) or not set(values).issubset(allowed):
            raise ValueError("Select valid symptom options")
        return values

    @field_validator("symptom_notes", "medications")
    @classmethod
    def trim_text(cls, value: str) -> str:
        return value.strip()


class ProviderCreate(BaseModel):
    subject: str = Field(min_length=1, max_length=160)
    display_name: str = Field(min_length=2, max_length=120)


class ProviderProfileUpdate(BaseModel):
    specialty: str = Field(default="", max_length=120)
    qualifications: str = Field(default="", max_length=3000)
    address: str = Field(default="", max_length=300)
    city: str = Field(default="", max_length=120)
    area: str = Field(default="", max_length=160)
    phone: str = Field(default="", max_length=32)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    photo_data: str | None = Field(default=None, max_length=400_000)

    @field_validator("specialty", "qualifications", "address", "city", "area", "phone")
    @classmethod
    def trim_profile_fields(cls, value: str) -> str:
        return value.strip()

    @field_validator("photo_data")
    @classmethod
    def validate_photo(cls, value: str | None) -> str | None:
        if value is None:
            return None
        header, separator, encoded = value.partition(",")
        allowed = {"data:image/jpeg;base64", "data:image/png;base64", "data:image/webp;base64"}
        if not separator or header not in allowed:
            raise ValueError("Photo must be a JPEG, PNG, or WebP image")
        try:
            content = base64.b64decode(encoded, validate=True)
        except (ValueError, base64.binascii.Error) as exc:
            raise ValueError("Photo data is invalid") from exc
        if not content or len(content) > 300_000:
            raise ValueError("Photo must be smaller than 300 KB")
        return value

    @model_validator(mode="after")
    def coordinates_are_a_pair(self):
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("Enter both map coordinates, or leave both empty")
        return self


@router.get("/providers")
def list_providers(user: dict = Depends(require_roles("patient"))):
    with database() as connection:
        rows = connection.execute(
            """SELECT subject, display_name, specialty, qualifications, address, city, area, phone, latitude, longitude,
                      photo_data
               FROM portal_providers WHERE active = 1 ORDER BY display_name"""
        ).fetchall()
        audit(connection, user, "list", "providers", "active")
    return [dict(row) for row in rows]


@router.post("/providers/me")
def register_current_provider(user: dict = Depends(require_roles("doctor"))):
    subject = str(user["sub"])
    display_name = str(user.get("name") or user.get("preferred_username") or "Clinicien")[:120]
    with database() as connection:
        connection.execute(
            """INSERT INTO portal_providers (subject, display_name, active, created_at)
               VALUES (?, ?, 1, ?) ON CONFLICT(subject) DO UPDATE SET
               display_name = excluded.display_name, active = 1""",
            (subject, display_name, utc_now()),
        )
        row = connection.execute(
            """SELECT subject, display_name, specialty, qualifications, address, city, area, phone, latitude, longitude,
                      photo_data
               FROM portal_providers WHERE subject = ?""", (subject,)
        ).fetchone()
        audit(connection, user, "register", "provider", subject)
    return {**dict(row), "active": True}


@router.put("/providers/me")
def update_current_provider_profile(
    profile: ProviderProfileUpdate,
    user: dict = Depends(require_roles("doctor")),
):
    subject = str(user["sub"])
    values = profile.model_dump()
    with database() as connection:
        existing = connection.execute(
            "SELECT subject FROM portal_providers WHERE subject = ?", (subject,)
        ).fetchone()
        if existing is None:
            raise HTTPException(404, "Clinician profile is not registered")
        connection.execute(
            """UPDATE portal_providers SET specialty = ?, qualifications = ?, address = ?, city = ?, area = ?,
               phone = ?, latitude = ?, longitude = ?, photo_data = ? WHERE subject = ?""",
            (values["specialty"], values["qualifications"], values["address"], values["city"], values["area"], values["phone"],
             values["latitude"], values["longitude"], values["photo_data"], subject),
        )
        audit(connection, user, "update", "provider_profile", subject)
    return {"saved": True, **values}


@router.post("/appointments", status_code=201)
def request_appointment(
    appointment: AppointmentCreate,
    user: dict = Depends(require_roles("patient")),
):
    appointment_id = str(uuid4())
    slot = appointment.starts_at.isoformat()
    now = utc_now()
    with database() as connection:
        provider = connection.execute(
            "SELECT subject FROM portal_providers WHERE subject = ? AND active = 1",
            (appointment.provider_subject,),
        ).fetchone()
        if provider is None:
            raise HTTPException(404, "Clinician not found")
        collision = connection.execute(
            """SELECT 1 FROM portal_appointments WHERE provider_subject = ? AND starts_at = ?
               AND status IN ('requested','confirmed')""",
            (appointment.provider_subject, slot),
        ).fetchone()
        if collision:
            raise HTTPException(409, "This time is no longer available")
        connection.execute(
            """INSERT INTO portal_appointments
               (id, patient_subject, provider_subject, starts_at, contact_phone, status, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, 'requested', ?, ?)""",
            (appointment_id, str(user["sub"]), appointment.provider_subject, slot,
             appointment.contact_phone, now, now),
        )
        audit(connection, user, "request", "appointment", appointment_id)
    return {"id": appointment_id, "starts_at": slot, "status": "requested"}


@router.get("/appointments")
def list_appointments(user: dict = Depends(require_roles("patient", "doctor"))):
    role = user.get("portal_role")
    if role is None:
        realm = user.get("realm_access", {})
        roles = realm.get("roles", []) if isinstance(realm, dict) else []
        role = "doctor" if "doctor" in roles else "patient"
    with database() as connection:
        if role == "doctor":
            rows = connection.execute(
                """SELECT a.id, a.starts_at, a.status, p.display_name AS clinician,
                          a.patient_subject, a.contact_phone AS patient_phone,
                          COALESCE(h.display_name, ac.display_name, 'Patient') AS patient_name
                   FROM portal_appointments a
                   JOIN portal_providers p ON p.subject = a.provider_subject
                   LEFT JOIN patient_health_profiles h ON h.patient_subject = a.patient_subject
                   LEFT JOIN portal_accounts ac ON ac.subject = a.patient_subject
                   WHERE a.provider_subject = ? ORDER BY a.starts_at""",
                (str(user["sub"]),),
            ).fetchall()
        else:
            rows = connection.execute(
                """SELECT a.id, a.starts_at, a.status, p.display_name AS clinician
                   FROM portal_appointments a JOIN portal_providers p ON p.subject = a.provider_subject
                   WHERE a.patient_subject = ? ORDER BY a.starts_at""",
                (str(user["sub"]),),
            ).fetchall()
        audit(connection, user, "list", "appointments", role)
    return [dict(row) for row in rows]


@router.get("/profile")
def get_patient_profile(user: dict = Depends(require_roles("patient"))):
    patient = str(user["sub"])
    with database() as connection:
        row = connection.execute(
            "SELECT * FROM patient_health_profiles WHERE patient_subject = ?", (patient,)
        ).fetchone()
        audit(connection, user, "view", "patient_profile", patient)
    if row is None:
        return {
            "display_name": str(user.get("name") or "Patient"), "age": None,
            "symptoms": [], "symptom_notes": "", "medications": "",
            "cnam_status": "unknown", "cnam_pathway": "unknown", "updated_at": None,
        }
    result = dict(row)
    result["symptoms"] = json.loads(result.pop("symptoms_json"))
    return result


@router.put("/profile")
def update_patient_profile(
    profile: PatientHealthProfileUpdate,
    user: dict = Depends(require_roles("patient")),
):
    patient = str(user["sub"])
    now = utc_now()
    values = profile.model_dump()
    with database() as connection:
        connection.execute(
            """INSERT INTO patient_health_profiles
               (patient_subject, display_name, age, symptoms_json, symptom_notes, medications,
                cnam_status, cnam_pathway, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(patient_subject) DO UPDATE SET
                 display_name = excluded.display_name, age = excluded.age,
                 symptoms_json = excluded.symptoms_json, symptom_notes = excluded.symptom_notes,
                 medications = excluded.medications, cnam_status = excluded.cnam_status,
                 cnam_pathway = excluded.cnam_pathway, updated_at = excluded.updated_at""",
            (patient, str(user.get("name") or "Patient"), values["age"],
             json.dumps(values["symptoms"], ensure_ascii=False), values["symptom_notes"],
             values["medications"], values["cnam_status"], values["cnam_pathway"], now),
        )
        audit(connection, user, "update", "patient_profile", patient)
    return {"saved": True, "updated_at": now}


@router.get("/appointments/{appointment_id}/patient-profile")
def get_appointment_patient_profile(
    appointment_id: str,
    user: dict = Depends(require_roles("doctor")),
):
    with database() as connection:
        appointment = connection.execute(
            "SELECT patient_subject FROM portal_appointments WHERE id = ? AND provider_subject = ?",
            (appointment_id, str(user["sub"])),
        ).fetchone()
        if appointment is None:
            raise HTTPException(404, "Appointment not found")
        patient = appointment["patient_subject"]
        row = connection.execute(
            "SELECT * FROM patient_health_profiles WHERE patient_subject = ?", (patient,)
        ).fetchone()
        audit(connection, user, "view", "patient_profile", patient)
    if row is None:
        return {"display_name": "Patient", "age": None, "symptoms": [], "symptom_notes": "",
                "medications": "", "cnam_status": "unknown", "cnam_pathway": "unknown", "updated_at": None}
    result = dict(row)
    result["symptoms"] = json.loads(result.pop("symptoms_json"))
    return result


@router.patch("/appointments/{appointment_id}")
def update_appointment(
    appointment_id: str,
    update: AppointmentUpdate,
    user: dict = Depends(require_roles("doctor")),
):
    now = utc_now()
    with database() as connection:
        result = connection.execute(
            """UPDATE portal_appointments SET status = ?, updated_at = ?
               WHERE id = ? AND provider_subject = ? AND status = 'requested'""",
            (update.status, now, appointment_id, str(user["sub"])),
        )
        if not result.rowcount:
            raise HTTPException(404, "Appointment not found or no longer pending")
        audit(connection, user, update.status, "appointment", appointment_id)
    return {"id": appointment_id, "status": update.status, "updated_at": now}


@router.delete("/appointments/{appointment_id}")
def cancel_appointment(
    appointment_id: str,
    user: dict = Depends(require_roles("patient")),
):
    now = utc_now()
    with database() as connection:
        result = connection.execute(
            """UPDATE portal_appointments SET status = 'cancelled', updated_at = ?
               WHERE id = ? AND patient_subject = ? AND status IN ('requested','confirmed')""",
            (now, appointment_id, str(user["sub"])),
        )
        if not result.rowcount:
            raise HTTPException(404, "Appointment not found or cannot be cancelled")
        audit(connection, user, "cancel", "appointment", appointment_id)
    return {"id": appointment_id, "status": "cancelled"}


CONSENT_PURPOSES = {
    "appointment_reminders": "Autoriser les rappels de rendez-vous lorsque ce service sera disponible",
    "document_sharing": "Autoriser le partage de documents lorsque ce service sera disponible",
    "research_contact": "Être contacté au sujet d’une recherche (sans autoriser l’usage des données)",
}


@router.get("/consents")
def list_consents(user: dict = Depends(require_roles("patient"))):
    patient = str(user["sub"])
    now = utc_now()
    with database() as connection:
        for purpose in CONSENT_PURPOSES:
            connection.execute(
                "INSERT OR IGNORE INTO portal_consents VALUES (?, ?, 0, ?)",
                (patient, purpose, now),
            )
        rows = connection.execute(
            "SELECT purpose, granted, updated_at FROM portal_consents WHERE patient_subject = ? ORDER BY purpose",
            (patient,),
        ).fetchall()
        audit(connection, user, "view", "consents", patient)
    return [
        {**dict(row), "granted": bool(row["granted"]), "description": CONSENT_PURPOSES[row["purpose"]]}
        for row in rows
    ]


@router.put("/consents/{purpose}")
def update_consent(
    purpose: str,
    update: ConsentUpdate,
    user: dict = Depends(require_roles("patient")),
):
    if purpose not in CONSENT_PURPOSES:
        raise HTTPException(404, "Consent purpose not found")
    patient = str(user["sub"])
    now = utc_now()
    with database() as connection:
        connection.execute(
            """INSERT INTO portal_consents (patient_subject, purpose, granted, updated_at)
               VALUES (?, ?, ?, ?) ON CONFLICT(patient_subject, purpose)
               DO UPDATE SET granted = excluded.granted, updated_at = excluded.updated_at""",
            (patient, purpose, int(update.granted), now),
        )
        audit(connection, user, "grant" if update.granted else "withdraw", "consent", purpose)
    return {"purpose": purpose, "granted": update.granted, "updated_at": now}


@router.get("/audit")
def list_audit(limit: int = 100, user: dict = Depends(require_roles("admin"))):
    limit = min(max(limit, 1), 500)
    with database() as connection:
        rows = connection.execute(
            "SELECT actor_subject, actor_role, action, resource, resource_id, occurred_at "
            "FROM portal_audit ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [dict(row) for row in rows]


@router.post("/providers", status_code=201)
def create_provider(provider: ProviderCreate, user: dict = Depends(require_roles("admin"))):
    with database() as connection:
        try:
            connection.execute(
                "INSERT INTO portal_providers (subject, display_name, active, created_at) VALUES (?, ?, 1, ?)",
                (provider.subject, provider.display_name.strip(), utc_now()),
            )
        except sqlite3.IntegrityError as exc:
            raise HTTPException(409, "Clinician already exists") from exc
        audit(connection, user, "create", "provider", provider.subject)
    return {"subject": provider.subject, "display_name": provider.display_name.strip(), "active": True}
