import { Activity, Droplets, TestTube2 } from "lucide-react";

const TESTS = [
  {
    name: "Hemoglobin",
    sample: "Blood sample",
    unit: "g/dL",
    icon: Droplets,
    accent: "bg-rose-50 text-rose-600",
    description:
      "Preliminary anemia-style screening from a blood-based colorimetric test strip.",
  },
  {
    name: "Glucose",
    sample: "Blood sample",
    unit: "mg/dL",
    icon: Activity,
    accent: "bg-sky-50 text-sky-600",
    description:
      "Preliminary glucose screening using a compatible blood-based colorimetric assay strip.",
  },
  {
    name: "Urine Albumin",
    sample: "Urine sample",
    unit: "mg/L",
    icon: TestTube2,
    accent: "bg-brand-50 text-brand-600",
    description:
      "Preliminary urine albumin screening from a urine-based colorimetric test strip.",
  },
];

export default function TestCards() {
  return (
    <section id="tests" className="mx-auto max-w-6xl px-4 py-16 sm:px-6 lg:py-24">
      <div className="mx-auto max-w-2xl text-center">
        <h2 className="text-3xl font-bold tracking-tight text-slate-900">
          Supported screening tests
        </h2>
        <p className="mt-3 text-slate-600">
          Three colorimetric screening modes, each with its own sample type,
          units, and interpretation boundaries.
        </p>
      </div>

      <div className="mt-12 grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
        {TESTS.map((test) => (
          <article
            key={test.name}
            className="rounded-2xl border border-slate-200 bg-white p-6 shadow-card transition hover:-translate-y-0.5 hover:border-brand-200"
          >
            <div className="flex items-center justify-between">
              <span
                className={`flex h-11 w-11 items-center justify-center rounded-xl ${test.accent}`}
              >
                <test.icon className="h-6 w-6" aria-hidden="true" />
              </span>
              <span className="rounded-full bg-slate-100 px-2.5 py-1 text-[11px] font-semibold text-slate-600">
                {test.sample}
              </span>
            </div>
            <h3 className="mt-4 text-lg font-semibold text-slate-900">
              {test.name}
            </h3>
            <p className="mt-2 text-sm leading-relaxed text-slate-600">
              {test.description}
            </p>
            <p className="mt-4 text-xs font-medium text-slate-400">
              Reported in {test.unit} · demonstration only
            </p>
          </article>
        ))}
      </div>
    </section>
  );
}
