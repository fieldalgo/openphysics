# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""C10 adversarial inputs of the pre-registered 3D plan, meshed without refinement.

Every case goes through ``mesh_plc`` (boundary recovery, regions, rounding, flip repair,
certification) and is checked from the output arrays: V1 (exact orient3d > 0 on the
doubles), V2 (the output contract and the Euler characteristic of ball-like regions),
V3 (every exterior face lies in its facet's plane, the faces of each exterior facet tile
its area) and V4 (region volumes against the analytic volumes, relative 1e-12, exact
on axis-aligned inputs). V18 itself grades C10 at three refinement sizes; refinement
does not exist yet, so these are the boundary-recovery checks only.

Cases: the twisted (Schonhardt) prism, a cospherical cube with an interior vertex,
near-coplanar quadrilaterals (a 1e-9 fold), stacked layers, a 4^3 lattice of boxes,
5 and 30 degree wedges, a 1:100 slab, and the configurations the C14 validity rule makes
valid: an edge with four facets, two shells touching at a vertex, a box standing on a
larger box (a facet inside a coplanar facet), and two boxes on one larger box
(their shared edge inside its top facet).
"""

from fractions import Fraction as F
import math

import numpy as np
import pytest

meshloom = pytest.importorskip("meshloom")
if not meshloom.kernel_available():
    pytest.skip("meshloom's compiled kernel is not built in this environment", allow_module_level=True)

from meshloom._core import mesh_plc  # noqa: E402


class Builder:
    """Points deduplicated by exact coordinates; facets as lists of loops."""

    def __init__(self):
        self.points, self.index, self.facets = [], {}, []

    def p(self, q):
        q = tuple(float(x) for x in q)
        if q not in self.index:
            self.index[q] = len(self.points)
            self.points.append(q)
        return self.index[q]

    def facet(self, *loops):
        self.facets.append([[self.p(q) for q in loop] for loop in loops])

    def box(self, lo, hi, skip=()):
        (x0, y0, z0), (x1, y1, z1) = lo, hi
        faces = {
            "z0": [(x0, y0, z0), (x0, y1, z0), (x1, y1, z0), (x1, y0, z0)],
            "z1": [(x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)],
            "y0": [(x0, y0, z0), (x1, y0, z0), (x1, y0, z1), (x0, y0, z1)],
            "y1": [(x0, y1, z0), (x0, y1, z1), (x1, y1, z1), (x1, y1, z0)],
            "x0": [(x0, y0, z0), (x0, y0, z1), (x0, y1, z1), (x0, y1, z0)],
            "x1": [(x1, y0, z0), (x1, y1, z0), (x1, y1, z1), (x1, y0, z1)],
        }
        for name, loop in faces.items():
            if name not in skip:
                self.facet(loop)

    def arrays(self):
        return np.array(self.points, dtype=float), self.facets


def check(m, points, facets, volumes, exact):
    """V1-V4 from the arrays (Fraction), returns the sorted region volumes."""
    nodes, tets, regions = m["nodes"], m["tetrahedra"], m["regions"]
    q = [[F(x) for x in p] for p in nodes.tolist()]

    def det(a, b, c, d):
        u, v, w = ([q[x][i] - q[a][i] for i in range(3)] for x in (b, c, d))
        return u[0] * (v[1] * w[2] - v[2] * w[1]) - u[1] * (v[0] * w[2] - v[2] * w[0]) + \
            u[2] * (v[0] * w[1] - v[1] * w[0])

    vol = [det(*t) for t in tets.tolist()]
    assert all(v > 0 for v in vol), "V1"
    # V2: faces, boundary, interfaces, orphans, regions
    owners = {}
    for ti, v in enumerate(tets.tolist()):
        for i in range(4):
            owners.setdefault(tuple(sorted(v[:i] + v[i + 1:])), []).append((ti, v[i]))
    assert all(len(o) <= 2 for o in owners.values()), "V2 faces"
    exterior = {f for f, o in owners.items() if len(o) == 1}
    tagged = [f for faces in m["boundary_faces"].values() for f in faces.tolist()]
    assert sorted(tuple(sorted(f)) for f in tagged) == sorted(exterior), "V2 boundary"
    for f in tagged:
        (_, apex), = owners[tuple(sorted(f))]
        assert det(*f, apex) < 0, "V2 winding"
    assert sorted(np.unique(tets).tolist()) == list(range(len(nodes))), "V2 orphans"
    k = len(m["region_names"])
    assert set(regions.tolist()) == set(range(k)), "V2 regions"
    for (a, b), faces in m["interfaces"].items():
        for f in faces.tolist():
            sides = {int(regions[t]) for t, _ in owners[tuple(sorted(f))]}
            assert sides == {a, b}, "V2 interface"
    # V2 Euler characteristic per region (every region here is a ball)
    for r in range(k):
        ts = [t for t, rr in zip(tets.tolist(), regions.tolist()) if rr == r]
        V = len({x for t in ts for x in t})
        E = len({tuple(sorted((t[i], t[j]))) for t in ts for i in range(4) for j in range(i + 1, 4)})
        Fc = len({tuple(sorted(t[:i] + t[i + 1:])) for t in ts for i in range(4)})
        assert V - E + Fc - len(ts) == 1, f"V2 Euler, region {r}"
    # V3 on exterior facets: nodes in the plane, areas tile the facet
    P = [[F(x) for x in p] for p in np.asarray(points).tolist()]

    def cross(u, v):
        return [u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0]]

    def sub(a, b):
        return [x - y for x, y in zip(a, b)]

    for tag, faces in m["boundary_faces"].items():
        loop = facets[tag][0]
        o = P[loop[0]]
        n = [F(0)] * 3
        for a, b in zip(loop, loop[1:] + loop[:1]):
            n = [x + y for x, y in zip(n, cross(P[a], P[b]))]  # Newell normal of the outer loop
        for f in faces.tolist():
            for x in f:
                d = sum(ni * di for ni, di in zip(n, sub(q[x], o)))
                if exact:
                    assert d == 0, "V3(b) exactly 0"
                else:
                    nn = math.sqrt(float(sum(c * c for c in n)))
                    assert abs(float(d)) / nn <= 4 * 2.0 ** -52 * diag(points), "V3(b)"
        area_in = sum(abs(float(sum(ni * ci for ni, ci in zip(n, cross(sub(P[lp[1]], P[lp[0]]), sub(P[lp[2]], P[lp[0]]))))))
                      for lp in [loop[0:1] + loop[i:i + 2] for i in range(1, len(loop) - 1)])
        # the facet's area is covered by its exterior faces and, where another region
        # sits on it, by interface faces in its plane and within its bounding box
        lo = [min(P[i][c] for i in loop) for c in range(3)]
        hi = [max(P[i][c] for i in loop) for c in range(3)]
        cover = faces.tolist() + [
            f for fs in m["interfaces"].values() for f in fs.tolist()
            if all(sum(ni * di for ni, di in zip(n, sub(q[x], o))) == 0 and
                   all(lo[c] <= q[x][c] <= hi[c] for c in range(3)) for x in f)]
        area_out = sum(abs(float(sum(ni * ci for ni, ci in zip(n, cross(sub(q[f[1]], q[f[0]]), sub(q[f[2]], q[f[0]]))))))
                       for f in cover)
        assert abs(area_out - area_in) <= 1e-12 * area_in, f"V3(a) facet {tag}"
    # V4 region volumes
    got = sorted(float(sum(v for v, r in zip(vol, regions.tolist()) if r == i) / 6) for i in range(k))
    want = sorted(volumes)
    assert len(got) == len(want), (got, want)
    for g, w in zip(got, want):
        assert abs(g - w) <= 1e-12 * w, ("V4", g, w)
    return got


def diag(points):
    p = np.asarray(points)
    return float(np.linalg.norm(p.max(0) - p.min(0)))


# ---------------------------------------------------------------- the cases

def twisted_prism(twist_deg=30.0):
    b = Builder()
    bottom = [(math.cos(2 * math.pi * i / 3), math.sin(2 * math.pi * i / 3), 0.0) for i in range(3)]
    top = [(math.cos(2 * math.pi * i / 3 + math.radians(twist_deg)), math.sin(2 * math.pi * i / 3 + math.radians(twist_deg)), 1.0)
           for i in range(3)]
    b.facet(bottom[::-1])
    b.facet(top)
    for i in range(3):
        j = (i + 1) % 3
        # each side quad split along the "bad" diagonal: the Schonhardt configuration
        b.facet([bottom[i], bottom[j], top[i]])
        b.facet([bottom[j], top[j], top[i]])
    pts, facets = b.arrays()
    # volume of the twisted prism with these side triangles: exact via divergence theorem
    return pts, facets, None


def divergence_volume(points, facets):
    """Signed volume of a closed polyhedron from consistently wound outer loops."""
    P = [[F(x) for x in p] for p in np.asarray(points).tolist()]
    v = F(0)
    for loops in facets:
        lp = loops[0]
        for i in range(1, len(lp) - 1):
            a, b, c = P[lp[0]], P[lp[i]], P[lp[i + 1]]
            v += a[0] * (b[1] * c[2] - b[2] * c[1]) - a[1] * (b[0] * c[2] - b[2] * c[0]) + a[2] * (b[0] * c[1] - b[1] * c[0])
    return float(v / 6)


def cases():
    out = {}
    pts, facets, _ = twisted_prism()
    out["schonhardt"] = (pts, facets, [abs(divergence_volume(pts, facets))], False)

    b = Builder()
    b.box((-1, -1, -1), (1, 1, 1))
    pts, facets = b.arrays()
    pts = np.vstack([pts, [[0.0, 0.0, 0.0], [1e-3, 2e-3, -3e-3]]])  # interior vertices
    out["cospherical-cube-interior-vertex"] = (pts, facets, [8.0], True)

    b = Builder()  # a box whose top is two quads folded by 1e-9
    h = 1e-9
    b.facet([(0, 0, 0), (0, 2, 0), (2, 2, 0), (2, 0, 0)])
    b.facet([(0, 0, 1), (1, 0, 1 + h), (1, 2, 1 + h), (0, 2, 1)])
    b.facet([(1, 0, 1 + h), (2, 0, 1), (2, 2, 1), (1, 2, 1 + h)])
    b.facet([(0, 0, 0), (2, 0, 0), (2, 0, 1), (1, 0, 1 + h), (0, 0, 1)])
    b.facet([(0, 2, 0), (0, 2, 1), (1, 2, 1 + h), (2, 2, 1), (2, 2, 0)])
    b.facet([(0, 0, 0), (0, 0, 1), (0, 2, 1), (0, 2, 0)])
    b.facet([(2, 0, 0), (2, 2, 0), (2, 2, 1), (2, 0, 1)])
    pts, facets = b.arrays()
    out["near-coplanar-quads"] = (pts, facets, [abs(divergence_volume(pts, facets))], False)

    b = Builder()  # stacked layers of uneven thickness, one region each
    zs = [0.0, 0.5, 0.625, 1.0, 1.0625, 2.0, 2.03125, 3.0]
    for z0, z1 in zip(zs, zs[1:]):
        b.box((0, 0, z0), (4, 3, z1), skip=("z1",) if z1 != zs[-1] else ())
    pts, facets = b.arrays()
    out["stacked-layers"] = (pts, facets, [12 * (z1 - z0) for z0, z1 in zip(zs, zs[1:])], True)

    b = Builder()  # a 4^3 lattice of unit boxes, every box its own region
    for i in range(4):
        for j in range(4):
            for k in range(4):
                skip = tuple(n for n, c in (("x1", i < 3), ("y1", j < 3), ("z1", k < 3)) if c)
                b.box((i, j, k), (i + 1, j + 1, k + 1), skip=skip)
    pts, facets = b.arrays()
    out["box-lattice-4"] = (pts, facets, [1.0] * 64, True)

    for deg in (5, 30):
        b = Builder()  # a wedge: triangular prism with a deg-degree dihedral edge along y
        t = math.radians(deg)
        a0, a1, a2 = (0.0, 0.0), (1.0, 0.0), (math.cos(t), math.sin(t))
        lo = [(a0[0], 0.0, a0[1]), (a1[0], 0.0, a1[1]), (a2[0], 0.0, a2[1])]
        hi = [(x, 1.0, z) for x, _, z in lo]
        b.facet(lo)
        b.facet(hi[::-1])
        for i in range(3):
            j = (i + 1) % 3
            b.facet([lo[i], hi[i], hi[j], lo[j]])
        pts, facets = b.arrays()
        out[f"wedge-{deg}"] = (pts, facets, [abs(divergence_volume(pts, facets))], False)

    b = Builder()
    b.box((0, 0, 0), (100, 1, 1))
    pts, facets = b.arrays()
    out["slab-1-100"] = (pts, facets, [100.0], True)

    b = Builder()  # two boxes sharing one edge: an edge with four facets
    b.box((0, 0, 0), (1, 1, 1))
    b.box((1, 1, 0), (2, 2, 1))
    pts, facets = b.arrays()
    out["edge-with-four-facets"] = (pts, facets, [1.0, 1.0], True)

    b = Builder()  # two boxes touching at one vertex
    b.box((0, 0, 0), (1, 1, 1))
    b.box((1, 1, 1), (2, 2, 2))
    pts, facets = b.arrays()
    out["shells-touching-at-a-vertex"] = (pts, facets, [1.0, 1.0], True)

    b = Builder()  # a box standing on a larger box: its bottom inside the top facet
    b.box((0, 0, 0), (4, 4, 1))
    b.box((1, 1, 1), (2, 3, 2))
    pts, facets = b.arrays()
    out["box-on-a-larger-box"] = (pts, facets, [16.0, 2.0], True)

    b = Builder()  # two boxes side by side on a larger one: their shared edge in its top
    b.box((0, 0, 0), (4, 4, 1))
    b.box((1, 1, 1), (2, 3, 2))
    b.box((2, 1, 1), (3, 3, 2), skip=("x0",))
    pts, facets = b.arrays()
    out["edge-inside-a-facet"] = (pts, facets, [16.0, 2.0, 2.0], True)
    return out


CASES = cases()


@pytest.mark.parametrize("name", sorted(CASES))
def test_c10_case(name):
    pts, facets, volumes, exact = CASES[name]
    m = mesh_plc(pts, facets)
    check(m, pts, facets, volumes, exact)
