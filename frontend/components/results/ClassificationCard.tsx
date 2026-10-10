import { Info, Tags } from "lucide-react";
import type { ScanAnalysisResponse } from "@/lib/types";

function formatLabel(label: string): string {
  return label.replace(/_/g, " ");
}

/**
 * Illustrative screening classification. Neutral/amber styling only — no
 * clinical emergency indicators for synthetic results.
 */
export default function ClassificationCard({
  analysis,
}: {
  analysis: ScanAnalysisResponse;
}) {
  const classification = analysis.classification;

  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-card">
      <div className="flex items-center justify-between">
        <h2 className="flex items-center gap-2 text-sm font-semibold uppercase tracking-wide text-slate-500">
          <Tags className="h-4 w-4 text-brand-600" aria-hidden="true" />
          Screening category
        </h2>
        {classification?.is_simulated && (
          <span className="rounded-full bg-amber-100 px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-wide text-amber-800">
            Simulated
          </span>
        )}
      </div>

      {classification ? (
        <>
          <p className="mt-3 text-xl font-semibold capitalize text-amber-700">
            {formatLabel(classification.label)}
          </p>
          <p className="mt-2 flex items-start gap-2 text-xs leading-relaxed text-slate-500">
            <Info className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden="true" />
            This label is an illustrative category produced by a demonstration
            classifier ({classification.method}). It describes the synthetic
            demo data only — it is not a diagnosis, a triage decision, or a
            measure of urgency.
          </p>
        </>
      ) : (
        <p className="mt-3 rounded-lg bg-slate-50 px-3 py-2.5 text-sm leading-relaxed text-slate-600">
          No screening category was assigned because the scan did not pass
          image validation.
        </p>
      )}
    </section>
  );
}
