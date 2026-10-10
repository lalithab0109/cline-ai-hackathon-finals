"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";
import { Bot, Loader2, RotateCcw, Send, ShieldAlert } from "lucide-react";
import AssistantMarkdown from "@/components/results/AssistantMarkdown";
import { askAssistant, AssistantRequestError, getAssistantStatus } from "@/lib/api";
import {
  ASSISTANT_DISCLAIMER,
  ASSISTANT_LIMITS,
  type AssistantAnswer,
  type AssistantStatus,
  type AssistantTurn,
} from "@/lib/assistant/types";
import type { ScreeningReportResponse } from "@/lib/types";

type ChatMessage =
  | { id: number; role: "user"; content: string }
  | { id: number; role: "assistant"; content: string; meta: AssistantAnswer };

type Failure = { message: string; retryable: boolean; question: string };

function suggestionsFor(report: ScreeningReportResponse): string[] {
  const { analysis } = report;
  if (analysis.status !== "success" || !analysis.measurement) {
    return [
      "Why couldn't this scan be analysed?",
      "What do the image-quality checks look for?",
      "How can I take a better photo of the card?",
    ];
  }
  if (analysis.source === "mock") {
    return [
      "What does \"mock result\" mean here?",
      "Was a model used for this result?",
      "Why is this not medically validated?",
    ];
  }
  return [
    "How was this value estimated?",
    "What does the demonstration category mean?",
    "What did the image-quality checks find?",
    "Why is this not medically validated?",
  ];
}

const UNAVAILABLE_TEXT: Record<string, string> = {
  missing_key: "Aarogya AI is not configured on this server (no API key set).",
  missing_model: "Aarogya AI is not configured on this server (no model selected).",
  unsupported_provider: "Aarogya AI is not configured on this server (unsupported provider).",
};

/**
 * Aarogya AI — explains THIS saved demonstration report. Answers come from
 * the server route /api/assistant (Cline SDK, no tools); every answer is
 * shown with the simulated-use disclaimer.
 */
export default function ReportAssistant({ report }: { report: ScreeningReportResponse }) {
  const [status, setStatus] = useState<AssistantStatus | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [pending, setPending] = useState(false);
  const [failure, setFailure] = useState<Failure | null>(null);
  const nextId = useRef(1);
  const listRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let cancelled = false;
    getAssistantStatus().then((s) => !cancelled && setStatus(s));
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    listRef.current?.scrollTo({ top: listRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, pending, failure]);

  async function send(question: string, retry = false) {
    const text = question.trim();
    if (!text || pending || text.length > ASSISTANT_LIMITS.questionMaxChars) return;
    const history: AssistantTurn[] = messages
      .slice(-ASSISTANT_LIMITS.historyMaxTurns)
      .map((m) => ({ role: m.role, content: m.content }));
    if (!retry) {
      setMessages((prev) => [...prev, { id: nextId.current++, role: "user", content: text }]);
      setInput("");
    }
    setFailure(null);
    setPending(true);
    try {
      const meta = await askAssistant({ reportId: report.report_id, question: text, history });
      setMessages((prev) => [...prev, { id: nextId.current++, role: "assistant", content: meta.answer, meta }]);
    } catch (err) {
      setFailure({
        message: err instanceof Error ? err.message : "Aarogya AI could not answer right now.",
        retryable: err instanceof AssistantRequestError ? err.retryable : true,
        question: text,
      });
    } finally {
      setPending(false);
    }
  }

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    void send(input);
  }

  const unavailable = status !== null && !status.available;
  const tooLong = input.length > ASSISTANT_LIMITS.questionMaxChars;

  return (
    <section
      className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-card print:hidden"
      aria-labelledby="aarogya-ai-title"
    >
      <div className="flex items-start gap-3 border-b border-slate-100 px-5 py-4 sm:px-6">
        <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-brand-50 text-brand-600">
          <Bot className="h-5 w-5" aria-hidden="true" />
        </span>
        <div className="min-w-0">
          <h2 id="aarogya-ai-title" className="flex flex-wrap items-center gap-2 text-sm font-semibold text-slate-900">
            Ask Aarogya AI about this report
            {status?.mode === "fake" && (
              <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-slate-500">
                Offline test mode
              </span>
            )}
          </h2>
          <p className="mt-0.5 text-xs leading-relaxed text-slate-500">
            Explains how this demonstration result was produced. It cannot diagnose,
            give treatment advice, or say whether a value is normal.
          </p>
        </div>
      </div>

      {status === null && (
        <div className="flex items-center gap-2 px-6 py-5 text-xs text-slate-500" role="status">
          <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" /> Checking assistant availability…
        </div>
      )}

      {unavailable && (
        <div className="px-5 py-5 sm:px-6" role="status">
          <p className="rounded-xl bg-slate-50 px-4 py-3 text-xs leading-relaxed text-slate-600">
            {UNAVAILABLE_TEXT[status.reason ?? ""] ?? "Aarogya AI is currently unavailable."} The rest of the
            report above is unaffected.
          </p>
        </div>
      )}

      {status?.available && (
        <div className="px-4 py-4 sm:px-6">
          <div
            ref={listRef}
            className="max-h-[26rem] space-y-3 overflow-y-auto pr-1"
            aria-live="polite"
            aria-busy={pending}
          >
            {messages.length === 0 && (
              <p className="text-xs text-slate-500">Try one of these questions:</p>
            )}
            {messages.map((m) =>
              m.role === "user" ? (
                <div key={m.id} className="flex justify-end">
                  <p className="max-w-[85%] whitespace-pre-wrap break-words rounded-2xl rounded-br-md bg-brand-600 px-3.5 py-2 text-sm leading-relaxed text-white">
                    {m.content}
                  </p>
                </div>
              ) : (
                <div key={m.id} className="flex justify-start">
                  <div className="max-w-[90%] rounded-2xl rounded-bl-md border border-slate-200 bg-slate-50 px-3.5 py-2.5">
                    {m.meta.kind !== "grounded" && (
                      <p className="mb-1 flex items-center gap-1 text-[11px] font-semibold text-slate-500">
                        <ShieldAlert className="h-3.5 w-3.5" aria-hidden="true" />
                        {m.meta.kind === "urgent_help" ? "Please seek real-world help" : "Outside what this assistant can do"}
                      </p>
                    )}
                    <AssistantMarkdown content={m.content} />
                    <p className="mt-2 border-t border-slate-200 pt-1.5 text-[10px] font-bold uppercase tracking-wide text-slate-400">
                      {m.meta.disclaimer}
                    </p>
                  </div>
                </div>
              ),
            )}
            {pending && (
              <div className="flex items-center gap-2 text-xs text-slate-500" role="status">
                <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" /> Aarogya AI is reading this report…
              </div>
            )}
            {failure && (
              <div className="rounded-xl bg-amber-50 px-3.5 py-2.5 text-xs leading-relaxed text-amber-800" role="alert">
                {failure.message}
                {failure.retryable && (
                  <button
                    type="button"
                    onClick={() => void send(failure.question, true)}
                    className="ml-2 inline-flex items-center gap-1 font-semibold underline underline-offset-2"
                  >
                    <RotateCcw className="h-3 w-3" aria-hidden="true" /> Retry
                  </button>
                )}
              </div>
            )}
          </div>

          {messages.length === 0 && (
            <div className="mt-2 flex flex-wrap gap-2">
              {suggestionsFor(report).map((s) => (
                <button
                  key={s}
                  type="button"
                  disabled={pending}
                  onClick={() => void send(s)}
                  className="rounded-full border border-brand-200 bg-brand-50 px-3 py-1.5 text-left text-xs font-medium text-brand-700 transition hover:bg-brand-100 disabled:opacity-50"
                >
                  {s}
                </button>
              ))}
            </div>
          )}

          <form onSubmit={onSubmit} className="mt-4 flex items-end gap-2">
            <label htmlFor="aarogya-ai-input" className="sr-only">
              Ask a question about this report
            </label>
            <textarea
              id="aarogya-ai-input"
              rows={2}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  void send(input);
                }
              }}
              placeholder="Ask about how this result was produced…"
              className="min-h-[2.75rem] flex-1 resize-none rounded-xl border border-slate-300 px-3 py-2 text-sm text-slate-800 placeholder:text-slate-400 focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-100"
              aria-invalid={tooLong}
              aria-describedby="aarogya-ai-help"
            />
            <button
              type="submit"
              disabled={pending || !input.trim() || tooLong}
              aria-label="Send question"
              className="inline-flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-brand-600 text-white shadow-card transition hover:bg-brand-700 disabled:opacity-50"
            >
              {pending ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" /> : <Send className="h-4 w-4" aria-hidden="true" />}
            </button>
          </form>
          <p id="aarogya-ai-help" className={`mt-1.5 text-[11px] ${tooLong ? "text-amber-700" : "text-slate-400"}`}>
            {input.length}/{ASSISTANT_LIMITS.questionMaxChars} · {ASSISTANT_DISCLAIMER} · Do not enter personal details.
          </p>
        </div>
      )}
    </section>
  );
}
