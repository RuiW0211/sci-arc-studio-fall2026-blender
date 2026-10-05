"""Download the 2023 USGS 3DEP LiDAR tile that covers the site into site-model/data/lidar/.

The tile is public domain but large (about 67 MB), so it is not in git. Needed by lidar_dsm.py,
lidar_labels.py, prep_blender.py (0.5 m terrain), prep_moca.py, prep_trees.py and
export_lidar_preview.py. Safe to re-run: an existing complete file is kept.

  python3 site-model/scripts/fetch_lidar.py
"""
from pathlib import Path

import requests

URL = ("https://rockyweb.usgs.gov/vdelivery/Datasets/Staged/Elevation/LPC/Projects/CA_LosAngeles_B23/"
       "CA_LosAngeles_1_B23/LAZ/USGS_LPC_CA_LosAngeles_B23_11SLT038400376800.laz")
OUT = Path(__file__).resolve().parent.parent / "data" / "lidar" / URL.rsplit("/", 1)[1]

OUT.parent.mkdir(parents=True, exist_ok=True)
size = int(requests.head(URL, allow_redirects=True, timeout=60).headers.get("content-length", 0))
if OUT.exists() and size and OUT.stat().st_size == size:
    print(f"already there: {OUT} ({size / 1e6:.1f} MB)")
else:
    tmp = OUT.with_suffix(".part")
    with requests.get(URL, stream=True, timeout=600) as r:
        r.raise_for_status()
        done = 0
        with open(tmp, "wb") as f:
            for chunk in r.iter_content(1 << 20):
                f.write(chunk)
                done += len(chunk)
                print(f"\r{done / 1e6:6.1f} / {size / 1e6:.1f} MB", end="", flush=True)
    tmp.replace(OUT)
    print(f"\nsaved {OUT}")
