import argparse
import os
import logging
import time

import pandas as pd
import geopandas as gpd

# Helper modules — data staging
from src.data_loader  import DataLoader
from src.preprocessor import clean_election_data, clean_census_data, clean_polling_data

# Helper modules — geospatial (polling density, original 2020 pipeline)
from src.geo_loader    import GeoLoader
from src.geo_processor import geocode_polling_locations, calculate_spatial_density
from src.geo_visualizer import generate_regional_density_map, generate_commute_bar_chart

# Helper modules — precinct-level predictive model (multi-year)
from src.model_runner import run_model

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
RAW_DIR          = "data/raw/"
PROCESSED_DIR    = "data/processed/"
GEO_RAW_DIR      = "data/geo/raw/"
GEO_PROCESSED_DIR = "data/geo/processed/"
GEO_OUTPUT_DIR   = "data/geo/output/"
LOG_DIR          = "logs/"

# Cached geocoded polling locations — avoids repeating the 40-minute geocoding run
GEOCODED_CACHE_FILE = "data/geo/processed/mo_polling_geocoded_cache.geojson"


# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------

def setup_logging():
    """Configures logging to write to a file (logs/pipeline.log)."""
    os.makedirs(LOG_DIR, exist_ok=True)
    log_file = os.path.join(LOG_DIR, "pipeline.log")
    logging.basicConfig(
        filename=log_file,
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    logging.info("=" * 50)
    logging.info("NEW PIPELINE EXECUTION STARTED")
    logging.info("=" * 50)


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------

def parse_args():
    """
    Parses command-line arguments.

    Flags
    -----
    --model-only
        Skip Stages 1–4 (data staging + polling geocoding) and jump
        directly to Stage 5 (precinct model). Requires that the three
        precinct GeoPackages (precinct_features_2016/2020/2024.gpkg)
        already exist in data/geo/output/.

    Usage examples
    --------------
    Full pipeline (all stages):
        python main.py

    Model only (assumes GeoPackages exist):
        python main.py --model-only
    """
    parser = argparse.ArgumentParser(
        description="Missouri Voter Resource Allocation Pipeline"
    )
    parser.add_argument(
        "--model-only",
        action="store_true",
        help=(
            "Skip data staging and geo pipeline (Stages 1–4). "
            "Runs only the precinct-level predictive model (Stage 5). "
            "Requires precinct_features_*.gpkg files to exist in data/geo/output/."
        ),
    )
    return parser.parse_args()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    args = parse_args()
    setup_logging()
    overall_start = time.time()

    # Ensure output directories exist regardless of run mode
    os.makedirs(PROCESSED_DIR, exist_ok=True)
    os.makedirs(GEO_PROCESSED_DIR, exist_ok=True)
    os.makedirs(GEO_OUTPUT_DIR, exist_ok=True)

    if args.model_only:
        print("=" * 50)
        print("MODE: --model-only")
        print("Skipping Stages 1–4. Running Stage 5 only.")
        print("=" * 50)
        logging.info("Pipeline started in --model-only mode.")
    else:
        # ---------------------------------------------------------------
        # Stage 1 — Election Data
        # Loads raw presidential election results for 2016, 2020, and 2024,
        # standardises precinct/county names, and writes a single staging CSV.
        # ---------------------------------------------------------------
        print("Stage 1: Staging Election Data...")
        logging.info("Starting Election Data Processing.")

        loader = DataLoader(raw_dir=RAW_DIR)
        raw_elections = loader.load_election_data()
        election_dfs = [
            clean_election_data(df, year)
            for year, df in raw_elections.items()
            if df is not None
        ]
        if election_dfs:
            stg_elections = pd.concat(election_dfs, ignore_index=True)
            stg_elections.to_csv(
                os.path.join(PROCESSED_DIR, "stg_election_results.csv"), index=False
            )
            print("  - Saved stg_election_results.csv")
            logging.info(f"Election data staged. Total rows: {len(stg_elections)}")

        # ---------------------------------------------------------------
        # Stage 2 — Census Data
        # Loops through each election year and each ACS category, cleans
        # the raw Census CSVs, and aggregates them into per-category staging
        # files covering all three years.
        # ---------------------------------------------------------------
        print("\nStage 2: Staging Census Data...")
        logging.info("Starting Census Data Processing.")

        categories = ["income", "education", "race", "commute", "sex_age"]
        census_collector = {cat: [] for cat in categories}

        for year in [2016, 2020, 2024]:
            year_data = loader.load_census_data(year)
            for cat in categories:
                df = year_data.get(cat)
                if df is not None:
                    census_collector[cat].append(clean_census_data(df, year))

        for cat, dfs in census_collector.items():
            if dfs:
                combined = pd.concat(dfs, ignore_index=True)
                fname = f"stg_census_{cat}.csv"
                combined.to_csv(os.path.join(PROCESSED_DIR, fname), index=False)
                print(f"  - Saved {fname}")
                logging.info(f"Census category staged: {cat}")

        # ---------------------------------------------------------------
        # Stage 3 — Polling Locations (Tabular)
        # Ingests 2020 polling location addresses and writes a clean staging
        # CSV for use in the county-level prescriptive model.
        # ---------------------------------------------------------------
        print("\nStage 3: Staging Polling Locations...")
        logging.info("Starting Polling Location Processing.")

        df_polling_raw = loader.load_polling_locations()
        df_polling = None
        if df_polling_raw is not None:
            df_polling = clean_polling_data(df_polling_raw)
            df_polling.to_csv(
                os.path.join(PROCESSED_DIR, "stg_polling_locations.csv"), index=False
            )
            print("  - Saved stg_polling_locations.csv")
            logging.info("Polling locations staged.")

        # ---------------------------------------------------------------
        # Stage 4 — Geospatial Pipeline (Polling Density)
        # Geocodes polling addresses, spatially joins them to precinct
        # boundaries, and calculates sq-miles-per-polling-place density.
        # Results feed the original county-level prescriptive model.
        #
        # Note: The VEST + Census block precinct feature pipeline (which
        # feeds the Stage 5 multi-year model) runs separately via
        # geo_pipeline_dev.ipynb and caches its output as .gpkg files in
        # data/geo/output/. Run that notebook before Stage 5 if the
        # .gpkg files do not yet exist.
        # ---------------------------------------------------------------
        print("\nStage 4: Geospatial Pipeline (Polling Density)...")
        logging.info("Starting Geospatial Pipeline.")

        geo_loader = GeoLoader(geo_raw_dir=GEO_RAW_DIR)

        if df_polling is not None:
            # Cache check: geocoding takes ~40 min; reuse if already done
            if os.path.exists(GEOCODED_CACHE_FILE):
                print(f"  Cache found — loading geocoded polling from {GEOCODED_CACHE_FILE}")
                logging.info("Geocoded cache found. Skipping geocoding.")
                polling_gdf = gpd.read_file(GEOCODED_CACHE_FILE)
            else:
                print("  No cache — starting geocoding (~40 min)...")
                logging.info("No cache found. Starting geocoding.")
                geo_start   = time.time()
                polling_gdf = geocode_polling_locations(df_polling)
                logging.info(f"Geocoding done in {time.time() - geo_start:.2f}s.")
                polling_gdf.to_file(GEOCODED_CACHE_FILE, driver="GeoJSON")
                print(f"  Geocoded data cached to {GEOCODED_CACHE_FILE}")
                logging.info("Geocoded data cached.")

            for year in [2016, 2020, 2024]:
                print(f"\n  Spatial join for {year}...")
                logging.info(f"Processing spatial joins for {year}.")
                precinct_shp = geo_loader.get_precinct_shapefile(year)
                if precinct_shp is not None:
                    density_gdf = calculate_spatial_density(precinct_shp, polling_gdf)
                    geo_out = os.path.join(GEO_PROCESSED_DIR, f"mo_density_{year}.geojson")
                    density_gdf.to_file(geo_out, driver="GeoJSON")
                    print(f"  - Saved {geo_out}")
                    logging.info(f"Saved density GeoJSON for {year}.")

                    if year == 2020:
                        print("  - Generating 2020 density map and commute chart...")
                        logging.info("Generating 2020 presentation visuals.")
                        generate_regional_density_map(density_gdf, output_dir=GEO_PROCESSED_DIR)
                        generate_commute_bar_chart(density_gdf, output_dir=GEO_PROCESSED_DIR)

    # -------------------------------------------------------------------
    # Stage 5 — Precinct-Level Predictive Model (Multi-Year)
    # Reads precinct_features_{year}.gpkg files built by geo_pipeline_dev.ipynb,
    # trains RF regressor + classifier with temporal cross-validation, and
    # writes predictions for 2024 precincts to data/processed/ (CSV) and
    # data/geo/output/ (GeoPackage with geometry for mapping).
    # -------------------------------------------------------------------
    print("\nStage 5: Precinct-Level Predictive Model...")
    logging.info("Starting Stage 5: Precinct-level model.")

    # Guard: check that the GeoPackages exist before running the model
    missing_gpkgs = [
        f"data/geo/output/precinct_features_{yr}.gpkg"
        for yr in [2016, 2020, 2024]
        if not os.path.exists(f"data/geo/output/precinct_features_{yr}.gpkg")
    ]
    if missing_gpkgs:
        print("\n  WARNING: The following GeoPackages are missing:")
        for f in missing_gpkgs:
            print(f"    {f}")
        print(
            "\n  Stage 5 requires output from the geo pipeline notebook.\n"
            "  Run geo_pipeline_dev.ipynb first to generate these files,\n"
            "  then re-run main.py (or main.py --model-only).\n"
            "  Skipping Stage 5."
        )
        logging.warning(f"Stage 5 skipped — missing GeoPackages: {missing_gpkgs}")
    else:
        run_model(geo_output_dir=GEO_OUTPUT_DIR, processed_dir=PROCESSED_DIR)

    # -------------------------------------------------------------------
    # Wrap-up
    # -------------------------------------------------------------------
    total_minutes = (time.time() - overall_start) / 60
    print(f"\nPipeline complete. Total runtime: {total_minutes:.2f} minutes.")
    logging.info(f"PIPELINE COMPLETE. Total runtime: {total_minutes:.2f} minutes.")
    logging.info("=" * 50)


if __name__ == "__main__":
    main()
