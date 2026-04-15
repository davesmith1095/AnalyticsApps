# Model Comparison: Baseline vs. Multi-Year Precinct Model

**Course:** CAPS 5576 — Analytics Applications
**Project:** Missouri Voter Resource Allocation (Group 1)
**Prepared by:** David Smith
**Last Updated:** April 2026

---

## Purpose

This document records the performance of the original county-level model (baseline), the design rationale and evolution of the new multi-year precinct-level model, and a direct comparison of both models' outputs. It is intended as a reference for team discussion and as supporting documentation for the model upgrade proposal.

---

## Baseline Model — County-Level, 2020 Only

### Setup

| Parameter | Value |
|---|---|
| Unit of analysis | Missouri counties (n = 113 after null removal) |
| Election years | 2020 only |
| Train/test split | Random 80/20 (90 train / 23 test, `random_state=42`) |
| Cross-validation | 5-fold KFold (regressor) / 5-fold StratifiedKFold (classifier) |
| Classification threshold | Turnout < **60%** (statewide average benchmark) |
| Features | 7 (see feature importance table below) |
| Polling features included | Yes — `unique_polling_places`, `precincts_per_polling_place` |

---

### Model 1 — Regressor: Predict County Turnout %

| Model | R² | MAE | RMSE |
|---|---|---|---|
| **Random Forest (primary)** | **0.5263** | **4.15%** | **5.51%** |
| Linear Regression (baseline) | 0.2159 | 4.78% | 7.09% |

**Random Forest 5-Fold CV R²: 0.2827 ± 0.2793**

> **Note:** The gap between the holdout R² (0.5263) and the CV R² (0.2827) is significant and the CV standard deviation (0.2793) is nearly as large as the CV mean. This indicates the holdout score was likely a favorable random split rather than a reliable performance estimate. The CV score is the more honest figure.

---

### Model 2 — Classifier: Identify Low-Turnout Counties (threshold: < 60%)

| Model | Accuracy |
|---|---|
| **Random Forest (primary)** | **0.6522** |
| Logistic Regression (baseline) | 0.5652 |

**Random Forest 5-Fold CV F1: 0.6251 ± 0.1260**

#### Classification Report (Random Forest, holdout test set, n = 23)

| Class | Precision | Recall | F1 | Support |
|---|---|---|---|---|
| High Turnout (0) | 0.53 | 0.89 | 0.67 | 9 |
| Low Turnout (1) | 0.88 | 0.50 | 0.64 | 14 |
| **Weighted avg** | **0.74** | **0.65** | **0.65** | **23** |

#### Confusion Matrix

| | Predicted High | Predicted Low |
|---|---|---|
| **Actual High** | 8 | 1 |
| **Actual Low** | 7 | 7 |

> **Note:** The classifier correctly flagged 7 of 14 low-turnout counties (recall = 0.50) while maintaining high precision (0.88). For a resource allocation problem, missing 7 true low-turnout counties is a material failure. This recall gap motivates moving to a higher-resolution precinct-level model.

*AUC-ROC was not computed in the original notebook.*

---

### Feature Importance (Random Forest)

| Feature | Regression Importance | Classification Importance |
|---|---|---|
| minority_2020 | 0.3828 | 0.2193 |
| income_2020 | 0.1744 | 0.1668 |
| vap_2020 | 0.1649 | 0.1548 |
| no_vehicle_2020 | 0.0941 | 0.1225 |
| edu_2020 | 0.0723 | 0.1250 |
| precincts_per_polling_place | 0.0622 | 0.1210 |
| unique_polling_places | 0.0494 | 0.0907 |

> `minority_2020` dominates the regression model (0.38 importance). Polling features rank last in both models, supporting the decision to drop them from the multi-year model.

---

## Structural Limitations of the Baseline

**1. Small test set (n = 23)**
With only 23 counties in the holdout, a single outlier (e.g., Jackson County reporting anomaly, Pulaski County's military population) can meaningfully swing every metric. Results should be interpreted directionally.

**2. Unstable cross-validation (CV R² std = 0.2793)**
The five CV folds produced wildly different R² scores, suggesting the model is sensitive to which counties happen to be in training vs. test. This is a fundamental consequence of having only 113 observations.

**3. No temporal generalization**
The baseline was trained and tested on the same election year (2020). It has never been asked to predict a year it wasn't trained on. The new model uses temporal cross-validation to test this explicitly.

**4. County resolution is too coarse for resource allocation**
A county-level prediction tells you which of 114 counties to prioritize. A precinct-level prediction tells you *which specific polling area* within a county to target — far more actionable for logistics.

**5. Polling features cannot be replicated across years**
The `unique_polling_places` and `precincts_per_polling_place` features exist only for 2020. Including them in a multi-year model would require imputing or copying 2020 values to 2016 and 2024, introducing noise. Feature importance rankings confirm these features add the least signal anyway.

---

## New Model — Design Evolution

The new model went through several design iterations before arriving at its final form. Each change was motivated by a specific observed problem. This section documents that progression so the final design choices can be understood in context.

### Version 1 — Initial Multi-Year Build

The first version pooled precinct-level GeoPackages for 2016, 2020, and 2024 and introduced temporal cross-validation. Features included five demographic variables plus `apportioned_population` (raw precinct population from Census block apportionment). Classification threshold was set at 30% (roughly half the statewide average, targeting the most severely underserved precincts).

**Problem identified:** `apportioned_population` accounted for 80–90% of feature importance in both the regressor and classifier. The model was essentially learning precinct size rather than demographic characteristics, making its predictions nearly identical to just ranking precincts by population.

### Version 2 — Population Replaced with Density

`apportioned_population` was replaced with `pop_density_per_sq_mile` (population divided by precinct area in square miles, computed by reprojecting geometry to EPSG:5070 before calculating area). The rationale was that density captures the urban/rural distinction more meaningfully than raw count.

**Problem identified:** Population density still dominated at 72% regression importance and 85% classification importance. The urban/rural signal was so strong it continued to crowd out the demographic features the model was intended to learn from.

### Version 3 — Population and Density Removed Entirely (Final Design)

Population and density were removed from the model entirely. This was a deliberate framing decision: the geospatial pipeline already produces density maps and polling location analysis that capture the urban/rural dimension. The predictive model's distinct contribution is identifying precincts that are *demographically underperforming* — places where turnout is lower than would be expected given the income, education, vehicle access, and minority share of the population. These are complementary lenses, not redundant ones.

**Problem identified:** With only 7% of precincts falling below the 30% threshold, the classifier learned to always predict "normal" to achieve 93% accuracy, producing F1 = 0.0 and zero flagged precincts. This is a class imbalance problem.

### Version 4 — Class Weight Balancing Added (Final Design)

`class_weight='balanced'` was added to both `RandomForestClassifier` instantiations (CV folds and final model). This causes the model to weight minority-class errors (missing a high-priority precinct) approximately 13x more heavily than majority-class errors during training, reflecting the project's stated priority of recall over precision. The output is intended to drive human review rather than automated action, so false positives are recoverable while false negatives represent permanently missed opportunities.

**Additionally**, the output was redesigned around a `need_score` combining `priority_proba` (the model's learned demographic underperformance signal) with `predicted_uncasted_votes` (the magnitude of potential impact). This lets analysts rank precincts by both the strength of the demographic signal and the size of the untapped voter pool simultaneously.

---

## Final New Model — Configuration

| Parameter | Value |
|---|---|
| Unit of analysis | Missouri precincts (n ≈ 3,400/year after null removal) |
| Election years | 2016, 2020, 2024 (pooled; ~10,044 precinct-years) |
| Train/test split | Temporal CV: Fold 1 train=2016/test=2020; Fold 2 train=2016+2020/test=2024 |
| Classification threshold | Turnout < **30%** |
| Class weighting | `balanced` (minority class weighted ~13x) |
| Features | 5 demographic only (no population, no polling) |
| Primary output metric | `need_score` = `priority_proba` × `predicted_uncasted_votes` |

### Features

| Feature | Rationale |
|---|---|
| `pct_minority` | Strongest demographic predictor (consistent with baseline) |
| `median_household_income` | Socioeconomic access signal |
| `pct_bachelors_plus` | Education as civic engagement proxy |
| `pct_no_vehicle` | Physical access barrier |
| `pct_voting_age` | Eligible voter share of precinct population |

### Output Files

| File | Contents |
|---|---|
| `data/processed/precinct_model_predictions.csv` | Tabular predictions for all 2024 precincts |
| `data/geo/output/precinct_model_predictions.gpkg` | Predictions with geometry for final priority map |

**Prediction columns:** `predicted_turnout_pct`, `priority_flag` (0/1), `priority_proba`, `predicted_uncasted_votes`, `need_score`

---

## Final New Model — Performance

### Regressor — Predict Precinct Turnout %

| Fold | R² | MAE | RMSE |
|---|---|---|---|
| Fold 1 (train 2016 → test 2020) | -0.0096 | 17.51% | 22.49% |
| Fold 2 (train 2016+2020 → test 2024) | 0.1037 | 14.82% | 18.48% |
| **Mean** | **0.0470** | **16.16%** | **20.49%** |

### Classifier — Flag High-Priority Precincts (threshold: < 30%)

| Fold | Accuracy | F1 | Precision | Recall | AUC-ROC |
|---|---|---|---|---|---|
| Fold 1 (train 2016 → test 2020) | 0.6131 | 0.2642 | 0.1552 | 0.8889 | 0.7724 |
| Fold 2 (train 2016+2020 → test 2024) | 0.6404 | 0.1400 | 0.0783 | 0.6618 | 0.6853 |
| **Mean** | **0.6268** | **0.2021** | **0.1167** | **0.7753** | **0.7289** |

### Feature Importance (Final Models — trained on all years)

| Feature | Regression | Classification |
|---|---|---|
| pct_minority | 0.5086 | 0.4285 |
| pct_no_vehicle | 0.1921 | 0.2023 |
| median_household_income | 0.1655 | 0.0573 |
| pct_voting_age | 0.0772 | 0.1000 |
| pct_bachelors_plus | 0.0566 | 0.2119 |

### Top 10 Precincts by Need Score (2024)

| Precinct | Priority Proba | Predicted Uncasted Votes | Need Score |
|---|---|---|---|
| 169_ST ROBERT | 0.4768 | 6,039 | 2,879.40 |
| 510_WARD 11 PRECINCT 1 | 0.7184 | 3,651 | 2,622.88 |
| 510_WARD 10 PRECINCT 4 | 0.7184 | 2,789 | 2,003.62 |
| 510_WARD 9 PRECINCT 4 | 0.7184 | 2,687 | 1,930.34 |
| 510_WARD 6 PRECINCT 6 | 0.7184 | 2,500 | 1,796.00 |
| 095_B1, 02,02,03 | 0.5425 | 3,070 | 1,665.48 |
| 095_B8 01,02 | 0.5425 | 3,064 | 1,662.22 |
| 510_WARD 2 PRECINCT 5 | 0.7184 | 2,289 | 1,644.42 |
| 510_WARD 1 PRECINCT 5 | 0.7184 | 2,284 | 1,640.83 |
| 510_WARD 5 PRECINCT 3 | 0.7184 | 2,106 | 1,512.95 |

> County 510 = St. Louis City; County 169 = Pulaski County (home to Fort Leonard Wood); County 095 = Jefferson County.

---

## Side-by-Side Comparison

| Metric | Baseline (County, 2020) | New Model (Precinct, Multi-Year) |
|---|---|---|
| **Regressor — R²** | 0.5263 (holdout) / 0.2827 (CV) | 0.0470 (temporal CV) |
| **Regressor — MAE** | 4.15% | 16.16% |
| **Regressor — RMSE** | 5.51% | 20.49% |
| **Classifier — Accuracy** | 0.6522 | 0.6268 |
| **Classifier — F1 (low turnout)** | 0.64 | 0.2021 |
| **Classifier — Precision (low turnout)** | 0.88 | 0.1167 |
| **Classifier — Recall (low turnout)** | 0.50 | **0.7753** |
| **Classifier — AUC-ROC** | *(not computed)* | 0.7289 |
| **CV method** | 5-fold random | 2-fold temporal |
| **Threshold** | 60% | 30% |
| **n (test set)** | 23 counties | ~3,400 precincts (2024) |
| **Primary output** | Predicted turnout % | `need_score` (proba × uncasted votes) |

> **Direct metric comparison should be interpreted with caution.** The two models differ in unit of analysis, classification threshold, feature set, and validation strategy. The new model is not a "better version" of the old one — it answers a more precise and actionable question.

---

## Risks and Trade-offs

### 1. Regression metrics declined significantly

The new model's MAE (16.16%) is far worse than the baseline (4.15%), and the mean R² (0.047) is near zero. This reflects two compounding factors: temporal CV is a harder test than random splitting on a single year, and demographic features alone explain less variance in precinct turnout than the baseline's county-level features did. **Trade-off:** The model's regression output (predicted turnout %) should be treated as directional rather than precise. The classifier and `need_score` are the more reliable outputs for decision-making.

### 2. Low precision (1 in 8 flags is a true positive)

With `class_weight='balanced'` and a 7% minority class, precision is 0.117. Roughly 87% of flagged precincts will not actually fall below the 30% threshold. **Trade-off:** This was an explicit design decision. The model's output is intended to surface candidates for human review, not to make automated resource commitments. The human review layer makes false positives recoverable; false negatives (missed high-priority precincts) are not. For a different use case where precision mattered more, the class weight or classification threshold could be tuned.

### 3. Fold 2 performance degrades meaningfully

Recall drops from 0.889 (Fold 1, 2016→2020) to 0.662 (Fold 2, 2016+2020→2024), and AUC drops from 0.772 to 0.685. This suggests the model generalizes less well as the temporal gap grows, likely because voter behavior and demographics shifted more between 2020 and 2024 than between 2016 and 2020. **Risk:** Future election cycles (2028, 2032) may see further degradation. The model should be retrained with each new cycle's data rather than used as a static predictor.

### 4. The 30% threshold is somewhat arbitrary

The threshold was set at half the statewide average turnout — a reasonable heuristic but not derived from domain knowledge about what constitutes a genuinely underserved precinct. **Risk:** At 7% positive class prevalence, the threshold may be too strict, causing the classifier to struggle to find signal. Raising it to 35% or 40% would increase positive class prevalence and potentially improve classifier stability, at the cost of a less selective flag.

### 5. `pct_minority` dominates both models

At 51% regression importance and 43% classification importance, `pct_minority` is by far the strongest feature. This reflects a real structural pattern in Missouri voter data but raises a methodological question: is the model identifying demographic underperformance, or is it largely a minority-share detector with modest additional signal from the other features? **Risk:** If `pct_minority` is acting as a proxy for geographic and socioeconomic factors already captured by the other features, the model may be less nuanced than it appears. This is worth examining with partial dependence plots in future work.

### 6. `need_score` is not normalized

`need_score = priority_proba × predicted_uncasted_votes` produces values on very different scales across precincts (ranging from near-zero to ~2,900 in the top 10). This makes it useful for ranking within the 2024 output but not directly comparable across years if precinct populations change. **Note:** For cross-year comparisons, a normalized version (e.g., dividing by `apportioned_vap`) would be more stable.

### 7. Geospatial and model layers are complementary, not integrated

The final pipeline produces two separate analytical outputs: the geospatial density/polling analysis (turnout maps, polling density, commute charts) and the demographic model predictions. These currently live in separate outputs and have not been formally combined. **Opportunity:** Precincts that rank highly on both the geospatial access analysis and the demographic `need_score` would represent the strongest candidates for resource allocation. A final combined scoring layer could surface these dual-signal precincts explicitly.

---

*This document was prepared in conjunction with `src/model_runner.py` (new model implementation) and `main.py` (pipeline orchestration). All model outputs are in `data/processed/` and `data/geo/output/`.*
