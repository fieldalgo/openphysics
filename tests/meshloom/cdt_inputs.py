# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Synthetic closed triangle surfaces for the boundary-recovery (CDT) readiness set.

Not a test module. Each input is a closed triangle surface with STL-like coordinates
(float32 values widened to float64) and one facet per triangle, as the C14 loader's
canonical arrays would give. Inputs are seeded and deterministic, and are built only
from the category definitions below; no C14 file or result was used to choose them.

The base shape is a terrain block: a top surface that is the graph of a height over a
triangulated rectangle, a flat bottom with the same triangulation at z = 0, and four
vertical walls. Rows of the triangulation are x-monotone polylines, and each strip
between two rows is zipped into triangles, so the surface is an embedding whenever every
top triangle has positive orientation in the xy plane and every height is positive;
``build`` checks both (exactly where the float64 filter is unsure) and fails otherwise.

Categories (each also sets the share of the other features):

- ``coplanar``: terraces of exactly equal height, so many coplanar neighbours; the
  bottom and the walls are coplanar runs too.
- ``nearflat``: heights with noise of slope up to tan(0.1 degree) per cell, so
  dihedral angles between neighbours from 179.9 to 180 degrees (some exactly 180).
- ``needle``: thin columns (width down to 1e-4 of a cell) give in-plane angles down to
  about 0.01 degree; thin rows with staggered vertices give caps (an angle near 180).
- ``fan``: a terrain and a separate cylinder of ``k`` sides with fan caps, apex angles
  360/k degrees (0.01 degree at k = 36000).
- ``touch``: pits whose lowest vertex lies a gap g above the bottom vertex below it,
  and a box whose face is g away from a wall, with g log-uniform down to 1e-6 of the
  bounding-box diagonal.
- ``mixed``: all of the above at once.

``python tests/meshloom/cdt_inputs.py --out DIR`` writes the readiness set as binary STL
files and a manifest with each file's SHA-256 and measured features.
"""

import argparse
import hashlib
import json
import math
from fractions import Fraction
from pathlib import Path
import struct

import numpy as np

CATEGORIES = ("coplanar", "nearflat", "needle", "fan", "touch", "mixed")
#: face counts of the readiness set (the task's range: 1e5 to 2e6)
SIZES = (100_000, 300_000, 1_000_000, 2_000_000)
GAP_MIN = 1e-6  # smallest near-touching gap, over the bounding-box diagonal
ANGLE_MIN_DEG = 0.01  # smallest in-plane angle targeted by needles and fans
DIHEDRAL_DEV_DEG = 0.1  # largest deviation from 180 degrees in near-flat regions


def f32(x):
    """Round to float32 and widen back to float64, as a binary STL would."""
    return np.asarray(x, dtype=np.float64).astype(np.float32).astype(np.float64)


def _orient2d_signs(a, b, c):
    """Exact signs of orient2d for rows of float64 points a, b, c (n x 2)."""
    det = (b[:, 0] - a[:, 0]) * (c[:, 1] - a[:, 1]) - (b[:, 1] - a[:, 1]) * (c[:, 0] - a[:, 0])
    mag = (np.abs(b[:, 0] - a[:, 0]) * np.abs(c[:, 1] - a[:, 1])
           + np.abs(b[:, 1] - a[:, 1]) * np.abs(c[:, 0] - a[:, 0]))
    sign = np.sign(det)
    unsure = np.abs(det) <= 1e-14 * mag  # far above the filter's true error bound
    for i in np.flatnonzero(unsure):
        fa, fb, fc = ([Fraction(float(v)) for v in p[i]] for p in (a, b, c))
        d = (fb[0] - fa[0]) * (fc[1] - fa[1]) - (fb[1] - fa[1]) * (fc[0] - fa[0])
        sign[i] = (d > 0) - (d < 0)
    return sign


def _widths(n, rng, thin_share, thin_min):
    """n cell widths summing to 1: most about 1, a share thin (log-uniform down to thin_min)."""
    w = np.ones(n)
    k = int(round(thin_share * n))
    if k:
        idx = rng.choice(np.arange(1, n - 1), size=min(k, max(n - 2, 0)), replace=False)
        w[idx] = 10.0 ** rng.uniform(math.log10(thin_min), 0.0, size=len(idx))
    return w / w.sum()


def _rows(nx, ny, rng, opt, span):
    """Row polylines: (ny+1) rows of nx+1 (x, y) points, x-monotone, rows not crossing."""
    ax, ay = span
    cw = _widths(nx, rng, opt["thin_cols"], opt["thin_min"]) * ax
    rh = _widths(ny, rng, opt["thin_rows"], opt["thin_min"]) * ay
    xs = np.concatenate([[0.0], np.cumsum(cw)])
    xs[-1] = ax
    ys = np.concatenate([[0.0], np.cumsum(rh)])
    ys[-1] = ay
    X = np.tile(xs, (ny + 1, 1))
    Y = np.tile(ys[:, None], (1, nx + 1))
    j = opt["jitter"]
    if j:
        # interior points move by up to j of their smaller neighbouring cell
        lx = np.minimum(cw[:-1], cw[1:])
        ly = np.minimum(rh[:-1], rh[1:])
        X[:, 1:-1] += rng.uniform(-j, j, size=(ny + 1, nx - 1)) * lx
        Y[1:-1, :] += rng.uniform(-j, j, size=(ny - 1, nx + 1)) * ly[:, None]
    if opt["stagger"]:
        # thin rows: shift every point of the upper row by half its cell, so the strip's
        # triangles have an apex near the middle of the opposite edge (caps)
        thin = np.flatnonzero(rh < 0.01 * ay / ny)
        for r in thin:
            if 0 < r + 1 < ny:
                X[r + 1, 1:-1] = 0.5 * (xs[1:-1] + xs[2:]) if nx > 1 else X[r + 1, 1:-1]
    return f32(X), f32(Y)


def _zip(lo, hi, X):
    """Triangles of the strip between row index lists lo and hi (x-monotone), merged by x."""
    tris = []
    i = k = 0
    n = len(lo) - 1
    xl, xh = X[0], X[1]
    while i < n or k < n:
        if k == n or (i < n and xl[i + 1] <= xh[k + 1]):
            tris.append((lo[i], lo[i + 1], hi[k]))
            i += 1
        else:
            tris.append((lo[i], hi[k + 1], hi[k]))
            k += 1
    return tris


def _heights(x, y, rng, opt, cell):
    z = 0.2 + 0.05 * np.sin(5.1 * x + 0.7) * np.cos(3.3 * y - 0.4)
    if opt["terraces"]:
        # exactly equal heights inside each terrace: many coplanar neighbours
        t = np.floor(8.0 * (0.5 + 0.5 * np.sin(2.3 * x) * np.sin(1.9 * y + 0.3)))
        z = 0.15 + 0.02 * t
    if opt["nearflat"]:
        # slope noise up to tan(0.1 deg) per cell over flat patches, some exactly flat
        base = 0.15 + 0.02 * np.floor(4.0 * (0.5 + 0.5 * np.sin(1.7 * x + 0.2)))
        noise = rng.uniform(-1.0, 1.0, size=x.shape) * math.tan(math.radians(DIHEDRAL_DEV_DEG)) * cell * 0.5
        noise[rng.random(x.shape) < 0.3] = 0.0
        z = base + noise
    return z


def _pits(z, X, Y, rng, opt, diag):
    """Lower some interior top points to a gap g above the bottom (z = 0)."""
    gaps = []
    if not opt["pits"]:
        return z, gaps
    ny1, nx1 = z.shape
    for _ in range(opt["pits"]):
        r, c = int(rng.integers(1, ny1 - 1)), int(rng.integers(1, nx1 - 1))
        g = float(f32(diag * 10.0 ** rng.uniform(math.log10(GAP_MIN), -3.0)))
        z[r, c] = g
        gaps.append(g)
    return z, gaps


def _terrain(nx, ny, rng, opt, offset):
    span = (1.0, 1.0)
    X, Y = _rows(nx, ny, rng, opt, span)
    cell = 1.0 / max(nx, ny)
    z = f32(_heights(X, Y, rng, opt, cell))
    diag = math.sqrt(1.0 + 1.0 + 0.3 ** 2)
    z, gaps = _pits(z, X, Y, rng, opt, diag)
    n = (nx + 1) * (ny + 1)
    top = np.stack([X.ravel(), Y.ravel(), z.ravel()], axis=1)
    bot = np.stack([X.ravel(), Y.ravel(), np.zeros(n)], axis=1)
    idx = np.arange(n).reshape(ny + 1, nx + 1)
    tri2d = []
    for r in range(ny):
        tri2d += _zip(idx[r], idx[r + 1], (X[r], X[r + 1]))
    tri2d = np.array(tri2d, dtype=np.int64)
    xy = top[:, :2]
    s = _orient2d_signs(xy[tri2d[:, 0]], xy[tri2d[:, 1]], xy[tri2d[:, 2]])
    if not (s > 0).all():
        raise ValueError(f"terrain: {int((s <= 0).sum())} triangles not positive in the plane")
    if not (z > 0).all():
        raise ValueError("terrain: a height is not positive")
    tris = [tri2d, tri2d[:, ::-1] + n]  # top (outward up) and bottom (outward down)
    # walls along the boundary loop, counter-clockwise seen from above
    loop = np.concatenate([idx[0, :-1], idx[:-1, -1], idx[-1, ::-1][:-1], idx[::-1, 0][:-1]])
    a, b = loop, np.roll(loop, -1)
    tris.append(np.stack([a, b, b + n], axis=1))
    tris.append(np.stack([a, b + n, a + n], axis=1))
    pts = np.concatenate([top, bot]) + np.asarray(offset, dtype=np.float64)
    return f32(pts), np.concatenate(tris), gaps


def _cylinder(k, center, radius, z0, z1):
    t = 2.0 * np.pi * np.arange(k) / k
    ring = np.stack([center[0] + radius * np.cos(t), center[1] + radius * np.sin(t)], axis=1)
    pts = np.concatenate([np.column_stack([ring, np.full(k, z0)]), np.column_stack([ring, np.full(k, z1)]),
                          [[center[0], center[1], z0], [center[0], center[1], z1]]])
    pts = f32(pts)
    i = np.arange(k)
    j = (i + 1) % k
    cb, ct = 2 * k, 2 * k + 1
    tris = np.concatenate([
        np.stack([np.full(k, cb), j, i], axis=1),  # bottom fan, outward down
        np.stack([np.full(k, ct), i + k, j + k], axis=1),  # top fan, outward up
        np.stack([i, j, j + k], axis=1), np.stack([i, j + k, i + k], axis=1),
    ])
    xy = pts[:, :2]
    s = _orient2d_signs(xy[np.full(k, ct)], xy[i + k], xy[j + k])
    if not (s > 0).all():
        raise ValueError("cylinder: a fan triangle is not positive in the plane")
    return pts, tris


def _box(lo, hi):
    lo, hi = f32(lo), f32(hi)
    c = np.array([[(hi if (v >> d) & 1 else lo)[d] for d in range(3)] for v in range(8)])
    q = [(0, 2, 3, 1), (4, 5, 7, 6), (0, 1, 5, 4), (2, 6, 7, 3), (0, 4, 6, 2), (1, 3, 7, 5)]
    return c, np.array([t for a, b, cc, d in q for t in ((a, b, cc), (a, cc, d))])


OPTIONS = {
    "coplanar": dict(terraces=True, nearflat=False, thin_cols=0.0, thin_rows=0.0, stagger=False, jitter=0.0,
                     pits=0, fan=0, box=False),
    "nearflat": dict(terraces=False, nearflat=True, thin_cols=0.0, thin_rows=0.0, stagger=False, jitter=0.2,
                     pits=0, fan=0, box=False),
    "needle": dict(terraces=False, nearflat=False, thin_cols=0.15, thin_rows=0.05, stagger=True, jitter=0.0,
                   pits=0, fan=0, box=False),
    "fan": dict(terraces=False, nearflat=False, thin_cols=0.0, thin_rows=0.0, stagger=False, jitter=0.2,
                pits=0, fan=36_000, box=False),
    "touch": dict(terraces=False, nearflat=False, thin_cols=0.0, thin_rows=0.0, stagger=False, jitter=0.2,
                  pits=64, fan=0, box=True),
    "mixed": dict(terraces=True, nearflat=False, thin_cols=0.05, thin_rows=0.02, stagger=True, jitter=0.0,
                  pits=32, fan=36_000, box=True),
}


def build(category, faces, seed=0, offset=(0.0, 0.0, 0.0)):
    """A closed surface of about ``faces`` triangles: (points n x 3 float64, triangles
    F x 3 int64, info). ``offset`` moves the terrain (and what is placed next to it)."""
    if category not in OPTIONS:
        raise ValueError(f"unknown category {category!r}")
    opt = dict(OPTIONS[category], thin_min=1e-4)
    rng = np.random.default_rng([seed, CATEGORIES.index(category), faces])
    k = opt["fan"]
    if k and 4 * k > faces // 2:
        k = max(360, faces // 8)  # keep the terrain at least half of the faces
    budget = faces - 4 * k - (12 if opt["box"] else 0)
    n = max(4, int(math.sqrt(budget / 4.0)))  # 4 n^2 + 8 n faces for an n x n terrain
    pts, tris, gaps = _terrain(n, n, rng, opt, offset)
    parts = [(pts, tris)]
    off = np.asarray(offset, dtype=np.float64)
    diag = math.sqrt(1.0 + 1.0 + 0.3 ** 2)
    if k:
        parts.append(_cylinder(k, off[:2] + (0.5, 1.6), 0.4, off[2] + 0.05, off[2] + 0.35))
    if opt["box"]:
        g = float(diag * GAP_MIN)
        x0 = float(f32(off[0] + 1.0))
        x1 = float(np.nextafter(np.float32(x0 + g), np.float32(np.inf)))
        parts.append(_box((x1, off[1] + 0.3, off[2] + 0.05), (x1 + 0.2, off[1] + 0.5, off[2] + 0.15)))
        gaps.append(x1 - x0)
    P, T, base = [], [], 0
    for p, t in parts:
        P.append(p)
        T.append(t + base)
        base += len(p)
    P, T = np.concatenate(P), np.concatenate(T)
    info = dict(category=category, seed=seed, faces=int(len(T)), points=int(len(P)), terrain_n=n, fan_k=k,
                gaps=sorted(gaps)[:4], offset=list(map(float, offset)))
    info.update(features(P, T))
    return P, T, info


def features(P, T):
    """Measured features: smallest and largest in-plane angle (degrees), largest edge
    ratio, and smallest gap is reported by ``build``."""
    a, b, c = P[T[:, 0]], P[T[:, 1]], P[T[:, 2]]
    e = [np.linalg.norm(b - c, axis=1), np.linalg.norm(c - a, axis=1), np.linalg.norm(a - b, axis=1)]
    area2 = np.linalg.norm(np.cross(b - a, c - a), axis=1)
    ang = []
    for u, v, w in ((a, b, c), (b, c, a), (c, a, b)):
        x, y = v - u, w - u
        ang.append(np.degrees(np.arctan2(np.linalg.norm(np.cross(x, y), axis=1), np.einsum("ij,ij->i", x, y))))
    ang = np.stack(ang)
    emax, emin = np.max(e, axis=0), np.min(e, axis=0)
    return dict(min_angle_deg=float(ang.min()), max_angle_deg=float(ang.max()),
                max_edge_ratio=float((emax / emin).max()), min_area2=float(area2.min()),
                angles_below_1deg=int((ang.min(axis=0) < 1.0).sum()))


def write_stl(path, P, T):
    """Binary STL (float32): the canonical arrays read back equal P and T's used points."""
    tri = P[T].astype(np.float32)
    rec = np.zeros(len(T), dtype=[("n", "<f4", 3), ("v", "<f4", (3, 3)), ("a", "<u2")])
    rec["v"] = tri
    with open(path, "wb") as f:
        f.write(b"meshloom cdt readiness input".ljust(80, b" "))
        f.write(struct.pack("<I", len(T)))
        f.write(rec.tobytes())


def readiness_set(sizes=SIZES, categories=CATEGORIES, seed=0):
    """(name, category, faces, seed) of the readiness set."""
    return [(f"{c}-{s // 1000}k-s{seed}", c, s, seed) for s in sizes for c in categories]


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--sizes", type=int, nargs="*", default=list(SIZES))
    ap.add_argument("--categories", nargs="*", default=list(CATEGORIES))
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    manifest = []
    for name, cat, size, seed in readiness_set(args.sizes, args.categories, args.seed):
        P, T, info = build(cat, size, seed)
        path = args.out / f"{name}.stl"
        write_stl(path, P, T)
        info.update(name=name, file=path.name, sha256=hashlib.sha256(path.read_bytes()).hexdigest())
        manifest.append(info)
        print(json.dumps(info))
    (args.out / "manifest.json").write_text(json.dumps(manifest, indent=1) + "\n")


if __name__ == "__main__":
    main()
