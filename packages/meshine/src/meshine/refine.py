# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Constrained Delaunay refinement (Ruppert's algorithm) on top of scipy's Delaunay.

The idea, in the order the code applies it every round:

1. Triangulate the current point set (unconstrained Delaunay, Qhull).
2. Every input segment must appear as an edge. A missing segment, or one whose
   diametral circle contains another vertex ("encroached"), is split at its
   midpoint (projected onto the true curve for circles).
3. Among triangles inside the domain, those with a too-small angle or a
   circumradius larger than the local target size are "bad". Their
   circumcenters are inserted — unless a circumcenter would encroach a
   segment, in which case that segment is split instead. This is the Ruppert
   rule that keeps the boundary from being crossed and gives the angle bound.
4. Repeat until nothing is bad.

Points are inserted in batches (with a separation filter so two new points do
not land in each other's circumcircle) and the whole set is re-triangulated
each round; that trades a little efficiency for a very small, robust code.

Refinement ends with a RuntimeError instead of running on when the built input or an
insertion would pass ``max_points`` (``MeshSizeLimitError``), after ``max_rounds`` rounds,
or as soon as Qhull leaves a boundary point out of the triangulation: a segment that ends
at such a point can never appear as an edge, however often it is split.

Small input angles
------------------
Ruppert's termination argument needs every input angle to be at least 60 degrees.
Two segments that meet at a smaller angle (``SHARP_CORNER``) form a sharp corner,
whether it opens into a region, into a hole or out of the domain. Plain refinement
does not finish two kinds of sharp corner:

* An acute corner opens into a region at less than ``min_angle``. The triangle in
  it always has the input angle and is always bad, and splitting it moves the
  problem closer to the apex.
* At a halving-incompatible corner, a vertex on one side encroaches the first piece
  of the other side once that piece is more than 1/cos(angle) times longer.
  Midpoint splits only halve pieces, so two sides whose length ratio is not within
  that band of a power of two split each other forever.

Trigger: an input vertex is treated when one of its sharp corners is acute or
halving-incompatible on its first pieces. A first piece is the input side, or, where
the side's far end is treated, the part up to the lattice vertex that end puts on
it (rule 1), so the test repeats until it treats no further vertex. Where the sides
are straight, plain refinement does not finish an input with a treated vertex (argued
above), and every other vertex takes none of the paths below, so an input that meshed
before gives the same mesh. A side on a ``Circle`` is the exception: each projected split
turns its first piece by up to pi/n toward the tangent, so the original rules can
finish a corner that is acute or incompatible on its input chord, and such an input
now gets a different (valid) mesh.

Rule 1, one halving lattice per treated vertex v. ``unit`` is the length of the
shortest side of a sharp corner at v. Before the first round, each such side gets
one vertex at ``unit * 2**k``, the largest below half its length. Later, a piece
that touches v (and no other treated vertex) is split at the ``unit * 2**k``
nearest its midpoint, a shell concentric with v, then projected onto its curve.
The first pieces at v stay equal, so neither encroaches the other.

Rule 2, at acute corners only. A triangle's angle at the apex is not tested when
the triangle lies inside the corner; its other angles and its size still are. A
triangle that is bad only by angle is left as it is when its circumcenter
encroaches a first piece of an acute corner and splitting that piece would put
vertices ``|piece| * sin(beta / 2)`` apart, closer than the triangle's own shortest
edge (Shewchuk's terminator; ``beta`` is the angle between the corner's current
first pieces, which turns when a side is curved). Refinement then ends through the
normal "nothing bad" exit.

Limits: the triangle in an acute corner keeps the input angle, and other
triangles below ``min_angle`` stay next to the apex (measured, not proved: at most
1.43 times the longest subsegment there, for two wedges of region sizes 0.01 and
0.5 at one apex). The terminator leaves skinny triangles in any
region, so beside a straight corner they can end a little below the input angle
(measured 13.02 degrees beside a 14-degree corner). Termination is measured, not
proved; an input the rules miss ends with one of the errors above.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from typing import NamedTuple

import numpy as np
from scipy.spatial import Delaunay, cKDTree

from .geometry import Domain, Region, Segment, points_in_loops
from .mesh import TriMesh

#: A triangle is degenerate when twice its signed area is below ``AREA_EPS`` times its
#: own longest edge squared — an area compared against an area built from the same
#: triangle, so the test is identical at every scale and wherever the triangle sits.
#: The form it replaces, ``1e-14 * max(1.0, max|P|**2)``, was absolute below unit scale:
#: measured on a 220 nm film written in metres, it called 24.7% of the triangles
#: degenerate, including near-equilateral ones with |2A| / h^2 = 0.33, and dropped them.
#: The named region came out with zero area and no exception was raised. For reference,
#: the smallest ratio any triangle reaches in this package's own test meshes is 2.2e-2,
#: ten orders of magnitude above this threshold.
AREA_EPS = 1e-12

#: Two segments that meet at a smaller angle than this form a sharp corner (see the module
#: docstring). From 60 degrees up, halving the longer of two first pieces always brings it
#: within 1/cos(angle) of the shorter one, so the plain rules finish such a corner.
SHARP_CORNER = math.radians(60.0)

#: Slack on the halving band of ``_halving_compatible``, in powers of two. The legs of a
#: right triangle put the length ratio exactly on the band edge, where the vertex sits on
#: the diametral circle and the strict encroachment test does not count it. Rounding must
#: not move such a corner out of the band: that would treat a corner that already meshes.
HALVING_SLACK = 1e-8


class MeshSizeLimitError(RuntimeError):
    """``generate`` refused to pass ``max_points``: the input domain as built already has
    more points, or an insertion would add more. A ``RuntimeError``, so a caller that catches
    ``RuntimeError`` still catches it; the message starts with ``more than <max_points> points``."""


class _Corner(NamedTuple):
    """A sharp corner at an input vertex: the gap of ``width`` radians that turns
    counter-clockwise from the side to vertex ``u`` (direction ``start``) to the side to ``w``."""
    start: float
    width: float
    u: int
    w: int
    inside: bool                            # opens into a region, not into a hole or outside


def generate(domain: Domain, boundary_names="outer", *, min_angle: float = 28.0,
             size_fn: Callable[[np.ndarray, np.ndarray], np.ndarray] | None = None,
             size_factor: float = 0.6, max_rounds: int = 80, max_points: int = 300_000,
             smooth: int = 2, verbose: bool = False) -> TriMesh:
    """Mesh a ``Domain``.

    Parameters
    ----------
    min_angle : quality bound in degrees (Ruppert guarantees termination below ~20.7;
                28-30 is a safe practical default for right-angled input). An input
                angle below it is kept in the one triangle that fills it.
    size_fn : optional callable h(x, y) -> target edge length, combined by minimum
              with the per-region sizes
    size_factor : a triangle is too big when circumradius > size_factor * h
                  (an equilateral triangle of edge h has circumradius 0.577 h)
    max_rounds : RuntimeError when refinement has not finished after this many rounds
    max_points : hard cap; MeshSizeLimitError (a RuntimeError) when the input domain as built
                 has more points, or before an insertion would pass it
    smooth : Laplacian smoothing sweeps of interior nodes after refinement
    """
    if min_angle >= 34:
        raise ValueError("min_angle above ~33 degrees cannot be guaranteed; use <= 33")
    pts, seg_list, regions = domain.build(boundary_names)
    if len(pts) > max_points:       # before the corner analysis, the lattice splits and Qhull
        raise MeshSizeLimitError(f"more than {max_points} points; the input domain has {len(pts)}")
    P = pts.copy()
    segs: dict[tuple[int, int], Segment] = {s.key: s for s in seg_list}
    sizes = np.array([r.size if r.size is not None else domain.default_size for r in regions])
    theta = np.radians(min_angle)
    on_segment = np.zeros(len(P), dtype=bool)
    for s in segs.values():
        on_segment[[s.a, s.b]] = True

    # small input angles (module docstring): acute, apex_piece and unit stay empty unless a vertex is treated
    corners = _sharp_corners(P, seg_list, regions)
    acute = {v: [c for c in cs if c.inside and c.width < theta] for v, cs in corners.items()}
    acute = {v: cs for v, cs in acute.items() if cs}
    apex_piece, unit = _treated_apices(P, corners, theta)    # piece key -> {treated apex: far end of its side}
    inserted: dict[tuple[int, int], int] = {}     # split segment -> its new vertex, not yet in the loops

    def add_points(new: np.ndarray, constrained: bool) -> list[int]:
        nonlocal P, on_segment
        if len(P) + len(new) > max_points:
            raise MeshSizeLimitError(f"more than {max_points} points; check sizes / min_angle")
        start = len(P)
        P = np.vstack([P, new])
        on_segment = np.concatenate([on_segment, np.full(len(new), constrained)])
        return list(range(start, len(P)))

    def split(batch: list[Segment], at: list[np.ndarray] | None = None) -> list[int]:
        """Split each segment of ``batch`` (all distinct) at its split point, or at the given
        point, projected onto its curve, with one insertion for the whole batch. The new
        vertices reach the region loops in ``update_loops``."""
        points = np.array([split_point(s) for s in batch] if at is None else at)
        for k, s in enumerate(batch):
            if s.curve is not None:
                points[k] = s.curve.project(points[k])
        new = add_points(points, True)
        for s, m in zip(batch, new):
            del segs[s.key]
            inserted[s.key] = m
            tags = apex_piece.pop(s.key, {})
            for a, b in ((s.a, m), (m, s.b)):
                child = Segment(a, b, s.curve, list(s.owners), s.name)
                segs[child.key] = child
                kept = {v: u for v, u in tags.items() if v in (a, b)}
                if kept:                            # a child keeps the apex tags it touches
                    apex_piece[child.key] = kept
        return new

    def split_point(seg: Segment) -> np.ndarray:
        tags = apex_piece.get(seg.key, {})
        if len(tags) == 1:                          # rule 1: the shell about the one treated apex
            (v,) = tags
            return _shell_point(P[v], P[seg.a + seg.b - v], unit[v])
        return 0.5 * (P[seg.a] + P[seg.b])

    def update_loops():
        """Put the vertices ``split`` added into the region loops, one pass per loop:
        inserting each vertex as it is made costs a scan of its loop per split."""
        def between(u: int, v: int) -> list[int]:
            m = inserted.get((min(u, v), max(u, v)))
            return [] if m is None else [*between(u, m), m, *between(m, v)]
        if inserted:
            for r in regions:
                r.loops = [[w for k, u in enumerate(lp) for w in (u, *between(u, lp[(k + 1) % len(lp)]))]
                           for lp in r.loops]
            inserted.clear()

    # rule 1 before the first round: one vertex on each treated side at its apex's lattice
    # point; a side treated at both ends gets two, the farthest from seg.a first, so the
    # second one splits the piece (seg.a, m) the first one left
    for key, tags in list(apex_piece.items()):
        seg = segs[key]
        points = [_lattice_point(P[v], P[u], unit[v]) for v, u in tags.items()]
        for point in sorted(points, key=lambda q: -np.linalg.norm(q - P[seg.a])):
            (m,) = split([seg], [point])
            seg = segs[(min(seg.a, m), max(seg.a, m))]

    tri = None
    for rnd in range(max_rounds):
        update_loops()
        tri = Delaunay(P)
        if len(tri.coplanar) and on_segment[tri.coplanar[:, 0]].any():
            _refuse_unresolved_points(P, tri.coplanar[on_segment[tri.coplanar[:, 0]]], domain)
        simp = tri.simplices.astype(np.int64)
        edges = _edge_keys(simp, len(P))

        # -- 2. segments: present and unencroached -------------------------------
        to_split: list[Segment] = []
        seg_arr = np.array([(s.a, s.b) for s in segs.values()], dtype=np.int64)
        seg_objs = list(segs.values())
        keys = np.minimum(seg_arr[:, 0], seg_arr[:, 1]) * len(P) + np.maximum(seg_arr[:, 0], seg_arr[:, 1])
        missing = ~np.isin(keys, edges)
        tree = cKDTree(P)
        mids = 0.5 * (P[seg_arr[:, 0]] + P[seg_arr[:, 1]])
        half = 0.5 * np.linalg.norm(P[seg_arr[:, 0]] - P[seg_arr[:, 1]], axis=1)
        near_all = tree.query_ball_point(mids, half * (1 - 1e-9))
        for i, s in enumerate(seg_objs):
            if missing[i] or any(j not in (s.a, s.b) for j in near_all[i]):
                to_split.append(s)
        if to_split:
            split(to_split)
            if verbose:
                print(f"round {rnd}: split {len(to_split)} segments, {len(P)} points")
            continue

        # -- 3. bad triangles ----------------------------------------------------
        region_id, _degenerate = _classify(P, simp, regions, keys)
        inside = region_id >= 0
        T = simp[inside]
        cc, R, angles, cent = _triangle_data(P, T)
        if acute:                                   # rule 2: the apex angle is not tested
            _excuse_acute_corners(P, T, angles, cent, acute)
        amin = angles.min(axis=1)
        h = sizes[region_id[inside]]
        if size_fn is not None:
            h = np.minimum(h, np.asarray(size_fn(cent[:, 0], cent[:, 1]), dtype=float))
        too_big = R > size_factor * h
        bad = (amin < theta) | too_big
        skinny = bad & ~too_big
        if acute and skinny.any():                  # rule 2: Shewchuk's terminator
            bad[skinny] = ~_terminated(P, T[skinny], cc[skinny], *_first_pieces(P, acute, apex_piece))
        if not bad.any():
            break
        cand, cand_R = cc[bad], R[bad]

        # circumcenters that encroach a segment -> split the segment instead
        seg_arr = np.array([(s.a, s.b) for s in segs.values()])
        seg_objs = list(segs.values())
        mids = 0.5 * (P[seg_arr[:, 0]] + P[seg_arr[:, 1]])
        half = 0.5 * np.linalg.norm(P[seg_arr[:, 0]] - P[seg_arr[:, 1]], axis=1)
        encroaches, seg_ids = _encroached(cand, mids, half)
        seg_to_split: set[int] = set(seg_ids.tolist())
        if seg_to_split:
            split([seg_objs[si] for si in seg_to_split])
        cand, cand_R = cand[~encroaches], cand_R[~encroaches]

        # drop circumcenters outside the domain, then enforce separation
        update_loops()
        if len(cand):
            keep = np.zeros(len(cand), dtype=bool)
            for r in regions:
                keep |= points_in_loops(cand, [P[np.array(lp)] for lp in r.loops])
            cand, cand_R = cand[keep], cand_R[keep]
        if len(cand):
            accepted = _separate(cand, cand_R)
            add_points(cand[accepted], False)
        if verbose:
            print(f"round {rnd}: {bad.sum()} bad, inserted {int(len(cand) and accepted.sum())}, "
                  f"split {len(seg_to_split)} segments, {len(P)} points")
    else:
        raise RuntimeError(f"refinement did not converge in {max_rounds} rounds")

    update_loops()
    tri = Delaunay(P)
    simp = tri.simplices.astype(np.int64)
    seg_arr = np.array([(s.a, s.b) for s in segs.values()], dtype=np.int64)
    keys = np.minimum(seg_arr[:, 0], seg_arr[:, 1]) * len(P) + np.maximum(seg_arr[:, 0], seg_arr[:, 1])
    region_id, degenerate = _classify(P, simp, regions, keys)
    T = simp[region_id >= 0]
    rid = region_id[region_id >= 0]
    if len(T) == 0:
        _refuse_empty_mesh(P, simp, degenerate, domain, regions)
    T = _orient_ccw(P, T)

    mesh = _assemble(P, T, rid, regions, segs, on_segment)
    if smooth > 0:
        _laplacian_smooth(mesh, on_segment[_used_nodes(P, T)], sweeps=smooth, min_angle_deg=min_angle)
    return mesh


# ---------------------------------------------------------------------------

def _refuse_empty_mesh(P: np.ndarray, simp: np.ndarray, degenerate: np.ndarray,
                       domain: Domain, regions: list[Region]) -> None:
    """Refuse an empty mesh here, where the reason for it is still known.

    An empty mesh is a valid data structure and never a valid mesh, so no caller is
    written to check for one and the failure surfaces several frames away as a shape
    error out of a numeric library. This stage can separate two causes that need
    different fixes, and it is the only place that still holds the numbers to do it.
    """
    n_deg = int(degenerate.sum())
    if n_deg == len(simp):
        raise ValueError(
            f"meshine.generate produced 0 triangles and 0 nodes: all {len(simp)} triangles of "
            f"the final triangulation are degenerate. The {len(P)} mesh points span "
            f"{domain.extent():g} units, and at that extent they are collapsed onto a line or "
            f"a single point. This is a geometry problem, not a mesh-size one; check the "
            f"region coordinates and the unit they are written in.")
    raise ValueError(
        f"meshine.generate produced 0 triangles and 0 nodes: of {len(simp)} triangles, "
        f"{n_deg} are degenerate and none of the remaining {len(simp) - n_deg} has its centroid "
        f"inside any of the {len(regions)} region(s) ({', '.join(sorted({r.name for r in regions}))}). "
        f"The regions enclose no area the triangulation covers: check that every loop is a "
        f"simple closed polygon and that each hole lies inside its own outer loop.")


def _refuse_unresolved_points(P: np.ndarray, coplanar: np.ndarray, domain: Domain) -> None:
    """Refuse a boundary point the triangulation dropped as indistinguishable from a neighbour.

    Qhull leaves out a point it cannot separate from a nearby vertex at double precision.
    A boundary edge ending at such a point can never appear in the triangulation, so the
    segment loop would split it, and its halves, without end. Besides a vertex a hair off an
    edge and a sliver edge, the sides of a sharp corner with a curved side that the trigger
    calls compatible end here: they split each other toward the apex (module docstring).
    """
    i, _facet, j = (int(x) for x in coplanar[0])
    raise RuntimeError(
        f"meshine.generate: the triangulation cannot resolve {len(coplanar)} boundary point(s); "
        f"the first is ({P[i, 0]:.17g}, {P[i, 1]:.17g}), {np.linalg.norm(P[i] - P[j]):.3g} from its "
        f"neighbour in a domain of extent {domain.extent():.6g}. Two boundaries come closer than "
        f"the triangulation separates at that extent: a vertex a hair off another edge or a "
        f"sliver edge (snap them together or remove the sliver), or a sharp corner with a curved "
        f"side whose two sides kept splitting each other toward the apex (for example a coarse "
        f"Circle that touches another boundary; see the Limits in meshine's documentation).")


def _longest_edge_squared(p: np.ndarray) -> np.ndarray:
    """(T,) squared length of the longest edge of each triangle in ``p`` of shape (T, 3, 2)."""
    e0, e1, e2 = p[:, 2] - p[:, 1], p[:, 0] - p[:, 2], p[:, 1] - p[:, 0]
    return np.maximum(np.maximum((e0 ** 2).sum(1), (e1 ** 2).sum(1)), (e2 ** 2).sum(1))


def _edge_keys(simp: np.ndarray, n: int) -> np.ndarray:
    simp = simp.astype(np.int64)          # Qhull returns int32; min*n + max overflows past ~46k points
    e = np.vstack([simp[:, [0, 1]], simp[:, [1, 2]], simp[:, [2, 0]]])
    return np.unique(np.minimum(e[:, 0], e[:, 1]) * n + np.maximum(e[:, 0], e[:, 1]))


def _classify(P: np.ndarray, simp: np.ndarray, regions: list[Region],
              seg_keys: np.ndarray | None = None) -> tuple[np.ndarray, np.ndarray]:
    """(region id per triangle, degeneracy mask). Region -1 = outside every region / in a hole.

    Triangles that share a non-constrained edge belong to the same region, so
    connected components of the "adjacent across an unconstrained edge" graph
    are found first (O(T log T)) and only one representative per component —
    the largest triangle, whose centroid is safely inside — is tested against
    the region polygons. This keeps classification cheap even when the loops
    have thousands of vertices.

    The degeneracy mask is returned as well as applied: it and "no centroid landed
    in a region" are the two ways this stage can end up with nothing, and they call
    for different fixes, so the caller needs to tell them apart.
    """
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components

    n = len(P)
    T = len(simp)
    simp = simp.astype(np.int64)
    p = P[simp]
    area2 = ((p[:, 1, 0] - p[:, 0, 0]) * (p[:, 2, 1] - p[:, 0, 1])
             - (p[:, 2, 0] - p[:, 0, 0]) * (p[:, 1, 1] - p[:, 0, 1]))
    degenerate = np.abs(area2) <= AREA_EPS * _longest_edge_squared(p)

    e = np.vstack([simp[:, [0, 1]], simp[:, [1, 2]], simp[:, [2, 0]]])
    keys = np.minimum(e[:, 0], e[:, 1]) * n + np.maximum(e[:, 0], e[:, 1])
    owner = np.tile(np.arange(T), 3)
    order = np.argsort(keys, kind="stable")
    ks, ow = keys[order], owner[order]
    same = ks[1:] == ks[:-1]                      # interior edges appear exactly twice
    if seg_keys is not None and len(seg_keys):
        same &= ~np.isin(ks[1:], seg_keys)
    a, b = ow[:-1][same], ow[1:][same]
    graph = coo_matrix((np.ones(len(a)), (a, b)), shape=(T, T))
    ncomp, labels = connected_components(graph, directed=False)

    region_id = np.full(T, -1, dtype=int)
    rep = np.full(ncomp, -1, dtype=int)
    big = np.where(degenerate, -1.0, np.abs(area2))
    for t in np.argsort(-big):
        if rep[labels[t]] < 0:
            rep[labels[t]] = t
    cent = p[rep].mean(axis=1)
    comp_region = np.full(ncomp, -1, dtype=int)
    for r, reg in enumerate(regions):
        polys = [P[np.array(lp)] for lp in reg.loops]
        hit = points_in_loops(cent, polys) & (comp_region < 0)
        comp_region[hit] = r
    region_id = comp_region[labels]
    region_id[degenerate] = -1
    return region_id, degenerate


def _triangle_data(P: np.ndarray, T: np.ndarray):
    """(circumcenters, circumradii, (T, 3) angles in radians, centroids)."""
    p = P[T]
    a, b, c = p[:, 0], p[:, 1], p[:, 2]
    d = 2 * ((a[:, 0] * (b[:, 1] - c[:, 1])) + (b[:, 0] * (c[:, 1] - a[:, 1])) + (c[:, 0] * (a[:, 1] - b[:, 1])))
    a2, b2, c2 = (a ** 2).sum(1), (b ** 2).sum(1), (c ** 2).sum(1)
    ux = (a2 * (b[:, 1] - c[:, 1]) + b2 * (c[:, 1] - a[:, 1]) + c2 * (a[:, 1] - b[:, 1])) / d
    uy = (a2 * (c[:, 0] - b[:, 0]) + b2 * (a[:, 0] - c[:, 0]) + c2 * (b[:, 0] - a[:, 0])) / d
    cc = np.column_stack([ux, uy])
    R = np.linalg.norm(cc - a, axis=1)
    la = np.linalg.norm(c - b, axis=1)
    lb = np.linalg.norm(a - c, axis=1)
    lc = np.linalg.norm(b - a, axis=1)
    cos0 = (lb ** 2 + lc ** 2 - la ** 2) / (2 * lb * lc)
    cos1 = (la ** 2 + lc ** 2 - lb ** 2) / (2 * la * lc)
    cos2 = (la ** 2 + lb ** 2 - lc ** 2) / (2 * la * lb)
    angles = np.arccos(np.clip(np.stack([cos0, cos1, cos2], 1), -1, 1))
    return cc, R, angles, p.mean(axis=1)


# -- small input angles (module docstring) ---------------------------------------

def _sharp_corners(P: np.ndarray, segs: list[Segment], regions: list[Region]) -> dict[int, list[_Corner]]:
    """{input vertex: its sharp corners}: every gap below ``SHARP_CORNER`` between two
    consecutive segments around the vertex, whether it opens into a region or not (a
    corner that opens into a hole or out of the domain still has two sides that encroach
    each other). ``inside`` probes the bisector at 1e-3 of the shorter side; the probes of
    all corners go through one point-in-polygon pass per region."""
    around: dict[int, list[int]] = {}
    for s in segs:
        around.setdefault(s.a, []).append(s.b)
        around.setdefault(s.b, []).append(s.a)
    found: list[tuple[int, float, float, int, int]] = []
    probes: list[np.ndarray] = []
    for v, nbrs in around.items():
        if len(nbrs) < 2:
            continue
        d = P[nbrs] - P[v]
        phi = np.arctan2(d[:, 1], d[:, 0])
        order = np.argsort(phi)
        phi, nbrs = phi[order], [nbrs[i] for i in order]
        width = np.diff(np.append(phi, phi[0] + 2 * np.pi))
        for k in np.nonzero((width > 0) & (width < SHARP_CORNER))[0]:
            u, w = nbrs[k], nbrs[(k + 1) % len(nbrs)]
            mid = phi[k] + 0.5 * width[k]
            r = 1e-3 * min(np.linalg.norm(P[u] - P[v]), np.linalg.norm(P[w] - P[v]))
            found.append((v, float(phi[k]), float(width[k]), u, w))
            probes.append(P[v] + r * np.array([np.cos(mid), np.sin(mid)]))
    corners: dict[int, list[_Corner]] = {}
    if not found:
        return corners
    # points_in_loops tests each point on its own, so one pass over all probes per region
    # gives every probe the answer it gets alone
    at = np.array(probes)
    inside = np.zeros(len(at), dtype=bool)
    for reg in regions:
        inside |= points_in_loops(at, [P[np.array(lp)] for lp in reg.loops])
    for (v, start, gap, u, w), into_region in zip(found, inside):
        corners.setdefault(v, []).append(_Corner(start, gap, u, w, bool(into_region)))
    return corners


def _halving_compatible(L1: float, L2: float, width: float) -> bool:
    """True when halving the longer of two first pieces of lengths L1 and L2 at a corner of
    this width eventually leaves neither one encroached by the other's far vertex: the
    length ratio is within 1/cos(width) of a power of two (``HALVING_SLACK``)."""
    band = math.log2(1.0 / math.cos(width)) + HALVING_SLACK
    frac = math.log2(max(L1, L2) / min(L1, L2)) % 1.0
    return frac <= band or frac >= 1.0 - band


def _treated_apices(P: np.ndarray, corners: dict[int, list[_Corner]], theta: float
                    ) -> tuple[dict[tuple[int, int], dict[int, int]], dict[int, float]]:
    """The trigger of the small-angle rules: (apex tags, unit).

    A vertex is treated when one of its sharp corners is acute (opens into a region at
    less than ``theta``) or halving-incompatible on its first pieces, where plain
    refinement does not finish. A first piece is the whole side, unless the side's far
    end is treated and puts its lattice vertex (``_lattice_point``) on it: then the piece
    ends there, and a corner compatible on the input lengths can become incompatible. The
    test repeats until it treats no further vertex. It can only spread from a vertex
    treated on its input lengths, so an input with none treats no vertex and takes none
    of the new paths. Each side of a sharp corner at a treated vertex v is tagged
    ``{segment key: {v: far end}}``, and ``unit[v]`` is the length of its shortest such
    side.
    """
    sides = {v: sorted({x for c in cs for x in (c.u, c.w)}) for v, cs in corners.items()}
    unit: dict[int, float] = {}

    def first_piece(v: int, x: int) -> float:
        """Length of the piece at v of side v-x once the lattice of a treated x is in."""
        if x in unit and v in sides[x]:
            return float(np.linalg.norm(_lattice_point(P[x], P[v], unit[x]) - P[v]))
        return float(np.linalg.norm(P[x] - P[v]))

    while True:
        new = []
        for v, cs in corners.items():
            if v in unit:
                continue
            piece = {x: first_piece(v, x) for x in sides[v]}
            if any(c.inside and c.width < theta or not _halving_compatible(piece[c.u], piece[c.w], c.width)
                   for c in cs):
                new.append(v)
        if not new:
            break
        for v in new:
            unit[v] = min(float(np.linalg.norm(P[x] - P[v])) for x in sides[v])
    unit = {v: unit[v] for v in corners if v in unit}           # in the order of the corners
    tags: dict[tuple[int, int], dict[int, int]] = {}
    for v in unit:
        for x in sides[v]:
            tags.setdefault((min(v, x), max(v, x)), {})[v] = x
    return tags, unit


def _lattice_point(apex: np.ndarray, other: np.ndarray, unit: float) -> np.ndarray:
    """The point of segment apex-other at distance ``unit * 2**k`` from the apex, for the
    largest k that keeps it below half the segment's length: in [L/4, L/2) of length L."""
    length = float(np.linalg.norm(other - apex))
    d = math.ldexp(unit, math.floor(math.log2(length / unit)) - 1)
    if d >= 0.5 * length:
        d *= 0.5
    return apex + (other - apex) * (d / length)


def _shell_point(apex: np.ndarray, other: np.ndarray, unit: float) -> np.ndarray:
    """The point of segment apex-other at distance ``unit * 2**k`` from the apex, for the k
    nearest its midpoint. It lies between one and two thirds of the way along, and on a
    piece that already ends on the lattice it is the midpoint."""
    d = other - apex
    length = float(np.hypot(*d))
    half = 0.5 * length / unit
    lo = 2.0 ** np.floor(np.log2(half))
    r = lo if half - lo <= 2 * lo - half else 2 * lo
    return apex + d * (r * unit / length)


def _excuse_acute_corners(P: np.ndarray, T: np.ndarray, angles: np.ndarray, cent: np.ndarray,
                          acute: dict[int, list[_Corner]]) -> None:
    """Set to pi the angle a triangle has at the apex of an acute corner when its centroid
    lies inside that corner. No inserted vertex can raise that angle."""
    rows, cols = np.nonzero(np.isin(T, list(acute)))
    for t, k in zip(rows, cols):
        v = int(T[t, k])
        d = cent[t] - P[v]
        phi = math.atan2(d[1], d[0])
        if any((phi - c.start) % (2 * math.pi) < c.width for c in acute[v]):
            angles[t, k] = np.pi


def _first_pieces(P: np.ndarray, acute: dict[int, list[_Corner]],
                  apex_piece: dict[tuple[int, int], dict[int, int]]) -> tuple[np.ndarray, np.ndarray]:
    """((K, 2) current subsegments at the apex of each acute corner, one per side, (K,) sin
    of half the angle between the two first pieces of their corner). The angle is measured
    on the current pieces, not the input segments: a curved side turns as its piece shrinks."""
    first = {(v, x): key for key, tags in apex_piece.items() for v, x in tags.items()}
    pieces, sines = [], []
    for v, cs in acute.items():
        for c in cs:
            a, b = (sum(first[(v, x)]) - v for x in (c.u, c.w))
            du, dw = P[a] - P[v], P[b] - P[v]
            cos = float(du @ dw) / (np.linalg.norm(du) * np.linalg.norm(dw))
            half = 0.5 * math.acos(min(1.0, max(-1.0, cos)))
            pieces += [(v, a), (v, b)]
            sines += [math.sin(half)] * 2
    return np.array(pieces, dtype=np.int64).reshape(-1, 2), np.array(sines)


def _terminated(P: np.ndarray, T: np.ndarray, cc: np.ndarray, pieces: np.ndarray,
                sines: np.ndarray) -> np.ndarray:
    """(T,) mask of skinny triangles to leave as they are: the circumcenter encroaches a
    first piece of an acute corner, and splitting it would leave vertices
    |piece| * sin(angle / 2) apart, closer than the triangle's shortest edge.

    A tree of the circumcenters is asked, once per piece, for those within the piece's own
    half-length, and only those pairs take the strict test: comparing every triangle with
    every piece built an (S, K, 2) array of S skinny triangles by K pieces."""
    out = np.zeros(len(T), dtype=bool)
    if not len(pieces):
        return out
    a, b = P[pieces[:, 0]], P[pieces[:, 1]]
    mid, length = 0.5 * (a + b), np.linalg.norm(a - b, axis=1)
    p = P[T]
    shortest = np.sqrt(np.minimum(np.minimum(((p[:, 1] - p[:, 2]) ** 2).sum(1), ((p[:, 2] - p[:, 0]) ** 2).sum(1)),
                                  ((p[:, 0] - p[:, 1]) ** 2).sum(1)))
    near = cKDTree(cc).query_ball_point(mid, 0.5 * length)
    ki = np.repeat(np.arange(len(mid)), [len(lst) for lst in near])
    ti = np.fromiter((t for lst in near for t in lst), dtype=np.int64, count=len(ki))
    if len(ki):
        hit = np.linalg.norm(cc[ti] - mid[ki], axis=1) < (0.5 * length * (1 - 1e-9))[ki]
        hit &= (length * sines)[ki] < shortest[ti]
        out[ti[hit]] = True
    return out


def _encroached(cand: np.ndarray, mids: np.ndarray, half: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """((C,) mask of the candidate points strictly inside the diametral circle of a segment,
    sorted unique ids of the segments they encroach), for segments of midpoints ``mids`` and
    half-lengths ``half``. Strict: a point closer than ``half * (1 - 1e-9)`` to the midpoint.

    The tree holds the candidates and each segment asks for those within its own radius, so
    only pairs near a segment are examined. Asking for every segment midpoint within the
    largest radius of all segments, as before, examines nearly every pair once one long
    segment lies beside a finely meshed region."""
    near = cKDTree(cand).query_ball_point(mids, half)
    si = np.repeat(np.arange(len(mids)), [len(lst) for lst in near])
    ci = np.fromiter((c for lst in near for c in lst), dtype=np.int64, count=len(si))
    encroaches = np.zeros(len(cand), dtype=bool)
    if not len(si):
        return encroaches, np.empty(0, dtype=np.int64)
    hit = np.linalg.norm(cand[ci] - mids[si], axis=1) < half[si] * (1 - 1e-9)
    encroaches[ci[hit]] = True
    return encroaches, np.unique(si[hit])


def _separate(cand: np.ndarray, R: np.ndarray, factor: float = 0.7) -> np.ndarray:
    """Greedy filter: accept candidates (largest circumradius first) whose distance to
    every previously accepted candidate exceeds ``factor`` times their own radius."""
    order = np.argsort(-R)
    tree = cKDTree(cand)
    accepted = np.zeros(len(cand), dtype=bool)
    for i in order:
        near = tree.query_ball_point(cand[i], factor * R[i])
        if not any(accepted[j] for j in near if j != i):
            accepted[i] = True
    return accepted


def _orient_ccw(P: np.ndarray, T: np.ndarray) -> np.ndarray:
    p = P[T]
    area2 = ((p[:, 1, 0] - p[:, 0, 0]) * (p[:, 2, 1] - p[:, 0, 1])
             - (p[:, 2, 0] - p[:, 0, 0]) * (p[:, 1, 1] - p[:, 0, 1]))
    T = T.copy()
    flip = area2 < 0
    T[flip, 1], T[flip, 2] = T[flip, 2], T[flip, 1]
    return T


def _used_nodes(P: np.ndarray, T: np.ndarray) -> np.ndarray:
    return np.unique(T)


def _assemble(P, T, rid, regions, segs, on_segment) -> TriMesh:
    used = np.unique(T)
    remap = np.full(len(P), -1, dtype=int)
    remap[used] = np.arange(len(used))
    nodes = P[used].copy()
    tris = remap[T]
    # regions added under the same name are one material
    names: list[str] = []
    for r in regions:
        if r.name not in names:
            names.append(r.name)
    region_to_id = np.array([names.index(r.name) for r in regions])

    boundary: dict[str, list] = {}
    interfaces: dict[tuple[str, str], list] = {}
    for s in segs.values():
        e = (remap[s.a], remap[s.b])
        if len(s.owners) == 1:
            boundary.setdefault(s.name or "outer", []).append(e)
        else:
            a, b = (regions[o].name for o in s.owners)
            if a != b:
                interfaces.setdefault(tuple(sorted((a, b))), []).append(e)
    boundary_edges = {k: np.array(v, dtype=int) for k, v in boundary.items()}
    boundary_nodes = {k: np.unique(v) for k, v in boundary_edges.items()}
    return TriMesh(nodes, tris, region_to_id[rid], names, boundary_edges, boundary_nodes,
                   {k: np.array(v, dtype=int) for k, v in interfaces.items()})


def _laplacian_smooth(mesh: TriMesh, fixed: np.ndarray, sweeps: int, omega: float = 0.5,
                      min_angle_deg: float = 28.0):
    """Move free nodes toward the average of their neighbours, accepting a move only
    where no incident triangle's smallest angle gets worse (below the target)."""
    T = mesh.triangles
    n = mesh.num_nodes
    e = np.vstack([T[:, [0, 1]], T[:, [1, 2]], T[:, [2, 0]]])
    rows = np.concatenate([e[:, 0], e[:, 1]])
    cols = np.concatenate([e[:, 1], e[:, 0]])
    deg = np.maximum(np.bincount(rows, minlength=n), 1).astype(float)
    theta = np.radians(min_angle_deg)

    def tri_min_angle(X):
        p = X[T]
        la = np.linalg.norm(p[:, 2] - p[:, 1], axis=1)
        lb = np.linalg.norm(p[:, 0] - p[:, 2], axis=1)
        lc = np.linalg.norm(p[:, 1] - p[:, 0], axis=1)
        with np.errstate(invalid="ignore", divide="ignore"):
            c0 = (lb ** 2 + lc ** 2 - la ** 2) / (2 * lb * lc)
            c1 = (la ** 2 + lc ** 2 - lb ** 2) / (2 * la * lc)
            c2 = (la ** 2 + lb ** 2 - lc ** 2) / (2 * la * lb)
        area2 = ((p[:, 1, 0] - p[:, 0, 0]) * (p[:, 2, 1] - p[:, 0, 1])
                 - (p[:, 2, 0] - p[:, 0, 0]) * (p[:, 1, 1] - p[:, 0, 1]))
        amin = np.arccos(np.clip(np.stack([c0, c1, c2], 1), -1, 1)).min(axis=1)
        amin[area2 <= 0] = -1.0                      # inverted: always rejected
        return amin

    for _ in range(sweeps):
        old = mesh.nodes
        amin_old = tri_min_angle(old)
        avg = np.zeros_like(old)
        np.add.at(avg, rows, old[cols])
        avg /= deg[:, None]
        allowed = ~fixed
        new = old.copy()
        for _it in range(6):
            new = old.copy()
            new[allowed] += omega * (avg[allowed] - old[allowed])
            amin_new = tri_min_angle(new)
            worse = amin_new < np.minimum(amin_old, theta)
            if not worse.any():
                break
            allowed[np.unique(T[worse])] = False     # freeze nodes of worsened triangles, retry
        else:
            new = old
        mesh.nodes = new
