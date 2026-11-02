# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Numpy wrappers of the compiled kernel's building blocks (internal, not public API).

The exact predicates and the Delaunay tetrahedralization are the first stages of
the mesher. They are exposed here for the pre-registered checks (V16, V17) and the
benchmark; the public mesher API comes with a later release and may change them.
"""

from __future__ import annotations

import numpy as np

from . import KernelUnavailable, _IMPORT_ERROR, _kernel

_GROUP = {"orient3d": 4, "incircle3d": 4, "insphere": 5, "insphere_sos": 5}


def _require():
    if _kernel is None:
        raise KernelUnavailable(f"meshloom's compiled kernel is not available here: {_IMPORT_ERROR}")
    return _kernel


def _points(points) -> np.ndarray:
    p = np.ascontiguousarray(points, dtype="<f8")
    if p.ndim != 2 or p.shape[1] != 3:
        raise ValueError(f"points must have shape (n, 3), got {p.shape}")
    return p


def predicate_signs(kind: str, coords, ids=None) -> np.ndarray:
    """Exact signs of one predicate over a batch.

    ``coords`` has shape (n, k, 3) with k = 4 for ``orient3d`` and ``incircle3d`` and
    k = 5 for ``insphere`` and ``insphere_sos``; ``ids`` (n, 5) gives the global point
    indices that order the perturbation of ``insphere_sos``. Returns n int8 values in
    {-1, 0, 1}. Conventions: orient3d(a, b, c, d) = det[b - a, c - a, d - a];
    insphere > 0 when e is inside the sphere through a positively oriented a, b, c, d;
    incircle3d > 0 when coplanar d is inside the circle through a, b, c.
    """
    kernel = _require()
    k = _GROUP.get(kind)
    if k is None:
        raise ValueError(f"unknown predicate {kind!r}")
    c = np.ascontiguousarray(coords, dtype="<f8")
    if c.ndim != 3 or c.shape[1:] != (k, 3):
        raise ValueError(f"{kind} takes coordinates of shape (n, {k}, 3), got {c.shape}")
    i = None
    if ids is not None:
        i = np.ascontiguousarray(ids, dtype="<i8")
        if i.shape != c.shape[:2]:
            raise ValueError(f"ids must have shape {c.shape[:2]}, got {i.shape}")
        i = i.tobytes()
    out = kernel.predicate_signs(kind, c.tobytes(), i)
    return np.frombuffer(out, dtype=np.int8).copy()


def delaunay(points, order=None) -> tuple[np.ndarray, np.ndarray, dict]:
    """Delaunay tetrahedralization of ``points`` (n, 3).

    Returns ``(tetrahedra, vertex_of, stats)``: positively oriented tetrahedra (T, 4)
    int64 indexing ``points``; for each point the index of the equal point that is
    the vertex (the lowest index of its group), and the kernel counters. Ties of
    cospherical points are broken by a symbolic perturbation ordered by point index,
    so the result does not depend on the insertion order. ``order`` (a permutation of
    the indices) fixes the insertion order; by default a biased randomized order
    with Hilbert rounds is used.
    """
    kernel = _require()
    p = _points(points)
    o = None if order is None else np.ascontiguousarray(order, dtype="<i8").tobytes()
    tets, vertex_of, stats = kernel.delaunay(p.tobytes(), o)
    # astype copies into a writable native int64 array (the bytes are read-only)
    return (np.frombuffer(tets, dtype="<i8").reshape(-1, 4).astype(np.int64),
            np.frombuffer(vertex_of, dtype="<i8").astype(np.int64), stats)


def verify_delaunay(points, tetrahedra) -> dict:
    """Check that ``tetrahedra`` is the Delaunay tetrahedralization of the distinct
    ``points`` under the index-ordered perturbation, from the arrays alone, with exact
    predicates. Raises ``ValueError`` naming the first violation; returns counts."""
    kernel = _require()
    p = _points(points)
    t = np.ascontiguousarray(tetrahedra, dtype="<i8")
    if t.ndim != 2 or t.shape[1] != 4:
        raise ValueError(f"tetrahedra must have shape (T, 4), got {t.shape}")
    return kernel.verify_delaunay(p.tobytes(), t.tobytes())
