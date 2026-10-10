/**
 * SERVER-ONLY Aarogya AI pipeline built on the Cline SDK (`@cline/agents`).
 *
 * - Uses the tool-free `Agent` runtime ONLY (never @cline/sdk / ClineCore,
 *   which ship shell/file/web tools). `tools: []` and `maxIterations: 1`
 *   make each request a single model turn with no tool execution possible.
 * - Live mode: providerId/modelId/apiKey from server env (see config.ts).
 * - Fake mode: deterministic offline AgentModel (fake-model.ts), no network.
 * - Timeout via `agent.abort()`; provider errors are never forwarded.
 */

import "server-only";

import { Agent } from "@cline/agents";

import type { AssistantConfig } from "@/lib/assistant/server/config";
import type { AssistantContext } from "@/lib/assistant/server/context";
import { createFakeModel } from "@/lib/assistant/server/fake-model";
import { buildUserMessage, SYSTEM_PROMPT } from "@/lib/assistant/server/prompt";
import type { AssistantTurn } from "@/lib/assistant/types";

const MAX_OUTPUT_TOKENS = 400;

export type ModelRunResult =
  | { ok: true; text: string }
  | { ok: false; reason: "timeout" | "provider_error" };

type RunnableConfig = Extract<AssistantConfig, { mode: "live" | "fake" }>;

/** Structural subset of the SDK's AgentModel (used for tests / offline mode). */
export type StreamingModel = ReturnType<typeof createFakeModel>;

export async function runAssistantModel(
  config: RunnableConfig,
  context: AssistantContext,
  contextJson: string,
  question: string,
  history: AssistantTurn[],
  modelOverride?: StreamingModel,
): Promise<ModelRunResult> {
  const common = {
    systemPrompt: SYSTEM_PROMPT,
    tools: [],
    maxIterations: 1,
    modelOptions: { maxTokens: MAX_OUTPUT_TOKENS, temperature: 0.2 },
  };
  const agent = modelOverride
    ? new Agent({ ...common, model: modelOverride })
    : config.mode === "live"
      ? new Agent({
          ...common,
          providerId: config.providerId,
          modelId: config.modelId,
          apiKey: config.apiKey,
        })
      : new Agent({ ...common, model: createFakeModel(context, question) });

  let timedOut = false;
  const timer = setTimeout(() => {
    timedOut = true;
    agent.abort("timeout");
  }, config.timeoutMs);

  try {
    const result = await agent.run(buildUserMessage(contextJson, question, history));
    if (timedOut || result.status === "aborted") return { ok: false, reason: "timeout" };
    if (result.status !== "completed" || result.error) return { ok: false, reason: "provider_error" };
    return { ok: true, text: result.outputText ?? "" };
  } catch {
    return { ok: false, reason: timedOut ? "timeout" : "provider_error" };
  } finally {
    clearTimeout(timer);
  }
}
