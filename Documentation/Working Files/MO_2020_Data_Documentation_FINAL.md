# Missouri 2020 Voter Resource Allocation Project

## Dataset Documentation

Generated: 2026-03-08

This document describes the datasets collected for the Missouri voter resource allocation analytics project.

### MO 2020 Election Results.csv
**Source:** Voting and Election Science Team (VEST) / Harvard Dataverse  
**Description:** Precinct-level vote totals for the 2020 Missouri general election. Each row represents a voting precinct with columns for candidate vote totals.  
**Key Fields:**
- STATEFP
- COUNTYFP
- NAME (precinct name)
- candidate vote columns (e.g., G20PRERTRU, G20PREDBID)
**Analytical Purpose:** Used to calculate turnout, compare candidate performance, and analyze voting patterns at the precinct level.

### MO 2020 Polling Locations.csv
**Source:** MIT Election Data and Science Lab – Polling Places Dataset  
**Description:** Dataset containing polling locations associated with counties and precincts in Missouri.  
**Key Fields:**
- county_name
- precinct_id
- precinct_name
- polling_place_id
- name
- address
**Analytical Purpose:** Used to analyze polling location distribution and evaluate whether resources are adequately allocated across precincts.

### MO 2020 Census Income.csv
**Source:** U.S. Census Bureau – American Community Survey (ACS) 2016–2020  
**Description:** Median household income and related economic indicators for Missouri counties.  
**Key Fields:**
- GEO_ID
- NAME (county name)
- income estimate columns
**Analytical Purpose:** Provides socioeconomic indicators that may correlate with voting turnout and access to polling resources.

### MO 2020 Census Education.csv
**Source:** U.S. Census Bureau – American Community Survey (ACS) 2016–2020  
**Description:** Educational attainment statistics for Missouri counties.  
**Key Fields:**
- GEO_ID
- NAME
- education attainment fields
**Analytical Purpose:** Used as a demographic predictor that may correlate with voting participation.

### MO 2020 Census Race.csv
**Source:** U.S. Census Bureau – American Community Survey (ACS) 2016–2020  
**Description:** Race and ethnicity demographic breakdown for Missouri counties.  
**Key Fields:**
- GEO_ID
- NAME
- race population counts
**Analytical Purpose:** Provides demographic composition data useful for understanding population characteristics influencing voting behavior.

### MO 2020 Census Sex by Age.csv
**Source:** U.S. Census Bureau – American Community Survey (ACS) 2016–2020  
**Description:** Population distribution by age and gender categories for Missouri counties.  
**Key Fields:**
- GEO_ID
- NAME
- age and sex population columns
**Analytical Purpose:** Helps estimate eligible voter populations and age-related turnout patterns.

### MO 2020 Census Commute.csv
**Source:** U.S. Census Bureau – American Community Survey (ACS) 2016–2020  
**Description:** Commuting characteristics including travel time to work for Missouri counties.  
**Key Fields:**
- GEO_ID
- NAME
- commute time categories
**Analytical Purpose:** Used as a proxy for transportation access and potential barriers to voting.

### MO 2020 Precincts (Shapefile Set)
**Source:** U.S. Census Bureau – TIGER/Line Voting District (VTD) Shapefiles  
**Description:** Geographic boundaries for Missouri voting districts (precinct equivalents). Includes multiple files sharing the same base name.  
**Key Fields:**
- STATEFP20
- COUNTYFP20
- VTDST20
- GEOID20
- NAME20
**Analytical Purpose:** Provides spatial boundaries allowing mapping, geographic joins, and spatial analysis of precinct-level voting patterns.
