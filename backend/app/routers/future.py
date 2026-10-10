"""Explicit 501 stubs for endpoints scheduled for later iterations.

These routes make the agreed API contract discoverable (and visible in the
auto-generated OpenAPI docs) without implementing any behaviour early.
Report retrieval and PDF generation arrive in the next iteration.
"""

from fastapi import APIRouter, HTTPException

router = APIRouter(tags=["future"])

_DETAIL = (
    "This endpoint is part of the agreed API contract but is scheduled for "
    "a later development iteration."
)


def _not_implemented() -> None:
    raise HTTPException(status_code=501, detail=_DETAIL)


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
