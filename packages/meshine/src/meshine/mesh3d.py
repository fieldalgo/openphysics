# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Tetrahedral mesh contract shared by OpenPhysics's 3D meshers.

``TetMesh`` carries the fields of ``gmshio.FemMesh3D`` that ``galerkin.from_mesher``
reads, plus interfaces. ``check`` verifies the contract exactly (orientation by
exact arithmetic, face counts, tags, winding); ``write_msh`` writes Gmsh MSH 4.1
ASCII without Gmsh. The criteria are in docs/packages/meshine/validation3d.md.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from fractions import Fraction
from pathlib import Path

import numpy as np

# Faces opposite local vertex 0..3, wound so that the normal points out of a
# positively oriented tetrahedron (volume (p1-p0).((p2-p0)x(p3-p0)) > 0).
OUTWARD_FACES = np.array([[1, 2, 3], [0, 3, 2], [0, 1, 3], [0, 2, 1]])
# Local edges and, for each, the two faces (by opposite vertex) that contain it.
EDGES = np.array([[0, 1], [0, 2], [0, 3], [1, 2], [1, 3], [2, 3]])
EDGE_FACES = np.array([[2, 3], [1, 3], [1, 2], [0, 3], [0, 2], [0, 1]])

# Shewchuk's static error bound for orient3d evaluated as below is (7 + 56 eps) eps
# with eps = 2^-53; the factor 8 leaves margin. Below the bound, or near underflow,
# the sign is decided in exact rational arithmetic.
_ORIENT_BOUND = 8.0 * 2.0 ** -53
_TINY = 2.0 ** -900


class MeshCheckError(ValueError):
    """A ``TetMesh`` breaks the output contract; ``problems`` lists every violation."""

    def __init__(self, problems: list[str]):
        self.problems = problems
        super().__init__("tetrahedral mesh contract violated:\n- " + "\n- ".join(problems))


@dataclass
class TetMesh:
    nodes: np.ndarray                              # (N, 3)
    tetrahedra: np.ndarray                         # (T, 4) positive orientation
    regions: np.ndarray                            # (T,) index into region_names
    region_names: list[str]
    boundary_faces: dict[str, np.ndarray]          # name -> (F, 3) outward-wound exterior faces
    boundary_nodes: dict[str, np.ndarray] = field(default_factory=dict)
    interfaces: dict[tuple[str, str], np.ndarray] = field(default_factory=dict)  # (a, b), a < b -> (F, 3) wound a to b

    def __post_init__(self):
        if not self.boundary_nodes:
            self.boundary_nodes = {k: np.unique(v) for k, v in self.boundary_faces.items()}

    # -- geometry / quality --------------------------------------------------

    @property
    def num_nodes(self) -> int:
        return len(self.nodes)

    @property
    def num_tetrahedra(self) -> int:
        return len(self.tetrahedra)

    @property
    def volumes(self) -> np.ndarray:
        p = self.nodes[self.tetrahedra]
        a, b, c = p[:, 1] - p[:, 0], p[:, 2] - p[:, 0], p[:, 3] - p[:, 0]
        return np.einsum("ij,ij->i", a, np.cross(b, c)) / 6.0

    def region_volume(self, name: str) -> float:
        return float(self.volumes[self.regions == self.region_names.index(name)].sum())

    def edge_lengths(self) -> np.ndarray:
        """(T, 6) lengths of the local edges in ``EDGES`` order."""
        p = self.nodes[self.tetrahedra]
        return np.linalg.norm(p[:, EDGES[:, 1]] - p[:, EDGES[:, 0]], axis=2)

    def edges(self) -> np.ndarray:
        """(E, 2) sorted node pairs of the unique mesh edges."""
        e = np.sort(self.tetrahedra[:, EDGES].reshape(-1, 2), axis=1)
        return np.unique(e, axis=0)

    def _face_normals(self) -> tuple[np.ndarray, np.ndarray]:
        """Outward area vectors (T, 4, 3), twice the face area each, and the face areas (T, 4)."""
        p = self.nodes[self.tetrahedra]
        f = p[:, OUTWARD_FACES]                                   # (T, 4, 3 vertices, 3)
        n = np.cross(f[:, :, 1] - f[:, :, 0], f[:, :, 2] - f[:, :, 0])
        return n, 0.5 * np.linalg.norm(n, axis=2)

    def dihedral_angles(self) -> np.ndarray:
        """(T, 6) dihedral angles in degrees at the local edges in ``EDGES`` order."""
        n, _ = self._face_normals()
        n = n / np.linalg.norm(n, axis=2, keepdims=True)
        nk, nl = n[:, EDGE_FACES[:, 0]], n[:, EDGE_FACES[:, 1]]
        sin = np.linalg.norm(np.cross(nk, nl), axis=2)
        cos = -np.einsum("tek,tek->te", nk, nl)
        return np.degrees(np.arctan2(sin, cos))

    def min_dihedral(self) -> float:
        return float(self.dihedral_angles().min())

    def circumradii(self) -> np.ndarray:
        p = self.nodes[self.tetrahedra]
        a, b, c = p[:, 1] - p[:, 0], p[:, 2] - p[:, 0], p[:, 3] - p[:, 0]
        num = (np.einsum("ij,ij->i", a, a)[:, None] * np.cross(b, c)
               + np.einsum("ij,ij->i", b, b)[:, None] * np.cross(c, a)
               + np.einsum("ij,ij->i", c, c)[:, None] * np.cross(a, b))
        return np.linalg.norm(num, axis=1) / (2.0 * np.abs(np.einsum("ij,ij->i", a, np.cross(b, c))))

    def quality(self) -> np.ndarray:
        """Per-tetrahedron radius ratio q = 3 r_in / R in (0, 1]; 1 is the regular tetrahedron."""
        _, areas = self._face_normals()
        r_in = 3.0 * np.abs(self.volumes) / areas.sum(axis=1)
        return 3.0 * r_in / self.circumradii()

    def radius_edge(self) -> np.ndarray:
        """Per-tetrahedron R / shortest edge (0.612 for the regular tetrahedron)."""
        return self.circumradii() / self.edge_lengths().min(axis=1)

    def boundary_face_set(self) -> np.ndarray:
        """(F, 3) outward-wound faces used by exactly one tetrahedron (the topological boundary)."""
        faces, counts, _ = _faces(self.tetrahedra)
        return faces[counts == 1]

    def euler_characteristic(self, region: str | None = None) -> int:
        """V - E + F - T of the tetrahedra of ``region`` (all when None); 1 for a ball."""
        t = self.tetrahedra if region is None else self.tetrahedra[self.regions == self.region_names.index(region)]
        if len(t) == 0:
            return 0
        v = len(np.unique(t))
        e = len(np.unique(np.sort(t[:, EDGES].reshape(-1, 2), axis=1), axis=0))
        f = len(np.unique(np.sort(t[:, OUTWARD_FACES].reshape(-1, 3), axis=1), axis=0))
        return v - e + f - len(t)

    def __repr__(self) -> str:
        return (f"TetMesh(nodes={self.num_nodes}, tetrahedra={self.num_tetrahedra}, "
                f"regions={self.region_names})")


# ---------------------------------------------------------------------------
# exact orientation

def orient3d_signs(nodes: np.ndarray, tetrahedra: np.ndarray) -> np.ndarray:
    """Exact sign (-1, 0, 1) of (p1-p0).((p2-p0)x(p3-p0)) for every tetrahedron.

    A floating-point filter decides the clear cases; the rest are evaluated with
    ``Fraction`` on the exact binary values of the coordinates.
    """
    p = np.asarray(nodes, dtype=float)[np.asarray(tetrahedra)]
    a, b, c = p[:, 1] - p[:, 0], p[:, 2] - p[:, 0], p[:, 3] - p[:, 0]
    m1 = b[:, 1] * c[:, 2] - b[:, 2] * c[:, 1]
    m2 = b[:, 2] * c[:, 0] - b[:, 0] * c[:, 2]
    m3 = b[:, 0] * c[:, 1] - b[:, 1] * c[:, 0]
    det = a[:, 0] * m1 + a[:, 1] * m2 + a[:, 2] * m3
    perm = (np.abs(a[:, 0]) * (np.abs(b[:, 1] * c[:, 2]) + np.abs(b[:, 2] * c[:, 1]))
            + np.abs(a[:, 1]) * (np.abs(b[:, 2] * c[:, 0]) + np.abs(b[:, 0] * c[:, 2]))
            + np.abs(a[:, 2]) * (np.abs(b[:, 0] * c[:, 1]) + np.abs(b[:, 1] * c[:, 0])))
    sign = np.sign(det).astype(np.int8)
    unsure = (np.abs(det) <= _ORIENT_BOUND * perm) | (perm < _TINY) | ~np.isfinite(perm)
    for i in np.flatnonzero(unsure):
        q = [[Fraction(float(x)) for x in row] for row in p[i]]
        u = [[q[k][j] - q[0][j] for j in range(3)] for k in (1, 2, 3)]
        d = (u[0][0] * (u[1][1] * u[2][2] - u[1][2] * u[2][1])
             + u[0][1] * (u[1][2] * u[2][0] - u[1][0] * u[2][2])
             + u[0][2] * (u[1][0] * u[2][1] - u[1][1] * u[2][0]))
        sign[i] = (d > 0) - (d < 0)
    return sign


# ---------------------------------------------------------------------------
# contract check

def _faces(tets: np.ndarray):
    """Unique faces (oriented as first seen), their use counts and, per (tet, local face), the unique index."""
    f = tets[:, OUTWARD_FACES].reshape(-1, 3)
    key = np.sort(f, axis=1)
    _, first, inverse, counts = np.unique(key, axis=0, return_index=True, return_inverse=True, return_counts=True)
    return f[first], counts, inverse.reshape(-1)


def _canonical(faces: np.ndarray) -> set[tuple[int, int, int]]:
    """Oriented faces as tuples rotated so the smallest index comes first (keeps the winding)."""
    out = set()
    for a, b, c in np.asarray(faces, dtype=np.int64).reshape(-1, 3).tolist():
        if b < a and b < c:
            a, b, c = b, c, a
        elif c < a and c < b:
            a, b, c = c, a, b
        out.add((a, b, c))
    return out


def validate(mesh: TetMesh) -> list[str]:
    """Return every violation of the output contract (empty when the mesh satisfies it)."""
    problems: list[str] = []
    nodes = np.asarray(mesh.nodes)
    tets = np.asarray(mesh.tetrahedra)
    regions = np.asarray(mesh.regions)
    if nodes.ndim != 2 or nodes.shape[1] != 3 or not np.issubdtype(nodes.dtype, np.floating):
        return [f"nodes must be an (N, 3) float array, got shape {nodes.shape} and dtype {nodes.dtype}"]
    if tets.ndim != 2 or tets.shape[1] != 4 or not np.issubdtype(tets.dtype, np.integer):
        return [f"tetrahedra must be a (T, 4) integer array, got shape {tets.shape} and dtype {tets.dtype}"]
    if len(tets) == 0:
        return ["the mesh has no tetrahedra"]
    if tets.min() < 0 or tets.max() >= len(nodes):
        return [f"tetrahedra reference node indices outside [0, {len(nodes)})"]
    if not np.isfinite(nodes).all():
        problems.append("nodes contain non-finite coordinates")
    if (np.sort(tets, axis=1)[:, 1:] == np.sort(tets, axis=1)[:, :-1]).any():
        problems.append("a tetrahedron repeats a node")

    # V1: exact orientation of every tetrahedron on the output doubles
    if not problems:
        signs = orient3d_signs(nodes, tets)
        bad = np.flatnonzero(signs <= 0)
        if len(bad):
            problems.append(f"{len(bad)} tetrahedra are not positively oriented (exact orient3d <= 0), "
                            f"first {bad[:5].tolist()}")

    used = np.zeros(len(nodes), dtype=bool)
    used[tets.ravel()] = True
    if not used.all():
        problems.append(f"{int((~used).sum())} orphan nodes, first {np.flatnonzero(~used)[:5].tolist()}")
    if len(np.unique(nodes, axis=0)) != len(nodes):
        problems.append("two nodes have identical coordinates")

    # regions
    names = list(mesh.region_names)
    if regions.shape != (len(tets),) or not np.issubdtype(regions.dtype, np.integer):
        problems.append(f"regions must be a ({len(tets)},) integer array, got shape {regions.shape}")
        return problems
    if len(set(names)) != len(names):
        problems.append("region_names repeats a name")
    if regions.min() < 0 or regions.max() >= len(names):
        problems.append(f"region ids outside [0, {len(names)})")
        return problems
    empty = [names[i] for i in range(len(names)) if not (regions == i).any()]
    if empty:
        problems.append(f"regions without tetrahedra: {empty}")

    # face use counts and the tagged exterior
    faces, counts, inverse = _faces(tets)
    if (counts > 2).any():
        problems.append(f"{int((counts > 2).sum())} faces are shared by more than two tetrahedra")
    exterior = _canonical(faces[counts == 1])
    tagged: dict[tuple[int, int, int], str] = {}
    for tag, arr in mesh.boundary_faces.items():
        arr = np.asarray(arr)
        if arr.size and (arr.ndim != 2 or arr.shape[1] != 3):
            problems.append(f"boundary_faces[{tag!r}] must be (F, 3), got shape {arr.shape}")
            continue
        for f in _canonical(arr):
            if f in tagged:
                problems.append(f"face {f} is tagged twice ({tagged[f]!r} and {tag!r})")
            tagged[f] = tag
        if len(_canonical(arr)) != len(arr):
            problems.append(f"boundary_faces[{tag!r}] repeats a face")
    missing = exterior - tagged.keys()
    extra = tagged.keys() - exterior
    if missing:
        problems.append(f"{len(missing)} exterior faces carry no tag (or are wound inward), e.g. {sorted(missing)[:3]}")
    if extra:
        problems.append(f"{len(extra)} tagged faces are not outward-wound exterior faces, e.g. {sorted(extra)[:3]}")
    if set(mesh.boundary_nodes) != set(mesh.boundary_faces):
        problems.append("boundary_nodes and boundary_faces have different tags")
    for tag, arr in mesh.boundary_faces.items():
        if tag in mesh.boundary_nodes and not np.array_equal(np.asarray(mesh.boundary_nodes[tag]), np.unique(arr)):
            problems.append(f"boundary_nodes[{tag!r}] is not the set of nodes of boundary_faces[{tag!r}]")

    # interfaces: every face between two regions, wound from the first region to the second
    expected = {k: _canonical(v) for k, v in interface_faces(mesh).items()}
    given = {}
    for key, arr in mesh.interfaces.items():
        if len(key) != 2 or not key[0] < key[1]:
            problems.append(f"interface key {key!r} must be a pair of region names (a, b) with a < b")
            continue
        given[tuple(key)] = _canonical(arr)
    if given != expected:
        wrong = sorted(k for k in expected.keys() | given.keys() if expected.get(k) != given.get(k))
        problems.append(f"interfaces differ from the faces between regions (missing, extra or wound from b to a) "
                        f"for {wrong}")
    return problems


def check(mesh: TetMesh) -> TetMesh:
    """Raise ``MeshCheckError`` listing every contract violation; return the mesh when it holds."""
    problems = validate(mesh)
    if problems:
        raise MeshCheckError(problems)
    return mesh


def interface_faces(mesh: TetMesh) -> dict[tuple[str, str], np.ndarray]:
    """Faces between two regions, keyed by the sorted name pair and wound from the first to the second."""
    tets = np.asarray(mesh.tetrahedra)
    _, counts, inverse = _faces(tets)
    owner = np.repeat(np.arange(len(tets)), 4)
    order = np.argsort(inverse, kind="stable")
    pairs = order[counts[inverse[order]] == 2].reshape(-1, 2)    # the two slots of each shared face
    regions = np.asarray(mesh.regions)
    pairs = pairs[regions[owner[pairs[:, 0]]] != regions[owner[pairs[:, 1]]]]
    names = mesh.region_names
    out: dict[tuple[str, str], list] = {}
    for i, j in pairs.tolist():
        ri, rj = int(regions[owner[i]]), int(regions[owner[j]])
        if names[ri] > names[rj]:
            i, ri, rj = j, rj, ri
        out.setdefault((names[ri], names[rj]), []).append(tets[owner[i]][OUTWARD_FACES[i % 4]])
    return {k: np.array(v, dtype=np.int64) for k, v in sorted(out.items())}


# ---------------------------------------------------------------------------
# MSH 4.1 ASCII output

def write_msh(mesh: TetMesh, path: str | Path, *, interfaces: bool = False) -> Path:
    """Write ``mesh`` as Gmsh MSH 4.1 ASCII, readable by ``gmshio.read_msh`` and Gmsh.

    Volume physical group ``i + 1`` is ``region_names[i]``; each boundary tag is a
    surface physical group in ``boundary_faces`` order. Interfaces become surface
    groups named ``"a|b"`` only when ``interfaces`` is true, because readers that
    treat every surface group as boundary (``gmshio.to_fem3d``) would otherwise add
    interior faces to the boundary. Coordinates are written with ``repr``, which
    round-trips every float64 exactly.
    """
    surfaces = [(str(tag), np.asarray(f, dtype=np.int64).reshape(-1, 3)) for tag, f in mesh.boundary_faces.items()]
    if interfaces:
        surfaces += [(f"{a}|{b}", np.asarray(f, dtype=np.int64).reshape(-1, 3)) for (a, b), f in mesh.interfaces.items()]
    names = [str(n) for n in mesh.region_names]
    for n in names + [s for s, _ in surfaces]:
        if '"' in n or "\n" in n:
            raise ValueError(f"name {n!r} cannot be written to MSH: it contains a quote or a newline")
    nodes = np.asarray(mesh.nodes, dtype=float)
    tets = np.asarray(mesh.tetrahedra, dtype=np.int64)
    regions = np.asarray(mesh.regions, dtype=np.int64)
    lo, hi = nodes.min(axis=0), nodes.max(axis=0)
    box = " ".join(repr(float(v)) for v in (*lo, *hi))

    out = ["$MeshFormat", "4.1 0 8", "$EndMeshFormat", "$PhysicalNames", str(len(names) + len(surfaces))]
    out += [f'2 {j + 1} "{s}"' for j, (s, _) in enumerate(surfaces)]
    out += [f'3 {i + 1} "{n}"' for i, n in enumerate(names)]
    out += ["$EndPhysicalNames", "$Entities", f"0 0 {len(surfaces)} {len(names)}"]
    out += [f"{j + 1} {box} 1 {j + 1} 0" for j in range(len(surfaces))]
    out += [f"{i + 1} {box} 1 {i + 1} 0" for i in range(len(names))]
    out += ["$EndEntities", "$Nodes", f"1 {len(nodes)} 1 {len(nodes)}", f"3 1 0 {len(nodes)}"]
    out += [str(k) for k in range(1, len(nodes) + 1)]
    out += [" ".join(map(repr, row)) for row in nodes.tolist()]
    out.append("$EndNodes")

    blocks = [(2, j + 1, 2, f) for j, (_, f) in enumerate(surfaces)]
    blocks += [(3, i + 1, 4, tets[regions == i]) for i in range(len(names))]
    total = sum(len(b[3]) for b in blocks)
    out += ["$Elements", f"{len(blocks)} {total} 1 {total}"]
    tag = 1
    for dim, entity, etype, cells in blocks:
        out.append(f"{dim} {entity} {etype} {len(cells)}")
        for row in (cells + 1).tolist():
            out.append(f"{tag} " + " ".join(map(str, row)))
            tag += 1
    out.append("$EndElements")
    path = Path(path)
    path.write_text("\n".join(out) + "\n", encoding="ascii")
    return path
