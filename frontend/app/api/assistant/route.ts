/**
 * Aarogya AI — server-side route (Node.js runtime; the Cline SDK needs Node).
 *
 * POST /api/assistant  { reportId, question, history? } -> AssistantAnswer
 * GET  /api/assistant  -> AssistantStatus (secret-free: available / mode / reason)
 *
 * The API key never leaves the server; the browser only talks to this route.
 */

import { NextResponse, type NextRequest } from "next/server";

import { getAssistantStatus } from "@/lib/assistant/server/config";
import { checkRateLimit, clientKeyFrom } from "@/lib/assistant/server/rate-limit";
import { handleAssistantRequest } from "@/lib/assistant/server/service";
import { ASSISTANT_LIMITS, type AssistantErrorBody } from "@/lib/assistant/types";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const NO_STORE = { "Cache-Control": "no-store" };

function error(status: number, code: string, message: string, retryable: boolean, extra?: HeadersInit) {
  const body: AssistantErrorBody = { error: { code, message, retryable } };
  return NextResponse.json(body, { status, headers: { ...NO_STORE, ...extra } });
}

export async function GET() {
  return NextResponse.json(getAssistantStatus(), { headers: NO_STORE });
}

export async function POST(request: NextRequest) {
  const limit = checkRateLimit(clientKeyFrom(request.headers));
  if (!limit.ok) {
    return error(429, "rate_limited", "Too many questions. Please wait a moment and try again.", true, {
      "Retry-After": String(limit.retryAfterSec),
    });
  }

  if (!(request.headers.get("content-type") ?? "").toLowerCase().includes("application/json")) {
    return error(415, "unsupported_media_type", "The request was not valid.", false);
  }
  const declared = Number(request.headers.get("content-length") ?? "0");
  if (declared > ASSISTANT_LIMITS.requestMaxBytes) {
    return error(413, "request_too_large", "The request was too large.", false);
  }

  let raw: unknown;
  try {
    const text = await request.text();
    if (text.length > ASSISTANT_LIMITS.requestMaxBytes) {
      return error(413, "request_too_large", "The request was too large.", false);
    }
    raw = JSON.parse(text);
  } catch {
    return error(400, "invalid_json", "The request was not valid.", false);
  }

  try {
    const result = await handleAssistantRequest(raw);
    return NextResponse.json(result.body, { status: result.status, headers: NO_STORE });
  } catch {
    // Never forward internal error details (could include provider messages).
    console.error("[assistant] unexpected failure");
    return error(500, "internal_error", "Aarogya AI could not answer right now. Please try again.", true);
  }
}
