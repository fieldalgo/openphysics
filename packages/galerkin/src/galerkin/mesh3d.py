# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Tetrahedral mesh data structure and a structured generator for boxes.

The 3D counterpart of mesh.py. What changes going from triangles to tetrahedra:

  - an element has four vertices and six edges instead of three and three
  - orientation is a sign of a 3x3 determinant rather than of a cross product
  - "the boundary" is a set of triangular faces, and an edge lies on the boundary
    only if it lies *in* one of those faces. In 2D "both endpoints on the
    boundary" was equivalent; in 3D it is not — an edge can join two boundary
    nodes while passing through the interior — and getting that wrong silently
    over-constrains a PEC problem.

Tagged boundary faces follow the contract shared with meshine and gmshio
(docs/packages/galerkin/mesh3d_format.md): ``tagged_faces`` maps a name to
(F, 3) exterior faces wound so that their normal points out of the domain, every
exterior face carries exactly one tag, and the node sets in ``boundary`` are the
nodes of those faces. ``check`` verifies the rules; ``from_mesher`` runs it on
every mesh that arrives with faces.

Boxes are triangulated in-house with the Kuhn (Freudenthal) subdivision: each
cube is cut into six tetrahedra, one per ordering of the three axis directions,
each following a monotone path from the (0,0,0) corner to the (1,1,1) corner.
Neighbouring cubes then agree face for face, so the mesh is conforming without
any bookkeeping, and the subdivision is self-similar, so element quality does not
degrade under refinement.
"""

from __future__ import annotations

from itertools import permutations

import numpy as np


# Faces opposite local vertex 0..3, wound so that the normal points out of a
# positively oriented tetrahedron (volume (p1-p0).((p2-p0)x(p3-p0)) > 0).
OUTWARD_FACES = np.array([[1, 2, 3], [0, 3, 2], [0, 1, 3], [0, 2, 1]])


class MeshCheckError(ValueError):
    """A ``Mesh3D`` breaks the tetrahedral mesh contract; ``problems`` lists every violation."""

    def __init__(self, problems):
        self.problems = list(problems)
        super().__init__("tetrahedral mesh contract violated:\n- " + "\n- ".join(self.problems))


def _face_keys(faces):
    """Sorted node triples (F, 3) and the winding parity (F,) of each face (0 even, 1 odd)."""
    f = np.asarray(faces, dtype=np.int64).reshape(-1, 3)
    a, b, c = f[:, 0], f[:, 1], f[:, 2]
    parity = ((a > b).astype(np.int64) + (a > c) + (b > c)) % 2
    return np.sort(f, axis=1), parity


class Mesh3D:
    """Tetrahedral mesh: nodes (N, 3), tets (T, 4), optional regions and tagged boundary.

    boundary: {name: node ids} (kept for compatibility; derived from the faces
        when ``tagged_faces`` is given and ``boundary`` is not).
    tagged_faces: {name: (F, 3)} exterior faces, outward-wound, each exterior face
        tagged exactly once. The accessor method ``boundary_faces()`` keeps its
        meaning: every exterior face, untagged and sorted.
    regions, region_names: per-tetrahedron region id into region_names; ids are
        refused outside [0, len(region_names)) and negative ids always.
    interfaces: optional {(a, b): (F, 3)} faces between two regions, as the
        mesher hands them over; stored, not verified.
    """

    def __init__(self, nodes: np.ndarray, tets: np.ndarray,
                 boundary: dict[str, np.ndarray] | None = None,
                 regions: np.ndarray | None = None,
                 region_names: list[str] | None = None,
                 tagged_faces: dict[str, np.ndarray] | None = None,
                 interfaces: dict | None = None):
        self.nodes = np.asarray(nodes, dtype=float)
        self.tets = np.asarray(tets, dtype=int)
        if self.nodes.ndim != 2 or self.nodes.shape[1] != 3:
            raise ValueError(f"nodes must be an (N, 3) array, got shape {self.nodes.shape}")
        if self.tets.ndim != 2 or self.tets.shape[1] != 4:
            raise ValueError(f"tets must be a (T, 4) array, got shape {self.tets.shape}")
        self.tagged_faces = {str(k): np.asarray(v, dtype=int).reshape(-1, 3)
                             for k, v in (tagged_faces or {}).items()}
        if boundary is None and tagged_faces is not None:
            boundary = {k: np.unique(v) for k, v in self.tagged_faces.items()}
        self.boundary = {k: np.asarray(v, dtype=int)
                         for k, v in (boundary or {}).items()}
        self.regions = (None if regions is None
                        else np.asarray(regions, dtype=int))
        self.region_names = list(region_names) if region_names is not None else None
        self.interfaces = {tuple(k): np.asarray(v, dtype=int).reshape(-1, 3)
                           for k, v in (interfaces or {}).items()}
        self._faces = None
        self._check_regions()
        self._fix_orientation()   # reorders vertices only, so regions stays aligned

    def _check_regions(self):
        """Cheap input checks that need no face sort: region ids and names."""
        if self.regions is None:
            return
        if self.regions.shape != (len(self.tets),):
            raise ValueError(f"regions must hold one id per tetrahedron: got shape "
                             f"{self.regions.shape} for {len(self.tets)} tetrahedra")
        negative = int(np.count_nonzero(self.regions < 0))
        if negative:
            raise ValueError(
                f"{negative} tetrahedra carry a negative region id (a mesher marks tetrahedra "
                "outside every named volume this way); tag every volume or drop them "
                "before building the mesh")
        if self.region_names is not None:
            names = self.region_names
            if not all(isinstance(n, str) for n in names) or len(set(names)) != len(names):
                raise ValueError("region_names must be unique strings")
            if len(self.regions) and self.regions.max() >= len(names):
                raise ValueError(f"region ids must lie in [0, {len(names)}) = "
                                 f"range(len(region_names)); got {self.regions.max()}")

    @property
    def num_nodes(self) -> int:
        return len(self.nodes)

    @property
    def num_tets(self) -> int:
        return len(self.tets)

    def _edge_matrix(self) -> np.ndarray:
        """(T, 3, 3) with rows p1-p0, p2-p0, p3-p0."""
        p = self.nodes[self.tets]
        return np.stack([p[:, 1] - p[:, 0], p[:, 2] - p[:, 0], p[:, 3] - p[:, 0]],
                        axis=1)

    def _fix_orientation(self):
        """Swap two vertices so that every tetrahedron has a positive volume."""
        flipped = np.linalg.det(self._edge_matrix()) < 0.0
        self.tets[flipped] = self.tets[flipped][:, [0, 1, 3, 2]]

    def volumes(self) -> np.ndarray:
        return np.abs(np.linalg.det(self._edge_matrix())) / 6.0

    def by_region(self, values) -> np.ndarray:
        """Per-tetrahedron coefficient array from one value per material region.

        values: a {region name: value} mapping, or a sequence indexed by region id.
        """
        if self.regions is None:
            raise ValueError("this mesh carries no region information")
        if len(self.regions) and self.regions.min() < 0:
            raise ValueError("mesh.regions holds negative ids; they index no region")
        if isinstance(values, dict):
            if self.region_names is None:
                raise ValueError("this mesh has no region names to look up")
            missing = set(self.region_names) - set(values)
            if missing:
                raise KeyError(f"no value given for region(s) {sorted(missing)}")
            values = [values[name] for name in self.region_names]
        table = np.asarray(values)
        if len(self.regions) and self.regions.max() >= len(table):
            raise ValueError(f"region id {self.regions.max()} has no entry among {len(table)} values")
        return table[self.regions]

    def dihedral_angles(self) -> np.ndarray:
        """(T, 6) interior dihedral angles in degrees, one per edge.

        Interpolation accuracy on a tetrahedron is governed by the MAXIMUM angle,
        not the minimum: slender elements are harmless as long as they do not
        flatten. Face normals are turned outward by pointing each away from the
        vertex it faces, so the angles come out interior rather than mixed.
        """
        p = self.nodes[self.tets]
        opposite = [(1, 2, 3), (0, 2, 3), (0, 1, 3), (0, 1, 2)]
        n = np.empty((self.num_tets, 4, 3))
        for i, (a, b, c) in enumerate(opposite):
            nv = np.cross(p[:, b] - p[:, a], p[:, c] - p[:, a])
            nv /= np.linalg.norm(nv, axis=1)[:, None]
            inward = np.einsum("td,td->t", nv, p[:, i] - p[:, a]) > 0
            nv[inward] *= -1.0
            n[:, i] = nv
        ang = [180.0 - np.degrees(np.arccos(np.clip(
                   np.einsum("td,td->t", n[:, i], n[:, j]), -1.0, 1.0)))
               for i in range(4) for j in range(i + 1, 4)]
        return np.stack(ang, axis=1)

    def faces(self):
        """(unique sorted faces, how many tetrahedra each belongs to)."""
        if self._faces is None:
            t = self.tets
            f = np.concatenate([t[:, [1, 2, 3]], t[:, [0, 2, 3]],
                                t[:, [0, 1, 3]], t[:, [0, 1, 2]]])
            self._faces = np.unique(np.sort(f, axis=1), axis=0, return_counts=True)
        return self._faces

    def boundary_faces(self) -> np.ndarray:
        """(F, 3) faces belonging to exactly one tetrahedron, sorted node triples (no tag)."""
        uniq, count = self.faces()
        return uniq[count == 1]

    def boundary_nodes(self) -> np.ndarray:
        return np.unique(self.boundary_faces())

    def outward_boundary_faces(self) -> np.ndarray:
        """(F, 3) exterior faces wound so that the normal points out of the domain.

        Every tetrahedron is positively oriented after construction, so the face
        opposite each vertex, read from ``OUTWARD_FACES``, is outward-wound.
        """
        f = self.tets[:, OUTWARD_FACES].reshape(-1, 3)
        _, first, count = np.unique(np.sort(f, axis=1), axis=0, return_index=True,
                                    return_counts=True)
        return f[first[count == 1]]

    def validate(self) -> list[str]:
        """Every violation of the tagged-face contract (empty when the mesh satisfies it).

        Rules (shared with meshine's ``TetMesh`` and gmshio's ``FemMesh3D``): the
        tagged faces are exactly the exterior faces, each tagged once and wound
        outward; ``boundary[tag]`` is the node set of ``tagged_faces[tag]``. A mesh
        without tagged faces passes (node sets alone carry no face information).
        """
        problems = []
        if len(self.tets) and (self.tets.min() < 0 or self.tets.max() >= self.num_nodes):
            return [f"tets reference node indices outside [0, {self.num_nodes})"]
        if not self.tagged_faces:
            return problems
        for tag, arr in self.tagged_faces.items():
            if len(arr) and (arr.min() < 0 or arr.max() >= self.num_nodes):
                problems.append(f"tagged_faces[{tag!r}] references node indices outside "
                                f"[0, {self.num_nodes})")
        if problems:
            return problems
        exterior = self.outward_boundary_faces()
        ext_key, ext_parity = _face_keys(exterior)
        tags = list(self.tagged_faces)
        given = np.concatenate([self.tagged_faces[t] for t in tags]) if tags else np.zeros((0, 3), int)
        owner = np.repeat(np.arange(len(tags)), [len(self.tagged_faces[t]) for t in tags])
        giv_key, giv_parity = _face_keys(given)
        both = np.concatenate([ext_key, giv_key])
        _, inverse = np.unique(both, axis=0, return_inverse=True)
        inverse = inverse.reshape(-1)
        ext_id, giv_id = inverse[:len(ext_key)], inverse[len(ext_key):]
        # Exterior face id -> position; -1 for a tagged face that is not exterior.
        position = np.full(inverse.max(initial=-1) + 1, -1)
        position[ext_id] = np.arange(len(ext_id))
        where = position[giv_id]
        not_exterior = where < 0
        if not_exterior.any():
            n = int(not_exterior.sum())
            example = given[not_exterior][:3].tolist()
            problems.append(f"{n} tagged faces are not exterior faces (interior or unknown), "
                            f"e.g. {example}")
        hits = np.bincount(where[~not_exterior], minlength=len(ext_key))
        untagged = int(np.count_nonzero(hits == 0))
        if untagged:
            example = exterior[hits == 0][:3].tolist()
            problems.append(f"{untagged} exterior faces carry no tag, e.g. {example}")
        doubled = np.flatnonzero(hits > 1)
        if len(doubled):
            face = exterior[doubled[0]].tolist()
            names = sorted({tags[o] for o in owner[~not_exterior][where[~not_exterior] == doubled[0]]})
            problems.append(f"{len(doubled)} exterior faces are tagged more than once, "
                            f"e.g. {face} by {names}")
        ok = ~not_exterior
        inward = giv_parity[ok] != ext_parity[where[ok]]
        if inward.any():
            n = int(inward.sum())
            problems.append(f"{n} tagged faces are wound inward (normal points into the "
                            f"domain), e.g. {given[ok][inward][:3].tolist()}")
        if set(self.boundary) != set(self.tagged_faces):
            problems.append("boundary (node sets) and tagged_faces have different tags: "
                            f"{sorted(set(self.boundary) ^ set(self.tagged_faces))}")
        for tag in tags:
            if tag in self.boundary and not np.array_equal(
                    np.unique(self.boundary[tag]), np.unique(self.tagged_faces[tag])):
                problems.append(f"boundary[{tag!r}] is not the node set of tagged_faces[{tag!r}]")
        return problems

    def check(self) -> "Mesh3D":
        """Raise ``MeshCheckError`` listing every violation of ``validate``; return the mesh otherwise."""
        problems = self.validate()
        if problems:
            raise MeshCheckError(problems)
        return self

    def faces_tagged(self, *tags) -> np.ndarray:
        """(F, 3) outward-wound faces of the given tags concatenated; unknown tags raise KeyError."""
        unknown = [t for t in tags if t not in self.tagged_faces]
        if unknown:
            raise KeyError(f"unknown face tag(s) {unknown}; this mesh has {sorted(self.tagged_faces)}")
        if not tags:
            return np.zeros((0, 3), dtype=int)
        return np.concatenate([self.tagged_faces[t] for t in tags])


def tag_faces_by_node_sets(mesh: Mesh3D, node_sets: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
    """Outward-wound exterior faces of ``mesh`` grouped by the node set holding all three nodes.

    Each exterior face must lie in exactly one set (a face with all three nodes in
    two sets would be degenerate on a box); otherwise ValueError.
    """
    faces = mesh.outward_boundary_faces()
    out, claimed = {}, np.zeros(len(faces), dtype=int)
    for name, nodes in node_sets.items():
        inside = np.isin(faces, np.asarray(nodes, dtype=int)).all(axis=1)
        out[name] = faces[inside]
        claimed += inside
    if np.any(claimed != 1):
        raise ValueError(f"{int(np.count_nonzero(claimed != 1))} exterior faces lie in no node set "
                         "or in several")
    return out


def box_mesh(lx: float, ly: float, lz: float,
             nx: int, ny: int, nz: int) -> Mesh3D:
    """Kuhn subdivision of [0,lx] x [0,ly] x [0,lz] into 6 nx ny nz tetrahedra.

    Boundary tags: 'x0', 'x1', 'y0', 'y1', 'z0', 'z1', as node sets (``boundary``)
    and outward-wound faces (``tagged_faces``).
    """
    x = np.linspace(0.0, lx, nx + 1)
    y = np.linspace(0.0, ly, ny + 1)
    z = np.linspace(0.0, lz, nz + 1)
    X, Y, Z = np.meshgrid(x, y, z, indexing="ij")
    nodes = np.column_stack([X.ravel(), Y.ravel(), Z.ravel()])

    def nid(i, j, k):
        return (i * (ny + 1) + j) * (nz + 1) + k

    I, J, K = (a.ravel() for a in np.meshgrid(np.arange(nx), np.arange(ny),
                                              np.arange(nz), indexing="ij"))
    tets = []
    for order in permutations(range(3)):
        # cumulative unit steps along the axes in this order: (0,0,0) -> (1,1,1)
        step = np.zeros((4, 3), dtype=int)
        for s, axis in enumerate(order):
            step[s + 1:] += np.eye(3, dtype=int)[axis]
        tets.append(np.stack([nid(I + d[0], J + d[1], K + d[2]) for d in step],
                             axis=1))

    i, j, k = (np.arange(nx + 1), np.arange(ny + 1), np.arange(nz + 1))
    JJ, KK = (a.ravel() for a in np.meshgrid(j, k, indexing="ij"))
    II, KK2 = (a.ravel() for a in np.meshgrid(i, k, indexing="ij"))
    II2, JJ2 = (a.ravel() for a in np.meshgrid(i, j, indexing="ij"))
    boundary = {
        "x0": nid(0, JJ, KK),   "x1": nid(nx, JJ, KK),
        "y0": nid(II, 0, KK2),  "y1": nid(II, ny, KK2),
        "z0": nid(II2, JJ2, 0), "z1": nid(II2, JJ2, nz),
    }
    mesh = Mesh3D(nodes, np.concatenate(tets), boundary,
                  regions=np.zeros(6 * nx * ny * nz, dtype=int),
                  region_names=["domain"])
    mesh.tagged_faces = tag_faces_by_node_sets(mesh, boundary)
    return mesh
