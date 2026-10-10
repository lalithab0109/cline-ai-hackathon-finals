import { AlertTriangle } from "lucide-react";

/**
 * Persistent prototype disclaimer. Every demonstration result in the app
 * must be visibly labeled "SIMULATED — NOT FOR MEDICAL USE".
 */
export default function DisclaimerBanner() {
  return (
    <div className="bg-amber-400 px-4 py-2 text-center">
      <p className="mx-auto flex max-w-4xl items-center justify-center gap-2 text-xs font-semibold tracking-wide text-amber-950 sm:text-sm">
        <AlertTriangle className="h-4 w-4 shrink-0" aria-hidden="true" />
        SIMULATED — NOT FOR MEDICAL USE. Aarogya Bindu is a technology
        demonstration and cannot diagnose, treat, or rule out any condition.
      </p>
    </div>
  );
}
