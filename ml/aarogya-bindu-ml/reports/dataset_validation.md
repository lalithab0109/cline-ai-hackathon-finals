# Dataset validation report

> SIMULATED - NOT FOR MEDICAL USE. Trained and evaluated only on synthetic images whose colors come from an invented target-to-color mapping. Outputs are not hemoglobin measurements and are not clinically validated.

Overall: **PASS** - 600 images

| check | status | detail |
|---|---|---|
| sources_and_mapping | PASS | 1 source(s) ['contrib_a']; identical mapping 'synthetic_lab_linear_v1' |
| second_contributor | WARN | only one contributor dataset found; per-contributor comparison covers a single source |
| files_exist_and_readable | PASS | missing=[] unreadable=[] |
| rgb_dimensions_512x512 | PASS | bad=[] |
| file_hash_matches_manifest | PASS | mismatched=[] |
| target_finite_numeric | PASS | invalid=[] |
| target_within_documented_range | PASS | documented range [4.0, 18.0] g/dL |
| duplicate_ids_and_paths | PASS | dup_ids=[] dup_paths=[] |
| consistent_label_per_base_sample | PASS | conflicting=[] |
| duplicate_images_and_conflicting_labels | WARN | 9 identical-pixel group(s), max label spread 0.07 g/dL (8-bit quantization); united into one split group |
| grouping_metadata | PASS | 150 base samples; profiles ['challenging', 'clean', 'mild', 'moderate'] |
| contributor_distributions | PASS | per-source target statistics |
| dataset_type_synthetic | PASS | all rows marked synthetic |
| split_group_leakage | PASS | 141 split groups from 150 base samples; each group in exactly one split |

## Split counts

```
{
  "train": {
    "images": 424,
    "groups": 100,
    "target_mean": 10.911,
    "target_min": 4.2,
    "target_max": 17.91
  },
  "val": {
    "images": 92,
    "groups": 21,
    "target_mean": 11.038,
    "target_min": 4.79,
    "target_max": 17.7
  },
  "test": {
    "images": 84,
    "groups": 20,
    "target_mean": 11.393,
    "target_min": 4.08,
    "target_max": 17.02
  }
}
```
