# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Export saved fields to VTU for ParaView and other VTK viewers.

Reads a ``fields.npz`` written by ``save()`` and writes one mesh file with
meshio (MIT), installed by the optional extra ``simcase[export]``. The saved
``fields.npz`` stays the reference result; the export is a viewing copy.

Supported layouts:

- rectangle heat, format 0.3 (``thermal2d-p1-node-cell-v2``; with flux or
  convection sides ``thermal2d-p1-node-cell-boundary-v3``): point data
  ``temperature`` and the nodal ``generated_heat_rate_per_depth``,
  ``reaction_heat_rate_per_depth`` and ``residual_heat_rate_per_depth`` arrays,
  plus ``outward_prescribed_heat_rate_per_depth``,
  ``ambient_convective_heat_rate_per_depth``,
  ``outward_convective_heat_rate_per_depth`` and ``applied_heat_rate_per_depth``
  with boundary sides (W/m); cell data ``heat_flux``. Each name is its
  ``fields.npz`` name, and a ``<FieldData>`` block holds two ``UInt8`` arrays
  (UTF-8 JSON): ``units`` (each exported array's canonical unit, the same as
  ``field_units``) and ``conventions`` (the registry sign sentence of each signed
  array)
- transient rectangle heat, format 0.3 (``thermal2d-transient-p1-node-cell-v2``;
  with flux or convection sides ``thermal2d-transient-p1-node-cell-boundary-v2``):
  the same arrays plus ``heat_storage_rate_per_depth`` at one stored time
  (``time_index``, default the last), or every stored time with
  ``export_time_series``: one VTU per time plus a ParaView collection (``.pvd``)
  that records each ``time`` (s) as its timestep. The step rates are present from
  the second stored time on. Each VTU carries the same FieldData block
- region heat, format 0.3 (``thermal2d-p1-node-cell-regions-v2``,
  ``thermal2d-transient-p1-node-cell-regions-v2`` and the axisymmetric
  ``thermal-axisymmetric-p1-node-cell-regions-v2`` and
  ``thermal-axisymmetric-transient-p1-node-cell-regions-v2``): the rectangle
  arrays and FieldData block, plus the static integer cell data
  ``triangle_regions`` (no unit). An axisymmetric result has (r, z) points and
  full-revolution rates without ``_per_depth`` (W, J)
- the heat, electric and Joule layouts saved before the units and naming batch
  (``RETIRED_LAYOUTS``) are refused by name: re-create the document in format 0.3
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
- electric conduction and Joule heating, format 0.3 (``electric-joule2d-p1-v2``, the
  layout of ``electric.steady2d``, ``joule.steady2d`` and ``joule.temperature2d``; and
  ``electric2d-p1-node-cell-regions-v2`` of region ``electric.steady2d`` and
  ``electric-joule2d-p1-node-cell-regions-v2`` of region ``joule.steady2d``, which add
  the static integer cell data ``triangle_regions``): point data
  ``electric_potential`` and the nodal ``joule_power_per_depth``,
  ``reaction_current_per_depth``, ``outward_prescribed_current_per_depth`` and
  ``residual_current_per_depth``; cell data ``electric_field``, ``current_density``,
  ``electrical_conductivity`` and ``joule_power_density`` at centroids. A Joule result
  adds ``temperature``, the nodal heat rates and cell ``heat_flux``; a
  temperature-dependent one adds ``evaluation_temperature``. Each name is its
  ``fields.npz`` name, and the FieldData block holds ``units`` and ``conventions``
- waveguide modes (``em-modes2d-p1-node-centroid-v2``, the layout of
  ``em.modes2d`` results tracked per mode, SI under exp(-i omega t)): points are
  the saved ``node_coordinates`` in metres. Each array is named by its
  ``fields.npz`` name with the per-mode suffix ``_mode_<k>`` (zero-based column)
  and, for a complex array, the parts ``_real``/``_imag``: a scalar result
  writes the nodal ``unnormalized_mode_field_mode_<k>`` (complex when lossy or
  with PML); a vector result writes the complex centroid field as cell data
  ``unnormalized_electric_field_mode_<k>_real``/``_imag`` (x, y, z; the saved
  relative normalization, maximum centroid |E| = 1) and the complex nodal
  longitudinal component as point data
  ``unnormalized_electric_field_z_mode_<k>_real``/``_imag``. Every mode VTU
  carries the static integer cell data ``regions`` and the FieldData ``units``
  and ``conventions`` (with ``time_convention`` when an array is complex).
  ``export_fields`` takes a single-point result; ``export_sweep`` writes one VTU
  per study point plus a ``.pvd`` collection whose timestep is the vacuum
  wavelength in metres for a strictly monotone wavelength sweep and the point
  index otherwise. PML results (``field_representation`` ``pml-*``) use the same
  layout: the arrays cover the absorbing layer too, where the fields are
  artificial. ``effective_index``, ``edges``, the edge line integrals, tracking
  and open-boundary diagnostics stay in ``fields.npz``. The subspace layout
  ``em-modes2d-subspace-raw-v2`` (raw eigenpair columns per cluster) is
  refused.
- 2D linear elasticity (``mechanics2d-p1-v2``, the layout of
  ``mechanics.elasticity2d``): point data ``displacement`` and the nodal
  ``applied_force_per_depth``, ``reaction_force_per_depth`` and
  ``residual_force_per_depth`` arrays as vectors with a zero z component; cell
  data one named scalar per saved component, by its ``field_components`` name:
  ``strain_xx``, ``strain_yy``, ``engineering_shear_strain_xy`` from ``strain``
  and ``stress_xx``, ``stress_yy``, ``stress_xy`` from ``stress``.
- steady heat then thermal stress (``thermoelastic2d-p1-v2``, the layout of
  ``mechanics.thermoelastic2d``): point data ``temperature`` and the nodal heat
  rates (W/m) as scalars, ``displacement`` and the nodal applied, thermal
  equivalent, body, traction, reaction and residual force arrays (N/m) as
  vectors; cell data ``heat_flux`` (vector), ``stress_zz`` and ``strain_zz``
  (scalars) and the named components of ``strain``, ``thermal_strain``
  (``thermal_strain_xx``, ..., ``engineering_shear_thermal_strain_xy``),
  ``elastic_strain`` and ``stress``. Both mechanics layouts carry the FieldData
  ``units`` and ``conventions``; the region mechanics layouts are not exported.

Dirichlet node lists, ``metadata_json`` and the summary are not copied: the
arrays named above are exported when the saved file holds them, nothing else.
A ``fields.npz`` without a ``field_layout`` array is refused: results saved
before their layout was recorded must be regenerated from their ``model.json``.

2D coordinates get z = 0, and 2D cell vectors get a zero z component, as VTK
expects. Times, frequencies and units stay in ``fields.npz`` and
``summary.json``. XDMF is not offered: meshio's XDMF writer requires h5py.
The ``.pvd`` collection is plain VTK XML written with the standard library.
"""

import json
import os
from pathlib import Path
import xml.etree.ElementTree as ET

import numpy as np

__all__ = ["export_fields", "export_time_series", "export_sweep", "SUPPORTED_LAYOUTS", "RETIRED_LAYOUTS",
           "inject_field_data", "read_field_data"]

#: layout identifiers of results saved before the units and naming batch, each mapped to the
#: identifier that replaced it; such a fields.npz is refused by name. Each kind's commit of
#: the batch moves its identifiers here when it replaces them in SUPPORTED_LAYOUTS.
RETIRED_LAYOUTS: dict[str, str] = {
    "thermal2d-p1-node-cell-v1": "thermal2d-p1-node-cell-v2",
    "thermal2d-p1-node-cell-boundary-v2": "thermal2d-p1-node-cell-boundary-v3",
    "thermal2d-transient-p1-node-cell-v1": "thermal2d-transient-p1-node-cell-v2",
    "thermal2d-transient-p1-node-cell-boundary-v1": "thermal2d-transient-p1-node-cell-boundary-v2",
    "thermal2d-p1-node-cell-regions-v1": "thermal2d-p1-node-cell-regions-v2",
    "thermal2d-transient-p1-node-cell-regions-v1": "thermal2d-transient-p1-node-cell-regions-v2",
    "thermal-axisymmetric-p1-node-cell-regions-v1": "thermal-axisymmetric-p1-node-cell-regions-v2",
    "thermal-axisymmetric-transient-p1-node-cell-regions-v1": "thermal-axisymmetric-transient-p1-node-cell-regions-v2",
    "electric-joule2d-p1-v1": "electric-joule2d-p1-v2",
    "electric2d-p1-node-cell-regions-v1": "electric2d-p1-node-cell-regions-v2",
    "electric-joule2d-p1-node-cell-regions-v1": "electric-joule2d-p1-node-cell-regions-v2",
    "mechanics2d-p1-v1": "mechanics2d-p1-v2",
    "thermoelastic2d-p1-v1": "thermoelastic2d-p1-v2",
    "em-modes2d-p1-node-centroid-v1": "em-modes2d-p1-node-centroid-v2",
    "em-modes2d-subspace-raw-v1": "em-modes2d-subspace-raw-v2",
}

# rectangle heat (format 0.3): arrays under registry names, SI, with VTU unit metadata
_STEADY = "thermal2d-p1-node-cell-v2"
_STEADY_BOUNDARY = "thermal2d-p1-node-cell-boundary-v3"
_TRANSIENT = "thermal2d-transient-p1-node-cell-v2"
_TRANSIENT_BOUNDARY = "thermal2d-transient-p1-node-cell-boundary-v2"
_STEADY_REGIONS = "thermal2d-p1-node-cell-regions-v2"
_AXISYMMETRIC_REGIONS = "thermal-axisymmetric-p1-node-cell-regions-v2"   # (r, z) points; rates in W, plain names
_TRANSIENT_REGIONS = "thermal2d-transient-p1-node-cell-regions-v2"
_TRANSIENT_AXISYMMETRIC_REGIONS = "thermal-axisymmetric-transient-p1-node-cell-regions-v2"   # (r, z); W, plain names
_HEAT_03 = (_STEADY, _STEADY_BOUNDARY, _TRANSIENT, _TRANSIENT_BOUNDARY, _STEADY_REGIONS, _TRANSIENT_REGIONS,
            _AXISYMMETRIC_REGIONS, _TRANSIENT_AXISYMMETRIC_REGIONS)
_CAVITY = "cavity3d-edge-v1"
_CAVITY_COMPLEX = "cavity3d-edge-complex-v1"
# electric and Joule (format 0.3): arrays under registry names, SI, with VTU unit metadata
_ELECTRIC_JOULE = "electric-joule2d-p1-v2"
_ELECTRIC_REGIONS = "electric2d-p1-node-cell-regions-v2"   # electric.steady2d on material regions
_JOULE_REGIONS = "electric-joule2d-p1-node-cell-regions-v2"   # joule.steady2d on material regions
_ELECTRIC_LAYOUTS = (_ELECTRIC_JOULE, _ELECTRIC_REGIONS, _JOULE_REGIONS)
_MODES = "em-modes2d-p1-node-centroid-v2"
_MODES_SUBSPACE = "em-modes2d-subspace-raw-v2"
# mechanics (format 0.3): arrays under registry names, SI, with VTU unit metadata
_MECHANICS = "mechanics2d-p1-v2"
_THERMOELASTIC = "thermoelastic2d-p1-v2"
_MECHANICS_LAYOUTS = (_MECHANICS, _THERMOELASTIC)
_TRANSIENT_LAYOUTS = (_TRANSIENT, _TRANSIENT_REGIONS, _TRANSIENT_BOUNDARY, _TRANSIENT_AXISYMMETRIC_REGIONS)
_REGION_LAYOUTS = (_STEADY_REGIONS, _TRANSIENT_REGIONS, _AXISYMMETRIC_REGIONS, _TRANSIENT_AXISYMMETRIC_REGIONS)
# the order of SUPPORTED_LAYOUTS is pinned by tests: new layouts go at the end
SUPPORTED_LAYOUTS = (_STEADY, _STEADY_BOUNDARY, _TRANSIENT, _CAVITY, _STEADY_REGIONS, _TRANSIENT_REGIONS,
                     _ELECTRIC_JOULE, _CAVITY_COMPLEX, _TRANSIENT_BOUNDARY, _MODES, *_MECHANICS_LAYOUTS,
                     _AXISYMMETRIC_REGIONS, _TRANSIENT_AXISYMMETRIC_REGIONS, _ELECTRIC_REGIONS, _JOULE_REGIONS)
#: nodal arrays of the format 0.3 heat layouts; the steps rates start at the second stored time
_RATES_03 = ("generated_heat_rate", "reaction_heat_rate", "residual_heat_rate", "heat_storage_rate",
             "outward_prescribed_heat_rate", "ambient_convective_heat_rate", "outward_convective_heat_rate",
             "applied_heat_rate")
# planar layouts save the rates per depth; the axisymmetric ones over the full revolution (plain names)
_NODAL_03 = ("temperature", *(name + "_per_depth" for name in _RATES_03), *_RATES_03)
# electric and Joule arrays by VTK association; absent arrays are skipped (a plain electric
# result has no heat arrays, only joule.temperature2d has evaluation_temperature). Prescribed
# node lists are not exported.
_ELECTRIC_NODAL = ("electric_potential", "joule_power_per_depth", "reaction_current_per_depth",
                   "outward_prescribed_current_per_depth", "residual_current_per_depth",
                   "temperature", "generated_heat_rate_per_depth", "reaction_heat_rate_per_depth",
                   "residual_heat_rate_per_depth", "outward_prescribed_heat_rate_per_depth",
                   "ambient_convective_heat_rate_per_depth", "outward_convective_heat_rate_per_depth",
                   "applied_heat_rate_per_depth", "evaluation_temperature")
_ELECTRIC_CELL_VECTORS = ("electric_field", "current_density", "heat_flux")
_ELECTRIC_CELL_SCALARS = ("electrical_conductivity", "joule_power_density")
# mechanics2d-p1-v2 and thermoelastic2d-p1-v2: (N,) nodal scalars, (N,2) nodal
# vectors, (T,2) cell vectors, (T,) cell scalars and (T,3) element arrays split
# into named scalar cell data, their field_components names in the saved order.
# Prescribed node and DOF lists stay in fields.npz; absent arrays are skipped.
_MECHANICS_NODAL_SCALARS = ("temperature", "generated_heat_rate_per_depth", "reaction_heat_rate_per_depth",
                            "residual_heat_rate_per_depth", "outward_prescribed_heat_rate_per_depth",
                            "ambient_convective_heat_rate_per_depth", "outward_convective_heat_rate_per_depth",
                            "applied_heat_rate_per_depth")
_MECHANICS_NODAL = ("displacement", "applied_force_per_depth", "thermal_equivalent_force_per_depth",
                    "applied_body_force_per_depth", "applied_traction_force_per_depth", "reaction_force_per_depth",
                    "residual_force_per_depth")
_MECHANICS_CELL_VECTORS = ("heat_flux",)
_MECHANICS_CELL_SCALARS = ("stress_zz", "strain_zz")
_MECHANICS_CELL = {"strain": ("strain_xx", "strain_yy", "engineering_shear_strain_xy"),
                   "thermal_strain": ("thermal_strain_xx", "thermal_strain_yy", "engineering_shear_thermal_strain_xy"),
                   "elastic_strain": ("elastic_strain_xx", "elastic_strain_yy", "engineering_shear_elastic_strain_xy"),
                   "stress": ("stress_xx", "stress_yy", "stress_xy")}
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


def _transient_at_03(data, index):
    """Point and cell data of a format 0.3 transient heat result at the stored time ``index``."""
    times = np.asarray(data["time"], dtype=float)
    point_data = {}
    for name in _NODAL_03:
        if name not in data:
            continue
        history = np.asarray(data[name], dtype=float)
        offset = len(times) - len(history)
        if index - offset >= 0:
            point_data[name] = history[index - offset]
    cell_data = {"heat_flux": [_vector3(np.asarray(data["heat_flux"])[index])]}
    return point_data, cell_data


def _heat_03(data, layout, time_index):
    points = _points(data["node_coordinates"])
    cells = [("triangle", np.asarray(data["triangles"], dtype=np.int64))]
    if layout in _TRANSIENT_LAYOUTS:
        index = range(len(data["time"]))[time_index]  # IndexError for an invalid index
        point_data, cell_data = _transient_at_03(data, index)
    else:
        point_data = {name: np.asarray(data[name], dtype=float) for name in _NODAL_03 if name in data}
        cell_data = {"heat_flux": [_vector3(data["heat_flux"])]}
    cell_data.update(_region_cell_data(data, layout))
    return points, cells, point_data, cell_data


#: exported arrays without a unit: the static region ids of a region layout
_STRUCTURAL = ("triangle_regions",)


def _unit_metadata(names, complex_names=()):
    """The FieldData ``units`` and ``conventions`` of the exported arrays: each array's
    canonical unit and, for a signed quantity, its registry sign sentence."""
    from physmat import units as registry
    found = {name: registry.quantity(name) for name in names}
    conventions = {"sign": {name: q.sign["en"] for name, q in found.items() if q.sign}}
    if complex_names:
        from .results_common import TIME_CONVENTION
        conventions["time_convention"] = TIME_CONVENTION
    return {name: q.unit for name, q in found.items()}, conventions


def _region_cell_data(data, layout):
    """Static dimensionless region IDs, without renumbering or interpolation."""
    if layout not in (*_REGION_LAYOUTS, _ELECTRIC_REGIONS, _JOULE_REGIONS):
        return {}
    regions = np.asarray(data.get("triangle_regions"))
    if (regions.shape != (len(data["triangles"]),) or regions.dtype.kind not in "iu"
            or np.any(regions < 0)):
        raise ValueError("triangle_regions must contain one non-negative integer per triangle")
    return {"triangle_regions": [regions]}


def _electric_joule(data):
    points = _points(data["node_coordinates"])
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
    if "electric_potential" not in point_data:
        raise ValueError("an electric or Joule export needs the saved electric_potential array")
    return points, cells, point_data, cell_data


def _mechanics(data, layout):
    points = _points(data["node_coordinates"])
    triangles = np.asarray(data["triangles"], dtype=np.int64)
    cells = [("triangle", triangles)]
    point_data, cell_data = {}, {}
    for name in _MECHANICS_NODAL_SCALARS:
        if name in data:
            values = np.asarray(data[name], dtype=float)
            if values.shape != (len(points),):
                raise ValueError(f"{name}: expected one value per node, got shape {values.shape}")
            point_data[name] = values
    for name in _MECHANICS_NODAL:
        if name in data:
            values = np.asarray(data[name], dtype=float)
            if values.shape != (len(points), 2):
                raise ValueError(f"{name}: expected one 2D vector per node, got shape {values.shape}")
            point_data[name] = _vector3(values)
    for name in _MECHANICS_CELL_VECTORS:
        if name in data:
            values = np.asarray(data[name], dtype=float)
            if values.shape != (len(triangles), 2):
                raise ValueError(f"{name}: expected one 2D vector per triangle, got shape {values.shape}")
            cell_data[name] = [_vector3(values)]
    for name in _MECHANICS_CELL_SCALARS:
        if name in data:
            values = np.asarray(data[name], dtype=float)
            if values.shape != (len(triangles),):
                raise ValueError(f"{name}: expected one value per triangle, got shape {values.shape}")
            cell_data[name] = [values]
    for name, components in _MECHANICS_CELL.items():
        if name in data:
            values = np.asarray(data[name], dtype=float)
            if values.shape != (len(triangles), 3):
                raise ValueError(f"{name}: expected three components per triangle, got shape {values.shape}")
            for k, component in enumerate(components):
                cell_data[component] = [np.ascontiguousarray(values[:, k])]
    if "displacement" not in point_data:
        raise ValueError(f"{layout} export needs the saved displacement array")
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
    """Points in metres (the saved ``node_coordinates``), triangle cells and the static region
    IDs of a mode result."""
    points = _points(data["node_coordinates"])
    triangles = np.asarray(data["triangles"], dtype=np.int64)
    regions = np.asarray(data["regions"])
    if regions.shape != (len(triangles),) or regions.dtype.kind not in "iu" or np.any(regions < 0):
        raise ValueError("regions must contain one non-negative integer per triangle")
    return points, [("triangle", triangles)], {"regions": [regions]}


def _mode_arrays(data):
    """(study points, validated per-point arrays) of a mode result.

    A scalar result holds ``unnormalized_mode_field`` (points, nodes, modes); a vector result
    ``unnormalized_electric_field`` (points, triangles, modes, 3) and, when saved,
    ``unnormalized_electric_field_z`` (points, nodes, modes).
    """
    n_nodes, n_triangles = len(data["node_coordinates"]), len(data["triangles"])
    if "unnormalized_electric_field" in data:
        electric = np.asarray(data["unnormalized_electric_field"])
        if electric.ndim != 4 or electric.shape[1] != n_triangles or electric.shape[3] != 3:
            raise ValueError("unnormalized_electric_field: expected shape (points, triangles, modes, 3) with "
                             f"{n_triangles} triangles, got {electric.shape}")
        count, modes = electric.shape[0], electric.shape[2]
        arrays = {"unnormalized_electric_field": electric}
        if "unnormalized_electric_field_z" in data:
            longitudinal = np.asarray(data["unnormalized_electric_field_z"])
            if longitudinal.shape != (count, n_nodes, modes):
                raise ValueError(f"unnormalized_electric_field_z: expected shape {(count, n_nodes, modes)}, "
                                 f"got {longitudinal.shape}")
            arrays["unnormalized_electric_field_z"] = longitudinal
    elif "unnormalized_mode_field" in data:
        fields = np.asarray(data["unnormalized_mode_field"])
        if fields.ndim != 3 or fields.shape[1] != n_nodes:
            raise ValueError(f"unnormalized_mode_field: expected shape (points, nodes, modes) with {n_nodes} nodes, "
                             f"got {fields.shape}")
        count, arrays = fields.shape[0], {"unnormalized_mode_field": fields}
    else:
        raise ValueError(f"{_MODES} export needs the saved unnormalized_mode_field (scalar) or "
                         "unnormalized_electric_field (vector) array")
    values = np.asarray(data["vacuum_wavelength"])
    if values.shape != (count,):
        raise ValueError(f"vacuum_wavelength: expected one value per study point, {(count,)}, got {values.shape}")
    return count, arrays


def _modes_at(arrays, index):
    """Point and cell data of the modes at study point ``index``, named by the saved array
    with the suffix ``_mode_<k>`` and, for a complex array, ``_real``/``_imag``."""
    point_data, cell_data = {}, {}
    if "unnormalized_mode_field" in arrays:
        fields = arrays["unnormalized_mode_field"][index]
        for k in range(fields.shape[1]):
            name = f"unnormalized_mode_field_mode_{k}"
            if fields.dtype.kind == "c":
                point_data[f"{name}_real"], point_data[f"{name}_imag"] = _real_imag(fields[:, k])
            else:
                point_data[name] = np.ascontiguousarray(fields[:, k], dtype=float)
        return point_data, cell_data
    electric = arrays["unnormalized_electric_field"][index]
    for k in range(electric.shape[1]):
        real, imag = _real_imag(electric[:, k, :])
        cell_data[f"unnormalized_electric_field_mode_{k}_real"] = [real]
        cell_data[f"unnormalized_electric_field_mode_{k}_imag"] = [imag]
    if "unnormalized_electric_field_z" in arrays:
        longitudinal = arrays["unnormalized_electric_field_z"][index]
        for k in range(longitudinal.shape[1]):
            real, imag = _real_imag(longitudinal[:, k])
            point_data[f"unnormalized_electric_field_z_mode_{k}_real"] = real
            point_data[f"unnormalized_electric_field_z_mode_{k}_imag"] = imag
    return point_data, cell_data


def _modes_metadata(names):
    """The FieldData ``units`` and ``conventions`` of exported mode arrays (``<array>_mode_<k>``
    with ``_real``/``_imag`` parts): each name's unit is its saved array's; a complex part adds
    the time convention."""
    from physmat import units as registry
    import re
    pattern = re.compile(r"(.+)_mode_\d+(_real|_imag)?")
    units, signs, complex_ = {}, {}, False
    for name in names:
        if name == "regions":
            continue
        found = pattern.fullmatch(name)
        base = found.group(1)
        quantity = registry.quantity("unnormalized_electric_field" if base == "unnormalized_electric_field_z"
                                     else base)
        units[name] = quantity.unit
        if quantity.sign:
            signs[name] = quantity.sign["en"]
        complex_ = complex_ or found.group(2) is not None
    conventions = {"sign": signs}
    if complex_:
        from .results_common import TIME_CONVENTION
        conventions["time_convention"] = TIME_CONVENTION
    return units, conventions


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
    """Vacuum wavelengths in metres of a strictly monotone wavelength sweep, else point indices."""
    values = np.asarray(data["vacuum_wavelength"], dtype=float)
    steps = np.diff(values)
    if str(data.get("study_parameter", "")).endswith(".vacuum_wavelength") and (
            np.all(steps > 0) or np.all(steps < 0)):
        return [float(v) for v in values]
    return [float(i) for i in range(count)]


def _refuse_subspace():
    raise ValueError(
        f"layout {_MODES_SUBSPACE!r} holds raw eigenpair columns per cluster (effective_index and the "
        "unnormalized_* fields of each column, frame_transform), not tracked modes; their VTU export is deferred. "
        "Read them from fields.npz, or run the sweep with resolved-mode tracking "
        f"(the default) for the per-mode layout {_MODES!r}")


def _layout(data):
    """The saved layout identifier. A file without one cannot be interpreted; a retired one is refused."""
    if "field_layout" not in data:
        raise ValueError(
            "fields.npz has no 'field_layout' array, so its layout cannot be identified. A result saved "
            "before its layout was recorded (em.modes2d results before em-modes2d-p1-node-centroid-v1) must "
            "be regenerated: run its model.json again into a new directory "
            "(python -m simcase run model.json -o <new directory>) and export that fields.npz")
    layout = str(data["field_layout"])
    if layout in RETIRED_LAYOUTS:
        raise ValueError(f"saved before the units and naming batch (layout {layout}); re-create the document in "
                         "format 0.3 and run it")
    return layout


# -- unit metadata in VTU -------------------------------------------------------------------------

def _uint8_array(name: str, value) -> str:
    data = json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False).encode("utf-8")
    numbers = " ".join(str(b) for b in data)
    return (f'<DataArray type="UInt8" Name="{name}" NumberOfTuples="{len(data)}" format="ascii">\n'
            f"{numbers}\n</DataArray>\n")


def inject_field_data(path, units: dict, conventions: dict) -> None:
    """Insert the unit metadata into a VTU file meshio wrote.

    Adds ``<FieldData>`` as the first child of ``<UnstructuredGrid>`` with two ``UInt8`` arrays
    in ASCII: ``units``, the UTF-8 bytes of a JSON map of every exported array to its canonical
    unit, and ``conventions``, the UTF-8 bytes of a JSON object (the time convention of complex
    arrays and the sign sentences of signed quantities). ``UInt8``, not ``String``: meshio 5.3
    cannot read a ``String`` array back, and it drops field data when it writes VTU itself.
    Every other byte of the file stays as written."""
    path = Path(path)
    data = path.read_bytes()
    tag = b"<UnstructuredGrid>"
    at = data.find(tag)
    if at < 0 or data.count(tag) != 1 or b"<FieldData" in data:
        raise ValueError(f"{path}: expected one VTU UnstructuredGrid without FieldData")
    block = ("\n<FieldData>\n" + _uint8_array("units", units) + _uint8_array("conventions", conventions)
             + "</FieldData>").encode("utf-8")
    path.write_bytes(data[:at + len(tag)] + block + data[at + len(tag):])


def read_field_data(path) -> dict:
    """The JSON values of the ``UInt8`` FieldData arrays of a VTU file, read with ``xml.etree``."""
    root = ET.parse(path).getroot()
    out = {}
    for array in root.iter("FieldData"):
        for item in array:
            raw = bytes(int(b) for b in (item.text or "").split())
            out[item.get("Name")] = json.loads(raw.decode("utf-8"))
    return out


def _load(fields_npz):
    with np.load(fields_npz, allow_pickle=False) as archive:
        return {key: archive[key] for key in archive.files}


def export_fields(fields_npz, output, *, time_index=-1):
    """Write the fields of a saved result to the VTU file ``output``.

    Region layouts also include static cell data ``triangle_regions``. Its IDs
    index ``region_names`` in the saved metadata/summary; no names or material
    properties are copied to VTU. Complex cavity fields are written as
    ``_real``/``_imag`` pairs; elasticity strain and stress components become
    named scalar cell data. ``time_index`` applies to transient layouts
    only. A waveguide mode result (``em-modes2d-p1-node-centroid-v2``) must
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
    if layout in _HEAT_03:
        parts = _heat_03(data, layout, time_index)
    elif layout in _ELECTRIC_LAYOUTS:
        parts = _electric_joule(data)
        parts[3].update(_region_cell_data(data, layout))
    elif layout in _MECHANICS_LAYOUTS:
        parts = _mechanics(data, layout)
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
    if layout in (*_HEAT_03, *_ELECTRIC_LAYOUTS, *_MECHANICS_LAYOUTS):
        inject_field_data(output, *_unit_metadata([name for name in (*point_data, *cell_data)
                                                   if name not in _STRUCTURAL]))
    elif layout == _MODES:
        inject_field_data(output, *_modes_metadata([*point_data, *cell_data]))
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


def _write_collection(output_dir, name, points, cells, count, frames, metadata=None):
    """Write ``<name>_<k>.vtu`` per frame and the collection ``<name>.pvd``.

    ``frames`` yields ``count`` tuples ``(timestep, point_data, cell_data)`` in
    order; each timestep is written with ``repr`` so it round-trips exactly. With
    ``metadata`` (a function of the frame's array names giving ``units`` and
    ``conventions``), each VTU gets its FieldData unit block.
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
            if metadata is not None:
                inject_field_data(target, *metadata([*point_data, *cell_data]))
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
    times = np.asarray(data["time"], dtype=float)
    if times.ndim != 1 or not len(times):
        raise ValueError("time must be a non-empty 1D array")
    points = _points(data["node_coordinates"])
    cells = [("triangle", np.asarray(data["triangles"], dtype=np.int64))]
    region_data = _region_cell_data(data, layout)

    def frames_03():
        for index, time in enumerate(times):
            point_data, cell_data = _transient_at_03(data, index)
            cell_data.update(region_data)
            yield time, point_data, cell_data

    def metadata(names):
        return _unit_metadata([name for name in names if name not in _STRUCTURAL])

    return _write_collection(output_dir, name, points, cells, len(times), frames_03(), metadata)


def export_sweep(fields_npz, output_dir, *, name="fields"):
    """Write every study point of a waveguide mode result for ParaView.

    Takes the layout ``em-modes2d-p1-node-centroid-v2`` with any number of
    study points and writes ``<name>_<k>.vtu`` per point ``k`` (zero-padded)
    plus the collection ``<name>.pvd`` into ``output_dir``, which must be new
    or empty. Each VTU holds that point's modes as ``export_fields`` writes
    them (points in metres, static ``regions``, the FieldData unit block). The
    ``.pvd`` timestep is the vacuum wavelength in metres when the saved
    ``study_parameter`` is the wavelength and the values are strictly
    monotone (every vector and PML sweep), and the point index otherwise (a
    scalar sweep of another parameter, or one whose values repeat or reverse);
    the values themselves stay in ``fields.npz``.
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

    return _write_collection(output_dir, name, points, cells, count, frames(), _modes_metadata)
