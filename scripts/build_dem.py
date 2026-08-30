# scripts/build_dem.py
"""Cut the elevation model VED needs out of the USGS 3DEP tile, once.

VED logs latitude and longitude but no elevation, so road gradient has to come
from a digital elevation model. This script does the part that needs GDAL and
a network: it reads only the window covering the fleet's bounding box out of a
1 degree 3DEP tile, without downloading the whole 421 MB file, and writes a
compact array.

Everything downstream reads that array with numpy alone, so the geospatial
stack is a build-time dependency and not a runtime one. Run it once; the
result is deterministic.

    python3 scripts/build_dem.py

Source: USGS 3D Elevation Program, 1/3 arc-second (about 10 m) seamless DEM,
tile n43w084, public domain. https://www.usgs.gov/3d-elevation-program
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

import numpy as np

# The bounding box of the VED battery-electric GPS traces, padded so that
# bilinear interpolation never reaches past the edge of the array.
VED_BOUNDS = dict(west=-83.82, south=42.20, east=-83.65, north=42.34)

TILE_URL = ("https://prd-tnm.s3.amazonaws.com/StagedProducts/Elevation/13/"
            "TIFF/current/n43w084/USGS_13_n43w084.tif")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default=TILE_URL)
    ap.add_argument("--out", default="data/raw/dem/annarbor_3dep_13.npz")
    ap.add_argument("--geotiff", default="data/raw/dem/annarbor_3dep_13.tif",
                    help="cached window; reused instead of refetching")
    args = ap.parse_args()

    os.environ.setdefault("GDAL_DISABLE_READDIR_ON_OPEN", "EMPTY_DIR")
    os.environ.setdefault("CPL_VSIL_CURL_ALLOWED_EXTENSIONS", ".tif")
    import rasterio
    from rasterio.windows import from_bounds

    crop = Path(args.geotiff)
    if crop.exists():
        src_path = str(crop)
        window = None
        print(f"reusing cached window {crop}")
    else:
        src_path = f"/vsicurl/{args.url}"
        window = True
        crop.parent.mkdir(parents=True, exist_ok=True)
        print(f"reading the window from {args.url}\n"
              f"(byte-range reads only; the full tile is 421 MB)")

    with rasterio.open(src_path) as src:
        if window is None:
            arr, transform, nodata = src.read(1), src.transform, src.nodata
        else:
            win = from_bounds(VED_BOUNDS["west"], VED_BOUNDS["south"],
                              VED_BOUNDS["east"], VED_BOUNDS["north"],
                              src.transform)
            arr = src.read(1, window=win)
            transform = src.window_transform(win)
            nodata = src.nodata
            profile = src.profile
            profile.update(height=arr.shape[0], width=arr.shape[1],
                           transform=transform, compress="deflate", tiled=True,
                           blockxsize=256, blockysize=256)
            with rasterio.open(crop, "w", **profile) as dst:
                dst.write(arr, 1)
            print(f"cached the window to {crop}")
        crs = str(src.crs)

    arr = np.asarray(arr, dtype=np.float32)
    if nodata is not None:
        arr = np.where(arr == np.float32(nodata), np.nan, arr)

    # transform is (lon_step, 0, west, 0, lat_step, north) with lat_step < 0.
    lon_step, _, west, _, lat_step, north = (transform.a, transform.b,
                                             transform.c, transform.d,
                                             transform.e, transform.f)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        out, elevation=arr, west=west, north=north,
        lon_step=lon_step, lat_step=lat_step, crs=crs,
        source="USGS 3DEP 1/3 arc-second, tile n43w084, public domain",
    )

    finite = np.isfinite(arr)
    print(f"\ngrid      {arr.shape[0]} x {arr.shape[1]} at "
          f"{abs(lon_step)*111320:.1f} m")
    print(f"crs       {crs}")
    print(f"bounds    lon {west:.4f} to {west + lon_step*arr.shape[1]:.4f}, "
          f"lat {north + lat_step*arr.shape[0]:.4f} to {north:.4f}")
    print(f"elevation {np.nanmin(arr):.2f} to {np.nanmax(arr):.2f} m, "
          f"{100*finite.mean():.2f}% of cells valid")
    print(f"wrote     {out} ({out.stat().st_size/1e6:.1f} MB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
