"use client";

import { useState } from "react";
import DisclaimerBanner from "@/components/DisclaimerBanner";
import Header from "@/components/Header";
import PatientForm from "@/components/screening/PatientForm";
import ProcessingState from "@/components/screening/ProcessingState";
import ScanResultSummary from "@/components/screening/ScanResultSummary";
import Stepper, { type ScreeningStep } from "@/components/screening/Stepper";
import StripScanner from "@/components/screening/StripScanner";
import TestSelector from "@/components/screening/TestSelector";
import { analyzeScan } from "@/lib/api";
import type {
  PatientResponse,
  ScanAnalysisResponse,
  TestMetadata,
} from "@/lib/types";

/**
 * Guided screening journey:
 * Patient details -> Test selection -> Image upload -> Mock analysis ->
 * Saved screening session (result summary).
 *
 * All data flows through the typed API client; no inference logic or
 * hardcoded responses live in components.
 */
export default function ScreeningPage() {
  const [step, setStep] = useState<ScreeningStep>("patient");
  const [patient, setPatient] = useState<PatientResponse | null>(null);
  const [test, setTest] = useState<TestMetadata | null>(null);
  const [result, setResult] = useState<ScanAnalysisResponse | null>(null);
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
      setResult(response);
      setStep("result");
    } catch (err) {
      setAnalyzeError(
        err instanceof Error ? err.message : "Analysis failed unexpectedly."
      );
      setStep("upload");
    }
  }

  function handleRetake() {
    setResult(null);
    setAnalyzeError(null);
    setStep("upload");
  }

  function handleNewScreening() {
    // Keep the demo patient; choose a new test and photo.
    setTest(null);
    setResult(null);
    setAnalyzeError(null);
    setStep("test");
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

          {step === "result" && result && test && (
            <ScanResultSummary
              result={result}
              test={test}
              onRetake={handleRetake}
              onNewScreening={handleNewScreening}
            />
          )}
        </div>
      </main>
    </div>
  );
}
