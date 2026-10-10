"use client";

import {
  AlertTriangle,
  CheckCircle2,
  FlaskConical,
  RotateCcw,
  ShieldAlert,
} from "lucide-react";
import type { ScanAnalysisResponse, TestMetadata } from "@/lib/types";

function formatLabel(label: string): string {
  return label.replace(/_/g, " ");
}

/**
 * Step 5 — analysis outcome. Summary-level view; the full explainable
 * results page (quality detail, color features, evidence panel, PDF)
 * arrives in Task 3. Everything shown here comes from the API response —
 * nothing is fabricated client-side.
 */
export default function ScanResultSummary({
  result,
  test,
  onRetake,
  onNewScreening,
}: {
  result: ScanAnalysisResponse;
  test: TestMetadata;
  onRetake: () => void;
  onNewScreening: () => void;
}) {
  if (result.status !== "success" || !result.measurement || !result.classification) {
    return (
      <FailureView result={result} test={test} onRetake={onRetake} />
    );
  }

  return (
    <div className="mx-auto w-full max-w-xl">
      <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-card">
        <div className="flex items-center justify-between border-b border-slate-100 px-6 py-4">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="h-5 w-5 text-brand-600" aria-hidden="true" />
            <h2 className="font-semibold text-slate-900">Scan complete</h2>
          </div>
          <span className="rounded-full bg-amber-100 px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-wide text-amber-800">
            Simulated
          </span>
        </div>

        <div className="px-6 py-5">
          <p className="text-xs font-medium uppercase tracking-wide text-slate-500">
            {test.name} · {test.sample_type} sample
          </p>
          <p className="mt-1 text-4xl font-bold text-slate-900">
            {result.measurement.value}{" "}
            <span className="text-lg font-medium text-slate-500">
              {result.measurement.unit}
            </span>
          </p>
          <p className="mt-2 text-sm text-slate-600">
            Illustrative screening category:{" "}
            <span className="font-semibold capitalize text-amber-700">
              {formatLabel(result.classification.label)}
            </span>
          </p>

          <div className="mt-5 flex items-start gap-2 rounded-xl bg-amber-50 px-4 py-3">
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-amber-600" aria-hidden="true" />
            <p className="text-xs font-semibold leading-relaxed text-amber-900">
              SIMULATED — NOT FOR MEDICAL USE. This is a demonstration result
              and cannot diagnose or rule out any condition.
            </p>
          </div>

          <p className="mt-5 text-sm leading-relaxed text-slate-600">
            {result.explanation.summary}
          </p>

          <div className="mt-4">
            <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">
              Limitations
            </h3>
            <ul className="mt-2 space-y-1.5">
              {result.explanation.limitations.map((item) => (
                <li key={item} className="flex items-start gap-2 text-xs leading-relaxed text-slate-500">
                  <span className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-slate-400" />
                  {item}
                </li>
              ))}
            </ul>
          </div>

          {result.explanation.warnings.length > 0 && (
            <div className="mt-4 space-y-1.5">
              {result.explanation.warnings.map((warning) => (
                <p
                  key={warning}
                  className="flex items-start gap-2 rounded-lg bg-sky-50 px-3 py-2 text-xs leading-relaxed text-sky-800"
                >
                  <ShieldAlert className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden="true" />
                  {warning}
                </p>
              ))}
            </div>
          )}

          <p className="mt-5 border-t border-dashed border-slate-200 pt-3 text-[11px] leading-relaxed text-slate-400">
            Model: {result.model.identifier} v{result.model.version} · Source:{" "}
            {result.source} · Scan {result.scan_id.slice(0, 8)}…
          </p>
        </div>
      </div>

      <div className="mt-5 flex flex-col gap-3 sm:flex-row">
        <button
          type="button"
          onClick={onNewScreening}
          className="inline-flex flex-1 items-center justify-center gap-2 rounded-xl bg-brand-600 px-5 py-2.5 text-sm font-semibold text-white shadow-card transition hover:bg-brand-700"
        >
          <FlaskConical className="h-4 w-4" aria-hidden="true" />
          Run another test
        </button>
        <button
          type="button"
          onClick={onRetake}
          className="inline-flex flex-1 items-center justify-center gap-2 rounded-xl border border-slate-300 bg-white px-5 py-2.5 text-sm font-semibold text-slate-700 transition hover:border-brand-300 hover:text-brand-700"
        >
          <RotateCcw className="h-4 w-4" aria-hidden="true" />
          Retake this test
        </button>
      </div>

      <p className="mt-4 text-center text-xs text-slate-400">
        A full explainable report page and PDF download arrive in the next
        iteration.
      </p>
    </div>
  );
}

/** Failed-quality scan: actionable issues, never a fabricated result. */
function FailureView({
  result,
  test,
  onRetake,
}: {
  result: ScanAnalysisResponse;
  test: TestMetadata;
  onRetake: () => void;
}) {
  return (
    <div className="mx-auto w-full max-w-xl">
      <div className="rounded-2xl border border-rose-200 bg-white p-6 shadow-card sm:p-8">
        <div className="flex items-center gap-3">
          <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-rose-50 text-rose-600">
            <AlertTriangle className="h-5 w-5" aria-hidden="true" />
          </span>
          <div>
            <h2 className="font-semibold text-slate-900">Scan couldn&apos;t be used</h2>
            <p className="text-xs text-slate-500">
              {test.name} · no result was generated for this upload
            </p>
          </div>
        </div>

        <ul className="mt-5 space-y-2">
          {result.quality.issues.map((issue) => (
            <li
              key={issue}
              className="rounded-lg bg-rose-50 px-3 py-2 text-sm leading-relaxed text-rose-700"
            >
              {issue}
            </li>
          ))}
        </ul>

        <p className="mt-4 text-sm leading-relaxed text-slate-600">
          {result.explanation.summary}
        </p>

        <button
          type="button"
          onClick={onRetake}
          className="mt-6 inline-flex w-full items-center justify-center gap-2 rounded-xl bg-brand-600 px-5 py-2.5 text-sm font-semibold text-white shadow-card transition hover:bg-brand-700"
        >
          <RotateCcw className="h-4 w-4" aria-hidden="true" />
          Try again with a new photo
        </button>
      </div>
    </div>
  );
}
