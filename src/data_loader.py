import pandas as pd
import os

class DataLoader:
    """Handles the ingestion of raw CSV data from the data/raw/ directory."""
    
    def __init__(self, raw_dir="data/raw/"):
        self.raw_dir = raw_dir

    def _load_csv(self, filename, low_memory=False):
        """Helper to load a CSV with consistent NA handling used in the original notebook."""
        path = os.path.join(self.raw_dir, filename)
        if not os.path.exists(path):
            print(f"Warning: File not found - {path}")
            return None
        
        return pd.read_csv(
            path, 
            keep_default_na=False, 
            na_values=[''], 
            low_memory=low_memory
        )

    def load_election_data(self):
        """Loads raw election results for 2016, 2020, and 2024."""
        return {
            2016: self._load_csv('MO 2016 Election Results.csv'),
            2020: self._load_csv('MO 2020 Election Results.csv', low_memory=True),
            2024: self._load_csv('MO 2024 Election Results.csv')
        }

    def load_census_data(self, year):
        """
        Loads the 5 ACS census categories for a specific year.
        Categories: Income, Education, Race, Commute, and Sex by Age.
        """
        categories = {
            "income": f"MO {year} Census Income.csv",
            "education": f"MO {year} Census Education.csv",
            "race": f"MO {year} Census Race.csv",
            "commute": f"MO {year} Census Commute.csv",
            "sex_age": f"MO {year} Census Sex by Age.csv"
        }
        
        return {cat: self._load_csv(fname) for cat, fname in categories.items()}

    def load_polling_locations(self):
        """Loads the 2020 Polling Locations dataset."""
        return self._load_csv('MO 2020 Polling Locations.csv')