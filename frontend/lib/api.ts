/**
 * Thin, typed API client for the Aarogya Bindu FastAPI backend.
 *
 * The screening flow (implemented in later iterations) must call these
 * helpers — React components never contain ML/inference logic, and the
 * request/response shapes stay stable when mock inference is replaced by
 * the real OpenCV -> SVR -> SVM pipeline.
 */

import type {
  HealthResponse,
  ModelsInfoResponse,
  PatientCreatePayload,
  PatientResponse,
  ScanAnalysisResponse,
  ScreeningHistoryResponse,
  TestType,
  TestsResponse,
} from "@/lib/types";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

/** Extract a human-readable message from a FastAPI error response. */
async function parseError(response: Response, path: string): Promise<Error> {
  try {
    const body = await response.json();
    const detail = body?.detail;
    if (typeof detail === "string") return new Error(detail);
    if (Array.isArray(detail) && detail.length > 0) {
      return new Error(
        detail
          .map((item: { msg?: string }) => item?.msg ?? "Invalid input")
          .join("; ")
      );
    }
  } catch {
    // Fall through to the generic message below.
  }
  return new Error(`API request failed: ${response.status} ${path}`);
}

async function getJson<T>(path: string): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      headers: { Accept: "application/json" },
    });
  } catch {
    throw new Error(
      "Could not reach the screening server. Check that the backend is running."
    );
  }
  if (!response.ok) throw await parseError(response, path);
  return (await response.json()) as T;
}

export function getHealth(): Promise<HealthResponse> {
  return getJson<HealthResponse>("/api/health");
}

export function getTests(): Promise<TestsResponse> {
  return getJson<TestsResponse>("/api/tests");
}

export function getModelsInfo(): Promise<ModelsInfoResponse> {
  return getJson<ModelsInfoResponse>("/api/models/info");
}

export async function createPatient(
  payload: PatientCreatePayload
): Promise<PatientResponse> {
  const path = "/api/patients";
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify(payload),
    });
  } catch {
    throw new Error(
      "Could not reach the screening server. Check that the backend is running."
    );
  }
  if (!response.ok) throw await parseError(response, path);
  return (await response.json()) as PatientResponse;
}

/**
 * Upload a test-strip image for analysis. The multipart field names match
 * the backend contract; the response shape is identical for mock and
 * (future) ML-backed inference.
 */
export async function analyzeScan(params: {
  patientId: string;
  testType: TestType;
  image: File;
}): Promise<ScanAnalysisResponse> {
  const path = "/api/scans/analyze";
  const form = new FormData();
  form.append("image", params.image);
  form.append("test_type", params.testType);
  form.append("patient_id", params.patientId);

  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      method: "POST",
      body: form,
    });
  } catch {
    throw new Error(
      "Could not reach the screening server. Check that the backend is running."
    );
  }
  if (!response.ok) throw await parseError(response, path);
  return (await response.json()) as ScanAnalysisResponse;
}

export function getPatientHistory(
  patientId: string
): Promise<ScreeningHistoryResponse> {
  return getJson<ScreeningHistoryResponse>(`/api/patients/${patientId}/history`);
}
