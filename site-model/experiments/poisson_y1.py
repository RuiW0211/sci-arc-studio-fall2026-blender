"""Experiment: Poisson surface reconstruction straight from the aerial LiDAR around Y-1.

Question: can the 2023 airborne LiDAR be turned into a site mesh directly, without the modelling
pipeline (DEM + tiered buildings + fitted landmarks)? Output meshes (PLY, local coords, Z up):
  out/poisson_all_d10.ply     all non-noise returns (ground + vegetation + structures)
  out/poisson_ground_d10.ply  ground returns only
Vertex colours: tan = from ground returns, green-grey = from everything else (Poisson interpolates them).
"""
import json
from pathlib import Path

import laspy
import numpy as np
import open3d as o3d
from shapely.geometry import shape

ROOT = Path(__file__).resolve().parent.parent
DATA, OUT = ROOT / "data", Path(__file__).resolve().parent / "out"
OUT.mkdir(exist_ok=True)
MARGIN, DEPTH, TRIM_Q = 30.0, 10, 0.04

site = json.loads((DATA / "site.json").read_text())
ox, oy = site["origin"]
y1 = next(shape(f["geometry"]) for f in json.loads((DATA / "parcels_y1.geojson").read_text())["features"]
          if f["properties"]["APN"] == "5149-010-951")
x0, y0, x1, y1b = y1.buffer(MARGIN).bounds

las = laspy.read(next((DATA / "lidar").glob("*.laz")))
x, y, z, cl = np.asarray(las.x), np.asarray(las.y), np.asarray(las.z), np.asarray(las.classification)
m = (x > x0) & (x < x1) & (y > y0) & (y < y1b) & ~np.isin(cl, (7, 18))
P = np.column_stack([x[m] - ox, y[m] - oy, z[m]])
ground = cl[m] == 2
C = np.where(ground[:, None], [0.74, 0.64, 0.48], [0.42, 0.52, 0.44])
print(f"crop {x1 - x0:.0f} x {y1b - y0:.0f} m: {len(P):,} points ({ground.mean():.0%} ground)")


def reconstruct(points, colors, name):
    pcd = o3d.geometry.PointCloud(o3d.utility.Vector3dVector(points))
    pcd.colors = o3d.utility.Vector3dVector(colors)
    pcd.estimate_normals(o3d.geometry.KDTreeSearchParamKNN(knn=20))
    pcd.orient_normals_to_align_with_direction((0.0, 0.0, 1.0))  # airborne: surfaces face the sky
    mesh, dens = o3d.geometry.TriangleMesh.create_from_point_cloud_poisson(pcd, depth=DEPTH)
    dens = np.asarray(dens)
    mesh.remove_vertices_by_mask(dens < np.quantile(dens, TRIM_Q))  # drop the extrapolated skirt
    mesh = mesh.crop(pcd.get_axis_aligned_bounding_box())
    mesh.compute_vertex_normals()
    o3d.io.write_triangle_mesh(str(OUT / f"{name}.ply"), mesh)
    print(f"{name}: {len(mesh.vertices):,} vertices, {len(mesh.triangles):,} triangles, "
          f"watertight={mesh.is_watertight()}")


reconstruct(P, C, f"poisson_all_d{DEPTH}")
reconstruct(P[ground], C[ground], f"poisson_ground_d{DEPTH}")
json.dump({"bounds_local": [x0 - ox, y0 - oy, x1 - ox, y1b - oy]}, open(OUT / "crop.json", "w"))
