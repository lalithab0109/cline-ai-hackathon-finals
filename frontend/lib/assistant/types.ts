/**
 * Client-safe types and constants for the "Aarogya AI" report assistant.
 *
 * This file is imported by BOTH the browser component and the server route,
 * so it must never contain secrets, environment access, or SDK imports.
 */

/** Fixed simulated-use disclaimer appended to EVERY assistant answer. */
export const ASSISTANT_DISCLAIMER = "SIMULATED — NOT FOR MEDICAL USE";

export const ASSISTANT_LIMITS = {
  questionMaxChars: 500,
  historyMaxTurns: 6,
  historyTurnMaxChars: 1200,
  requestMaxBytes: 16_000,
} as const;

export type AssistantRole = "user" | "assistant";

export interface AssistantTurn {
  role: AssistantRole;
  content: string;
}

export interface AssistantRequestBody {
  reportId: string;
  question: string;
  history?: AssistantTurn[];
}

/**
 * - grounded: model (or offline test responder) answer that passed the output checks
 * - clinical_refusal: fixed response to diagnosis/treatment requests
 * - urgent_help: fixed response pointing to real-world medical help
 * - safety_fallback: model output failed the safety checks and was replaced
 */
export type AssistantAnswerKind =
  | "grounded"
  | "clinical_refusal"
  | "urgent_help"
  | "safety_fallback";

/** "live" = Cline SDK provider; "fake" = deterministic offline test responder (no AI model). */
export type AssistantMode = "live" | "fake";

export interface AssistantAnswer {
  answer: string;
  disclaimer: typeof ASSISTANT_DISCLAIMER;
  kind: AssistantAnswerKind;
  mode: AssistantMode;
}

export type AssistantUnavailableReason =
  | "missing_key"
  | "missing_model"
  | "unsupported_provider";

export interface AssistantStatus {
  available: boolean;
  mode: AssistantMode | "unavailable";
  reason?: AssistantUnavailableReason;
}

export interface AssistantErrorBody {
  error: { code: string; message: string; retryable: boolean };
}
