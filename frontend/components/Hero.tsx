import Link from "next/link";
import { ArrowRight, ScanLine, ShieldAlert, Sparkles } from "lucide-react";

export default function Hero() {
  return (
    <section className="bg-clinical-grid relative overflow-hidden bg-white">
      <div className="pointer-events-none absolute inset-x-0 top-0 h-64 bg-gradient-to-b from-brand-50 to-transparent" />
      <div className="relative mx-auto grid max-w-6xl items-center gap-12 px-4 pb-20 pt-16 sm:px-6 lg:grid-cols-2 lg:pb-28 lg:pt-24">
        <div>
          <span className="inline-flex items-center gap-1.5 rounded-full border border-brand-200 bg-brand-50 px-3 py-1 text-xs font-semibold text-brand-700">
            <Sparkles className="h-3.5 w-3.5" aria-hidden="true" />
            Hackathon prototype — colorimetric strip screening
          </span>
          <h1 className="mt-5 text-4xl font-extrabold leading-tight tracking-tight text-slate-900 sm:text-5xl">
            Preliminary health screening,{" "}
            <span className="bg-gradient-to-r from-brand-600 to-sky-600 bg-clip-text text-transparent">
              from a single drop.
            </span>
          </h1>
          <p className="mt-5 max-w-xl text-base leading-relaxed text-slate-600 sm:text-lg">
            Aarogya Bindu demonstrates how a smartphone photo of a diagnostic
            test strip could be turned into an explainable, patient-friendly
            preliminary screening report — from image capture to a clear
            summary you can download.
          </p>
          <div className="mt-8 flex flex-col gap-3 sm:flex-row">
            <Link
              href="/screening"
              className="inline-flex items-center justify-center gap-2 rounded-xl bg-brand-600 px-6 py-3 text-base font-semibold text-white shadow-card transition hover:bg-brand-700 focus:outline-none focus:ring-2 focus:ring-brand-500 focus:ring-offset-2"
            >
              Start Screening
              <ArrowRight className="h-5 w-5" aria-hidden="true" />
            </Link>
            <a
              href="#how-it-works"
              className="inline-flex items-center justify-center gap-2 rounded-xl border border-slate-300 bg-white px-6 py-3 text-base font-semibold text-slate-700 transition hover:border-brand-300 hover:text-brand-700"
            >
              <ScanLine className="h-5 w-5" aria-hidden="true" />
              How it works
            </a>
          </div>
          <p className="mt-6 flex items-start gap-2 text-xs leading-relaxed text-slate-500 sm:text-sm">
            <ShieldAlert
              className="mt-0.5 h-4 w-4 shrink-0 text-amber-500"
              aria-hidden="true"
            />
            Demonstration results use synthetic data and illustrative models.
            They are not medical diagnoses. Always consult a qualified
            clinician for health concerns.
          </p>
        </div>

        <HeroPreviewCard />
      </div>
    </section>
  );
}

/** Illustrative, clearly-labeled preview of a simulated screening result. */
function HeroPreviewCard() {
  return (
    <div className="relative mx-auto w-full max-w-md">
      <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-card">
        <div className="flex items-center justify-between">
          <p className="text-sm font-semibold text-slate-900">
            Screening Report Preview
          </p>
          <span className="rounded-full bg-amber-100 px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-wide text-amber-800">
            Simulated
          </span>
        </div>

        <div className="mt-4 rounded-xl bg-slate-50 p-4">
          <p className="text-xs font-medium uppercase tracking-wide text-slate-500">
            Hemoglobin (blood)
          </p>
          <p className="mt-1 text-3xl font-bold text-slate-900">
            9.2 <span className="text-base font-medium text-slate-500">g/dL</span>
          </p>
          <p className="mt-1 text-xs text-slate-500">
            Illustrative category:{" "}
            <span className="font-semibold text-amber-700">
              moderate abnormality
            </span>
          </p>
        </div>

        <div className="mt-4 space-y-2.5">
          {[
            "Scan quality gate passed",
            "Calibrated color features extracted",
            "Experimental estimate + illustrative category",
            "Explainable, downloadable report",
          ].map((step) => (
            <div key={step} className="flex items-center gap-2.5 text-sm text-slate-600">
              <span className="h-1.5 w-1.5 rounded-full bg-brand-500" />
              {step}
            </div>
          ))}
        </div>

        <p className="mt-5 border-t border-dashed border-slate-200 pt-3 text-[11px] leading-relaxed text-slate-400">
          All values on this card are fictional and shown only to illustrate
          the interface. SIMULATED — NOT FOR MEDICAL USE.
        </p>
      </div>
    </div>
  );
}
