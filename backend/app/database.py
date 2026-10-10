"""SQLite persistence for Aarogya Bindu (standard-library sqlite3).

Three tables, mirroring the agreed data model:

- patients:            fictional/demo patient records (minimal data only)
- screening_sessions:  one row per scan attempt (success or failed quality)
- analysis_results:    structured analysis payload + model provenance,
                       stored as JSON blobs matching the API contract

Raw uploaded images are NOT stored; only the structured analysis outcome.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Iterator, Optional

from .config import DATABASE_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS patients (
    id           TEXT PRIMARY KEY,
    display_name TEXT,
    age          INTEGER NOT NULL,
    sex          TEXT,
    created_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS screening_sessions (
    id         TEXT PRIMARY KEY,
    patient_id TEXT NOT NULL REFERENCES patients(id),
    test_type  TEXT NOT NULL,
    status     TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS analysis_results (
    session_id           TEXT PRIMARY KEY REFERENCES screening_sessions(id),
    measurement_json     TEXT,
    classification_json  TEXT,
    quality_json         TEXT NOT NULL,
    image_analysis_json  TEXT,
    explanation_json     TEXT NOT NULL,
    model_identifier     TEXT NOT NULL,
    model_version        TEXT NOT NULL,
    source               TEXT NOT NULL,
    is_simulated         INTEGER NOT NULL,
    clinically_validated INTEGER NOT NULL,
    created_at           TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_sessions_patient
    ON screening_sessions(patient_id);
"""


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id() -> str:
    return str(uuid.uuid4())


@contextmanager
def _connect() -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    """Create tables if they do not exist (called at app startup)."""
    with _connect() as conn:
        conn.executescript(SCHEMA)


def create_patient(
    display_name: Optional[str], age: int, sex: Optional[str]
) -> dict[str, Any]:
    row = {
        "id": _new_id(),
        "display_name": display_name,
        "age": age,
        "sex": sex,
        "created_at": _utcnow(),
    }
    with _connect() as conn:
        conn.execute(
            "INSERT INTO patients (id, display_name, age, sex, created_at)"
            " VALUES (:id, :display_name, :age, :sex, :created_at)",
            row,
        )
    return row


def get_patient(patient_id: str) -> Optional[dict[str, Any]]:
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM patients WHERE id = ?", (patient_id,)
        ).fetchone()
    return dict(row) if row else None


def create_session(patient_id: str, test_type: str, status: str) -> dict[str, Any]:
    row = {
        "id": _new_id(),
        "patient_id": patient_id,
        "test_type": test_type,
        "status": status,
        "created_at": _utcnow(),
    }
    with _connect() as conn:
        conn.execute(
            "INSERT INTO screening_sessions"
            " (id, patient_id, test_type, status, created_at)"
            " VALUES (:id, :patient_id, :test_type, :status, :created_at)",
            row,
        )
    return row



def save_analysis(session_id: str, analysis: Any) -> None:
    """Persist a ScanAnalysisResponse (or its dict form) for a session."""

    payload = analysis.model_dump() if hasattr(analysis, "model_dump") else analysis

    def dump(key: str) -> Optional[str]:
        value = payload.get(key)
        return json.dumps(value) if value is not None else None

    model = payload["model"]
    measurement = payload.get("measurement")
    classification = payload.get("classification")
    is_simulated = bool(
        (measurement or {}).get("is_simulated", True)
        and (classification or {}).get("is_simulated", True)
    )

    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO analysis_results (
                session_id, measurement_json, classification_json,
                quality_json, image_analysis_json, explanation_json,
                model_identifier, model_version, source,
                is_simulated, clinically_validated, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                session_id,
                dump("measurement"),
                dump("classification"),
                dump("quality") or "{}",
                dump("image_analysis"),
                dump("explanation") or "{}",
                model["identifier"],
                model["version"],
                payload["source"],
                int(is_simulated),
                int(bool(payload.get("clinically_validated", False))),
                _utcnow(),
            ),
        )


def get_report(report_id: str) -> Optional[dict[str, Any]]:
    """Fetch one screening session joined with its patient and analysis.

    The report ID is the screening-session ID. Returns None when unknown.
    """

    with _connect() as conn:
        row = conn.execute(
            """
            SELECT s.id AS session_id, s.test_type, s.status,
                   s.created_at AS session_created_at,
                   p.id AS patient_id, p.display_name, p.age, p.sex,
                   a.measurement_json, a.classification_json, a.quality_json,
                   a.image_analysis_json, a.explanation_json,
                   a.model_identifier, a.model_version, a.source,
                   a.is_simulated, a.clinically_validated
            FROM screening_sessions s
            JOIN patients p ON p.id = s.patient_id
            LEFT JOIN analysis_results a ON a.session_id = s.id
            WHERE s.id = ?
            """,
            (report_id,),
        ).fetchone()

    if row is None:
        return None

    record = dict(row)
    for key in (
        "measurement_json",
        "classification_json",
        "quality_json",
        "image_analysis_json",
        "explanation_json",
    ):
        raw = record.pop(key)
        record[key.removesuffix("_json")] = json.loads(raw) if raw else None
    for flag in ("is_simulated", "clinically_validated"):
        if record[flag] is not None:
            record[flag] = bool(record[flag])
    return record


def get_sessions_with_analysis(patient_id: str) -> list[dict[str, Any]]:
    """Return a patient's screening sessions joined with their analysis."""

    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT s.id AS session_id, s.test_type, s.status, s.created_at,
                   a.measurement_json, a.classification_json, a.source,
                   a.is_simulated
            FROM screening_sessions s
            LEFT JOIN analysis_results a ON a.session_id = s.id
            WHERE s.patient_id = ?
            ORDER BY s.created_at DESC
            """,
            (patient_id,),
        ).fetchall()

    history = []
    for row in rows:
        entry = dict(row)
        for key in ("measurement_json", "classification_json"):
            raw = entry.pop(key)
            entry[key.removesuffix("_json")] = json.loads(raw) if raw else None
        if entry["is_simulated"] is not None:
            entry["is_simulated"] = bool(entry["is_simulated"])
        history.append(entry)
    return history
