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
  one stored time (``time_index``, default the last)
- 3D PEC cavity (``cavity3d-edge-v1``): tetrahedra with cell data
  ``electric_field_mode_<k>`` at centroids (the saved arbitrary SI
  normalization, unit m^-3/2)

2D coordinates get z = 0, and 2D cell vectors get a zero z component, as VTK
expects. Times, frequencies and units stay in ``fields.npz`` and
``summary.json``. XDMF is not offered: meshio's XDMF writer requires h5py.
"""

from pathlib import Path

import numpy as np

__all__ = ["export_fields", "SUPPORTED_LAYOUTS"]

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


def _thermal(data, layout, time_index):
    points = _points(data["nodes_m"])
    cells = [("triangle", np.asarray(data["triangles"], dtype=np.int64))]
    point_data, cell_data = {}, {}
    if layout == _TRANSIENT:
        times = np.asarray(data["time_s"], dtype=float)
        index = range(len(times))[time_index]  # IndexError for an invalid index
        for name in _NODAL:
            if name not in data:
                continue
            history = np.asarray(data[name], dtype=float)
            # reaction/residual/storage start at the second stored time.
            offset = len(times) - len(history)
            if index - offset >= 0:
                point_data[name] = history[index - offset]
        cell_data["heat_flux_w_m2"] = [_vector3(np.asarray(data["heat_flux_w_m2"])[index])]
    else:
        for name in _NODAL:
            if name in data:
                point_data[name] = np.asarray(data[name], dtype=float)
        cell_data["heat_flux_w_m2"] = [_vector3(data["heat_flux_w_m2"])]
    return points, cells, point_data, cell_data


def _cavity(data):
    points = _points(data["nodes"])
    cells = [("tetra", np.asarray(data["tetrahedra"], dtype=np.int64))]
    fields = np.asarray(data["electric_field"], dtype=float)
    cell_data = {f"electric_field_mode_{k}": [fields[k]] for k in range(len(fields))}
    return points, cells, {}, cell_data


def export_fields(fields_npz, output, *, time_index=-1):
    """Write the fields of a saved result to the VTU file ``output``.

    Refuses to overwrite an existing file. Returns the output path.
    """
    output = Path(output)
    if output.suffix.lower() != ".vtu":
        raise ValueError("output must end in .vtu")
    if output.exists():
        raise FileExistsError(f"{output} already exists; choose a new file name")
    with np.load(fields_npz, allow_pickle=False) as archive:
        data = {key: archive[key] for key in archive.files}
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
