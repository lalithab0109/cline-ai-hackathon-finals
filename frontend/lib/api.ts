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
  ScreeningReportResponse,
  TestType,
  TestsResponse,
} from "@/lib/types";
import type {
  AssistantAnswer,
  AssistantErrorBody,
  AssistantRequestBody,
  AssistantStatus,
} from "@/lib/assistant/types";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

/** API error carrying the HTTP status so callers can branch (e.g. 404). */
export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

/** Extract a human-readable message from a FastAPI error response. */
async function parseError(response: Response, path: string): Promise<ApiError> {
  try {
    const body = await response.json();
    const detail = body?.detail;
    if (typeof detail === "string") return new ApiError(detail, response.status);
    if (Array.isArray(detail) && detail.length > 0) {
      return new ApiError(
        detail
          .map((item: { msg?: string }) => item?.msg ?? "Invalid input")
          .join("; "),
        response.status
      );
    }
  } catch {
    // Fall through to the generic message below.
  }
  return new ApiError(
    `API request failed: ${response.status} ${path}`,
    response.status
  );
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

export function getReport(reportId: string): Promise<ScreeningReportResponse> {
  return getJson<ScreeningReportResponse>(`/api/reports/${reportId}`);
}

/**
 * Aarogya AI calls go to the SAME-ORIGIN Next.js route (/api/assistant), never
 * to FastAPI or the model provider directly — the API key stays server-side.
 */
export async function getAssistantStatus(): Promise<AssistantStatus> {
  try {
    const response = await fetch("/api/assistant", { headers: { Accept: "application/json" } });
    if (!response.ok) return { available: false, mode: "unavailable" };
    return (await response.json()) as AssistantStatus;
  } catch {
    return { available: false, mode: "unavailable" };
  }
}

export async function askAssistant(body: AssistantRequestBody): Promise<AssistantAnswer> {
  let response: Response;
  try {
    response = await fetch("/api/assistant", {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify(body),
    });
  } catch {
    throw new AssistantRequestError("Could not reach Aarogya AI. Check your connection and try again.", 0, true);
  }
  if (!response.ok) {
    let message = "Aarogya AI could not answer right now. Please try again.";
    let retryable = response.status >= 500 || response.status === 429;
    try {
      const err = ((await response.json()) as AssistantErrorBody).error;
      if (err?.message) message = err.message;
      if (typeof err?.retryable === "boolean") retryable = err.retryable;
    } catch {
      // keep the generic message
    }
    throw new AssistantRequestError(message, response.status, retryable);
  }
  return (await response.json()) as AssistantAnswer;
}

export class AssistantRequestError extends ApiError {
  retryable: boolean;

  constructor(message: string, status: number, retryable: boolean) {
    super(message, status);
    this.name = "AssistantRequestError";
    this.retryable = retryable;
  }
}

/** Direct URL of the PDF download endpoint (used as an anchor href). */
export function getReportPdfUrl(reportId: string): string {
  return `${API_BASE_URL}/api/reports/${reportId}/pdf`;
}
