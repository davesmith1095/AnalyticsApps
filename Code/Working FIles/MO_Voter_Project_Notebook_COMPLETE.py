# =============================================================================
# MISSOURI VOTER RESOURCE ALLOCATION PROJECT
# =============================================================================
# Course: 5576 Analytics Applications
# Project: Prescriptive and Predictive Voter Resource Allocation
# Focus: Missouri Presidential Elections (2016, 2020, 2024)
# =============================================================================
#
# FILES REQUIRED (upload as notebook assets before execution):
# ------------------------------------------------------------
# Election Data:
#   - MO_2016_Election_Results.csv
#   - MO_2020_Election_Results.csv
#   - MO_2024_Election_Results.csv
#
# Census Data:
#   - MO_2020_Census_Income.csv
#   - MO_2020_Census_Education.csv
#   - MO_2020_Census_Race.csv
#   - MO_2020_Census_Sex_by_Age.csv
#   - MO_2020_Census_Commute.csv
#
# Polling Location Data:
#   - MO_2020_Polling_Locations.csv
#
# TOTAL: 9 CSV files
#
# =============================================================================
#
# NOTEBOOK STRUCTURE:
# -------------------
# SECTION 1: Setup & Documentation (Cells 1-4)
# SECTION 2: Data Ingestion (Cells 5-9)
# SECTION 3: Data Cleaning & Transformation (Cells 10-17)
# SECTION 4: Data Integration via SQL JOINs (Cells 18-21)
# SECTION 5: Data Quality Validation (Cells 22-23)
# SECTION 6: Exploratory Data Analysis (Cells 24-35)
#
# =============================================================================


# =============================================================================
# CELL 1 | MARKDOWN | Project Overview and Data Documentation
# =============================================================================

# Missouri Voter Resource Allocation Project

## Project Goal
Analyze historical presidential election results alongside demographic and geographic data to evaluate how polling resources could be allocated more effectively across Missouri precincts.

## Data Architecture Overview
The project integrates several categories of data:
- **Presidential election results** (precinct-level) - 2016, 2020, 2024
- **Census demographic data** (county-level) - ACS 5-Year Estimates
- **Polling location data** - Physical polling places by precinct

Combining these sources allows analysis of relationships between demographics, turnout patterns, and polling infrastructure.

## Why Presidential Elections?
Presidential election years were chosen because they produce the **highest voter turnout** and the **most consistent statewide participation**. Focusing on presidential election cycles provides a clearer signal for modeling voter demand and analyzing polling resource allocation across precincts.

## Programming Paradigms Demonstrated
- **Imperative (Python):** Data loading, cleaning, transformations
- **Declarative (SQL):** Joins, aggregations, analytical queries

## Coding Standards
- snake_case naming with meaningful variable names
- One output per cell
- Explanations in Markdown cells (not inline comments)
- Pandas method chaining
- List comprehensions over loops


# =============================================================================
# CELL 2 | MARKDOWN | Data Sources Documentation
# =============================================================================

# Data Sources

## Election Results (Presidential Elections: 2016, 2020, 2024)

**Source:** OpenElections Project (GitHub)
https://github.com/openelections/openelections-data-mo

**Files:**
- MO_2016_Election_Results.csv
- MO_2020_Election_Results.csv
- MO_2024_Election_Results.csv

**Schema Note:** The 2020 and 2024 election files include a `precinct_code` field not present in 2016. This column is dropped during preprocessing to maintain a consistent schema across years.

## Census Demographic Data

**Source:** U.S. Census Bureau – American Community Survey (ACS) 5-Year Estimates
https://data.census.gov

**Files:**
- MO_2020_Census_Income.csv
- MO_2020_Census_Education.csv
- MO_2020_Census_Race.csv
- MO_2020_Census_Sex_by_Age.csv
- MO_2020_Census_Commute.csv

These datasets provide county-level demographic indicators that overlap with the election years being analyzed.

## Polling Location Data

**Source:** MIT Election Data and Science Lab
https://electionlab.mit.edu/data

**File:**
- MO_2020_Polling_Locations.csv

Identifies physical polling places associated with precincts. Although the dataset reflects 2020, polling locations typically remain relatively stable across election cycles.


# =============================================================================
# CELL 3 | SQL | Environment Setup
# =============================================================================

USE DATABASE SNOWBEARAIR_DB;
CREATE SCHEMA IF NOT EXISTS VOTER_PROJECT;
USE SCHEMA VOTER_PROJECT;
USE WAREHOUSE SNOWFLAKE_LEARNING_WH;
USE ROLE TRAINING_ROLE;


# =============================================================================
# CELL 4 | PYTHON | Library Imports and Session Initialization
# =============================================================================

from snowflake.snowpark.context import get_active_session
import pandas as pd
import numpy as np

session = get_active_session()

print("=" * 70)
print("ENVIRONMENT INITIALIZED")
print("=" * 70)
print(f"Database:  {session.get_current_database()}")
print(f"Schema:    {session.get_current_schema()}")
print(f"Warehouse: {session.get_current_warehouse()}")
print("=" * 70)


# =============================================================================
# CELL 5 | MARKDOWN | Section 2: Data Ingestion
# =============================================================================

---
# SECTION 2: Data Ingestion
---

Load all raw data files into pandas DataFrames. Files are loaded exactly as downloaded to preserve raw source data. All transformations occur programmatically to ensure reproducibility.


# =============================================================================
# CELL 6 | PYTHON | Load Election Results (All Three Years)
# =============================================================================

raw_election_2016 = pd.read_csv('MO_2016_Election_Results.csv', keep_default_na=False, na_values=[''])
raw_election_2020 = pd.read_csv('MO_2020_Election_Results.csv', keep_default_na=False, na_values=[''], low_memory=False)
raw_election_2024 = pd.read_csv('MO_2024_Election_Results.csv', keep_default_na=False, na_values=[''])

print("=" * 70)
print("ELECTION DATA LOADED")
print("=" * 70)
print(f"2016 Election Results: {raw_election_2016.shape[0]:,} rows × {raw_election_2016.shape[1]} columns")
print(f"2020 Election Results: {raw_election_2020.shape[0]:,} rows × {raw_election_2020.shape[1]} columns")
print(f"2024 Election Results: {raw_election_2024.shape[0]:,} rows × {raw_election_2024.shape[1]} columns")
print("=" * 70)


# =============================================================================
# CELL 7 | PYTHON | Load Census Data (All Five Files)
# =============================================================================

raw_census_income = pd.read_csv('MO_2020_Census_Income.csv', keep_default_na=False, na_values=[''])
raw_census_education = pd.read_csv('MO_2020_Census_Education.csv', keep_default_na=False, na_values=[''])
raw_census_race = pd.read_csv('MO_2020_Census_Race.csv', keep_default_na=False, na_values=[''])
raw_census_sex_age = pd.read_csv('MO_2020_Census_Sex_by_Age.csv', keep_default_na=False, na_values=[''])
raw_census_commute = pd.read_csv('MO_2020_Census_Commute.csv', keep_default_na=False, na_values=[''])

print("=" * 70)
print("CENSUS DATA LOADED")
print("=" * 70)
print(f"Census Income:      {raw_census_income.shape[0]:,} rows × {raw_census_income.shape[1]} columns")
print(f"Census Education:   {raw_census_education.shape[0]:,} rows × {raw_census_education.shape[1]} columns")
print(f"Census Race:        {raw_census_race.shape[0]:,} rows × {raw_census_race.shape[1]} columns")
print(f"Census Sex/Age:     {raw_census_sex_age.shape[0]:,} rows × {raw_census_sex_age.shape[1]} columns")
print(f"Census Commute:     {raw_census_commute.shape[0]:,} rows × {raw_census_commute.shape[1]} columns")
print("=" * 70)


# =============================================================================
# CELL 8 | PYTHON | Load Polling Locations Data
# =============================================================================

raw_polling_locations = pd.read_csv('MO_2020_Polling_Locations.csv', keep_default_na=False, na_values=[''])

print("=" * 70)
print("POLLING LOCATIONS DATA LOADED")
print("=" * 70)
print(f"Polling Locations: {raw_polling_locations.shape[0]:,} rows × {raw_polling_locations.shape[1]} columns")
print("=" * 70)


# =============================================================================
# CELL 9 | PYTHON | Verify Raw Data Schema (Election Files)
# =============================================================================

print("=" * 70)
print("RAW ELECTION DATA SCHEMA COMPARISON")
print("=" * 70)
print(f"\n2016 Columns: {raw_election_2016.columns.tolist()}")
print(f"2020 Columns: {raw_election_2020.columns.tolist()}")
print(f"2024 Columns: {raw_election_2024.columns.tolist()}")
print(f"\nNote: 2020/2024 have 'precinct_code' column not in 2016 - will be dropped")
print("=" * 70)


# =============================================================================
# CELL 10 | MARKDOWN | Section 3: Data Cleaning & Transformation
# =============================================================================

---
# SECTION 3: Data Cleaning & Transformation
---

## Election Data Preprocessing Steps:
1. **Add YEAR column** - Enables combining datasets from different election cycles
2. **Drop precinct_code column** - Not present in 2016, dropped from 2020/2024 for consistency
3. **Normalize precinct names** - Standardize to uppercase, remove special characters
4. **Normalize county names** - Uppercase and trim whitespace
5. **Filter to Presidential results only** - Focus on highest-turnout races
6. **Standardize column order** - Ensure consistent schema across years

## Census Data Preprocessing Steps:
1. **Remove header description row** - ACS files have metadata in row 2
2. **Remove state-level totals** - Keep only county-level records
3. **Extract county FIPS code** - For joining across datasets
4. **Rename cryptic ACS codes** - Convert to readable column names
5. **Convert to numeric types** - Ensure proper data types for analysis


# =============================================================================
# CELL 11 | PYTHON | Define Precinct Name Normalization Function
# =============================================================================

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

print("✅ normalize_precinct_name() function defined")


# =============================================================================
# CELL 12 | PYTHON | Clean and Combine Election Results (Presidential Only)
# =============================================================================

election_2016_clean = (
    raw_election_2016
    .query("office == 'President'")
    .assign(year=2016)
    .assign(precinct_clean=lambda x: x['precinct'].apply(normalize_precinct_name))
    .assign(county_clean=lambda x: x['county'].str.upper().str.strip())
    [['year', 'county', 'county_clean', 'precinct', 'precinct_clean', 
      'office', 'district', 'candidate', 'party', 'votes']]
    .reset_index(drop=True)
)

election_2020_clean = (
    raw_election_2020
    .query("office == 'President'")
    .drop(columns=['precinct_code'], errors='ignore')
    .assign(year=2020)
    .assign(precinct_clean=lambda x: x['precinct'].apply(normalize_precinct_name))
    .assign(county_clean=lambda x: x['county'].str.upper().str.strip())
    [['year', 'county', 'county_clean', 'precinct', 'precinct_clean', 
      'office', 'district', 'candidate', 'party', 'votes']]
    .reset_index(drop=True)
)

election_2024_clean = (
    raw_election_2024
    .query("office == 'President'")
    .drop(columns=['precinct_code'], errors='ignore')
    .assign(year=2024)
    .assign(precinct_clean=lambda x: x['precinct'].apply(normalize_precinct_name))
    .assign(county_clean=lambda x: x['county'].str.upper().str.strip())
    [['year', 'county', 'county_clean', 'precinct', 'precinct_clean', 
      'office', 'district', 'candidate', 'party', 'votes']]
    .reset_index(drop=True)
)

print("=" * 70)
print("PRESIDENTIAL ELECTION DATA CLEANED")
print("=" * 70)
print(f"2016 Presidential: {election_2016_clean.shape[0]:,} rows")
print(f"2020 Presidential: {election_2020_clean.shape[0]:,} rows")
print(f"2024 Presidential: {election_2024_clean.shape[0]:,} rows")
print("=" * 70)


# =============================================================================
# CELL 13 | PYTHON | Combine All Election Years into Single Dataset
# =============================================================================

all_elections_df = pd.concat(
    [election_2016_clean, election_2020_clean, election_2024_clean], 
    ignore_index=True
)

print("=" * 70)
print("COMBINED ELECTION DATASET")
print("=" * 70)
print(f"Total Rows:    {all_elections_df.shape[0]:,}")
print(f"Total Columns: {all_elections_df.shape[1]}")
print(f"Years:         {sorted(all_elections_df['year'].unique().tolist())}")
print(f"Counties:      {all_elections_df['county_clean'].nunique()}")
print(f"Unique Precincts (all years): {all_elections_df['precinct_clean'].nunique()}")
print("=" * 70)
all_elections_df.head(10)


# =============================================================================
# CELL 14 | PYTHON | Clean Census Income Data
# =============================================================================

census_income_df = (
    raw_census_income
    .iloc[1:]
    .query("GEO_ID.str.contains('0500000US', na=False)")
    .assign(county_fips=lambda x: x['GEO_ID'].str[-5:])
    .assign(county_name=lambda x: x['NAME'].str.replace(', Missouri', '').str.replace(' County', ''))
    .assign(county_clean=lambda x: x['county_name'].str.upper().str.strip())
    .rename(columns={
        'B19013_001E': 'median_household_income',
        'B19013_001M': 'median_household_income_moe'
    })
    [['county_fips', 'county_name', 'county_clean', 'median_household_income', 'median_household_income_moe']]
    .assign(median_household_income=lambda x: pd.to_numeric(x['median_household_income'], errors='coerce'))
    .assign(median_household_income_moe=lambda x: pd.to_numeric(x['median_household_income_moe'], errors='coerce'))
    .reset_index(drop=True)
)

print(f"✅ Census Income cleaned: {census_income_df.shape[0]} counties")
census_income_df.head()


# =============================================================================
# CELL 15 | PYTHON | Clean Census Education Data
# =============================================================================

census_education_df = (
    raw_census_education
    .query("GEO_ID.str.contains('0500000US', na=False)")
    .assign(county_fips=lambda x: x['GEO_ID'].str[-5:])
    .assign(county_name=lambda x: x['NAME'].str.replace(', Missouri', '').str.replace(' County', ''))
    .assign(county_clean=lambda x: x['county_name'].str.upper().str.strip())
    .rename(columns={
        'B15003_001E': 'total_pop_25_plus',
        'B15003_017E': 'hs_diploma',
        'B15003_018E': 'ged',
        'B15003_019E': 'some_college_lt_1yr',
        'B15003_020E': 'some_college_1plus_yr',
        'B15003_021E': 'associates_degree',
        'B15003_022E': 'bachelors_degree',
        'B15003_023E': 'masters_degree',
        'B15003_024E': 'professional_degree',
        'B15003_025E': 'doctorate_degree'
    })
    [['county_fips', 'county_name', 'county_clean', 'total_pop_25_plus', 'hs_diploma', 'ged', 
      'some_college_lt_1yr', 'some_college_1plus_yr', 'associates_degree', 
      'bachelors_degree', 'masters_degree', 'professional_degree', 'doctorate_degree']]
    .reset_index(drop=True)
)

numeric_cols = ['total_pop_25_plus', 'hs_diploma', 'ged', 'some_college_lt_1yr', 
                'some_college_1plus_yr', 'associates_degree', 'bachelors_degree', 
                'masters_degree', 'professional_degree', 'doctorate_degree']

for col in numeric_cols:
    census_education_df[col] = pd.to_numeric(census_education_df[col], errors='coerce')

census_education_df = census_education_df.assign(
    pct_bachelors_plus=lambda x: (
        (x['bachelors_degree'] + x['masters_degree'] + x['professional_degree'] + x['doctorate_degree']) 
        / x['total_pop_25_plus'] * 100
    ).round(2),
    pct_hs_plus=lambda x: (
        (x['hs_diploma'] + x['ged'] + x['some_college_lt_1yr'] + x['some_college_1plus_yr'] + 
         x['associates_degree'] + x['bachelors_degree'] + x['masters_degree'] + 
         x['professional_degree'] + x['doctorate_degree']) 
        / x['total_pop_25_plus'] * 100
    ).round(2)
)

print(f"✅ Census Education cleaned: {census_education_df.shape[0]} counties")
census_education_df.head()


# =============================================================================
# CELL 16 | PYTHON | Clean Census Race Data
# =============================================================================

census_race_df = (
    raw_census_race
    .query("GEO_ID.str.contains('0500000US', na=False)")
    .assign(county_fips=lambda x: x['GEO_ID'].str[-5:])
    .assign(county_name=lambda x: x['NAME'].str.replace(', Missouri', '').str.replace(' County', ''))
    .assign(county_clean=lambda x: x['county_name'].str.upper().str.strip())
    .rename(columns={
        'B02001_001E': 'total_population',
        'B02001_002E': 'white_alone',
        'B02001_003E': 'black_alone',
        'B02001_004E': 'aian_alone',
        'B02001_005E': 'asian_alone',
        'B02001_006E': 'nhpi_alone',
        'B02001_007E': 'other_alone',
        'B02001_008E': 'two_or_more'
    })
    [['county_fips', 'county_name', 'county_clean', 'total_population', 'white_alone', 
      'black_alone', 'aian_alone', 'asian_alone', 'nhpi_alone', 'other_alone', 'two_or_more']]
    .reset_index(drop=True)
)

race_numeric_cols = ['total_population', 'white_alone', 'black_alone', 'aian_alone', 
                     'asian_alone', 'nhpi_alone', 'other_alone', 'two_or_more']

for col in race_numeric_cols:
    census_race_df[col] = pd.to_numeric(census_race_df[col], errors='coerce')

census_race_df = census_race_df.assign(
    pct_white=lambda x: (x['white_alone'] / x['total_population'] * 100).round(2),
    pct_black=lambda x: (x['black_alone'] / x['total_population'] * 100).round(2),
    pct_minority=lambda x: ((x['total_population'] - x['white_alone']) / x['total_population'] * 100).round(2)
)

print(f"✅ Census Race cleaned: {census_race_df.shape[0]} counties")
census_race_df.head()


# =============================================================================
# CELL 17 | PYTHON | Clean Census Sex by Age Data
# =============================================================================

census_sex_age_df = (
    raw_census_sex_age
    .query("GEO_ID.str.contains('0500000US', na=False)")
    .assign(county_fips=lambda x: x['GEO_ID'].str[-5:])
    .assign(county_name=lambda x: x['NAME'].str.replace(', Missouri', '').str.replace(' County', ''))
    .assign(county_clean=lambda x: x['county_name'].str.upper().str.strip())
    .reset_index(drop=True)
)

for col in census_sex_age_df.columns:
    if col.startswith('B01001'):
        census_sex_age_df[col] = pd.to_numeric(census_sex_age_df[col], errors='coerce')

male_18plus_cols = [f'B01001_{str(i).zfill(3)}E' for i in range(7, 26)]
female_18plus_cols = [f'B01001_{str(i).zfill(3)}E' for i in range(31, 50)]

male_18plus_cols = [c for c in male_18plus_cols if c in census_sex_age_df.columns]
female_18plus_cols = [c for c in female_18plus_cols if c in census_sex_age_df.columns]

census_sex_age_df = census_sex_age_df.assign(
    total_population=lambda x: x['B01001_001E'],
    male_population=lambda x: x['B01001_002E'],
    female_population=lambda x: x['B01001_026E'],
    male_18plus=lambda x: x[male_18plus_cols].sum(axis=1),
    female_18plus=lambda x: x[female_18plus_cols].sum(axis=1),
    voting_age_population=lambda x: x['male_18plus'] + x['female_18plus'],
    pct_voting_age=lambda x: (x['voting_age_population'] / x['total_population'] * 100).round(2)
)

census_sex_age_df = census_sex_age_df[['county_fips', 'county_name', 'county_clean', 'total_population', 
                                        'male_population', 'female_population',
                                        'voting_age_population', 'pct_voting_age']]

print(f"✅ Census Sex/Age cleaned: {census_sex_age_df.shape[0]} counties")
census_sex_age_df.head()


# =============================================================================
# CELL 18 | PYTHON | Clean Census Commute Data
# =============================================================================

census_commute_df = (
    raw_census_commute
    .query("GEO_ID.str.contains('0500000US', na=False)")
    .assign(county_fips=lambda x: x['GEO_ID'].str[-5:])
    .assign(county_name=lambda x: x['NAME'].str.replace(', Missouri', '').str.replace(' County', ''))
    .assign(county_clean=lambda x: x['county_name'].str.upper().str.strip())
    .rename(columns={
        'B08301_001E': 'total_workers',
        'B08301_003E': 'drove_alone',
        'B08301_004E': 'carpooled',
        'B08301_010E': 'public_transit',
        'B08301_019E': 'walked',
        'B08301_021E': 'worked_from_home'
    })
    [['county_fips', 'county_name', 'county_clean', 'total_workers', 'drove_alone', 
      'carpooled', 'public_transit', 'walked', 'worked_from_home']]
    .reset_index(drop=True)
)

commute_numeric_cols = ['total_workers', 'drove_alone', 'carpooled', 'public_transit', 
                        'walked', 'worked_from_home']

for col in commute_numeric_cols:
    census_commute_df[col] = pd.to_numeric(census_commute_df[col], errors='coerce')

census_commute_df = census_commute_df.assign(
    pct_drove_alone=lambda x: (x['drove_alone'] / x['total_workers'] * 100).round(2),
    pct_public_transit=lambda x: (x['public_transit'] / x['total_workers'] * 100).round(2),
    pct_no_vehicle=lambda x: ((x['public_transit'] + x['walked']) / x['total_workers'] * 100).round(2)
)

print(f"✅ Census Commute cleaned: {census_commute_df.shape[0]} counties")
census_commute_df.head()


# =============================================================================
# CELL 19 | PYTHON | Clean Polling Locations Data
# =============================================================================

polling_locations_df = (
    raw_polling_locations
    .copy()
    .assign(county_clean=lambda x: x['county_name'].str.strip().str.upper())
    .assign(precinct_clean=lambda x: x['precinct_name'].apply(normalize_precinct_name))
    .assign(polling_address=lambda x: x['address'].str.strip())
)

print(f"✅ Polling Locations cleaned: {polling_locations_df.shape[0]:,} rows")
print(f"   Unique Counties: {polling_locations_df['county_clean'].nunique()}")
print(f"   Unique Precincts: {polling_locations_df['precinct_clean'].nunique()}")
print(f"   Unique Polling Places: {polling_locations_df['polling_place_id'].nunique()}")
polling_locations_df.head()


# =============================================================================
# CELL 20 | PYTHON | Write All Staging Tables to Snowflake
# =============================================================================

staging_tables = {
    'STG_ELECTION_RESULTS': all_elections_df,
    'STG_CENSUS_INCOME': census_income_df,
    'STG_CENSUS_EDUCATION': census_education_df,
    'STG_CENSUS_RACE': census_race_df,
    'STG_CENSUS_SEX_AGE': census_sex_age_df,
    'STG_CENSUS_COMMUTE': census_commute_df,
    'STG_POLLING_LOCATIONS': polling_locations_df
}

print("=" * 70)
print("WRITING STAGING TABLES TO SNOWFLAKE")
print("=" * 70)

for table_name, df in staging_tables.items():
    session.write_pandas(df, table_name, auto_create_table=True, overwrite=True)
    print(f"✅ {table_name}: {len(df):,} rows")

print("=" * 70)
print("All staging tables written successfully!")
print("=" * 70)


# =============================================================================
# CELL 21 | MARKDOWN | Section 4: Data Integration via SQL JOINs
# =============================================================================

---
# SECTION 4: Data Integration via SQL JOINs
---

Create analytical tables by joining staging tables using SQL (declarative approach). This demonstrates:
- GROUP BY aggregations
- Multiple LEFT JOINs
- Calculated columns
- Window functions


# =============================================================================
# CELL 22 | SQL | Create Precinct Turnout Summary by Year
# =============================================================================

-- Aggregate votes to precinct level for each year
-- Calculate total votes per precinct (sum across all candidates)

CREATE OR REPLACE TABLE PRECINCT_TURNOUT AS
SELECT 
    year,
    county_clean AS county,
    precinct_clean AS precinct,
    SUM(votes) AS total_votes,
    SUM(CASE WHEN party = 'REP' THEN votes ELSE 0 END) AS republican_votes,
    SUM(CASE WHEN party = 'DEM' THEN votes ELSE 0 END) AS democrat_votes,
    SUM(CASE WHEN party NOT IN ('REP', 'DEM') THEN votes ELSE 0 END) AS other_votes,
    ROUND(SUM(CASE WHEN party = 'REP' THEN votes ELSE 0 END) / NULLIF(SUM(votes), 0) * 100, 2) AS republican_pct,
    ROUND(SUM(CASE WHEN party = 'DEM' THEN votes ELSE 0 END) / NULLIF(SUM(votes), 0) * 100, 2) AS democrat_pct
FROM STG_ELECTION_RESULTS
GROUP BY year, county_clean, precinct_clean
ORDER BY year, county, precinct;

SELECT 'PRECINCT_TURNOUT created' AS status, COUNT(*) AS row_count FROM PRECINCT_TURNOUT;


# =============================================================================
# CELL 23 | SQL | Create County Turnout Summary by Year
# =============================================================================

-- Aggregate precinct data to county level for each year

CREATE OR REPLACE TABLE COUNTY_TURNOUT AS
SELECT 
    year,
    county,
    COUNT(DISTINCT precinct) AS precinct_count,
    SUM(total_votes) AS total_votes,
    SUM(republican_votes) AS republican_votes,
    SUM(democrat_votes) AS democrat_votes,
    SUM(other_votes) AS other_votes,
    ROUND(SUM(republican_votes) / NULLIF(SUM(total_votes), 0) * 100, 2) AS republican_pct,
    ROUND(SUM(democrat_votes) / NULLIF(SUM(total_votes), 0) * 100, 2) AS democrat_pct
FROM PRECINCT_TURNOUT
GROUP BY year, county
ORDER BY year, county;

SELECT 'COUNTY_TURNOUT created' AS status, COUNT(*) AS row_count FROM COUNTY_TURNOUT;


# =============================================================================
# CELL 24 | SQL | Create County Turnout Trend (Pivot by Year)
# =============================================================================

-- Pivot county turnout to show trends across years

CREATE OR REPLACE TABLE COUNTY_TURNOUT_TREND AS
SELECT 
    county,
    MAX(CASE WHEN year = 2016 THEN total_votes END) AS votes_2016,
    MAX(CASE WHEN year = 2020 THEN total_votes END) AS votes_2020,
    MAX(CASE WHEN year = 2024 THEN total_votes END) AS votes_2024,
    MAX(CASE WHEN year = 2016 THEN republican_pct END) AS rep_pct_2016,
    MAX(CASE WHEN year = 2020 THEN republican_pct END) AS rep_pct_2020,
    MAX(CASE WHEN year = 2024 THEN republican_pct END) AS rep_pct_2024,
    MAX(CASE WHEN year = 2016 THEN democrat_pct END) AS dem_pct_2016,
    MAX(CASE WHEN year = 2020 THEN democrat_pct END) AS dem_pct_2020,
    MAX(CASE WHEN year = 2024 THEN democrat_pct END) AS dem_pct_2024
FROM COUNTY_TURNOUT
GROUP BY county
ORDER BY county;

SELECT 'COUNTY_TURNOUT_TREND created' AS status, COUNT(*) AS row_count FROM COUNTY_TURNOUT_TREND;


# =============================================================================
# CELL 25 | SQL | Create Master County Demographics Table (JOINs)
# =============================================================================

-- Join all census data with election turnout
-- Uses LEFT JOINs to preserve all counties

CREATE OR REPLACE TABLE COUNTY_DEMOGRAPHICS AS
SELECT 
    i.county_fips,
    i.county_name,
    i.county_clean,
    i.median_household_income,
    
    e.total_pop_25_plus,
    e.pct_bachelors_plus,
    e.pct_hs_plus,
    
    r.total_population,
    r.pct_white,
    r.pct_black,
    r.pct_minority,
    
    s.voting_age_population,
    s.pct_voting_age,
    
    c.total_workers,
    c.pct_drove_alone,
    c.pct_public_transit,
    c.pct_no_vehicle,
    
    t.votes_2016,
    t.votes_2020,
    t.votes_2024,
    t.rep_pct_2016,
    t.rep_pct_2020,
    t.rep_pct_2024,
    t.dem_pct_2016,
    t.dem_pct_2020,
    t.dem_pct_2024

FROM STG_CENSUS_INCOME i
LEFT JOIN STG_CENSUS_EDUCATION e ON i.county_clean = e.county_clean
LEFT JOIN STG_CENSUS_RACE r ON i.county_clean = r.county_clean
LEFT JOIN STG_CENSUS_SEX_AGE s ON i.county_clean = s.county_clean
LEFT JOIN STG_CENSUS_COMMUTE c ON i.county_clean = c.county_clean
LEFT JOIN COUNTY_TURNOUT_TREND t ON i.county_clean = t.county
ORDER BY i.county_fips;

SELECT 'COUNTY_DEMOGRAPHICS created' AS status, COUNT(*) AS row_count FROM COUNTY_DEMOGRAPHICS;


# =============================================================================
# CELL 26 | SQL | Create Polling Location Summary by County
# =============================================================================

-- Aggregate polling locations to county level

CREATE OR REPLACE TABLE COUNTY_POLLING_SUMMARY AS
SELECT 
    county_clean AS county,
    COUNT(DISTINCT polling_place_id) AS unique_polling_places,
    COUNT(DISTINCT precinct_clean) AS unique_precincts,
    COUNT(*) AS total_records,
    ROUND(COUNT(DISTINCT precinct_clean) / NULLIF(COUNT(DISTINCT polling_place_id), 0), 2) AS precincts_per_polling_place
FROM STG_POLLING_LOCATIONS
GROUP BY county_clean
ORDER BY precincts_per_polling_place DESC;

SELECT 'COUNTY_POLLING_SUMMARY created' AS status, COUNT(*) AS row_count FROM COUNTY_POLLING_SUMMARY;


# =============================================================================
# CELL 27 | MARKDOWN | Section 5: Data Quality Validation
# =============================================================================

---
# SECTION 5: Data Quality Validation
---

Verify data integrity before proceeding with EDA:
- Row counts for all tables
- Missing value checks
- Join validation (county matching)


# =============================================================================
# CELL 28 | PYTHON | Data Quality Summary - Table Row Counts
# =============================================================================

print("=" * 70)
print("DATA QUALITY SUMMARY - TABLE ROW COUNTS")
print("=" * 70)

staging_tables = [
    'STG_ELECTION_RESULTS',
    'STG_CENSUS_INCOME', 
    'STG_CENSUS_EDUCATION',
    'STG_CENSUS_RACE',
    'STG_CENSUS_SEX_AGE',
    'STG_CENSUS_COMMUTE',
    'STG_POLLING_LOCATIONS'
]

analytical_tables = [
    'PRECINCT_TURNOUT',
    'COUNTY_TURNOUT',
    'COUNTY_TURNOUT_TREND',
    'COUNTY_DEMOGRAPHICS',
    'COUNTY_POLLING_SUMMARY'
]

print("\n📦 STAGING TABLES (Python-created):")
for table in staging_tables:
    count = session.sql(f"SELECT COUNT(*) FROM {table}").collect()[0][0]
    print(f"   {table}: {count:,} rows")

print("\n📊 ANALYTICAL TABLES (SQL-created):")
for table in analytical_tables:
    count = session.sql(f"SELECT COUNT(*) FROM {table}").collect()[0][0]
    print(f"   {table}: {count:,} rows")

print("=" * 70)


# =============================================================================
# CELL 29 | SQL | Validate County Matching Across Datasets
# =============================================================================

-- Check for counties in election data that don't match census data

SELECT 'Counties in Election Data not in Census' AS check_type,
       COUNT(DISTINCT t.county) AS count
FROM COUNTY_TURNOUT t
LEFT JOIN STG_CENSUS_INCOME c ON t.county = c.county_clean
WHERE c.county_clean IS NULL

UNION ALL

SELECT 'Counties in Census not in Election Data' AS check_type,
       COUNT(DISTINCT c.county_clean) AS count
FROM STG_CENSUS_INCOME c
LEFT JOIN COUNTY_TURNOUT t ON c.county_clean = t.county
WHERE t.county IS NULL;


# =============================================================================
# CELL 30 | MARKDOWN | Section 6: Exploratory Data Analysis
# =============================================================================

---
# SECTION 6: Exploratory Data Analysis (EDA)
---

Analyze the cleaned and integrated data to understand:
- Voter turnout patterns across years
- Demographic correlations
- Polling resource distribution
- Geographic patterns


# =============================================================================
# CELL 31 | SQL | Statewide Turnout Summary by Year
# =============================================================================

-- Overall Missouri turnout by presidential election year

SELECT 
    year,
    COUNT(DISTINCT county) AS counties,
    COUNT(DISTINCT precinct) AS precincts,
    SUM(total_votes) AS total_votes,
    ROUND(SUM(republican_votes) / SUM(total_votes) * 100, 2) AS statewide_republican_pct,
    ROUND(SUM(democrat_votes) / SUM(total_votes) * 100, 2) AS statewide_democrat_pct
FROM PRECINCT_TURNOUT
GROUP BY year
ORDER BY year;


# =============================================================================
# CELL 32 | SQL | County Turnout Descriptive Statistics
# =============================================================================

-- Descriptive statistics for county-level turnout (2020 as baseline)

SELECT 
    '2020 County Turnout' AS metric,
    COUNT(*) AS county_count,
    ROUND(AVG(total_votes), 0) AS avg_votes,
    ROUND(MEDIAN(total_votes), 0) AS median_votes,
    MIN(total_votes) AS min_votes,
    MAX(total_votes) AS max_votes,
    ROUND(STDDEV(total_votes), 0) AS stddev_votes
FROM COUNTY_TURNOUT
WHERE year = 2020;


# =============================================================================
# CELL 33 | SQL | Top 10 Counties by Turnout (2020)
# =============================================================================

-- Highest turnout counties in 2020 presidential election

SELECT 
    county,
    precinct_count,
    total_votes,
    republican_pct,
    democrat_pct
FROM COUNTY_TURNOUT
WHERE year = 2020
ORDER BY total_votes DESC
LIMIT 10;


# =============================================================================
# CELL 34 | SQL | Bottom 10 Counties by Turnout (2020)
# =============================================================================

-- Lowest turnout counties in 2020 presidential election

SELECT 
    county,
    precinct_count,
    total_votes,
    republican_pct,
    democrat_pct
FROM COUNTY_TURNOUT
WHERE year = 2020
ORDER BY total_votes ASC
LIMIT 10;


# =============================================================================
# CELL 35 | SQL | Turnout Change 2016 to 2024
# =============================================================================

-- Counties with largest turnout changes

SELECT 
    county,
    votes_2016,
    votes_2020,
    votes_2024,
    votes_2024 - votes_2016 AS change_2016_to_2024,
    ROUND((votes_2024 - votes_2016) / NULLIF(votes_2016, 0) * 100, 2) AS pct_change_2016_to_2024
FROM COUNTY_TURNOUT_TREND
WHERE votes_2016 IS NOT NULL AND votes_2024 IS NOT NULL
ORDER BY pct_change_2016_to_2024 DESC
LIMIT 10;


# =============================================================================
# CELL 36 | SQL | Polling Resource Strain Analysis
# =============================================================================

-- Counties with high precincts-per-polling-place ratio (potential under-resourcing)

SELECT 
    p.county,
    p.unique_polling_places,
    p.unique_precincts,
    p.precincts_per_polling_place,
    d.total_population,
    d.voting_age_population,
    d.votes_2020
FROM COUNTY_POLLING_SUMMARY p
LEFT JOIN COUNTY_DEMOGRAPHICS d ON p.county = d.county_clean
WHERE p.precincts_per_polling_place > 1
ORDER BY p.precincts_per_polling_place DESC
LIMIT 15;


# =============================================================================
# CELL 37 | SQL | Demographics vs Turnout - Key Metrics
# =============================================================================

-- County demographics summary with turnout (2020)

SELECT 
    county_name,
    total_population,
    voting_age_population,
    votes_2020,
    ROUND(votes_2020 / NULLIF(voting_age_population, 0) * 100, 2) AS turnout_pct_2020,
    median_household_income,
    pct_bachelors_plus,
    pct_minority,
    pct_no_vehicle
FROM COUNTY_DEMOGRAPHICS
WHERE votes_2020 IS NOT NULL
ORDER BY turnout_pct_2020 DESC
LIMIT 15;


# =============================================================================
# CELL 38 | PYTHON | Correlation Analysis - Demographics vs Turnout
# =============================================================================

county_demo_df = session.table('COUNTY_DEMOGRAPHICS').to_pandas()

county_demo_df = county_demo_df.assign(
    turnout_pct_2020=lambda x: (x['VOTES_2020'] / x['VOTING_AGE_POPULATION'] * 100).round(2)
)

print("=" * 70)
print("CORRELATION MATRIX - DEMOGRAPHICS VS TURNOUT")
print("=" * 70)

correlation_cols = [
    'MEDIAN_HOUSEHOLD_INCOME', 
    'PCT_BACHELORS_PLUS', 
    'PCT_MINORITY', 
    'PCT_NO_VEHICLE', 
    'turnout_pct_2020',
    'REP_PCT_2020',
    'DEM_PCT_2020'
]

valid_cols = [c for c in correlation_cols if c in county_demo_df.columns]
correlation_matrix = county_demo_df[valid_cols].corr().round(3)
correlation_matrix


# =============================================================================
# CELL 39 | PYTHON | Key Insights Summary
# =============================================================================

print("=" * 70)
print("KEY INSIGHTS FOR VOTER RESOURCE ALLOCATION")
print("=" * 70)

print("""
1. TURNOUT PATTERNS (2016-2024):
   - Compare statewide turnout across three presidential cycles
   - Identify counties with increasing vs decreasing turnout
   - Examine urban vs rural turnout differences

2. DEMOGRAPHIC CORRELATIONS:
   - Relationship between income/education and turnout
   - Minority population representation in high/low turnout areas
   - Transportation access (no vehicle %) impact on participation

3. POLLING RESOURCE DISTRIBUTION:
   - Counties with high precincts-per-polling-place ratios
   - Cross-reference resource strain with population size
   - Identify potential under-resourced areas

4. PREDICTIVE MODELING OPPORTUNITIES:
   - Use demographic features to predict turnout
   - Model voter demand by precinct
   - Optimize polling resource allocation

NEXT STEPS:
   - Build predictive models for voter demand
   - Develop prescriptive recommendations for resource allocation
   - Create visualizations for final presentation
""")
print("=" * 70)


# =============================================================================
# CELL 40 | SQL | Create Final Visualization Export Table
# =============================================================================

-- Create comprehensive table for visualization tools (Tableau, Flourish)

CREATE OR REPLACE TABLE COUNTY_ANALYSIS_VIZ AS
SELECT 
    d.county_fips,
    d.county_name,
    d.county_clean,
    d.total_population,
    d.voting_age_population,
    d.median_household_income,
    d.pct_bachelors_plus,
    d.pct_minority,
    d.pct_no_vehicle,
    d.votes_2016,
    d.votes_2020,
    d.votes_2024,
    d.rep_pct_2016,
    d.rep_pct_2020,
    d.rep_pct_2024,
    d.dem_pct_2016,
    d.dem_pct_2020,
    d.dem_pct_2024,
    ROUND(d.votes_2020 / NULLIF(d.voting_age_population, 0) * 100, 2) AS turnout_pct_2020,
    p.unique_polling_places,
    p.unique_precincts,
    p.precincts_per_polling_place
FROM COUNTY_DEMOGRAPHICS d
LEFT JOIN COUNTY_POLLING_SUMMARY p ON d.county_clean = p.county
ORDER BY d.county_fips;

SELECT 'COUNTY_ANALYSIS_VIZ created for export' AS status, COUNT(*) AS row_count FROM COUNTY_ANALYSIS_VIZ;


# =============================================================================
# CELL 41 | PYTHON | Final Status Summary
# =============================================================================

print("=" * 70)
print("DATA PREPARATION COMPLETE")
print("=" * 70)
print("""
✅ Election data loaded and combined (2016, 2020, 2024)
✅ Census demographic data cleaned and staged
✅ Polling location data processed
✅ SQL aggregations and joins completed
✅ Analytical tables created for EDA
✅ Visualization export table ready

TABLES CREATED:
---------------
Staging:
  - STG_ELECTION_RESULTS (combined presidential results)
  - STG_CENSUS_INCOME, STG_CENSUS_EDUCATION, STG_CENSUS_RACE
  - STG_CENSUS_SEX_AGE, STG_CENSUS_COMMUTE
  - STG_POLLING_LOCATIONS

Analytical:
  - PRECINCT_TURNOUT (precinct-level by year)
  - COUNTY_TURNOUT (county-level by year)
  - COUNTY_TURNOUT_TREND (pivoted by year)
  - COUNTY_DEMOGRAPHICS (master demographics + turnout)
  - COUNTY_POLLING_SUMMARY (polling resource distribution)
  - COUNTY_ANALYSIS_VIZ (export-ready for visualization)

Ready for predictive and prescriptive analytics!
""")
print("=" * 70)
