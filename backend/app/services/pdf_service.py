"""PDF report generation with ReportLab (in-memory, A4).

Renders the persisted ScreeningReportResponse into a professional,
patient-readable document. Content rules (per roadmap section 10):
- Prominent SIMULATED — NOT FOR MEDICAL USE notice.
- Failed scans show the failure reason instead of a measurement.
- No fabricated reference ranges, diagnoses, or treatment advice.
"""

from __future__ import annotations

from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    HRFlowable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from ..config import SIMULATION_DISCLAIMER
from ..schemas import ScreeningReportResponse

TEAL = colors.HexColor("#0D9488")
TEAL_DARK = colors.HexColor("#0F766E")
DARK = colors.HexColor("#0F172A")
SLATE = colors.HexColor("#475569")
AMBER_BG = colors.HexColor("#FEF3C7")
AMBER_TEXT = colors.HexColor("#92400E")
LIGHT_BG = colors.HexColor("#F1F5F9")
ROSE_BG = colors.HexColor("#FFF1F2")
ROSE_TEXT = colors.HexColor("#9F1239")

_TITLE = ParagraphStyle("title", fontName="Helvetica-Bold", fontSize=20, textColor=colors.white)
_SUBTITLE = ParagraphStyle("subtitle", fontName="Helvetica", fontSize=9.5, textColor=colors.HexColor("#CCFBF1"))
_SECTION = ParagraphStyle("section", fontName="Helvetica-Bold", fontSize=12, textColor=TEAL_DARK, spaceBefore=14, spaceAfter=4)
_BODY = ParagraphStyle("body", fontName="Helvetica", fontSize=10, textColor=DARK, leading=14)
_SMALL = ParagraphStyle("small", fontName="Helvetica", fontSize=8.5, textColor=SLATE, leading=12)
_VALUE = ParagraphStyle("value", fontName="Helvetica-Bold", fontSize=24, textColor=DARK)
_DISCLAIMER = ParagraphStyle("disclaimer", fontName="Helvetica-Bold", fontSize=9.5, textColor=AMBER_TEXT, leading=13)


def _p(text: str, style: ParagraphStyle = _BODY) -> Paragraph:
    return Paragraph(escape(text), style)


def _label_value_rows(pairs: list[tuple[str, str]]) -> Table:
    table = Table(
        [[_p(label, _SMALL), _p(value)] for label, value in pairs],
        colWidths=[45 * mm, 129 * mm],
    )
    table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.white, LIGHT_BG]),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    return table


def _banner(text: str, bg: colors.Color, style: ParagraphStyle) -> Table:
    table = Table([[Paragraph(escape(text), style)]], colWidths=[174 * mm])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), bg),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
            ]
        )
    )
    return table


def _bullets(items: list[str]) -> list:
    return [
        Paragraph(f"&bull; {escape(item)}", _SMALL) for item in items
    ]



def build_report_pdf(report: ScreeningReportResponse) -> bytes:
    """Render a screening report PDF in memory and return its bytes."""

    analysis = report.analysis
    story: list = []

    # 1. Branding header
    header = Table(
        [[
            Paragraph("Aarogya Bindu", _TITLE),
            Paragraph(
                "AI-assisted preliminary screening — technology demonstration",
                _SUBTITLE,
            ),
        ]],
        colWidths=[90 * mm, 84 * mm],
    )
    header.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), TEAL),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 12),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
                ("LEFTPADDING", (0, 0), (-1, -1), 12),
                ("RIGHTPADDING", (0, 0), (-1, -1), 12),
            ]
        )
    )
    story.append(header)
    story.append(Spacer(1, 6))
    story.append(
        _banner(
            f"{SIMULATION_DISCLAIMER}. This report is generated from synthetic "
            "demonstration data. It is not a medical diagnosis and cannot "
            "confirm or rule out any condition.",
            AMBER_BG,
            _DISCLAIMER,
        )
    )

    # 2. Session + 3. fictional patient + 4. test
    story.append(Paragraph("Screening session", _SECTION))
    patient_label = report.patient.display_name or "Anonymous demo profile"
    story.append(
        _label_value_rows(
            [
                ("Report ID", report.report_id),
                ("Date (UTC)", report.created_at),
                ("Patient", f"{patient_label} (fictional demo profile)"),
                ("Age", str(report.patient.age)),
                ("Sex", report.patient.sex or "Not provided"),
                ("Test", f"{report.test.name} — {report.test.sample_type} sample"),
                ("Scan status", analysis.status.value.replace("_", " ")),
            ]
        )
    )

    # 5./6. Measurement + classification, or the failure reason
    story.append(Paragraph("Result", _SECTION))
    if (
        analysis.status.value == "success"
        and analysis.measurement
        and analysis.classification
    ):
        story.append(
            Paragraph(
                f"{escape(str(analysis.measurement.value))} "
                f"<font size=12 color=\"#475569\">{escape(analysis.measurement.unit)}</font>",
                _VALUE,
            )
        )
        story.append(
            _p(
                "Illustrative screening category: "
                + analysis.classification.label.replace("_", " ")
            )
        )
        story.append(
            _p(
                f"Estimation method: {analysis.measurement.method} · "
                f"Classifier: {analysis.classification.method} (both simulated)",
                _SMALL,
            )
        )
    else:
        reasons = "; ".join(analysis.quality.issues) or "Scan failed quality checks."
        story.append(
            _banner(
                "No result was generated for this scan. Reason: " + reasons,
                ROSE_BG,
                ParagraphStyle("fail", parent=_DISCLAIMER, textColor=ROSE_TEXT),
            )
        )

    # 7. Image quality
    story.append(Paragraph("Image quality", _SECTION))
    quality = analysis.quality
    quality_pairs = [("Quality gate", "Passed" if quality.passed else "Failed")]
    if quality.blur_score is not None:
        quality_pairs.append(("Blur score", str(quality.blur_score)))
    if quality.calibration_detected is not None:
        quality_pairs.append(
            ("Calibration detected", "Yes" if quality.calibration_detected else "No")
        )
    if quality.calibration_error is not None:
        quality_pairs.append(("Calibration error", str(quality.calibration_error)))
    story.append(_label_value_rows(quality_pairs))
    if analysis.image_analysis is None:
        story.append(
            _p(
                "Mock inference is active: no color features were extracted "
                "from the uploaded image.",
                _SMALL,
            )
        )

    # 8. Model provenance
    story.append(Paragraph("Model provenance", _SECTION))
    simulated_flags = {
        part.is_simulated
        for part in (analysis.measurement, analysis.classification)
        if part is not None
    }
    simulated_text = (
        "Yes"
        if simulated_flags == {True}
        else ("No" if simulated_flags == {False} else "n/a")
    )
    story.append(
        _label_value_rows(
            [
                ("Model identifier", analysis.model.identifier),
                ("Model version", analysis.model.version),
                ("Data source", analysis.source.value),
                ("Simulated data", simulated_text),
                (
                    "Clinically validated",
                    "Yes" if analysis.clinically_validated else "No",
                ),
            ]
        )
    )

    # 9. Explanation and limitations
    story.append(Paragraph("Explanation", _SECTION))
    story.append(_p(analysis.explanation.summary))
    if analysis.explanation.inputs_used:
        story.append(Spacer(1, 2))
        story.append(
            _p("Inputs used: " + ", ".join(analysis.explanation.inputs_used), _SMALL)
        )
    if analysis.explanation.limitations:
        story.append(Spacer(1, 4))
        story.append(Paragraph("Limitations", _SMALL))
        story.extend(_bullets(analysis.explanation.limitations))
    if analysis.explanation.warnings:
        story.append(Spacer(1, 4))
        story.append(Paragraph("Warnings", _SMALL))
        story.extend(_bullets(analysis.explanation.warnings))

    # 10. Footer disclaimer
    story.append(Spacer(1, 10))
    story.append(HRFlowable(width="100%", color=TEAL, thickness=1))
    story.append(Spacer(1, 4))
    story.append(
        _p(
            f"{SIMULATION_DISCLAIMER}. Aarogya Bindu demonstrates a screening "
            "workflow using synthetic data. It does not provide medical "
            "diagnoses, reference ranges, or treatment advice. Consult a "
            "qualified clinician for any health concern.",
            _SMALL,
        )
    )

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
        title=f"Aarogya Bindu Screening Report {report.report_id}",
        author="Aarogya Bindu (demonstration)",
    )
    doc.build(story)
    return buffer.getvalue()
