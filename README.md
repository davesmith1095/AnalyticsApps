# AnalyticsApps
Analytics Applications Spring 26 Group Project

# Analytics Applications — SP26: MO 2020 Election Analysis (Group 1)

## Project Overview
This project aims to analyze the distribution of voting resources across Missouri during presidential elections from 2016-2024. By combining precinct-level election results, polling locations, demographic/socioeconomic census data, and geographic boundaries, we are conducting a predictive and prescriptive analysis. Our ultimate goal is to provide data-driven recommendations for state government officials on where to allocate voting resources to reduce voter disenfranchisement.

## Repository Structure
To prevent merge conflicts and keep our work organized, please adhere to the following directory structure. 

**Critical Note:** The `data/` folder is explicitly included in our `.gitignore`. Git is meant for versioning code, not large datasets. Please do not force-push data files to this repository.

```text
.
├── main.py
├── README.md
├── data/
│   ├── geo/
│   │   ├── processed/                          # transformed / joined geospatial files
│   │   └── raw/                                # direct ingested shapefiles
│   │       ├── mo_2010_county/                 # Missouri County boundary 2010
│   │       ├── mo_2020_county/                 # Missouri County boundary 2020
│   │       ├── mo_2024_gen_all_prec/           # 2024 Voter Precinct Shapefiles
│   │       ├── mo_2024_gen_cong_prec/
│   │       └── mo_2024_gen_sldl_prec/
│   ├── processed/                              # Processed Census data
│   └── raw/                                    # Raw ingested tabular data -- Census, Voter, Polling
├── docs/
├── logs/
├── notebooks/                                  # "Sandbox" for pre-pythonic development
├── scratch/                                    # Python files not yet incorporated to main.py
└── src/                                        # Python modules/helper files
```


## Getting Started: Data Access
Because our raw data files (Shapefiles, Census CSVs) are too large for GitHub, we are using Canvas as our data hub.

1. Log in to our [ Canvas Group Files page](https://wustl.instructure.com/groups/144912/files).
2. Download the compressed raw data folder (`raw.zip`).
3. On your local machine, extract the contents of the zip file directly into the `mo-election-analysis/data/raw/` directory.
4. Run `notebooks/Group 1 Final Project - MO Voter.ipynb` to verify your local paths are working!