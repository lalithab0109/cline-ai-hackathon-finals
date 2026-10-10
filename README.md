# Aarogya Bindu

**AI-assisted preliminary diagnostic screening — hackathon prototype.**
All demonstration results are **SIMULATED — NOT FOR MEDICAL USE**.

Aarogya Bindu is a patient-facing web application demonstrating how
smartphone-based colorimetric test-strip analysis could support accessible
preliminary health screening:

```text
Patient Information
→ Select Diagnostic Test
→ Upload Test-Strip Image
→ OpenCV Image Processing      (future ML phase)
→ SVR Biomarker Estimation     (future ML phase)
→ SVM Screening Classification (future ML phase)
→ Explainable Screening Report
→ Downloadable PDF
```

The primary specification is
[`Aarogya_Bindu_Development_and_ML_Roadmap.md`](./Aarogya_Bindu_Development_and_ML_Roadmap.md).

## Repository layout

```text
frontend/   Next.js (App Router) + TypeScript + Tailwind CSS + Lucide icons
backend/    FastAPI + Pydantic (+ SQLite and ReportLab in later iterations)
ml/         Placeholder — future OpenCV / scikit-learn pipeline (see ml/README.md)
```

## Current status (Iteration 4 — hemoglobin ML integrated)

- ✅ Project scaffolding, design system, and landing page
- ✅ `GET /api/health`, `GET /api/tests`, `GET /api/models/info`
- ✅ `POST /api/patients`, `POST /api/scans/analyze`, screening history
- ✅ SQLite persistence (patients, screening sessions, analysis results)
- ✅ **Hemoglobin: trained SVR (OpenCV preprocessing + color features) from
  `ml/aarogya-bindu-ml`**, trained and evaluated only on synthetic images.
  The value is a *simulated hemoglobin-equivalent*, not clinically validated.
  A saved **demonstration SVM** adds an *artificial category*
  (`artificial_band_A/B/C`, equal-width slices of the synthetic value range;
  no clinical meaning, not a severity assessment). If the SVM is unavailable the
  SVR estimate is still returned with `classification = null` and a warning.
- ✅ **Glucose and urine albumin: still deterministic mock fixtures**
  (`source = "mock"`); no trained models exist for them yet.
- ✅ Guided screening UI: patient details → test selection → image upload →
  processing → redirect to the saved report
- ✅ `/results/[id]` explainable results page (fetches `GET /api/reports/{id}`)
- ✅ ReportLab A4 PDF report, generated in memory
- ⏳ ML models for glucose and urine albumin (none exist yet)

## Prerequisites

- Node.js 20+ and npm
- **Python 3.12+** (the pinned `numpy 2.5.3` / `scipy 1.18.1` require it).
  Verified on macOS arm64 with CPython 3.12.15.

## Run the backend (FastAPI)

```bash
cd backend
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # optional; defaults work for local dev
uvicorn app.main:app --reload --port 8000
```

- `pip install -r requirements.txt` also installs the hemoglobin ML inference
  dependencies via `-r ../ml/aarogya-bindu-ml/requirements-inference.txt`
  (**exact pins**: the model is a pickled scikit-learn pipeline). The model is
  loaded once at startup from `ml/aarogya-bindu-ml/models/hb_svr.joblib`
  (override the directory with `ML_PROJECT_DIR`). If it cannot be loaded the
  app still starts, hemoglobin scans return **HTTP 503** (never mock values),
  and `GET /api/models/info` reports `test_inference.hemoglobin = "unavailable"`.
- The hemoglobin model accepts **512×512 synthetic-style strip images only**
  (one colored rectangle on white paper); other images are returned as failed
  scans with guidance. Real phone photos are untested.
- API docs (OpenAPI/Swagger): http://localhost:8000/docs
- CORS origins are configured via `ALLOWED_ORIGINS` (default
  `http://localhost:3000`).

## Run the frontend (Next.js)

```bash
cd frontend
npm install
cp .env.example .env.local   # optional; defaults work for local dev
npm run dev
```

- App: http://localhost:3000
- The backend URL is configured via `NEXT_PUBLIC_API_BASE_URL`
  (default `http://localhost:8000`).
- Aarogya AI (optional) needs the server-side variables described in
  [Aarogya AI report assistant](#aarogya-ai-report-assistant). Requires Node.js ≥ 22.

Useful checks:

```bash
npm run lint        # ESLint (next/core-web-vitals)
npm run typecheck   # tsc --noEmit
npm run build       # production build
```

## API contract

| Method | Path | Status | Purpose |
|---|---|---|---|
| GET | `/api/health` | ✅ implemented | Liveness + inference mode (`hybrid`) |
| GET | `/api/tests` | ✅ implemented | Metadata for hemoglobin, glucose, urine albumin |
| GET | `/api/models/info` | ✅ implemented | Active models + per-test backend (`ml` / `mock` / `unavailable`) |
| POST | `/api/patients` | ✅ implemented | Create fictional/demo patient |
| POST | `/api/scans/analyze` | ✅ implemented (hemoglobin: ML; others: mock) | Multipart: `image`, `test_type`, `patient_id`; 503 if the hemoglobin model is unavailable |
| GET | `/api/reports/{id}` | ✅ implemented | Structured report (patient, test, analysis); 404 if unknown. Report ID == screening-session ID |
| GET | `/api/reports/{id}/pdf` | ✅ implemented | In-memory ReportLab A4 PDF (`application/pdf`, attachment) |
| GET | `/api/patients/{id}/history` | ✅ implemented | Demo screening history |
| GET | `/api/reports/{id}/assistant-context` | ✅ implemented | De-identified report summary used only by Aarogya AI (no name, patient ID, age, sex, IDs, timestamps or image data); 404 if unknown |
| POST/GET | `/api/assistant` (Next.js route) | ✅ implemented | Aarogya AI question endpoint / secret-free availability status |

The scan-analysis response contract (Pydantic: `backend/app/schemas.py`,
TypeScript: `frontend/lib/types.ts`) is **stable across the mock → ML
transition** and always carries: `test_type`, `status`, `quality`,
`measurement` (nullable), `source` (`mock`/`synthetic`/`validated`),
`model` (identifier + version), `classification` (nullable),
`clinically_validated`, `image_analysis`, `explanation`
(summary/inputs/limitations/warnings), and the simulation disclaimer.
Failed-quality scans never receive a measurement or classification.

## ML integration boundary

ML inference is never called from React components and never implemented
inside API route handlers. The single seam is
`backend/app/services/inference.py`, which routes by test type:

- `hemoglobin` → `services/ml_hemoglobin.py`, a thin wrapper around
  `aarogya_hb_ml.inference.predict_hemoglobin` (the OpenCV preprocessing and
  feature extraction stay in `ml/aarogya-bindu-ml`; nothing is duplicated). It
  maps the ML result onto `ScanAnalysisResponse` (`source="synthetic"`,
  `model.kind="svr"`, quality metrics, ROI detection).
- `glucose`, `urine_albumin` → `services/mock_inference.py` (unchanged).

The demo SVM (`models/hb_demo_svm.joblib`) takes the SVR's 30 features **plus
the raw SVR output** (`svr_pred`), in the order stored in its bundle; its
scaler is part of the saved pipeline. The ML package has no public SVM
function, so `ml_hemoglobin.py` re-runs the package's public
`preprocess` / `extract_features` / `feature_vector` once and applies the saved
pipeline. It is strictly validated at startup (feature order, class/label
match, artificial band names, synthetic + not-clinically-validated flags,
trained against this exact SVR) and reported as
`classification.method = "svm_synthetic_demo"`. Its labels are shown verbatim
and never mapped to clinical terms.

## Aarogya AI report assistant

An "Ask Aarogya AI about this report" panel on `/results/[id]` explains the
saved demonstration report: how the value was produced, image quality and ROI
detection, the artificial category, model provenance, and why nothing is
medically validated.

**Architecture** — browser → `POST /api/assistant` (Next.js, Node.js runtime)
→ FastAPI `GET /api/reports/{id}/assistant-context` → Cline SDK
(`@cline/agents` `Agent`, pinned `0.0.92`) → Cline provider. The browser never
talks to the model provider and never sees the key.

- **Tool-free agent:** `tools: []`, `maxIterations: 1`, `maxTokens: 400`.
  `@cline/sdk` / `ClineCore` (which include shell/file/web tools) are not used.
- **Safety layers** (`frontend/lib/assistant/server/safety.ts`):
  1. Diagnosis, treatment, dosing and "is this normal?" questions get a
     fixed refusal. Urgent symptoms get a fixed "seek real-world help"
     response. The model is not called for either.
  2. A strict system prompt treats the report, history and question as
     untrusted data. Envelope tags and control/bidi characters are stripped.
  3. Every model answer is checked before it is shown. Answers are rejected
     if they state or deny a diagnosis, give treatment or doses, attach
     clinical severity to bands, say a value is normal, quote numbers that
     are not in the report, or leak the prompt or a key. A fixed fallback
     replaces rejected answers.
  4. Every answer carries `SIMULATED — NOT FOR MEDICAL USE`.
- **Abuse limits:** questions are capped at 500 characters, history at 6
  turns, and the request body at 16 KB. Report IDs must be UUIDs. Rate limits
  are 8 requests per minute per IP and 60 per minute in total. The limiter is
  in-memory, so it is single-instance only. Requests time out after 30 s, and
  only generic error messages are returned.

**Configuration** (`frontend/.env.local`, server-side only, never
`NEXT_PUBLIC_`):

| Variable | Purpose |
|---|---|
| `CLINE_API_KEY` | Cline API key. Calls use your Cline credits. |
| `ASSISTANT_PROVIDER_ID` | `cline` (live) or `fake` (deterministic offline responder: no network, no AI) |
| `ASSISTANT_MODEL_ID` | e.g. `anthropic/claude-haiku-4.5` |
| `ASSISTANT_TIMEOUT_MS` | Default `30000` |
| `BACKEND_INTERNAL_URL` | FastAPI URL as seen from the Next.js server |

If the key or model ID is missing, the panel shows an "unavailable" state
and the rest of the report still works. Node.js 22 or later is required.

**Known limitations**

- **No authentication.** Anyone who has a report's random UUID can open
  the report and ask the assistant about it, the same as with
  `/api/reports/{id}`. Report IDs are not an access control. Use fictional
  data only.
- The safety checks are pattern-based and reduce risk but are not
  exhaustive. The live model path has not been tested against a paid
  provider in this repo; automated tests use fake models only.
- English only.

## Scope guardrails

- Patient-facing only — no doctor dashboard, hospital management,
  prescriptions, or treatment recommendations.
- No clinical claims: synthetic data and illustrative classifications are
  not clinically validated and are labeled as such throughout.
- No real patient records; demo/fictional profiles only.
