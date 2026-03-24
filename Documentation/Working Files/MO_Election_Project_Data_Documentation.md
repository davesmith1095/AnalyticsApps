# Project Data Documentation

Generated: 2026-03-12

This document describes the datasets used for the Missouri Voter Resource Allocation analytics project. The goal is to analyze historical election results alongside demographic and geographic data to evaluate how polling resources could be allocated more effectively across Missouri precincts.

# Overview of Data Architecture

The project integrates several categories of data:
- Historical election results (precinct-level)
- Census demographic data (county-level)
- Polling location data
- Precinct geographic boundaries

Combining these sources allows analysis of relationships between demographics, turnout patterns, and polling infrastructure.

# Election Results (2016–2024)

Precinct-level election results were collected for multiple election years to analyze turnout patterns and voting trends over time.

Files used:
- MO 2016 Election Results.csv
- MO 2018 Election Results.csv
- MO 2020 Election Results.csv
- MO 2024 Election Results.csv
- MO 2022 Election Results.csv

Primary source:
OpenElections Project (GitHub)
https://github.com/openelections/openelections-data-mo

The OpenElections datasets were available for 2016, 2018, 2020, and 2024. The 2022 dataset was obtained from a separate public election data source because it was not available in the OpenElections repository at the time of analysis.

# Census Demographic Data

Demographic information was obtained from the U.S. Census Bureau American Community Survey (ACS) 5‑Year Estimates (2016–2020).

Source:
https://data.census.gov

Files used:
- ACSDT5Y2020.B08301-Data.csv (Commute characteristics)
- ACSDT5Y2020.B15003-Data.csv (Educational attainment)
- ACSDT5Y2020.B19013-Data.csv (Median household income)
- ACSDT5Y2020.B02001-Data.csv (Race demographics)
- ACSDT5Y2020.B01001-Data.csv (Sex by age distribution)

These datasets were downloaded at the county level for Missouri.

# Polling Location Data

Polling place location data was collected from the MIT Election Data and Science Lab.

Source:
https://election.lab.ufl.edu/precinct-data/

File used:
- MO 2020 Polling Locations.csv

This dataset includes county names, precinct identifiers, polling location names, and addresses. Although the dataset reflects the 2020 election, polling locations generally change slowly and are suitable for multi‑year analysis.

# Precinct Geographic Boundaries

Precinct geographic boundaries were obtained from the U.S. Census Bureau TIGER/Line shapefiles.

Source:
https://www.census.gov/geographies/mapping-files/time-series/geo/tiger-line-file.html

Files used:
- MO 2020 Precincts.shp
- MO 2020 Precincts.dbf
- MO 2020 Precincts.shx
- MO 2020 Precincts.prj
- MO 2020 Precincts.cpg

These shapefiles represent voting district (VTD) boundaries for Missouri.

# Rationale for the Data Design

The project combines election, demographic, and geographic datasets to support predictive and prescriptive analytics. Multiple election years (2016–2024) allow examination of turnout patterns across several election cycles.

Using multiple elections provides:
- Historical turnout trends
- Identification of consistently high or low participation precincts
- Improved predictive modeling of voter demand

The ACS 2016–2020 census data provides stable demographic indicators overlapping with the election years studied.
