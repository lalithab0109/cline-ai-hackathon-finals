"""Explicit 501 stubs for endpoints scheduled for later iterations.

These routes make the agreed API contract discoverable (and visible in the
auto-generated OpenAPI docs) without implementing any behaviour early:
no scanner, no database persistence, no PDF generation, no history yet.
"""

from fastapi import APIRouter, HTTPException

from ..schemas import (
    PatientCreate,
    PatientResponse,
    ScanAnalysisResponse,
    ScreeningHistoryResponse,
)

router = APIRouter(tags=["future"])

_DETAIL = (
    "This endpoint is part of the agreed API contract but is scheduled for "
    "a later development iteration."
)


def _not_implemented() -> None:
    raise HTTPException(status_code=501, detail=_DETAIL)


@router.post(
    "/patients",
    response_model=PatientResponse,
    summary="Create a fictional/demo patient (later iteration)",
)
def create_patient(patient: PatientCreate) -> None:
    _not_implemented()


@router.post(
    "/scans/analyze",
    response_model=ScanAnalysisResponse,
    summary="Analyze a test-strip image (later iteration; mock first, ML later)",
)
def analyze_scan() -> None:
    # Will accept multipart form data: image, test_type, patient_id.
    _not_implemented()


@router.get(
    "/reports/{report_id}",
    summary="Retrieve a structured screening report (later iteration)",
)
def get_report(report_id: str) -> None:
    _not_implemented()


@router.get(
    "/reports/{report_id}/pdf",
    summary="Download a report PDF (later iteration)",
)
def get_report_pdf(report_id: str) -> None:
    _not_implemented()


@router.get(
    "/patients/{patient_id}/history",
    response_model=ScreeningHistoryResponse,
    summary="Retrieve demo screening history (later iteration)",
)
def get_patient_history(patient_id: str) -> None:
    _not_implemented()
