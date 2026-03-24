# Project Data Documentation

Generated: 2026-03-12

This document describes the datasets used for the Missouri Voter Resource Allocation analytics project. The goal of the project is to analyze historical presidential election results alongside demographic and geographic data to evaluate how polling resources could be allocated more effectively across Missouri precincts.

# Overview of Data Architecture

The project integrates several categories of data:
- Presidential election results (precinct-level)
- Census demographic data (county-level)
- Polling location data
- Optional precinct geographic boundaries

Combining these sources allows the project to analyze relationships between demographics, turnout patterns, and polling infrastructure.

# Election Results (Presidential Elections: 2016, 2020, 2024)

Precinct-level election results were collected for three presidential election years to analyze turnout patterns and voting trends over time.

Files used:
- MO 2016 Election Results.csv
- MO 2020 Election Results.csv
- MO 2024 Election Results.csv

Source:
OpenElections Project (GitHub)
https://github.com/openelections/openelections-data-mo

Presidential election years were chosen because they produce the highest voter turnout and the most consistent statewide participation. Focusing on presidential election cycles provides a clearer signal for modeling voter demand and analyzing polling resource allocation across precincts.

Schema note:
The 2020 and 2024 election files include an additional 'precinct_code' field that is not present in the 2016 file. To maintain a consistent schema across years, this column should be dropped or ignored during preprocessing.

# Census Demographic Data

Files used:
- MO 2020 Census Commute.csv
- MO 2020 Census Education.csv
- MO 2020 Census Income.csv
- MO 2020 Census Race.csv
- MO 2020 Census Sex by Age.csv

Source:
U.S. Census Bureau – American Community Survey (ACS) 5-Year Estimates
https://data.census.gov

These datasets provide county-level demographic indicators that overlap with the election years being analyzed.

# Polling Location Data

File used:
- MO 2020 Polling Locations.csv

This dataset identifies the physical polling places associated with precincts. Although the dataset reflects the 2020 election, polling locations typically remain relatively stable across election cycles.

# Precinct Geographic Boundaries (Optional Dataset)

The following files were downloaded as part of the project data collection process:

- MO 2020 Precincts.shp
- MO 2020 Precincts.dbf
- MO 2020 Precincts.shx
- MO 2020 Precincts.prj
- MO 2020 Precincts.cpg

These files represent the Missouri precinct (Voting Tabulation District) geographic boundaries from the U.S. Census TIGER/Line dataset.

These shapefiles are **not required for the current analytical workflow** and are not loaded into Snowflake. They are retained as an optional dataset that could be used for future spatial analysis such as:
- Mapping voter turnout by precinct
- Visualizing geographic clustering of polling locations
- Calculating geographic distance between voters and polling locations.

# Data Preprocessing Requirements

Three preprocessing steps are recommended before loading election data into Snowflake.

1. Add a YEAR column
This allows datasets from different election cycles to be combined into a single analytical table.

Recommended values:
- MO 2016 Election Results.csv  -> YEAR = 2016
- MO 2020 Election Results.csv  -> YEAR = 2020
- MO 2024 Election Results.csv  -> YEAR = 2024

2. Normalize precinct names
Missouri precinct names vary across datasets (for example, 'Ward 1', 'WARD 1', and 'Ward #1'). Standardizing names reduces the risk of failed joins between election results, polling locations, and precinct datasets.

3. Remove the precinct_code column
Because 2016 does not include this field, the column should be dropped from the 2020 and 2024 datasets.

# Example Python Preprocessing Code

import pandas as pd

def normalize_precinct_name(name):
    return (
        str(name)
        .upper()
        .replace('#','')
        .replace('  ',' ')
        .strip()
    )

df2016 = pd.read_csv('MO 2016 Election Results.csv')
df2020 = pd.read_csv('MO 2020 Election Results.csv')
df2024 = pd.read_csv('MO 2024 Election Results.csv')

df2016['year'] = 2016
df2020['year'] = 2020
df2024['year'] = 2024

df2020 = df2020.drop(columns=['precinct_code'], errors='ignore')
df2024 = df2024.drop(columns=['precinct_code'], errors='ignore')

for df in [df2016, df2020, df2024]:
    df['precinct_clean'] = df['precinct'].apply(normalize_precinct_name)
    df['county'] = df['county'].astype(str).str.upper().str.strip()

all_elections = pd.concat([df2016, df2020, df2024], ignore_index=True)

This produces a unified election dataset ready for loading into Snowflake.

# Proposed Snowflake Table Structure

Table: election_results
- year
- county
- precinct
- precinct_clean
- office
- district
- candidate
- party
- votes

Table: census_income
- county
- median_income

Table: census_education
- county
- education variables

Table: census_race
- county
- race variables

Table: census_age
- county
- age distribution

Table: census_commute
- county
- commute metrics

Table: polling_locations
- county
- precinct
- polling_location
- address

This relational structure allows election turnout to be analyzed alongside demographic characteristics and polling infrastructure.
