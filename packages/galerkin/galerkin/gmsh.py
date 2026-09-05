"""Read and write Gmsh .msh meshes — ASCII formats 2.2 and 4.1.

Why a reader rather than a binding
----------------------------------
Gmsh is GPL. Linking its library into this engine would make the engine GPL too,
so Gmsh is never linked: it is run as a separate executable and this module reads
the file it writes. Parsing a published file format creates no derivative work,
which is the whole point of the arrangement.

    gmsh -3 cavity.geo -o cavity.msh -format msh2     # or the default 4.1
    mesh = read_msh("cavity.msh")

What is supported
-----------------
ASCII only (binary files are rejected with a clear message rather than
mis-parsed), tetrahedra for 3D and triangles for 2D, plus the surface elements
that carry the physical groups used as boundary tags. Node tags need not be
contiguous or start at one; they are remapped. Higher-order elements are not
read: this engine is lowest-order, and silently dropping the mid-side nodes of a
second-order mesh would be worse than refusing it.

Element type codes used here: 1 = 2-node line, 2 = 3-node triangle,
4 = 4-node tetrahedron, 15 = 1-node point.

Honest limitation
-----------------
The Gmsh executable is not available in the development container, so this reader
is gated on hand-written fixtures transcribed from the format documentation and
on a round trip that ends in a physics check (a cavity spectrum computed on a
mesh that has been written out and read back). It has not yet been run against a
file produced by Gmsh itself.
"""

from __future__ import annotations

import numpy as np

from .mesh import Mesh
from .mesh3d import Mesh3D

_LINE, _TRI, _TET, _POINT = 1, 2, 4, 15
_NODES_PER_TYPE = {_LINE: 2, _TRI: 3, _TET: 4, _POINT: 1}


class GmshFormatError(ValueError):
    pass


def _tokens(text: str):
    """Stream of whitespace-separated tokens, so a block's layout can be read
    without caring where Gmsh chose to break lines."""
    return iter(text.split())


def _read_sections(path):
    """{section name: raw text} for a $Name ... $EndName file."""
    sections, name, buf = {}, None, []
    with open(path, "r") as fh:
        for line in fh:
            s = line.strip()
            if s.startswith("$End"):
                if name is not None:
                    sections[name] = "\n".join(buf)
                name, buf = None, []
            elif s.startswith("$"):
                name, buf = s[1:], []
            elif name is not None:
                buf.append(s)
    return sections


def _parse_physical_names(text):
    """{(dim, tag): name}."""
    if not text:
        return {}
    lines = [l for l in text.splitlines() if l.strip()]
    out = {}
    for line in lines[1:]:
        parts = line.split(None, 2)
        if len(parts) < 3:
            continue
        out[(int(parts[0]), int(parts[1]))] = parts[2].strip().strip('"')
    return out


def _parse_entities_41(text):
    """{(dim, entity tag): [physical tags]} from a format 4.1 $Entities block."""
    if not text:
        return {}
    t = _tokens(text)
    counts = [int(next(t)) for _ in range(4)]          # points, curves, surfaces, volumes
    out = {}
    for dim, n in enumerate(counts):
        for _ in range(n):
            tag = int(float(next(t)))
            for _ in range(3 if dim == 0 else 6):      # a point has no bounding box
                next(t)
            phys = [int(float(next(t))) for _ in range(int(float(next(t))))]
            if dim > 0:                                # then the bounding entities
                for _ in range(int(float(next(t)))):
                    next(t)
            out[(dim, tag)] = phys
    return out


def _parse_nodes_22(text):
    t = _tokens(text)
    n = int(next(t))
    tags = np.empty(n, dtype=np.int64)
    xyz = np.empty((n, 3))
    for i in range(n):
        tags[i] = int(float(next(t)))
        xyz[i] = [float(next(t)) for _ in range(3)]
    return tags, xyz


def _parse_nodes_41(text):
    t = _tokens(text)
    n_blocks, n_nodes = int(next(t)), int(next(t))
    next(t); next(t)                                   # min and max node tag
    tags = np.empty(n_nodes, dtype=np.int64)
    xyz = np.empty((n_nodes, 3))
    at = 0
    for _ in range(n_blocks):
        next(t); next(t)                               # entity dim, entity tag
        parametric, count = int(next(t)), int(next(t))
        if parametric:
            raise GmshFormatError("parametric nodes are not supported")
        for i in range(count):
            tags[at + i] = int(float(next(t)))
        for i in range(count):
            xyz[at + i] = [float(next(t)) for _ in range(3)]
        at += count
    return tags[:at], xyz[:at]


def _parse_elements_22(text, names):
    """[(type, physical tag, node tags)] from a format 2.2 $Elements block."""
    t = _tokens(text)
    n = int(next(t))
    out = []
    for _ in range(n):
        next(t)                                        # element tag
        etype, n_tags = int(next(t)), int(next(t))
        tags = [int(float(next(t))) for _ in range(n_tags)]
        k = _NODES_PER_TYPE.get(etype)
        if k is None:
            raise GmshFormatError(
                f"element type {etype} is not supported (lowest-order meshes only)")
        nodes = [int(float(next(t))) for _ in range(k)]
        out.append((etype, tags[0] if tags else 0, nodes))
    return out


def _parse_elements_41(text, entities):
    t = _tokens(text)
    n_blocks = int(next(t))
    next(t); next(t); next(t)                          # count, min tag, max tag
    out = []
    for _ in range(n_blocks):
        dim, entity = int(next(t)), int(next(t))
        etype, count = int(next(t)), int(next(t))
        k = _NODES_PER_TYPE.get(etype)
        if k is None:
            raise GmshFormatError(
                f"element type {etype} is not supported (lowest-order meshes only)")
        phys = entities.get((dim, entity), [])
        for _ in range(count):
            next(t)                                    # element tag
            nodes = [int(float(next(t))) for _ in range(k)]
            out.append((etype, phys[0] if phys else 0, nodes))
    return out


def read_msh(path):
    """Read a Gmsh ASCII mesh; returns a Mesh3D if it has tetrahedra, else a Mesh.

    Physical groups on the surface elements become boundary tags, named from
    $PhysicalNames when the file provides them.
    """
    sections = _read_sections(path)
    if "MeshFormat" not in sections:
        raise GmshFormatError(f"{path}: no $MeshFormat section — not a .msh file")
    fields = sections["MeshFormat"].split()
    version, file_type = float(fields[0]), int(fields[1])
    if file_type != 0:
        raise GmshFormatError(
            f"{path}: binary .msh is not supported; re-export as ASCII")

    names = _parse_physical_names(sections.get("PhysicalNames", ""))
    if version < 4.0:
        tags, xyz = _parse_nodes_22(sections["Nodes"])
        elements = _parse_elements_22(sections["Elements"], names)
    else:
        entities = _parse_entities_41(sections.get("Entities", ""))
        tags, xyz = _parse_nodes_41(sections["Nodes"])
        elements = _parse_elements_41(sections["Elements"], entities)

    lookup = np.full(int(tags.max()) + 1, -1, dtype=np.int64)
    lookup[tags] = np.arange(len(tags))                # gmsh tag -> 0-based index

    tets = np.array([e[2] for e in elements if e[0] == _TET], dtype=np.int64)
    tris = np.array([e[2] for e in elements if e[0] == _TRI], dtype=np.int64)
    lines = np.array([e[2] for e in elements if e[0] == _LINE], dtype=np.int64)
    tri_phys = np.array([e[1] for e in elements if e[0] == _TRI], dtype=np.int64)
    line_phys = np.array([e[1] for e in elements if e[0] == _LINE], dtype=np.int64)

    def group_nodes(cells, phys, dim):
        groups = {}
        for tag in np.unique(phys):
            if tag == 0:
                continue
            nodes = np.unique(lookup[cells[phys == tag]])
            groups[names.get((dim, int(tag)), str(int(tag)))] = nodes
        return groups

    if len(tets):
        return Mesh3D(xyz, lookup[tets], group_nodes(tris, tri_phys, 2))
    if len(tris):
        return Mesh(xyz[:, :2], lookup[tris], group_nodes(lines, line_phys, 1))
    raise GmshFormatError(f"{path}: no triangles or tetrahedra found")


def write_msh(mesh, path, physical: dict[str, int] | None = None):
    """Write a Mesh3D or Mesh as ASCII .msh 2.2.

    Boundary tags are written as physical groups on the surface elements, so a
    read-back mesh carries the same named boundaries — otherwise a round trip
    would quietly lose every boundary condition.
    """
    is3d = hasattr(mesh, "tets")
    cells = mesh.tets if is3d else mesh.triangles
    cell_type, dim = (_TET, 3) if is3d else (_TRI, 2)
    face_type = _TRI if is3d else _LINE
    nodes = mesh.nodes if is3d else np.column_stack(
        [mesh.nodes, np.zeros(len(mesh.nodes))])

    physical = physical or {name: i + 1 for i, name in enumerate(sorted(mesh.boundary))}
    vol_tag = (max(physical.values()) + 1) if physical else 1

    # surface elements carrying the boundary tags
    faces, face_tags = [], []
    if is3d:
        for f in mesh.boundary_faces():
            for name, tag in physical.items():
                if np.isin(f, mesh.boundary[name]).all():
                    faces.append(f); face_tags.append(tag)
                    break
    else:
        for name, tag in physical.items():
            for e in mesh.boundary_edges.get(name, []):
                faces.append(e); face_tags.append(tag)

    with open(path, "w") as fh:
        fh.write("$MeshFormat\n2.2 0 8\n$EndMeshFormat\n")
        fh.write(f"$PhysicalNames\n{len(physical) + 1}\n")
        fh.write(f'{dim} {vol_tag} "domain"\n')
        for name, tag in sorted(physical.items(), key=lambda kv: kv[1]):
            fh.write(f'{dim - 1} {tag} "{name}"\n')
        fh.write("$EndPhysicalNames\n")

        fh.write(f"$Nodes\n{len(nodes)}\n")
        for i, p in enumerate(nodes, start=1):
            fh.write("%d %r %r %r\n" % (i, float(p[0]), float(p[1]), float(p[2])))
        fh.write("$EndNodes\n")

        fh.write(f"$Elements\n{len(faces) + len(cells)}\n")
        n = 0
        for f, tag in zip(faces, face_tags):
            n += 1
            fh.write(f"{n} {face_type} 2 {tag} 1 "
                     + " ".join(str(int(v) + 1) for v in f) + "\n")
        for c in cells:
            n += 1
            fh.write(f"{n} {cell_type} 2 {vol_tag} 1 "
                     + " ".join(str(int(v) + 1) for v in c) + "\n")
        fh.write("$EndElements\n")
