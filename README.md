# Aarogya Bindu

### AI-assisted, image-based preliminary screening — a synthetic-data hackathon prototype

> [!IMPORTANT]
> **SIMULATED — NOT FOR MEDICAL USE.** Aarogya Bindu is a technology demonstration, not a diagnostic device. Its hemoglobin model was trained and evaluated exclusively on computer-generated test-strip images using an invented color-to-target mapping. It does **not** measure actual blood hemoglobin, detect anemia, or provide clinically validated results. Use fictional patient information only.

## The problem

Conventional hemoglobin screening involves blood collection and access to appropriate testing equipment and personnel. This can make frequent, convenient preliminary screening difficult, particularly in resource-constrained settings. An accessible image-based workflow is worth exploring—but color-based estimates must be clinically validated before they can be used for healthcare decisions.

## Our idea

**Aarogya Bindu** explores what an accessible, patient-facing screening experience could look like. A user enters fictional patient details, chooses a test, uploads an image of a demonstration test strip, and receives an explainable screening report. The hemoglobin pathway combines **OpenCV image processing**, **support vector regression (SVR)** for a simulated hemoglobin-equivalent estimate, and a separate **support vector machine (SVM)** for nonclinical demonstration categories. A **Cline Agents SDK-powered report assistant** can explain the saved report in natural language, with safety checks and clear simulation warnings.

The current implementation is a **working software prototype**, not a validated non-invasive hemoglobin measurement system.

## Demo workflow

```text
Fictional patient information
          ↓
Choose a screening test
          ↓
Upload a test-strip image
          ↓
Image-quality checks and region-of-interest detection
          ↓
Hemoglobin: OpenCV color features → trained SVR → demo SVM
Glucose / urine albumin: deterministic mock demonstration results
          ↓
Saved screening report + explanation
          ↓
PDF download + optional Cline-powered report Q&A
```

## Features

- **Guided screening flow:** patient details, test selection, image upload, processing, and report view.
- **Synthetic hemoglobin inference:** trained SVR applied to a restricted, synthetic-style test-strip image format.
- **Image analysis:** region-of-interest detection, image-quality checks, and explanations for failed-quality scans.
- **Demonstration classification:** trained SVM assigns artificial `artificial_band_A/B/C` labels, **not** clinical risk or anemia-severity categories.
- **Additional demo tests:** glucose and urine albumin are deterministic **mock** outputs, not trained predictions.
- **Saved reports:** SQLite persistence, screening history, and downloadable A4 PDF reports generated with ReportLab.
- **Aarogya AI:** optional, context-aware report assistant built with the Cline Agents SDK (`@cline/agents`), with explicit safety restrictions.
- **Transparency:** simulation disclaimers, model provenance, quality details, and limitations are surfaced in the product.

## Technology stack

| Layer | Technologies | Role |
| --- | --- | --- |
| Frontend | Next.js 15, React, TypeScript, Tailwind CSS, Lucide | Screening workflow, report UI, assistant chat |
| Backend | FastAPI, Pydantic | REST endpoints, validation, orchestration |
| Storage | SQLite | Fictional patient records, scans, report history |
| ML / computer vision | Python, OpenCV, scikit-learn, NumPy | Strip preprocessing, color features, SVR/SVM inference |
| PDF | ReportLab | Downloadable reports |
| Conversational AI | `@cline/agents` | Server-side report explanation |

## Repository structure

```text
frontend/
  app/                       # Next.js routes, including /results/[id]
  app/api/assistant/          # Server-side assistant endpoint
  components/results/        # Results and assistant UI
  lib/assistant/server/      # Cline agent, prompts, safety, context, limits

backend/
  app/routers/               # Health, models, scans, reports, patients
  app/services/              # ML integration, mock inference, PDF, context
  app/schemas.py             # API data contracts

ml/
  aarogya-bindu-ml/          # Trained SVR/SVM, preprocessing, tests, reports
  aarogya_bindu_dataset_generator/  # Synthetic dataset generation source
```

For the original project plan, see [Development and ML Roadmap](Aarogya_Bindu_Development_and_ML_Roadmap.md).

## Getting started

### Prerequisites

- **Node.js 22+** and npm (required for the optional Cline assistant)
- **Python 3.12+** (the pinned inference dependencies require it)
- macOS/Linux shell or equivalent terminal

### 1. Clone the repository

```bash
git clone https://github.com/lalithab0109/cline-ai-hackathon-finals.git
cd cline-ai-hackathon-finals
```

### 2. Start the FastAPI backend

In terminal 1:

```bash
cd backend
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --port 8000
```

Backend: `http://localhost:8000`  
Interactive API documentation: `http://localhost:8000/docs`

The backend requirements include the ML inference dependencies. The bundled models are loaded from `ml/aarogya-bindu-ml/models/` by default; use `ML_PROJECT_DIR` to override the ML project directory. If the hemoglobin model cannot load, the backend can still start, but hemoglobin inference returns **HTTP 503** rather than fabricated fallback values.

### 3. Start the Next.js frontend

In terminal 2, from the repository root:

```bash
cd frontend
npm install
cp .env.example .env.local
npm run dev
```

Open **http://localhost:3000**. The frontend uses `NEXT_PUBLIC_API_BASE_URL` (default `http://localhost:8000`) to contact FastAPI.

### 4. Optional: enable the Cline-powered report assistant

Set the following **server-side** values in `frontend/.env.local`:

```dotenv
CLINE_API_KEY=your_cline_api_key
ASSISTANT_PROVIDER_ID=cline
ASSISTANT_MODEL_ID=your_supported_model_id
ASSISTANT_TIMEOUT_MS=30000
BACKEND_INTERNAL_URL=http://localhost:8000
```

The Cline provider uses available Cline credits and requires a configured, supported model. **Never** commit the real API key, put it in a `NEXT_PUBLIC_` variable, or expose it in the browser.

For a deterministic offline assistant response (no live model call), set `ASSISTANT_PROVIDER_ID=fake`. This is a test fixture, not generative AI. If live assistant configuration is missing, the assistant panel becomes unavailable while the rest of the report continues to work.

### 5. Development checks

From `frontend/`:

```bash
npm run lint
npm run typecheck
npm run build
```

ML tests and training instructions are documented in [`ml/aarogya-bindu-ml/README.md`](ml/aarogya-bindu-ml/README.md). The dataset generator is documented in [`ml/aarogya_bindu_dataset_generator/README.md`](ml/aarogya_bindu_dataset_generator/README.md).

## How the ML pipeline works

The **hemoglobin demonstration** uses the following stages:

1. **Synthetic dataset generation:** create artificial strip images and targets using a specified, invented color mapping, with different augmentation profiles.
2. **Preprocessing and quality control:** detect the colored strip region and reject unsuitable images.
3. **Feature extraction:** compute a fixed vector of **30 color-derived features**.
4. **Regression:** load the saved, trained **RBF SVR** to estimate a *simulated hemoglobin-equivalent* value.
5. **Demonstration classification:** use a separately trained SVM with the 30 features plus SVR output to assign one of three **artificial** bands.
6. **Report generation:** return the estimate, provenance, image-quality information, disclaimers, and a PDF-ready explanation.

The SVM's bands are equal-width divisions of the synthetic target range. **They are not normal/abnormal labels, anemia diagnoses, or clinical severity levels.** If the SVM is unavailable, the SVR result may still be returned with a null classification and a warning.

### Synthetic evaluation results

The selected `svr_rbf__normalized` model was evaluated on a held-out **synthetic** test set of 83 samples:

| Metric | Held-out synthetic test result |
| --- | ---: |
| Mean absolute error (MAE) | 0.3873 simulated g/dL |
| Root mean squared error (RMSE) | 0.5816 simulated g/dL |
| R² | 0.9813 |
| Predictions within ±1.0 simulated g/dL | 89.16% |

**Interpretation:** these figures show agreement with the **synthetically generated target values only**. They do not establish performance on real test strips, smartphone photographs, or patient blood samples.

The error increases on challenging synthetic images: test MAE was **0.1189** on clean images versus **0.8060** on challenging augmentations. Blur, noise, lighting, and perspective remain important limitations. Full breakdowns and plots are available in [`ml/aarogya-bindu-ml/reports/evaluation.md`](ml/aarogya-bindu-ml/reports/evaluation.md).

## Cline SDK integration: Aarogya AI

Aarogya AI appears on the saved report page as an **“Ask Aarogya AI about this report”** panel. It answers questions about how the simulated result was produced, image quality, the artificial classification band, and model limitations.

```text
Report page (browser)
       ↓
Next.js POST /api/assistant
       ↓
FastAPI GET /api/reports/{id}/assistant-context
       ↓
Report-grounded prompt + server-side safety checks
       ↓
@cline/agents Agent → Cline provider
       ↓
Response validation → safe answer or fixed fallback
```

The project uses **`@cline/agents` (`Agent`, pinned version `0.0.92`)**, not `@cline/sdk` / `ClineCore`. The agent is **tool-free** (`tools: []`) with `maxIterations: 1` and `maxTokens: 400`; it is not permitted to execute shell commands, access files, or browse the web. The browser never receives the Cline API key.

Safety controls include fixed responses for diagnosis/treatment questions, grounded prompts, post-generation claim filtering, an always-visible simulation disclaimer, input-size limits, request timeouts, and in-memory rate limiting. These checks **reduce risk but cannot guarantee complete safety**. Automated assistant tests use fake models; the live paid-provider path has not been verified in this repository.

## API overview

| Method | Endpoint | Purpose |
| --- | --- | --- |
| GET | `/api/health` | Service health and inference mode |
| GET | `/api/tests` | Supported test metadata |
| GET | `/api/models/info` | Model status and ML/mock/unavailable sources |
| POST | `/api/patients` | Create a fictional patient |
| POST | `/api/scans/analyze` | Analyze uploaded image and save screening |
| GET | `/api/reports/{id}` | Retrieve a saved report |
| GET | `/api/reports/{id}/pdf` | Download PDF report |
| GET | `/api/patients/{id}/history` | Retrieve demonstration screening history |
| GET | `/api/reports/{id}/assistant-context` | Retrieve de-identified assistant context |
| POST / GET | `/api/assistant` | Next.js assistant Q&A / availability |

The backend reports whether a result is synthetic or mock and whether it is clinically validated. A failed-quality scan has **no measurement or classification**. The model integration boundary is `backend/app/services/inference.py`; the frontend does not run inference directly.

## Current limitations and responsible use

- **Synthetic-only validation:** no clinical samples, real hemoglobin measurements, or real-world diagnostic performance evidence.
- **Restricted image input:** the hemoglobin model expects **512 × 512 synthetic-style strip images** containing one colored rectangle on white paper; real smartphone photographs are untested.
- **No medical interpretation:** artificial SVM bands have no clinical meaning; the application does not diagnose anemia or recommend treatment.
- **Mock tests:** glucose and urine albumin results are deterministic demonstration fixtures.
- **No authentication:** report UUIDs are not access controls; anyone with a valid report URL may access it. **Never enter real patient data.**
- **Assistant limitations:** English-only; pattern-based safety checks are imperfect; rate limiting is in-memory and intended for a single instance.
- **No clinical deployment:** the prototype is not intended for healthcare decision-making.

## Future work

- Explore data collection protocols and validation against reference laboratory measurements, subject to appropriate approvals and safeguards.
- Investigate calibration, lighting normalization, and more robust real-world strip detection.
- Evaluate generalization across devices, imaging conditions, and diverse samples.
- Replace mock tests only when appropriate trained and validated models exist.
- Add authentication, privacy controls, and production-grade operational safeguards before any real-user deployment.

---

**Built for the Cline AI Builders Hackathon.**  
**SIMULATED — NOT FOR MEDICAL USE.**
