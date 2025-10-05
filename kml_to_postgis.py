import geopandas as gpd
from sqlalchemy import create_engine
import fiona
import pandas as pd
from shapely.ops import transform

# Read KML
path = r'C:\Users\ruyca\Desktop\Hackatones\SpaceApps_2025\farmlands\kml_files\farmlands_2025_2.kml'

# List all layers in the KML
layers = fiona.listlayers(path)
print("Available layers:", layers)

# Read all layers and combine them
gdfs = []
for layer in layers:
    try:
        gdf = gpd.read_file(path, layer=layer)
        if len(gdf) > 0:
            gdf['layer_name'] = layer
            
            # Force 2D geometries (remove Z coordinate)
            gdf['geometry'] = gdf['geometry'].apply(lambda geom: transform(lambda x, y, z=None: (x, y), geom))
            
            gdfs.append(gdf)
            print(f"✓ Read layer: {layer} with {len(gdf)} features")
        else:
            print(f"⚠ Skipped layer: {layer} (empty)")
    except Exception as e:
        print(f"✗ Error reading layer: {layer} - {str(e)}")
        continue

# Combine all layers into one GeoDataFrame
if gdfs:
    combined_gdf = gpd.GeoDataFrame(pd.concat(gdfs, ignore_index=True))
    print(f"\n✓ Total features combined: {len(combined_gdf)}")
    
    # Write to PostGIS
    engine = create_engine('postgresql://ruyca:ruycc312@localhost:5433/farmlands_2025')
    combined_gdf.to_postgis('farm_boundaries', engine, if_exists='replace', index=False)
    
    print("✓ Successfully imported all valid layers to PostGIS!")
else:
    print("✗ No valid layers found to import")