import Link from "next/link";
import type { Metadata } from "next";
import { ArrowLeft, Construction } from "lucide-react";
import DisclaimerBanner from "@/components/DisclaimerBanner";
import Header from "@/components/Header";

export const metadata: Metadata = {
  title: "Start Screening — Aarogya Bindu",
};

const PLANNED_STEPS = [
  "Patient details (demo profile)",
  "Diagnostic test selection",
  "Test-strip image upload",
  "Scan processing with quality checks",
  "Explainable screening result",
  "Downloadable PDF report",
];

/**
 * Placeholder for the screening journey. The patient form, test selection,
 * scanner, results, and report download are scheduled for the next
 * development iterations — this page exists so the landing CTA has an
 * honest, clearly labeled destination.
 */
export default function ScreeningPlaceholderPage() {
  return (
    <div className="flex min-h-screen flex-col">
      <DisclaimerBanner />
      <Header />
      <main className="flex flex-1 items-center justify-center bg-clinical-grid px-4 py-16">
        <div className="w-full max-w-lg rounded-2xl border border-slate-200 bg-white p-8 text-center shadow-card">
          <span className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-brand-50 text-brand-600">
            <Construction className="h-7 w-7" aria-hidden="true" />
          </span>
          <h1 className="mt-5 text-2xl font-bold tracking-tight text-slate-900">
            Screening journey — coming next
          </h1>
          <p className="mt-3 text-sm leading-relaxed text-slate-600">
            This is a placeholder page. The guided screening flow is being
            built in the next development iteration and will walk you through:
          </p>
          <ol className="mx-auto mt-6 max-w-xs space-y-2.5 text-left">
            {PLANNED_STEPS.map((step, index) => (
              <li
                key={step}
                className="flex items-center gap-3 rounded-lg border border-slate-100 bg-slate-50 px-3 py-2 text-sm text-slate-700"
              >
                <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-brand-600 text-xs font-bold text-white">
                  {index + 1}
                </span>
                {step}
              </li>
            ))}
          </ol>
          <p className="mt-6 text-xs leading-relaxed text-slate-500">
            All demonstration results will be labeled{" "}
            <span className="font-semibold text-amber-600">
              SIMULATED — NOT FOR MEDICAL USE
            </span>
            .
          </p>
          <Link
            href="/"
            className="mt-6 inline-flex items-center gap-2 rounded-xl border border-slate-300 bg-white px-5 py-2.5 text-sm font-semibold text-slate-700 transition hover:border-brand-300 hover:text-brand-700"
          >
            <ArrowLeft className="h-4 w-4" aria-hidden="true" />
            Back to home
          </Link>
        </div>
      </main>
    </div>
  );
}
