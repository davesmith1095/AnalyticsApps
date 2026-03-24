from pathlib import Path
import geopandas as gpd

# create a Path object for the current and work directories
current_dir = Path.cwd()

# Looks to parent directory of current directory, which is the root of the project
working_dir = current_dir.parent

# create a Path object for the data, logs, and raw geodata directories
data_dir = working_dir / "data"
logs_dir = working_dir / "logs"
geodata = working_dir / "data/geo/raw/"

# Looks in each subfolder under raw geodata for shapefiles and prints their names
shapefiles = list(geodata.glob("**/*.shp"))

# variable for all shapefiles in geodata directory
shapefile_names = [shapefile.name for shapefile in shapefiles]

mo_2010_county = gpd.read_file(geodata / "mo_county_2010/mo_county_2010.shp")
mo_2010_county.head()

