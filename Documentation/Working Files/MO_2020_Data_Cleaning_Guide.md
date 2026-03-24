
# Missouri 2020 Voter Resource Allocation Project
## Data Cleaning Guide (Notebook Workflow)

Generated: 2026-03-08

This document explains how the **raw datasets should be cleaned programmatically inside the project notebook** rather than manually modifying the source files.

The goal is to:
- Preserve **raw source data**
- Ensure **reproducibility**
- Clearly demonstrate **data wrangling steps** for the analytics assignment

All datasets should be loaded **exactly as downloaded** and then cleaned using Python (Pandas / GeoPandas).

---

# General Workflow

Recommended workflow inside the notebook:

1. Load raw datasets
2. Inspect structure
3. Detect anomalies
4. Apply cleaning transformations
5. Standardize join keys
6. Validate results

Example structure:

```python
import pandas as pd

df = pd.read_csv("MO 2020 Census Income.csv")

df.head()
df.shape
df.columns
```

---

# Dataset-Specific Cleaning Steps

## 1. Census Datasets

Files:

- MO 2020 Census Income.csv
- MO 2020 Census Education.csv
- MO 2020 Census Race.csv
- MO 2020 Census Sex by Age.csv
- MO 2020 Census Commute.csv

### Common Issues

ACS downloads typically contain:

1. Metadata header rows
2. State-level totals
3. Margin-of-error columns
4. Empty columns

### Cleaning Steps

#### Remove Metadata Rows

Keep only rows containing county-level GEO_ID values.

```python
df = df[df["GEO_ID"].str.contains("0500000US")]
```

#### Remove State Totals

Sometimes the dataset includes a row for the entire state.

```python
df = df[df["NAME"] != "Missouri"]
```

#### Extract County FIPS Code

County FIPS codes will be used as join keys.

```python
df["county_fips"] = df["GEO_ID"].str[-5:]
```

Example:

| GEO_ID | county_fips |
|------|------|
0500000US29001 | 29001 |
0500000US29189 | 29189 |

#### Drop Empty Columns

```python
df = df.dropna(axis=1, how="all")
```

#### Rename Key Columns

Example:

```python
df = df.rename(columns={
    "B19013_001E": "median_income"
})
```

---

# 2. Election Results Dataset

File:

- MO 2020 Election Results.csv

### Structure

Each row represents a **precinct**.

Columns contain vote totals for candidates.

Example:

| Column | Meaning |
|------|------|
G20PRERTRU | Trump votes |
G20PREDBID | Biden votes |

### Cleaning Steps

#### Create Total Turnout

```python
df["total_votes"] = df["G20PRERTRU"] + df["G20PREDBID"]
```

#### Extract County FIPS

```python
df["county_fips"] = df["COUNTYFP"]
```

#### Standardize Precinct Name

```python
df["precinct"] = df["NAME"].str.strip().str.upper()
```

---

# 3. Polling Locations Dataset

File:

- MO 2020 Polling Locations.csv

### Key Fields

- county_name
- precinct_name
- polling_place_id
- address

### Cleaning Steps

#### Standardize County Names

```python
df["county_name"] = df["county_name"].str.strip().str.upper()
```

#### Standardize Precinct Names

```python
df["precinct_name"] = df["precinct_name"].str.strip().str.upper()
```

#### Remove Duplicate Polling Locations

```python
df = df.drop_duplicates()
```

---

# 4. Precinct Geography Dataset

Files:

- MO 2020 Precincts.shp
- MO 2020 Precincts.dbf
- MO 2020 Precincts.shx
- MO 2020 Precincts.prj
- MO 2020 Precincts.cpg

### Load with GeoPandas

```python
import geopandas as gpd

gdf = gpd.read_file("MO 2020 Precincts.shp")
```

### Extract Join Keys

```python
gdf["county_fips"] = gdf["COUNTYFP20"]
gdf["precinct"] = gdf["NAME20"].str.strip().str.upper()
```

---

# Join Strategy

Datasets will be linked using:

| Dataset | Join Key |
|------|------|
Election Results | COUNTYFP |
Census Data | county_fips |
Polling Locations | county_name / precinct_name |
Precinct Geography | COUNTYFP20 / NAME20 |

Typical join pipeline:

```
Precinct Results
    ↓
County Demographics
    ↓
Polling Locations
    ↓
Spatial Precinct Boundaries
```

---

# Validation Checks

Before analysis, confirm:

```python
print(df.shape)
print(df.isnull().sum())
```

Check county counts:

```python
df["county_fips"].nunique()
```

Expected:

```
116 counties (Missouri)
```

---

# Important Project Principle

Raw files should **never be modified manually**.

All transformations should occur **inside the notebook** to ensure:

- transparency
- reproducibility
- clear documentation of analytical steps

Example comment:

```python
# NOTE:
# Raw datasets are loaded exactly as downloaded.
# Cleaning and normalization steps are applied programmatically
# to preserve reproducibility.
```

---

# Result

After cleaning, the datasets will support:

- turnout analysis
- demographic correlation analysis
- polling location accessibility modeling
- predictive voter demand modeling
- prescriptive polling resource allocation

