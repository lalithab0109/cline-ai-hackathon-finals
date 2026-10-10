import { Gauge } from "lucide-react";
import type { ScanAnalysisResponse } from "@/lib/types";

/**
 * Simulated measurement with unit, method, and provenance. Renders an
 * honest placeholder for failed scans — never an invented value.
 */
export default function MeasurementCard({
  analysis,
}: {
  analysis: ScanAnalysisResponse;
}) {
  const measurement = analysis.measurement;

  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-card">
      <div className="flex items-center justify-between">
        <h2 className="flex items-center gap-2 text-sm font-semibold uppercase tracking-wide text-slate-500">
          <Gauge className="h-4 w-4 text-brand-600" aria-hidden="true" />
          Measurement
        </h2>
        {measurement?.is_simulated && (
          <span className="rounded-full bg-amber-100 px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-wide text-amber-800">
            Simulated
          </span>
        )}
      </div>

      {measurement ? (
        <>
          <p className="mt-3 text-4xl font-bold text-slate-900">
            {measurement.value}{" "}
            <span className="text-lg font-medium text-slate-500">
              {measurement.unit}
            </span>
          </p>
          <dl className="mt-4 space-y-1.5 text-xs text-slate-500">
            <div className="flex justify-between gap-4">
              <dt>Estimation method</dt>
              <dd className="font-medium text-slate-700">{measurement.method}</dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt>Model</dt>
              <dd className="text-right font-medium text-slate-700">
                {analysis.model.identifier} v{analysis.model.version}
              </dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt>Data source</dt>
              <dd className="font-medium text-slate-700">{analysis.source}</dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt>Clinically validated</dt>
              <dd className="font-medium text-slate-700">
                {analysis.clinically_validated ? "Yes" : "No"}
              </dd>
            </div>
          </dl>
        </>
      ) : (
        <p className="mt-3 rounded-lg bg-slate-50 px-3 py-2.5 text-sm leading-relaxed text-slate-600">
          No measurement is available — this scan did not pass image
          validation, so no value was estimated.
        </p>
      )}
    </section>
  );
}
