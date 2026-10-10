"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import DisclaimerBanner from "@/components/DisclaimerBanner";
import Header from "@/components/Header";
import PatientForm from "@/components/screening/PatientForm";
import ProcessingState from "@/components/screening/ProcessingState";
import Stepper, { type ScreeningStep } from "@/components/screening/Stepper";
import StripScanner from "@/components/screening/StripScanner";
import TestSelector from "@/components/screening/TestSelector";
import { analyzeScan } from "@/lib/api";
import type { PatientResponse, TestMetadata } from "@/lib/types";

/**
 * Guided screening journey:
 * Patient details -> Test selection -> Image upload -> Analysis ->
 * redirect to the persisted report at /results/{scan_id}.
 *
 * Both successful and failed-quality scans navigate to the results page,
 * which fetches the saved report from the backend (no transient state).
 */
export default function ScreeningPage() {
  const router = useRouter();
  const [step, setStep] = useState<ScreeningStep>("patient");
  const [patient, setPatient] = useState<PatientResponse | null>(null);
  const [test, setTest] = useState<TestMetadata | null>(null);
  const [analyzeError, setAnalyzeError] = useState<string | null>(null);

  async function handleAnalyze(file: File) {
    if (!patient || !test) return;
    setAnalyzeError(null);
    setStep("processing");
    try {
      const response = await analyzeScan({
        patientId: patient.patient_id,
        testType: test.id,
        image: file,
      });
      // The scan (success or quality_failed) is persisted server-side;
      // hand off to the report page, which fetches it by ID.
      router.push(`/results/${response.scan_id}`);
    } catch (err) {
      setAnalyzeError(
        err instanceof Error ? err.message : "Analysis failed unexpectedly."
      );
      setStep("upload");
    }
  }

  return (
    <div className="flex min-h-screen flex-col">
      <DisclaimerBanner />
      <Header />
      <main className="flex-1 bg-clinical-grid px-4 py-10 sm:py-14">
        <Stepper current={step} />

        {patient && step !== "patient" && (
          <p className="mt-4 text-center text-xs text-slate-500">
            Demo profile:{" "}
            <span className="font-medium text-slate-700">
              {patient.display_name ?? "Anonymous"} · age {patient.age}
              {patient.sex ? ` · ${patient.sex}` : ""}
            </span>
          </p>
        )}

        <div className="mt-8">
          {step === "patient" && (
            <PatientForm
              onComplete={(created) => {
                setPatient(created);
                setStep("test");
              }}
            />
          )}

          {step === "test" && (
            <TestSelector
              selected={test}
              onSelect={setTest}
              onContinue={() => test && setStep("upload")}
            />
          )}

          {step === "upload" && test && (
            <StripScanner
              testName={test.name}
              disabled={false}
              serverError={analyzeError}
              onAnalyze={handleAnalyze}
            />
          )}

          {step === "processing" && test && (
            <ProcessingState testName={test.name} />
          )}
        </div>
      </main>
    </div>
  );
}
