"""Download the Y-1 site context data, everything in EPSG:26911 (NAD83 / UTM 11N, meters).

Outputs to ../data/:
  dem.tif            USGS 3DEP 1 m DEM, NAVD88 meters
  buildings.geojson  LA County LARIAC 2020 building outlines (HEIGHT/ELEV kept in feet as delivered)
  parcels_y1.geojson Y-1 candidate parcels from LA County Assessor
  site.json          origin, extent, CRS
"""
import json
from pathlib import Path

import requests
from pyproj import Transformer

DATA = Path(__file__).resolve().parent.parent / "data"
DATA.mkdir(exist_ok=True)

CRS = 26911
HALF = 400  # half-size of the square extent, meters
# Centroid of Assessor parcel 5149-010-951 (Angels Knoll), from the parcel layer's CENTER_LAT/LON
CENTER_LL = (34.05099185, -118.25055878)
Y1_APNS = ["5149-010-951", "5149-010-269", "5149-010-952"]

LAC = "https://public.gis.lacounty.gov/public/rest/services"
BLD = f"{LAC}/LACounty_Dynamic/LARIAC_Buildings_2020/MapServer/0/query"
PCL = f"{LAC}/LACounty_Cache/LACounty_Parcel/MapServer/0/query"
DEP = "https://elevation.nationalmap.gov/arcgis/rest/services/3DEPElevation/ImageServer/exportImage"

to_utm = Transformer.from_crs(4326, CRS, always_xy=True)
cx, cy = to_utm.transform(CENTER_LL[1], CENTER_LL[0])
ox, oy = round(cx / 10) * 10, round(cy / 10) * 10  # scene origin, rounded to 10 m
xmin, ymin, xmax, ymax = ox - HALF, oy - HALF, ox + HALF, oy + HALF
envelope = json.dumps({"xmin": xmin, "ymin": ymin, "xmax": xmax, "ymax": ymax,
                       "spatialReference": {"wkid": CRS}})
print(f"origin {ox}, {oy}  extent {xmin},{ymin} - {xmax},{ymax}")


def query_all(url, params):
    feats, offset = [], 0
    while True:
        p = dict(params, resultOffset=offset, resultRecordCount=1000, f="geojson")
        r = requests.get(url, params=p, timeout=120)
        r.raise_for_status()
        batch = r.json().get("features", [])
        feats += batch
        if len(batch) < 1000:
            return feats
        offset += len(batch)


# 1. DEM
r = requests.get(DEP, params={
    "bbox": f"{xmin},{ymin},{xmax},{ymax}", "bboxSR": CRS, "imageSR": CRS,
    "size": f"{2 * HALF},{2 * HALF}", "format": "tiff", "pixelType": "F32",
    "interpolation": "RSP_BilinearInterpolation", "f": "image"}, timeout=300)
r.raise_for_status()
(DATA / "dem.tif").write_bytes(r.content)
print("dem.tif", len(r.content), "bytes")

# 2. Buildings
bld = query_all(BLD, {"geometry": envelope, "geometryType": "esriGeometryEnvelope", "inSR": CRS,
                      "spatialRel": "esriSpatialRelIntersects", "outFields": "*", "outSR": CRS})
(DATA / "buildings.geojson").write_text(json.dumps({"type": "FeatureCollection", "features": bld}))
print("buildings", len(bld))

# 3. Y-1 candidate parcels
where = "APN IN ({})".format(",".join(f"'{a}'" for a in Y1_APNS))
pcl = query_all(PCL, {"where": where, "outFields": "APN,AgencyName,UseDescription,LegalDescription",
                      "outSR": CRS})
(DATA / "parcels_y1.geojson").write_text(json.dumps({"type": "FeatureCollection", "features": pcl}))
print("parcels", [f["properties"]["APN"] for f in pcl])

(DATA / "site.json").write_text(json.dumps({
    "crs": f"EPSG:{CRS}", "units": "m", "vertical_datum": "NAVD88 (m)",
    "origin": [ox, oy], "extent": [xmin, ymin, xmax, ymax], "center_latlon": CENTER_LL,
    "sources": {"dem": DEP, "buildings": BLD, "parcels": PCL}}, indent=2))
