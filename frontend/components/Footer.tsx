import { Droplet } from "lucide-react";

export default function Footer() {
  return (
    <footer className="bg-slate-900 py-10 text-slate-300">
      <div className="mx-auto max-w-6xl px-4 sm:px-6">
        <div className="flex flex-col items-start justify-between gap-6 sm:flex-row sm:items-center">
          <div className="flex items-center gap-2.5">
            <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-brand-500 to-sky-600 text-white">
              <Droplet className="h-4 w-4" aria-hidden="true" />
            </span>
            <span className="text-base font-semibold text-white">
              Aarogya Bindu
            </span>
          </div>
          <p className="text-xs text-slate-400">
            Built for the Cline AI Builders Hackathon.
          </p>
        </div>
        <p className="mt-6 max-w-3xl border-t border-slate-800 pt-6 text-xs leading-relaxed text-slate-400">
          Aarogya Bindu is a technology prototype. All demonstration results
          are produced from synthetic data and illustrative models, are{" "}
          <span className="font-semibold text-amber-400">
            SIMULATED — NOT FOR MEDICAL USE
          </span>
          , and cannot diagnose, treat, or rule out any medical condition. A
          deployable diagnostic product would require real assay calibration
          data, clinical validation, and regulatory review.
        </p>
      </div>
    </footer>
  );
}
