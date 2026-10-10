/**
 * SERVER-ONLY: fetches the de-identified grounding context from FastAPI.
 * Mirrors backend `AssistantContextResponse`. No patient identifiers or images.
 */

import "server-only";

export interface AssistantContext {
  test_type: "hemoglobin" | "glucose" | "urine_albumin";
  test_name: string;
  sample_type: string;
  status: "success" | "quality_failed" | "error";
  source: "mock" | "synthetic" | "validated";
  clinically_validated: false;
  measurement: { value: number; unit: string; method: string; is_simulated: boolean } | null;
  classification: {
    label: string;
    method: string;
    is_simulated: boolean;
    model: { identifier: string; version: string; kind: string } | null;
  } | null;
  quality: { passed: boolean; blur_score: number | null; issues: string[]; metrics: Record<string, number> };
  roi_detection: { method: string; confidence: number; corners_xy: number[][] } | null;
  model: { identifier: string; version: string; kind: string };
  explanation: { summary: string; inputs_used: string[]; limitations: string[]; warnings: string[] };
  interpretation_note: string;
  disclaimer: string;
}

/** Report IDs are UUIDs; validating first prevents path injection into the backend URL. */
export const REPORT_ID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export type ContextResult =
  | { ok: true; context: AssistantContext; json: string }
  | { ok: false; reason: "not_found" | "backend_error" };

export async function fetchAssistantContext(
  backendUrl: string,
  reportId: string,
  signal?: AbortSignal,
): Promise<ContextResult> {
  const url = `${backendUrl}/api/reports/${encodeURIComponent(reportId)}/assistant-context`;
  try {
    const res = await fetch(url, { cache: "no-store", signal, headers: { Accept: "application/json" } });
    if (res.status === 404) return { ok: false, reason: "not_found" };
    if (!res.ok) return { ok: false, reason: "backend_error" };
    const context = (await res.json()) as AssistantContext;
    if (!context || typeof context !== "object" || !context.test_type || !context.model) {
      return { ok: false, reason: "backend_error" };
    }
    // Defence in depth: the model never sees anything flagged as validated.
    context.clinically_validated = false;
    // Compact the corners array (not useful to the model, many numbers).
    const forModel = { ...context, roi_detection: context.roi_detection
      ? { method: context.roi_detection.method, confidence: context.roi_detection.confidence }
      : null };
    return { ok: true, context, json: JSON.stringify(forModel, null, 1) };
  } catch {
    return { ok: false, reason: "backend_error" };
  }
}
