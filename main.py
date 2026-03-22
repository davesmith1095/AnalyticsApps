import pandas as pd
import os
from src.data_loader import DataLoader
from src.preprocessor import clean_election_data, clean_census_data

# Configuration
RAW_DIR = "data/raw/"
PROCESSED_DIR = "data/processed/"

def main():
    loader = DataLoader(raw_dir=RAW_DIR)
    os.makedirs(PROCESSED_DIR, exist_ok=True)

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

    # --- 2. Process Census Data ---
    print("Staging Census Data...")
    # Categories defined in your DataLoader
    categories = ["income", "education", "race", "commute", "sex_age"]
    
    # We will store lists of dataframes for each category here
    census_collector = {cat: [] for cat in categories}

    for year in [2016, 2020, 2024]:
        year_data = loader.load_census_data(year)
        for cat in categories:
            df = year_data.get(cat)
            if df is not None:
                cleaned_df = clean_census_data(df, year)
                census_collector[cat].append(cleaned_df)

    # --- 3. Save All Staging Tables ---
    # Process and save each census category
    for cat, dfs in census_collector.items():
        if dfs:
            combined_df = pd.concat(dfs, ignore_index=True)
            filename = f"stg_census_{cat}.csv"
            combined_df.to_csv(os.path.join(PROCESSED_DIR, filename), index=False)
            print(f"  - Saved {filename}")

    # --- 4. Process Polling Locations ---
    print("Staging Polling Locations...")
    df_polling = loader.load_polling_locations()
    if df_polling is not None:
        # Note: Polling data is just for 2020 per your colleague's notes
        df_polling.to_csv(os.path.join(PROCESSED_DIR, "stg_polling_locations.csv"), index=False)

    print(f"\nStaging Complete. All files are in {PROCESSED_DIR}")

if __name__ == "__main__":
    main()