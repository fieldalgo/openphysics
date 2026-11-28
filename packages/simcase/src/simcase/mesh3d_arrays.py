# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""A 3D mesh as plain NumPy arrays and back (``mesh3d_to_arrays`` / ``mesh3d_from_arrays``).

The mesh is a ``Mesh3DResult`` (``build_mesh3d``: the meshloom route and meshloom's builder shapes) or
the ``galerkin.Mesh3D`` of the ``meshine.extrude`` route (a lone slab ``layers`` component), as
``build_thermal3d_mesh`` makes them. ``mesh3d_to_arrays`` gives a flat ``{name: ndarray}`` of numeric
and string arrays only, so it can be written with ``numpy.savez`` and read back with
``allow_pickle=False``; names carry an index, never a tag or a provenance name. Every array is kept
bit for bit, so a solve on the read-back mesh equals one on the original. The exact complex (a
meshloom-route ``Mesh3DResult``'s ``complex``) is not stored: ``mesh3d_from_arrays`` rebuilds it from
the document's geometry. The hand-off and meshloom's raw output are not kept.

The arrays carry the SHA-256 of the document's canonical ``geometry`` and ``mesh`` blocks (keys
sorted, no spaces, numbers as written: the blocks that make the mesh, so a change of physics keeps
it) and the component's name; ``mesh3d_from_arrays`` refuses arrays of another format, or made from
another document's geometry and mesh blocks or another component.

Experimental, and internal to Studio's process hand-off (a mesh child writes, the server reads): it
is not a file format users save, and it may change in any release.
"""

from __future__ import annotations

import hashlib
import json

import numpy as np

FORMAT = "openphysics-mesh3d-arrays-v1"


def _meta_array(meta: dict) -> np.ndarray:
    return np.array(json.dumps(meta, ensure_ascii=True, allow_nan=False, sort_keys=True))


def _table(out: dict, meta: dict, name: str, table: dict, *, pairs=False) -> None:
    keys = list(table)
    meta[name] = [list(k) for k in keys] if pairs else keys
    for i, k in enumerate(keys):
        out[f"{name}.{i}"] = np.ascontiguousarray(table[k], dtype=np.int64)


def mesh_digest(document) -> str:
    """SHA-256 of a document's canonical ``geometry`` and ``mesh`` blocks (``reader.dumps``, keys sorted,
    no spaces, ASCII, numbers as written): the Studio mesh job's reuse key."""
    from . import reader
    data = getattr(document, "data", document)
    blocks = {"geometry": data.get("geometry"), "mesh": data.get("mesh")}
    text = reader.dumps(blocks, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _component(document, component):
    from .geometry_document import _pick, parse
    return _pick(parse(getattr(document, "data", document)), component).name


def mesh3d_to_arrays(mesh, document, component: str | None = None) -> dict:
    """``{name: ndarray}`` of a ``Mesh3DResult`` or a ``galerkin.Mesh3D`` made from ``document``'s
    ``component`` (see the module)."""
    from galerkin.mesh3d import Mesh3D
    from .geometry_engine3d import Mesh3DResult
    if isinstance(mesh, Mesh3DResult):
        kind, m = "result", mesh.mesh
    elif isinstance(mesh, Mesh3D):
        kind, m = "mesh", mesh
    else:
        raise TypeError("mesh3d_to_arrays takes a simcase.Mesh3DResult or a galerkin.Mesh3D")
    meta = {"format": FORMAT, "kind": kind, "region_names": list(m.region_names),
            "mesh_digest": mesh_digest(document), "component": _component(document, component)}
    out = {"nodes": np.ascontiguousarray(m.nodes, dtype=np.float64),
           "tets": np.ascontiguousarray(m.tets, dtype=np.int64),
           "regions": np.ascontiguousarray(m.regions, dtype=np.int64)}
    _table(out, meta, "boundary", m.boundary)
    _table(out, meta, "tagged_faces", m.tagged_faces)
    _table(out, meta, "interfaces", m.interfaces, pairs=True)
    meta["mesh_provenance"] = hasattr(m, "provenance_faces")
    if hasattr(m, "provenance_faces"):
        _table(out, meta, "mesh_provenance_faces", m.provenance_faces)
    if kind == "result":
        r = mesh
        meta["complex"] = None if r.complex is None else r.complex.component
        meta["estimate"] = float(r.estimate).hex()
        meta["diagnostics"] = [[d.code, d.path, d.message] for d in r.diagnostics]
        meta["face_of_facet"] = [int(f) for f in r.face_of_facet]
        _table(out, meta, "provenance_faces", r.provenance_faces)
        meta["selection_kinds"] = [r.selections[k][0] for k in r.selections]
        _table(out, meta, "selections", {k: v[1] for k, v in r.selections.items()})
        _table(out, meta, "selection_nodes", r.selection_nodes)
        for i, faces in enumerate(r.facet_faces):
            out[f"facet_faces.{i}"] = np.ascontiguousarray(faces, dtype=np.int64)
    out["meta"] = _meta_array(meta)
    return out


def _read_table(arrays: dict, meta: dict, name: str, *, pairs=False) -> dict:
    return {(tuple(k) if pairs else k): np.asarray(arrays[f"{name}.{i}"]) for i, k in enumerate(meta[name])}


def mesh3d_from_arrays(arrays, document, component: str | None = None):
    """The ``Mesh3DResult`` or ``galerkin.Mesh3D`` of ``mesh3d_to_arrays``'s arrays, made from
    ``document``'s ``component``: arrays of another format, or of another document's geometry and mesh
    blocks or another component, are refused (``ValueError``). On the meshloom route the exact complex
    is rebuilt from the document's geometry."""
    from galerkin.mesh3d import Mesh3D
    from physmat.units import Diagnostic
    from .geometry_document import GeometryError, parse
    from .geometry_engine3d import Mesh3DResult, _evaluate
    from .geometry_document import _pick
    if "meta" not in arrays:
        raise ValueError("not mesh3d_to_arrays arrays: no meta")
    meta = json.loads(str(np.asarray(arrays["meta"])[()]))
    if meta.get("format") != FORMAT:
        raise ValueError(f"not mesh3d_to_arrays arrays: format {meta.get('format')!r}, expected {FORMAT!r}")
    if meta["mesh_digest"] != mesh_digest(document):
        raise ValueError("these mesh arrays were made from other geometry and mesh blocks than the document's "
                         f"(SHA-256 {meta['mesh_digest'][:12]}…, the document's {mesh_digest(document)[:12]}…)")
    name = _component(document, component)
    if meta["component"] != name:
        raise ValueError(f"these mesh arrays are of component {meta['component']!r}, not {name!r}")
    mesh = Mesh3D(np.asarray(arrays["nodes"]), np.asarray(arrays["tets"]),
                  boundary=_read_table(arrays, meta, "boundary"), regions=np.asarray(arrays["regions"]),
                  region_names=meta["region_names"], tagged_faces=_read_table(arrays, meta, "tagged_faces"),
                  interfaces=_read_table(arrays, meta, "interfaces", pairs=True))
    if meta["mesh_provenance"]:
        mesh.provenance_faces = _read_table(arrays, meta, "mesh_provenance_faces")
    if meta["kind"] == "mesh":
        return mesh
    cx = None
    if meta["complex"] is not None:
        comp = _pick(parse(getattr(document, "data", document)), meta["complex"])
        cx = _evaluate(comp, through_meshloom=False)
        if len(cx.faces) <= max(meta["face_of_facet"], default=-1):
            raise GeometryError("the document's geometry is not the one this mesh was made from")
    selections = {k: (kind, v) for kind, (k, v) in
                  zip(meta["selection_kinds"], _read_table(arrays, meta, "selections").items())}
    facets = [np.asarray(arrays[f"facet_faces.{i}"]) for i in range(len(meta["face_of_facet"]))]
    return Mesh3DResult(mesh, cx, _read_table(arrays, meta, "provenance_faces"), selections,
                        _read_table(arrays, meta, "selection_nodes"), facets, list(meta["face_of_facet"]),
                        float.fromhex(meta["estimate"]),
                        diagnostics=[Diagnostic(c, p, m) for c, p, m in meta["diagnostics"]])
