# AnalyticsApps
Analytics Applications Spring 26 Group Project

# Analytics Applications — SP26: MO 2020 Election Analysis (Group 1)

## Project Overview
This project aims to analyze the distribution of voting resources across Missouri during the 2020 election. By combining precinct-level election results, polling locations, demographic/socioeconomic census data, and geographic boundaries, we are conducting a predictive and prescriptive analysis. Our ultimate goal is to provide data-driven recommendations for state government officials on where to allocate voting resources to reduce voter disenfranchisement.

## Repository Structure
To prevent merge conflicts and keep our work organized, please adhere to the following directory structure. 

**Critical Note:** The `data/` folder is explicitly included in our `.gitignore`. Git is meant for versioning code, not large datasets. Please do not force-push data files to this repository.

```text
mo-election-analysis/
├── .gitignore
├── README.md
├── data/                           # GITIGNORED (Do not push to GitHub)
│   ├── raw/                        # Extract the Canvas data zip here
│   └── processed/                  # Store cleaned dataframe outputs here
├── notebooks/
│   ├── 01_initial_cleaning_eda.ipynb   # Initial data cleaning
│   ├── 02_metric_selection.ipynb       # Defining our 3-5 key metrics
│   ├── 03_turnout_analysis.ipynb       # EDA for Metric 1
│   └── 04_demographic_analysis.ipynb   # EDA for Metric 2
├── src/                            # Reusable Python scripts and helper functions
└── docs/
    └── Group1_ProjectProposal.docx


## Getting Started: Data Access
Because our raw data files (Shapefiles, Census CSVs) are too large for GitHub, we are using Canvas as our data hub.

1. Log in to our [ Canvas Group Files page](https://wustl.instructure.com/groups/144912/files).
2. Download the compressed raw data folder (`raw.zip`).
3. On your local machine, extract the contents of the zip file directly into the `mo-election-analysis/data/raw/` directory.
4. Run `notebooks/Group 1 Final Project - MO Voter.ipynb` to verify your local paths are working!

## Next Steps: Team Meeting Agenda
Our next major deliverable is the Retrospective Data Analysis. During our next meeting, we need to finalize the following:

1. **Metric Selection:** We must identify, define, and justify 3–5 key metrics that directly address our problem statement (e.g., Voters per Polling Location, Average Commute Time).
2. **Assigning EDA Notebooks:** We will divide the exploratory analysis (trends, distributions, segments) among the team. Each person will get their own notebook to avoid merge conflicts.
3. **The Golden Rule:** As we build our EDA, remember the rubric rule: If a trend or distribution doesn't directly support one of our key metrics, exclude it.