# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Matched P1 thermal contact between independently numbered tetrahedral surfaces."""
from collections import Counter, defaultdict
from collections.abc import Mapping
from dataclasses import dataclass

import numpy as np
import scipy.sparse as sp
from scipy.sparse.csgraph import connected_components, minimum_spanning_tree

from .core.checks import finite_scalar
from .core.solve import scipy_solve_dirichlet
from .mesh3d import face_keys_and_parity


def _surface(mesh, tag, coord_ids, exterior, used):
    """Order nodes within each triangle, and triangles on the trace, by position."""
    faces = mesh.tagged_faces.get(tag)
    if faces is None or not len(faces):
        raise ValueError(f"thermal contact needs a nonempty exterior face tag, got {tag!r}")
    node_keys, parity = face_keys_and_parity(faces)
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
    keys, winding = face_keys_and_parity(coordinates)
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
    node_keys, parity = face_keys_and_parity(boundary)
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


def _differences(a, b, size):
    """Map nodal temperatures to the ordered trace jumps T[a] - T[b]."""
    return sp.csr_matrix((np.tile([1., -1.], len(a)),
                          (np.repeat(np.arange(len(a)), 2), np.column_stack((a, b)).ravel())),
                         shape=(len(a), size))


def _independent_jumps(a, b, weight, size, fixed):
    """A tree of independent temperature jumps at each coincident junction."""
    pairs, inverse = np.unique(np.sort(np.column_stack((a, b)), axis=1), axis=0, return_inverse=True)
    inverse = inverse.ravel()
    strength = np.zeros(len(pairs))
    np.maximum.at(strength, inverse, weight)
    _, rank = np.unique(strength, return_inverse=True)
    graph = sp.csr_matrix((-1. - rank.ravel(), pairs.T), shape=(size, size))
    if fixed.size:
        # A difference between two fixed nodes is known exactly. Put these
        # differences in the tree first; its remaining rows stay independent
        # after eliminating the prescribed nodal increments.
        groups, labels = connected_components(graph, directed=False)
        anchors = np.full(groups, size)
        np.minimum.at(anchors, labels[fixed], fixed)
        other = fixed[fixed != anchors[labels[fixed]]]
        graph += sp.csr_matrix((np.full(len(other), -2. - rank.max()), (anchors[labels[other]], other)),
                               shape=graph.shape)
    # Prefer the strongest links: a weak link may then be reconstructed from
    # stronger trace jumps, preserving tiny differences across strong links.
    tree = minimum_spanning_tree(graph).tocoo()
    jump = _differences(tree.row, tree.col, size)
    lookup = {(u, v): i for i, (u, v) in enumerate(zip(tree.row, tree.col))}
    adjacency = defaultdict(list)
    for (u, v), i in lookup.items():
        adjacency[u].append((v, i, 1.))
        adjacency[v].append((u, i, -1.))
    rows, cols, data = [], [], []
    for row, (start, end) in enumerate(pairs):
        if (start, end) in lookup:
            path = [(lookup[start, end], 1.)]
        else:
            # Only redundant links at a junction need a path. All vertices
            # reached here are distinct node IDs at the same spatial point.
            stack = [(start, -1, [])]
            while stack:
                node, previous, path = stack.pop()
                if node == end:
                    break
                stack.extend((other, node, path + [(index, sign)]) for other, index, sign in adjacency[node]
                             if other != previous)
        rows.extend([row] * len(path))
        cols.extend(index for index, _ in path)
        data.extend(sign for _, sign in path)
    paths = sp.csr_matrix((data, (rows, cols)), shape=(len(pairs), tree.nnz))
    face_jumps = paths[inverse].multiply(np.where(a < b, 1., -1.)[:, None]).tocsr()
    return jump, face_jumps


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

    def face_operators(self, size, active=None):
        if active is None:
            active = self.weight > 0
        a, b = self.left[active].ravel(), self.right[active].ravel()
        area_mass = sp.kron(sp.diags(self.weight[active]), np.eye(3) + np.ones((3, 3)), format="csr")
        return a, b, _differences(a, b, size), area_mass

    def transient_operators(self, size, fixed, active):
        """Independent jumps and the corresponding consistent nodal exchange.

        The mixed time step solves for nodal increments and interval-end jump
        amplitudes together. Scale each amplitude to keep the contact columns
        bounded even for a nearly perfect contact.
        """
        a, b, side, area_mass = self.face_operators(size, active)
        if not len(a):
            return side, side.T.tocsr(), np.empty(0)
        jump, face_jumps = _independent_jumps(a, b, np.repeat(self.weight[active], 3), size, fixed)
        face_rates = area_mass @ face_jumps
        scale = abs(face_rates).max(axis=0).toarray().ravel()
        if not np.all(np.isfinite(scale) & (scale > 0)):
            raise ValueError("transient contact exchange exceeds floating-point range")
        face_rates = face_rates.tocsr()
        face_rates.data /= scale[face_rates.indices]
        rate = (side.T @ face_rates).tocsr()
        return jump, rate, scale

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

        a, b, side, face_mass = self.face_operators(size)
        # Expanding Bᵀ H B with B = [I, -I] gives the four signed face blocks.
        # Taking differences of the basis first cancels a common temperature
        # exactly. H is the consistent P1 face mass h A (I + 11ᵀ) / 12.
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


class TransientContact:
    """Backward Euler interface equations in nodal increments and interval-end jumps."""

    def __init__(self, faces, mass, initial, free, fixed, longest_step):
        capacity = mass.diagonal()
        face_capacity = np.minimum(capacity[faces.left].min(axis=1), capacity[faces.right].min(axis=1))
        strong = faces.weight > (face_capacity / 12) / longest_step
        # Always-weak faces use their original two traces. At a junction this
        # avoids recovering an extremely small exchange from a difference of
        # larger transfers involving a third body.
        _, _, direct, area_mass = faces.face_operators(len(initial), (faces.weight > 0) & ~strong)
        self.direct_jump = direct[:, free]
        self.direct_transfer = (direct.T @ area_mass).tocsr()
        self.direct_stiffness = self.direct_transfer[free] @ self.direct_jump
        jump, transfer, scale = faces.transient_operators(len(initial), fixed, strong)
        row_scale = np.minimum(1., scale)
        compliance = 1. / np.maximum(1., scale)
        initial_jump = row_scale * (jump @ initial)
        unknown = jump[:, free].getnnz(axis=1) > 0
        # Jumps between two fixed nodes are exact constants. Their consistent
        # mass still acts on neighboring free nodes on the same triangle.
        self.known_rate = transfer[:, ~unknown] @ (initial_jump[~unknown] / compliance[~unknown])
        if not np.all(np.isfinite(self.known_rate)):
            raise ValueError("prescribed thermal contact heat rate exceeds floating-point range")
        self.free = free
        self.state = (direct @ initial, initial_jump[unknown])
        self.transfer = transfer[:, unknown]
        self.transfer_free = self.transfer[free]
        self.jump_free = (sp.diags(row_scale[unknown]) @ jump[unknown][:, free]).tocsr()
        self.compliance = compliance[unknown]
        self.conductance = scale[unknown]
        endpoints = jump[unknown].indices.reshape(-1, 2)
        self.capacity = capacity[endpoints].min(axis=1)

    def system(self, dt, bulk):
        # A dT + F y = net, J dT - C y = -previous_jump, where F y
        # is the nodal exchange. Eliminate y for links weaker than the
        # capacity rate. Their tiny heat rates then remain accurate even if
        # another body carries a much larger load. For strong links y stays
        # independent, preserving a finite rate across a sub-ulp jump.
        bulk = bulk + self.direct_stiffness
        weak = self.conductance <= self.capacity / dt
        if weak.any():
            bulk = bulk + self.transfer_free[:, weak] @ sp.diags(1. / self.compliance[weak]) @ self.jump_free[weak]
        strong = ~weak
        if strong.any():
            bulk = sp.bmat([[bulk, self.transfer_free[:, strong]],
                            [self.jump_free[strong], -sp.diags(self.compliance[strong])]], format="csc")
        return bulk.tocsc(), weak

    def advance(self, factor, weak, rhs, interval):
        strong = ~weak
        previous_direct, previous_jump = self.state
        rhs_free = rhs[self.free] - (self.known_rate + self.direct_transfer @ previous_direct)[self.free]
        if weak.any():
            rhs_free -= self.transfer_free[:, weak] @ (previous_jump[weak] / self.compliance[weak])
        solution = factor.solve(np.concatenate((rhs_free, -previous_jump[strong]))) if factor else np.empty(0)
        delta = solution[:len(self.free)]
        change = self.jump_free @ delta
        amplitudes = np.empty_like(previous_jump)
        amplitudes[weak] = (previous_jump[weak] + change[weak]) / self.compliance[weak]
        amplitudes[strong] = solution[len(self.free):]
        next_jump = self.compliance * amplitudes
        scale = abs(self.jump_free) @ np.abs(delta) + np.abs(previous_jump) + np.abs(next_jump)
        if (not np.all(np.isfinite(scale)) or np.max(np.abs(change + previous_jump - next_jump), initial=0.)
                > 1e-10 * np.max(scale, initial=0.)):
            raise ValueError(f"transient thermal contact failed jump compatibility on interval {interval}")
        next_direct = previous_direct + self.direct_jump @ delta
        rate = self.direct_transfer @ next_direct + self.transfer @ amplitudes + self.known_rate
        return delta, (next_direct, next_jump), rate
