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
    KeepTogether,
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

_TITLE = ParagraphStyle("title", fontName="Helvetica-Bold", fontSize=20, leading=24, textColor=colors.white)
_SUBTITLE = ParagraphStyle(
    "subtitle", fontName="Helvetica", fontSize=9.5, leading=12, textColor=colors.HexColor("#CCFBF1")
)
# keepWithNext: a section heading never ends up alone at the bottom of a page.
_SECTION = ParagraphStyle(
    "section", fontName="Helvetica-Bold", fontSize=12, leading=15, textColor=TEAL_DARK,
    spaceBefore=14, spaceAfter=5, keepWithNext=1,
)
_BODY = ParagraphStyle("body", fontName="Helvetica", fontSize=10, textColor=DARK, leading=14)
_SMALL = ParagraphStyle("small", fontName="Helvetica", fontSize=8.5, textColor=SLATE, leading=12)
# Every style sets `leading` (line height) >= fontSize * 1.2. ReportLab's default
# leading is 12pt whatever the font size, so a 24pt value used to reserve only
# 12pt and its glyphs were drawn over the next paragraph.
_VALUE = ParagraphStyle(
    "value", fontName="Helvetica-Bold", fontSize=26, leading=32, textColor=DARK, spaceAfter=2
)
_RESULT_NOTE = ParagraphStyle("result_note", parent=_SMALL, spaceAfter=8)
_CATEGORY_LABEL = ParagraphStyle(
    "category_label", fontName="Helvetica-Bold", fontSize=8.5, leading=12, textColor=SLATE, spaceAfter=1
)
# splitLongWords (ReportLab default) breaks unspaced labels longer than the line.
_CATEGORY = ParagraphStyle(
    "category", fontName="Helvetica-Bold", fontSize=11, leading=15, textColor=DARK, spaceAfter=6,
    splitLongWords=1,
)
_DETAIL = ParagraphStyle("detail", parent=_SMALL, spaceAfter=3)
_DISCLAIMER = ParagraphStyle("disclaimer", fontName="Helvetica-Bold", fontSize=9.5, textColor=AMBER_TEXT, leading=13)
_FOOTER_FONT = ("Helvetica", 7.5)


# (key in QualityResult.metrics, label). sharpness is shown as "Blur score".
_QUALITY_METRIC_LABELS = [
    ("paper_brightness", "Paper brightness (0-255)"),
    ("roi_clipped_fraction", "Clipped pixel fraction"),
    ("roi_color_std", "Reaction-area color spread"),
    ("roi_pixel_count", "Reaction-area pixels"),
]


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



def _result_block(analysis) -> list:
    """Measurement and category as stacked flowables (heights computed by Platypus).

    Each element is its own Paragraph with explicit leading and spacing, so the
    large value, the simulated notice, the category and the method notes can
    never overlap, and long labels/descriptions wrap within the frame. The block
    is kept together so the value is never separated from its notices by a page
    break.
    """
    m = analysis.measurement
    block: list = [
        Paragraph(
            f"{escape(str(m.value))}"
            f"<font name=\"Helvetica\" size=13 color=\"#475569\">&nbsp;{escape(m.unit)}</font>",
            _VALUE,
        ),
        _p("Simulated value (synthetic data) — not a laboratory measurement.", _RESULT_NOTE),
    ]
    classification = analysis.classification
    if classification and classification.model and classification.model.kind == "svm":
        # Trained demonstration SVM: artificial bands, labels shown verbatim.
        # The visible text keeps the exact phrase "Demonstration category (artificial): <label>".
        block += [
            Paragraph(
                "Demonstration category (artificial):<br/>"
                f"<font name=\"Helvetica-Bold\" size=11 color=\"#0F172A\">{escape(classification.label)}</font>",
                ParagraphStyle("cat_combined", parent=_CATEGORY_LABEL, leading=15, spaceAfter=6, splitLongWords=1),
            ),
            _p(f"Estimation method: {m.method}", _DETAIL),
            _p(
                f"Classifier: Demonstration SVM ({classification.method}), both simulated",
                _DETAIL,
            ),
            _p(
                "Artificial category based on synthetic training labels. "
                "Not a medical severity assessment.",
                _DETAIL,
            ),
        ]
    elif classification:
        # Mock fixture (glucose / urine albumin).
        block += [
            Paragraph(
                "Illustrative screening category (mock fixture):<br/>"
                f"<font name=\"Helvetica-Bold\" size=11 color=\"#0F172A\">"
                f"{escape(classification.label.replace('_', ' '))}</font>",
                ParagraphStyle("mock_combined", parent=_CATEGORY_LABEL, leading=15, spaceAfter=6, splitLongWords=1),
            ),
            _p(f"Estimation method: {m.method}", _DETAIL),
            _p(f"Classifier: {classification.method} (both simulated)", _DETAIL),
        ]
    else:
        block += [
            _p("No category is assigned to this scan.", _CATEGORY),
            _p(f"Estimation method: {m.method} (simulated)", _DETAIL),
        ]
    return [KeepTogether(block)]


def _page_footer(canvas, doc) -> None:
    """Footer on every page: disclaimer + page number, drawn inside the bottom margin."""
    canvas.saveState()
    canvas.setFont(*_FOOTER_FONT)
    canvas.setFillColor(SLATE)
    y = 9 * mm
    canvas.drawString(doc.leftMargin, y, f"Aarogya Bindu — {SIMULATION_DISCLAIMER}")
    canvas.drawRightString(doc.pagesize[0] - doc.rightMargin, y, f"Page {doc.page}")
    canvas.restoreState()


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
                # .value: printing the Enum itself rendered "SampleType.BLOOD".
                ("Test", f"{report.test.name} — {report.test.sample_type.value} sample"),
                ("Scan status", analysis.status.value.replace("_", " ")),
            ]
        )
    )

    # 5./6. Measurement + classification, or the failure reason
    story.append(Paragraph("Result", _SECTION))
    if analysis.status.value == "success" and analysis.measurement:
        story.extend(_result_block(analysis))
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
    for key, label in _QUALITY_METRIC_LABELS:
        if key in quality.metrics:
            quality_pairs.append((label, str(quality.metrics[key])))
    roi = analysis.image_analysis.roi_detection if analysis.image_analysis else None
    if roi:
        quality_pairs.append(
            ("Reaction area", f"found via {roi.method} (confidence {roi.confidence})")
        )
        if roi.corners_xy:
            corners = "; ".join(f"({x:g}, {y:g})" for x, y in roi.corners_xy)
            quality_pairs.append(("Area corners (px)", corners))
    story.append(_label_value_rows(quality_pairs))
    if analysis.status.value != "success":
        story.append(_p("No color analysis was completed for this scan.", _SMALL))
    elif analysis.source.value == "mock":
        story.append(
            _p(
                "Mock inference is active: no color features were extracted "
                "from the uploaded image.",
                _SMALL,
            )
        )
    else:
        story.append(
            _p(
                "Color features were extracted from the reaction area by the "
                "image-analysis pipeline using white-paper normalization "
                "(not colorimetric calibration).",
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
    provenance = [
        ("Model identifier", analysis.model.identifier),
        ("Model version", analysis.model.version),
    ]
    cls_model = analysis.classification.model if analysis.classification else None
    if cls_model:
        provenance += [
            ("Classifier identifier", cls_model.identifier),
            ("Classifier version", cls_model.version),
        ]
    provenance += [
        ("Data source", analysis.source.value),
        ("Simulated data", simulated_text),
        (
            "Clinically validated",
            "Yes" if analysis.clinically_validated else "No",
        ),
    ]
    story.append(_label_value_rows(provenance))

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
    doc.build(story, onFirstPage=_page_footer, onLaterPages=_page_footer)
    return buffer.getvalue()
