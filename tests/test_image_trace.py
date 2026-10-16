# SPDX-License-Identifier: GPL-3.0-or-later
"""Unit tests for the pure-numpy tracing core (run with plain ``pytest``)."""

import importlib.util
import pathlib

import numpy as np
import pytest

_PATH = pathlib.Path(__file__).resolve().parents[1] / "sketch_to_hardsurface" / "core" / "image_trace.py"
_spec = importlib.util.spec_from_file_location("image_trace", _PATH)
it = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(it)


def rgba_from_ink(ink):
    """Black ink on white paper."""
    img = np.ones(ink.shape + (4,), dtype=np.float32)
    img[ink, :3] = 0.0
    return img


def square_outline(size=100, lo=20, hi=80, width=3):
    ink = np.zeros((size, size), dtype=bool)
    ink[lo:hi, lo:lo + width] = True
    ink[lo:hi, hi - width:hi] = True
    ink[lo:lo + width, lo:hi] = True
    ink[hi - width:hi, lo:hi] = True
    return ink


def bbox(pts):
    return pts[:, 0].min(), pts[:, 1].min(), pts[:, 0].max(), pts[:, 1].max()


# -- masks ------------------------------------------------------------------

def test_rgba_to_mask_sources():
    img = np.zeros((1, 3, 4), dtype=np.float32)
    img[0, 0] = (0, 0, 0, 1)      # opaque black
    img[0, 1] = (1, 1, 1, 1)      # opaque white
    img[0, 2] = (0, 0, 0, 0)      # transparent
    assert it.rgba_to_mask(img, "DARK").tolist() == [[True, False, False]]
    assert it.rgba_to_mask(img, "LIGHT").tolist() == [[False, True, False]]
    assert it.rgba_to_mask(img, "ALPHA").tolist() == [[True, True, False]]
    with pytest.raises(ValueError):
        it.rgba_to_mask(img, "NOPE")


def test_downsample_limits_size():
    img = np.zeros((1000, 500, 4), dtype=np.float32)
    small, factor = it.downsample(img, 256)
    assert factor == 4
    assert small.shape == (250, 125, 4)
    same, factor = it.downsample(img, 2000)
    assert factor == 1 and same is img


def test_close_gaps_bridges_small_gap_only():
    ink = np.zeros((20, 40), dtype=bool)
    ink[10, 5:18] = True
    ink[10, 21:35] = True          # 3 px gap
    assert not it.close_gaps(ink, 1)[10, 19]
    assert it.close_gaps(ink, 2)[10, 19]


def test_flood_fill_spiral_converges():
    # A corridor that zig-zags forces several row/column sweeps.
    passable = np.zeros((9, 9), dtype=bool)
    passable[1, 1:8] = True
    passable[1:8, 7] = True
    passable[7, 1:8] = True
    passable[3:8, 1] = True
    passable[3, 1:6] = True
    seeds = np.zeros_like(passable)
    seeds[1, 1] = True
    assert np.array_equal(it.flood_fill(passable, seeds), passable)


def test_solid_mask_modes():
    ink = square_outline()
    sil = it.solid_mask(ink, "SILHOUETTE")
    assert sil[50, 50] and sil[21, 21] and not sil[5, 5]
    regions = it.solid_mask(ink, "REGIONS")
    assert regions[50, 50] and not regions[21, 21] and not regions[5, 5]
    assert np.array_equal(it.solid_mask(ink, "FILLED"), ink)


# -- contours ---------------------------------------------------------------

def test_single_pixel_contour_is_ccw_diamond():
    mask = np.zeros((3, 3), dtype=bool)
    mask[1, 1] = True
    loops = it.find_contours(mask)
    assert len(loops) == 1
    assert len(loops[0]) == 4
    assert it.polygon_area(loops[0]) == pytest.approx(0.5)


def test_hole_is_clockwise():
    mask = np.zeros((12, 12), dtype=bool)
    mask[2:10, 2:10] = True
    mask[5:7, 5:7] = False
    areas = sorted(it.polygon_area(p) for p in it.find_contours(mask))
    assert areas[0] < 0 < areas[1]


def test_diagonal_pixels_are_joined():
    mask = np.zeros((4, 4), dtype=bool)
    mask[1, 1] = mask[2, 2] = True
    assert len(it.find_contours(mask)) == 1


def test_trace_filled_square_gives_four_corners():
    ink = np.zeros((100, 100), dtype=bool)
    ink[20:80, 30:70] = True
    shapes = it.trace_image(rgba_from_ink(ink), mode="FILLED", gap=0, simplify=1.0)
    assert len(shapes) == 1
    outer = shapes[0].outer
    assert len(outer) == 4
    assert it.polygon_area(outer) > 0
    u0, v0, u1, v1 = bbox(outer)
    # Boundary midpoints sit half a pixel inside the inked area.
    assert u0 == pytest.approx(0.30, abs=0.011) and u1 == pytest.approx(0.70, abs=0.011)
    assert v0 == pytest.approx(0.20, abs=0.011) and v1 == pytest.approx(0.80, abs=0.011)


def test_silhouette_of_outline_fills_inside():
    shapes = it.trace_image(rgba_from_ink(square_outline()), mode="SILHOUETTE", gap=0)
    assert len(shapes) == 1
    assert not shapes[0].holes
    assert len(shapes[0].outer) == 4


def test_filled_keeps_holes_and_can_drop_them():
    ink = square_outline(width=6)
    shapes = it.trace_image(rgba_from_ink(ink), mode="FILLED", gap=0)
    assert len(shapes) == 1 and len(shapes[0].holes) == 1
    shapes = it.trace_image(rgba_from_ink(ink), mode="FILLED", gap=0, keep_holes=False)
    assert len(shapes) == 1 and not shapes[0].holes


def test_regions_split_by_line():
    ink = square_outline()
    ink[20:80, 49:52] = True       # vertical divider
    shapes = it.trace_image(rgba_from_ink(ink), mode="REGIONS", gap=0)
    assert len(shapes) == 2
    for shape in shapes:
        assert len(shape.outer) == 4


def test_gap_closing_makes_silhouette_watertight():
    ink = square_outline()
    ink[48:51, 20:23] = False      # 3 px opening in the left side
    leaky = it.trace_image(rgba_from_ink(ink), mode="SILHOUETTE", gap=0)
    # Without closing, the inside leaks: only the thin outline remains.
    assert it.polygon_area(leaky[0].outer) < 0.2
    closed = it.trace_image(rgba_from_ink(ink), mode="SILHOUETTE", gap=2)
    assert it.polygon_area(closed[0].outer) == pytest.approx(0.36, abs=0.02)


def test_min_area_drops_specks():
    ink = np.zeros((100, 100), dtype=bool)
    ink[20:80, 20:80] = True
    ink[5:7, 5:7] = True
    assert len(it.trace_image(rgba_from_ink(ink), mode="FILLED", gap=0, min_area=0.001)) == 1
    assert len(it.trace_image(rgba_from_ink(ink), mode="FILLED", gap=0, min_area=0.0)) == 2


def test_straighten_snaps_near_axis_edges():
    poly = np.array([[0.0, 0.0], [10.0, 0.3], [10.2, 8.0], [0.1, 8.4]])
    out = it.straighten(poly, 5.0)
    assert len(out) == 4
    ys = sorted(set(np.round(out[:, 1], 9)))
    xs = sorted(set(np.round(out[:, 0], 9)))
    assert len(ys) == 2 and len(xs) == 2


def test_straighten_leaves_diagonals():
    tri = np.array([[0.0, 0.0], [10.0, 0.0], [5.0, 8.0]])
    out = it.straighten(tri, 5.0)
    assert np.allclose(out, tri)


def test_simplify_keeps_circle_round():
    yy, xx = np.mgrid[0:200, 0:200]
    ink = (xx - 100) ** 2 + (yy - 100) ** 2 < 70 ** 2
    shapes = it.trace_image(rgba_from_ink(ink), mode="FILLED", gap=0, simplify=0.75)
    outer = shapes[0].outer
    assert 16 <= len(outer) <= 200
    radii = np.hypot(outer[:, 0] - 0.5025, outer[:, 1] - 0.5025)
    assert radii.min() > 0.33 and radii.max() < 0.36


def test_point_in_polygon():
    square = np.array([[0, 0], [1, 0], [1, 1], [0, 1]], dtype=float)
    assert it.point_in_polygon((0.5, 0.5), square)
    assert not it.point_in_polygon((1.5, 0.5), square)


def test_group_holes_nested_island():
    outer = np.array([[0, 0], [10, 0], [10, 10], [0, 10]], dtype=float)
    hole = outer[::-1] * 0.6 + 2          # clockwise, inside outer
    island = np.array([[4.5, 4.5], [5.5, 4.5], [5.5, 5.5], [4.5, 5.5]])
    shapes = it.group_holes([outer, hole, island])
    assert len(shapes) == 2
    big = max(shapes, key=lambda s: it.polygon_area(s.outer))
    small = min(shapes, key=lambda s: it.polygon_area(s.outer))
    assert len(big.holes) == 1 and not small.holes


def test_remove_thin_drops_overshooting_lines():
    ink = square_outline()
    ink[20:23, 5:20] = True        # construction line overshooting the top-left corner
    ink[5:20, 77:80] = True        # and another one at the bottom-right
    raw = it.trace_image(rgba_from_ink(ink), mode="SILHOUETTE", gap=0, thin=0)
    clean = it.trace_image(rgba_from_ink(ink), mode="SILHOUETTE", gap=0, thin=2)
    assert len(raw[0].outer) > 4
    assert len(clean[0].outer) == 4
    u0, v0, u1, v1 = bbox(clean[0].outer)
    assert (u0, v0, u1, v1) == (pytest.approx(0.2, abs=0.011), pytest.approx(0.2, abs=0.011),
                                pytest.approx(0.8, abs=0.011), pytest.approx(0.8, abs=0.011))


def test_remove_thin_keeps_right_angles():
    mask = np.zeros((60, 60), dtype=bool)
    mask[10:50, 10:50] = True
    assert np.array_equal(it.remove_thin(mask, 3), mask)
