# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Export saved fields to VTU for ParaView and other VTK viewers.

Reads a ``fields.npz`` written by ``save()`` and writes one mesh file with
meshio (MIT), installed by the optional extra ``simcase[export]``. The saved
``fields.npz`` stays the reference result; the export is a viewing copy.

Supported layouts:

- steady heat (``thermal2d-p1-node-cell-v1``): point data ``temperature_k`` and
  the nodal ``load/reaction/residual`` arrays, cell data ``heat_flux_w_m2``
- transient heat (``thermal2d-transient-p1-node-cell-v1``): the same arrays at
  one stored time (``time_index``, default the last), or every stored time with
  ``export_time_series``: one VTU per time plus a ParaView collection (``.pvd``)
  that records each ``time_s`` as its timestep
- 3D PEC cavity (``cavity3d-edge-v1``): tetrahedra with cell data
  ``electric_field_mode_<k>`` at centroids (the saved arbitrary SI
  normalization, unit m^-3/2)

2D coordinates get z = 0, and 2D cell vectors get a zero z component, as VTK
expects. Times, frequencies and units stay in ``fields.npz`` and
``summary.json``. XDMF is not offered: meshio's XDMF writer requires h5py.
The ``.pvd`` collection is plain VTK XML written with the standard library.
"""

import os
from pathlib import Path
import xml.etree.ElementTree as ET

import numpy as np

__all__ = ["export_fields", "export_time_series", "SUPPORTED_LAYOUTS"]

_STEADY = "thermal2d-p1-node-cell-v1"
_TRANSIENT = "thermal2d-transient-p1-node-cell-v1"
_CAVITY = "cavity3d-edge-v1"
SUPPORTED_LAYOUTS = (_STEADY, _TRANSIENT, _CAVITY)
_NODAL = ("temperature_k", "load_w_per_m", "source_load_w_per_m", "reaction_w_per_m",
          "residual_w_per_m", "storage_rate_w_per_m")


def _meshio():
    try:
        import meshio
    except ImportError as error:  # pragma: no cover - depends on the environment
        raise ImportError("export needs meshio: pip install 'simcase[export]'") from error
    return meshio


def _points(nodes):
    nodes = np.asarray(nodes, dtype=float)
    if nodes.ndim != 2 or nodes.shape[1] not in (2, 3):
        raise ValueError("expected (N,2) or (N,3) node coordinates")
    if nodes.shape[1] == 2:
        nodes = np.column_stack([nodes, np.zeros(len(nodes))])
    return nodes


def _vector3(values):
    values = np.asarray(values, dtype=float)
    if values.shape[-1] == 2:
        values = np.concatenate([values, np.zeros(values.shape[:-1] + (1,))], axis=-1)
    return values


def _transient_at(data, index):
    """Point and cell data of a transient result at the stored time ``index``."""
    times = np.asarray(data["time_s"], dtype=float)
    point_data = {}
    for name in _NODAL:
        if name not in data:
            continue
        history = np.asarray(data[name], dtype=float)
        # reaction/residual/storage start at the second stored time.
        offset = len(times) - len(history)
        if index - offset >= 0:
            point_data[name] = history[index - offset]
    cell_data = {"heat_flux_w_m2": [_vector3(np.asarray(data["heat_flux_w_m2"])[index])]}
    return point_data, cell_data


def _thermal(data, layout, time_index):
    points = _points(data["nodes_m"])
    cells = [("triangle", np.asarray(data["triangles"], dtype=np.int64))]
    if layout == _TRANSIENT:
        index = range(len(data["time_s"]))[time_index]  # IndexError for an invalid index
        point_data, cell_data = _transient_at(data, index)
    else:
        point_data = {name: np.asarray(data[name], dtype=float) for name in _NODAL if name in data}
        cell_data = {"heat_flux_w_m2": [_vector3(data["heat_flux_w_m2"])]}
    return points, cells, point_data, cell_data


def _cavity(data):
    points = _points(data["nodes"])
    cells = [("tetra", np.asarray(data["tetrahedra"], dtype=np.int64))]
    fields = np.asarray(data["electric_field"], dtype=float)
    cell_data = {f"electric_field_mode_{k}": [fields[k]] for k in range(len(fields))}
    return points, cells, {}, cell_data


def _load(fields_npz):
    with np.load(fields_npz, allow_pickle=False) as archive:
        return {key: archive[key] for key in archive.files}


def export_fields(fields_npz, output, *, time_index=-1):
    """Write the fields of a saved result to the VTU file ``output``.

    Refuses to overwrite an existing file. Returns the output path.
    """
    output = Path(output)
    if output.suffix.lower() != ".vtu":
        raise ValueError("output must end in .vtu")
    if output.exists():
        raise FileExistsError(f"{output} already exists; choose a new file name")
    data = _load(fields_npz)
    layout = str(data.get("field_layout", ""))
    if layout in (_STEADY, _TRANSIENT):
        parts = _thermal(data, layout, time_index)
    elif layout == _CAVITY:
        parts = _cavity(data)
    else:
        raise ValueError(f"unsupported field layout {layout!r}; supported: {SUPPORTED_LAYOUTS}")
    points, cells, point_data, cell_data = parts
    meshio = _meshio()
    mesh = meshio.Mesh(points, cells, point_data=point_data, cell_data=cell_data)
    meshio.vtu.write(output, mesh, binary=True, compression="zlib")
    return output


def export_time_series(fields_npz, output_dir, *, name="fields"):
    """Write every stored time of a transient heat result for ParaView.

    Writes ``<name>_<k>.vtu`` for each stored time ``k`` (zero-padded) and the
    collection ``<name>.pvd`` into ``output_dir``, which must be new or empty;
    nothing is overwritten. Each VTU holds the arrays stored at that time, so
    ``reaction_w_per_m``, ``residual_w_per_m`` and ``storage_rate_w_per_m``
    appear from the second time on. The ``.pvd`` lists each file by a relative
    POSIX path with ``time_s`` as its timestep (written with ``repr``, so the
    value round-trips exactly). On failure, files written so far are removed.
    Returns the ``.pvd`` path.
    """
    if not isinstance(name, str) or not name or name in (".", "..") or any(
            c in name for c in '/\\:'):
        raise ValueError("name must be a plain file stem without path separators")
    output_dir = Path(output_dir)
    if os.path.lexists(output_dir) and (not output_dir.is_dir() or any(output_dir.iterdir())):
        raise FileExistsError(f"{output_dir} exists and is not an empty directory; "
                              "choose a new or empty output directory")
    data = _load(fields_npz)
    layout = str(data.get("field_layout", ""))
    if layout != _TRANSIENT:
        raise ValueError(f"time series export needs layout {_TRANSIENT!r}, got {layout!r}")
    times = np.asarray(data["time_s"], dtype=float)
    if times.ndim != 1 or not len(times):
        raise ValueError("time_s must be a non-empty 1D array")
    meshio = _meshio()
    points = _points(data["nodes_m"])
    cells = [("triangle", np.asarray(data["triangles"], dtype=np.int64))]
    width = max(5, len(str(len(times) - 1)))
    created_dir = not output_dir.exists()
    output_dir.mkdir(parents=True, exist_ok=True)
    written = []
    collection = ET.Element("VTKFile", type="Collection", version="0.1", byte_order="LittleEndian")
    datasets = ET.SubElement(collection, "Collection")
    try:
        for index, time in enumerate(times):
            file_name = f"{name}_{index:0{width}d}.vtu"
            point_data, cell_data = _transient_at(data, index)
            target = output_dir / file_name
            if os.path.lexists(target):
                raise FileExistsError(f"{target} appeared during export")
            mesh = meshio.Mesh(points, cells, point_data=point_data, cell_data=cell_data)
            written.append(target)
            meshio.vtu.write(target, mesh, binary=True, compression="zlib")
            ET.SubElement(datasets, "DataSet", timestep=repr(float(time)), group="", part="0",
                          file=file_name)
        pvd = output_dir / f"{name}.pvd"
        ET.indent(collection)
        with open(pvd, "xb") as stream:
            # Only a file this call created is removed on failure.
            written.append(pvd)
            ET.ElementTree(collection).write(stream, encoding="utf-8", xml_declaration=True)
    except BaseException:
        for path in written:
            try:
                path.unlink()
            except FileNotFoundError:
                pass
        if created_dir:
            try:
                output_dir.rmdir()
            except OSError:
                pass
        raise
    return pvd
