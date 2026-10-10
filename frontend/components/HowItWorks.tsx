import {
  ClipboardList,
  FileDown,
  FlaskConical,
  ScanSearch,
  UploadCloud,
  UserRound,
} from "lucide-react";

const STEPS = [
  {
    icon: UserRound,
    title: "Patient details",
    text: "Enter minimal demo details — age and, when relevant, sex. No real personal health data needed.",
  },
  {
    icon: FlaskConical,
    title: "Select a test",
    text: "Choose hemoglobin, glucose, or urine albumin screening with plain-language guidance.",
  },
  {
    icon: UploadCloud,
    title: "Upload strip photo",
    text: "Capture or upload a photo of the diagnostic test strip with your smartphone.",
  },
  {
    icon: ScanSearch,
    title: "Image analysis",
    text: "Computer vision locates the strip, checks scan quality, and reads calibrated color features.",
  },
  {
    icon: ClipboardList,
    title: "Explainable result",
    text: "See the measurement, illustrative screening category, quality evidence, and honest limitations.",
  },
  {
    icon: FileDown,
    title: "Download report",
    text: "Save a clearly labeled PDF report with full provenance of how the result was generated.",
  },
];

export default function HowItWorks() {
  return (
    <section
      id="how-it-works"
      className="border-y border-slate-200 bg-white py-16 lg:py-24"
    >
      <div className="mx-auto max-w-6xl px-4 sm:px-6">
        <div className="mx-auto max-w-2xl text-center">
          <h2 className="text-3xl font-bold tracking-tight text-slate-900">
            How it works
          </h2>
          <p className="mt-3 text-slate-600">
            A transparent pipeline from a smartphone photo to a report patients
            can understand — every step shows its evidence.
          </p>
        </div>

        <ol className="mt-12 grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {STEPS.map((step, index) => (
            <li
              key={step.title}
              className="relative rounded-2xl border border-slate-200 bg-slate-50/60 p-6"
            >
              <span className="absolute right-5 top-5 text-sm font-bold text-slate-300">
                {String(index + 1).padStart(2, "0")}
              </span>
              <span className="flex h-11 w-11 items-center justify-center rounded-xl bg-brand-600/10 text-brand-700">
                <step.icon className="h-6 w-6" aria-hidden="true" />
              </span>
              <h3 className="mt-4 text-base font-semibold text-slate-900">
                {step.title}
              </h3>
              <p className="mt-2 text-sm leading-relaxed text-slate-600">
                {step.text}
              </p>
            </li>
          ))}
        </ol>
      </div>
    </section>
  );
}
