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
import time
import zipfile
import logging
import requests
import pandas as pd
import geopandas as gpd
from pathlib import Path

# Shared headers for all Census API requests.
# Some government APIs silently drop connections from clients with no User-Agent.
_CENSUS_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; AnalyticsApps/1.0; Census data research)"
}

# Seconds to wait between county-level block queries to avoid rate limiting.
_INTER_QUERY_SLEEP = 0.5

# Request timeouts: (connect_timeout_seconds, read_timeout_seconds)
_REQUEST_TIMEOUT = (10, 60)

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

    def _get_with_retry(self, url, params, max_retries=2, backoff=2.0):
        """
        Wraps requests.get with simple retry logic for transient Census API errors.

        Retries on ConnectionError or HTTP 5xx responses. Raises on the final
        attempt so the caller still sees the error if all retries are exhausted.
        """
        last_exc = None
        for attempt in range(max_retries + 1):
            try:
                resp = requests.get(
                    url,
                    params=params,
                    headers=_CENSUS_HEADERS,
                    timeout=_REQUEST_TIMEOUT,
                )
                resp.raise_for_status()
                return resp.json()
            except (requests.ConnectionError, requests.Timeout) as exc:
                last_exc = exc
                if attempt < max_retries:
                    wait = backoff * (attempt + 1)
                    logging.warning(
                        f"    Request failed ({exc}), retrying in {wait}s "
                        f"(attempt {attempt+1}/{max_retries})..."
                    )
                    time.sleep(wait)
            except requests.HTTPError as exc:
                # Only retry on server-side errors (5xx); propagate client errors (4xx)
                if exc.response is not None and exc.response.status_code < 500:
                    raise
                last_exc = exc
                if attempt < max_retries:
                    wait = backoff * (attempt + 1)
                    logging.warning(
                        f"    HTTP {exc.response.status_code}, retrying in {wait}s..."
                    )
                    time.sleep(wait)
        raise last_exc

    def _query_census_api(self):
        """
        Queries the 2020 Decennial Census PL 94-171 API for all Missouri blocks
        using the Census Bureau REST API directly via requests.

        The `census` Python package does not support block-level PL queries —
        its state_county_blockgroup method returns block GROUP data (too coarse).
        We need individual blocks, so we call the API directly.

        Iterates by county to avoid API timeouts on large state-wide queries.

        Census API docs: https://api.census.gov/data/2020/dec/pl/variables.html
        """
        BASE_URL = "https://api.census.gov/data/2020/dec/pl"
        vars_to_get = ",".join(CENSUS_BLOCK_VARS.keys())

        # Step 1: Get the list of Missouri county FIPS codes from the API
        logging.info("Fetching Missouri county FIPS list from Census API...")
        county_resp = requests.get(
            BASE_URL,
            params={
                "get": "NAME",
                "for": "county:*",
                "in": f"state:{MO_STATE_FIPS}",
                "key": self.census_api_key,
            },
            headers=_CENSUS_HEADERS,
            timeout=_REQUEST_TIMEOUT,
        )
        county_resp.raise_for_status()
        county_data = county_resp.json()
        # Response format: first row = headers, subsequent rows = data
        # Headers: ['NAME', 'state', 'county']
        county_fips_list = [row[2] for row in county_data[1:]]
        logging.info(f"Found {len(county_fips_list)} Missouri counties to query.")

        # Step 2: Query block-level population for each county
        all_rows = []
        headers = None

        for i, county_fips in enumerate(county_fips_list):
            logging.info(
                f"  Querying county {county_fips} ({i+1}/{len(county_fips_list)})..."
            )
            data = self._get_with_retry(
                BASE_URL,
                params={
                    "get": vars_to_get,
                    "for": "block:*",
                    "in": f"state:{MO_STATE_FIPS} county:{county_fips}",
                    "key": self.census_api_key,
                },
            )

            # Capture headers from first county only; they're identical for all
            if headers is None:
                headers = data[0]

            all_rows.extend(data[1:])

            # Pause between requests to stay within the Census API rate limit
            time.sleep(_INTER_QUERY_SLEEP)

        df = pd.DataFrame(all_rows, columns=headers)

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
        # GEOID20 = 2-digit state + 3-digit county + 6-digit tract + 4-digit block = 15 digits
        df["GEOID20"] = (
            df["state"].str.zfill(2)
            + df["county"].str.zfill(3)
            + df["tract"].str.zfill(6)
            + df["block"].str.zfill(4)
        )
        return df
