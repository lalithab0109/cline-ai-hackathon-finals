import { ScanSearch } from "lucide-react";
import type { ScanAnalysisResponse } from "@/lib/types";

function swatch(rgb: [number, number, number]): string {
  return `rgb(${Math.round(rgb[0])}, ${Math.round(rgb[1])}, ${Math.round(rgb[2])})`;
}

/**
 * Image-analysis evidence: quality gate, calibration, and color features.
 * Built to accommodate future OpenCV outputs (RGB/Lab means, synthetic
 * intensity, annotated strip image); in mock mode it states plainly that
 * no image colors were analyzed.
 */
export default function ImageAnalysisCard({
  analysis,
}: {
  analysis: ScanAnalysisResponse;
}) {
  const { quality, image_analysis: image } = analysis;

  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-card">
      <div className="flex items-center justify-between">
        <h2 className="flex items-center gap-2 text-sm font-semibold uppercase tracking-wide text-slate-500">
          <ScanSearch className="h-4 w-4 text-brand-600" aria-hidden="true" />
          Image analysis
        </h2>
        <span
          className={`rounded-full px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-wide ${
            quality.passed
              ? "bg-brand-100 text-brand-800"
              : "bg-rose-100 text-rose-800"
          }`}
        >
          Quality {quality.passed ? "passed" : "failed"}
        </span>
      </div>

      {quality.issues.length > 0 && (
        <ul className="mt-3 space-y-1.5">
          {quality.issues.map((issue) => (
            <li
              key={issue}
              className="rounded-lg bg-rose-50 px-3 py-2 text-xs leading-relaxed text-rose-700"
            >
              {issue}
            </li>
          ))}
        </ul>
      )}

      <dl className="mt-4 space-y-1.5 text-xs text-slate-500">
        {quality.blur_score !== null && (
          <div className="flex justify-between gap-4">
            <dt>Blur score</dt>
            <dd className="font-medium text-slate-700">{quality.blur_score}</dd>
          </div>
        )}
        {quality.calibration_detected !== null && (
          <div className="flex justify-between gap-4">
            <dt>Calibration patches</dt>
            <dd className="font-medium text-slate-700">
              {quality.calibration_detected ? "Detected" : "Not detected"}
            </dd>
          </div>
        )}
        {quality.calibration_error !== null && (
          <div className="flex justify-between gap-4">
            <dt>Calibration error</dt>
            <dd className="font-medium text-slate-700">
              {quality.calibration_error}
            </dd>
          </div>
        )}
      </dl>

      {image ? (
        <div className="mt-4 space-y-3 border-t border-slate-100 pt-4">
          {image.mean_rgb && (
            <div className="flex items-center justify-between text-xs">
              <span className="text-slate-500">
                Mean pad RGB ({image.mean_rgb.map((v) => Math.round(v)).join(", ")})
              </span>
              <span
                className="h-6 w-10 rounded-md border border-slate-200"
                style={{ backgroundColor: swatch(image.mean_rgb) }}
                aria-label="Mean reaction-pad color swatch"
              />
            </div>
          )}
          {image.mean_lab && (
            <p className="text-xs text-slate-500">
              Mean Lab: {image.mean_lab.map((v) => v.toFixed(1)).join(", ")}
            </p>
          )}
          {image.synthetic_intensity !== null && (
            <p className="text-xs text-slate-500">
              Synthetic intensity: {image.synthetic_intensity}
            </p>
          )}
          {image.annotated_image_url && (
            <p className="text-xs text-slate-500">
              Annotated strip: {image.annotated_image_url}
            </p>
          )}
        </div>
      ) : (
        <p className="mt-4 rounded-lg bg-sky-50 px-3 py-2.5 text-xs leading-relaxed text-sky-800">
          Mock inference is active: the uploaded photo was validated but its
          colors were <span className="font-semibold">not</span> analyzed.
          Calibrated RGB/Lab features and an annotated strip will appear here
          once the OpenCV pipeline is integrated.
        </p>
      )}
    </section>
  );
}
