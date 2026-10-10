/**
 * SERVER-ONLY assistant configuration. Never import from client components.
 *
 * Reads (server environment only; none use the NEXT_PUBLIC_ prefix):
 *   CLINE_API_KEY          Cline API key (Bearer) — never logged or returned
 *   ASSISTANT_PROVIDER_ID  "cline" (live, Cline SDK) or "fake" (offline test responder)
 *   ASSISTANT_MODEL_ID     Cline model ID, e.g. "anthropic/claude-haiku-4.5"
 *   ASSISTANT_TIMEOUT_MS   provider timeout (default 30000, clamped 1000–60000)
 *   BACKEND_INTERNAL_URL   FastAPI base URL used server-side (falls back to NEXT_PUBLIC_API_BASE_URL)
 */

import type { AssistantStatus } from "@/lib/assistant/types";

/** Only providers whose credentials this app knows how to supply. */
const LIVE_PROVIDERS = new Set(["cline"]);

export type AssistantConfig =
  | { mode: "live"; providerId: string; modelId: string; apiKey: string; timeoutMs: number; backendUrl: string }
  | { mode: "fake"; timeoutMs: number; backendUrl: string }
  | { mode: "unavailable"; reason: NonNullable<AssistantStatus["reason"]>; backendUrl: string };

function clean(value: string | undefined): string {
  return (value ?? "").trim();
}

function timeoutMs(): number {
  const parsed = Number.parseInt(clean(process.env.ASSISTANT_TIMEOUT_MS), 10);
  if (!Number.isFinite(parsed)) return 30_000;
  return Math.min(60_000, Math.max(1_000, parsed));
}

function backendUrl(): string {
  const raw =
    clean(process.env.BACKEND_INTERNAL_URL) ||
    clean(process.env.NEXT_PUBLIC_API_BASE_URL) ||
    "http://127.0.0.1:8000";
  const url = raw.replace(/\/+$/, "");
  if (!/^https?:\/\/[^\s/]+/i.test(url)) return "http://127.0.0.1:8000";
  return url;
}

export function getAssistantConfig(): AssistantConfig {
  const providerId = clean(process.env.ASSISTANT_PROVIDER_ID).toLowerCase() || "cline";
  const base = { backendUrl: backendUrl() };

  if (providerId === "fake") return { mode: "fake", timeoutMs: timeoutMs(), ...base };
  if (!LIVE_PROVIDERS.has(providerId)) {
    return { mode: "unavailable", reason: "unsupported_provider", ...base };
  }
  const apiKey = clean(process.env.CLINE_API_KEY);
  if (!apiKey) return { mode: "unavailable", reason: "missing_key", ...base };
  const modelId = clean(process.env.ASSISTANT_MODEL_ID);
  if (!modelId) return { mode: "unavailable", reason: "missing_model", ...base };

  return { mode: "live", providerId, modelId, apiKey, timeoutMs: timeoutMs(), ...base };
}

/** Public, secret-free status for the UI. */
export function getAssistantStatus(config = getAssistantConfig()): AssistantStatus {
  if (config.mode === "unavailable") {
    return { available: false, mode: "unavailable", reason: config.reason };
  }
  return { available: true, mode: config.mode };
}
