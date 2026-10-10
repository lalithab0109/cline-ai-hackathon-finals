# Evaluation report (TEST split, evaluated once)

> SIMULATED - NOT FOR MEDICAL USE. Trained and evaluated only on synthetic images whose colors come from an invented target-to-color mapping. Outputs are not hemoglobin measurements and are not clinically validated.

Model: `svr_rbf__normalized` {'svr__C': 10, 'svr__epsilon': 0.05, 'svr__gamma': 0.01}

## Overall

| subset | n | MAE | RMSE | R2 | bias | within 1.0 |
|---|---|---|---|---|---|---|
| TEST selected SVR | 83 | 0.3873 | 0.5816 | 0.9813 | -0.0329 | 0.8916 |
| VAL selected SVR | 92 | 0.3875 | 0.6029 | 0.9796 | -0.1026 | 0.8913 |
| VAL baseline dummy_mean | 92 | 3.7126 | 4.2192 | -0.0009 | -0.1276 | 0.087 |
| TEST baseline dummy_mean | 83 | 3.7481 | 4.2868 | -0.0165 | -0.5467 | 0.1446 |
| VAL baseline linear_regression__raw_color | 92 | 0.5781 | 0.8864 | 0.9558 | -0.0125 | 0.7935 |
| VAL baseline linear_regression__normalized | 92 | 0.4406 | 0.6422 | 0.9768 | -0.0183 | 0.8913 |
| TEST baseline linear_regression__normalized | 83 | 0.4452 | 0.6437 | 0.9771 | 0.0502 | 0.9036 |

## Candidates (validation)

| subset | n | MAE | RMSE | R2 | bias | within 1.0 |
|---|---|---|---|---|---|---|
| svr_linear__raw_color | 92 | 0.5641 | 0.9155 | 0.9529 | 0.008 | 0.8261 |
| svr_rbf__raw_color | 92 | 0.5384 | 0.8949 | 0.955 | 0.0637 | 0.8152 |
| svr_linear__normalized | 92 | 0.4059 | 0.6185 | 0.9785 | -0.1185 | 0.9022 |
| svr_rbf__normalized | 92 | 0.3875 | 0.6029 | 0.9796 | -0.1026 | 0.8913 |

## By augmentation profile

| subset | n | MAE | RMSE | R2 | bias | within 1.0 |
|---|---|---|---|---|---|---|
| challenging | 20 | 0.806 | 0.9816 | 0.9422 | -0.1798 | 0.65 |
| clean | 21 | 0.1189 | 0.1899 | 0.9981 | 0.1044 | 1.0 |
| mild | 21 | 0.1849 | 0.2318 | 0.9971 | -0.0008 | 1.0 |
| moderate | 21 | 0.4592 | 0.5741 | 0.9822 | -0.0623 | 0.9048 |

## By target range

| subset | n | MAE | RMSE | R2 | bias | within 1.0 |
|---|---|---|---|---|---|---|
| (10.0, 13.0] | 16 | 0.4435 | 0.6992 | -0.2564 | -0.0346 | 0.75 |
| (13.0, 16.0] | 24 | 0.3359 | 0.5376 | 0.3328 | -0.0875 | 0.9167 |
| (16.0, 18.0] | 12 | 0.2515 | 0.4145 | -3.8424 | -0.1234 | 0.9167 |
| (3.999, 7.0] | 19 | 0.4453 | 0.5446 | 0.7095 | 0.1944 | 0.9474 |
| (7.0, 10.0] | 12 | 0.4589 | 0.6843 | -3.1128 | -0.1908 | 0.9167 |

## By contributor source

| subset | n | MAE | RMSE | R2 | bias | within 1.0 |
|---|---|---|---|---|---|---|
| contrib_a | 83 | 0.3873 | 0.5816 | 0.9813 | -0.0329 | 0.8916 |

## By brightness_factor (terciles)

| subset | n | MAE | RMSE | R2 | bias | within 1.0 |
|---|---|---|---|---|---|---|
| (0.81, 1.0] | 46 | 0.2135 | 0.3171 | 0.9942 | 0.0943 | 0.9783 |
| (1.0, 1.025] | 9 | 0.276 | 0.3363 | 0.9918 | -0.1576 | 1.0 |
| (1.025, 1.196] | 28 | 0.7085 | 0.8951 | 0.9596 | -0.2018 | 0.7143 |

## By blur_level (terciles)

| subset | n | MAE | RMSE | R2 | bias | within 1.0 |
|---|---|---|---|---|---|---|
| (-0.001, 0.162] | 28 | 0.1469 | 0.2115 | 0.9977 | 0.0526 | 1.0 |
| (0.162, 1.031] | 27 | 0.3565 | 0.5101 | 0.9849 | 0.1097 | 0.8889 |
| (1.031, 2.467] | 28 | 0.6573 | 0.8409 | 0.9596 | -0.2558 | 0.7857 |

## By noise_level (terciles)

| subset | n | MAE | RMSE | R2 | bias | within 1.0 |
|---|---|---|---|---|---|---|
| (-0.001, 0.793] | 28 | 0.1464 | 0.2136 | 0.9976 | 0.0881 | 1.0 |
| (0.793, 3.916] | 27 | 0.2706 | 0.348 | 0.9934 | -0.0369 | 1.0 |
| (3.916, 9.932] | 28 | 0.7406 | 0.9167 | 0.9475 | -0.15 | 0.6786 |

## By rotation_degrees (terciles)

| subset | n | MAE | RMSE | R2 | bias | within 1.0 |
|---|---|---|---|---|---|---|
| (-0.001, 0.465] | 28 | 0.1595 | 0.2397 | 0.997 | 0.0943 | 1.0 |
| (0.465, 2.435] | 27 | 0.3143 | 0.4339 | 0.9884 | -0.0061 | 0.9259 |
| (2.435, 9.789] | 28 | 0.6854 | 0.8739 | 0.959 | -0.1859 | 0.75 |

## By perspective_strength (terciles)

| subset | n | MAE | RMSE | R2 | bias | within 1.0 |
|---|---|---|---|---|---|---|
| (-0.001, 0.00138] | 28 | 0.2052 | 0.3908 | 0.9915 | 0.0682 | 0.9286 |
| (0.00138, 0.00882] | 27 | 0.3862 | 0.5416 | 0.9831 | -0.1435 | 0.9259 |
| (0.00882, 0.0448] | 28 | 0.5703 | 0.7531 | 0.9699 | -0.0273 | 0.8214 |

## By apparent_delta_e_vs_clean (terciles)

| subset | n | MAE | RMSE | R2 | bias | within 1.0 |
|---|---|---|---|---|---|---|
| (-0.001, 2.056] | 28 | 0.1058 | 0.1691 | 0.9984 | 0.0768 | 1.0 |
| (2.056, 6.083] | 27 | 0.3383 | 0.4255 | 0.9897 | -0.0572 | 0.963 |
| (6.083, 24.213] | 28 | 0.716 | 0.8942 | 0.9554 | -0.1191 | 0.7143 |

## Excluded by quality gate

```
[
  {
    "uid": "contrib_a:IMG000072",
    "augmentation_profile": "challenging",
    "pre_issues": "overexposed_or_clipped_roi (29.0% pixels with >=2 saturated channels > 5%)"
  }
]
```

## Worst 10 test predictions

```
[
  {
    "uid": "contrib_a:IMG000304",
    "augmentation_profile": "challenging",
    "target_hb_g_dl": 8.68,
    "svr_pred": 6.751,
    "abs_err": 1.929,
    "brightness_factor": 1.196,
    "blur_level": 2.169,
    "noise_level": 9.932,
    "rotation_degrees": 6.866
  },
  {
    "uid": "contrib_a:IMG000056",
    "augmentation_profile": "challenging",
    "target_hb_g_dl": 11.37,
    "svr_pred": 9.565,
    "abs_err": 1.805,
    "brightness_factor": 1.137,
    "blur_level": 1.272,
    "noise_level": 9.407,
    "rotation_degrees": -5.617
  },
  {
    "uid": "contrib_a:IMG000356",
    "augmentation_profile": "challenging",
    "target_hb_g_dl": 15.74,
    "svr_pred": 14.155,
    "abs_err": 1.585,
    "brightness_factor": 1.088,
    "blur_level": 1.763,
    "noise_level": 8.65,
    "rotation_degrees": -3.523
  },
  {
    "uid": "contrib_a:IMG000324",
    "augmentation_profile": "challenging",
    "target_hb_g_dl": 14.62,
    "svr_pred": 13.111,
    "abs_err": 1.509,
    "brightness_factor": 1.11,
    "blur_level": 1.252,
    "noise_level": 4.214,
    "rotation_degrees": -7.19
  },
  {
    "uid": "contrib_a:IMG000592",
    "augmentation_profile": "challenging",
    "target_hb_g_dl": 10.64,
    "svr_pred": 11.996,
    "abs_err": 1.356,
    "brightness_factor": 1.044,
    "blur_level": 1.018,
    "noise_level": 7.56,
    "rotation_degrees": 2.891
  },
  {
    "uid": "contrib_a:IMG000583",
    "augmentation_profile": "moderate",
    "target_hb_g_dl": 5.59,
    "svr_pred": 6.881,
    "abs_err": 1.291,
    "brightness_factor": 1.032,
    "blur_level": 0.968,
    "noise_level": 4.177,
    "rotation_degrees": 2.918
  },
  {
    "uid": "contrib_a:IMG000208",
    "augmentation_profile": "challenging",
    "target_hb_g_dl": 17.02,
    "svr_pred": 15.857,
    "abs_err": 1.163,
    "brightness_factor": 0.977,
    "blur_level": 1.943,
    "noise_level": 7.021,
    "rotation_degrees": -1.648
  },
  {
    "uid": "contrib_a:IMG000059",
    "augmentation_profile": "moderate",
    "target_hb_g_dl": 11.59,
    "svr_pred": 10.463,
    "abs_err": 1.127,
    "brightness_factor": 1.085,
    "blur_level": 0.524,
    "noise_level": 4.517,
    "rotation_degrees": 3.63
  },
  {
    "uid": "contrib_a:IMG000524",
    "augmentation_profile": "challenging",
    "target_hb_g_dl": 12.39,
    "svr_pred": 13.439,
    "abs_err": 1.049,
    "brightness_factor": 1.063,
    "blur_level": 1.568,
    "noise_level": 9.781,
    "rotation_degrees": 0.482
  },
  {
    "uid": "contrib_a:IMG000303",
    "augmentation_profile": "moderate",
    "target_hb_g_dl": 8.68,
    "svr_pred": 7.81,
    "abs_err": 0.87,
    "brightness_factor": 1.053,
    "blur_level": 1.209,
    "noise_level": 3.961,
    "rotation_degrees": 4.002
  }
]
```

Plots: pred_vs_true.png, residuals.png, error_by_profile_and_range.png, error_vs_conditions.png
