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
"""

from __future__ import annotations

from collections.abc import Callable

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


def generate(domain: Domain, boundary_names="outer", *, min_angle: float = 28.0,
             size_fn: Callable[[np.ndarray, np.ndarray], np.ndarray] | None = None,
             size_factor: float = 0.6, max_rounds: int = 80, max_points: int = 300_000,
             smooth: int = 2, verbose: bool = False) -> TriMesh:
    """Mesh a ``Domain``.

    Parameters
    ----------
    min_angle : quality bound in degrees (Ruppert guarantees termination below ~20.7;
                28-30 is a safe practical default for right-angled input)
    size_fn : optional callable h(x, y) -> target edge length, combined by minimum
              with the per-region sizes
    size_factor : a triangle is too big when circumradius > size_factor * h
                  (an equilateral triangle of edge h has circumradius 0.577 h)
    smooth : Laplacian smoothing sweeps of interior nodes after refinement
    """
    if min_angle >= 34:
        raise ValueError("min_angle above ~33 degrees cannot be guaranteed; use <= 33")
    pts, seg_list, regions = domain.build(boundary_names)
    P = pts.copy()
    segs: dict[tuple[int, int], Segment] = {s.key: s for s in seg_list}
    sizes = np.array([r.size if r.size is not None else domain.default_size for r in regions])
    theta = np.radians(min_angle)
    on_segment = np.zeros(len(P), dtype=bool)
    for s in segs.values():
        on_segment[[s.a, s.b]] = True

    def add_points(new: np.ndarray, constrained: bool):
        nonlocal P, on_segment
        start = len(P)
        P = np.vstack([P, new])
        on_segment = np.concatenate([on_segment, np.full(len(new), constrained)])
        return np.arange(start, len(P))

    def split(seg: Segment):
        mid = 0.5 * (P[seg.a] + P[seg.b])
        if seg.curve is not None:
            mid = seg.curve.project(mid)
        (m,) = add_points(mid[None, :], True)
        del segs[seg.key]
        for a, b in ((seg.a, m), (m, seg.b)):
            child = Segment(a, b, seg.curve, list(seg.owners), seg.name)
            segs[child.key] = child
        for r in seg.owners:
            for loop in regions[r].loops:
                n = len(loop)
                for k in range(n):
                    u, v = loop[k], loop[(k + 1) % n]
                    if (u, v) == (seg.a, seg.b) or (u, v) == (seg.b, seg.a):
                        loop.insert(k + 1, int(m))
                        break

    tri = None
    for rnd in range(max_rounds):
        tri = Delaunay(P)
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
            for s in to_split:
                split(s)
            if verbose:
                print(f"round {rnd}: split {len(to_split)} segments, {len(P)} points")
            continue

        # -- 3. bad triangles ----------------------------------------------------
        region_id, _degenerate = _classify(P, simp, regions, keys)
        inside = region_id >= 0
        T = simp[inside]
        cc, R, amin, cent = _triangle_data(P, T)
        h = sizes[region_id[inside]]
        if size_fn is not None:
            h = np.minimum(h, np.asarray(size_fn(cent[:, 0], cent[:, 1]), dtype=float))
        bad = (amin < theta) | (R > size_factor * h)
        if not bad.any():
            break
        cand, cand_R = cc[bad], R[bad]

        # circumcenters that encroach a segment -> split the segment instead
        seg_arr = np.array([(s.a, s.b) for s in segs.values()])
        seg_objs = list(segs.values())
        mids = 0.5 * (P[seg_arr[:, 0]] + P[seg_arr[:, 1]])
        half = 0.5 * np.linalg.norm(P[seg_arr[:, 0]] - P[seg_arr[:, 1]], axis=1)
        seg_tree = cKDTree(mids)
        hmax = half.max()
        encroaches = np.zeros(len(cand), dtype=bool)
        near_lists = seg_tree.query_ball_point(cand, hmax)
        ci_idx = np.repeat(np.arange(len(cand)), [len(l) for l in near_lists])
        si_idx = np.fromiter((si for l in near_lists for si in l), dtype=int, count=len(ci_idx))
        seg_to_split: set[int] = set()
        if len(ci_idx):
            dist = np.linalg.norm(cand[ci_idx] - mids[si_idx], axis=1)
            hit = dist < half[si_idx] * (1 - 1e-9)
            encroaches[ci_idx[hit]] = True
            seg_to_split = set(np.unique(si_idx[hit]).tolist())
        for si in seg_to_split:
            split(seg_objs[si])
        cand, cand_R = cand[~encroaches], cand_R[~encroaches]

        # drop circumcenters outside the domain, then enforce separation
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
        if len(P) > max_points:
            raise RuntimeError(f"more than {max_points} points; check sizes / min_angle")
    else:
        raise RuntimeError(f"refinement did not converge in {max_rounds} rounds")

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
    amin = np.arccos(np.clip(np.stack([cos0, cos1, cos2], 1), -1, 1)).min(axis=1)
    return cc, R, amin, p.mean(axis=1)


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
