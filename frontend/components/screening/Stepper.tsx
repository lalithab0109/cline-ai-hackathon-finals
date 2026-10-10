import { Check } from "lucide-react";

export type ScreeningStep = "patient" | "test" | "upload" | "processing" | "result";

const STEPS: { id: ScreeningStep; label: string }[] = [
  { id: "patient", label: "Details" },
  { id: "test", label: "Test" },
  { id: "upload", label: "Upload" },
  { id: "result", label: "Result" },
];

const ORDER: ScreeningStep[] = ["patient", "test", "upload", "processing", "result"];

/** Progress indicator for the screening wizard. */
export default function Stepper({ current }: { current: ScreeningStep }) {
  const currentIndex = ORDER.indexOf(current);

  return (
    <ol className="flex items-center justify-center gap-2 sm:gap-3" aria-label="Screening progress">
      {STEPS.map((step, index) => {
        const stepIndex = ORDER.indexOf(step.id);
        const done = stepIndex < currentIndex || current === "result";
        const active = step.id === current || (current === "processing" && step.id === "upload");
        return (
          <li key={step.id} className="flex items-center gap-2 sm:gap-3">
            <span
              className={`flex h-8 w-8 items-center justify-center rounded-full text-xs font-bold transition ${
                done
                  ? "bg-brand-600 text-white"
                  : active
                    ? "border-2 border-brand-600 bg-white text-brand-700"
                    : "border border-slate-300 bg-white text-slate-400"
              }`}
              aria-current={active ? "step" : undefined}
            >
              {done ? <Check className="h-4 w-4" aria-hidden="true" /> : index + 1}
            </span>
            <span
              className={`hidden text-xs font-medium sm:inline ${
                active || done ? "text-slate-800" : "text-slate-400"
              }`}
            >
              {step.label}
            </span>
            {index < STEPS.length - 1 && (
              <span
                className={`h-px w-6 sm:w-10 ${done ? "bg-brand-500" : "bg-slate-200"}`}
                aria-hidden="true"
              />
            )}
          </li>
        );
      })}
    </ol>
  );
}
