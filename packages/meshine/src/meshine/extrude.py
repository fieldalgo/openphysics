# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Layered tetrahedral meshes: a meshine footprint extruded through a stack of layers.

Every footprint triangle becomes one prism per sub-layer, and every prism is split
into three tetrahedra by the vertex-order rule (Dompierre et al., 1999): with the
triangle's vertices sorted by global index, each side quad is cut along the
diagonal from its lower-index bottom vertex to its higher-index top vertex. A side
quad is shared by two prisms that sort its two vertices the same way, so the cuts
always agree and the mesh is conforming without any search.

Each (footprint region, layer) is mapped to a material name or ``None`` (void, left
out of the mesh). Faces are classified column by column, without a global face
sort: the bottom and top of the stack, the footprint's own boundary names on the
sides, ``void`` where a solid cell meets a left-out one, and interfaces where two
different materials meet. Node z coordinates are the given layer boundaries and
equal subdivisions of them, so they are affine in the layer thicknesses.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence

import numpy as np

from .mesh import TriMesh
from .mesh3d import TetMesh

Materials = Mapping[str, Sequence[str | None]] | Callable[[str, int], str | None] | None


def extrude(footprint: TriMesh, z: Sequence[float], materials: Materials = None, *,
            divisions: int | Sequence[int] | None = None, size: float | None = None,
            bottom: str = "z0", top: str = "z1", void: str = "void") -> TetMesh:
    """Extrude ``footprint`` through the layers ``z[0] < z[1] < ... < z[L]``.

    ``materials`` names the material of each footprint region in each layer: a
    mapping ``{region: [name or None per layer]}``, a function
    ``(region, layer_index) -> name or None``, or ``None`` to keep each footprint
    region's own name in every layer. ``None`` as a name leaves that cell out.

    Each layer is split into ``divisions`` equal sub-layers (one number, or one per
    layer); alternatively ``size`` picks the fewest sub-layers that are at most
    ``size`` thick. With neither, every layer is one sub-layer.

    Exterior faces are tagged ``bottom`` and ``top`` (default ``z0`` and ``z1``) on
    the first and last level, with the footprint's boundary-edge name on the sides,
    and ``void`` against a left-out cell. A footprint side named like one of those
    three is refused rather than merged with it. ``interfaces`` holds the faces
    between two materials.
    """
    z = np.asarray(z, dtype=float)
    if z.ndim != 1 or len(z) < 2 or not np.isfinite(z).all() or not (np.diff(z) > 0).all():
        raise ValueError("z must hold at least two finite, strictly increasing levels")
    clash = {bottom, top, void} & set(footprint.boundary_edges)
    if len({bottom, top, void}) != 3 or clash:
        raise ValueError(f"bottom, top and void must differ from each other and from the footprint's side names; "
                         f"clash: {sorted(clash) or [bottom, top, void]}")
    n_layers = len(z) - 1
    counts = _divisions(np.diff(z), divisions, size)
    sub_z = np.concatenate([z[k] + (z[k + 1] - z[k]) * np.arange(counts[k]) / counts[k]
                            for k in range(n_layers)] + [z[-1:]])
    layer_of = np.repeat(np.arange(n_layers), counts)              # layer index of each sub-layer
    n_sub = len(layer_of)

    P = np.asarray(footprint.nodes, dtype=float)
    T = np.asarray(footprint.triangles, dtype=np.int64)
    n2 = len(P)

    # material of every (triangle, sub-layer) cell; -1 = void
    lookup = _material_lookup(materials, footprint.region_names, n_layers)
    names: list[str] = []
    zone_layer = np.full((len(footprint.region_names), n_layers), -1, dtype=np.int64)
    for k in range(n_layers):
        for r, zone in enumerate(footprint.region_names):
            name = lookup(zone, k)
            if name is None:
                continue
            if name not in names:
                names.append(str(name))
            zone_layer[r, k] = names.index(str(name))
    if not names:
        raise ValueError("every cell is void: materials leave nothing to mesh")
    cell = zone_layer[np.asarray(footprint.regions)][:, layer_of]   # (T2, n_sub)

    # tetrahedra: three per solid prism, from the triangle's vertices in index order
    tri = np.sort(T, axis=1)
    a, b, c = tri[:, 0], tri[:, 1], tri[:, 2]
    cw = _cross2(P[b] - P[a], P[c] - P[a]) < 0                     # sorted order turns clockwise
    tets, regs = [], []
    for s in range(n_sub):
        solid = np.flatnonzero(cell[:, s] >= 0)
        if not len(solid):
            continue
        lo, hi = s * n2, (s + 1) * n2
        ta, tb, tc = a[solid], b[solid], c[solid]
        block = np.stack([np.stack([ta + lo, tb + lo, tc + lo, tc + hi], axis=1),
                          np.stack([ta + lo, tb + lo, tc + hi, tb + hi], axis=1),
                          np.stack([ta + lo, ta + hi, tb + hi, tc + hi], axis=1)], axis=1)
        flip = cw[solid]
        block[flip] = block[flip][:, :, [0, 1, 3, 2]]
        tets.append(block.reshape(-1, 4))
        regs.append(np.repeat(cell[solid, s], 3))
    tets = np.concatenate(tets)
    regions = np.concatenate(regs)

    faces: dict[str, list[np.ndarray]] = {}
    pairs: dict[tuple[int, int], list[np.ndarray]] = {}

    def add(store, key, arr):
        if len(arr):
            store.setdefault(key, []).append(arr)

    # horizontal faces at every sub-level; footprint triangles are counter-clockwise
    ccw = np.asarray(footprint.triangles, dtype=np.int64)
    for j in range(n_sub + 1):
        below = cell[:, j - 1] if j > 0 else np.full(len(T), -1)
        above = cell[:, j] if j < n_sub else np.full(len(T), -1)
        up = ccw + j * n2                                           # normal +z
        down = up[:, [0, 2, 1]]                                     # normal -z
        name = bottom if j == 0 else top if j == n_sub else void
        add(faces, name, up[(below >= 0) & (above < 0)])
        add(faces, name, down[(above >= 0) & (below < 0)])
        both = (below >= 0) & (above >= 0) & (below != above)
        if both.any():
            lo_first = _name_lt(names, below, above)                # a = below: wound up, from a to b
            for i in np.flatnonzero(both):
                ra, rb = (below[i], above[i]) if lo_first[i] else (above[i], below[i])
                add(pairs, (ra, rb), (up if lo_first[i] else down)[i:i + 1])

    # vertical faces on every footprint edge, two triangles per quad
    e = np.concatenate([T[:, [0, 1]], T[:, [1, 2]], T[:, [2, 0]]])
    owner = np.tile(np.arange(len(T)), 3)
    third = np.concatenate([T[:, 2], T[:, 0], T[:, 1]])
    key = np.sort(e, axis=1)
    order = np.lexsort((key[:, 1], key[:, 0]))
    key, owner, third = key[order], owner[order], third[order]
    first = np.ones(len(key), dtype=bool)
    first[1:] = (key[1:] != key[:-1]).any(axis=1)
    start = np.flatnonzero(first)
    has_two = np.zeros(len(start), dtype=bool)
    has_two[:-1] = (start[1:] - start[:-1]) == 2
    has_two[-1] = len(key) - start[-1] == 2
    u, v = key[start, 0], key[start, 1]
    t1, w1 = owner[start], third[start]
    t2 = np.where(has_two, owner[np.minimum(start + 1, len(key) - 1)], -1)
    # +1 when the triangle t1 lies to the left of u->v
    left1 = _cross2(P[v] - P[u], P[w1] - P[u]) > 0

    side_name = {}
    for tag, edges in footprint.boundary_edges.items():
        for p, q in np.sort(np.asarray(edges, dtype=np.int64), axis=1).tolist():
            side_name[(p, q)] = tag
    outer_tags = np.array([side_name.get((p, q), "") for p, q in zip(u.tolist(), v.tolist())], dtype=object)
    if (outer_tags[~has_two] == "").any():
        raise ValueError("a footprint boundary edge has no name in footprint.boundary_edges")

    for s in range(n_sub):
        c1 = cell[t1, s]
        c2 = np.where(has_two, cell[np.maximum(t2, 0), s], -1)
        lo, hi = s * n2, (s + 1) * n2
        # quad (u0, v0, v1, u1) as triangles (u0, v0, v1) and (u0, v1, u1); normal points right of u->v
        right = np.stack([np.stack([u + lo, v + lo, v + hi], axis=1),
                          np.stack([u + lo, v + hi, u + hi], axis=1)], axis=1)
        left = right[:, :, [0, 2, 1]]

        def wound_out_of(side_one: np.ndarray) -> np.ndarray:
            """Quads wound outward from the cell on side 1 (True) or side 2 (False)."""
            # side 1 is left of u->v exactly when left1; outward from a left cell points right
            out_right = side_one == left1
            return np.where(out_right[:, None, None], right, left)

        only1 = (c1 >= 0) & (c2 < 0)
        only2 = (c2 >= 0) & (c1 < 0)
        q1 = wound_out_of(np.ones(len(u), dtype=bool))
        q2 = wound_out_of(np.zeros(len(u), dtype=bool))
        for mask, quads in ((only1, q1), (only2, q2)):
            outer = mask & ~has_two
            for tag in np.unique(outer_tags[outer]).tolist():
                add(faces, tag, quads[outer & (outer_tags == tag)].reshape(-1, 3))
            add(faces, void, quads[mask & has_two].reshape(-1, 3))
        both = (c1 >= 0) & (c2 >= 0) & (c1 != c2)
        if both.any():
            one_first = _name_lt(names, c1, c2)
            for i in np.flatnonzero(both):
                ra, rb = (c1[i], c2[i]) if one_first[i] else (c2[i], c1[i])
                add(pairs, (ra, rb), (q1 if one_first[i] else q2)[i])

    # keep the nodes the tetrahedra use, in level-major order
    xyz = np.column_stack([np.tile(P, (n_sub + 1, 1)), np.repeat(sub_z, n2)])
    used = np.zeros(len(xyz), dtype=bool)
    used[tets.ravel()] = True
    remap = np.cumsum(used) - 1
    boundary = {tag: remap[np.concatenate(v)] for tag, v in faces.items()}
    interfaces = {}
    for (ra, rb), v in sorted(pairs.items(), key=lambda kv: (names[kv[0][0]], names[kv[0][1]])):
        interfaces[(names[ra], names[rb])] = remap[np.concatenate(v)]
    return TetMesh(xyz[used], remap[tets], regions, names, boundary, interfaces=interfaces)


def _divisions(thickness: np.ndarray, divisions, size) -> np.ndarray:
    if divisions is not None and size is not None:
        raise ValueError("give divisions or size, not both")
    if size is not None:
        if not size > 0:
            raise ValueError("size must be positive")
        q = thickness / float(size)
        return np.maximum(1, np.ceil(q * (1 - 1e-12))).astype(np.int64)   # 1e-12: ratios that are integers up to rounding
    if divisions is None:
        return np.ones(len(thickness), dtype=np.int64)
    d = np.broadcast_to(np.asarray(divisions), thickness.shape)
    if not np.issubdtype(d.dtype, np.integer) or (d < 1).any():
        raise ValueError("divisions must be positive integers, one or one per layer")
    return d.astype(np.int64)


def _material_lookup(materials: Materials, zones: list[str], n_layers: int):
    if materials is None:
        return lambda zone, k: zone
    if callable(materials):
        return materials
    missing = [z for z in zones if z not in materials]
    if missing:
        raise ValueError(f"materials has no entry for footprint regions {missing}")
    for zone, row in materials.items():
        if len(row) != n_layers:
            raise ValueError(f"materials[{zone!r}] has {len(row)} entries for {n_layers} layers")
    return lambda zone, k: materials[zone][k]


def _cross2(p: np.ndarray, q: np.ndarray) -> np.ndarray:
    return p[..., 0] * q[..., 1] - p[..., 1] * q[..., 0]


def _name_lt(names: list[str], ra: np.ndarray, rb: np.ndarray) -> np.ndarray:
    rank = np.argsort(np.argsort(np.array(names, dtype=object)))
    return rank[ra] < rank[rb]
