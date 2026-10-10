"""Patient endpoints: create fictional/demo patients and list their history."""

from fastapi import APIRouter, HTTPException

from .. import database
from ..config import SIMULATION_DISCLAIMER
from ..schemas import (
    PatientCreate,
    PatientResponse,
    ScreeningHistoryEntry,
    ScreeningHistoryResponse,
)

router = APIRouter(tags=["patients"])


@router.post("/patients", response_model=PatientResponse, status_code=201)
def create_patient(patient: PatientCreate) -> PatientResponse:
    """Create and persist a fictional/demo patient record."""

    row = database.create_patient(
        display_name=patient.display_name,
        age=patient.age,
        sex=patient.sex,
    )
    return PatientResponse(
        patient_id=row["id"],
        display_name=row["display_name"],
        age=row["age"],
        sex=row["sex"],
        created_at=row["created_at"],
    )


@router.get(
    "/patients/{patient_id}/history",
    response_model=ScreeningHistoryResponse,
)
def get_patient_history(patient_id: str) -> ScreeningHistoryResponse:
    """Return previous screening sessions for a demo patient."""

    if database.get_patient(patient_id) is None:
        raise HTTPException(status_code=404, detail="Patient not found.")

    entries = [
        ScreeningHistoryEntry(
            scan_id=row["session_id"],
            report_id=None,
            test_type=row["test_type"],
            status=row["status"],
            source=row["source"],
            is_simulated=row["is_simulated"] if row["is_simulated"] is not None else True,
            measurement=row["measurement"],
            classification=row["classification"],
            created_at=row["created_at"],
        )
        for row in database.get_sessions_with_analysis(patient_id)
    ]
    return ScreeningHistoryResponse(
        patient_id=patient_id,
        entries=entries,
        disclaimer=SIMULATION_DISCLAIMER,
    )
