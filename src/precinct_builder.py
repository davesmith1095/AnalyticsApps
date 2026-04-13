"""
precinct_builder.py
-------------------
Assembles precinct-level features from VEST shapefiles, census block data,
and county-level ACS demographics.

Core stages handled here:
  Stage 1 — CRS alignment
  Stage 2 — Area-weighted apportionment: census blocks → VEST precincts
  Stage 3 — Vote extraction and turnout calculation from VEST columns
  Stage 4 — ACS demographic downscaling (county → precinct via population weight)
  Stage 5 — County-level aggregation from precinct data

The output is a single GeoDataFrame per year — one row per precinct —
ready for both geospatial visualization and tabular modeling (drop geometry
column to get a flat DataFrame for Random Forest input).
"""

import re
import logging
import numpy as np
import pandas as pd
import geopandas as gpd

# Standard projected CRS for Missouri spatial operations (Equal Area, meters)
# Matches the CRS used in geo_processor.py
TARGET_CRS = "EPSG:5070"

# VEST presidential vote column pattern: G{YY}PRE{PARTY}{CANDIDATE}
# e.g. G16PRERTRU, G20PREDCLI, G24PRERTRU
VEST_PRE_PATTERN = re.compile(r"^G\d{2}PRE[A-Z]+$")

# Map year → 2-digit suffix used in VEST column names
YEAR_SUFFIX = {2016: "16", 2020: "20", 2024: "24"}

# County FIPS column name in VEST shapefiles (may vary; checked at runtime)
COUNTY_FIPS_CANDIDATES = ["COUNTYFP20", "COUNTYFP", "COUNTY_FPS", "CNTY_CODE"]


# =============================================================================
# Stage 1 — CRS Alignment
# =============================================================================

def align_crs(*gdfs, target_crs=TARGET_CRS):
    """
    Reprojects all input GeoDataFrames to a common CRS.
    Always call this before any spatial join or overlay.

    Returns the same number of GeoDataFrames as were passed in.
    """
    aligned = []
    for gdf in gdfs:
        if gdf.crs is None:
            logging.warning("GeoDataFrame has no CRS set — assuming EPSG:4326.")
            gdf = gdf.set_crs("EPSG:4326")
        if gdf.crs.to_epsg() != int(target_crs.split(":")[1]):
            gdf = gdf.to_crs(target_crs)
        aligned.append(gdf)
    return aligned if len(aligned) > 1 else aligned[0]


# =============================================================================
# Stage 2 — Area-weighted apportionment: blocks → precincts
# =============================================================================

def apportion_blocks_to_precincts(blocks_gdf, precincts_gdf, precinct_id_col):
    """
    Apportions census block population and VAP into VEST precinct boundaries
    using area-weighted intersection.

    For blocks that fall entirely within one precinct (the common case), the
    full population is assigned to that precinct. For blocks that straddle
    a boundary, population is split proportionally by overlap area.

    Parameters
    ----------
    blocks_gdf : GeoDataFrame
        Must have columns: GEOID20, total_population, vap_total, geometry
        CRS must already match precincts_gdf (call align_crs first).
    precincts_gdf : GeoDataFrame
        VEST precinct shapefile for a single year.
    precinct_id_col : str
        Column in precincts_gdf that uniquely identifies each precinct.

    Returns
    -------
    DataFrame (no geometry) with one row per precinct:
        {precinct_id_col}, apportioned_population, apportioned_vap
    """
    logging.info("Computing block → precinct apportionment via area intersection...")

    # Record original block areas for weight calculation
    blocks = blocks_gdf.copy()
    blocks["_block_area"] = blocks.geometry.area

    # Drop blocks with zero area (degenerate geometries)
    blocks = blocks[blocks["_block_area"] > 0]

    # Repair any invalid geometries before overlay
    blocks["geometry"]    = blocks.geometry.make_valid()
    precincts = precincts_gdf.copy()
    precincts["geometry"] = precincts.geometry.make_valid()

    # Intersect: each row = portion of a block inside a precinct
    logging.info("  Running gpd.overlay intersection (may take 1-2 minutes)...")
    intersection = gpd.overlay(
        blocks[["GEOID20", "total_population", "vap_total", "_block_area", "geometry"]],
        precincts[[precinct_id_col, "geometry"]],
        how="intersection",
        keep_geom_type=False
    )

    # Area of each intersection piece
    intersection["_intersection_area"] = intersection.geometry.area

    # Apportionment weight = what fraction of this block falls in this precinct
    intersection["_weight"] = (
        intersection["_intersection_area"] / intersection["_block_area"]
    ).clip(0, 1)   # clip to guard against floating-point > 1.0

    # Apply weights to population columns
    intersection["apportioned_population"] = (
        intersection["total_population"] * intersection["_weight"]
    )
    intersection["apportioned_vap"] = (
        intersection["vap_total"] * intersection["_weight"]
    )

    # Aggregate to precinct level
    result = (
        intersection
        .groupby(precinct_id_col)[["apportioned_population", "apportioned_vap"]]
        .sum()
        .reset_index()
    )

    logging.info(
        f"  Apportionment complete. "
        f"Total apportioned population: {result['apportioned_population'].sum():,.0f}"
    )
    return result


# =============================================================================
# Stage 3 — VEST vote extraction and turnout
# =============================================================================

def extract_vest_vote_totals(vest_gdf, year, precinct_id_col):
    """
    Extracts presidential vote columns from a VEST shapefile and computes
    per-precinct totals for Republican, Democrat, and all other candidates.

    Parameters
    ----------
    vest_gdf : GeoDataFrame
        Loaded VEST shapefile for the given year (geometry + attribute columns).
    year : int
        Election year (2016, 2020, or 2024).
    precinct_id_col : str
        Column that uniquely identifies each precinct.

    Returns
    -------
    DataFrame with columns:
        {precinct_id_col}, rep_votes, dem_votes, other_votes, total_votes
    """
    suffix = YEAR_SUFFIX.get(year)
    if suffix is None:
        raise ValueError(f"Unsupported year: {year}. Add it to YEAR_SUFFIX dict.")

    # Find all presidential columns for this year
    pre_cols = [c for c in vest_gdf.columns if re.match(rf"^G{suffix}PRE[A-Z]+$", c)]

    if not pre_cols:
        logging.warning(
            f"No presidential vote columns found for year {year}. "
            f"Expected pattern: G{suffix}PRE... — check VEST column names."
        )
        return vest_gdf[[precinct_id_col]].copy()

    logging.info(f"  Found {len(pre_cols)} presidential candidate columns for {year}.")

    # Identify Republican and Democrat columns by party code (4th character)
    rep_cols   = [c for c in pre_cols if c[4] == "R"]
    dem_cols   = [c for c in pre_cols if c[4] == "D"]
    other_cols = [c for c in pre_cols if c[4] not in ("R", "D")]

    votes = vest_gdf[[precinct_id_col]].copy()

    def _safe_sum(cols):
        """Sum columns, coercing to numeric and treating nulls as 0."""
        return (
            vest_gdf[cols]
            .apply(pd.to_numeric, errors="coerce")
            .fillna(0)
            .sum(axis=1)
        )

    votes["rep_votes"]   = _safe_sum(rep_cols)   if rep_cols   else 0
    votes["dem_votes"]   = _safe_sum(dem_cols)   if dem_cols   else 0
    votes["other_votes"] = _safe_sum(other_cols) if other_cols else 0
    votes["total_votes"] = votes[["rep_votes", "dem_votes", "other_votes"]].sum(axis=1)

    return votes


def calculate_turnout(precinct_votes_df, precinct_pop_df, precinct_id_col):
    """
    Merges vote totals with apportioned VAP to compute turnout rate.

    Parameters
    ----------
    precinct_votes_df : DataFrame
        Output of extract_vest_vote_totals.
    precinct_pop_df : DataFrame
        Output of apportion_blocks_to_precincts.
    precinct_id_col : str

    Returns
    -------
    DataFrame with additional columns:
        turnout_pct, rep_pct, dem_pct
        Rows where VAP == 0 get NaN turnout (flagged for QA).
    """
    df = precinct_votes_df.merge(precinct_pop_df, on=precinct_id_col, how="left")

    df["turnout_pct"] = (
        (df["total_votes"] / df["apportioned_vap"].replace(0, np.nan)) * 100
    ).round(2)

    df["rep_pct"] = (
        (df["rep_votes"] / df["total_votes"].replace(0, np.nan)) * 100
    ).round(2)

    df["dem_pct"] = (
        (df["dem_votes"] / df["total_votes"].replace(0, np.nan)) * 100
    ).round(2)

    # Flag implausible turnout for QA (can't have > 100% turnout)
    implausible = (df["turnout_pct"] > 100).sum()
    if implausible > 0:
        logging.warning(
            f"{implausible} precincts have turnout > 100% — likely a VAP "
            "apportionment or vote data issue. Review before modeling."
        )

    return df


# =============================================================================
# Stage 4 — ACS demographic downscaling (county → precinct)
# =============================================================================

def apportion_acs_to_precincts(precinct_df, acs_df, precinct_id_col,
                                county_col="county_clean",
                                acs_feature_cols=None):
    """
    Downscales county-level ACS demographics to precincts using population
    weight: each precinct receives its share of its county's total population.

    Parameters
    ----------
    precinct_df : DataFrame
        Must have: {precinct_id_col}, county_clean, apportioned_population
    acs_df : DataFrame
        Staged ACS data (e.g. from stg_census_income.csv).
        Must have: county_clean, census_year, and one or more feature columns.
    precinct_id_col : str
    county_col : str
        Join key between precincts and ACS (default: county_clean).
    acs_feature_cols : list, optional
        ACS columns to apportion. If None, all numeric non-key columns are used.

    Returns
    -------
    DataFrame: precinct_df with ACS feature columns appended.
    """
    if acs_feature_cols is None:
        key_cols = {precinct_id_col, county_col, "census_year",
                    "county_fips", "county_name", "GEO_ID"}
        acs_feature_cols = [
            c for c in acs_df.select_dtypes(include="number").columns
            if c not in key_cols
        ]

    # County-level population totals (sum of all precinct apportioned populations)
    county_pops = (
        precinct_df
        .groupby(county_col)["apportioned_population"]
        .sum()
        .rename("county_total_pop")
        .reset_index()
    )

    # Precinct's share of its county's total population
    df = precinct_df.merge(county_pops, on=county_col, how="left")
    df["_pop_share"] = (
        df["apportioned_population"] / df["county_total_pop"].replace(0, np.nan)
    )

    # Join ACS county-level values
    df = df.merge(acs_df[[county_col] + acs_feature_cols], on=county_col, how="left")

    # Apportion each ACS feature by population share
    # NOTE: This is appropriate for count-based variables.
    # Rate/percentage variables (e.g. pct_minority) should be used as-is
    # from the county level, not multiplied by pop_share.
    for col in acs_feature_cols:
        if col.startswith("pct_") or col.startswith("median_"):
            # Rates and medians: assign county value directly (no apportionment)
            pass
        else:
            df[col] = df[col] * df["_pop_share"]

    df = df.drop(columns=["county_total_pop", "_pop_share"])
    return df


# =============================================================================
# Stage 5 — County aggregation
# =============================================================================

def aggregate_to_county(precinct_gdf, precinct_id_col, county_col="county_clean"):
    """
    Rolls up precinct-level data to county level.

    Votes and population are summed. Turnout and party percentages are
    recalculated from the aggregated totals rather than averaged, which
    is the statistically correct approach. ACS rate columns (pct_*, median_*)
    are population-weighted averaged.

    Parameters
    ----------
    precinct_gdf : GeoDataFrame
        Full precinct-level output from build_precinct_features().
    precinct_id_col : str
    county_col : str

    Returns
    -------
    GeoDataFrame with county-level geometry (unioned from precincts)
    and aggregated feature columns.
    """
    logging.info("Aggregating precinct data to county level...")

    # Separate numeric aggregation from geometry union
    sum_cols   = ["total_votes", "rep_votes", "dem_votes", "other_votes",
                  "apportioned_population", "apportioned_vap"]
    sum_cols   = [c for c in sum_cols if c in precinct_gdf.columns]

    rate_cols  = [c for c in precinct_gdf.columns
                  if c.startswith("pct_") or c.startswith("median_")]

    # Aggregate counts
    county_df = (
        precinct_gdf
        .groupby(county_col)[sum_cols]
        .sum()
        .reset_index()
    )

    # Recalculate rates from aggregated totals
    if "total_votes" in county_df.columns and "apportioned_vap" in county_df.columns:
        county_df["turnout_pct"] = (
            county_df["total_votes"] / county_df["apportioned_vap"].replace(0, np.nan) * 100
        ).round(2)
    if "rep_votes" in county_df.columns:
        county_df["rep_pct"] = (
            county_df["rep_votes"] / county_df["total_votes"].replace(0, np.nan) * 100
        ).round(2)
    if "dem_votes" in county_df.columns:
        county_df["dem_pct"] = (
            county_df["dem_votes"] / county_df["total_votes"].replace(0, np.nan) * 100
        ).round(2)

    # Population-weighted average for rate columns
    if rate_cols and "apportioned_population" in precinct_gdf.columns:
        for col in rate_cols:
            if col in precinct_gdf.columns:
                weighted = (
                    precinct_gdf
                    .assign(_w=lambda x: x[col] * x["apportioned_population"])
                    .groupby(county_col)
                    .agg(_wsum=("_w", "sum"), _psum=("apportioned_population", "sum"))
                    .assign(**{col: lambda x: x["_wsum"] / x["_psum"].replace(0, np.nan)})
                    [[col]]
                    .reset_index()
                )
                county_df = county_df.merge(weighted, on=county_col, how="left")

    # Union precinct geometries to county polygons
    county_geom = (
        precinct_gdf[[county_col, "geometry"]]
        .dissolve(by=county_col)
        .reset_index()
    )

    county_gdf = county_geom.merge(county_df, on=county_col, how="left")
    logging.info(f"County aggregation complete: {len(county_gdf)} counties.")
    return county_gdf


# =============================================================================
# Top-level orchestrator for one year
# =============================================================================

def build_precinct_features(vest_gdf, blocks_gdf, acs_staging_dfs,
                             year, precinct_id_col):
    """
    Orchestrates Stages 1–4 for a single election year.

    Parameters
    ----------
    vest_gdf : GeoDataFrame
        Loaded VEST shapefile for this year (geometry + vote columns).
    blocks_gdf : GeoDataFrame
        Output of CensusBlockLoader.get_blocks_with_population().
    acs_staging_dfs : dict
        Keys: ACS category names (e.g. 'income', 'education').
        Values: DataFrames loaded from data/processed/stg_census_*.csv
    year : int
    precinct_id_col : str
        Column in vest_gdf that uniquely identifies each precinct.

    Returns
    -------
    GeoDataFrame: one row per precinct with geometry, votes, population,
                  turnout, and ACS demographics.
    """
    print(f"\nBuilding precinct features for {year}...")

    # --- Stage 1: CRS alignment ---
    print("  [1/4] Aligning coordinate reference systems...")
    vest_gdf, blocks_gdf = align_crs(vest_gdf, blocks_gdf)

    # --- Stage 2: Apportion blocks → precincts ---
    print("  [2/4] Apportioning census blocks to precincts...")
    pop_df = apportion_blocks_to_precincts(blocks_gdf, vest_gdf, precinct_id_col)

    # --- Stage 3: Extract votes + turnout ---
    print("  [3/4] Extracting vote totals and calculating turnout...")
    votes_df = extract_vest_vote_totals(vest_gdf, year, precinct_id_col)
    features_df = calculate_turnout(votes_df, pop_df, precinct_id_col)

    # --- Stage 4: ACS demographics ---
    print("  [4/4] Downscaling ACS demographics to precinct level...")

    # Detect which county column the VEST shapefile uses
    county_col = _detect_county_col(vest_gdf)

    # Add county identifier to features_df
    features_df = features_df.merge(
        vest_gdf[[precinct_id_col, county_col]].drop_duplicates(),
        on=precinct_id_col, how="left"
    )

    # Filter each ACS staging df to the matching census year and attach
    for category, acs_df in acs_staging_dfs.items():
        if "census_year" in acs_df.columns:
            acs_year_df = acs_df[acs_df["census_year"] == year].copy()
        else:
            acs_year_df = acs_df.copy()

        if acs_year_df.empty:
            logging.warning(f"No ACS data for category '{category}', year {year}. Skipping.")
            continue

        # Normalise county key to match VEST county column
        if "county_clean" in acs_year_df.columns and county_col != "county_clean":
            acs_year_df = acs_year_df.rename(columns={"county_clean": county_col})

        features_df = apportion_acs_to_precincts(
            features_df, acs_year_df,
            precinct_id_col=precinct_id_col,
            county_col=county_col
        )

    features_df["year"] = year

    # Attach geometry from VEST shapefile
    result_gdf = vest_gdf[[precinct_id_col, "geometry"]].merge(
        features_df, on=precinct_id_col, how="left"
    )

    print(f"  Done. {len(result_gdf):,} precincts assembled for {year}.")
    return gpd.GeoDataFrame(result_gdf, geometry="geometry", crs=vest_gdf.crs)


# =============================================================================
# Helpers
# =============================================================================

def _detect_county_col(gdf):
    """Finds the county FIPS column in a VEST shapefile by checking known names."""
    for candidate in COUNTY_FIPS_CANDIDATES:
        if candidate in gdf.columns:
            return candidate
    # Fall back: look for any column with 'county' in the name
    county_cols = [c for c in gdf.columns if "county" in c.lower()]
    if county_cols:
        logging.warning(
            f"County column not in standard list. Using: {county_cols[0]}"
        )
        return county_cols[0]
    raise KeyError(
        "Could not find a county column in the VEST shapefile. "
        f"Available columns: {list(gdf.columns)}"
    )
