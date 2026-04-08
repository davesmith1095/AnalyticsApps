import pandas as pd

# ==========================================
# ELECTION DATA PREPROCESSING
# ==========================================

def normalize_precinct_name(name):
    """
    Standardize precinct names for consistent joining across datasets.
    Missouri precinct names vary (e.g., 'Ward 1', 'WARD 1', 'Ward #1').
    """
    return (
        str(name)
        .upper()
        .replace('#', '')
        .replace('  ', ' ')
        .strip()
    )

def clean_election_data(df, year):
    """Applies preprocessing steps to election data (Section 3 of Notebook)."""
    df = df.copy()
    
    # Add year
    df['year'] = year
    
    # Filter for Presidential results
    if 'office' in df.columns:
        df = df[df['office'] == 'President']
        
    # Drop unnecessary columns
    df = df.drop(columns=['precinct_code'], errors='ignore')
    
    # Normalize precinct names
    if 'precinct' in df.columns:
        df['precinct_clean'] = df['precinct'].apply(normalize_precinct_name)
        
    # Clean county names
    if 'county' in df.columns:
        df['county_clean'] = df['county'].str.upper().str.strip()
        
    # Select specific columns as structured in the notebook
    cols = ['year', 'county', 'county_clean', 'precinct', 'precinct_clean', 
            'office', 'district', 'candidate', 'party', 'votes']
    
    # Return only existing columns to prevent KeyErrors across different years
    cols = [c for c in cols if c in df.columns]
    return df[cols].reset_index(drop=True)


# ==========================================
# CENSUS DATA PREPROCESSING
# ==========================================

def clean_census_data(df, year):
    """
    Applies base preprocessing steps to ACS Census data (Section 4 of Notebook).
    Automatically routes to the correct category logic based on columns present.
    """
    df = df.copy()
    
    # Remove header artifact row where GEO_ID = "Geography" and filter for Counties
    if "GEO_ID" in df.columns:
        df = df[df["GEO_ID"] != "Geography"]
        df = df[df["GEO_ID"].str.contains('0500000US', na=False)]
        df["county_fips"] = df["GEO_ID"].str[-5:]
    
    df["census_year"] = year
    
    # Format county names (Explicitly leaving ' city' for St. Louis FIPS distinctions)
    if "NAME" in df.columns:
        df["county_name"] = df["NAME"].str.replace(", Missouri", "", regex=False).str.replace(" County", "", regex=False)
        df["county_clean"] = df["county_name"].str.upper().str.strip()
        
    # Route to specific category logic based on the census metric IDs
    if 'B19013_001E' in df.columns:
        return _clean_census_income(df)
    elif 'B15003_001E' in df.columns:
        return _clean_census_education(df)
    elif 'B02001_001E' in df.columns:
        return _clean_census_race(df)
    elif 'B08301_001E' in df.columns:
        return _clean_census_commute(df)
    elif 'B01001_001E' in df.columns:
        return _clean_census_sex_age(df)
    else:
        return df.reset_index(drop=True)


# --- Category Specific Helper Functions ---

def _clean_census_income(df):
    df = df.rename(columns={'B19013_001E': 'median_household_income'})
    df['median_household_income'] = pd.to_numeric(df['median_household_income'], errors='coerce')
    
    cols = ['census_year', 'county_fips', 'county_name', 'county_clean', 'median_household_income']
    return df[[c for c in cols if c in df.columns]].reset_index(drop=True)

def _clean_census_education(df):
    df = df.rename(columns={
        'B15003_001E': 'total_pop_25_plus',
        'B15003_017E': 'hs_diploma',
        'B15003_022E': 'bachelors_degree',
        'B15003_023E': 'masters_degree',
        'B15003_024E': 'professional_degree',
        'B15003_025E': 'doctorate_degree'
    })
    
    num_cols = ['total_pop_25_plus', 'hs_diploma', 'bachelors_degree', 'masters_degree', 'professional_degree', 'doctorate_degree']
    for col in num_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')
            
    df['pct_bachelors_plus'] = (
        (df.get('bachelors_degree', 0) + df.get('masters_degree', 0) + 
         df.get('professional_degree', 0) + df.get('doctorate_degree', 0)) 
        / df['total_pop_25_plus'] * 100
    ).round(2)
    
    cols = ['census_year', 'county_fips', 'county_name', 'county_clean', 'total_pop_25_plus', 'pct_bachelors_plus']
    return df[[c for c in cols if c in df.columns]].reset_index(drop=True)

def _clean_census_race(df):
    df = df.rename(columns={
        'B02001_001E': 'total_population',
        'B02001_002E': 'white_alone',
        'B02001_003E': 'black_alone'
    })
    
    for col in ['total_population', 'white_alone', 'black_alone']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')
            
    df['pct_white'] = (df.get('white_alone', 0) / df.get('total_population', 1) * 100).round(2)
    df['pct_minority'] = ((df.get('total_population', 1) - df.get('white_alone', 0)) / df.get('total_population', 1) * 100).round(2)
    
    cols = ['census_year', 'county_fips', 'county_name', 'county_clean', 'total_population', 'pct_white', 'pct_minority']
    return df[[c for c in cols if c in df.columns]].reset_index(drop=True)

def _clean_census_commute(df):
    df = df.rename(columns={
        'B08301_001E': 'total_workers',
        'B08301_003E': 'drove_alone',
        'B08301_010E': 'public_transit',
        'B08301_019E': 'walked'
    })
    
    for col in ['total_workers', 'drove_alone', 'public_transit', 'walked']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')
            
    df['pct_no_vehicle'] = ((df.get('public_transit', 0) + df.get('walked', 0)) / df['total_workers'] * 100).round(2)
    
    cols = ['census_year', 'county_fips', 'county_name', 'county_clean', 'total_workers', 'pct_no_vehicle']
    return df[[c for c in cols if c in df.columns]].reset_index(drop=True)

# ==========================================
# POLLING LOCATION PREPROCESSING
# ==========================================

def clean_polling_data(df):
    """
    Applies preprocessing steps to polling location data (Section 5 of Notebook).
    Adds normalized county/precinct keys and strips the address for geocoding.
    """
    df = df.copy()

    if 'county_name' in df.columns:
        df['county_clean'] = df['county_name'].str.strip().str.upper()

    if 'precinct_name' in df.columns:
        df['precinct_clean'] = df['precinct_name'].apply(normalize_precinct_name)

    if 'address' in df.columns:
        df['polling_address'] = df['address'].str.strip()

    return df.reset_index(drop=True)


def _clean_census_sex_age(df):
    for col in df.columns:
        if col.startswith('B01001'):
            df[col] = pd.to_numeric(df[col], errors='coerce')
            
    df['total_population'] = df.get('B01001_001E', 0)
    
    male_18plus_cols = [f'B01001_{str(i).zfill(3)}E' for i in range(7, 26)]
    female_18plus_cols = [f'B01001_{str(i).zfill(3)}E' for i in range(31, 50)]
    
    m_cols = [c for c in male_18plus_cols if c in df.columns]
    f_cols = [c for c in female_18plus_cols if c in df.columns]
    
    df['voting_age_population'] = df[m_cols].sum(axis=1) + df[f_cols].sum(axis=1)
    df['pct_voting_age'] = (df['voting_age_population'] / df['total_population'] * 100).round(2)
    
    cols = ['census_year', 'county_fips', 'county_name', 'county_clean', 'total_population', 'voting_age_population', 'pct_voting_age']
    return df[[c for c in cols if c in df.columns]].reset_index(drop=True)