# Missouri Election Analytics Project – Data Documentation

**Group 1**

## Project Overview
This document describes the datasets collected for the Missouri Voter Resource Allocation analytics project.
The project analyzes voting patterns across presidential elections and demographic characteristics of Missouri counties
to evaluate how polling resources could potentially be allocated more effectively.

The analysis focuses on three presidential election cycles:
2016, 2020, and 2024.

Demographic characteristics are aligned with American Community Survey (ACS) 5‑Year datasets ending in those same years.

## Election Results Data
Files used:

MO 2016 Election Results.csv
MO 2020 Election Results.csv
MO 2024 Election Results.csv

Source:
OpenElections Project (GitHub)
https://github.com/openelections/openelections-data-mo

These datasets contain precinct‑level vote totals for each candidate and office.
Each row represents the vote total for one candidate within a specific precinct.

Important schema note:
The 2020 and 2024 files include a column called precinct_code which is not present in the 2016 dataset.
To maintain a consistent schema across all election years, the precinct_code column will be dropped during preprocessing.

## Census Demographic Data
Demographic data was downloaded from the U.S. Census Bureau's American Community Survey (ACS) 5‑Year Estimates Detailed Tables.

Three ACS datasets were collected in order to align demographic data with each presidential election year.

2016 Election → ACS 2012‑2016
2020 Election → ACS 2016‑2020
2024 Election → ACS 2020‑2024

Each ACS dataset includes the following five tables:

B01001 – Sex by Age
B02001 – Race
B08301 – Commuting / Transportation to Work
B15003 – Educational Attainment
B19013 – Median Household Income

Files used:

MO 2016 Census Sex by Age.csv
MO 2016 Census Race.csv
MO 2016 Census Commute.csv
MO 2016 Census Education.csv
MO 2016 Census Income.csv

MO 2020 Census Sex by Age.csv
MO 2020 Census Race.csv
MO 2020 Census Commute.csv
MO 2020 Census Education.csv
MO 2020 Census Income.csv

MO 2024 Census Sex by Age.csv
MO 2024 Census Race.csv
MO 2024 Census Commute.csv
MO 2024 Census Education.csv
MO 2024 Census Income.csv

All ACS datasets were downloaded at the county level for the state of Missouri.

## Polling Location Data
File used:

MO 2020 Polling Locations.csv

This dataset contains polling locations associated with Missouri precincts.
Although the data represents the 2020 election cycle, polling locations generally change slowly,
making the dataset suitable for analysis across nearby election years.

## Precinct Geographic Files (Optional)
The following precinct boundary shapefiles were downloaded but are not currently required for the core analysis.

MO 2020 Precincts.shp
MO 2020 Precincts.dbf
MO 2020 Precincts.shx
MO 2020 Precincts.prj
MO 2020 Precincts.cpg

These files represent Missouri Voting Tabulation District (precinct) boundaries from the Census TIGER/Line dataset.

They may be used in future work for:

• mapping turnout geographically
• spatial analysis of polling locations
• calculating distances between voters and polling places

## Data Preprocessing

### Election Data Preprocessing
Before combining election datasets, several preprocessing steps are performed.

Add election year column:

```python
df2016["year"] = 2016
df2020["year"] = 2020
df2024["year"] = 2024
```

Remove precinct_code where present:

```python
df = df.drop(columns=["precinct_code"], errors="ignore")
```

Normalize precinct names:

```python
df["precinct_clean"] = (
    df["precinct"]
    .astype(str)
    .str.upper()
    .str.replace("#","")
    .str.replace("  "," ")
    .str.strip()
)
```

### Census Data Preprocessing
Census datasets exported from data.census.gov contain some artifacts that should be cleaned.

Remove header artifact row:

```python
df = df[df["GEO_ID"] != "Geography"]
```

Remove blank export columns:

```python
df = df.loc[:, ~df.columns.str.contains("^Unnamed")]
```

Extract county name:

```python
df["county_clean"] = (
    df["NAME"]
    .str.replace(", Missouri", "", regex=False)
    .str.replace(" County", "", regex=False)
    .str.upper()
)
```

**Important – St. Louis County vs. St. Louis City:**
Missouri has both "St. Louis County" (FIPS 29189) and "St. Louis city" (FIPS 29510), which is an independent city that is not part of any county. The cleaning process preserves this distinction by only removing " County" from county names, not " city". This results in:

- St. Louis County → "ST. LOUIS"
- St. Louis city → "ST. LOUIS CITY"

If both entities are cleaned to the same name, JOINs between election and census data will produce duplicate rows (a cartesian product), leading to inflated row counts in analytical tables.

Add census year column:

```python
df["census_year"] = 2016  # or 2020 or 2024
```

## Snowflake Implementation Notes

### Column Naming and Case Sensitivity

Snowflake handles column names differently depending on how tables are created:

**Staging Tables (created via Python/Snowpark):**
- Column names are lowercase (e.g., `year`, `county_clean`, `votes`)
- Must use double quotes in SQL to reference them: `"year"`, `"county_clean"`

**Analytical Tables (created via SQL):**
- Use uppercase aliases when creating: `SELECT "year" AS YEAR, "county_clean" AS COUNTY`
- This allows unquoted references in downstream SQL: `WHERE YEAR = 2020`

### Snowflake Table Structure

**Staging Tables (loaded via Python):**

STG_ELECTION_RESULTS – Combined presidential election results (all years)
STG_CENSUS_INCOME – Median household income by county
STG_CENSUS_EDUCATION – Educational attainment by county
STG_CENSUS_RACE – Race demographics by county
STG_CENSUS_COMMUTE – Commuting patterns by county
STG_CENSUS_SEX_AGE – Sex and age demographics by county
STG_POLLING_LOCATIONS – Polling place locations

**Analytical Tables (created via SQL):**

PRECINCT_TURNOUT – Aggregated votes by precinct and year
COUNTY_TURNOUT – Aggregated votes by county and year
COUNTY_TURNOUT_TREND – Pivoted view with all years side by side
COUNTY_CENSUS – Combined census demographics with all years
COUNTY_ANALYSIS – Joined turnout and census data for analysis
COUNTY_POLLING_SUMMARY – Polling locations aggregated by county
COUNTY_VIZ_EXPORT – Final export table for visualization tools

### Expected Row Counts

| Table | Expected Rows | Notes |
|-------|---------------|-------|
| STG_ELECTION_RESULTS | ~70,000 | Presidential votes only |
| STG_CENSUS_* | 345 each | 115 counties × 3 years |
| STG_POLLING_LOCATIONS | ~14,000 | 2020 polling places |
| PRECINCT_TURNOUT | ~10,000 | Precincts × 3 years |
| COUNTY_TURNOUT | 348 | 116 counties × 3 years |
| COUNTY_TURNOUT_TREND | 117 | One row per county |
| COUNTY_CENSUS | 345 | 115 counties × 3 years |
| COUNTY_ANALYSIS | 117 | One row per county |
| COUNTY_POLLING_SUMMARY | 116 | One row per county |

Note: Missouri has 114 counties plus the independent city of St. Louis, for a total of 115 county-level entities. Some election data may show 116 counties due to Kansas City reporting.

## Verified Results

Statewide presidential election totals match official Missouri results:

| Year | Total Votes | Republican % | Democrat % |
|------|-------------|--------------|------------|
| 2016 | 2,808,298 | 56.78% | 38.14% |
| 2020 | 2,963,270 | 57.17% | 41.03% |
| 2024 | 2,995,327 | 58.49% | 40.08% |
