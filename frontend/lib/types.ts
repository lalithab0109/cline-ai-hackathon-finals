/**
 * TypeScript types mirroring the FastAPI Pydantic schemas
 * (backend/app/schemas.py). These define the STABLE API contract agreed
 * before ML integration — responses look identical whether inference is
 * mocked or backed by the real OpenCV -> SVR -> SVM pipeline.
 */

export type TestType = "hemoglobin" | "glucose" | "urine_albumin";

export type SampleType = "blood" | "urine";

export type DataSource = "mock" | "synthetic" | "validated";

export type ScanStatus = "success" | "quality_failed" | "error";

export type InferenceMode = "mock" | "ml";

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
}

export interface QualityResult {
  passed: boolean;
  blur_score: number | null;
  calibration_detected: boolean | null;
  calibration_error: number | null;
  issues: string[];
}

export interface ImageAnalysis {
  mean_rgb: [number, number, number] | null;
  mean_lab: [number, number, number] | null;
  synthetic_intensity: number | null;
  annotated_image_url: string | null;
}

export interface Measurement {
  value: number;
  unit: string;
  method: string;
  is_simulated: boolean;
}

export interface Classification {
  label: string;
  method: string;
  is_simulated: boolean;
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

export interface ScreeningHistoryEntry {
  scan_id: string;
  report_id: string | null;
  test_type: TestType;
  status: ScanStatus;
  created_at: string;
}

export interface ScreeningHistoryResponse {
  patient_id: string;
  entries: ScreeningHistoryEntry[];
  disclaimer: string;
}
