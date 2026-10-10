import { Info, Tags } from "lucide-react";
import type { ScanAnalysisResponse } from "@/lib/types";

/**
 * Presents a classification honestly by provenance:
 * - trained demonstration SVM (`model.kind === "svm"`): an ARTIFICIAL category
 *   from equal-width bands of the synthetic value range;
 * - mock fixture (glucose / urine albumin): an illustrative placeholder.
 *
 * Neutral styling only: no severity colors, no emergency indicators, no
 * diagnostic language. Labels are shown verbatim from the backend.
 */
export default function ClassificationCard({
  analysis,
}: {
  analysis: ScanAnalysisResponse;
}) {
  const classification = analysis.classification;
  const isDemoSvm = classification?.model?.kind === "svm";

  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-card">
      <div className="flex items-center justify-between">
        <h2 className="flex items-center gap-2 text-sm font-semibold uppercase tracking-wide text-slate-500">
          <Tags className="h-4 w-4 text-brand-600" aria-hidden="true" />
          {isDemoSvm ? "Demonstration category" : "Screening category"}
        </h2>
        {classification?.is_simulated && (
          <span className="rounded-full bg-slate-100 px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-wide text-slate-700">
            {isDemoSvm ? "Artificial" : "Mock"} · Simulated
          </span>
        )}
      </div>

      {classification && isDemoSvm ? (
        <>
          <p className="mt-3 break-words text-lg font-semibold text-slate-900">
            {classification.label}
          </p>
          <dl className="mt-3 space-y-1.5 text-xs text-slate-500">
            <div className="flex justify-between gap-4">
              <dt>Method</dt>
              <dd className="text-right font-medium text-slate-700">
                Demonstration SVM
              </dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt>Classifier</dt>
              <dd className="text-right font-medium text-slate-700">
                {classification.model?.identifier} v
                {classification.model?.version}
              </dd>
            </div>
          </dl>
          <p className="mt-3 flex items-start gap-2 rounded-lg bg-slate-50 px-3 py-2.5 text-xs leading-relaxed text-slate-600">
            <Info className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden="true" />
            <span>
              <span className="font-semibold">
                Artificial category based on synthetic training labels. Not a
                medical severity assessment.
              </span>{" "}
              The bands are equal-width slices of the synthetic value range
              and have no clinical meaning.
            </span>
          </p>
        </>
      ) : classification ? (
        <>
          <p className="mt-3 text-xl font-semibold capitalize text-slate-900">
            {classification.label.replace(/_/g, " ")}
          </p>
          <p className="mt-2 flex items-start gap-2 text-xs leading-relaxed text-slate-500">
            <Info className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden="true" />
            Mock fixture ({classification.method}): a fixed placeholder, not
            produced by a trained model and not derived from your image. It is
            not a diagnosis, a triage decision, or a measure of urgency.
          </p>
        </>
      ) : analysis.status === "success" ? (
        <p className="mt-3 rounded-lg bg-slate-50 px-3 py-2.5 text-sm leading-relaxed text-slate-600">
          No category is assigned to this scan. The simulated value above is
          still valid; the demonstration classifier was not available, and a
          category is never invented.
        </p>
      ) : (
        <p className="mt-3 rounded-lg bg-slate-50 px-3 py-2.5 text-sm leading-relaxed text-slate-600">
          No category was assigned because the scan did not pass image
          validation.
        </p>
      )}
    </section>
  );
}
