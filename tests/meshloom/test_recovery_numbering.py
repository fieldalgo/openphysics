# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Segment recovery does not add a dependence on how the input numbers its points.

The pipeline's symbolic perturbation breaks cospherical ties by point number, so a
mesh may change when the points are renumbered at random (documented in the
overview). Renumbering the points in the order the triangles first use them (as a
mesh file loader does) leaves these inputs' first Delaunay tetrahedralization
unchanged, and segment recovery must then give the same mesh: it used to order a
round's split points by segment number, and the needle readiness input at 1e5 faces
met V3(a)'s bound in one numbering and not in the other.
"""

import hashlib

import numpy as np
import pytest

meshloom = pytest.importorskip("meshloom")
if not meshloom.kernel_available():
    pytest.skip("meshloom's compiled kernel is not built in this environment", allow_module_level=True)

import cdt_inputs as C  # noqa: E402
from meshloom._core import mesh_plc  # noqa: E402


def geometric_digest(m):
    """The mesh's tetrahedra as sets of node coordinates, independent of numbering."""
    nodes = np.asarray(m["nodes"])
    tets = sorted(tuple(sorted(map(tuple, nodes[t].tolist()))) for t in np.asarray(m["tetrahedra"]))
    return hashlib.sha256(repr(tets).encode()).hexdigest()


def first_use_numbering(P, T):
    """The points renumbered in the order the triangles first use them."""
    order, seen = [], {}
    for v in T.reshape(-1).tolist():
        if v not in seen:
            seen[v] = len(order)
            order.append(v)
    new = np.full(len(P), -1, dtype=np.int64)
    new[order] = np.arange(len(order))
    return P[np.array(order)], new[T]


@pytest.mark.parametrize("category", ["needle", "fan"])
def test_loader_numbering_gives_the_same_mesh(category):
    P, T, _ = C.build(category, 5000)
    P2, T2 = first_use_numbering(P, T)
    assert len(P2) == len(P)
    a = mesh_plc(P, [[list(map(int, t))] for t in T], domain="parity")
    b = mesh_plc(P2, [[list(map(int, t))] for t in T2], domain="parity")
    assert len(a["tetrahedra"]) == len(b["tetrahedra"])
    assert geometric_digest(a) == geometric_digest(b)
