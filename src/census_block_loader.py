"""
census_block_loader.py
----------------------
Downloads and loads 2020 Decennial Census block-level data for Missouri.

Provides two things the precinct_builder needs:
  1. Block geometries (TIGER/Line shapefiles from Census Bureau)
  2. Block-level population and Voting Age Population (VAP)

Census API key required for population data.
Get a free key at: https://api.census.gov/data/key_signup.html
"""

import os
import io
import zipfile
import logging
import requests
import pandas as pd
import geopandas as gpd
from pathlib import Path

# Missouri's FIPS state code
MO_STATE_FIPS = "29"

# 2020 Decennial Census PL 94-171 variable codes
# PL file is the redistricting dataset — it has population and VAP at block level
CENSUS_BLOCK_VARS = {
    "P1_001N": "total_population",     # Total population
    "P3_001N": "vap_total",            # Total voting age population (18+)
}

# URL for Missouri 2020 TIGER/Line block boundaries (no API key needed)
TIGER_BLOCK_URL = (
    "https://www2.census.gov/geo/tiger/TIGER2020/TABBLOCK20/"
    "tl_2020_29_tabblock20.zip"
)


class CensusBlockLoader:
    """
    Handles downloading and loading of 2020 Census block data for Missouri.

    Usage:
        loader = CensusBlockLoader(
            geo_raw_dir="data/geo/raw/",
            census_api_key="a07ea69ad3d8540b2af06b4cf1476768e695afd9"
        )
        blocks_gdf = loader.get_blocks_with_population()
    """

    def __init__(self, geo_raw_dir="data/geo/raw/", census_api_key=None):
        self.geo_dir = Path(geo_raw_dir)
        self.census_api_key = census_api_key
        self.blocks_dir = self.geo_dir / "mo_2020_census_blocks"
        self.blocks_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def get_blocks_with_population(self):
        """
        Main entry point. Returns a GeoDataFrame of Missouri census blocks
        with geometry, total population, and VAP columns attached.

        If local files exist, loads from disk. Otherwise downloads first.

        Returns
        -------
        geopandas.GeoDataFrame
            Columns: GEOID20, geometry, total_population, vap_total
            CRS: EPSG:4326 (will be reprojected by precinct_builder as needed)
        """
        blocks_gdf  = self._load_or_download_block_geometry()
        pop_df      = self._load_or_fetch_block_population()

        # Join population onto geometry using the 20-digit block GEOID
        merged = blocks_gdf.merge(pop_df, on="GEOID20", how="left")

        missing = merged["total_population"].isna().sum()
        if missing > 0:
            logging.warning(
                f"{missing} blocks have no population data after merge. "
                "Check that GEOID20 formats match between geometry and API response."
            )

        logging.info(
            f"Census blocks loaded: {len(merged):,} blocks, "
            f"total MO population: {merged['total_population'].sum():,.0f}"
        )
        return merged

    # ------------------------------------------------------------------
    # Block geometry
    # ------------------------------------------------------------------

    def _load_or_download_block_geometry(self):
        """Loads block shapefile from disk, downloading from Census if missing."""
        shp_path = self.blocks_dir / "tl_2020_29_tabblock20.shp"

        if shp_path.exists():
            logging.info("Loading cached block geometry from disk...")
            return gpd.read_file(shp_path)[["GEOID20", "geometry"]]

        logging.info("Block shapefile not found locally. Downloading from Census Bureau...")
        print("  Downloading Missouri block boundaries (~60MB, one-time download)...")

        response = requests.get(TIGER_BLOCK_URL, stream=True)
        response.raise_for_status()

        # Unzip directly into the blocks directory
        with zipfile.ZipFile(io.BytesIO(response.content)) as z:
            z.extractall(self.blocks_dir)

        print(f"  Block geometry saved to {self.blocks_dir}")
        logging.info("Block geometry downloaded and extracted.")

        gdf = gpd.read_file(shp_path)
        return gdf[["GEOID20", "geometry"]]

    # ------------------------------------------------------------------
    # Block population (Census API)
    # ------------------------------------------------------------------

    def _load_or_fetch_block_population(self):
        """Loads block population CSV from disk, querying Census API if missing."""
        csv_path = self.blocks_dir / "mo_2020_block_population.csv"

        if csv_path.exists():
            logging.info("Loading cached block population data from disk...")
            df = pd.read_csv(csv_path, dtype={"state": str, "county": str,
                                               "tract": str, "block": str})
            return self._build_geoid(df)

        if not self.census_api_key:
            raise ValueError(
                "Census API key required to download block population data.\n"
                "Get a free key at: https://api.census.gov/data/key_signup.html\n"
                "Then pass it as: CensusBlockLoader(census_api_key='a07ea69ad3d8540b2af06b4cf1476768e695afd9')"
            )

        logging.info("Querying Census API for block-level population...")
        print("  Fetching block population from Census API (this may take a minute)...")

        df = self._query_census_api()
        df.to_csv(csv_path, index=False)
        print(f"  Block population cached to {csv_path}")

        return self._build_geoid(df)

    def _query_census_api(self):
        """
        Queries the 2020 Decennial Census PL 94-171 API for all Missouri blocks.
        Iterates by county to avoid API timeouts on large state-wide queries.
        """
        from census import Census          # pip install census
        client = Census(self.census_api_key, year=2020)

        # Get list of Missouri county FIPS codes to iterate over
        counties = client.pl.state_county(
            fields=["NAME"],
            state_fips=MO_STATE_FIPS,
            county_fips="*"
        )
        county_fips_list = [c["county"] for c in counties]

        # Variables to pull: rename keys to human-readable names
        vars_to_get = list(CENSUS_BLOCK_VARS.keys()) + ["GEO_ID"]
        all_rows = []

        for county_fips in county_fips_list:
            rows = client.pl.state_county_blockgroup(
                fields=vars_to_get,
                state_fips=MO_STATE_FIPS,
                county_fips=county_fips,
                blockgroup_fips="*"
            )
            all_rows.extend(rows)

        df = pd.DataFrame(all_rows)

        # Rename Census variable codes to human-readable column names
        df = df.rename(columns=CENSUS_BLOCK_VARS)

        # Coerce numeric columns
        for col in CENSUS_BLOCK_VARS.values():
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)

        return df

    @staticmethod
    def _build_geoid(df):
        """
        Reconstructs the 15-digit block GEOID from component FIPS parts
        (state + county + tract + block), matching the GEOID20 format in
        the TIGER shapefile.
        """
        if "GEOID20" in df.columns:
            return df

        # Pad each component to its standard width
        df["GEOID20"] = (
            df["state"].str.zfill(2)
            + df["county"].str.zfill(3)
            + df["tract"].str.zfill(6)
            + df["block"].str.zfill(4)
        )
        return df
