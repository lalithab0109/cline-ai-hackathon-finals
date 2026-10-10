"""Report endpoints: structured report retrieval and PDF download.

A report is a rendered view over a persisted screening session + analysis
(report ID == session ID). No new persistence is introduced here.
"""

from fastapi import APIRouter, HTTPException, Response

from .. import database
from ..config import SIMULATION_DISCLAIMER
from ..schemas import (
    AssistantContextResponse,
    ModelDescriptor,
    ReportPatient,
    ScanAnalysisResponse,
    ScreeningReportResponse,
)
from ..services import pdf_service
from ..services.assistant_context import build_assistant_context
from .tests import SUPPORTED_TESTS

router = APIRouter(tags=["reports"])

_TESTS_BY_ID = {test.id.value: test for test in SUPPORTED_TESTS}


def _load_report(report_id: str) -> ScreeningReportResponse:
    record = database.get_report(report_id)
    if record is None or record.get("quality") is None:
        raise HTTPException(status_code=404, detail="Report not found.")

    test = _TESTS_BY_ID[record["test_type"]]
    analysis = ScanAnalysisResponse(
        scan_id=record["session_id"],
        report_id=record["session_id"],
        test_type=record["test_type"],
        status=record["status"],
        source=record["source"],
        clinically_validated=bool(record["clinically_validated"]),
        model=ModelDescriptor(
            identifier=record["model_identifier"],
            version=record["model_version"],
            kind="mock" if record["source"] == "mock" else "svr",
        ),
        quality=record["quality"],
        image_analysis=record["image_analysis"],
        measurement=record["measurement"],
        classification=record["classification"],
        explanation=record["explanation"],
        disclaimer=SIMULATION_DISCLAIMER,
    )
    return ScreeningReportResponse(
        report_id=record["session_id"],
        scan_id=record["session_id"],
        created_at=record["session_created_at"],
        patient=ReportPatient(
            patient_id=record["patient_id"],
            display_name=record["display_name"],
            age=record["age"],
            sex=record["sex"],
        ),
        test=test,
        analysis=analysis,
        disclaimer=SIMULATION_DISCLAIMER,
    )


@router.get("/reports/{report_id}", response_model=ScreeningReportResponse)
def get_report(report_id: str) -> ScreeningReportResponse:
    """Retrieve a structured screening report (404 when unknown)."""

    return _load_report(report_id)


@router.get(
    "/reports/{report_id}/assistant-context",
    response_model=AssistantContextResponse,
    summary="De-identified report summary for the Aarogya AI assistant",
)
def get_assistant_context(report_id: str) -> AssistantContextResponse:
    """Minimal, de-identified grounding data for one saved report (404 when unknown).

    No authentication exists in this demo: access is equivalent to
    GET /api/reports/{id}. Intended for fictional demonstration records only.
    """

    return build_assistant_context(_load_report(report_id))


@router.get(
    "/reports/{report_id}/pdf",
    summary="Download the report as an A4 PDF",
    responses={200: {"content": {"application/pdf": {}}}},
)
def get_report_pdf(report_id: str) -> Response:
    """Generate the report PDF in memory and return it as a download."""

    report = _load_report(report_id)
    pdf_bytes = pdf_service.build_report_pdf(report)
    filename = f"aarogya-bindu-report-{report_id[:8]}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
