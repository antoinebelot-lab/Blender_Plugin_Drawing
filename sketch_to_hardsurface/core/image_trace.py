# SPDX-License-Identifier: GPL-3.0-or-later
"""Vectorise a sketch image into clean polygons (pure numpy, no ``bpy``).

Conventions
-----------
* Images are float arrays of shape ``(H, W, 4)`` (RGBA in ``[0, 1]``) or
  boolean masks of shape ``(H, W)``. Row 0 is the *bottom* row, which is the
  pixel order Blender uses for ``Image.pixels``.
* Returned polygons are ``(N, 2)`` float arrays in normalised UV space:
  ``u`` goes right and ``v`` goes up, both in ``[0, 1]`` over the image.
* Outer boundaries are counter-clockwise (positive area), holes clockwise.

This module is deliberately free of Blender imports so it can be unit tested
with plain ``pytest``.
"""

import math

import numpy as np

SOURCES = ("DARK", "LIGHT", "ALPHA")
MODES = ("SILHOUETTE", "FILLED", "REGIONS")

_LUMA = np.array((0.2126, 0.7152, 0.0722), dtype=np.float32)


# ---------------------------------------------------------------------------
# Pixels -> mask
# ---------------------------------------------------------------------------

def rgba_to_mask(rgba, source="DARK", threshold=0.5):
    """Return the boolean "ink" mask of an RGBA image.

    ``DARK``  ink is darker than ``threshold`` (pencil/marker on paper).
    ``LIGHT`` ink is lighter than ``threshold`` (chalk on a dark board).
    ``ALPHA`` ink is any pixel more opaque than ``threshold``.
    Transparent pixels count as paper in every mode.
    """
    rgba = np.asarray(rgba, dtype=np.float32)
    alpha = rgba[..., 3]
    if source == "ALPHA":
        return alpha > threshold
    luma = rgba[..., :3] @ _LUMA
    if source == "DARK":
        return (luma * alpha + (1.0 - alpha)) < threshold
    if source == "LIGHT":
        return (luma * alpha) > threshold
    raise ValueError("unknown source: %r" % (source,))


def downsample(rgba, max_size):
    """Box-filter ``rgba`` so that its largest side is at most ``max_size``.

    Returns ``(image, factor)``. Remainder rows/columns are cropped, which is
    at most ``factor - 1`` pixels and irrelevant for tracing.
    """
    h, w = rgba.shape[:2]
    factor = max(1, math.ceil(max(h, w) / float(max_size)))
    if factor == 1:
        return rgba, 1
    hh, ww = h // factor, w // factor
    trimmed = rgba[:hh * factor, :ww * factor]
    return trimmed.reshape(hh, factor, ww, factor, -1).mean(axis=(1, 3)), factor


# ---------------------------------------------------------------------------
# Morphology and flood fill
# ---------------------------------------------------------------------------

def _shift_or(mask, radius, axis):
    out = mask.copy()
    for s in range(1, radius + 1):
        if axis == 0:
            out[s:] |= mask[:-s]
            out[:-s] |= mask[s:]
        else:
            out[:, s:] |= mask[:, :-s]
            out[:, :-s] |= mask[:, s:]
    return out


def dilate(mask, radius):
    """Dilate with a square structuring element of half-size ``radius``."""
    if radius <= 0:
        return mask.copy()
    return _shift_or(_shift_or(mask, radius, 0), radius, 1)


def erode(mask, radius):
    """Erode with a square structuring element (outside counts as inside)."""
    if radius <= 0:
        return mask.copy()
    return ~dilate(~mask, radius)


def close_gaps(mask, radius):
    """Morphological closing: bridges gaps up to about ``2 * radius`` pixels."""
    if radius <= 0:
        return mask.copy()
    # Pad so that shapes touching the border are not glued to it by erosion.
    padded = np.pad(mask, radius, mode="constant", constant_values=False)
    closed = erode(dilate(padded, radius), radius)
    return closed[radius:-radius, radius:-radius]


def remove_thin(mask, radius):
    """Morphological opening: removes parts narrower than ``2 * radius + 1``.

    Gets rid of construction lines overshooting the corners of a sketch while
    keeping straight edges and right angles intact (square element).
    """
    if radius <= 0:
        return mask.copy()
    padded = np.pad(mask, radius, mode="constant", constant_values=False)
    opened = dilate(erode(padded, radius), radius)
    return opened[radius:-radius, radius:-radius]


def _expand_runs(passable, seeds):
    """Grow ``seeds`` to every horizontal run of ``passable`` they touch."""
    h, w = passable.shape
    p = np.zeros((h, w + 1), dtype=bool)
    p[:, :w] = passable
    s = np.zeros((h, w + 1), dtype=bool)
    s[:, :w] = seeds & passable
    flat_p = p.ravel()
    starts = flat_p.copy()
    starts[1:] &= ~flat_p[:-1]
    ids = np.cumsum(starts)
    ids[~flat_p] = 0
    hit = np.bincount(ids, weights=s.ravel(), minlength=int(ids[-1]) + 1) > 0
    hit[0] = False
    return hit[ids].reshape(h, w + 1)[:, :w]


def flood_fill(passable, seeds):
    """4-connected flood fill of ``passable`` cells starting from ``seeds``.

    Alternates whole-row and whole-column sweeps, which converges in a handful
    of iterations for typical drawings (one per "turn" of the fill path).
    """
    reach = seeds & passable
    while True:
        grown = _expand_runs(passable, reach)
        grown = _expand_runs(passable.T, grown.T).T
        if np.array_equal(grown, reach):
            return grown
        reach = grown


def border_seeds(shape):
    seeds = np.zeros(shape, dtype=bool)
    seeds[0, :] = seeds[-1, :] = True
    seeds[:, 0] = seeds[:, -1] = True
    return seeds


def solid_mask(ink, mode="SILHOUETTE"):
    """Turn an ink mask into the mask of the solid area to extrude.

    ``SILHOUETTE`` outer shape of the drawing, every enclosed area filled.
    ``FILLED``     the ink itself, holes kept (silhouettes, solid fills).
    ``REGIONS``    the areas enclosed by lines (one region per panel/part).
    """
    if mode == "FILLED":
        return ink.copy()
    outside = flood_fill(~ink, border_seeds(ink.shape))
    if mode == "SILHOUETTE":
        return ~outside
    if mode == "REGIONS":
        return ~ink & ~outside
    raise ValueError("unknown mode: %r" % (mode,))


# ---------------------------------------------------------------------------
# Contours (oriented marching squares)
# ---------------------------------------------------------------------------

# Cell corners: a=(x, y) b=(x+1, y) c=(x+1, y+1) d=(x, y+1), case = a|b<<1|c<<2|d<<3.
# Edge midpoints: 0 bottom, 1 right, 2 top, 3 left. Each segment is oriented
# so that the inside is on its left; saddles keep the inside connected
# (8-connectivity for ink, 4-connectivity for the background flood fill).
_SEGMENTS = {
    1: ((0, 3),), 2: ((1, 0),), 3: ((1, 3),), 4: ((2, 1),),
    5: ((0, 1), (2, 3)), 6: ((2, 0),), 7: ((2, 3),), 8: ((3, 2),),
    9: ((0, 2),), 10: ((1, 2), (3, 0)), 11: ((1, 2),), 12: ((3, 1),),
    13: ((0, 1),), 14: ((3, 0),),
}
# Doubled-integer offsets of each edge midpoint from (2x, 2y).
_EDGE_OFFSET = ((1, 0), (2, 1), (1, 2), (0, 1))


def find_contours(mask):
    """Return the closed boundaries of ``mask`` as lists of lattice points.

    Points are ``(x, y)`` float pairs in pixel units, pixel ``(i, j)`` having
    its centre at ``(j, i)``. Loops are not repeated at the end.
    """
    h, w = mask.shape
    grid = np.zeros((h + 2, w + 2), dtype=np.uint8)
    grid[1:-1, 1:-1] = mask
    case = (grid[:-1, :-1] | (grid[:-1, 1:] << 1)
            | (grid[1:, 1:] << 2) | (grid[1:, :-1] << 3))

    stride = 2 * (h + 2) + 4
    starts, ends = [], []
    for value, segments in _SEGMENTS.items():
        ys, xs = np.nonzero(case == value)
        if not len(xs):
            continue
        for e_from, e_to in segments:
            fx, fy = _EDGE_OFFSET[e_from]
            tx, ty = _EDGE_OFFSET[e_to]
            starts.append((2 * xs + fx) * stride + (2 * ys + fy))
            ends.append((2 * xs + tx) * stride + (2 * ys + ty))
    if not starts:
        return []

    following = dict(zip(np.concatenate(starts).tolist(), np.concatenate(ends).tolist()))
    loops = []
    while following:
        first, key = following.popitem()
        loop = [first]
        while key != first:
            loop.append(key)
            key = following.pop(key)
        arr = np.asarray(loop, dtype=np.int64)
        # Back to pixel units, removing the 1-pixel padding.
        pts = np.stack((arr // stride, arr % stride), axis=1).astype(np.float64) * 0.5 - 1.0
        loops.append(pts)
    return loops


# ---------------------------------------------------------------------------
# Polygon utilities
# ---------------------------------------------------------------------------

def polygon_area(pts):
    """Signed area (shoelace): positive for counter-clockwise polygons."""
    x, y = pts[:, 0], pts[:, 1]
    return 0.5 * float(np.dot(x, np.roll(y, -1)) - np.dot(np.roll(x, -1), y))


def point_in_polygon(point, pts):
    """Even-odd ray casting test."""
    x, y = point
    xs, ys = pts[:, 0], pts[:, 1]
    xs2, ys2 = np.roll(xs, -1), np.roll(ys, -1)
    crosses = (ys > y) != (ys2 > y)
    with np.errstate(divide="ignore", invalid="ignore"):
        x_at = xs + (y - ys) * (xs2 - xs) / (ys2 - ys)
    return bool(np.count_nonzero(crosses & (x < x_at)) % 2)


def _rdp_keep(pts, eps):
    """Douglas-Peucker on an open polyline, returns the boolean keep mask."""
    n = len(pts)
    keep = np.zeros(n, dtype=bool)
    keep[0] = keep[-1] = True
    stack = [(0, n - 1)]
    while stack:
        i, j = stack.pop()
        if j <= i + 1:
            continue
        a, b = pts[i], pts[j]
        seg = b - a
        inner = pts[i + 1:j]
        length = math.hypot(seg[0], seg[1])
        if length < 1e-12:
            dist = np.hypot(inner[:, 0] - a[0], inner[:, 1] - a[1])
        else:
            dist = np.abs(seg[0] * (inner[:, 1] - a[1]) - seg[1] * (inner[:, 0] - a[0])) / length
        k = int(np.argmax(dist))
        if dist[k] > eps:
            m = i + 1 + k
            keep[m] = True
            stack.append((i, m))
            stack.append((m, j))
    return keep


def drop_collinear(pts, eps):
    """Remove vertices closer than ``eps`` to the line through their neighbours."""
    pts = np.asarray(pts, dtype=np.float64)
    changed = True
    while changed and len(pts) > 3:
        changed = False
        prev, nxt = np.roll(pts, 1, axis=0), np.roll(pts, -1, axis=0)
        seg = nxt - prev
        length = np.hypot(seg[:, 0], seg[:, 1])
        cross = np.abs(seg[:, 0] * (pts[:, 1] - prev[:, 1]) - seg[:, 1] * (pts[:, 0] - prev[:, 0]))
        dist = np.where(length > 1e-12, cross / np.maximum(length, 1e-12),
                        np.hypot(pts[:, 0] - prev[:, 0], pts[:, 1] - prev[:, 1]))
        k = int(np.argmin(dist))
        if dist[k] <= eps:
            pts = np.delete(pts, k, axis=0)
            changed = True
    return pts


def simplify_closed(pts, eps):
    """Douglas-Peucker for a closed loop, anchored on two extreme points."""
    n = len(pts)
    if n < 4 or eps <= 0:
        return pts.copy()
    i0 = int(np.argmin(pts[:, 0] + pts[:, 1]))
    pts = np.roll(pts, -i0, axis=0)
    i1 = int(np.argmax(np.hypot(pts[:, 0] - pts[0, 0], pts[:, 1] - pts[0, 1])))
    first = pts[:i1 + 1]
    second = np.vstack((pts[i1:], pts[:1]))
    out = np.vstack((first[_rdp_keep(first, eps)][:-1], second[_rdp_keep(second, eps)][:-1]))
    return drop_collinear(out, eps * 0.5)


def straighten(pts, angle_deg):
    """Snap nearly horizontal/vertical edges to exact axis-aligned lines.

    Consecutive near-horizontal edges share one ``y`` (their length-weighted
    mean), near-vertical ones share one ``x``. Corners between a horizontal
    and a vertical run therefore become exact right angles, which is what
    hard-surface profiles usually intend.
    """
    if angle_deg <= 0 or len(pts) < 3:
        return pts.copy()
    pts = np.asarray(pts, dtype=np.float64).copy()
    n = len(pts)
    tol = math.tan(math.radians(angle_deg))
    delta = np.roll(pts, -1, axis=0) - pts
    lengths = np.hypot(delta[:, 0], delta[:, 1])
    flags = (np.abs(delta[:, 1]) <= tol * np.abs(delta[:, 0]),   # horizontal -> fix y
             np.abs(delta[:, 0]) <= tol * np.abs(delta[:, 1]))   # vertical -> fix x
    for coord, flagged in ((1, flags[0]), (0, flags[1])):
        if flagged.all() or not flagged.any():
            continue
        # Start right after an unflagged edge so runs do not wrap around.
        start = (int(np.flatnonzero(~flagged)[0]) + 1) % n
        run = []
        for step in range(n + 1):
            e = (start + step) % n
            if step < n and flagged[e]:
                run.append(e)
                continue
            if run:
                weights = lengths[run]
                mids = 0.5 * (pts[run, coord] + pts[[(i + 1) % n for i in run], coord])
                value = float(np.dot(weights, mids) / max(weights.sum(), 1e-12))
                for i in run:
                    pts[i, coord] = value
                    pts[(i + 1) % n, coord] = value
                run = []
    return drop_collinear(pts, 1e-9)


# ---------------------------------------------------------------------------
# High level API
# ---------------------------------------------------------------------------

class Shape:
    """One fillable area: an outer loop and the holes it contains (UV space)."""

    __slots__ = ("outer", "holes")

    def __init__(self, outer, holes=None):
        self.outer = outer
        self.holes = holes or []

    def __repr__(self):
        return "Shape(%d verts, %d holes)" % (len(self.outer), len(self.holes))


def group_holes(loops):
    """Split oriented loops into :class:`Shape` objects (outer + its holes)."""
    outers = [p for p in loops if polygon_area(p) > 0]
    holes = [p for p in loops if polygon_area(p) < 0]
    outers.sort(key=polygon_area)  # smallest first: innermost container wins
    shapes = [Shape(p) for p in outers]
    for hole in holes:
        probe = hole.mean(axis=0) if len(hole) < 3 else hole[0]
        for shape in shapes:
            if point_in_polygon(probe, shape.outer):
                shape.holes.append(hole)
                break
    shapes.sort(key=lambda s: -polygon_area(s.outer))
    return shapes


def trace_mask(mask, *, simplify=1.0, min_area=0.0, straighten_deg=0.0, keep_holes=True):
    """Vectorise a solid mask into :class:`Shape` objects in UV space.

    ``simplify``  Douglas-Peucker tolerance in pixels of ``mask``.
    ``min_area``  loops smaller than this fraction of the image are dropped.
    """
    h, w = mask.shape
    min_px = float(min_area) * w * h
    loops = []
    for pts in find_contours(mask):
        if abs(polygon_area(pts)) < max(min_px, 1.0):
            continue
        if simplify > 0:
            pts = simplify_closed(pts, simplify)
        if straighten_deg > 0:
            pts = straighten(pts, straighten_deg)
        if len(pts) < 3 or abs(polygon_area(pts)) < max(min_px, 1.0):
            continue
        if not keep_holes and polygon_area(pts) < 0:
            continue
        # Pixel centres -> UV.
        uv = np.empty_like(pts)
        uv[:, 0] = (pts[:, 0] + 0.5) / w
        uv[:, 1] = (pts[:, 1] + 0.5) / h
        loops.append(uv)
    return group_holes(loops)


def trace_image(rgba, *, source="DARK", threshold=0.5, mode="SILHOUETTE",
                max_size=1024, gap=2, thin=0, simplify=1.0, min_area=0.0005,
                straighten_deg=0.0, keep_holes=True):
    """Full pipeline: RGBA pixels -> list of :class:`Shape` in UV space.

    ``gap``  closing radius applied to the ink (joins broken lines).
    ``thin`` opening radius applied to the solid (removes overshooting lines).
    """
    rgba = np.asarray(rgba, dtype=np.float32)
    if rgba.ndim != 3 or rgba.shape[2] != 4:
        raise ValueError("expected an (H, W, 4) RGBA array")
    small, _factor = downsample(rgba, max_size)
    ink = rgba_to_mask(small, source, threshold)
    if gap > 0:
        ink = close_gaps(ink, int(gap))
    solid = solid_mask(ink, mode)
    if thin > 0:
        solid = remove_thin(solid, int(thin))
    return trace_mask(solid, simplify=simplify, min_area=min_area,
                      straighten_deg=straighten_deg, keep_holes=keep_holes)
