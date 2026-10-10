import { CalendarClock, Fingerprint, FlaskConical } from "lucide-react";
import type { ScreeningReportResponse } from "@/lib/types";

function formatDate(iso: string): string {
  const date = new Date(iso);
  return Number.isNaN(date.getTime()) ? iso : date.toLocaleString();
}

/** Report masthead: test, date, session identifier, simulation notice. */
export default function ReportHeader({
  report,
}: {
  report: ScreeningReportResponse;
}) {
  return (
    <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-card">
      <div className="bg-gradient-to-r from-brand-600 to-sky-600 px-6 py-5 text-white">
        <p className="text-xs font-semibold uppercase tracking-widest text-brand-100">
          Screening Report
        </p>
        <h1 className="mt-1 text-2xl font-bold">{report.test.name} Screening</h1>
        <p className="mt-1 text-sm text-brand-50">
          {report.test.sample_type} sample ·{" "}
          {report.patient.display_name ?? "Anonymous demo profile"} · age{" "}
          {report.patient.age}
          {report.patient.sex ? ` · ${report.patient.sex}` : ""}
        </p>
      </div>

      <div className="flex flex-col gap-2 px-6 py-4 text-xs text-slate-500 sm:flex-row sm:items-center sm:justify-between">
        <span className="inline-flex items-center gap-1.5">
          <CalendarClock className="h-4 w-4" aria-hidden="true" />
          {formatDate(report.created_at)}
        </span>
        <span className="inline-flex items-center gap-1.5">
          <Fingerprint className="h-4 w-4" aria-hidden="true" />
          Session {report.scan_id}
        </span>
        <span className="inline-flex items-center gap-1.5 font-semibold text-amber-700">
          <FlaskConical className="h-4 w-4" aria-hidden="true" />
          SIMULATED — NOT FOR MEDICAL USE
        </span>
      </div>
    </div>
  );
}
