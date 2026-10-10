"""De-identified report summary used to ground the "Aarogya AI" assistant.

Built from the SAME `ScreeningReportResponse` the report page and PDF use
(`routers.reports._load_report`), so it never diverges from what the patient
sees. An explicit allow-list is used (not a deny-list): any field added to the
report later is excluded unless it is added here on purpose.

Excluded on purpose: patient name, patient ID, report/scan/session IDs, age,
sex, timestamps, uploaded image / annotated image URL, raw RGB/Lab values.
"""

from __future__ import annotations

from ..schemas import (
    AssistantContextResponse,
    AssistantQuality,
    ScreeningReportResponse,
)


def build_assistant_context(report: ScreeningReportResponse) -> AssistantContextResponse:
    analysis = report.analysis
    roi = analysis.image_analysis.roi_detection if analysis.image_analysis else None
    explanation = analysis.explanation.model_copy(deep=True)
    # Mock fixtures list "age"/"sex" as classifier inputs; the VALUES are never
    # included, only the fact that these input kinds exist.
    return AssistantContextResponse(
        test_type=analysis.test_type,
        test_name=report.test.name,
        sample_type=report.test.sample_type,
        status=analysis.status,
        source=analysis.source,
        clinically_validated=False,  # never true for this demonstration
        measurement=analysis.measurement,
        classification=analysis.classification,
        quality=AssistantQuality(
            passed=analysis.quality.passed,
            blur_score=analysis.quality.blur_score,
            issues=list(analysis.quality.issues),
            metrics=dict(analysis.quality.metrics),
        ),
        roi_detection=roi,
        model=analysis.model,
        explanation=explanation,
        interpretation_note=report.test.interpretation_note,
        disclaimer=report.disclaimer,
    )
