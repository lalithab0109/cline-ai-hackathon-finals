"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { AlertTriangle, Loader2 } from "lucide-react";
import DisclaimerBanner from "@/components/DisclaimerBanner";
import Header from "@/components/Header";
import ClassificationCard from "@/components/results/ClassificationCard";
import ExplainabilityPanel from "@/components/results/ExplainabilityPanel";
import ImageAnalysisCard from "@/components/results/ImageAnalysisCard";
import MeasurementCard from "@/components/results/MeasurementCard";
import ReportActions from "@/components/results/ReportActions";
import ReportAssistant from "@/components/results/ReportAssistant";
import ReportHeader from "@/components/results/ReportHeader";
import { ApiError, getReport } from "@/lib/api";
import type { ScreeningReportResponse } from "@/lib/types";

type FetchState =
  | { kind: "loading" }
  | { kind: "ready"; report: ScreeningReportResponse }
  | { kind: "not_found" }
  | { kind: "error"; message: string };

/**
 * /results/[id] — explainable screening report. All content is fetched
 * from GET /api/reports/{id}; no report data comes from transient wizard
 * state, so refresh and direct links work.
 */
export default function ResultsPage() {
  const params = useParams<{ id: string }>();
  const [state, setState] = useState<FetchState>({ kind: "loading" });

  useEffect(() => {
    let cancelled = false;
    getReport(params.id)
      .then((report) => {
        if (!cancelled) setState({ kind: "ready", report });
      })
      .catch((err) => {
        if (cancelled) return;
        if (err instanceof ApiError && err.status === 404) {
          setState({ kind: "not_found" });
        } else {
          setState({
            kind: "error",
            message: err instanceof Error ? err.message : "Failed to load report.",
          });
        }
      });
    return () => {
      cancelled = true;
    };
  }, [params.id]);

  return (
    <div className="flex min-h-screen flex-col">
      <div className="print:hidden">
        <DisclaimerBanner />
        <Header />
      </div>

      <main className="flex-1 bg-clinical-grid px-4 py-10 sm:py-14">
        {state.kind === "loading" && (
          <div
            className="flex items-center justify-center gap-2 py-24 text-sm text-slate-500"
            role="status"
          >
            <Loader2 className="h-5 w-5 animate-spin" aria-hidden="true" />
            Loading your screening report…
          </div>
        )}

        {state.kind === "not_found" && (
          <StateCard
            title="Report not found"
            body="We couldn't find a screening report with this ID. It may have been removed, or the link may be incorrect."
          />
        )}

        {state.kind === "error" && (
          <StateCard title="Couldn't load the report" body={state.message} />
        )}

        {state.kind === "ready" && (
          <div className="mx-auto w-full max-w-2xl space-y-5">
            <ReportHeader report={state.report} />
            <div className="grid gap-5 sm:grid-cols-2">
              <MeasurementCard analysis={state.report.analysis} />
              <ClassificationCard analysis={state.report.analysis} />
            </div>
            <ImageAnalysisCard analysis={state.report.analysis} />
            <ExplainabilityPanel report={state.report} />
            <ReportAssistant report={state.report} />
            <ReportActions reportId={state.report.report_id} />
            <p className="text-center text-xs leading-relaxed text-slate-400">
              {state.report.disclaimer}. This demonstration report cannot
              diagnose or rule out any condition — consult a qualified
              clinician for health concerns.
            </p>
          </div>
        )}
      </main>
    </div>
  );
}

function StateCard({ title, body }: { title: string; body: string }) {
  return (
    <div className="mx-auto max-w-md rounded-2xl border border-slate-200 bg-white p-8 text-center shadow-card">
      <span className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl bg-amber-50 text-amber-600">
        <AlertTriangle className="h-6 w-6" aria-hidden="true" />
      </span>
      <h1 className="mt-4 text-lg font-semibold text-slate-900">{title}</h1>
      <p className="mt-2 text-sm leading-relaxed text-slate-600">{body}</p>
      <Link
        href="/screening"
        className="mt-6 inline-flex items-center justify-center rounded-xl bg-brand-600 px-5 py-2.5 text-sm font-semibold text-white shadow-card transition hover:bg-brand-700"
      >
        Start a new screening
      </Link>
    </div>
  );
}
