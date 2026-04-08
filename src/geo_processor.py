import pandas as pd
import geopandas as gpd
from geopy.geocoders import Nominatim
import time
import numpy as np

def geocode_polling_locations(df_polling, user_agent="mo_voting_pipeline_v1"):
    """Safely geocodes addresses with hardcoded fallbacks for rural routes."""
    geolocator = Nominatim(user_agent=user_agent, timeout=10)
    
    # Hardcoded fallbacks for known un-geocodable rural locations
    fallbacks = {
        "403 College St, Greenfield, MO 65661": (37.4142, -93.8404),
        "409 Montgomery St, Greenfield, MO 65661": (37.4153, -93.8410),
        "121 W Commercial St, Everton, MO 65646": (37.3425, -93.7024),
        "37631 Arcola, Arcola, MO 65603": (37.5492, -93.8753)
    }

    def _safe_geocode(address):
        if address in fallbacks:
            return fallbacks[address]
        try:
            time.sleep(1.1) # Respect API limits
            loc = geolocator.geocode(address)
            if loc: return loc.latitude, loc.longitude
        except:
            pass
        return None, None

    # Deduplicate and apply
    unique_locations = df_polling.drop_duplicates(subset=['LOCATION_ADDRESS']).copy()
    unique_locations['coords'] = unique_locations['LOCATION_ADDRESS'].apply(_safe_geocode)
    unique_locations['lat'] = unique_locations['coords'].apply(lambda x: x[0])
    unique_locations['lon'] = unique_locations['coords'].apply(lambda x: x[1])
    
    clean_locs = unique_locations.dropna(subset=['lat', 'lon'])
    
    # Convert to standard web coordinates
    gdf = gpd.GeoDataFrame(
        clean_locs, 
        geometry=gpd.points_from_xy(clean_locs.lon, clean_locs.lat),
        crs="EPSG:4326"
    )
    return gdf.drop(columns=['coords'])

def prepare_precincts(shapefile_path):
    """Loads shapefile, repairs geometry, projects to meters, calculates area."""
    gdf = gpd.read_file(shapefile_path)
    gdf['geometry'] = gdf.geometry.make_valid()
    gdf = gdf.to_crs(epsg=5070) # Project to Equal Area (Meters)
    gdf['Area_Sq_Miles'] = gdf.geometry.area * 0.000000386102
    return gdf

def calculate_spatial_density(precincts_gdf, polling_gdf):
    """Performs the spatial join and calculates Square Miles per Poll."""
    # Ensure matching projections before joining
    polling_gdf = polling_gdf.to_crs(epsg=5070)
    
    # Spatial Join
    joined = gpd.sjoin(precincts_gdf, polling_gdf, how="left", predicate="intersects")
    poll_counts = joined.groupby('GEOID20')['LOCATION_NAME'].count().reset_index(name='Polling_Locations_Count')
    
    final_gdf = precincts_gdf.merge(poll_counts, on='GEOID20')
    
    # Calculate Metric (Handle divide by zero for resource deserts)
    final_gdf['Sq_Miles_Per_Poll'] = final_gdf['Area_Sq_Miles'] / final_gdf['Polling_Locations_Count'].replace(0, np.nan)
    return final_gdf