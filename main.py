import pandas as pd
import os
from src.data_loader import DataLoader
from src.preprocessor import clean_election_data, clean_census_data

# --- NEW GEOSPATIAL IMPORTS ---
from src.geo_loader import GeoLoader
from src.geo_processor import geocode_polling_locations, process_spatial_join
from src.visualizer import generate_regional_density_map, generate_commute_bar_chart

# Configuration
RAW_DIR = "data/raw/"
PROCESSED_DIR = "data/processed/"
GEO_RAW_DIR = "data/geo/raw/"
GEO_PROCESSED_DIR = "data/geo/processed/"

def main():
    loader = DataLoader(raw_dir=RAW_DIR)
    
    # Ensure all output directories exist
    os.makedirs(PROCESSED_DIR, exist_ok=True)
    os.makedirs(GEO_PROCESSED_DIR, exist_ok=True)

    # --- 1. Process Election Data ---
    print("Staging Election Data...")
    raw_elections = loader.load_election_data()
    election_dfs = []
    for year, df in raw_elections.items():
        if df is not None:
            election_dfs.append(clean_election_data(df, year))
    
    if election_dfs:
        stg_election_results = pd.concat(election_dfs, ignore_index=True)
        stg_election_results.to_csv(os.path.join(PROCESSED_DIR, "stg_election_results.csv"), index=False)
        print("  - Saved stg_election_results.csv")

    # --- 2. Process Census Data ---
    print("\nStaging Census Data...")
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
    for cat, dfs in census_collector.items():
        if dfs:
            combined_df = pd.concat(dfs, ignore_index=True)
            filename = f"stg_census_{cat}.csv"
            combined_df.to_csv(os.path.join(PROCESSED_DIR, filename), index=False)
            print(f"  - Saved {filename}")

    # --- 4. Process Polling Locations (Tabular) ---
    print("\nStaging Polling Locations...")
    df_polling = loader.load_polling_locations()
    if df_polling is not None:
        df_polling.to_csv(os.path.join(PROCESSED_DIR, "stg_polling_locations.csv"), index=False)
        print("  - Saved stg_polling_locations.csv")

    # --- 5. Geospatial Pipeline ---
    print("\n" + "="*40)
    print("STARTING GEOSPATIAL PIPELINE")
    print("="*40)
    
    geo_loader = GeoLoader(geo_raw_dir=GEO_RAW_DIR)

    if df_polling is not None:
        print("Geocoding polling locations... (This may take a moment)")
        polling_gdf = geocode_polling_locations(df_polling)

        for year in [2016, 2020, 2024]:
            print(f"\nProcessing spatial data for {year}...")
            precinct_shapefile = geo_loader.get_precinct_shapefile(year)

            if precinct_shapefile is not None:
                # 1. Join points to polygons and calculate density
                yearly_density_gdf = process_spatial_join(precinct_shapefile, polling_gdf)

                # 2. Save the fully calculated spatial data for Tableau/QGIS
                geo_output = os.path.join(GEO_PROCESSED_DIR, f"mo_density_{year}.geojson")
                yearly_density_gdf.to_file(geo_output, driver="GeoJSON")
                print(f"  - Saved {geo_output}")

                # 3. Generate Presentation Visuals (Only for 2020)
                if year == 2020:
                    print("  - Generating 2020 Maps and Charts for presentation...")
                    generate_regional_density_map(yearly_density_gdf, output_dir=GEO_PROCESSED_DIR)
                    generate_commute_bar_chart(yearly_density_gdf, output_dir=GEO_PROCESSED_DIR)

    print("\nPipeline Complete! All tabular and geospatial data is ready for analysis.")

if __name__ == "__main__":
    main()