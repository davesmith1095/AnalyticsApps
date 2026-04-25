# Missouri Voter Resource Allocation
**CAPS 5576 — Analytics Applications, Spring 2026 | Group 1**

This project analyzes the distribution of voting resources across Missouri during the 2020 presidential election. By combining precinct-level election results, polling location data, demographic and socioeconomic Census data, and geographic boundaries, the pipeline produces predictive and prescriptive recommendations for where voting resources should be allocated to reduce voter disenfranchisement.

---

## Repository Structure

> **Note:** The `data/` folder is in `.gitignore`. Do not force-push data files to this repository. Raw data is distributed via the [Canvas Group Files page](https://wustl.instructure.com/groups/144912/files).

```
.
├── main.py                         # Pipeline entry point
├── README.md
├── requirements.txt
├── data/
│   ├── geo/
│   │   ├── raw/                    # VEST shapefiles, TIGER block geometry
│   │   │   ├── mo_2016_vest/
│   │   │   ├── mo_2020_vest/
│   │   │   ├── mo_2024_gen_all_prec/
│   │   │   └── mo_2020_census_blocks/
│   │   └── output/                 # GeoPackages + dashboard HTML
│   └── processed/                  # ACS staging CSVs + model output CSVs
├── docs/                           # Model comparison and technical write-ups
├── logs/
├── notebooks/                      # Group final project notebook (main model)
├── scripts/
│   └── build_dashboard.py          # Standalone dashboard generator
└── src/                            # Python modules
    ├── geo_loader.py
    ├── census_block_loader.py
    ├── precinct_builder.py
    ├── geo_processor.py
    ├── model_runner.py
    └── geo_visualizer.py
```

---

## Getting Started

1. Log in to the [Canvas Group Files page](https://wustl.instructure.com/groups/144912/files) and download `raw.zip`
2. Extract its contents into `data/raw/`
3. Install dependencies: `pip install -r requirements.txt`
4. Run the group notebook to verify your local setup: `notebooks/Group 1 Final Project - MO Voter.ipynb`

---

## Primary Model — County-Level, 2020

The primary deliverable for this course is the group notebook (`notebooks/Group 1 Final Project - MO Voter.ipynb`). It operates at the county level using 2020 election data and produces two models:

**Regressor** — predicts county-level turnout percentage using a Random Forest, compared against a Linear Regression baseline. Achieved a holdout R² of 0.53, though 5-fold cross-validation (R² = 0.28 ± 0.28) suggests meaningful variance due to the small dataset size (n = 113 counties).

**Classifier** — flags low-turnout counties below a 60% threshold. Achieved 65% accuracy with precision of 0.88 and recall of 0.50 on the held-out test set. The high precision but limited recall means the model was conservative — it missed roughly half of the counties that genuinely needed attention.

**Features used:** `pct_minority`, `median_household_income`, `pct_voting_age`, `pct_no_vehicle`, `pct_bachelors_plus`, `unique_polling_places`, `precincts_per_polling_place`

---

## Alternate Model — Precinct-Level, Multi-Year (What's Next)

`src/model_runner.py` and `main.py` implement an extended version of the analysis at precinct resolution across three election years (2016, 2020, 2024). This model is not the primary course deliverable — it represents what the analysis could look like with more time and data infrastructure.

**Key design decisions:**

The model pools roughly 3,400 precincts per year (~10,000 precinct-year observations total) and uses temporal cross-validation: train on past years, test on a future year. This is a more demanding and honest test than random splitting on a single year because the model must generalize forward in time, not just to held-out data it was drawn from.

Polling place features were dropped because they ranked last in feature importance in the primary model and were only available for 2020, making cross-year consistency impossible. Population and population density were also removed after testing showed they dominated feature importance (80-90%), effectively reducing the model to a precinct-size ranking rather than a demographic analysis.

The classification threshold was set at 30% (roughly half the statewide average), targeting the most severely underserved precincts. Because only about 7% of precincts fall below this threshold, `class_weight='balanced'` is used to prevent the model from ignoring the minority class entirely. This trades precision for recall — the right trade-off when the output is meant to queue up human review rather than drive automated decisions.

The primary output is a `need_score` combining the model's demographic underperformance signal (`priority_proba`) with the magnitude of potential impact (`predicted_uncasted_votes`). This lets analysts rank precincts by both how likely they are to be structurally underserved and how many voters could be reached.

**Features used:** `pct_minority`, `median_household_income`, `pct_bachelors_plus`, `pct_no_vehicle`, `pct_voting_age`

**Performance (temporal cross-validation):**

| Metric | Fold 1 (train 2016 → test 2020) | Fold 2 (train 2016+2020 → test 2024) | Mean |
|---|---|---|---|
| Regressor R² | -0.010 | 0.104 | 0.047 |
| Regressor MAE | 17.5% | 14.8% | 16.2% |
| Classifier Recall | 0.889 | 0.662 | 0.775 |
| Classifier AUC-ROC | 0.772 | 0.685 | 0.729 |

The regression metrics are weaker than the primary model — temporal CV is a harder test, and demographic features alone carry less variance than county-level features on a larger dataset. Recall is the meaningful improvement: the alternate model catches 77.5% of high-priority precincts compared to 50% in the primary model.

See `docs/model_comparison_baseline.md` for a full side-by-side comparison, design rationale, and documented risks and trade-offs.

---

## How the Two Models Differ

| | Primary Model | Alternate Model |
|---|---|---|
| Unit of analysis | Missouri counties (n = 113) | Missouri precincts (~3,400/year) |
| Election years | 2020 only | 2016, 2020, 2024 (pooled) |
| Validation strategy | Random 80/20 split + 5-fold CV | Temporal CV (train past → test future) |
| Classification threshold | 60% (statewide average) | 30% (most severe cases) |
| Class balancing | None | `class_weight='balanced'` |
| Polling features | Included | Excluded |
| Population features | Included | Excluded |
| Primary output | Predicted turnout % | `need_score` (proba × uncasted votes) |
| Classifier recall | 0.50 | 0.775 |

The two models are answering related but distinct questions. The primary model identifies which counties are likely to have low turnout and can guide county-level planning. The alternate model identifies which specific precincts are demographically underperforming — places where turnout is lower than the income, education, vehicle access, and minority share of the population would predict. These are complementary lenses, not competing ones.

---

## Dashboard

`scripts/build_dashboard.py` produces a self-contained HTML choropleth map of Missouri at precinct resolution. No server or internet connection is required to open the output file after the first load.

**To generate:**
```bash
python scripts/build_dashboard.py
# Output: data/geo/output/mo_precinct_dashboard.html
```

**Views available:**

| View | Description |
|---|---|
| 2016 / 2020 / 2024 Turnout | Actual precinct-level turnout % from VEST shapefiles |
| 2024 Predicted Turnout | Model-predicted turnout % for 2024 precincts |
| 2024 Precinct Need Score | `need_score` ranking — higher values indicate greater resource need |

The dashboard opens on the 2024 Predicted Turnout view by default. County outlines are displayed as a permanent overlay on all views for geographic context. Layer switching is near-instant because all view data is pre-computed and embedded at build time — switching views only updates the colour values rather than re-rendering the map.

The dashboard is built from the alternate model's outputs (`precinct_model_predictions.gpkg`) and is intended as a consumption-layer companion to `model_runner.py`, not to the primary group notebook.
