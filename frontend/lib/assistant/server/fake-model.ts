/**
 * SERVER-ONLY deterministic offline responder ("fake" provider).
 *
 * Implements the Cline SDK `AgentModel` streaming contract so the full
 * AgentRuntime path (system prompt, no tools, abort, output checks) is
 * exercised WITHOUT any network call, API key, or AI model. It only restates
 * fields from the de-identified report context with fixed templates. It is a
 * test/offline aid — answers are labelled mode="fake" in the API and UI.
 */

import "server-only";

import type { AssistantContext } from "@/lib/assistant/server/context";

type StreamEvent =
  | { type: "text-delta"; text: string }
  | { type: "usage"; usage: { inputTokens: number; outputTokens: number } }
  | { type: "finish"; reason: "stop" };

function describe(ctx: AssistantContext, question: string): string {
  const q = question.toLowerCase();
  const parts: string[] = [];
  const failed = ctx.status !== "success" || !ctx.measurement;

  if (failed) {
    parts.push(
      `This ${ctx.test_name} scan did not produce a result (status: ${ctx.status}).`,
      ctx.quality.issues.length
        ? `Image-quality notes: ${ctx.quality.issues.join("; ")}.`
        : "The image could not be analysed.",
      "Retaking the photo with even lighting, a steady camera and the whole card in frame may help.",
    );
  } else if (/quality|blur|light|roi|region|detect|card|photo|image/.test(q)) {
    parts.push(
      `The image passed the quality checks (passed: ${ctx.quality.passed}).`,
      ctx.roi_detection
        ? `The reaction area was located with method "${ctx.roi_detection.method}".`
        : "No region-of-interest details were recorded for this scan.",
    );
  } else if (/categor|band|class|svm/.test(q) && ctx.classification) {
    parts.push(
      `The category shown is "${ctx.classification.label}" from method "${ctx.classification.method}".`,
      ctx.test_type === "hemoglobin"
        ? "It is an artificial demonstration band, not a medical severity level."
        : "It is a fixed mock label used only to demonstrate the screen.",
    );
  } else {
    const m = ctx.measurement!;
    parts.push(
      `This ${ctx.test_name} report shows a simulated estimate of ${m.value} ${m.unit} (method: ${m.method}).`,
      ctx.source === "mock"
        ? "It is a deterministic mock value; no model was used."
        : `It was produced by ${ctx.model.identifier} (version ${ctx.model.version}) trained only on synthetic images.`,
    );
  }
  parts.push("It is not clinically validated.");
  return parts.join(" ");
}

/** Builds an AgentModel-compatible object that answers from the report context. */
export function createFakeModel(ctx: AssistantContext, question: string) {
  return {
    async *stream(request: { signal?: AbortSignal }): AsyncGenerator<StreamEvent> {
      if (request.signal?.aborted) throw new Error("aborted");
      const text = describe(ctx, question);
      yield { type: "text-delta", text };
      yield { type: "usage", usage: { inputTokens: 0, outputTokens: 0 } };
      yield { type: "finish", reason: "stop" };
    },
  };
}
