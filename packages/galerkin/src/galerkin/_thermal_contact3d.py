# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Matched P1 thermal contact between independently numbered tetrahedral surfaces."""
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass

import numpy as np
import scipy.sparse as sp
from scipy.sparse.csgraph import connected_components

from .core.checks import finite_scalar
from .core.solve import scipy_solve_dirichlet
from .mesh3d import _face_keys


def _surface(mesh, tag, coord_ids, exterior, used):
    """Order nodes within each triangle, and triangles on the trace, by position."""
    faces = mesh.tagged_faces.get(tag)
    if faces is None or not len(faces):
        raise ValueError(f"thermal contact needs a nonempty exterior face tag, got {tag!r}")
    node_keys, parity = _face_keys(faces)
    for face, winding in zip(node_keys, parity):
        key = tuple(face)
        if exterior.get(key) != winding:
            raise ValueError(f"thermal contact tag {tag!r} needs outward-wound exterior faces")
        if key in used:
            raise ValueError(f"thermal contact tag {tag!r} overlaps a contact, flux or convection face")
        used.add(key)
    nodes = np.unique(faces)
    if np.unique(coord_ids[nodes]).size != nodes.size:
        raise ValueError(f"thermal contact tag {tag!r} has ambiguous coincident nodes")
    coordinates = coord_ids[faces]
    keys, winding = _face_keys(coordinates)
    order = np.lexsort(keys.T[::-1])
    ordered_nodes = np.take_along_axis(faces, np.argsort(coordinates, axis=1), axis=1)
    return keys[order], ordered_nodes[order], winding[order]


def contact_faces(mesh, values, natural):
    if values is None:
        return None
    if not isinstance(values, Mapping):
        raise ValueError("thermal_contact_conductance must map pairs of exterior face tags to conductance")
    if not values:
        return None
    volumes = mesh.volumes()
    if not np.all(np.isfinite(mesh.nodes)) or not np.all(np.isfinite(volumes) & (volumes > 0)):
        raise ValueError("thermal contact requires finite coordinates and positive tetrahedron volumes")
    boundary = mesh.outward_boundary_faces()
    node_keys, parity = _face_keys(boundary)
    exterior = dict(zip(map(tuple, node_keys), parity))
    nodes = np.unique(boundary)
    coord_ids = np.full(mesh.num_nodes, -1, dtype=int)
    _, inverse = np.unique(mesh.nodes[nodes], axis=0, return_inverse=True)
    coord_ids[nodes] = inverse.ravel()
    # A third exterior sheet through the same triangle makes a two-sided
    # contact ambiguous, even if the third sheet was not named in the pair.
    multiplicity = Counter(map(tuple, np.sort(coord_ids[boundary], axis=1)))
    used = {tuple(face) for _, faces, _, _ in natural for face in np.sort(faces, axis=1)}
    left, right, weights = [], [], []
    for pair, value in values.items():
        if (not isinstance(pair, tuple) or len(pair) != 2 or any(not isinstance(tag, str) for tag in pair)
                or pair[0] == pair[1]):
            raise ValueError("thermal_contact_conductance keys must be pairs of distinct exterior face tags")
        h = finite_scalar(value, "thermal_contact_conductance")
        if h < 0:
            raise ValueError("thermal_contact_conductance must be nonnegative")
        a_key, a, a_winding = _surface(mesh, pair[0], coord_ids, exterior, used)
        b_key, b, b_winding = _surface(mesh, pair[1], coord_ids, exterior, used)
        if not np.array_equal(a_key, b_key):
            raise ValueError(f"thermal contact {pair!r} needs exactly matching coincident triangles")
        if np.intersect1d(a, b).size:
            raise ValueError(f"thermal contact {pair!r} requires independent node numbers on each side")
        if np.any(a_winding == b_winding) or any(multiplicity[tuple(key)] != 2 for key in a_key):
            raise ValueError(f"thermal contact {pair!r} needs exactly two oppositely oriented exterior sheets")
        points = mesh.nodes[a]
        area = 0.5 * np.linalg.norm(np.cross(points[:, 1] - points[:, 0],
                                            points[:, 2] - points[:, 0]), axis=1)
        weight = h * (area / 12)
        if (not np.all(np.isfinite(area) & (area > 0)) or not np.all(np.isfinite(weight))
                or (h > 0 and np.any(weight == 0))):
            raise ValueError(f"thermal contact {pair!r} area or coefficient exceeds floating-point range")
        left.append(a)
        right.append(b)
        weights.append(weight)
    return ContactFaces(np.concatenate(left), np.concatenate(right), np.concatenate(weights))


@dataclass
class ContactFaces:
    left: np.ndarray
    right: np.ndarray
    weight: np.ndarray  # h A / 12 for each aligned pair of triangles

    def graph(self, size, active):
        a, b = self.left[active].ravel(), self.right[active].ravel()
        return sp.coo_matrix((np.ones(len(a), dtype=bool), (a, b)), shape=(size, size)).tocsr()

    def strong_faces(self, stiffness):
        # Choose coordinates by comparing the integrated interface conductance
        # with the local conducting solid (both in W/K). All positive contacts
        # enter the same physical equations, whichever coordinates are used.
        diagonal = stiffness.diagonal()
        bulk_scale = np.minimum(diagonal[self.left].max(axis=1), diagonal[self.right].max(axis=1))
        return (self.weight > 0) & (self.weight >= bulk_scale / 12)

    def solve(self, stiffness, rhs, prescribed, links, offsets, regions, anchored):
        # In each set of coincident, conductively linked nodes, keep one
        # temperature and a difference from it for every other node. Large h
        # then acts only on the jumps and cannot cancel the bulk stiffness in
        # the common-temperature equation. Choose a prescribed reference when
        # possible so that every Dirichlet constraint still fixes a single DOF.
        size = len(rhs)
        count, group = connected_components(links, directed=False)
        nodes = np.arange(size)
        roots = np.full(count, size)
        np.minimum.at(roots, group, nodes)
        for node in prescribed:
            roots[group[node]] = node
        root = roots[group]
        different = root != nodes
        coupled = nodes[different]
        transform = sp.eye(size, format="csr") + sp.csr_matrix(
            (np.ones(len(coupled)), (coupled, root[coupled])), shape=stiffness.shape)
        matrix = (transform.T @ stiffness @ transform).tocsr()

        # A body anchored only through weak contacts has a uniform-temperature
        # mode. Give it its own unknown: bulk conduction annihilates that mode
        # exactly. This retains a tiny contact conductance on the pivot even
        # when adding it directly to the solid's diagonal would round it away.
        floating = nodes[~different & ~anchored[regions]]
        pivot = np.full(len(anchored), size)
        np.minimum.at(pivot, regions[floating], floating)
        pivots = pivot[~anchored]
        if len(pivots):
            keep = np.ones(size)
            keep[pivots] = 0
            other = floating[floating != pivot[regions[floating]]]
            translate = sp.eye(size, format="csr") + sp.csr_matrix(
                (np.ones(len(other)), (other, pivot[regions[other]])), shape=stiffness.shape)
            transform = transform @ translate
            matrix = sp.diags(keep) @ matrix @ sp.diags(keep)

        active = self.weight > 0
        a, b = self.left[active].ravel(), self.right[active].ravel()
        side = sp.csr_matrix((np.tile([1., -1.], len(a)),
                              (np.repeat(np.arange(len(a)), 2), np.column_stack((a, b)).ravel())),
                             shape=(len(a), size))
        # Expanding Bᵀ H B with B = [I, -I] gives the four signed face blocks.
        # Taking differences of the basis first cancels a common temperature
        # exactly. H is the consistent P1 face mass h A (I + 11ᵀ) / 12.
        face_mass = sp.kron(sp.diags(self.weight[active]), np.eye(3) + np.ones((3, 3)), format="csr")
        jumps = side @ transform
        offset_jump = offsets[a] - offsets[b]
        matrix += jumps.T @ face_mass @ jumps
        load = transform.T @ rhs - jumps.T @ (face_mass @ offset_jump)
        if not np.all(np.isfinite(matrix.data)) or not np.all(np.isfinite(load)):
            raise ValueError("assembled thermal contact system exceeds floating-point range")
        fixed = {node: (value - prescribed[root[node]] if different[node] else value)
                 for node, value in prescribed.items()}
        solution = scipy_solve_dirichlet(matrix, load, fixed, factor=True)
        temperature = transform @ solution
        rate = side.T @ (face_mass @ (jumps @ solution + offset_jump))
        # Remove the uniform modes before recovering bulk flux and residuals.
        solution[pivots] = 0
        bulk_temperature = transform @ solution
        return temperature, bulk_temperature, rate
