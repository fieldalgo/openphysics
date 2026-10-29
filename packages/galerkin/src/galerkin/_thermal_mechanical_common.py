# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""What the heat-to-mechanics workflows share: isolating their inputs from the caller.

A workflow copies the caller's mesh once (``isolated_mesh``), records its state
(``mesh_state``) and checks that the copy is unchanged between stages
(``check_mesh_unchanged``). ``dirichlet_supports`` validates scalar or
(node, component) Dirichlet mappings before any stage runs.

Package-private: galerkin.thermal_mechanical and
galerkin.transient_thermal_mechanical import these names so that neither
imports the other's private helpers.
"""
from collections.abc import Mapping
import copy

import numpy as np

from .core.checks import real_array, real_scalar
from .mesh import Mesh


def _integer(value, name):
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, (int, np.integer)):
        raise ValueError(f'{name} must be an integer')
    return int(value)


def dirichlet_supports(mapping, vector=False):
    if not isinstance(mapping, Mapping):
        raise ValueError('Dirichlet data must be a mapping')
    result = {}
    for key, value in mapping.items():
        if vector:
            if not isinstance(key, tuple) or len(key) != 2:
                raise ValueError('mechanical Dirichlet keys must be (node, component)')
            key = tuple(_integer(k, 'mechanical Dirichlet index') for k in key)
            if key[1] not in (0, 1):
                raise ValueError('mechanical component must be 0 or 1')
        else:
            key = _integer(key, 'thermal Dirichlet node')
        result[key] = real_scalar(value, 'Dirichlet value')
    return result


def isolated_mesh(mesh):
    if not isinstance(mesh, Mesh):
        raise ValueError('mesh must be a galerkin.mesh.Mesh with SI coordinates')
    p = real_array(mesh.nodes, 'mesh.nodes')
    t = np.array(mesh.triangles, copy=True)
    if p.ndim != 2 or p.shape[1] != 2 or len(p) < 3:
        raise ValueError('mesh.nodes must have shape (N,2), N>=3')
    if (t.ndim != 2 or t.shape[1] != 3 or not len(t) or t.dtype.kind not in 'iu'
            or np.any(t < 0) or np.any(t >= len(p))):
        raise ValueError('mesh.triangles must be integer (M,3) valid indices before construction')
    q = p[t]
    with np.errstate(over='ignore', invalid='ignore'):
        j = q[:, 1:] - q[:, :1]
        det = j[:, 0, 0]*j[:, 1, 1]-j[:, 0, 1]*j[:, 1, 0]
    if np.any(~np.isfinite(det)) or np.any(det <= 0):
        raise ValueError('raw mesh triangles must be finite, CCW and nondegenerate; no orientation repair')
    def tags(mapping, width):
        if not isinstance(mapping, Mapping):
            raise ValueError('mesh boundary data must be mappings')
        out = {}
        for name, ids in mapping.items():
            a = np.array(ids, copy=True)
            if (not isinstance(name, str) or a.dtype.kind not in 'iu'
                    or a.ndim != (1 if width == 1 else 2)
                    or (width == 2 and a.shape[1] != 2)
                    or np.any(a < 0) or np.any(a >= len(p))):
                raise ValueError('invalid raw boundary tag/index data')
            out[name] = a.astype(np.int64, copy=True)
        return out
    boundary = tags(mesh.boundary, 1)
    edges = tags(mesh.boundary_edges, 2)
    # Geometry/connectivity were checked BEFORE Mesh can cast or flip triangles.
    regions = None if mesh.regions is None else np.array(mesh.regions, copy=True)
    if regions is not None and (regions.shape != (len(t),) or regions.dtype.kind not in 'iu'):
        raise ValueError('mesh.regions must be integer (M,) data when supplied')
    if regions is not None and np.any(regions > np.iinfo(np.int64).max):
        raise ValueError('mesh.regions exceeds integer representation')
    names = copy.deepcopy(mesh.region_names)
    if names is not None and (not isinstance(names, list) or any(not isinstance(v, str) for v in names)):
        raise ValueError('mesh.region_names must be a list of strings when supplied')
    owned = Mesh(p, t.astype(np.int64, copy=True), boundary, edges, regions, names)
    return owned


def mesh_state(mesh):
    return (mesh.nodes.copy(), mesh.triangles.copy(),
            {k: v.copy() for k, v in mesh.boundary.items()},
            {k: v.copy() for k, v in mesh.boundary_edges.items()},
            None if mesh.regions is None else mesh.regions.copy(), copy.deepcopy(mesh.region_names))


def check_mesh_unchanged(mesh, state):
    if not (np.array_equal(mesh.nodes, state[0]) and np.array_equal(mesh.triangles, state[1])):
        raise ValueError('isolated reference mesh changed during workflow')
    if not np.array_equal(mesh.regions, state[4]) or mesh.region_names != state[5]:
        raise ValueError('isolated reference region metadata changed during workflow')
    for actual, expected in ((mesh.boundary, state[2]), (mesh.boundary_edges, state[3])):
        if set(actual) != set(expected) or any(not np.array_equal(actual[k], expected[k]) for k in expected):
            raise ValueError('isolated reference boundary data changed during workflow')
