from pathlib import Path
import geopandas as gpd

class GeoLoader:
    """Handles the dynamic ingestion of spatial data from the data/geo/raw/ directory."""
    
    def __init__(self, geo_raw_dir="data/geo/raw/"):
        # We use Path() here exactly like you did in your explorer!
        self.geo_dir = Path(geo_raw_dir)

    def get_precinct_shapefile(self, year):
        """
        Dynamically finds and loads the correct precinct shapefile based on the election year.
        Because shapefile names change every census cycle, this dictionary maps the year 
        to the correct subfolder in your raw data.
        """
        # Mapping based on the directory structure you provided earlier
        year_folder_map = {
            2016: "mo_2016_vest",
            2020: "mo_2020_vest",
            2024: "mo_2024_gen_all_prec" 
        }

        folder_name = year_folder_map.get(year)
        if not folder_name:
            print(f"Warning: No shapefile folder mapped for year {year}")
            return None

        # Look specifically inside the mapped folder for the .shp file
        target_folder = self.geo_dir / folder_name
        shapefiles = list(target_folder.glob("*.shp"))

        if not shapefiles:
            print(f"Warning: No .shp file found in {target_folder}")
            return None

        # Geopandas reads the first .shp file it finds in that folder
        file_to_load = shapefiles[0]
        print(f"    -> Loading shapefile: {file_to_load.name}")
        
        return gpd.read_file(file_to_load)