"use client";

import { useState } from "react";
import { ArrowRight, UserRound } from "lucide-react";
import { createPatient } from "@/lib/api";
import type { PatientResponse } from "@/lib/types";

type Sex = "female" | "male" | "other";

/**
 * Step 1 — minimal fictional patient details. Only age is required; the
 * display name and sex are optional and used solely for the demo session
 * and (when relevant) interpretation context.
 */
export default function PatientForm({
  onComplete,
}: {
  onComplete: (patient: PatientResponse) => void;
}) {
  const [displayName, setDisplayName] = useState("");
  const [age, setAge] = useState("");
  const [sex, setSex] = useState<Sex | "">("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  function validate(): string | null {
    if (age.trim() === "") return "Please enter an age.";
    const parsed = Number(age);
    if (!Number.isInteger(parsed) || parsed < 0 || parsed > 120) {
      return "Age must be a whole number between 0 and 120.";
    }
    if (displayName.trim().length > 80) {
      return "Display name must be 80 characters or fewer.";
    }
    return null;
  }

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    const validationError = validate();
    if (validationError) {
      setError(validationError);
      return;
    }
    setError(null);
    setSubmitting(true);
    try {
      const patient = await createPatient({
        age: Number(age),
        ...(sex ? { sex } : {}),
        ...(displayName.trim() ? { display_name: displayName.trim() } : {}),
      });
      onComplete(patient);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
    } finally {
      setSubmitting(false);
    }
  }

  const inputClass =
    "w-full rounded-lg border border-slate-300 px-3.5 py-2.5 text-sm text-slate-900 placeholder:text-slate-400 focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/30";

  return (
    <form
      onSubmit={handleSubmit}
      className="mx-auto w-full max-w-md rounded-2xl border border-slate-200 bg-white p-6 shadow-card sm:p-8"
      noValidate
    >
      <div className="flex items-center gap-3">
        <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-brand-50 text-brand-600">
          <UserRound className="h-5 w-5" aria-hidden="true" />
        </span>
        <div>
          <h2 className="text-lg font-semibold text-slate-900">Patient details</h2>
          <p className="text-xs text-slate-500">
            Use a fictional demo profile — no real personal health data.
          </p>
        </div>
      </div>

      <div className="mt-6 space-y-4">
        <div>
          <label htmlFor="display-name" className="mb-1.5 block text-sm font-medium text-slate-700">
            Display name <span className="font-normal text-slate-400">(optional, fictional)</span>
          </label>
          <input
            id="display-name"
            type="text"
            value={displayName}
            onChange={(e) => setDisplayName(e.target.value)}
            placeholder="e.g. Demo Patient A"
            className={inputClass}
            maxLength={80}
          />
        </div>

        <div>
          <label htmlFor="age" className="mb-1.5 block text-sm font-medium text-slate-700">
            Age <span className="text-rose-500">*</span>
          </label>
          <input
            id="age"
            type="number"
            inputMode="numeric"
            min={0}
            max={120}
            value={age}
            onChange={(e) => setAge(e.target.value)}
            placeholder="e.g. 34"
            className={inputClass}
            required
          />
        </div>

        <div>
          <label htmlFor="sex" className="mb-1.5 block text-sm font-medium text-slate-700">
            Sex <span className="font-normal text-slate-400">(optional — used when relevant to interpretation)</span>
          </label>
          <select
            id="sex"
            value={sex}
            onChange={(e) => setSex(e.target.value as Sex | "")}
            className={inputClass}
          >
            <option value="">Prefer not to say</option>
            <option value="female">Female</option>
            <option value="male">Male</option>
            <option value="other">Other</option>
          </select>
        </div>
      </div>

      {error && (
        <p role="alert" className="mt-4 rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-700">
          {error}
        </p>
      )}

      <button
        type="submit"
        disabled={submitting}
        className="mt-6 inline-flex w-full items-center justify-center gap-2 rounded-xl bg-brand-600 px-5 py-3 text-sm font-semibold text-white shadow-card transition hover:bg-brand-700 disabled:cursor-not-allowed disabled:opacity-60"
      >
        {submitting ? "Saving…" : "Continue"}
        {!submitting && <ArrowRight className="h-4 w-4" aria-hidden="true" />}
      </button>
    </form>
  );
}
