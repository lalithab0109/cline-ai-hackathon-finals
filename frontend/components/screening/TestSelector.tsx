"use client";

import { useEffect, useState } from "react";
import {
  Activity,
  ArrowRight,
  Droplets,
  Loader2,
  RefreshCw,
  TestTube2,
} from "lucide-react";
import { getTests } from "@/lib/api";
import type { TestMetadata, TestType } from "@/lib/types";

const TEST_ICONS: Record<TestType, typeof Droplets> = {
  hemoglobin: Droplets,
  glucose: Activity,
  urine_albumin: TestTube2,
};

const TEST_ACCENTS: Record<TestType, string> = {
  hemoglobin: "bg-rose-50 text-rose-600",
  glucose: "bg-sky-50 text-sky-600",
  urine_albumin: "bg-brand-50 text-brand-600",
};

/**
 * Step 2 — test selection. Metadata is fetched live from
 * GET /api/tests so card content always matches backend capabilities.
 */
export default function TestSelector({
  selected,
  onSelect,
  onContinue,
}: {
  selected: TestMetadata | null;
  onSelect: (test: TestMetadata) => void;
  onContinue: () => void;
}) {
  const [tests, setTests] = useState<TestMetadata[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  function load() {
    setError(null);
    getTests()
      .then((res) => setTests(res.tests))
      .catch((err) =>
        setError(err instanceof Error ? err.message : "Failed to load tests.")
      );
  }

  useEffect(load, []);

  if (error) {
    return (
      <div className="mx-auto max-w-md rounded-2xl border border-slate-200 bg-white p-8 text-center shadow-card">
        <p role="alert" className="text-sm text-rose-700">{error}</p>
        <button
          onClick={load}
          className="mt-4 inline-flex items-center gap-2 rounded-lg border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-700 hover:border-brand-300 hover:text-brand-700"
        >
          <RefreshCw className="h-4 w-4" aria-hidden="true" />
          Retry
        </button>
      </div>
    );
  }

  if (!tests) {
    return (
      <div className="flex items-center justify-center gap-2 py-16 text-sm text-slate-500">
        <Loader2 className="h-5 w-5 animate-spin" aria-hidden="true" />
        Loading supported tests…
      </div>
    );
  }

  return (
    <div className="mx-auto w-full max-w-3xl">
      <h2 className="text-center text-lg font-semibold text-slate-900">
        Choose a screening test
      </h2>
      <p className="mt-1 text-center text-sm text-slate-500">
        Each test uses its own sample type and units.
      </p>

      <div className="mt-6 grid gap-4 sm:grid-cols-3" role="radiogroup" aria-label="Screening test">
        {tests.map((test) => {
          const Icon = TEST_ICONS[test.id];
          const isSelected = selected?.id === test.id;
          return (
            <button
              key={test.id}
              type="button"
              role="radio"
              aria-checked={isSelected}
              onClick={() => onSelect(test)}
              className={`rounded-2xl border-2 bg-white p-5 text-left transition ${
                isSelected
                  ? "border-brand-600 shadow-card ring-2 ring-brand-500/20"
                  : "border-slate-200 hover:border-brand-300"
              }`}
            >
              <div className="flex items-center justify-between">
                <span
                  className={`flex h-10 w-10 items-center justify-center rounded-xl ${TEST_ACCENTS[test.id]}`}
                >
                  <Icon className="h-5 w-5" aria-hidden="true" />
                </span>
                <span
                  className={`flex h-5 w-5 items-center justify-center rounded-full border-2 ${
                    isSelected ? "border-brand-600 bg-brand-600" : "border-slate-300"
                  }`}
                  aria-hidden="true"
                >
                  {isSelected && <span className="h-2 w-2 rounded-full bg-white" />}
                </span>
              </div>
              <h3 className="mt-3 font-semibold text-slate-900">{test.name}</h3>
              <p className="mt-0.5 text-xs font-medium uppercase tracking-wide text-slate-400">
                {test.sample_type} sample · {test.unit}
              </p>
              <p className="mt-2 text-sm leading-relaxed text-slate-600">
                {test.description}
              </p>
            </button>
          );
        })}
      </div>

      <div className="mt-6 flex justify-center">
        <button
          type="button"
          onClick={onContinue}
          disabled={!selected}
          className="inline-flex items-center gap-2 rounded-xl bg-brand-600 px-6 py-3 text-sm font-semibold text-white shadow-card transition hover:bg-brand-700 disabled:cursor-not-allowed disabled:opacity-50"
        >
          Continue to upload
          <ArrowRight className="h-4 w-4" aria-hidden="true" />
        </button>
      </div>
    </div>
  );
}
