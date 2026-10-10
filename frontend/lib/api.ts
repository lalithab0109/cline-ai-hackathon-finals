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
  TestsResponse,
} from "@/lib/types";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: { Accept: "application/json" },
  });
  if (!response.ok) {
    throw new Error(`API request failed: ${response.status} ${path}`);
  }
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
