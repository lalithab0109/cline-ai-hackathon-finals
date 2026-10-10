# Aarogya Bindu — Development and ML Implementation Roadmap

**Project:** AI-assisted preliminary diagnostic screening and patient-friendly report interpretation  
**Build context:** Three-person team; eight-hour hackathon prototype  
**Current priority:** Finish frontend and backend first, using mock results. Dataset creation, model training, and chatbot come later.

> **Prototype boundary:** Synthetic images, simulated biomarker values, and illustrative SVM classifications are **not clinically validated** and must be labeled **SIMULATED — NOT FOR MEDICAL USE** throughout the UI and PDF. The prototype cannot provide actual medical diagnoses, rule out disease, or determine real patient urgency. A deployable diagnostic product would require real assay calibration data, clinical validation, and appropriate regulatory review.

## 1. Product vision and scope

Aarogya Bindu is a mobile-first, patient-facing application designed to demonstrate how smartphone images of biochemical test strips could support accessible preliminary screening. Its goal is to show a transparent pipeline from image capture to a report patients can understand.

### Supported test modes

- **Hemoglobin:** proposed blood-based anemia screening.
- **Glucose:** proposed glucose screening using a compatible assay.
- **Albumin:** proposed **urine** albumin screening (not a blood test).

Each assay ultimately needs its own real-world chemistry, calibration, reference interpretation, and validation. For the hackathon, the modes share a synthetic image-processing framework.

### In scope

- Patient details and test selection.
- Diagnostic-strip image upload and preview.
- Computer-vision strip detection, quality assessment, color correction, and color-feature extraction (ML phase).
- Experimental SVR-based synthetic intensity/biomarker demonstration (ML phase).
- Experimental SVM-based illustrative screening severity classification using relevant patient attributes (ML phase).
- Explainable results: show measurements, input features, scan quality, model outputs, and interpretation provenance.
- Patient-friendly report, downloadable PDF, optional screening history.
- **Optional later:** report-aware chatbot, potentially using Cline SDK, with multilingual explanations.

### Out of scope

- Doctor dashboard or clinician workflow.
- Symptom-interview chatbot.
- Treatment plans, medication prescriptions, autonomous medical decisions.
- Hardware manufacture during the hackathon.
- Claims of clinical-grade accuracy from synthetic datasets.

## 2. End-to-end architecture

```text
Patient (Next.js + TypeScript + Tailwind)
  |
  | Patient details + test selection + strip image
  v
FastAPI backend
  |-- SQLite: patient/demo sessions, scan metadata, reports
  |-- Scan endpoint -> ML adapter
  |                      |
  |                      +--> OpenCV strip/pad detection
  |                      +--> Quality checks
  |                      +--> Calibration and RGB/Lab features
  |                      +--> SVR: synthetic target estimation
  |                      +--> SVM: illustrative screening category
  |
  |-- Interpretation/explainability layer
  |-- PDF report generator
  |-- Optional later: Gemini/Cline SDK report chatbot
  v
Results UI: measurement + label + evidence + limitations + PDF
```

**Separation of responsibility:** OpenCV computes image features; SVR estimates an experimental target; SVM assigns an experimental category; backend records evidence and applies guardrails; a language model (if added) explains structured data but never invents measurements or independently diagnoses.

## 3. Phase plan

| Phase | Objective | Deliverable |
|---|---|---|
| **1 — Development (now)** | Build the full patient-facing application with mock ML responses | Working frontend, backend APIs, SQLite, explainable results, PDF, history |
| **2 — Synthetic data** | Generate strips and fictional patient profiles | Images, labels, splits, dataset documentation |
| **3 — ML/CV** | Implement OpenCV, optional SVR, and SVM experiments | Inference function, model artifacts, evaluation |
| **4 — Integration** | Replace mock adapter with ML inference | End-to-end scan -> results -> report |
| **5 — Add-ons** | Add report-aware chatbot, languages, possibly voice | Optional Cline SDK/Gemini assistant |

## 4. Phase 1: Frontend development

**Stack:** Next.js, React, TypeScript, Tailwind CSS. Prioritize responsive mobile layouts.

### Pages and functionality

1. **Landing (`/`)** — Explain purpose, three supported screening modes, how it works, prominent *Start Screening* CTA, and prototype limitations.
2. **Patient details (`/screening`)** — Collect minimum relevant fields (age, sex when relevant, optional demo identifier). Validate inputs. Use fictional patients for demo; avoid collecting unnecessary personal health information.
3. **Test selection** — Hemoglobin, glucose, **urine** albumin cards with plain-language descriptions. Test selection flows into scan session.
4. **Scanner (`/scanner`)** — Camera/file upload, preview, file-type/size checks, progress/loading, error and retake states. Initially call mock scan API.
5. **Results (`/results/[id]`)** — Show test, measurement, unit, simulated classification, quality indicators, annotated image when available, RGB/Lab values, and expandable *How was this result generated?* evidence panel. Clearly differentiate experimental model output from medical conclusions.
6. **Report download** — Download PDF from backend; include model/data provenance and simulation disclaimer.
7. **History (`/history`)** — Optional list of previous fictional/demo screening sessions.

**Results page layout:** (a) top-line finding; (b) measurement and simulated category; (c) scan-quality summary; (d) calibrated color measurements; (e) inputs used for experimental SVM; (f) explanation of what the output means and what it cannot establish; (g) PDF download. Avoid reassuring labels like “disease-free.”

### Frontend components

```text
PatientForm.tsx
TestSelector.tsx
StripScanner.tsx
AnalysisViewer.tsx
SeverityCard.tsx
ExplainabilityPanel.tsx
ReportDownload.tsx
ScreeningHistory.tsx
ReportChatbot.tsx  # optional later
```

## 5. Phase 1: Backend development

**Stack:** Python, FastAPI, Pydantic, SQLite, ReportLab; CORS configured for frontend origin.

### Endpoints

| Method | Path | Responsibility |
|---|---|---|
| POST | `/api/patients` | Create fictional/demo patient record |
| GET | `/api/tests` | Return supported test metadata |
| POST | `/api/scans/analyze` | Accept selected test + image; validate; return mock inference initially |
| GET | `/api/reports/{id}` | Retrieve structured report |
| GET | `/api/reports/{id}/pdf` | Download generated PDF |
| GET | `/api/patients/{id}/history` | Retrieve previous demo scans |
| POST | `/api/chat` | **Optional later** report-aware assistant |

### Backend modules

- `main.py`: FastAPI application, middleware, route registration.
- `routes/scans.py`: upload handling and scan orchestration.
- `routes/reports.py`: report retrieval and PDF delivery.
- `services/mock_inference.py`: deterministic fake ML response matching future interface.
- `services/inference_adapter.py`: replace mock implementation with actual ML pipeline later.
- `services/interpretation.py`: structured report construction, limitations, reference-rule metadata.
- `services/pdf_service.py`: generate PDF from stored structured report.
- `database.py`: SQLite persistence and simple schemas.
- `schemas.py`: Pydantic request/response models.
- Later: `services/gemini_service.py`, `routes/chat.py`.

### Data model (minimal)

- `patients`: id, demo identifier, age, optional sex, created_at.
- `scans`: id, patient_id, test_type, image path, quality status, analysis JSON, created_at.
- `reports`: id, scan_id, report JSON, created_at.

For a hackathon, avoid unnecessary authentication complexity; do not expose real patient records or publish uploaded images. Do not retain raw images longer than needed.

## 6. Lock the ML-to-backend contract before coding

The frontend must not depend on whether analysis is mocked or model-backed. Define and test a stable response contract immediately.

**`POST /api/scans/analyze`**: multipart form data with `image`, `test_type`, and a `patient_id` or demo session identifier.

**Illustrative response** (all values fictional):

```json
{
  "scan_id": "scan_001",
  "report_id": "report_001",
  "test_type": "hemoglobin",
  "status": "success",
  "source": "synthetic_demo",
  "clinically_validated": false,
  "quality": {
    "passed": true,
    "blur_score": 142.5,
    "calibration_detected": true,
    "calibration_error": 3.2
  },
  "image_analysis": {
    "mean_rgb": [108, 151, 142],
    "mean_lab": [60.1, -18.4, -1.7],
    "synthetic_intensity": 0.71,
    "annotated_image_url": "/api/scans/scan_001/annotated"
  },
  "measurement": {
    "value": 9.2,
    "unit": "g/dL",
    "method": "mock",
    "is_simulated": true
  },
  "classification": {
    "label": "moderate_abnormality",
    "method": "mock_svm_demo",
    "is_simulated": true
  },
  "explanation": {
    "summary": "Illustrative screening result; not a medical diagnosis.",
    "inputs_used": ["simulated measurement", "age", "sex"],
    "limitations": ["Synthetic demonstration data", "Not clinically validated"]
  }
}
```

**Contract rules:**

- Always include `source`, `clinically_validated`, and explicit simulated flags.
- Failed-quality scans must not receive a measurement or classification; return an actionable retry/error state.
- `measurement` and `classification` can be `null` for failed analyses.
- Use consistent units and test-specific metadata; don't silently mix urine albumin and blood-based results.
- Never label model inputs as proven *causal explanations* of SVM predictions without actual attribution analysis.
- Keep mock response deterministic for UI and integration tests.

## 7. Phase 2: Synthetic datasets

### 7.1 Diagnostic-strip image dataset

Generate a standardized strip with a reaction pad and calibration reference patches. Randomize:

- Pad color, brightness, rotation, perspective, placement.
- Noise, blur, glare, shadows, and lighting conditions.
- Reference-patch observed colors while preserving known expected colors.

Store labels for pad bounding box, reference patch coordinates, target RGB/Lab, and synthetic intensity. Start with **100–300 images** to validate detection; scale toward **1,000–2,000** if useful. Split at the base-sample level before augmentation to avoid leakage.

### 7.2 Synthetic patient-profile dataset

Generate fictional ages, relevant sex categories, test types, simulated biomarker readings, and illustrative severity labels. Document exactly how labels were assigned. **This dataset tests software and reproduces chosen rules; it does not establish medically valid severity prediction.**

## 8. Phase 3: ML implementation

### 8.1 OpenCV pipeline

```text
Image upload
  -> file/resolution checks
  -> detect strip and four corners
  -> perspective alignment
  -> detect calibration patches + reaction pad
  -> blur/glare/exposure checks
  -> color normalization
  -> extract mean/median RGB, CIELAB, synthetic intensity
  -> return features + annotated image + quality evidence
```

Use OpenCV contours, geometric constraints, and perspective transforms first. A trained object detector is unnecessary for a simple standardized synthetic template.

### 8.2 SVR regression model

- Inputs: calibrated RGB/Lab/intensity features.
- Target: **synthetic** intensity or a clearly fictional concentration mapping.
- Model: `StandardScaler` + `SVR` from scikit-learn.
- Evaluate MAE/RMSE on held-out synthetic data; compare with direct color-extraction baseline.
- Do **not** claim clinical concentration accuracy without measured strip-to-laboratory ground truth.

### 8.3 SVM classification model

- Inputs: test-specific synthetic measurement, relevant patient attributes, and any validated additional features (once available).
- Target: illustrative screening category generated using documented demonstration rules.
- Model: `StandardScaler` + `SVC`, with categorical encoding as needed.
- Prefer **separate test-specific models/rules**; hemoglobin, glucose, and urine albumin have different interpretation requirements.
- Evaluate confusion matrix, class precision/recall, and held-out performance; note that high accuracy against synthetic rule labels **does not prove clinical validity**.
- Image quality should be a gate, not an excuse to classify poor scans.

### 8.4 Unified inference interface

```python
def analyze_strip(image, test_type, patient_info):
    # 1. Validate and inspect image
    # 2. Detect strip, calibrate, extract features
    # 3. Reject poor-quality scans
    # 4. Run experimental SVR estimate
    # 5. Run experimental SVM classification
    # 6. Return versioned, explainable structured result
    ...
```

**Interpretation note:** For a clinically deployed system, screening labels and reference thresholds must come from validated, test-specific clinical criteria and data. Gemini must never invent them.

## 9. Phase 4: Integrate ML with backend

1. Finish ML `analyze_strip(...)` and unit tests.
2. Wrap it behind `inference_adapter.py` using the same response schema as mock inference.
3. Validate outputs and handle timeouts/errors.
4. Store features, model version, source, and result provenance.
5. Render real extracted color values and annotated strip in the results UI.
6. Verify invalid scans never show a fabricated result.
7. Run full end-to-end tests across supported demo modes.

## 10. Explainable report and PDF

Every report should contain:

1. Test name and sample type (blood or urine, as appropriate).
2. Fictional/demo patient metadata and scan timestamp.
3. Image-quality findings and calibration status.
4. Extracted reaction-pad color features and optional annotated image.
5. Experimental SVR estimate, unit, and simulated-data provenance.
6. Experimental SVM category and the **inputs** used to classify it.
7. Separate explanation of any reference-rule comparison (if used), without falsely claiming model causality.
8. Plain-language explanation and limitations.
9. Visible **SIMULATED — NOT FOR MEDICAL USE** notice.

A model-produced severity label is not a confirmed diagnosis. The chatbot, if added, may explain only these recorded results and limitations.

## 11. Phase 5: Optional report-aware chatbot

**Defer until the core flow works.** Potential implementation: Cline SDK with an appropriate LLM provider, or a simpler Gemini API call if SDK integration is too time-consuming.

- Input: authenticated/authorized report context plus patient question.
- Output: simple-language explanation, possibly English/Hindi/Assamese.
- Read-only access to the selected report; no shell/file editing/browsing permissions.
- No independent diagnosis, prescribing, treatment plans, or invented measurements.
- Clearly acknowledge simulated results in every relevant answer.
- Verify current SDK API and hackathon bonus/credit rules before choosing implementation.

## 12. Three-person team split

| Team member | Ownership | Interfaces |
|---|---|---|
| **1 — Frontend** | Next.js pages, upload UX, results visualization, report/history UI | Uses agreed FastAPI JSON schema |
| **2 — ML/CV** | Synthetic strip generator, OpenCV, quality/calibration, optional SVR/SVM training | Exposes `analyze_strip(...)` returning agreed schema |
| **3 — Backend/AI** | FastAPI, SQLite, mock adapter, report/PDF generation, later chatbot | Owns API schema and inference adapter |

Use Git branches `feature/frontend`, `feature/ml-pipeline`, and `feature/backend-ai`. Agree on contracts first; keep changes isolated and merge tested features frequently. Cline can assist with implementation and testing, but avoid simultaneous agent edits to shared files.

## 13. Eight-hour hackathon schedule

| Time | Frontend | ML/CV | Backend |
|---|---|---|---|
| 0–1h | Scaffold Next.js, routes | Strip template/generator | Scaffold FastAPI, lock contract |
| 1–2h | Patient form/test selection | Generate initial labeled images | Database + mock scan endpoint |
| 2–3h | Scanner upload UI | Detect strip/pad | Connect mock response |
| 3–4h | Results/explainability UI | Color calibration/quality | Report structure and explanation |
| 4–5h | Integrate scanner | Optional SVR experiment | PDF endpoint |
| 5–6h | Polish/report download | Optional SVM experiment | Connect actual inference adapter |
| 6–7h | Error states/responsive QA | Unseen-image tests | End-to-end QA |
| 7–8h | Demo rehearsal | Validate ML output | Deploy and integration check |

**Critical milestones:** API contract agreed by hour 1; actual image processed by hour 3; frontend displays scanner output by hour 4; report/PDF by hour 5–6; full demo by hour 7.

## 14. Priorities and fallback plan

| Priority | Feature |
|---|---|
| P0 | Frontend journey, backend API, stable mock contract |
| P0 | Working OpenCV scan, quality checks, color extraction |
| P0 | Explainable results with clear synthetic labels |
| P1 | PDF report and integrated inference |
| P1 | SVR/SVM demonstration, if datasets and tests are ready |
| P2 | Screening history |
| P2 | Cline SDK report chatbot |
| P3 | Voice and extra language options |

**Fallback:** Build a complete, polished **hemoglobin-only** demo first; then add glucose and urine albumin modes. If models are not ready, show real OpenCV features with clearly mocked estimates rather than pretending the trained models work.

## 15. Immediate development checklist

- [ ] Create repository and separate frontend/backend directories.
- [ ] Initialize Next.js + Tailwind and FastAPI.
- [ ] Agree on `POST /api/scans/analyze` request and response schemas.
- [ ] Implement mock inference adapter and one demo fixture.
- [ ] Build patient form and test selection.
- [ ] Build upload, preview, validation, and loading/error states.
- [ ] Build results page and explainability panel.
- [ ] Implement SQLite persistence and report endpoints.
- [ ] Generate PDF with synthetic-data disclaimer.
- [ ] Test the full mock-driven journey.
- [ ] **Only then** start dataset generation, model training, and ML integration.
- [ ] Consider Cline SDK chatbot as a final add-on.

## 16. Demo script for judges

1. Create a fictional patient profile.
2. Choose hemoglobin screening.
3. Upload a synthetic test-strip image.
4. Show OpenCV locating the strip and reaction pad.
5. Show measured calibrated color features.
6. Show the experimental SVR output and illustrative SVM category.
7. Expand the explanation panel to show input evidence and limitations.
8. Download the clearly labeled demonstration PDF.
9. If ready, ask the optional report-aware chatbot to explain the report.

**Positioning:** *Aarogya Bindu — AI-powered preliminary screening and understandable reports.* The hackathon demonstrates the technical architecture, not clinical diagnostic performance.
