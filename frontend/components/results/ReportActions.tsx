"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowLeft, FileDown, Plus } from "lucide-react";
import { getReportPdfUrl } from "@/lib/api";

/** Report actions: PDF download, start over, and back navigation. */
export default function ReportActions({ reportId }: { reportId: string }) {
  const router = useRouter();

  return (
    <div className="flex flex-col gap-3 print:hidden sm:flex-row">
      <a
        href={getReportPdfUrl(reportId)}
        download
        className="inline-flex flex-1 items-center justify-center gap-2 rounded-xl bg-brand-600 px-5 py-3 text-sm font-semibold text-white shadow-card transition hover:bg-brand-700"
      >
        <FileDown className="h-4 w-4" aria-hidden="true" />
        Download PDF report
      </a>
      <Link
        href="/screening"
        className="inline-flex flex-1 items-center justify-center gap-2 rounded-xl border border-slate-300 bg-white px-5 py-3 text-sm font-semibold text-slate-700 transition hover:border-brand-300 hover:text-brand-700"
      >
        <Plus className="h-4 w-4" aria-hidden="true" />
        Start new screening
      </Link>
      <button
        type="button"
        onClick={() => router.back()}
        className="inline-flex flex-1 items-center justify-center gap-2 rounded-xl border border-slate-300 bg-white px-5 py-3 text-sm font-semibold text-slate-700 transition hover:border-brand-300 hover:text-brand-700"
      >
        <ArrowLeft className="h-4 w-4" aria-hidden="true" />
        Back to screening
      </button>
    </div>
  );
}
