/**
 * TypeScript types mirroring the FastAPI Pydantic schemas
 * (backend/app/schemas.py). These define the STABLE API contract agreed
 * before ML integration — responses look identical whether inference is
 * mocked or backed by the real OpenCV -> SVR -> SVM pipeline.
 */

export type TestType = "hemoglobin" | "glucose" | "urine_albumin";

export type SampleType = "blood" | "urine";

export type DataSource = "mock" | "synthetic" | "validated";

// Aarogya AI assistant types live in a client-safe module shared with the server route.
export type {
  AssistantAnswer,
  AssistantAnswerKind,
  AssistantMode,
  AssistantRequestBody,
  AssistantStatus,
  AssistantTurn,
} from "@/lib/assistant/types";

export type ScanStatus = "success" | "quality_failed" | "error";

/** "hybrid": hemoglobin uses the trained ML model; other tests are mocked. */
export type InferenceMode = "mock" | "ml" | "hybrid";

export interface HealthResponse {
  status: "ok";
  service: string;
  version: string;
  inference_mode: InferenceMode;
}

export interface TestMetadata {
  id: TestType;
  name: string;
  sample_type: SampleType;
  unit: string;
  description: string;
  interpretation_note: string;
}

export interface TestsResponse {
  tests: TestMetadata[];
  disclaimer: string;
}

export interface ModelDescriptor {
  identifier: string;
  version: string;
  kind: "mock" | "svr" | "svm" | "opencv";
}

export interface ModelsInfoResponse {
  inference_mode: InferenceMode;
  clinically_validated: boolean;
  active_models: ModelDescriptor[];
  planned_pipeline: string[];
  notes: string;
  disclaimer: string;
  /** Backend serving each test; "unavailable" means HTTP 503, never mocked. */
  test_inference: Record<string, "ml" | "mock" | "unavailable">;
  /** Classifier backend per test; "unavailable" = value returned, category null. */
  test_classification: Record<string, "ml" | "mock" | "unavailable">;
}

export interface QualityResult {
  passed: boolean;
  blur_score: number | null;
  calibration_detected: boolean | null;
  calibration_error: number | null;
  issues: string[];
  /** Extra numeric quality evidence from the image pipeline (empty for mock). */
  metrics: Record<string, number>;
}

export interface RoiDetection {
  method: string;
  confidence: number;
  /** Four [x, y] pixel corners, ordered TL, TR, BR, BL. */
  corners_xy: [number, number][];
}

export interface ImageAnalysis {
  mean_rgb: [number, number, number] | null;
  mean_lab: [number, number, number] | null;
  synthetic_intensity: number | null;
  annotated_image_url: string | null;
  roi_detection: RoiDetection | null;
}

export interface Measurement {
  value: number;
  unit: string;
  method: string;
  is_simulated: boolean;
}

export interface Classification {
  /** Verbatim label (e.g. "artificial_band_A_4.0-8.7" or a mock label). */
  label: string;
  /** "svm_synthetic_demo" (trained demonstration SVM) or "mock_svm_demo". */
  method: string;
  is_simulated: boolean;
  /** Classifier provenance; null for mock fixtures. kind "svm" = demonstration SVM. */
  model: ModelDescriptor | null;
}

export interface Explanation {
  summary: string;
  inputs_used: string[];
  limitations: string[];
  warnings: string[];
}

/**
 * Stable response contract for POST /api/scans/analyze.
 * `measurement` and `classification` are null when the scan fails quality
 * checks or errors — render the retry/error state instead.
 */
export interface ScanAnalysisResponse {
  scan_id: string;
  report_id: string | null;
  test_type: TestType;
  status: ScanStatus;
  source: DataSource;
  clinically_validated: boolean;
  model: ModelDescriptor;
  quality: QualityResult;
  image_analysis: ImageAnalysis | null;
  measurement: Measurement | null;
  classification: Classification | null;
  explanation: Explanation;
  disclaimer: string;
}

export interface PatientCreatePayload {
  age: number;
  sex?: "female" | "male" | "other";
  display_name?: string;
}

export interface PatientResponse {
  patient_id: string;
  age: number;
  sex: string | null;
  display_name: string | null;
  created_at: string;
}

export interface ScreeningHistoryEntry {
  scan_id: string;
  report_id: string | null;
  test_type: TestType;
  status: ScanStatus;
  source: DataSource | null;
  is_simulated: boolean;
  measurement: Measurement | null;
  classification: Classification | null;
  created_at: string;
}

export interface ScreeningHistoryResponse {
  patient_id: string;
  entries: ScreeningHistoryEntry[];
  disclaimer: string;
}

export interface ReportPatient {
  patient_id: string;
  display_name: string | null;
  age: number;
  sex: string | null;
}

/** GET /api/reports/{id} — a saved session joined with its analysis. */
export interface ScreeningReportResponse {
  report_id: string;
  scan_id: string;
  created_at: string;
  patient: ReportPatient;
  test: TestMetadata;
  analysis: ScanAnalysisResponse;
  disclaimer: string;
}
