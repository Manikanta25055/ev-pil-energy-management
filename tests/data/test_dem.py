"""DEM sampling: bilinear, cell-centre referenced, and honest off the edge."""

import numpy as np
import pytest

from evpil.data.dem import DEM

# A 3x3 grid with a pure eastward slope, one metre of rise per cell.
# Cell centres sit at lon -83.0, -82.9, -82.8 and lat 42.2, 42.1, 42.0.
GRID = np.array([[10.0, 11.0, 12.0],
                 [10.0, 11.0, 12.0],
                 [10.0, 11.0, 12.0]])
D = DEM(elevation=GRID, west=-83.05, north=42.25, lon_step=0.1, lat_step=-0.1)


def test_sampling_a_cell_centre_returns_that_cell():
    assert D.sample(42.2, -83.0) == pytest.approx(10.0)
    assert D.sample(42.1, -82.9) == pytest.approx(11.0)
    assert D.sample(42.0, -82.8) == pytest.approx(12.0)


def test_sampling_between_centres_interpolates():
    """Halfway between the 10 m and 11 m columns is 10.5 m, not either of them."""
    assert D.sample(42.2, -82.95) == pytest.approx(10.5)
    assert D.sample(42.2, -82.975) == pytest.approx(10.25)


def test_a_north_south_move_does_not_change_an_eastward_slope():
    assert D.sample(42.0, -82.95) == pytest.approx(D.sample(42.2, -82.95))


def test_bilinear_interpolates_in_both_axes():
    tilted = DEM(elevation=np.array([[0.0, 0.0], [0.0, 4.0]]),
                 west=0.0, north=1.0, lon_step=1.0, lat_step=-1.0)
    # The single interpolatable point is the centre of the 2x2 stencil.
    assert tilted.sample(0.0, 1.0) == pytest.approx(1.0)


def test_outside_the_grid_is_nan_not_a_guess():
    assert np.isnan(D.sample(50.0, -83.0))
    assert np.isnan(D.sample(42.2, -70.0))
    assert not D.covers(50.0, -83.0)


def test_the_outer_half_cell_extends_the_edge_rather_than_dropping_out():
    """A point inside the grid's edge is on the grid, centres notwithstanding."""
    assert D.covers(42.2, -83.0)          # first cell centre
    assert D.covers(42.2, -83.04)         # west of every centre, still on grid
    assert D.sample(42.2, -83.04) == pytest.approx(10.0)
    assert not D.covers(42.2, -83.06)     # past the western edge


def test_sampling_accepts_arrays():
    out = D.sample(np.array([42.2, 42.2]), np.array([-83.0, -82.9]))
    assert out.shape == (2,)
    assert out == pytest.approx([10.0, 11.0])


def test_bounds_and_cell_size_are_reported():
    w, s, e, n = D.bounds
    assert (w, n) == pytest.approx((-83.05, 42.25))
    assert (e, s) == pytest.approx((-82.75, 41.95))
    assert D.cell_size_m == pytest.approx(0.1 * 111_320.0)


def test_roundtrip_through_a_saved_file(tmp_path):
    p = tmp_path / "dem.npz"
    np.savez_compressed(p, elevation=GRID.astype(np.float32), west=-83.05,
                        north=42.25, lon_step=0.1, lat_step=-0.1,
                        crs="EPSG:4269", source="test")
    loaded = DEM.load(p)
    assert loaded.crs == "EPSG:4269"
    assert loaded.sample(42.2, -82.95) == pytest.approx(10.5)


def test_nan_cells_propagate_rather_than_being_filled():
    holed = DEM(elevation=np.array([[np.nan, 1.0, 2.0],
                                    [0.0, 1.0, 2.0],
                                    [0.0, 1.0, 2.0]]),
                west=-83.05, north=42.25, lon_step=0.1, lat_step=-0.1)
    assert np.isnan(holed.sample(42.2, -82.95))
