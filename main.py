import pandas as pd
import os
import logging
import time

from src.data_loader import DataLoader
from src.preprocessor import clean_election_data, clean_census_data
from src.geo_loader import GeoLoader
from src.geo_processor import geocode_polling_locations, process_spatial_join
from src.geo_visualizer import generate_regional_density_map, generate_commute_bar_chart

# Configuration
RAW_DIR = "data/raw/"
PROCESSED_DIR = "data/processed/"
GEO_RAW_DIR = "data/geo/raw/"
GEO_PROCESSED_DIR = "data/geo/processed/"
LOG_DIR = "logs/"

def setup_logging():
    """Configures logging to write to both a file and keep the console clean."""
    os.makedirs(LOG_DIR, exist_ok=True)
    log_file = os.path.join(LOG_DIR, 'pipeline.log')
    
    logging.basicConfig(
        filename=log_file,
        level=logging.INFO,
        format='%(asctime)s | %(levelname)s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    logging.info("="*50)
    logging.info("NEW PIPELINE EXECUTION STARTED")
    logging.info("="*50)

def main():
    # Initialize timing and logging
    setup_logging()
    overall_start_time = time.time()
    
    # Ensure all output directories exist
    os.makedirs(PROCESSED_DIR, exist_ok=True)
    os.makedirs(GEO_PROCESSED_DIR, exist_ok=True)

    loader = DataLoader(raw_dir=RAW_DIR)

    # --- 1. Process Election Data ---
    # Loads raw election results for all years, cleans the precinct names, filters for presidential races, and combines them into a single staging file.
    print("Staging Election Data...")
    logging.info("Starting Election Data Processing.")
    raw_elections = loader.load_election_data()
    election_dfs = []
    for year, df in raw_elections.items():
        if df is not None:
            election_dfs.append(clean_election_data(df, year))
    
    if election_dfs:
        stg_election_results = pd.concat(election_dfs, ignore_index=True)
        stg_election_results.to_csv(os.path.join(PROCESSED_DIR, "stg_election_results.csv"), index=False)
        print("  - Saved stg_election_results.csv")
        logging.info(f"Successfully staged election data. Total rows: {len(stg_election_results)}")

    # --- 2. Process Census Data ---
    # Loops through each election year to load demographic census categories, standardizes the county names, and aggregates them into category-specific staging files.
    print("\nStaging Census Data...")
    logging.info("Starting Census Data Processing.")
    categories = ["income", "education", "race", "commute", "sex_age"]
    census_collector = {cat: [] for cat in categories}

    for year in [2016, 2020, 2024]:
        year_data = loader.load_census_data(year)
        for cat in categories:
            df = year_data.get(cat)
            if df is not None:
                cleaned_df = clean_census_data(df, year)
                census_collector[cat].append(cleaned_df)

    # --- 3. Save All Census Staging Tables ---
    # Writes the aggregated census dictionaries out to clean, physical CSV files for downstream analysis.
    for cat, dfs in census_collector.items():
        if dfs:
            combined_df = pd.concat(dfs, ignore_index=True)
            filename = f"stg_census_{cat}.csv"
            combined_df.to_csv(os.path.join(PROCESSED_DIR, filename), index=False)
            print(f"  - Saved {filename}")
            logging.info(f"Successfully staged census category: {cat}.")

    # --- 4. Process Polling Locations (Tabular) ---
    # Ingests the 2020 polling location addresses and prepares them for both tabular analysis and geospatial geocoding.
    print("\nStaging Polling Locations...")
    logging.info("Starting Tabular Polling Location Processing.")
    df_polling = loader.load_polling_locations()
    if df_polling is not None:
        df_polling.to_csv(os.path.join(PROCESSED_DIR, "stg_polling_locations.csv"), index=False)
        print("  - Saved stg_polling_locations.csv")
        logging.info("Successfully staged tabular polling locations.")

    # --- 5. Geospatial Pipeline ---
    # Geocodes the physical polling addresses into coordinates and maps them against yearly precinct boundaries to calculate spatial density and coverage areas.
    print("\n" + "="*40)
    print("STARTING GEOSPATIAL PIPELINE")
    print("="*40)
    logging.info("Starting Geospatial Pipeline. (Note: Geocoding may take significant time).")
    
    geo_loader = GeoLoader(geo_raw_dir=GEO_RAW_DIR)

    if df_polling is not None:
        print("Geocoding polling locations... (This may take a moment)")
        geo_start = time.time()
        polling_gdf = geocode_polling_locations(df_polling)
        logging.info(f"Geocoding completed in {time.time() - geo_start:.2f} seconds.")

        for year in [2016, 2020, 2024]:
            print(f"\nProcessing spatial data for {year}...")
            logging.info(f"Processing spatial joins for year {year}...")
            precinct_shapefile = geo_loader.get_precinct_shapefile(year)

            if precinct_shapefile is not None:
                yearly_density_gdf = process_spatial_join(precinct_shapefile, polling_gdf)

                geo_output = os.path.join(GEO_PROCESSED_DIR, f"mo_density_{year}.geojson")
                yearly_density_gdf.to_file(geo_output, driver="GeoJSON")
                print(f"  - Saved {geo_output}")
                logging.info(f"Saved processed geospatial data for {year}.")

                if year == 2020:
                    print("  - Generating 2020 Maps and Charts for presentation...")
                    logging.info("Generating presentation visuals for 2020.")
                    generate_regional_density_map(yearly_density_gdf, output_dir=GEO_PROCESSED_DIR)
                    generate_commute_bar_chart(yearly_density_gdf, output_dir=GEO_PROCESSED_DIR)

    # Wrap up execution and calculate total runtime
    overall_end_time = time.time()
    total_minutes = (overall_end_time - overall_start_time) / 60
    
    print("\nPipeline Complete! All tabular and geospatial data is ready for analysis.")
    logging.info(f"PIPELINE COMPLETE. Total execution time: {total_minutes:.2f} minutes.")
    logging.info("="*50)

if __name__ == "__main__":
    main()