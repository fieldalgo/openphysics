# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Run a document end to end: geometry -> mesh -> materials -> physics -> study -> results.

The pipeline is also available one stage at a time. ``build_mesh`` stops after
geometry, meshing and material resolution and hands back a ``MeshedModel``;
``solve_point`` takes that model and one physics setting. ``run`` is their
composition over the study points. A GUI previewing a mesh, or a future caching
layer that recomputes only what changed, uses the stages rather than repeating
them.

The stages speak SI and exp(-i omega t) (units batch C8, phase-2 spec §3.8): ``build_mesh``
returns nodes in metres, ``study_points`` the SI values of the swept slot, ``solve_point``
takes a resolved SI physics entry and returns SI results. The mode kernel underneath keeps its
micrometre frame and exp(+i omega t); two boundary functions, ``_to_kernel`` and ``_to_public``,
are the only places that conjugate a convention or scale a result (hazard H16).
"""

from __future__ import annotations

import copy
import dataclasses
import json
import time
from dataclasses import dataclass, field
from fractions import Fraction
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
import physmat

from galerkin import Mesh
from meshine import TriMesh, generate, shapes as mshapes

from . import modes_document, physics_em_modes2d, results_common, views
from .geometry import build_domain, provenance_edges_of, size_function
from .mesh_limits import _is_region_document, _mesh_limits
from . import units
from .fields import VectorField
from . import mode_postprocessing
from .registry import PhysicsKind, kind_of, kind_of_type, register
from .schema import Document, DocumentError
from .tracking import ModeTracker, ModeTrackingError, tracking_settings
from .subspace_tracking import SUBSPACE_METHOD, SubspaceTracker


if TYPE_CHECKING:
    from .cavity import CavityRunResult
    from .electric_joule import ElectricJouleRunResult
    from .mechanics import MechanicsRunResult
    from .subspace_result import SubspaceSweepResult
    from .thermal import ThermalRunResult
    from .transient_thermal import TransientThermalRunResult

#: Saved layout of ``em.modes2d`` results tracked per mode (``RunResult``): P1 nodal
#: scalar fields, or vector edge/nodal coefficients with the electric field at
#: triangle centroids, in SI under exp(-i omega t). ``field_representation`` keeps naming the
#: vector/PML representation; this identifier names the file layout the exporter reads.
FIELD_LAYOUT = "em-modes2d-p1-node-centroid-v2"
#: the complex-mode summary schema (``effective_index`` with its imaginary part, losses)
MODE_RESULT_SCHEMA = "openphysics.modes2d/3"
VECTOR_REPRESENTATION = "vector-edge-nodal-v2"
PML_REPRESENTATIONS = {"vector": "pml-vector-edge-nodal-v2", "scalar": "pml-scalar-nodal-v2"}
PML_CANDIDATES_SCHEMA = "openphysics.pml-candidates/2"
#: the modal phasor's propagation factor beside ``time_convention`` (exp(-i omega t))
PROPAGATION = "exp(+i beta z)"
#: the kernel's micrometre in metres: every kernel length comes back as ``x_um * 1e-6`` (H11)
KERNEL_LENGTH = units.UM_IN_SI
#: the kernel's square micrometre in square metres
KERNEL_AREA = 1e-12


def _kernel_length(metres) -> float:
    """A length in metres, in the kernel's micrometres: ``float(Fraction(repr(x)) * 10**6)``
    (equal to ``float(exact * 10**6)`` for every value of at most 15 significant digits)."""
    return float(Fraction(repr(float(metres))) * 10 ** 6)


def _to_kernel(relative_permittivity: np.ndarray) -> np.ndarray:
    """physmat's per-triangle permittivity (exp(-i omega t)) under the kernel's exp(+i omega t):
    the one conjugation on the way in (hazard H16)."""
    return np.conjugate(relative_permittivity)


@dataclass
class MeshedModel:
    """Everything a document determines before any physics runs.

    Depends only on the ``geometry``, ``mesh`` and ``materials`` sections, so it
    survives any change to ``physics`` or ``study`` -- which is what makes it
    worth caching. ``tri`` and ``mesh`` hold the nodes in metres (the micrometre mesh times
    1e-6, the same doubles as the saved ``node_coordinates``).
    """
    doc: Document
    tri: TriMesh                            # meshine output in metres: regions, quality, boundary edges
    mesh: Mesh                              # the same mesh as the solver wants it, in metres
    region_materials: dict[str, str]        # region name -> material reference ("physmat:Si", a local name)
    materials: dict[str, physmat.Material]  # region name -> resolved material
    #: The mesh in micrometres, as meshine produced it: the mode kernel runs on this one
    #: with the wavelength in micrometres, so a document's answer does not depend on its
    #: declared unit (internal; kernel frame).
    solver_mesh: Mesh | None = None
    #: meshine's micrometre output (internal; kernel frame)
    kernel_tri: TriMesh | None = None
    #: the micrometre kernel hand-off of the document (``modes_document.kernel_document``; internal)
    kernel_doc: Document | None = None

    def relative_permittivity(self, vacuum_wavelength: float) -> np.ndarray:
        """Relative permittivity of each triangle at one vacuum wavelength in metres, as physmat
        gives it: complex, under exp(-i omega t) (loss is a positive imaginary part).

        Dropping the imaginary part here would leave the physics with no way to tell a lossy
        material from a lossless one, and its own guard against loss would never fire.
        """
        return self._permittivity(_kernel_length(vacuum_wavelength))

    def _permittivity(self, wavelength_um: float) -> np.ndarray:
        """``relative_permittivity`` at a kernel wavelength in micrometres (physmat's own unit)."""
        tri = self.kernel_tri if self.kernel_tri is not None else self.tri
        lut = np.array([self.materials[n].eps(wavelength_um) for n in tri.region_names])
        return lut[tri.regions]


def build_mesh(doc: Document) -> MeshedModel:
    """Geometry -> mesh -> materials. The first stage of ``run``; nodes in metres."""
    doc.validate()
    refusal = kind_of(doc.data).stage_refusal
    if refusal is not None:
        raise DocumentError(refusal.format(stage="build_mesh"))
    # Geometry and meshing run in micrometres whatever the document declares: the same
    # device written in nm, um or m gives meshine the same doubles, and so the same mesh
    # (the kernel hand-off, modes_document.kernel_document). Coordinates come back as the
    # micrometre values times 1e-6 (hazard H11).
    k = modes_document.kernel_document(doc)
    grid = views.modes_mesh(k)
    canonical = grid.canonical
    before = len(canonical.notes)
    domain, namer, region_materials = build_domain(canonical)
    from .thermal_regions import mesh_diagnostics_03
    mesh_diagnostics_03(doc, modes_document.component(doc)[0], canonical.notes[before:])
    size_fn = None
    if grid.grading is not None:
        g = grid.grading
        size_fn = mshapes.size_graded(g.near, g.far, g.distance, center=g.center)
    size_fn = _combined_size(size_fn, size_function(canonical))
    tri_um = generate(domain, namer, min_angle=grid.minimum_angle_deg, size_fn=size_fn)
    if tri_um.num_triangles == 0 or tri_um.num_nodes == 0:
        raise DocumentError(
            f"meshing produced {tri_um.num_nodes} nodes and {tri_um.num_triangles} triangles. An empty mesh is "
            f"never a usable intermediate result, so it is refused here rather than in whatever reduction "
            f"reaches it first. The usual cause is an element_size or a feature far from the scale of the "
            f"length_unit this document declares.")
    tags = set(tri_um.boundary_edges)
    sides = {"left", "right", "bottom", "top"}
    if not sides <= tags or (tags != sides and canonical.geometry_model is not None):
        raise DocumentError(f"mesh: this runner takes exterior edges on the four domain sides only; found tags "
                            f"{sorted(tags)}. A boundary_tags entry that renames a side, a void region, a sliver "
                            "gap and an axisymmetric component's axis give other tags, which no physics here "
                            "accepts yet")
    tri = dataclasses.replace(tri_um, nodes=views.handback_m(tri_um.nodes))
    provenance = provenance_edges_of(canonical, tri_um)         # node pairs: the same in both frames
    materials = {region: modes_document.optical_material(doc, ref) for region, ref in region_materials.items()}
    return MeshedModel(doc, tri, _solver_mesh(tri, provenance), region_materials, materials,
                       solver_mesh=_solver_mesh(tri_um, provenance), kernel_tri=tri_um, kernel_doc=k)


def _combined_size(*functions):
    """The point-wise minimum of the given size functions, None when there is none."""
    functions = [f for f in functions if f is not None]
    if not functions:
        return None
    if len(functions) == 1:
        return functions[0]

    def h(x, y):
        out = functions[0](x, y)
        for f in functions[1:]:
            out = np.minimum(out, f(x, y))
        return out
    return h


def _solver_mesh(tri: TriMesh, provenance_edges: dict | None = None) -> Mesh:
    return Mesh(tri.nodes, tri.triangles, boundary=dict(tri.boundary_nodes),
                boundary_edges=dict(tri.boundary_edges), provenance_edges=provenance_edges)


def micrometre_document(doc: Document, *, validate: bool = True) -> Document:
    """The same EM or region heat document with every length in micrometres.

    Each number is converted once and exactly where it is representable
    (``units.length_to_micrometres``). A micrometre document comes back equal.
    This lists geometry/mesh lengths shared by EM and region heat documents,
    plus EM wavelength and dispersion lengths. SI-suffixed thermal properties
    and study times stay unchanged. Add new length fields here.

    ``validate=False`` takes the copy of a format 0.3 region hand-off
    (``thermal_regions.handoff_03``), which holds geometry and mesh only and was
    checked as its 0.3 document: the copy gets its unit scale and is not
    validated as a document of its own.
    """
    d = copy.deepcopy(doc.data)
    um = lambda v, power=1: units.length_to_micrometres(v, doc.scale, power)   # noqa: E731
    g = d["geometry"]
    if doc.is_version_1:
        # the exact model is unit-free (integer pm); the block stays as written and the
        # accessors read the model in the copy's micrometres
        pass
    else:
        g["domain"] = {k: um(v) for k, v in g["domain"].items()}
        if "mesh_size" in g["background"]:
            g["background"]["mesh_size"] = um(g["background"]["mesh_size"])
        for s in g["shapes"]:
            for k in ("x", "y", "w", "h", "cx", "cy", "r", "mesh_size"):
                if s.get(k) is not None:
                    s[k] = um(s[k])
            if "points" in s:
                s["points"] = [[um(c) for c in p] for p in s["points"]]
    m = d["mesh"]
    m["size"] = um(m["size"])
    for entry in m.get("controls") or []:
        for k in ("size", "near", "far", "distance"):
            if k in entry:
                entry[k] = um(entry[k])
    if m.get("grading"):
        gr = m["grading"]
        gr["center"] = [um(c) for c in gr["center"]]
        for k in ("near", "far", "distance"):
            gr[k] = um(gr[k])
    for p in d["physics"].values():
        if p.get("type") == "em.modes2d":
            p["wavelength"] = um(p["wavelength"])
            if "pml" in p:
                p["pml"]["thickness"] = {k: um(v) for k,v in p["pml"]["thickness"].items()}
            if "bend" in p:
                for key in ("radius", "origin"):
                    if key in p["bend"]: p["bend"][key] = um(p["bend"][key])
    st = d["study"]
    if st.get("type") == "sweep" and str(st.get("parameter", "")).endswith(".wavelength"):
        st["values"] = [um(v) for v in st["values"]]
    for spec in d["materials"].values():
        sm = spec.get("sellmeier") if isinstance(spec, dict) else None
        if sm:
            sm["C"] = [um(c, 2) for c in sm["C"]]
            if "range" in sm:
                sm["range"] = [um(r) for r in sm["range"]]
    gaussian = d.get("results", {}).get("mode_overlap", {}).get("gaussian")
    if gaussian is not None:
        gaussian["waist"] = um(gaussian["waist"])
        gaussian["center"] = [um(c) for c in gaussian["center"]]
    d["units"] = dict(d["units"], length="um")
    if doc.is_version_1:
        # the block is not re-read in micrometres: the model travels with the copy, and the
        # block in the copy's data stays in the document's unit (geometry_block_unit), so the
        # copy refuses to be serialised; results record the original document
        out = Document(d)
        out.geometry_block_unit = doc.geometry_block_unit or doc["units"]["length"]
        out.geometry_model = doc.geometry_model
        out.geometry_complex = doc.geometry_complex
        out.geometry_source, out.geometry_roundings = doc.geometry_source, list(doc.geometry_roundings)
        if validate:
            out.validate()
        else:
            out.scale = units.resolve(d["units"])
        return out
    if validate:
        out = Document.from_dict(d)
    else:
        out = Document(d)
        out.scale = units.resolve(d["units"])
    # the exact geometry of a version 1 document is unit-free (integer pm) and travels with it
    out.geometry_model = doc.geometry_model
    out.geometry_complex = doc.geometry_complex
    return out


def study_points(doc: Document) -> tuple[str | None, list]:
    """(parameter path, SI values) of the study; (None, [None]) for a single point. The path is
    the document's (``physics.<n>.vacuum_wavelength``); a wavelength is in metres."""
    study = doc.si["study"] if doc.si is not None else doc["study"]
    if study["type"] == "sweep":
        return study["parameter"], list(study["values"])
    return None, [None]


def _kernel_points(k: Document) -> tuple[str | None, list]:
    """(kernel parameter path, kernel values) of the hand-off's study (micrometre wavelengths)."""
    study = k["study"]
    if study["type"] == "sweep":
        return study["parameter"], list(study["values"])
    return None, [None]


def solve_point(model: MeshedModel, physics: dict) -> dict:
    """One physics solve on an already meshed model.

    ``physics`` is a resolved SI physics entry: ``doc.si["physics"][name]``, or the same entry of
    a ``doc.with_value(...)`` copy for one sweep point (``vacuum_wavelength`` in metres). The
    result is SI under exp(-i omega t): ``effective_index``, ``guided``, and
    ``unnormalized_mode_field`` (scalar) or ``vector_field`` (a ``VectorField``), plus
    ``open_boundary`` with PML. ``run`` and ``solve_point`` hand the kernel the same doubles."""
    kind = kind_of_type(physics.get("type"))
    if kind is not None and kind.stage_refusal is not None:
        raise DocumentError(kind.stage_refusal.format(stage="solve_point"))
    res = _kernel_solve(model, modes_document.stage_point(physics))
    return _to_public(None, model, res, point=True)


def _kernel_solve(model: MeshedModel, physics: dict) -> dict:
    """One kernel solve: ``physics`` in the kernel's keys and micrometres (the hand-off's entry,
    or ``modes_document.stage_point``), on the micrometre mesh. Kernel frame in and out."""
    eps = model._permittivity(physics["wavelength"])
    mesh = model.mesh if model.solver_mesh is None else model.solver_mesh
    point = views.modes_inputs(physics)
    # physmat uses n+ik; the kernel's modal phasor is exp(+i omega t-i beta z).
    try:
        return physics_em_modes2d.solve(mesh, _to_kernel(eps), point.wavelength, point.boundary,
                                        point.num_modes, point.formulation, point.n_cladding,
                                        n_target=point.n_target, pml=point.pml, bend=point.bend)
    except ValueError as exc:                    # the kernel's message under the document's names
        raise ValueError(modes_document.public_kernel_message(str(exc))) from exc


#: (40 pi / ln 10): the power attenuation in dB of exp(-2 Im(n_eff) k0 z) per unit Im(n_eff) / lambda0
PROPAGATION_LOSS_FACTOR = 40 * np.pi / np.log(10)

#: the saved arrays: registry quantity (None for a structural array), location, components
FIELDS = {
    "node_coordinates": ("node_coordinates", "nodes", ["x", "y"]),
    "triangles": (None, "triangle_connectivity", None),
    "regions": (None, "triangles", None),
    "region_names": (None, "regions", None),
    "edges": (None, "edge_connectivity", None),
    "vacuum_wavelength": ("vacuum_wavelength", "study_points", None),
    "effective_index": ("effective_index", "study_points_modes", None),
    "group_index": ("group_index", "study_points_modes", None),
    "unnormalized_mode_field": ("unnormalized_mode_field", "study_points_nodes_modes", None),
    "unnormalized_electric_field_line_integral": ("unnormalized_electric_field_line_integral",
                                                  "study_points_edges_modes", None),
    "unnormalized_electric_field_z": ("unnormalized_electric_field", "study_points_nodes_modes", ["z"]),
    "unnormalized_electric_field": ("unnormalized_electric_field", "study_points_triangle_centroids_modes",
                                    ["x", "y", "z"]),
    "unnormalized_mode_power": ("unnormalized_mode_power", "study_points_modes", None),
    "unnormalized_mode_field_square_integral": ("unnormalized_mode_field_square_integral", "study_points_modes",
                                                None),
    "confinement_factor": ("confinement_factor", "study_points_modes_regions", None),
    "unnormalized_field_overlap": ("unnormalized_field_overlap", "study_points_modes_modes", None),
    "coupling_efficiency": ("coupling_efficiency", "study_points_modes", None),
    "frame_transform": (None, "study_points_columns_columns", None),
    "cluster_ids": (None, "clusters", None),
    "cluster_offsets": (None, "clusters", None),
    "mean_effective_index": ("mean_effective_index", "study_points_clusters", None),
    "mean_group_index": ("mean_group_index", "study_points_clusters", None),
}


def _finite(x):
    x = float(x)
    return x if np.isfinite(x) else None


def _nested(values):
    """Nested lists of SI doubles (non-finite values as null)."""
    a = np.asarray(values)
    if a.ndim == 0:
        return _finite(a)
    return [_nested(v) for v in a]


def _series(values, quantity: str | None) -> dict:
    """A tagged array of a real result, or the complex list form ``{"re", "im"}`` of a complex one;
    the values of a swept enum (no quantity) as a plain list."""
    from physmat import units as registry
    a = np.asarray(values)
    if quantity is None:
        return {"values": a.tolist()}
    unit = registry.quantity(quantity).unit
    if np.iscomplexobj(a):
        return {"unit": unit, "re": _nested(a.real), "im": _nested(a.imag),
                "time_convention": results_common.TIME_CONVENTION}
    return {"unit": unit, "values": _nested(a)}


@dataclass
class RunResult:
    """An ``em.modes2d`` result in SI under exp(-i omega t) and exp(+i beta z) (spec §5.3.4).

    ``node_coordinates`` (N, 2) in metres; ``vacuum_wavelength`` (P,) in metres, one per study
    point; ``effective_index`` (P, M), complex when lossy or with PML (Im >= 0 is loss);
    ``mode_fields`` the scalar fields per point (N, M), empty for vector results, whose
    ``vector_fields`` hold the edge line integrals in metres and the complex fields. The
    kernel computed every value in its micrometre frame; ``_to_public`` converted them once.
    """
    doc: Document
    node_coordinates: np.ndarray
    triangles: np.ndarray
    regions: np.ndarray
    region_names: list[str]
    region_materials: dict[str, str]
    parameter: str | None
    vacuum_wavelength: np.ndarray
    effective_index: np.ndarray            # (n_points, num_modes)
    mode_fields: list[np.ndarray]          # scalar per point: (N, num_modes); empty for vector
    timings: dict[str, float] = field(default_factory=dict)
    log: list[str] = field(default_factory=list)
    vector_fields: list[VectorField] | None = None
    mode_tracking: dict | None = None
    open_boundary: list[dict] | None = None
    #: ``unnormalized_mode_power`` (vector, W) or ``unnormalized_mode_field_square_integral``
    #: (scalar, m^2) (P, M), ``confinement_factor`` (P, M, R), ``unnormalized_field_overlap``
    #: (P, M, M, m^2) and, with ``results.mode_overlap.gaussian``, ``coupling_efficiency`` (P, M);
    #: None for PML results (``simcase.mode_postprocessing``)
    postprocessing: dict | None = None
    #: the swept values of a sweep over another slot than the wavelength, in SI
    study_values: np.ndarray | None = None
    #: n_g = n_eff - lambda dn/dlambda (computed in the kernel frame), None when not defined
    group_index_values: np.ndarray | None = None

    # -- derived -----------------------------------------------------------

    def _physics(self) -> dict:
        return self.doc.si["physics"][self.doc.sole_physics()[0]]

    def propagation_loss(self) -> np.ndarray:
        """Power attenuation in dB/m: (40 pi / ln 10) Im(n_eff) / lambda0 (exp(-i omega t))."""
        return PROPAGATION_LOSS_FACTOR * self.effective_index.imag / self.vacuum_wavelength[:, None]

    def bend_loss(self) -> np.ndarray | None:
        """Loss per 90 degrees of the bend in dB: ``propagation_loss() * pi * bend_radius / 2``."""
        bend = self._physics().get("bend")
        if bend is None:
            return None
        return self.propagation_loss() * (np.pi * bend["bend_radius"] / 2)

    def group_index(self) -> np.ndarray | None:
        """n_g = n_eff - lambda dn/dlambda when the study sweeps the wavelength (else None)."""
        return self.group_index_values

    # -- output ------------------------------------------------------------

    def _representation(self) -> str | None:
        if self.open_boundary is not None:
            return PML_REPRESENTATIONS["vector" if self.vector_fields is not None else "scalar"]
        return VECTOR_REPRESENTATION if self.vector_fields is not None else None

    def arrays(self) -> dict:
        """The ``fields.npz`` arrays (without ``metadata_json``)."""
        arrays = dict(node_coordinates=self.node_coordinates, triangles=self.triangles, regions=self.regions,
                      region_names=np.array(self.region_names), vacuum_wavelength=self.vacuum_wavelength,
                      effective_index=self.effective_index, field_layout=FIELD_LAYOUT,
                      study_parameter=self.parameter or "")
        if self.study_values is not None:
            arrays["study_values"] = self.study_values
        if self.vector_fields is None:
            arrays["unnormalized_mode_field"] = np.stack(self.mode_fields)
        else:
            arrays.update(edges=self.vector_fields[0].edges,
                          unnormalized_electric_field_line_integral=np.stack([f.transverse for f in self.vector_fields]),
                          unnormalized_electric_field_z=np.stack([f.longitudinal for f in self.vector_fields]),
                          unnormalized_electric_field=np.stack([f.electric for f in self.vector_fields]))
        if self._representation() is not None:
            arrays["field_representation"] = self._representation()
        if self.mode_tracking is not None:
            arrays.update(mode_tracking_json=json.dumps(self.mode_tracking), group_index=self.group_index())
        if self.postprocessing is not None:
            arrays.update(self.postprocessing)
        if self.open_boundary is not None:
            arrays["open_boundary_json"] = json.dumps(self.open_boundary)
        return arrays

    def _field_maps(self, arrays: dict) -> dict:
        fields = {}
        for name, a in arrays.items():
            if name == "study_values":
                quantity = _parameter_quantity(self.doc, self.parameter)
                fields[name] = {"quantity": quantity, "location": "study_points", "shape": list(np.shape(a))}
            elif name in FIELDS:
                quantity, location, components = FIELDS[name]
                fields[name] = {"quantity": quantity, "location": location, "shape": list(np.shape(a)),
                                "components": components}
        maps = results_common.field_maps(fields)
        del maps["field_time_axes"]                  # the study axis is not a time axis
        return maps

    def _study_block(self) -> dict:
        if self.study_values is not None:
            return {"parameter": self.parameter, "values": _series(self.study_values,
                                                                   _parameter_quantity(self.doc, self.parameter))}
        return {"parameter": self.parameter, "values": _series(self.vacuum_wavelength, "vacuum_wavelength")}

    def _envelope(self, arrays: dict) -> dict:
        doc = self.doc
        return {"name": doc.si["name"], "field_layout": FIELD_LAYOUT,
                "diagnostics": [d.as_dict() for d in doc.diagnostics],
                "defaults_applied": list(doc.defaults_applied), "resolved_inputs": doc.resolved_inputs(),
                "extent": doc.extent_lines(),
                "timing": results_common.timing(self.timings.get("mesh", 0.0), self.timings.get("solve", 0.0)),
                **self._field_maps(arrays),
                "mesh": {"nodes": int(len(self.node_coordinates)), "triangles": int(len(self.triangles)),
                         "regions": {n: self.region_materials[n] for n in self.region_names}},
                "study": self._study_block(),
                "vacuum_wavelength": _series(self.vacuum_wavelength, "vacuum_wavelength")}

    def summary(self) -> dict:
        arrays = self.arrays()
        out = self._envelope(arrays)
        physics = self._physics()
        out["effective_index"] = _series(self.effective_index, "effective_index")
        if any(isinstance(a, np.ndarray) and np.iscomplexobj(a) for a in arrays.values()):
            out.update(time_convention=results_common.TIME_CONVENTION, propagation=PROPAGATION)
        ng = self.group_index()
        if self.vector_fields is not None:
            out.update(formulation="vector", field_representation=VECTOR_REPRESENTATION,
                       normalization="max_centroid_magnitude",
                       effective_index_threshold=physics["effective_index_threshold"],
                       mode_count=int(physics["mode_count"]), returned_mode_count=int(self.effective_index.shape[1]))
        if ng is not None:
            out["group_index"] = _series(ng, "group_index")
        if np.iscomplexobj(self.effective_index):
            out.update(mode_result_schema=MODE_RESULT_SCHEMA, propagation_loss=_series(self.propagation_loss(),
                                                                                       "propagation_loss"),
                       selection="near_target" if physics.get("target_effective_index") is not None
                       else ("real_index_interval" if self.vector_fields is not None else "descending_real_index"))
        if self.open_boundary is not None:
            out.update(open_boundary=copy.deepcopy(self.open_boundary),
                       normalization="physical_max_centroid_magnitude" if self.vector_fields is not None
                       else "physical_nodal_peak", field_representation=self._representation(),
                       selection="pml_heuristic_near_target", attenuation="total_absorption_and_radiation")
            loss = self.bend_loss()
            if loss is not None:
                out["bend_loss"] = _series(loss, "bend_loss")
        if self.mode_tracking is not None:
            out["mode_tracking"] = copy.deepcopy(self.mode_tracking)
        if self.postprocessing is not None:
            out["mode_postprocessing"] = mode_postprocessing.summary_block(
                self.postprocessing, vector=self.vector_fields is not None, region_names=self.region_names,
                gaussian=_gaussian_echo(self.doc))
        results_common.dumps_summary(out)                # finite JSON only
        return out

    def save(self, outdir: str | Path) -> Path:
        outdir = Path(outdir)
        outdir.mkdir(parents=True, exist_ok=True)
        summary = self.summary()
        (outdir / "summary.json").write_text(results_common.dumps_summary(summary), encoding="utf-8")
        (outdir / "log.txt").write_text("\n".join(self.log) + "\n", encoding="utf-8")
        results_common.write_model_json(self.doc, outdir / "model.json")
        if self.doc.si["results"]["save_fields"]:
            arrays = dict(self.arrays(), metadata_json=results_common.metadata_json(summary))
            np.savez_compressed(outdir / "fields.npz", **arrays)
        if self.doc.si["results"]["plots"]:
            self.plot(outdir / "results.png")
        return outdir

    def _display(self):
        """(length unit text, metres per unit) of the plot axes: display_units.length, else the
        component's length_unit (display only, rule 2.9)."""
        from physmat import units as registry
        block = modes_document.component(self.doc)[1]
        unit = (self.doc.si.get("display_units") or {}).get("length") or block["length_unit"]
        return unit, float(registry.convert(f"1 {unit}", "length").exact)

    def plot(self, path: str | Path) -> None:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        sweep = self.parameter is not None and len(self.vacuum_wavelength) > 1
        length, per_unit = self._display()
        nodes = self.node_coordinates / per_unit
        wavelength_sweep = self.study_values is None
        if wavelength_sweep:
            values = self.vacuum_wavelength / per_unit
        elif self.study_values.dtype.kind in "fiu":
            values = self.study_values
        else:                                           # a swept enum: plotted against the point index
            values = np.arange(len(self.study_values), dtype=float)
        ncols = 3 if sweep else 2
        fig, axes = plt.subplots(1, ncols, figsize=(5.2 * ncols, 4.4))
        ax = axes[0]
        ax.tripcolor(nodes[:, 0], nodes[:, 1], self.triangles, facecolors=self.regions.astype(float), cmap="Blues",
                     edgecolors="k", linewidth=0.1, alpha=0.9)
        ax.set_aspect("equal"); ax.set_title(f"mesh: {len(self.triangles)} triangles")
        ax.set_xlabel(f"x ({length})"); ax.set_ylabel(f"y ({length})")
        i = len(values) // 2
        ax = axes[1]
        if self.vector_fields is None:
            f = np.abs(self.mode_fields[i][:, 0])
            ax.tricontourf(nodes[:, 0], nodes[:, 1], self.triangles, f, levels=30, cmap="inferno")
        else:
            f = np.linalg.norm(self.vector_fields[i].electric[:, 0, :], axis=1)
            ax.tripcolor(nodes[:, 0], nodes[:, 1], self.triangles, facecolors=f, shading="flat", cmap="inferno")
        if self.open_boundary is not None:
            # Mask artificial PML values in saved figures as in Studio.
            from matplotlib.tri import Triangulation
            bounds = np.asarray(self.open_boundary[i]["physical_bounds"]["values"]) / per_unit
            centers = nodes[self.triangles].mean(axis=1)
            mask = np.any((centers < bounds[0]) | (centers > bounds[1]), axis=1)
            triangulation = Triangulation(nodes[:, 0], nodes[:, 1], self.triangles, mask=mask)
            ax.clear()
            ax.set_facecolor("#d0d5dd")
            if self.vector_fields is None:
                ax.tricontourf(triangulation, f, levels=30, cmap="inferno")
            else:
                ax.tripcolor(triangulation, facecolors=f, shading="flat", cmap="inferno")
        ax.set_aspect("equal")
        pname, phys = self.doc.sole_physics()
        unit_text = f" {length}" if wavelength_sweep else ""
        shown = f"{values[i]:g}" if wavelength_sweep or self.study_values.dtype.kind in "fiu" else self.study_values[i]
        label = f"{'vacuum_wavelength' if wavelength_sweep else self.parameter} = {shown}{unit_text}"
        ax.set_title(f"|mode 1|, {label}: n_eff = {self.effective_index[i, 0]:.5f}")
        ax.set_xlabel(f"x ({length})"); ax.set_ylabel(f"y ({length})")
        if sweep:
            ax = axes[2]
            for j in range(self.effective_index.shape[1]):
                ax.plot(values, self.effective_index[:, j].real, "o-", label=f"mode {j + 1}")
            ax.set_xlabel((self.parameter or "vacuum_wavelength") + (f" ({length})" if unit_text else ""))
            ax.set_ylabel("Re n_eff" if np.iscomplexobj(self.effective_index) else "n_eff"); ax.legend(fontsize=8)
            ng = self.group_index()
            if ng is not None:
                ax2 = ax.twinx()
                ax2.plot(values, ng[:, 0].real, "s--", color="C3", ms=4,
                         label="Re n_g (mode 1)" if np.iscomplexobj(ng) else "n_g (mode 1)")
                ax2.set_ylabel("Re group index" if np.iscomplexobj(ng) else "group index", color="C3")
            ax.set_title("study")
        fig.suptitle(f"{self.doc.si['name']}  ({pname}: {phys['type']}, {phys['formulation']})")
        fig.tight_layout()
        fig.savefig(path, dpi=130)
        plt.close(fig)


def _parameter_quantity(doc, parameter) -> str | None:
    """The registry quantity of a swept slot (None for an enum)."""
    from .reader import split_path
    from .slots import table_for
    found = table_for(kind_of(doc.data)).match(split_path(parameter), doc.data)
    return found[0].get("quantity") if found else None


def _gaussian_echo(doc) -> dict | None:
    """The Gaussian the kernel used, in metres: its micrometre waist and centre times 1e-6 (H11),
    as every length of the result."""
    spec = (doc.si.get("results") or {}).get("mode_overlap")
    if spec is None:
        return None
    where = "results.mode_overlap.gaussian"
    waist = modes_document.um(doc, f"{where}.beam_waist_radius") * KERNEL_LENGTH
    position = [x * KERNEL_LENGTH for x in modes_document.um(doc, f"{where}.position")]
    return {"beam_waist_radius": results_common.value_object(waist, "beam_waist_radius"),
            "position": results_common.tagged_array(position, "position")}


def run(doc: Document, verbose: bool = True, *, max_nodes: int | None = None, max_triangles: int | None = None,
        max_input_vertices: int | None = None
        ) -> (RunResult | SubspaceSweepResult | CavityRunResult | ThermalRunResult | TransientThermalRunResult
              | ElectricJouleRunResult | MechanicsRunResult):
    """Run a document with the runner of its physics kind (``registry``).

    ``max_nodes``, ``max_triangles`` and ``max_input_vertices`` are optional mesh limits for
    steady and transient heat region documents, region electric conduction and steady Joule
    heating documents and mechanics region documents only (see simcase.mesh_limits): each limit
    given is a positive int, checked before the solve, and a document over it raises
    MeshLimitError. Giving one for any other document is a ValueError. Only
    max_input_vertices bounds the work before meshing; give it for documents from others.
    The limits reach the kind's runner as ``mesh_limits`` only when its
    ``accepts_mesh_limits`` claims the document; without a limit every runner is called
    as ``run(doc, verbose=verbose)``.
    """
    limits = _mesh_limits(max_nodes=max_nodes, max_triangles=max_triangles, max_input_vertices=max_input_vertices)
    doc.validate()
    kind = kind_of(doc.data)
    if limits is None:
        return kind.run(doc, verbose=verbose)
    if not _is_region_document(doc.data):
        raise ValueError("mesh limits apply only to region documents (heat, electric conduction, steady "
                         "Joule heating and mechanics)")
    return kind.run(doc, verbose=verbose, mesh_limits=limits)


def _run_em_modes2d(doc: Document, verbose: bool = True) -> RunResult | SubspaceSweepResult:
    """The 2D mode pipeline: ``build_mesh``, then the kernel over the study, then ``_to_public``.

    The study runs on the micrometre kernel hand-off (``MeshedModel.kernel_doc``) in the
    kernel's frame, exactly as format 0.2 micrometre documents ran; nothing is converted until
    the result is complete."""
    log: list[str] = []

    def say(msg):
        log.append(msg)
        if verbose:
            print(msg)

    say(results_common.log_header(doc).rstrip("\n"))
    t0 = time.time()
    model = build_mesh(doc)
    t_mesh = time.time() - t0
    k, tm = model.kernel_doc, model.kernel_tri
    say(f"mesh: {tm.num_nodes} nodes, {tm.num_triangles} triangles, min angle {tm.min_angle():.1f} deg, {t_mesh:.2f} s")
    for r, m in model.materials.items():
        say(f"  {r}: {m.name}  [{m.source.split(';')[0]}]")
    kp = k.sole_physics()[1]
    modes_document.plausibility(doc, model, kp["wavelength"], say)

    parameter, values = _kernel_points(k)
    neffs, fields = [], []
    open_diagnostics = [] if "pml" in kp else None
    # Power, confinement, overlaps and Gaussian coupling of every saved mode, in the kernel
    # frame (simcase.mode_postprocessing). PML results are skipped: their coefficients are
    # covariant integrals in stretched coordinates and the window is not the physical one.
    postprocessing = [] if open_diagnostics is None else None
    gaussian = mode_postprocessing.gaussian_settings(k["results"])
    vector_fields = [] if kp["formulation"] == "vector" else None
    tracker, tracking = None, None
    scalar_tracking = (vector_fields is None and parameter is not None and parameter.endswith(".wavelength")
                       and (open_diagnostics is not None or any(np.any(model._permittivity(v).imag != 0)
                                                                for v in values)))
    if scalar_tracking:
        w = np.asarray(values, dtype=float)
        if len(w) < 3 or not np.isfinite(w).all() or not (np.all(np.diff(w) > 0) or np.all(np.diff(w) < 0)):
            raise ModeTrackingError("lossy scalar wavelength sweeps need at least 3 strictly monotone values")
    if (vector_fields is not None or scalar_tracking) and parameter is not None:
        requested = int(kp["num_modes"])
        settings = tracking_settings(requested, k["study"].get("tracking"))
        if settings.get("method") == SUBSPACE_METHOD:
            return _run_subspace(doc, model, parameter, values, settings, say, log, t_mesh)
        weights = 1.0
        if open_diagnostics is not None:
            from .physics_pml_modes import coordinates
            # the physical-weights mask in the micrometre frame with micrometre PML numbers (H12)
            weights = coordinates(model.solver_mesh, kp["pml"], kp.get("bend")).physical.astype(float)
        tracker = ModeTracker(model.solver_mesh, requested, settings, scalar=scalar_tracking, physical_weights=weights,
                              seed_target=kp["n_target"] if open_diagnostics is not None else None)
        tracking = dict(method="scalar-l2-assignment-v1" if scalar_tracking else "electric-l2-assignment-v1",
                        settings=settings, points=[])
        say(f"{'scalar' if scalar_tracking else 'vector'} sweep: tracking resolved modes by L2 overlap; check "
            "wavelength-step convergence")
    t0 = time.time()
    for v in values:
        d = k.copy()
        if parameter is not None:
            d.set_path(parameter, v)
        physics = d.sole_physics()[1]
        location = _location(doc, parameter, v)
        if tracker is not None:
            physics = dict(physics, num_modes=tracker.settings["search_modes"])
            try:
                res = _kernel_solve(model, physics)
            except (ValueError, RuntimeError) as exc:
                raise ModeTrackingError(f"{'scalar' if scalar_tracking else 'vector'} sweep at {location}: {exc}") from exc
            key = "fields" if scalar_tracking else "vector_field"
            res["neff"], res[key], evidence = tracker.step(res["neff"], res[key], location)
            selected = np.asarray(evidence["candidate_ranks"])-1
            res["guided"] = res["guided"][selected]
            if "open_boundary" in res:
                diagnostic = res["open_boundary"]
                diagnostic["search_requested_modes"] = diagnostic["requested_modes"]
                diagnostic.update(requested_modes=tracker.num_modes, returned_modes=len(selected))
                diagnostic["selected_candidates"] = [diagnostic["selected_candidates"][i] for i in selected]
                for candidate in diagnostic["candidates"]:
                    if candidate["selected"] and candidate["candidate"] not in diagnostic["selected_candidates"]:
                        candidate.update(selected=False, reasons=["not_selected_by_tracking"])
            tracking["points"].append(evidence)
        else:
            res = _kernel_solve(model, physics)
        if open_diagnostics is not None:
            open_diagnostics.append(res["open_boundary"])
        neffs.append(res["neff"])
        if postprocessing is not None:
            if vector_fields is None:
                point = mode_postprocessing.scalar_postprocessing(tm.nodes, tm.triangles, res["fields"], tm.regions,
                                                                  len(tm.region_names), gaussian)
            else:
                vf = res["vector_field"]
                point = mode_postprocessing.vector_postprocessing(
                    tm.nodes, tm.triangles, vf.edges, vf.transverse, vf.longitudinal, res["neff"],
                    physics["wavelength"], model._permittivity(physics["wavelength"]), tm.regions,
                    len(tm.region_names), gaussian)
            postprocessing.append(point)
        if vector_fields is None:
            fields.append(res["fields"])
        else:
            vector_fields.append(res["vector_field"])
            requested = int(d.sole_physics()[1]["num_modes"])
            if len(res["neff"]) < requested:
                say(f"  warning: requested {requested} modes; found {len(res['neff'])} in the guided interval")
        # the kernel's n_eff is under exp(+i omega t); the log shows the public sign of Im n_eff
        say(f"  {location}: n_eff = " + ", ".join(_shown(n) for n in res["neff"]) +
            ("  (PML candidates; stability not checked)" if open_diagnostics is not None
             else "" if res["guided"].all() else "  (some modes below cladding index: not guided)"))
    t_solve = time.time() - t0
    say(f"solved {len(values)} point(s) in {t_solve:.2f} s")
    kernel = dict(parameter=parameter, values=values, wavelength=kp["wavelength"], neff=np.array(neffs),
                  fields=fields, vector_fields=vector_fields, tracking=tracking, open_boundary=open_diagnostics,
                  postprocessing=None if postprocessing is None else mode_postprocessing.stack_points(postprocessing))
    return _to_public(doc, model, kernel, {"mesh": t_mesh, "solve": t_solve}, log)


def _shown(n) -> str:
    """A kernel n_eff in the log, with the imaginary part of exp(-i omega t) (loss positive)."""
    n = complex(n)
    return f"{n.real:.6f}" if n.imag == 0 else f"{n.real:.6f}{0.0 - n.imag:+.3e}i"


def _location(doc: Document, parameter: str | None, value) -> str:
    """A study point as the log and the tracker's messages name it (a kernel wavelength in um)."""
    if parameter is None:
        return "single point"
    if parameter.endswith(".wavelength"):
        return f"vacuum_wavelength {value:g} um"
    return f"{doc.si['study']['parameter']} = {value}"


def _run_subspace(doc, model, parameter, values, settings, say, log, t_mesh) -> "SubspaceSweepResult":
    """Opt-in electric-l2-subspace-v1 sweep: all points succeed or nothing is returned."""
    k = model.kernel_doc
    requested = int(k.sole_physics()[1]["num_modes"])
    tracker = SubspaceTracker(model.solver_mesh, requested, settings)
    tracking = dict(method=SUBSPACE_METHOD, settings=settings, points=[])
    say("vector sweep: tracking isolated clusters by electric L2 principal angles "
        "(electric-l2-subspace-v1); check wavelength-step, mesh and search_mode_count convergence")
    neffs, fields, transforms, offsets = [], [], [], None
    t0 = time.time()
    for v in values:
        d = k.copy()
        d.set_path(parameter, v)
        physics = dict(d.sole_physics()[1], num_modes=settings["search_modes"])
        location = _location(doc, parameter, v)
        try:
            res = _kernel_solve(model, physics)
        except (ValueError, RuntimeError) as exc:
            raise ModeTrackingError(f"vector subspace sweep at {location}: {exc}") from exc
        if np.iscomplexobj(res["neff"]):
            raise ModeTrackingError("electric-l2-subspace-v1 requires a real spectrum; "
                                    "use resolved-mode assignment for lossy sweeps")
        neff, vector_field, transform, point_offsets, evidence = tracker.step(res["neff"], res["vector_field"],
                                                                              location)
        if offsets is None:
            offsets = point_offsets
        tracking["points"].append(evidence)
        neffs.append(neff)
        fields.append(vector_field)
        transforms.append(transform)
        bands = "; ".join(f"cluster {c + 1}: " + ", ".join(f"{n:.6f}" for n in neff[offsets[c]:offsets[c + 1]])
                          for c in range(len(offsets) - 1))
        say(f"  {location}: {bands}")
    t_solve = time.time() - t0
    say(f"solved {len(values)} point(s) in {t_solve:.2f} s")
    kernel = dict(parameter=parameter, values=values, wavelength=k.sole_physics()[1]["wavelength"],
                  neff=np.array(neffs), fields=[], vector_fields=fields, tracking=tracking, open_boundary=None,
                  postprocessing=None, cluster_offsets=np.asarray(offsets), frame_transforms=transforms)
    return _to_public(doc, model, kernel, {"mesh": t_mesh, "solve": t_solve}, log)


# -- the result boundary ----------------------------------------------------------------------------

def _kernel_group_index(parameter, values, neff, vector, tracked):
    """n_g = n_eff - lambda dn/dlambda in the kernel frame (micrometre wavelengths), as before:
    first-order differences, second-order ones for a tracked sweep; None when undefined."""
    if parameter is None or not parameter.endswith(".wavelength") or len(values) < 2:
        return None
    if vector and not tracked:
        return None
    if np.iscomplexobj(neff) and not tracked:
        return None
    wl = np.asarray(values, dtype=float)
    order = 2 if tracked else 1
    return neff - wl[:, None] * np.gradient(neff, wl, axis=0, edge_order=order)


def _public_tracking(tracking: dict | None) -> dict | None:
    """``mode_tracking`` under the format 0.3 names: the settings by §4.8, the point evidence
    as before except ``minimum_principal_squared``."""
    if tracking is None:
        return None

    def evidence(value):
        if isinstance(value, dict):
            return {("minimum_principal_squared" if key == "min_principal_squared" else key): evidence(v)
                    for key, v in value.items()}
        if isinstance(value, list):
            return [evidence(v) for v in value]
        return copy.deepcopy(value)
    return {"method": tracking["method"],
            "settings": {modes_document.TRACKING_PUBLIC[key]: value for key, value in tracking["settings"].items()},
            "points": evidence(tracking["points"])}


def _public_candidate(candidate: dict) -> dict:
    out = {}
    for key, value in candidate.items():
        if key == "neff_real":
            out["effective_index"] = {"re": value, "im": 0.0 - candidate["neff_imag"], "unit": "1",
                                      "time_convention": results_common.TIME_CONVENTION}
        elif key == "neff_imag":
            continue
        elif key == "pencil_residual":
            out["relative_residual"] = value
        elif key == "reasons":
            out[key] = ["negative_imaginary_index" if r == "positive_imaginary_index" else r for r in value]
        else:
            out[key] = copy.deepcopy(value)
    return out


def _public_open_boundary(diagnostic: dict) -> dict:
    """An open-boundary (PML) diagnostic under the format 0.3 names, its bounds in metres."""
    renamed = {"min_physical_fraction": "pml_minimum_physical_fraction", "residual_limit":
               "relative_residual_threshold", "requested_modes": "mode_count", "returned_modes":
               "returned_mode_count", "search_requested_modes": "search_mode_count"}
    out = {}
    for key, value in diagnostic.items():
        if key == "schema":
            out[key] = PML_CANDIDATES_SCHEMA
        elif key == "physical_bounds":
            out[key] = {"unit": "m", "values": (np.asarray(value, dtype=float) * KERNEL_LENGTH).tolist()}
        elif key == "candidates":
            out[key] = [_public_candidate(c) for c in value]
        elif key == "length_unit":
            continue
        else:
            out[renamed.get(key, key)] = copy.deepcopy(value)
    return out


def _to_public(doc: Document | None, model: MeshedModel | None, kernel: dict, timings: dict | None = None,
               log: list[str] | None = None, *, point: bool = False):
    """The one boundary from the kernel frame to the public result (hazard H16, check P2-15):
    every complex kernel value is conjugated once (exp(+i omega t) -> exp(-i omega t)), every
    length is the micrometre value times 1e-6 once (H11) and every area times 1e-12. With
    ``point``, ``kernel`` is one kernel solve (``solve_point``) and a dict comes back."""

    def field(f: VectorField) -> VectorField:
        return VectorField(f.edges, np.conj(f.transverse) * KERNEL_LENGTH, np.conj(f.longitudinal),
                           np.conj(f.electric), f.normalization)

    def postprocessing(arrays: dict | None, vector: bool) -> dict | None:
        if arrays is None:
            return None
        out = {}
        if vector:
            out["unnormalized_mode_power"] = np.conj(arrays["mode_power"]) * KERNEL_AREA
        else:
            out["unnormalized_mode_field_square_integral"] = arrays["mode_power"] * KERNEL_AREA
        out["confinement_factor"] = arrays["confinement"]
        out["unnormalized_field_overlap"] = np.conj(arrays["field_overlap"]) * KERNEL_AREA
        if "coupling_efficiency" in arrays:
            out["coupling_efficiency"] = arrays["coupling_efficiency"]
        return out

    if point:
        out = {"effective_index": np.conj(kernel["neff"]), "guided": kernel["guided"]}
        if "fields" in kernel:
            out["unnormalized_mode_field"] = np.conj(kernel["fields"])
        if "vector_field" in kernel:
            out["vector_field"] = field(kernel["vector_field"])
        if "open_boundary" in kernel:
            out["open_boundary"] = _public_open_boundary(kernel["open_boundary"])
        return out
    parameter, values = kernel["parameter"], kernel["values"]
    wavelength_sweep = parameter is not None and parameter.endswith(".wavelength")
    wavelength_um = np.asarray(values if wavelength_sweep else [kernel["wavelength"]] * len(values), dtype=float)
    vector = kernel["vector_fields"] is not None
    neff = kernel["neff"]
    tracked = kernel["tracking"] is not None
    study = doc.si["study"]
    study_values = None
    if parameter is not None and not wavelength_sweep:
        study_values = np.asarray(study["values"])
    group = None if "cluster_offsets" in kernel else _kernel_group_index(parameter, values, neff, vector, tracked)
    common = dict(doc=doc, node_coordinates=model.tri.nodes, triangles=model.tri.triangles,
                  regions=model.tri.regions, region_names=list(model.tri.region_names),
                  region_materials=dict(model.region_materials),
                  parameter=study["parameter"] if parameter is not None else None,
                  vacuum_wavelength=wavelength_um * KERNEL_LENGTH, effective_index=np.conj(neff),
                  mode_fields=[np.conj(f) for f in kernel["fields"]], timings=timings, log=log,
                  vector_fields=None if not vector else [field(f) for f in kernel["vector_fields"]],
                  mode_tracking=_public_tracking(kernel["tracking"]),
                  open_boundary=None if kernel["open_boundary"] is None
                  else [_public_open_boundary(d) for d in kernel["open_boundary"]],
                  postprocessing=postprocessing(kernel["postprocessing"], vector),
                  study_values=study_values, group_index_values=None if group is None else np.conj(group))
    if "cluster_offsets" not in kernel:
        return RunResult(**common)
    from .subspace_result import SubspaceSweepResult, kernel_cluster_means
    mean, mean_group = kernel_cluster_means(neff, kernel["cluster_offsets"], wavelength_um)
    return SubspaceSweepResult(**common, cluster_offsets=kernel["cluster_offsets"],
                               frame_transforms=[np.conj(t) for t in kernel["frame_transforms"]],
                               mean_effective_index=mean, mean_group_index=mean_group)


register(PhysicsKind(
    name="em.modes2d", types=frozenset({"em.modes2d"}), precedence=100,
    validate=modes_document.validate, run=_run_em_modes2d, summary=modes_document.summary,
    result_types=(RunResult,), fallback=True, slots=modes_document.modes_slots(),
    refuse_03=modes_document.refuse_03))
