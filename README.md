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

## Current status (Iteration 2 — patient workflow + mock inference)

- ✅ Project scaffolding, design system, and landing page
- ✅ `GET /api/health`, `GET /api/tests`, `GET /api/models/info`
- ✅ `POST /api/patients`, `POST /api/scans/analyze`, screening history
- ✅ SQLite persistence (patients, screening sessions, analysis results)
- ✅ Deterministic mock inference behind the stable scan contract
- ✅ Guided screening UI: patient details → test selection → image upload →
  processing → simulated result summary
- ⏳ Explainable results page, reports/PDF — next iteration
- ⏳ Real ML models — developed separately in `ml/`, integrated behind the
  backend inference adapter without changing the API contract

## Prerequisites

- Node.js 20+ and npm
- Python 3.10+ (3.12 recommended)

## Run the backend (FastAPI)

```bash
cd backend
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # optional; defaults work for local dev
uvicorn app.main:app --reload --port 8000
```

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

Useful checks:

```bash
npm run lint        # ESLint (next/core-web-vitals)
npm run typecheck   # tsc --noEmit
npm run build       # production build
```

## API contract

| Method | Path | Status | Purpose |
|---|---|---|---|
| GET | `/api/health` | ✅ implemented | Liveness + inference mode |
| GET | `/api/tests` | ✅ implemented | Metadata for hemoglobin, glucose, urine albumin |
| GET | `/api/models/info` | ✅ implemented | Declares mock inference + planned ML pipeline |
| POST | `/api/patients` | ✅ implemented | Create fictional/demo patient |
| POST | `/api/scans/analyze` | ✅ implemented (mock) | Multipart: `image`, `test_type`, `patient_id` |
| GET | `/api/reports/{id}` | 🔜 501 stub | Structured screening report |
| GET | `/api/reports/{id}/pdf` | 🔜 501 stub | ReportLab-generated PDF |
| GET | `/api/patients/{id}/history` | ✅ implemented | Demo screening history |

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
`backend/app/services/inference.py`, which will wrap the ML module's
`analyze_strip(image, test_type, patient_info)` function (see
[`ml/README.md`](./ml/README.md)). Swapping mock → real models changes only
that adapter.

## Scope guardrails

- Patient-facing only — no doctor dashboard, hospital management,
  prescriptions, or treatment recommendations.
- No clinical claims: synthetic data and illustrative classifications are
  not clinically validated and are labeled as such throughout.
- No real patient records; demo/fictional profiles only.
