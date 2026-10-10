"use client";

import { useState } from "react";
import { ChevronDown, Layers } from "lucide-react";
import type { ScreeningReportResponse } from "@/lib/types";

/**
 * "How was this result generated?" — expandable evidence panel keeping a
 * clear separation between observed inputs, the estimated (simulated)
 * measurement, and the illustrative classification.
 */
export default function ExplainabilityPanel({
  report,
}: {
  report: ScreeningReportResponse;
}) {
  const [open, setOpen] = useState(false);
  const { analysis, patient } = report;
  const { explanation } = analysis;
  // Mock results are fixed fixtures; anything else came from the image pipeline.
  const isMock = analysis.source === "mock";

  return (
    <section className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-card">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="flex w-full items-center justify-between px-6 py-4 text-left transition hover:bg-slate-50"
      >
        <span className="flex items-center gap-2 text-sm font-semibold text-slate-900">
          <Layers className="h-4 w-4 text-brand-600" aria-hidden="true" />
          How was this result generated?
        </span>
        <ChevronDown
          className={`h-4 w-4 text-slate-400 transition-transform ${open ? "rotate-180" : ""}`}
          aria-hidden="true"
        />
      </button>

      {open && (
        <div className="space-y-5 border-t border-slate-100 px-6 py-5">
          <p className="text-sm leading-relaxed text-slate-600">
            {explanation.summary}
          </p>

          <div className="grid gap-3 sm:grid-cols-3">
            <div className="rounded-xl bg-slate-50 p-3.5">
              <h3 className="text-[11px] font-bold uppercase tracking-wide text-slate-500">
                Observed inputs
              </h3>
              <p className="mt-1.5 text-xs leading-relaxed text-slate-600">
                {isMock
                  ? `Age ${patient.age}${patient.sex ? `, sex ${patient.sex}` : ""}; a validated strip photo (its colors were not analyzed).`
                  : analysis.status === "success"
                    ? "Color features of the reaction area in the uploaded photo. Age and sex were not used by this model."
                    : "The uploaded photo, which could not be used."}
              </p>
            </div>
            <div className="rounded-xl bg-slate-50 p-3.5">
              <h3 className="text-[11px] font-bold uppercase tracking-wide text-slate-500">
                Estimated value
              </h3>
              <p className="mt-1.5 text-xs leading-relaxed text-slate-600">
                {analysis.measurement
                  ? isMock
                    ? `${analysis.measurement.value} ${analysis.measurement.unit} — a fixed simulated fixture, not read from the photo.`
                    : `${analysis.measurement.value} ${analysis.measurement.unit} — a simulated value estimated by a model trained on synthetic data. Not a laboratory measurement.`
                  : "None — the scan failed validation."}
              </p>
            </div>
            <div className="rounded-xl bg-slate-50 p-3.5">
              <h3 className="text-[11px] font-bold uppercase tracking-wide text-slate-500">
                {analysis.classification?.model?.kind === "svm"
                  ? "Demonstration category"
                  : "Illustrative category"}
              </h3>
              <p className="mt-1.5 text-xs leading-relaxed text-slate-600">
                {analysis.classification
                  ? analysis.classification.model?.kind === "svm"
                    ? `${analysis.classification.label} — an artificial category from a demonstration SVM trained on synthetic labels. Not a medical severity assessment.`
                    : `${analysis.classification.label.replace(/_/g, " ")} — a mock fixture, not a diagnosis.`
                  : analysis.status === "success"
                    ? "None — no category was assigned to this scan."
                    : "None assigned."}
              </p>
            </div>
          </div>

          {explanation.inputs_used.length > 0 && (
            <div>
              <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                {isMock ? "Inputs used by the classifier" : "Inputs used by the model"}
              </h3>
              <div className="mt-2 flex flex-wrap gap-1.5">
                {explanation.inputs_used.map((input) => (
                  <span
                    key={input}
                    className="rounded-full bg-brand-50 px-2.5 py-1 text-xs font-medium text-brand-700"
                  >
                    {input}
                  </span>
                ))}
              </div>
            </div>
          )}

          {explanation.limitations.length > 0 && (
            <div>
              <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                Limitations
              </h3>
              <ul className="mt-2 space-y-1.5">
                {explanation.limitations.map((item) => (
                  <li
                    key={item}
                    className="flex items-start gap-2 text-xs leading-relaxed text-slate-500"
                  >
                    <span className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-slate-400" />
                    {item}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {explanation.warnings.length > 0 && (
            <div className="space-y-1.5">
              {explanation.warnings.map((warning) => (
                <p
                  key={warning}
                  className="rounded-lg bg-amber-50 px-3 py-2 text-xs leading-relaxed text-amber-800"
                >
                  {warning}
                </p>
              ))}
            </div>
          )}
        </div>
      )}
    </section>
  );
}
