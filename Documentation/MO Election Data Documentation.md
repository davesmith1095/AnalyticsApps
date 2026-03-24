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

## Election Data Preprocessing
Before combining election datasets, several preprocessing steps will be performed.

Add election year column:

df2016["year"] = 2016
df2020["year"] = 2020
df2024["year"] = 2024

Remove precinct_code where present:

df = df.drop(columns=["precinct_code"], errors="ignore")

Normalize precinct names:

df["precinct_clean"] = (
    df["precinct"]
    .astype(str)
    .str.upper()
    .str.replace("#","")
    .str.replace("  "," ")
    .str.strip()
)

## Census Data Preprocessing
Census datasets exported from data.census.gov contain some artifacts that should be cleaned.

Remove header artifact row:

df = df[df["GEO_ID"] != "Geography"]

Remove blank export columns:

df = df.loc[:, ~df.columns.str.contains("^Unnamed")]

Extract county name:

df["county"] = (
    df["NAME"]
    .str.replace(" County, Missouri","", regex=False)
    .str.replace(" city, Missouri","", regex=False)
    .str.upper()
)

Add census year column:

df["census_year"] = 2016
df["census_year"] = 2020
df["census_year"] = 2024

## Proposed Snowflake Table Structure
Election Results Table

election_results
----------------
year
county
precinct
precinct_clean
office
district
candidate
party
votes

Census Tables

census_income
census_education
census_race
census_age
census_commute

Polling Locations

polling_locations
-----------------
county
precinct
polling_location
address
