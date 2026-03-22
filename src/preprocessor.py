import pandas as pd

def clean_election_data(df, year):
    """Applies preprocessing steps to election data."""
    df = df.copy()
    df["year"] = year
    # Remove precinct_code if present (consistent with notebook requirements)
    df = df.drop(columns=["precinct_code"], errors="ignore")
    # Normalize precinct names
    df["precinct_clean"] = (
        df["precinct"].astype(str).str.upper()
        .str.replace("#", "", regex=False)
        .str.replace("  ", " ", regex=False).str.strip()
    )
    # Filter for Presidential results as specified in project focus
    if 'office' in df.columns:
        df = df[df['office'].str.contains('President', case=False, na=False)]
    return df

def clean_census_data(df, year):
    """Applies preprocessing steps to ACS Census data."""
    df = df.copy()
    # Remove header artifact row where GEO_ID = "Geography"
    df = df[df["GEO_ID"] != "Geography"]
    # Remove blank export columns (Unnamed)
    df = df.loc[:, ~df.columns.str.contains("^Unnamed")]
    # Extract and normalize county name
    df["county_clean"] = (
        df["NAME"].str.replace(", Missouri", "", regex=False)
        .str.replace(" County", "", regex=False).str.upper()
    )
    df["census_year"] = year
    return df