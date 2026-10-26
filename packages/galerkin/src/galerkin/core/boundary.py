# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Natural boundary conditions on exterior edges of P1 triangle meshes."""
from typing import Mapping

import numpy as np

from .backend import is_live, namespace, to_numpy
from .checks import real_array, real_value


def scalar_boundary_samples(mesh, p, t, prescribed, outward_flux, convection, *, live=False):
    """Sample scalar natural conditions on selected exterior edges (4-point Gauss rules).

    ``outward_flux`` maps boundary_edges tags to a constant or callable(points,
    normals); ``convection`` maps tags to (h, ambient) pairs of the same kinds.
    Selected edge identities are validated before any callable runs. Returns a
    list of (kind, edges, shape, weights, values) tuples. With live=True a JAX
    or PyTorch constant or callback result stays in its library (otherwise it
    is refused); sampled values are then arrays of that library.
    """
    owners = {}
    for cell, tri in enumerate(t):
        for a, b in ((0, 1), (1, 2), (2, 0)):
            owners.setdefault(tuple(sorted((int(tri[a]), int(tri[b])))), []).append(cell)
    x, w = np.polynomial.legendre.leggauss(4)
    x, w = (x+1)/2, w/2
    shape = np.column_stack((1-x, x))
    samples = []
    for kind, data in (("outward_flux", outward_flux), ("convection", convection)):
        if data is None:
            continue
        if not isinstance(data, Mapping):
            raise ValueError(f"{kind} must map boundary edge tags to conditions")
        seen = set()
        for tag, condition in data.items():
            if tag not in mesh.boundary_edges:
                raise ValueError(f"unknown boundary edge tag {tag!r}")
            edges = np.asarray(mesh.boundary_edges[tag])
            if (edges.ndim != 2 or edges.shape[1] != 2 or not len(edges)
                    or edges.dtype.kind not in "iu"):
                raise ValueError("selected boundary edges must be nonempty integer (E,2)")
            normals = []
            for a, b in edges:
                if a == b or a < 0 or b < 0 or a >= len(p) or b >= len(p):
                    raise ValueError("invalid boundary edge node indices")
                key = tuple(sorted((int(a), int(b))))
                if key in seen:
                    raise ValueError(f"duplicate {kind} edge, including reversed/tag duplicates")
                seen.add(key)
                cells = owners.get(key, [])
                if len(cells) != 1:
                    raise ValueError("selected edge must have exactly one incident triangle")
                if int(a) in prescribed and int(b) in prescribed:
                    raise ValueError("natural condition overlaps a fully Dirichlet edge")
                v = p[b]-p[a]
                length = np.linalg.norm(v)
                if not np.isfinite(length) or length <= 0:
                    raise ValueError("boundary edge must have finite positive length")
                n = np.array([v[1], -v[0]])/length
                if n@(p[t[cells[0]]].mean(axis=0)-(p[a]+p[b])/2) > 0:
                    n = -n
                normals.append(n)
            points = np.einsum("qa,ead->eqd", shape, p[edges])
            normal = np.repeat(np.asarray(normals), len(w), axis=0)
            def evaluate(value, name):
                check = real_value if live else real_array
                if callable(value):
                    out = check(value(points.reshape(-1, 2).copy(), normal.copy()), name)
                    if tuple(out.shape) != (len(edges)*len(w),):
                        raise ValueError(f"{name} callback must return exactly shape (Q,)")
                    return out.reshape(len(edges), len(w))
                out = check(value, name)
                if tuple(out.shape) != ():
                    raise ValueError(f"{name} constant must be scalar")
                if is_live(out):
                    return namespace(out).broadcast_to(out, points.shape[:2])
                return np.full(points.shape[:2], float(out))
            if kind == "outward_flux":
                values = (evaluate(condition, "outward flux"),)
            else:
                if not isinstance(condition, (tuple, list)) or len(condition) != 2:
                    raise ValueError("convection condition must be a pair (h, ambient_temperature)")
                h = evaluate(condition[0], "convection h")
                ambient = evaluate(condition[1], "ambient temperature")
                if np.any(to_numpy(h) < 0):
                    raise ValueError("convection h must be nonnegative")
                values = (h, ambient)
            length = np.linalg.norm(p[edges[:, 1]]-p[edges[:, 0]], axis=1)
            samples.append((kind, edges, shape, length[:, None]*w, values))
    return samples


def traction_load(mesh, p, triangles, traction):
    """Consistent Cartesian nodal line load (2N,), N/m of out-of-plane thickness.

    ``traction`` maps boundary_edges tags to a global (2,) vector in Pa or to
    callable(points, outward_normals) -> (Q,2); None or {} gives zero load.
    """
    load = np.zeros((len(p), 2))
    if traction is None:
        return load.ravel()
    if not isinstance(traction, Mapping):
        raise ValueError("traction must map boundary edge tags to vectors or callables")
    if not traction:
        return load.ravel()
    if not isinstance(mesh.boundary_edges, Mapping):
        raise ValueError("traction requires mesh.boundary_edges")
    owners = {}
    for tri in triangles:
        for a, b, c in ((tri[0], tri[1], tri[2]), (tri[1], tri[2], tri[0]),
                        (tri[2], tri[0], tri[1])):
            owners.setdefault(tuple(sorted((int(a), int(b)))), []).append(int(c))
    selected, seen = [], set()
    # Validate the complete selection before evaluating any user callbacks.
    for tag, field in traction.items():
        if not isinstance(tag, str) or tag not in mesh.boundary_edges:
            raise ValueError(f"traction tag {tag!r} has no boundary_edges definition")
        edges = np.asarray(mesh.boundary_edges[tag])
        if (edges.ndim != 2 or edges.shape[1] != 2 or not len(edges)
                or edges.dtype.kind not in "iu"):
            raise ValueError(f"boundary_edges[{tag!r}] must be nonempty integer (E, 2)")
        if np.any(edges < 0) or np.any(edges >= len(p)):
            raise ValueError(f"boundary_edges[{tag!r}] index out of range")
        opposite = []
        for a, b in edges:
            key = tuple(sorted((int(a), int(b))))
            if a == b:
                raise ValueError("traction edge must have nonzero length")
            if key not in owners or len(owners[key]) != 1:
                raise ValueError("traction edges must be exterior triangle edges with one owner")
            if key in seen:
                raise ValueError("duplicate traction edge within or between selected tags")
            seen.add(key)
            opposite.append(owners[key][0])
        selected.append((edges, np.asarray(opposite), field))
    z, w = np.polynomial.legendre.leggauss(4)
    s, weights = (z+1)/2, w/2
    shape = np.column_stack([1-s, s])
    for edges, opposite, field in selected:
        tangent = p[edges[:, 1]]-p[edges[:, 0]]
        length = np.linalg.norm(tangent, axis=1)
        normals = np.column_stack([tangent[:, 1], -tangent[:, 0]]) / length[:, None]
        # Point away from the unique owning triangle, including into holes.
        inward = np.einsum("ed,ed->e", normals, p[opposite]-p[edges[:, 0]]) > 0
        normals[inward] *= -1
        points = np.einsum("qa,ead->eqd", shape, p[edges])
        if callable(field):
            value = real_array(field(points.reshape(-1, 2),
                                np.repeat(normals, len(weights), axis=0)), "traction callable")
            if value.shape != (points.shape[0]*points.shape[1], 2):
                raise ValueError("traction callable must return shape (Q, 2)")
            value = value.reshape(points.shape)
        else:
            value = real_array(field, "traction vector")
            if value.shape != (2,):
                raise ValueError("constant traction must be a global Cartesian vector of shape (2,)")
            value = np.broadcast_to(value, points.shape)
        fe = np.einsum("qa,q,eqd,e->ead", shape, weights, value, length)
        np.add.at(load, edges.ravel(), fe.reshape(-1, 2))
    if not np.all(np.isfinite(load)):
        raise ValueError("assembled traction load exceeds floating-point range")
    return load.ravel()
