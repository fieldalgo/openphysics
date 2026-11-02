# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Export saved fields to VTU for ParaView and other VTK viewers.

Reads a ``fields.npz`` written by ``save()`` and writes one mesh file with
meshio (MIT), installed by the optional extra ``simcase[export]``. The saved
``fields.npz`` stays the reference result; the export is a viewing copy.

Supported layouts:

- steady heat (``thermal2d-p1-node-cell-v1``): point data ``temperature_k`` and
  the nodal ``load/reaction/residual`` arrays, cell data ``heat_flux_w_m2``
- steady heat with flux or convection sides
  (``thermal2d-p1-node-cell-boundary-v2``): the same, plus the nodal
  ``prescribed_outward_load``, ``ambient_load``, ``convective_outward`` and
  ``system_rhs`` arrays (W/m)
- transient heat (``thermal2d-transient-p1-node-cell-v1``): the same arrays at
  one stored time (``time_index``, default the last), or every stored time with
  ``export_time_series``: one VTU per time plus a ParaView collection (``.pvd``)
  that records each ``time_s`` as its timestep
- region heat (``thermal2d-p1-node-cell-regions-v1`` and
  ``thermal2d-transient-p1-node-cell-regions-v1``): the same steady/transient
  arrays plus static integer cell data ``triangle_regions``; steady boundary
  loads are point data when present
- 3D PEC cavity (``cavity3d-edge-v1``): tetrahedra with cell data
  ``electric_field_mode_<k>`` at centroids (the saved arbitrary SI
  normalization, unit m^-3/2)
- 3D cavity with materials and lossy walls (``cavity3d-edge-complex-v1``):
  VTK has no complex arrays, so each complex mode field becomes the cell data
  ``electric_field_mode_<k>_real`` and ``electric_field_mode_<k>_imag`` (unit
  m^-3/2, the saved normalization and ``exp(+j*omega*t)`` convention), and the
  per-tetrahedron materials become ``tet_relative_permittivity_real``/``_imag``
  and ``tet_relative_permeability_real``/``_imag`` (dimensionless). Complex
  frequencies, quality factors and wall conductivities are not per cell and
  stay in ``fields.npz`` and ``summary.json``
- electric conduction and Joule heating (``electric-joule2d-p1-v1``, the layout
  of ``electric.steady2d``, ``joule.steady2d`` and ``joule.temperature2d``):
  point data ``potential_v`` and the nodal electric load, reaction, prescribed
  outward current and residual arrays; cell data ``electric_field_v_m``,
  ``current_density_a_m2``, ``conductivity_s_m`` and ``joule_heating_w_m3`` at
  centroids. A Joule result adds ``temperature_k``, the nodal heat arrays and
  cell ``heat_flux_w_m2``; a temperature-dependent one adds
  ``evaluated_temperature_k``. Each array keeps its saved name and unit suffix.
- waveguide modes (``em-modes2d-p1-node-centroid-v1``, the layout of
  ``em.modes2d`` results tracked per mode): the saved ``nodes`` are in the
  document length unit and are converted to metres with the saved
  ``length_unit_to_m``. A scalar result writes each nodal mode ``k`` (zero-based
  column of ``fields``) as point data ``mode_<k>``, or ``mode_<k>_real`` and
  ``mode_<k>_imag`` when the saved array is complex (lossy materials). A vector
  result writes the complex centroid field as cell data
  ``electric_field_mode_<k>_real``/``_imag`` (Ex, Ey, Ez; the saved relative
  normalization, maximum centroid |E| = 1) and the complex nodal longitudinal
  component as point data ``longitudinal_electric_mode_<k>_real``/``_imag``.
  Every mode VTU carries the static integer cell data ``triangle_regions``
  (the saved ``regions``). ``export_fields`` takes a single-point result;
  ``export_sweep`` writes one VTU per study point plus a ``.pvd`` collection
  whose timestep is the wavelength (in the document unit) for a strictly
  monotone wavelength sweep and the point index otherwise. PML results
  (``field_representation`` ``pml-*``) use the same layout: the arrays cover
  the absorbing layer too, where the fields are artificial. ``neff``, ``edges``,
  the transverse edge coefficients, tracking and open-boundary diagnostics stay
  in ``fields.npz``. The subspace layout ``em-modes2d-subspace-raw-v1`` (raw
  eigenpair columns per cluster) is refused.

Dirichlet node lists, ``metadata_json`` and the summary are not copied: the
arrays named above are exported when the saved file holds them, nothing else.
A ``fields.npz`` without a ``field_layout`` array is refused: results saved
before their layout was recorded must be regenerated from their ``model.json``.

2D coordinates get z = 0, and 2D cell vectors get a zero z component, as VTK
expects. Times, frequencies and units stay in ``fields.npz`` and
``summary.json``. XDMF is not offered: meshio's XDMF writer requires h5py.
The ``.pvd`` collection is plain VTK XML written with the standard library.
"""

import os
from pathlib import Path
import xml.etree.ElementTree as ET

import numpy as np

__all__ = ["export_fields", "export_time_series", "export_sweep", "SUPPORTED_LAYOUTS"]

_STEADY = "thermal2d-p1-node-cell-v1"
_STEADY_BOUNDARY = "thermal2d-p1-node-cell-boundary-v2"
_TRANSIENT = "thermal2d-transient-p1-node-cell-v1"
_CAVITY = "cavity3d-edge-v1"
_CAVITY_COMPLEX = "cavity3d-edge-complex-v1"
_STEADY_REGIONS = "thermal2d-p1-node-cell-regions-v1"
_TRANSIENT_REGIONS = "thermal2d-transient-p1-node-cell-regions-v1"
_ELECTRIC_JOULE = "electric-joule2d-p1-v1"
_MODES = "em-modes2d-p1-node-centroid-v1"
_MODES_SUBSPACE = "em-modes2d-subspace-raw-v1"
_TRANSIENT_LAYOUTS = (_TRANSIENT, _TRANSIENT_REGIONS)
_REGION_LAYOUTS = (_STEADY_REGIONS, _TRANSIENT_REGIONS)
_THERMAL_LAYOUTS = (_STEADY, _STEADY_BOUNDARY, _TRANSIENT, *_REGION_LAYOUTS)
SUPPORTED_LAYOUTS = (_STEADY, _STEADY_BOUNDARY, _TRANSIENT, _CAVITY, *_REGION_LAYOUTS,
                     _ELECTRIC_JOULE, _CAVITY_COMPLEX, _MODES)
_NODAL = ("temperature_k", "load_w_per_m", "source_load_w_per_m", "reaction_w_per_m",
          "residual_w_per_m", "storage_rate_w_per_m",
          "prescribed_outward_load_w_per_m", "ambient_load_w_per_m",
          "convective_outward_w_per_m", "system_rhs_w_per_m")
# electric-joule2d-p1-v1 arrays by VTK association; absent arrays are skipped
# (a plain electric result has no heat arrays, only joule.temperature2d has
# evaluated_temperature_k). Dirichlet node lists are not exported.
_ELECTRIC_NODAL = ("potential_v", "joule_load_w_per_m", "electric_reaction_a_per_m",
                   "prescribed_outward_current_a_per_m", "electric_residual_a_per_m",
                   "temperature_k", "thermal_load_w_per_m", "thermal_reaction_w_per_m",
                   "thermal_residual_w_per_m", "prescribed_outward_heat_w_per_m",
                   "ambient_load_w_per_m", "convective_outward_heat_w_per_m",
                   "thermal_system_rhs_w_per_m", "evaluated_temperature_k")
_ELECTRIC_CELL_VECTORS = ("electric_field_v_m", "current_density_a_m2", "heat_flux_w_m2")
_ELECTRIC_CELL_SCALARS = ("conductivity_s_m", "joule_heating_w_m3")
# cavity3d-edge-complex-v1 static per-tetrahedron complex material arrays.
_CAVITY_COMPLEX_CELL = ("tet_relative_permittivity", "tet_relative_permeability")


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


def _region_cell_data(data, layout):
    """Static dimensionless region IDs, without renumbering or interpolation."""
    if layout not in _REGION_LAYOUTS:
        return {}
    regions = np.asarray(data.get("triangle_regions"))
    if (regions.shape != (len(data["triangles"]),) or regions.dtype.kind not in "iu"
            or np.any(regions < 0)):
        raise ValueError("triangle_regions must contain one non-negative integer per triangle")
    return {"triangle_regions": [regions]}


def _thermal(data, layout, time_index):
    points = _points(data["nodes_m"])
    cells = [("triangle", np.asarray(data["triangles"], dtype=np.int64))]
    if layout in _TRANSIENT_LAYOUTS:
        index = range(len(data["time_s"]))[time_index]  # IndexError for an invalid index
        point_data, cell_data = _transient_at(data, index)
    else:
        point_data = {name: np.asarray(data[name], dtype=float) for name in _NODAL if name in data}
        cell_data = {"heat_flux_w_m2": [_vector3(data["heat_flux_w_m2"])]}
    cell_data.update(_region_cell_data(data, layout))
    return points, cells, point_data, cell_data


def _electric_joule(data):
    points = _points(data["nodes_m"])
    triangles = np.asarray(data["triangles"], dtype=np.int64)
    cells = [("triangle", triangles)]
    point_data, cell_data = {}, {}
    for name in _ELECTRIC_NODAL:
        if name in data:
            values = np.asarray(data[name], dtype=float)
            if values.shape != (len(points),):
                raise ValueError(f"{name}: expected one value per node, got shape {values.shape}")
            point_data[name] = values
    for name in _ELECTRIC_CELL_VECTORS:
        if name in data:
            values = np.asarray(data[name], dtype=float)
            if values.shape != (len(triangles), 2):
                raise ValueError(f"{name}: expected one 2D vector per triangle, got shape {values.shape}")
            cell_data[name] = [_vector3(values)]
    for name in _ELECTRIC_CELL_SCALARS:
        if name in data:
            values = np.asarray(data[name], dtype=float)
            if values.shape != (len(triangles),):
                raise ValueError(f"{name}: expected one value per triangle, got shape {values.shape}")
            cell_data[name] = [values]
    if "potential_v" not in point_data:
        raise ValueError("electric-joule2d-p1-v1 export needs the saved potential_v array")
    return points, cells, point_data, cell_data


def _cavity(data):
    points = _points(data["nodes"])
    cells = [("tetra", np.asarray(data["tetrahedra"], dtype=np.int64))]
    fields = np.asarray(data["electric_field"], dtype=float)
    cell_data = {f"electric_field_mode_{k}": [fields[k]] for k in range(len(fields))}
    return points, cells, {}, cell_data


def _real_imag(values):
    """VTK has no complex arrays: one C-ordered float array per part."""
    values = np.asarray(values)
    return (np.ascontiguousarray(values.real, dtype=float),
            np.ascontiguousarray(values.imag, dtype=float))


def _cavity_complex(data):
    points = _points(data["nodes"])
    tetrahedra = np.asarray(data["tetrahedra"], dtype=np.int64)
    cells = [("tetra", tetrahedra)]
    fields = np.asarray(data["electric_field"])
    if fields.ndim != 3 or fields.shape[1:] != (len(tetrahedra), 3):
        raise ValueError(f"electric_field: expected shape (modes, tetrahedra, 3), got {fields.shape}")
    cell_data = {}
    for k in range(len(fields)):
        real, imag = _real_imag(fields[k])
        cell_data[f"electric_field_mode_{k}_real"] = [real]
        cell_data[f"electric_field_mode_{k}_imag"] = [imag]
    for name in _CAVITY_COMPLEX_CELL:
        values = np.asarray(data[name])
        if values.shape != (len(tetrahedra),):
            raise ValueError(f"{name}: expected one value per tetrahedron, got shape {values.shape}")
        real, imag = _real_imag(values)
        cell_data[f"{name}_real"] = [real]
        cell_data[f"{name}_imag"] = [imag]
    return points, cells, {}, cell_data


def _modes_mesh(data):
    """Points in metres, triangle cells and the static region IDs of a mode result.

    The saved ``nodes`` are in the document length unit; ``length_unit_to_m``
    is the saved size of that unit, so ``points == nodes * length_unit_to_m``.
    """
    factor = np.asarray(data["length_unit_to_m"], dtype=float)
    if factor.shape != () or not (np.isfinite(factor) and factor > 0):
        raise ValueError(f"length_unit_to_m must be one positive finite number, got {factor!r}")
    points = _points(np.asarray(data["nodes"], dtype=float) * float(factor))
    triangles = np.asarray(data["triangles"], dtype=np.int64)
    regions = np.asarray(data["regions"])
    if regions.shape != (len(triangles),) or regions.dtype.kind not in "iu" or np.any(regions < 0):
        raise ValueError("regions must contain one non-negative integer per triangle")
    return points, [("triangle", triangles)], {"triangle_regions": [regions]}


def _mode_arrays(data):
    """(study points, validated per-point arrays) of a mode result.

    A scalar result holds ``fields`` (points, nodes, modes); a vector result
    ``vector_electric`` (points, triangles, modes, 3) and, when saved,
    ``vector_longitudinal`` (points, nodes, modes).
    """
    n_nodes, n_triangles = len(data["nodes"]), len(data["triangles"])
    if "vector_electric" in data:
        electric = np.asarray(data["vector_electric"])
        if electric.ndim != 4 or electric.shape[1] != n_triangles or electric.shape[3] != 3:
            raise ValueError("vector_electric: expected shape (points, triangles, modes, 3) with "
                             f"{n_triangles} triangles, got {electric.shape}")
        count, modes = electric.shape[0], electric.shape[2]
        arrays = {"vector_electric": electric}
        if "vector_longitudinal" in data:
            longitudinal = np.asarray(data["vector_longitudinal"])
            if longitudinal.shape != (count, n_nodes, modes):
                raise ValueError(f"vector_longitudinal: expected shape {(count, n_nodes, modes)}, "
                                 f"got {longitudinal.shape}")
            arrays["vector_longitudinal"] = longitudinal
    elif "fields" in data:
        fields = np.asarray(data["fields"])
        if fields.ndim != 3 or fields.shape[1] != n_nodes:
            raise ValueError(f"fields: expected shape (points, nodes, modes) with {n_nodes} nodes, "
                             f"got {fields.shape}")
        count, arrays = fields.shape[0], {"fields": fields}
    else:
        raise ValueError(f"{_MODES} export needs the saved fields (scalar) or vector_electric (vector) array")
    values = np.asarray(data["values"])
    if values.shape != (count,):
        raise ValueError(f"values: expected one study value per point, {(count,)}, got {values.shape}")
    return count, arrays


def _modes_at(arrays, index):
    """Point and cell data of the modes at study point ``index``.

    Scalar modes keep their saved dtype: a real array gives ``mode_<k>``, a
    complex one ``mode_<k>_real``/``_imag``. Vector arrays are complex and
    always written as ``_real``/``_imag`` pairs.
    """
    point_data, cell_data = {}, {}
    if "fields" in arrays:
        fields = arrays["fields"][index]
        for k in range(fields.shape[1]):
            if fields.dtype.kind == "c":
                point_data[f"mode_{k}_real"], point_data[f"mode_{k}_imag"] = _real_imag(fields[:, k])
            else:
                point_data[f"mode_{k}"] = np.ascontiguousarray(fields[:, k], dtype=float)
        return point_data, cell_data
    electric = arrays["vector_electric"][index]
    for k in range(electric.shape[1]):
        real, imag = _real_imag(electric[:, k, :])
        cell_data[f"electric_field_mode_{k}_real"] = [real]
        cell_data[f"electric_field_mode_{k}_imag"] = [imag]
    if "vector_longitudinal" in arrays:
        longitudinal = arrays["vector_longitudinal"][index]
        for k in range(longitudinal.shape[1]):
            real, imag = _real_imag(longitudinal[:, k])
            point_data[f"longitudinal_electric_mode_{k}_real"] = real
            point_data[f"longitudinal_electric_mode_{k}_imag"] = imag
    return point_data, cell_data


def _modes(data):
    points, cells, static = _modes_mesh(data)
    count, arrays = _mode_arrays(data)
    if count != 1:
        raise ValueError(f"this em.modes2d result has {count} study points; export_fields writes a "
                         "single-point result. Use export_sweep(fields_npz, output_dir) for one VTU per "
                         "point and a .pvd collection")
    point_data, cell_data = _modes_at(arrays, 0)
    cell_data.update(static)
    return points, cells, point_data, cell_data


def _sweep_timesteps(data, count):
    """Wavelengths (document unit) of a strictly monotone wavelength sweep, else point indices."""
    values = np.asarray(data["values"], dtype=float)
    steps = np.diff(values)
    if str(data.get("study_parameter", "")).endswith(".wavelength") and (
            np.all(steps > 0) or np.all(steps < 0)):
        return [float(v) for v in values]
    return [float(i) for i in range(count)]


def _refuse_subspace():
    raise ValueError(
        f"layout {_MODES_SUBSPACE!r} holds raw eigenpair columns per cluster (raw_neff, raw_transverse, "
        "raw_longitudinal, raw_electric, frame_transform), not tracked modes; their VTU export is deferred. "
        "Read the raw_* arrays from fields.npz, or run the sweep with resolved-mode tracking "
        f"(the default) for the per-mode layout {_MODES!r}")


def _layout(data):
    """The saved layout identifier. A file without one cannot be interpreted."""
    if "field_layout" not in data:
        raise ValueError(
            "fields.npz has no 'field_layout' array, so its layout cannot be identified. A result saved "
            "before its layout was recorded (em.modes2d results before em-modes2d-p1-node-centroid-v1) must "
            "be regenerated: run its model.json again into a new directory "
            "(python -m simcase run model.json -o <new directory>) and export that fields.npz")
    return str(data["field_layout"])


def _load(fields_npz):
    with np.load(fields_npz, allow_pickle=False) as archive:
        return {key: archive[key] for key in archive.files}


def export_fields(fields_npz, output, *, time_index=-1):
    """Write the fields of a saved result to the VTU file ``output``.

    Region layouts also include static cell data ``triangle_regions``. Its IDs
    index ``region_names`` in the saved metadata/summary; no names or material
    properties are copied to VTU. Complex cavity fields are written as
    ``_real``/``_imag`` pairs. ``time_index`` applies to transient layouts
    only. A waveguide mode result (``em-modes2d-p1-node-centroid-v1``) must
    hold one study point; ``export_sweep`` writes sweeps. Refuses to overwrite
    an existing file. Returns the output path.
    """
    output = Path(output)
    if output.suffix.lower() != ".vtu":
        raise ValueError("output must end in .vtu")
    if output.exists():
        raise FileExistsError(f"{output} already exists; choose a new file name")
    data = _load(fields_npz)
    layout = _layout(data)
    if layout in _THERMAL_LAYOUTS:
        parts = _thermal(data, layout, time_index)
    elif layout == _ELECTRIC_JOULE:
        parts = _electric_joule(data)
    elif layout == _CAVITY:
        parts = _cavity(data)
    elif layout == _CAVITY_COMPLEX:
        parts = _cavity_complex(data)
    elif layout == _MODES:
        parts = _modes(data)
    elif layout == _MODES_SUBSPACE:
        _refuse_subspace()
    else:
        raise ValueError(f"unsupported field layout {layout!r}; supported: {SUPPORTED_LAYOUTS}")
    points, cells, point_data, cell_data = parts
    meshio = _meshio()
    mesh = meshio.Mesh(points, cells, point_data=point_data, cell_data=cell_data)
    meshio.vtu.write(output, mesh, binary=True, compression="zlib")
    return output


def _collection_target(output_dir, name):
    """Check a collection's file stem and output directory before anything is read or written."""
    if not isinstance(name, str) or not name or name in (".", "..") or any(
            c in name for c in '/\\:'):
        raise ValueError("name must be a plain file stem without path separators")
    output_dir = Path(output_dir)
    if os.path.lexists(output_dir) and (not output_dir.is_dir() or any(output_dir.iterdir())):
        raise FileExistsError(f"{output_dir} exists and is not an empty directory; "
                              "choose a new or empty output directory")
    return output_dir


def _write_collection(output_dir, name, points, cells, count, frames):
    """Write ``<name>_<k>.vtu`` per frame and the collection ``<name>.pvd``.

    ``frames`` yields ``count`` tuples ``(timestep, point_data, cell_data)`` in
    order; each timestep is written with ``repr`` so it round-trips exactly.
    Files are listed by relative POSIX name. On failure every file this call
    wrote, and the directory if it created it, are removed. Returns the ``.pvd``
    path.
    """
    meshio = _meshio()
    width = max(5, len(str(count - 1)))
    created_dir = not output_dir.exists()
    output_dir.mkdir(parents=True, exist_ok=True)
    written = []
    collection = ET.Element("VTKFile", type="Collection", version="0.1", byte_order="LittleEndian")
    datasets = ET.SubElement(collection, "Collection")
    try:
        for index, (timestep, point_data, cell_data) in enumerate(frames):
            file_name = f"{name}_{index:0{width}d}.vtu"
            target = output_dir / file_name
            if os.path.lexists(target):
                raise FileExistsError(f"{target} appeared during export")
            mesh = meshio.Mesh(points, cells, point_data=point_data, cell_data=cell_data)
            written.append(target)
            meshio.vtu.write(target, mesh, binary=True, compression="zlib")
            ET.SubElement(datasets, "DataSet", timestep=repr(float(timestep)), group="", part="0",
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


def export_time_series(fields_npz, output_dir, *, name="fields"):
    """Write every stored time of a transient heat result for ParaView.

    Writes ``<name>_<k>.vtu`` for each stored time ``k`` (zero-padded) and the
    collection ``<name>.pvd`` into ``output_dir``, which must be new or empty;
    nothing is overwritten. Each VTU holds the arrays stored at that time, so
    ``reaction_w_per_m``, ``residual_w_per_m`` and ``storage_rate_w_per_m``
    appear from the second time on. The ``.pvd`` lists each file by a relative
    POSIX path with ``time_s`` as its timestep (written with ``repr``, so the
    value round-trips exactly). On failure, files written so far are removed.
    Region layouts include the same static ``triangle_regions`` in every VTU.
    Returns the ``.pvd`` path.
    """
    output_dir = _collection_target(output_dir, name)
    data = _load(fields_npz)
    layout = _layout(data)
    if layout not in _TRANSIENT_LAYOUTS:
        raise ValueError(f"time series export needs layout in {_TRANSIENT_LAYOUTS!r}, got {layout!r}")
    times = np.asarray(data["time_s"], dtype=float)
    if times.ndim != 1 or not len(times):
        raise ValueError("time_s must be a non-empty 1D array")
    points = _points(data["nodes_m"])
    cells = [("triangle", np.asarray(data["triangles"], dtype=np.int64))]
    region_data = _region_cell_data(data, layout)

    def frames():
        for index, time in enumerate(times):
            point_data, cell_data = _transient_at(data, index)
            cell_data.update(region_data)
            yield time, point_data, cell_data

    return _write_collection(output_dir, name, points, cells, len(times), frames())


def export_sweep(fields_npz, output_dir, *, name="fields"):
    """Write every study point of a waveguide mode result for ParaView.

    Takes the layout ``em-modes2d-p1-node-centroid-v1`` with any number of
    study points and writes ``<name>_<k>.vtu`` per point ``k`` (zero-padded)
    plus the collection ``<name>.pvd`` into ``output_dir``, which must be new
    or empty. Each VTU holds that point's modes as ``export_fields`` writes
    them (points in metres, static ``triangle_regions``). The ``.pvd``
    timestep is the swept wavelength in the document length unit
    (``mesh_length_unit``) when the saved ``study_parameter`` is a wavelength
    and ``values`` are strictly monotone (every vector and PML sweep), and the
    point index otherwise (a scalar sweep of another parameter, or one whose
    values repeat or reverse); the values themselves stay in ``fields.npz``.
    On failure, files written so far are removed. The subspace layout is
    refused. Returns the ``.pvd`` path.
    """
    output_dir = _collection_target(output_dir, name)
    data = _load(fields_npz)
    layout = _layout(data)
    if layout == _MODES_SUBSPACE:
        _refuse_subspace()
    if layout != _MODES:
        raise ValueError(f"sweep export needs layout {_MODES!r}, got {layout!r}")
    points, cells, static = _modes_mesh(data)
    count, arrays = _mode_arrays(data)
    timesteps = _sweep_timesteps(data, count)

    def frames():
        for index in range(count):
            point_data, cell_data = _modes_at(arrays, index)
            cell_data.update(static)
            yield timesteps[index], point_data, cell_data

    return _write_collection(output_dir, name, points, cells, count, frames())
