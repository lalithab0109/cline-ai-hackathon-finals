import { Loader2 } from "lucide-react";

/**
 * Step 4 — honest processing state. A single indeterminate indicator:
 * the mock analysis runs in one request, so no fabricated backend stages
 * (e.g. fake "detecting strip…" progress) are shown.
 */
export default function ProcessingState({ testName }: { testName: string }) {
  return (
    <div
      className="mx-auto flex max-w-md flex-col items-center rounded-2xl border border-slate-200 bg-white px-8 py-14 text-center shadow-card"
      role="status"
      aria-live="polite"
    >
      <span className="flex h-16 w-16 items-center justify-center rounded-full bg-brand-50">
        <Loader2 className="h-8 w-8 animate-spin text-brand-600" aria-hidden="true" />
      </span>
      <h2 className="mt-5 text-lg font-semibold text-slate-900">
        Analyzing your {testName} strip
      </h2>
      <p className="mt-2 text-sm leading-relaxed text-slate-500">
        Uploading the photo and running the demonstration analysis. This
        usually takes a few seconds — please don&apos;t close this page.
      </p>
    </div>
  );
}
