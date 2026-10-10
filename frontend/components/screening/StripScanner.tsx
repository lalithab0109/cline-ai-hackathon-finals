"use client";

import { useRef, useState } from "react";
import { ImageUp, ScanLine, X } from "lucide-react";

const ACCEPTED_TYPES = ["image/jpeg", "image/png", "image/webp"];
const MAX_BYTES = 10 * 1024 * 1024;

/**
 * Step 3 — test-strip image upload with drag-and-drop, file picker,
 * preview, and client-side type/size validation. The actual analysis is
 * triggered by the parent wizard via `onAnalyze`.
 */
export default function StripScanner({
  testName,
  disabled,
  serverError,
  onAnalyze,
}: {
  testName: string;
  disabled: boolean;
  serverError: string | null;
  onAnalyze: (file: File) => void;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);

  function acceptFile(candidate: File | undefined) {
    if (!candidate) return;
    if (!ACCEPTED_TYPES.includes(candidate.type)) {
      setError("Unsupported file type. Please use a JPG, PNG, or WebP photo.");
      return;
    }
    if (candidate.size > MAX_BYTES) {
      setError("The photo is larger than 10 MB. Please retake or compress it.");
      return;
    }
    if (candidate.size === 0) {
      setError("The selected file is empty. Please choose a photo of the test strip.");
      return;
    }
    setError(null);
    setFile(candidate);
    setPreviewUrl((previous) => {
      if (previous) URL.revokeObjectURL(previous);
      return URL.createObjectURL(candidate);
    });
  }

  function clearFile() {
    setFile(null);
    setError(null);
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    setPreviewUrl(null);
    if (inputRef.current) inputRef.current.value = "";
  }

  return (
    <div className="mx-auto w-full max-w-xl">
      <h2 className="text-center text-lg font-semibold text-slate-900">
        Upload your {testName} test strip
      </h2>
      <p className="mt-1 text-center text-sm text-slate-500">
        JPG, PNG, or WebP · up to 10 MB · good lighting, strip fully visible
      </p>

      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragging(false);
          acceptFile(e.dataTransfer.files?.[0]);
        }}
        className={`mt-6 rounded-2xl border-2 border-dashed bg-white p-6 text-center transition ${
          dragging ? "border-brand-500 bg-brand-50/50" : "border-slate-300"
        }`}
      >
        {previewUrl ? (
          <div className="space-y-4">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={previewUrl}
              alt="Preview of the selected test-strip photo"
              className="mx-auto max-h-64 rounded-xl border border-slate-200 object-contain"
            />
            <div className="flex items-center justify-center gap-3">
              <span className="max-w-[16rem] truncate text-sm text-slate-600">
                {file?.name}
              </span>
              <button
                type="button"
                onClick={clearFile}
                disabled={disabled}
                className="inline-flex items-center gap-1 rounded-lg border border-slate-300 px-3 py-1.5 text-xs font-semibold text-slate-600 hover:border-rose-300 hover:text-rose-600 disabled:opacity-50"
              >
                <X className="h-3.5 w-3.5" aria-hidden="true" />
                Remove
              </button>
            </div>
          </div>
        ) : (
          <button
            type="button"
            onClick={() => inputRef.current?.click()}
            className="flex w-full flex-col items-center gap-3 py-8 text-slate-500 transition hover:text-brand-700"
          >
            <span className="flex h-14 w-14 items-center justify-center rounded-2xl bg-brand-50 text-brand-600">
              <ImageUp className="h-7 w-7" aria-hidden="true" />
            </span>
            <span className="text-sm font-medium">
              Drag &amp; drop your strip photo here, or{" "}
              <span className="font-semibold text-brand-700 underline">browse files</span>
            </span>
          </button>
        )}

        <input
          ref={inputRef}
          type="file"
          accept={ACCEPTED_TYPES.join(",")}
          className="hidden"
          onChange={(e) => acceptFile(e.target.files?.[0])}
          aria-label="Choose a test-strip image"
        />
      </div>

      {(error || serverError) && (
        <p role="alert" className="mt-4 rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-700">
          {error ?? serverError}
        </p>
      )}

      <button
        type="button"
        onClick={() => file && onAnalyze(file)}
        disabled={!file || disabled}
        className="mt-6 inline-flex w-full items-center justify-center gap-2 rounded-xl bg-brand-600 px-6 py-3 text-sm font-semibold text-white shadow-card transition hover:bg-brand-700 disabled:cursor-not-allowed disabled:opacity-50"
      >
        <ScanLine className="h-4 w-4" aria-hidden="true" />
        Analyze strip
      </button>
    </div>
  );
}
