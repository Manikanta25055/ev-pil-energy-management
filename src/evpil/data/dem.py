"""Sample a digital elevation model at GPS coordinates.

VED logs latitude and longitude but no elevation, so the road gradient the
plant needs has to be recovered from a DEM. This module does the sampling and
nothing else: the array is prepared once by `scripts/build_dem.py`, which owns
the geospatial dependencies, so reading it here needs only numpy.

Bilinear interpolation rather than nearest neighbour, because nearest
neighbour makes elevation a staircase with a tread the width of a DEM cell.
Differentiating a staircase gives a gradient that is zero almost everywhere
and enormous at the risers, which is the same failure the i3 archive's raw
10 Hz elevation produced.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np


@dataclass(frozen=True)
class DEM:
    """A north-up geographic elevation grid and where its corners are."""

    elevation: np.ndarray      # (rows, cols), metres, NaN where absent
    west: float                # longitude of the western edge of column 0
    north: float               # latitude of the northern edge of row 0
    lon_step: float            # degrees per column, positive eastward
    lat_step: float            # degrees per row, negative southward
    crs: str = ""
    source: str = ""

    @classmethod
    def load(cls, path: Path | str) -> "DEM":
        with np.load(Path(path), allow_pickle=False) as z:
            return cls(
                elevation=z["elevation"].astype(np.float64),
                west=float(z["west"]), north=float(z["north"]),
                lon_step=float(z["lon_step"]), lat_step=float(z["lat_step"]),
                crs=str(z["crs"]) if "crs" in z else "",
                source=str(z["source"]) if "source" in z else "",
            )

    @property
    def bounds(self) -> tuple[float, float, float, float]:
        """(west, south, east, north) in degrees."""
        rows, cols = self.elevation.shape
        return (self.west, self.north + self.lat_step * rows,
                self.west + self.lon_step * cols, self.north)

    @property
    def cell_size_m(self) -> float:
        """Approximate north-south cell size in metres."""
        return abs(self.lat_step) * 111_320.0

    def sample(self, lat, lon) -> np.ndarray:
        """Bilinearly interpolated elevation, in metres, NaN outside the grid.

        Coordinates are cell-centre referenced: the value stored at row 0,
        column 0 describes the centre of that cell, not its corner, so half a
        cell is subtracted before interpolating. Getting this wrong offsets
        every elevation by half a cell of ground, which on a slope is a real
        error and a silent one.

        A point is inside when it falls within the grid's outer edges, not
        merely within the ring of cell centres. Requiring a neighbour on both
        sides would discard the outer half-cell, and would discard a point
        landing exactly on the first cell centre, where the arithmetic lands a
        hair below zero. Within the outer half-cell the interpolation weights
        clamp, so the edge value is extended rather than extrapolated.
        """
        lat = np.asarray(lat, dtype=float)
        lon = np.asarray(lon, dtype=float)
        rows, cols = self.elevation.shape

        col = (lon - self.west) / self.lon_step
        row = (lat - self.north) / self.lat_step
        inside = (col >= 0.0) & (col <= cols) & (row >= 0.0) & (row <= rows)

        x = np.clip(col - 0.5, 0.0, cols - 1.0)
        y = np.clip(row - 0.5, 0.0, rows - 1.0)

        xi = np.clip(np.floor(x).astype(int), 0, max(cols - 2, 0))
        yi = np.clip(np.floor(y).astype(int), 0, max(rows - 2, 0))
        fx = x - xi
        fy = y - yi

        g = self.elevation
        x1 = np.minimum(xi + 1, cols - 1)
        y1 = np.minimum(yi + 1, rows - 1)
        top = g[yi, xi] * (1.0 - fx) + g[yi, x1] * fx
        bot = g[y1, xi] * (1.0 - fx) + g[y1, x1] * fx
        out = top * (1.0 - fy) + bot * fy

        return np.where(inside, out, np.nan)

    def covers(self, lat, lon) -> np.ndarray:
        """Whether each coordinate falls inside the interpolatable interior."""
        return np.isfinite(self.sample(lat, lon))
