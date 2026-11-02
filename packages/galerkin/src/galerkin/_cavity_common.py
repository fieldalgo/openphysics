# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""What the cavity solvers share: the speed of light, numerical gates, the box mesh,
the normalization of an external mesh and the discrete gradient space.

Package-private: galerkin.cavity and galerkin.material_cavity import these
names so that neither imports the other's private helpers.

Gradient kernel on a general mesh
---------------------------------
On free edges (those in no constrained face) the curl-curl operator has the
kernel ``{grad phi}`` of nodal potentials whose edge differences vanish on
every constrained edge: phi is constant on each connected component of the
constrained surface (nodes joined by constrained edges). Constants map to zero,
so with ``n_free`` unconstrained nodes and ``C`` components the kernel has
dimension ``n_free + max(C, 1) - 1``, provided every curl-free free field is a
discrete gradient (a simply connected domain; an unconstrained hole adds
harmonic fields). On the PEC box this is the number of interior nodes, the
count the box solvers always used. A basis: one unit potential per
unconstrained node (one dropped when nothing is constrained) and the indicator
of every component but the first.
"""
import numpy as np
import scipy.sparse as sp
from scipy.sparse.csgraph import connected_components

from .core.checks import contains_live, positive_integer, positive_real
from .core.spaces import edge_ids
from .mesh3d import Mesh3D, box_mesh, tag_faces_by_node_sets

_FACE_EDGES = ((0, 1), (0, 2), (1, 2))

C0 = 299792458.0
RESIDUAL_LIMIT = 1e-8
GRADIENT_LIMIT = 1e-9
DENSE_LIMIT = 256


def cavity_mesh(lengths, cells):
    """Alternate Kuhn diagonals without changing cells, vertices or tet shapes.

    Reflect local coordinates along axis a whenever the cell index on a is odd.
    Two cells sharing a face have the same tangential parities, hence the same
    face diagonal: this is a conforming triangulation. Even subdivision counts
    restore coordinate-reflection symmetry across the box. No refinement or
    spectral information enters the mesh construction.
    """
    base = box_mesh(*lengths, *cells)
    shape = tuple(n + 1 for n in cells)
    grid = np.stack(np.unravel_index(base.tets, shape), axis=-1)
    lower = grid.min(axis=1)[:, None, :]
    local = grid - lower
    reflected = lower + np.where(lower % 2, 1 - local, local)
    tets = (reflected[:, :, 0] * shape[1] + reflected[:, :, 1]) * shape[2] + reflected[:, :, 2]
    mesh = Mesh3D(base.nodes, tets, base.boundary, base.regions, base.region_names)
    mesh.tagged_faces = tag_faces_by_node_sets(mesh, base.boundary)   # diagonals moved
    return mesh


def face_edge_ids(space, faces):
    """Sorted global ids of every edge of the given (F, 3) faces."""
    faces = np.asarray(faces, dtype=int).reshape(-1, 3)
    if not len(faces):
        return np.array([], dtype=int)
    pairs = np.concatenate([faces[:, list(e)] for e in _FACE_EDGES])
    return np.unique(edge_ids(space, pairs))


def gradient_potentials(mesh, constrained_faces):
    """Potential basis whose gradients span the curl-curl kernel on the free edges.

    Returns ``(unit_nodes, components, kernel_count)``: unit potentials sit on
    ``unit_nodes`` (sorted ascending), ``components`` lists the node arrays of
    every constrained-surface component but the first, and ``kernel_count`` is
    the kernel dimension of the module docstring. With every exterior face
    constrained and a connected boundary, ``unit_nodes`` are exactly the interior
    nodes and ``components`` is empty.
    """
    faces = np.asarray(constrained_faces, dtype=int).reshape(-1, 3)
    n = mesh.num_nodes
    if not len(faces):
        return np.arange(1, n), [], n - 1
    nodes = np.unique(faces)
    unit = np.setdiff1d(np.arange(n), nodes)
    pairs = np.concatenate([faces[:, list(e)] for e in _FACE_EDGES])
    graph = sp.coo_matrix((np.ones(len(pairs)), (pairs[:, 0], pairs[:, 1])), shape=(n, n))
    count, labels = connected_components(graph, directed=False)
    # Labels of the constrained nodes only; unconstrained nodes are isolated vertices.
    present = np.unique(labels[nodes])
    components = [nodes[labels[nodes] == label] for label in present[1:]]
    return unit, components, len(unit) + len(present) - 1


def gradient_incidence(space, free, unit_nodes, components):
    """Sparse (len(free), K) map from the potential basis to free-edge circulations."""
    mesh = space.mesh
    incidence = sp.coo_matrix(
        (np.tile([-1.0, 1.0], len(free)),
         (np.repeat(np.arange(len(free)), 2), space.edges[free].ravel())),
        shape=(len(free), mesh.num_nodes)).tocsc()
    if not components:
        return incidence[:, unit_nodes]
    rows = np.concatenate([unit_nodes] + components)
    cols = np.concatenate([np.arange(len(unit_nodes))]
                          + [np.full(len(c), len(unit_nodes) + k) for k, c in enumerate(components)])
    basis = sp.coo_matrix((np.ones(len(rows)), (rows, cols)),
                          shape=(mesh.num_nodes, len(unit_nodes) + len(components))).tocsc()
    return (incidence @ basis).tocsc()


def refuse_live_mesh_inputs(name, *values):
    """TypeError for JAX or PyTorch values: only the box solvers carry derivatives."""
    for value in values:
        if contains_live(value):
            raise TypeError(f"{name} runs on NumPy and carries no derivative; pass NumPy numbers. "
                            "Derivatives with respect to the geometry are available only from the "
                            "box solver's lengths_m")


def normalized_mesh(mesh, name):
    """Checked external mesh scaled by its longest bounding-box edge.

    Returns ``(normalized Mesh3D, length_scale, normalized bounding-box lengths)``.
    The mesh must carry tagged faces that satisfy ``Mesh3D.check``.
    """
    if not isinstance(mesh, Mesh3D):
        raise TypeError(f"{name} takes a galerkin.Mesh3D (use from_mesher for a mesher's output)")
    if not mesh.tagged_faces:
        raise ValueError(f"{name} needs tagged boundary faces (mesh.tagged_faces); build the mesh "
                         "through from_mesher, box_mesh or Mesh3D(..., tagged_faces=...)")
    mesh.check()
    if not np.isfinite(mesh.nodes).all():
        raise ValueError("mesh nodes must be finite")
    extent = mesh.nodes.max(axis=0) - mesh.nodes.min(axis=0)
    if not (extent > 0).all():
        raise ValueError("the mesh is flat along one axis")
    length_scale = float(extent.max())
    scaled = Mesh3D(mesh.nodes / length_scale, mesh.tets.copy(), mesh.boundary, mesh.regions,
                    mesh.region_names, tagged_faces=mesh.tagged_faces, interfaces=mesh.interfaces)
    return scaled, length_scale, extent / length_scale


def face_tags(mesh, tags, name):
    """The requested tag names as a tuple, each one carried by the mesh."""
    if isinstance(tags, str):
        tags = (tags,)
    try:
        tags = tuple(tags)
    except TypeError:
        raise ValueError(f"{name} must be a sequence of face tag names") from None
    unknown = [t for t in tags if t not in mesh.tagged_faces]
    if unknown:
        raise ValueError(f"{name}: unknown face tag(s) {unknown}; this mesh carries "
                         f"{sorted(mesh.tagged_faces)}")
    if len(set(tags)) != len(tags):
        raise ValueError(f"{name} repeats a tag")
    return tags


def search_parameters(normalized_lengths, length_scale, target_frequency_hz, num_modes):
    """Checked ``(count, target, sigma, fundamental, eigenvalue_scale, field_scale)``.

    sigma is the normalized squared wave number of the target, fundamental the
    lowest TE resonance of the normalized bounding box (the kernel cutoff
    reference) and the two scales turn normalized results into SI.
    """
    count = positive_integer(num_modes, "num_modes")
    target = positive_real(target_frequency_hz, "target_frequency_hz")
    with np.errstate(over="ignore", under="ignore", divide="ignore", invalid="ignore"):
        target_k = (2 * np.pi / C0) * target * length_scale
        sigma = target_k * target_k
        fundamental = np.pi**2 * np.sort(1 / np.asarray(normalized_lengths)**2)[:2].sum()
        eigenvalue_scale = 1 / np.float64(length_scale)**2
        field_scale = np.float64(length_scale)**-1.5
    if (not np.isfinite([sigma, fundamental, eigenvalue_scale, field_scale]).all()
            or min(sigma, eigenvalue_scale, field_scale) <= 0):
        raise ValueError("box lengths and target exceed the supported floating-point range")
    return count, target, sigma, fundamental, eigenvalue_scale, field_scale
