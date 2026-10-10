/**
 * SERVER-ONLY orchestration for one assistant request (framework-agnostic so
 * it can be unit-tested without Next.js):
 *   validate -> classify intent (fixed responses) -> fetch de-identified
 *   context -> run tool-free agent with timeout -> validate output ->
 *   append disclaimer. Errors are mapped to generic, secret-free messages.
 */

import "server-only";

import { runAssistantModel } from "@/lib/assistant/server/agent";
import { getAssistantConfig, type AssistantConfig } from "@/lib/assistant/server/config";
import { fetchAssistantContext, REPORT_ID_RE } from "@/lib/assistant/server/context";
import {
  CLINICAL_REFUSAL_RESPONSE,
  classifyQuestion,
  SAFETY_FALLBACK_RESPONSE,
  URGENT_HELP_RESPONSE,
  validateAnswer,
} from "@/lib/assistant/server/safety";
import {
  ASSISTANT_DISCLAIMER,
  ASSISTANT_LIMITS,
  type AssistantAnswer,
  type AssistantAnswerKind,
  type AssistantErrorBody,
  type AssistantTurn,
} from "@/lib/assistant/types";

export type ServiceResult =
  | { status: 200; body: AssistantAnswer }
  | { status: 400 | 404 | 413 | 429 | 502 | 503 | 504; body: AssistantErrorBody };

const fail = (
  status: Exclude<ServiceResult["status"], 200>,
  code: string,
  message: string,
  retryable: boolean,
): ServiceResult => ({ status, body: { error: { code, message, retryable } } });

type Parsed = { reportId: string; question: string; history: AssistantTurn[] };

export function parseRequest(raw: unknown): Parsed | ServiceResult {
  if (!raw || typeof raw !== "object") return fail(400, "invalid_request", "The request was not valid.", false);
  const { reportId, question, history } = raw as Record<string, unknown>;
  if (typeof reportId !== "string" || !REPORT_ID_RE.test(reportId)) {
    return fail(400, "invalid_report_id", "This report ID is not valid.", false);
  }
  if (typeof question !== "string" || !question.trim()) {
    return fail(400, "empty_question", "Please type a question.", false);
  }
  if (question.length > ASSISTANT_LIMITS.questionMaxChars) {
    return fail(400, "question_too_long", `Please keep questions under ${ASSISTANT_LIMITS.questionMaxChars} characters.`, false);
  }
  const turns: AssistantTurn[] = [];
  if (history !== undefined) {
    if (!Array.isArray(history)) return fail(400, "invalid_history", "The request was not valid.", false);
    for (const item of history.slice(-ASSISTANT_LIMITS.historyMaxTurns)) {
      const t = item as Record<string, unknown>;
      if (!t || (t.role !== "user" && t.role !== "assistant") || typeof t.content !== "string") {
        return fail(400, "invalid_history", "The request was not valid.", false);
      }
      turns.push({ role: t.role, content: t.content.slice(0, ASSISTANT_LIMITS.historyTurnMaxChars) });
    }
  }
  return { reportId, question: question.trim(), history: turns };
}

function answer(text: string, kind: AssistantAnswerKind, mode: "live" | "fake"): ServiceResult {
  return { status: 200, body: { answer: text.trim(), disclaimer: ASSISTANT_DISCLAIMER, kind, mode } };
}

/** Injection points for tests; production uses the defaults. */
export interface ServiceDeps {
  fetchContext?: typeof fetchAssistantContext;
  runModel?: typeof runAssistantModel;
}

export async function handleAssistantRequest(
  raw: unknown,
  config: AssistantConfig = getAssistantConfig(),
  deps: ServiceDeps = {},
): Promise<ServiceResult> {
  const fetchContext = deps.fetchContext ?? fetchAssistantContext;
  const runModel = deps.runModel ?? runAssistantModel;
  const parsed = parseRequest(raw);
  if ("status" in parsed) return parsed;

  if (config.mode === "unavailable") {
    return fail(503, "assistant_unavailable", "Aarogya AI is not configured on this server.", false);
  }
  const mode = config.mode;

  // Fixed responses: the model is never consulted for these.
  const intent = classifyQuestion(parsed.question);
  if (intent === "urgent") return answer(URGENT_HELP_RESPONSE, "urgent_help", mode);
  if (intent === "clinical") return answer(CLINICAL_REFUSAL_RESPONSE, "clinical_refusal", mode);

  const ctx = await fetchContext(config.backendUrl, parsed.reportId);
  if (!ctx.ok) {
    return ctx.reason === "not_found"
      ? fail(404, "report_not_found", "This report could not be found.", false)
      : fail(502, "report_unavailable", "The report could not be loaded right now. Please try again.", true);
  }

  const run = await runModel(config, ctx.context, ctx.json, parsed.question, parsed.history);
  if (!run.ok) {
    return run.reason === "timeout"
      ? fail(504, "assistant_timeout", "Aarogya AI took too long to respond. Please try again.", true)
      : fail(502, "assistant_error", "Aarogya AI could not answer right now. Please try again.", true);
  }

  const verdict = validateAnswer(run.text, ctx.json);
  if (!verdict.ok) {
    // Structured category + rule identifier only — never the answer text, question, report data or secrets.
    console.warn(JSON.stringify({ event: "assistant_output_rejected", category: verdict.reason, rule: verdict.rule }));
    return answer(SAFETY_FALLBACK_RESPONSE, "safety_fallback", mode);
  }
  return answer(run.text, "grounded", mode);
}
