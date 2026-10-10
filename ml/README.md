# Aarogya Bindu — ML / Computer-Vision Module (Placeholder)

This directory will contain the independently developed machine-learning and
image-processing pipeline for Aarogya Bindu. **Nothing here is implemented
yet** — this README defines the integration boundary so backend and ML work
can proceed in parallel.

## Planned contents (Phases 2–3 of the roadmap)

- **Synthetic dataset generation** — standardized test-strip images with a
  reaction pad and calibration patches, plus fictional patient profiles.
- **OpenCV pipeline** — strip/pad detection, perspective alignment, quality
  checks (blur/glare/exposure), color calibration, and RGB/Lab feature
  extraction.
- **SVR regression** — `StandardScaler` + `SVR` (scikit-learn) estimating a
  *synthetic* intensity / fictional concentration from calibrated color
  features.
- **SVM classification** — `StandardScaler` + `SVC` (scikit-learn) assigning
  an *illustrative* screening category per test type.

## Integration contract

The ML module will expose a single function consumed by the backend through
`backend/app/services/inference.py` (the inference adapter):

```python
def analyze_strip(image, test_type, patient_info):
    # 1. Validate and inspect image
    # 2. Detect strip, calibrate, extract features
    # 3. Reject poor-quality scans (quality gate)
    # 4. Run experimental SVR estimate
    # 5. Run experimental SVM classification
    # 6. Return versioned, explainable structured result
```

Its return value must map onto the agreed API schema
(`backend/app/schemas.py::ScanAnalysisResponse`), including `source`,
`clinically_validated`, `is_simulated` flags, model identifier/version,
quality evidence, and limitations. Failed-quality scans must never produce
a measurement or classification.

> **Reminder:** all outputs are synthetic demonstrations and must remain
> labeled **SIMULATED — NOT FOR MEDICAL USE**. High accuracy against
> synthetic rule labels does not establish clinical validity.

See `Aarogya_Bindu_Development_and_ML_Roadmap.md` (root) sections 7–9 for
full details.
