"""
model_runner.py
---------------
Multi-year precinct-level Random Forest models for Missouri voter resource allocation.

Two models are trained:
  1. RF Regressor  — predict precinct-level voter turnout (%)
  2. RF Classifier — identify high-priority precincts (predicted turnout < 30%)

Evaluation strategy:
  Temporal cross-validation (2 folds):
    Fold 1: train on 2016 precincts → test on 2020 precincts
    Fold 2: train on 2016 + 2020   → test on 2024 precincts
  Final models are then re-trained on all three years for deployment.

Inputs:
  data/geo/output/precinct_features_{2016,2020,2024}.gpkg  (from geo pipeline)

Outputs:
  data/processed/precinct_model_predictions.csv    (tabular, no geometry)
  data/geo/output/precinct_model_predictions.gpkg  (with geometry, for mapping)

Called by main.py as Stage 5:
    from src.model_runner import run_model
    run_model(geo_output_dir=GEO_OUTPUT_DIR, processed_dir=PROCESSED_DIR)
"""

import logging
import numpy as np
import pandas as pd
import geopandas as gpd
from pathlib import Path

from sklearn.ensemble import RandomForestRegressor, RandomForestClassifier
from sklearn.linear_model import LinearRegression, LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import (
    r2_score, mean_absolute_error, mean_squared_error,
    accuracy_score, f1_score, precision_score, recall_score,
    roc_auc_score, classification_report, confusion_matrix,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ELECTION_YEARS = [2016, 2020, 2024]

# Feature columns present in all three GeoPackages.
# pct_white excluded — near-perfect collinearity with pct_minority.
# Population / density excluded — covered by the geospatial pipeline separately.
# Model intentionally uses only demographic characteristics so that priority_proba
# reflects demographic underperformance rather than the urban/rural divide.
FEATURE_COLS = [
    "pct_minority",
    "median_household_income",
    "pct_bachelors_plus",
    "pct_no_vehicle",
    "pct_voting_age",
]

REGRESSION_TARGET    = "turnout_pct"
CLASSIFICATION_TARGET = "low_turnout_flag"
LOW_TURNOUT_THRESHOLD = 30.0   # precincts below this are flagged as high-priority


# ---------------------------------------------------------------------------
# Stage 1 — Load
# ---------------------------------------------------------------------------

def load_precinct_features(geo_output_dir, years=None):
    """
    Loads and pools precinct GeoPackages for all election years into a
    single GeoDataFrame.

    Parameters
    ----------
    geo_output_dir : str or Path
        Directory containing precinct_features_{year}.gpkg files.
    years : list of int, optional
        Election years to load. Defaults to [2016, 2020, 2024].

    Returns
    -------
    GeoDataFrame with all years concatenated, CRS preserved from the files.

    Raises
    ------
    FileNotFoundError if any expected GeoPackage is missing.
    """
    if years is None:
        years = ELECTION_YEARS

    geo_output_dir = Path(geo_output_dir)
    gdfs = []

    for year in years:
        path = geo_output_dir / f"precinct_features_{year}.gpkg"
        if not path.exists():
            raise FileNotFoundError(
                f"GeoPackage not found: {path}\n"
                "The geo pipeline must be run first (geo_pipeline_dev.ipynb) before "
                "the model can execute. If running from main.py, omit --model-only "
                "or ensure the .gpkg files exist in data/geo/output/."
            )
        gdf = gpd.read_file(path)
        if "year" not in gdf.columns:
            gdf["year"] = year
        gdfs.append(gdf)
        logging.info(f"  Loaded {year}: {len(gdf):,} precincts")

    pooled = pd.concat(gdfs, ignore_index=True)
    logging.info(f"Pooled dataset: {len(pooled):,} precinct-years across {len(years)} years")
    return gpd.GeoDataFrame(pooled, geometry="geometry", crs=gdfs[0].crs)


# ---------------------------------------------------------------------------
# Stage 2 — Feature engineering
# ---------------------------------------------------------------------------

def engineer_features(gdf):
    """
    Adds derived columns used as the classification target and output metric:

    - low_turnout_flag  : 1 if turnout_pct < LOW_TURNOUT_THRESHOLD, else 0
                          Used as the classifier training label.
    - uncasted_votes    : apportioned_vap × (1 − turnout_pct / 100)
                          Measures the raw number of eligible voters who did
                          not turn out — combined with priority_proba in
                          build_predictions() to produce the need_score.

    Parameters
    ----------
    gdf : GeoDataFrame
        Pooled precinct features from load_precinct_features().

    Returns
    -------
    GeoDataFrame with two additional columns.
    """
    gdf = gdf.copy()

    # --- Classification target ---
    gdf[CLASSIFICATION_TARGET] = (
        gdf[REGRESSION_TARGET] < LOW_TURNOUT_THRESHOLD
    ).astype(int)

    # --- Uncasted votes ---
    if "apportioned_vap" in gdf.columns:
        gdf["uncasted_votes"] = (
            gdf["apportioned_vap"] * (1 - gdf[REGRESSION_TARGET] / 100)
        ).round(0)
    else:
        gdf["uncasted_votes"] = np.nan
        logging.warning("apportioned_vap column not found — uncasted_votes will be NaN.")

    return gdf


# ---------------------------------------------------------------------------
# Stage 3 — Feature matrix
# ---------------------------------------------------------------------------

def build_feature_matrix(gdf):
    """
    Selects feature and target columns, drops rows with nulls in any
    feature or target column, and separates model inputs from metadata.

    Parameters
    ----------
    gdf : GeoDataFrame
        Output of engineer_features().

    Returns
    -------
    X     : DataFrame  — feature columns only
    y_reg : Series     — regression target (turnout_pct)
    y_cls : Series     — classification target (low_turnout_flag)
    meta  : GeoDataFrame — precinct identifiers, year, geometry (for rejoining)
    """
    id_cols = ["composite_prec_id", "COUNTYFP", "year",
               "uncasted_votes", "apportioned_vap", "geometry"]

    # Keep only columns that are present in this GeoPackage vintage
    id_cols = [c for c in id_cols if c in gdf.columns]
    required_features = FEATURE_COLS + [REGRESSION_TARGET, CLASSIFICATION_TARGET]

    working = gdf[id_cols + required_features].dropna(
        subset=FEATURE_COLS + [REGRESSION_TARGET]
    ).reset_index(drop=True)

    X     = working[FEATURE_COLS]
    y_reg = working[REGRESSION_TARGET]
    y_cls = working[CLASSIFICATION_TARGET]
    meta  = working[id_cols]

    return X, y_reg, y_cls, gpd.GeoDataFrame(meta, geometry="geometry", crs=gdf.crs)


# ---------------------------------------------------------------------------
# Stage 4 — Temporal cross-validation
# ---------------------------------------------------------------------------

def _temporal_folds(years_series):
    """
    Defines two temporal folds as boolean index masks.

    Fold 1: train = 2016,        test = 2020
    Fold 2: train = 2016 + 2020, test = 2024

    Returns
    -------
    list of (train_mask, test_mask, fold_label) tuples
    """
    return [
        (
            years_series == 2016,
            years_series == 2020,
            "Fold 1  (train 2016       → test 2020)",
        ),
        (
            years_series.isin([2016, 2020]),
            years_series == 2024,
            "Fold 2  (train 2016+2020  → test 2024)",
        ),
    ]


def run_temporal_cv(X, y_reg, y_cls, meta):
    """
    Runs 2-fold temporal cross-validation, training and evaluating both
    the regressor and classifier on each fold.

    Parameters
    ----------
    X     : DataFrame  — features
    y_reg : Series     — regression target
    y_cls : Series     — classification target
    meta  : GeoDataFrame — must contain a 'year' column

    Returns
    -------
    reg_metrics : dict  — lists of R², MAE, RMSE per fold
    cls_metrics : dict  — lists of accuracy, F1, precision, recall, AUC-ROC per fold
    fold_labels : list of str
    """
    years  = meta["year"]
    folds  = _temporal_folds(years)

    reg_metrics = {"r2": [], "mae": [], "rmse": []}
    cls_metrics = {"accuracy": [], "f1": [], "precision": [], "recall": [], "auc_roc": []}
    fold_labels = []

    for train_mask, test_mask, label in folds:
        fold_labels.append(label)

        X_tr,  X_te  = X[train_mask],    X[test_mask]
        yr_tr, yr_te = y_reg[train_mask], y_reg[test_mask]
        yc_tr, yc_te = y_cls[train_mask], y_cls[test_mask]

        n_train = int(train_mask.sum())
        n_test  = int(test_mask.sum())
        logging.info(f"  {label}: n_train={n_train:,}  n_test={n_test:,}")

        # --- Regressor ---
        rf_reg = RandomForestRegressor(n_estimators=200, random_state=42, n_jobs=-1)
        rf_reg.fit(X_tr, yr_tr)
        reg_pred = rf_reg.predict(X_te)

        reg_metrics["r2"].append(r2_score(yr_te, reg_pred))
        reg_metrics["mae"].append(mean_absolute_error(yr_te, reg_pred))
        reg_metrics["rmse"].append(mean_squared_error(yr_te, reg_pred) ** 0.5)

        # --- Classifier ---
        # class_weight='balanced' upweights the minority class (high-priority
        # precincts, ~7% of data) to prioritize recall over precision — appropriate
        # since output drives human review rather than automated action.
        rf_cls = RandomForestClassifier(n_estimators=200, random_state=42,
                                        class_weight="balanced", n_jobs=-1)
        rf_cls.fit(X_tr, yc_tr)
        cls_pred  = rf_cls.predict(X_te)
        cls_proba = rf_cls.predict_proba(X_te)[:, 1]

        cls_metrics["accuracy"].append(accuracy_score(yc_te, cls_pred))
        cls_metrics["f1"].append(f1_score(yc_te, cls_pred, zero_division=0))
        cls_metrics["precision"].append(precision_score(yc_te, cls_pred, zero_division=0))
        cls_metrics["recall"].append(recall_score(yc_te, cls_pred, zero_division=0))

        # AUC-ROC requires at least one positive class in the test set
        if yc_te.nunique() > 1:
            cls_metrics["auc_roc"].append(roc_auc_score(yc_te, cls_proba))
        else:
            cls_metrics["auc_roc"].append(float("nan"))
            logging.warning(f"  {label}: only one class in test set — AUC-ROC undefined.")

        # Per-fold classification report
        logging.info(
            "\n" + classification_report(
                yc_te, cls_pred,
                target_names=["Normal (0)", "High Priority (1)"],
                zero_division=0,
            )
        )

    return reg_metrics, cls_metrics, fold_labels


# ---------------------------------------------------------------------------
# Stage 5 — Final model training (all years)
# ---------------------------------------------------------------------------

def train_final_models(X, y_reg, y_cls):
    """
    Trains the deployment models on the full pooled dataset (2016+2020+2024).

    Also trains Linear Regression and Logistic Regression baselines for
    reference. Baseline models are returned but not used for predictions.

    Returns
    -------
    rf_reg  : fitted RandomForestRegressor
    rf_cls  : fitted RandomForestClassifier
    lr_reg  : fitted LinearRegression Pipeline (baseline)
    lr_cls  : fitted LogisticRegression Pipeline (baseline)
    """
    rf_reg = RandomForestRegressor(n_estimators=200, random_state=42, n_jobs=-1)
    rf_reg.fit(X, y_reg)

    rf_cls = RandomForestClassifier(n_estimators=200, random_state=42,
                                    class_weight="balanced", n_jobs=-1)
    rf_cls.fit(X, y_cls)

    lr_reg = Pipeline([("scaler", StandardScaler()), ("lr", LinearRegression())])
    lr_reg.fit(X, y_reg)

    lr_cls = Pipeline([
        ("scaler", StandardScaler()),
        ("lr", LogisticRegression(random_state=42, max_iter=1000)),
    ])
    lr_cls.fit(X, y_cls)

    logging.info("Final models (RF + baseline) trained on full pooled dataset.")
    return rf_reg, rf_cls, lr_reg, lr_cls


# ---------------------------------------------------------------------------
# Stage 6 — Predictions on 2024 precincts
# ---------------------------------------------------------------------------

def build_predictions(rf_reg, rf_cls, X_2024, meta_2024):
    """
    Applies the final models to 2024 precincts (the most recent cycle),
    producing the actionable resource allocation output.

    Columns added:
      predicted_turnout_pct   — RF regressor output
      priority_flag           — RF classifier output (1 = high priority)
      priority_proba          — classifier probability (for ranking)
      predicted_uncasted_votes — apportioned_vap × (1 − predicted_turnout / 100)

    Parameters
    ----------
    rf_reg   : fitted RandomForestRegressor
    rf_cls   : fitted RandomForestClassifier
    X_2024   : DataFrame  — 2024 feature rows
    meta_2024 : GeoDataFrame — 2024 metadata rows (aligned index with X_2024)

    Returns
    -------
    GeoDataFrame with all metadata columns + prediction columns.
    """
    pred_turnout = rf_reg.predict(X_2024).round(2)
    pred_flag    = rf_cls.predict(X_2024)
    pred_proba   = rf_cls.predict_proba(X_2024)[:, 1].round(4)

    out = meta_2024.copy().reset_index(drop=True)
    out["predicted_turnout_pct"]   = pred_turnout
    out["priority_flag"]           = pred_flag
    out["priority_proba"]          = pred_proba

    if "apportioned_vap" in out.columns:
        out["predicted_uncasted_votes"] = (
            out["apportioned_vap"] * (1 - pred_turnout / 100)
        ).round(0)

        # need_score combines the model's demographic underperformance signal
        # (priority_proba) with the magnitude of potential impact (predicted
        # uncasted votes). Precincts that rank highly on both dimensions are
        # the strongest candidates for resource allocation.
        out["need_score"] = (
            out["priority_proba"] * out["predicted_uncasted_votes"]
        ).round(2)

    return gpd.GeoDataFrame(out, geometry="geometry", crs=meta_2024.crs)


# ---------------------------------------------------------------------------
# Reporting helpers
# ---------------------------------------------------------------------------

def _print_cv_summary(reg_metrics, cls_metrics, fold_labels):
    """Prints a formatted cross-validation summary table."""
    print("\n" + "=" * 72)
    print("TEMPORAL CROSS-VALIDATION RESULTS")
    print("=" * 72)

    print("\nRegressor — predict turnout %:")
    print(f"  {'Fold':<45} {'R²':>7} {'MAE':>7} {'RMSE':>7}")
    print(f"  {'-' * 68}")
    for i, label in enumerate(fold_labels):
        print(f"  {label:<45} {reg_metrics['r2'][i]:>7.4f} "
              f"{reg_metrics['mae'][i]:>7.2f} {reg_metrics['rmse'][i]:>7.2f}")
    r2_vals = [v for v in reg_metrics['r2'] if not np.isnan(v)]
    print(f"  {'Mean':<45} {np.mean(r2_vals):>7.4f} "
          f"{np.mean(reg_metrics['mae']):>7.2f} {np.mean(reg_metrics['rmse']):>7.2f}")

    print(f"\nClassifier — flag priority precincts (threshold = {LOW_TURNOUT_THRESHOLD}%):")
    print(f"  {'Fold':<45} {'Acc':>6} {'F1':>6} {'Prec':>6} {'Rec':>6} {'AUC':>6}")
    print(f"  {'-' * 74}")
    for i, label in enumerate(fold_labels):
        auc_str = f"{cls_metrics['auc_roc'][i]:>6.4f}" if not np.isnan(cls_metrics['auc_roc'][i]) else "   N/A"
        print(f"  {label:<45} {cls_metrics['accuracy'][i]:>6.4f} "
              f"{cls_metrics['f1'][i]:>6.4f} {cls_metrics['precision'][i]:>6.4f} "
              f"{cls_metrics['recall'][i]:>6.4f} {auc_str}")
    auc_vals = [v for v in cls_metrics["auc_roc"] if not np.isnan(v)]
    print(f"  {'Mean':<45} {np.mean(cls_metrics['accuracy']):>6.4f} "
          f"{np.mean(cls_metrics['f1']):>6.4f} {np.mean(cls_metrics['precision']):>6.4f} "
          f"{np.mean(cls_metrics['recall']):>6.4f} "
          f"{np.mean(auc_vals):>6.4f}" if auc_vals else "")
    print("=" * 72)


def _print_feature_importance(rf_reg, rf_cls):
    """Prints a side-by-side feature importance table for both models."""
    imp_df = pd.DataFrame({
        "feature":        FEATURE_COLS,
        "regression":     rf_reg.feature_importances_,
        "classification": rf_cls.feature_importances_,
    }).sort_values("regression", ascending=False).reset_index(drop=True)

    print("\n" + "=" * 72)
    print("FEATURE IMPORTANCE (Final Models — trained on all years)")
    print("=" * 72)
    print(f"  {'Feature':<32} {'Regression':>12} {'Classification':>16}")
    print(f"  {'-' * 62}")
    for _, row in imp_df.iterrows():
        bar = "█" * int(row["regression"] * 40)
        print(f"  {row['feature']:<32} {row['regression']:>12.4f} "
              f"{row['classification']:>16.4f}  {bar}")
    print("=" * 72)
    return imp_df


# ---------------------------------------------------------------------------
# Save outputs
# ---------------------------------------------------------------------------

def save_outputs(predictions_gdf, processed_dir, geo_output_dir):
    """
    Saves the 2024 precinct predictions in two formats:

    1. CSV (no geometry) → data/processed/precinct_model_predictions.csv
       For tabular analysis and dashboard import.

    2. GeoPackage (with geometry) → data/geo/output/precinct_model_predictions.gpkg
       For final map of high-priority precincts.

    Returns
    -------
    (csv_path, gpkg_path) as Path objects.
    """
    processed_dir  = Path(processed_dir)
    geo_output_dir = Path(geo_output_dir)
    geo_output_dir.mkdir(parents=True, exist_ok=True)

    csv_path = processed_dir / "precinct_model_predictions.csv"
    predictions_gdf.drop(columns="geometry").to_csv(csv_path, index=False)
    print(f"  Saved CSV  : {csv_path}")
    logging.info(f"Saved predictions CSV: {csv_path}")

    gpkg_path = geo_output_dir / "precinct_model_predictions.gpkg"
    predictions_gdf.to_file(gpkg_path, driver="GPKG")
    print(f"  Saved GPKG : {gpkg_path}")
    logging.info(f"Saved predictions GeoPackage: {gpkg_path}")

    return csv_path, gpkg_path


# ---------------------------------------------------------------------------
# Top-level orchestrator
# ---------------------------------------------------------------------------

def run_model(geo_output_dir, processed_dir):
    """
    Orchestrates the full precinct-level model pipeline. Called by main.py.

    Steps
    -----
    1. Load precinct GeoPackages for 2016, 2020, 2024
    2. Engineer features (low_turnout_flag, uncasted_votes)
    3. Build feature matrix (drop nulls, separate X/y/meta)
    4. Temporal cross-validation (evaluate generalization)
    5. Train final models on full pooled dataset
    6. Generate predictions on 2024 precincts
    7. Print feature importance summary
    8. Save CSV and GeoPackage outputs

    Parameters
    ----------
    geo_output_dir : str or Path
        Directory containing precinct_features_{year}.gpkg and where
        precinct_model_predictions.gpkg will be written.
    processed_dir : str or Path
        Directory where precinct_model_predictions.csv will be written.

    Returns
    -------
    predictions_gdf : GeoDataFrame of 2024 precinct predictions
    """
    print("\n" + "=" * 50)
    print("STAGE 5: PRECINCT-LEVEL PREDICTIVE MODEL")
    print("=" * 50)
    logging.info("Starting precinct-level model pipeline.")

    # 1. Load
    print("\nLoading precinct GeoPackages (2016, 2020, 2024)...")
    gdf = load_precinct_features(geo_output_dir)

    # 2. Engineer features
    print("Engineering features...")
    gdf = engineer_features(gdf)

    flag_counts = gdf[CLASSIFICATION_TARGET].value_counts()
    total       = len(gdf)
    n_priority  = int(flag_counts.get(1, 0))
    print(f"  Pooled dataset   : {total:,} precinct-years")
    print(f"  High priority (1): {n_priority:,}  ({n_priority / total * 100:.1f}%)")
    print(f"  Normal (0)       : {total - n_priority:,}  "
          f"({(total - n_priority) / total * 100:.1f}%)")

    # 3. Feature matrix
    X, y_reg, y_cls, meta = build_feature_matrix(gdf)
    print(f"  Rows after null drop: {len(X):,}")

    # 4. Temporal CV
    print("\nRunning temporal cross-validation...")
    reg_metrics, cls_metrics, fold_labels = run_temporal_cv(X, y_reg, y_cls, meta)
    _print_cv_summary(reg_metrics, cls_metrics, fold_labels)

    # 5. Final models (all years)
    print("\nTraining final models on full pooled dataset (2016 + 2020 + 2024)...")
    rf_reg, rf_cls, _, _ = train_final_models(X, y_reg, y_cls)

    # 6. Predict on 2024 precincts
    print("\nGenerating predictions on 2024 precincts...")
    mask_2024  = meta["year"] == 2024
    X_2024     = X[mask_2024].reset_index(drop=True)
    meta_2024  = meta[mask_2024].reset_index(drop=True)

    predictions_gdf = build_predictions(rf_reg, rf_cls, X_2024, meta_2024)

    n_flagged = int(predictions_gdf["priority_flag"].sum())
    print(f"  2024 precincts scored : {len(predictions_gdf):,}")
    print(f"  Flagged high-priority : {n_flagged:,}  "
          f"({n_flagged / len(predictions_gdf) * 100:.1f}%)")

    if "need_score" in predictions_gdf.columns:
        top10 = (
            predictions_gdf[["composite_prec_id", "priority_proba",
                              "predicted_uncasted_votes", "need_score"]]
            .sort_values("need_score", ascending=False)
            .head(10)
            .reset_index(drop=True)
        )
        print("\n  Top 10 precincts by need_score (proba × predicted uncasted votes):")
        print(f"  {'Precinct':<35} {'Proba':>7} {'Uncasted':>10} {'NeedScore':>10}")
        print(f"  {'-' * 65}")
        for _, row in top10.iterrows():
            print(f"  {str(row['composite_prec_id']):<35} "
                  f"{row['priority_proba']:>7.4f} "
                  f"{row['predicted_uncasted_votes']:>10,.0f} "
                  f"{row['need_score']:>10,.2f}")

    # 7. Feature importance
    _print_feature_importance(rf_reg, rf_cls)

    # 8. Save outputs
    print("\nSaving outputs...")
    save_outputs(predictions_gdf, processed_dir, geo_output_dir)

    logging.info("Precinct-level model pipeline complete.")
    print("\nStage 5 complete.")

    return predictions_gdf
