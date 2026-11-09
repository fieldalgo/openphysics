# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Internal SI views between documents and the solvers and the mesher. Not public API.

A runner does not read document numbers on its way to galerkin or meshine: it builds one
frozen view here and hands its fields to today's solver and mesher signatures. The adapters
that turn a view into node and edge data (Dirichlet nodes, boundary edges, region maps) stay
in the kind modules, beside the mesh they need.

Every view of this module is built from a 0.2 document and holds exactly what the runners
passed before the views existed: the same doubles, the same Python number types (an int a
0.2 document gives stays an int, hazard H8) and the same mapping orders (H6). Physics values
are SI in a 0.2 document already (their keys carry the SI unit) and are copied as written,
or as the 0.2 contract readers return them; the adapters keep their ``float()`` and
``int()`` calls at the hand-off. Lengths are converted here, once:

- a structured rectangle or box (``RectangleMesh``): corners in metres, and side lengths by
  the operation order of the kind that uses them (hazard H17 b);
- a region mesh (``RegionMesh``): the document's micrometre copy, which the geometry is
  built from, and the angle number meshine receives (H2, H3). Mesh nodes come back as
  micrometres times 1e-6 (``handback_m``, H11), and so does every corner a region kind uses
  in a solver input or a contract check (``region_corner_m``, H17 a);
- an em.modes2d solve point (``ModesInputs``): the wavelength, PML and bend lengths in
  micrometres, the kernel frame (H13).

Containers in a view are built fresh for each view and are not shared with the document (the
micrometre copy of a version 1 document shares its exact geometry model, as it always has).
The 0.3 document reader builds the same views from resolved SI values.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass

import numpy as np

from . import units

#: how a kind computes a rectangle side length from the document (hazard H17 b):
#: ``difference`` converts ``max - min``; ``corners`` subtracts the converted corners
LENGTH_FORMULAS = ("difference", "corners")


# -- meshes -------------------------------------------------------------------------------------

@dataclass(frozen=True)
class RectangleMesh:
    """A structured rectangle (axes x, y) or box (x, y, z) in metres.

    ``origin`` and ``upper`` are the converted corners; ``lengths`` are the side lengths by
    ``formula`` (one of ``LENGTH_FORMULAS``); ``subdivisions`` are Python ints.
    """
    origin: tuple
    upper: tuple
    lengths: tuple
    subdivisions: tuple
    formula: str


def rectangle_mesh(doc, formula: str, *, axes: str = "xy", scale=None) -> RectangleMesh:
    """The structured grid of a validated 0.2 rectangle (or box, ``axes="xyz"``) document.

    ``scale`` is the document's resolved unit scale, ``doc.scale`` by default.
    """
    if formula not in LENGTH_FORMULAS:
        raise ValueError(f"formula: expected one of {LENGTH_FORMULAS}, got {formula!r}")
    scale = doc.scale if scale is None else scale
    dom = doc.domain

    def si(value):
        return scale.to_si(value, {"length": 1})
    origin = tuple(si(dom[a + "min"]) for a in axes)
    upper = tuple(si(dom[a + "max"]) for a in axes)
    if formula == "difference":
        lengths = tuple(si(dom[a + "max"] - dom[a + "min"]) for a in axes)
    else:
        lengths = tuple(u - o for u, o in zip(upper, origin))
    return RectangleMesh(origin, upper, lengths, tuple(int(n) for n in doc["mesh"]["subdivisions"]), formula)


@dataclass(frozen=True)
class RadialGrading:
    """em.modes2d ``mesh.grading`` in micrometres: ``near`` at ``center``, growing to ``far``
    at ``distance`` from it (``meshine.shapes.size_graded``)."""
    near: object
    far: object
    distance: object
    center: tuple


@dataclass(frozen=True)
class RegionMesh:
    """What a region mesh is made from.

    ``canonical`` is the document's micrometre copy (``runner.micrometre_document``): the
    geometry, the element size and the mesh controls the mesher receives, in micrometres
    (a version 1 model travels with it in integer pm). ``minimum_angle_deg`` is the number
    meshine receives as ``min_angle``, in degrees as the document wrote it (hazard H3).
    ``grading`` is an em.modes2d radial grading, None otherwise.
    """
    canonical: object
    minimum_angle_deg: object
    grading: RadialGrading | None = None


def region_mesh(doc) -> RegionMesh:
    """The region mesh of a validated heat, electric, Joule or mechanics region document."""
    from .runner import micrometre_document
    canonical = micrometre_document(doc)
    return RegionMesh(canonical, float(doc["mesh"]["min_angle"]))


def modes_mesh(doc) -> RegionMesh:
    """The mesh of a validated em.modes2d document: the angle as written, 28 when absent."""
    from .runner import micrometre_document
    canonical = micrometre_document(doc)
    mesh = canonical["mesh"]
    grading = None
    if mesh.get("grading"):
        g = mesh["grading"]
        grading = RadialGrading(g["near"], g["far"], g["distance"], tuple(g["center"]))
    return RegionMesh(canonical, mesh.get("min_angle", 28.0), grading)


def handback_m(values_um) -> np.ndarray:
    """Mesher coordinates in micrometres, in metres: ``x_um * 1e-6`` elementwise (hazard H11)."""
    return np.asarray(values_um, dtype=float) * units.UM_IN_SI


def region_corner_m(value, scale):
    """A region document's length, or list of lengths, in metres by the micrometre hand-back:
    the document number in micrometres, correctly rounded, times 1e-6, as the mesh nodes are
    (hazard H17 a). A list gives an array."""
    return units.length_to_micrometres(value, scale) * units.UM_IN_SI


# -- heat -----------------------------------------------------------------------------------------

@dataclass(frozen=True)
class AffineTemperature:
    """``T(x) = origin_temperature + gradient . (x - origin)``; the origin is the domain's
    lower corner, taken from the mesh view of the kind (K, K/m)."""
    origin_temperature: object
    gradient: np.ndarray


@dataclass(frozen=True)
class HeatInputs:
    """Heat-stage inputs in SI.

    On a rectangle ``conductivity`` (W/(m K)) and ``volumetric_heat_capacity`` (J/(m^3 K))
    are numbers; on regions they map material names to numbers, and the adapter maps the
    meshed regions to them. ``heat_source`` (W/m^3) is a number or {region: number}.
    ``dirichlet`` maps boundary names to K (steady) or to a tuple of K per requested time
    (transient); ``outward_flux`` to W/m^2; ``convection`` to (W/(m^2 K), K). ``time`` (s)
    and ``initial_temperature`` (K, or ``AffineTemperature``) are set for transient heat.
    ``boundary_layout`` is True when a rectangle document selects the boundary result layout
    (a region result always carries the boundary fields).
    """
    conductivity: object
    heat_source: object
    dirichlet: dict
    outward_flux: dict
    convection: dict
    boundary_layout: bool = False
    volumetric_heat_capacity: object = None
    time: np.ndarray | None = None
    initial_temperature: object = None


def rectangle_heat(doc) -> HeatInputs:
    """thermal.steady2d on a rectangle without boundary data (layout v1): values as written."""
    _, p = doc.sole_physics()
    return HeatInputs(conductivity=p["conductivity_w_mk"], heat_source=p["heat_source_w_m3"],
                      dirichlet=dict(p["dirichlet_temperature_k"]), outward_flux={}, convection={})


def steady_rectangle(doc) -> tuple[RectangleMesh, HeatInputs]:
    """The steady rectangle boundary contract (``steady_boundary_contract``) of a document,
    read and validated without changing it: the grid (lengths by ``difference``) and the
    heat inputs as the contract returns them (floats)."""
    from .steady_boundary_contract import V2, _validated
    bounds, sides, k, q, flux, convection, versions = _validated(doc)
    d = doc.data
    scale = units.resolve(d["units"])
    dom = d["geometry"]["domain"]
    grid = RectangleMesh(origin=(bounds["xmin"], bounds["ymin"]), upper=(bounds["xmax"], bounds["ymax"]),
                         lengths=tuple(scale.to_si(dom[a + "max"] - dom[a + "min"], {"length": 1}) for a in "xy"),
                         subdivisions=tuple(int(n) for n in d["mesh"]["subdivisions"]), formula="difference")
    heat = HeatInputs(conductivity=k, heat_source=q, dirichlet=sides, outward_flux=flux, convection=convection,
                      boundary_layout=versions == V2)
    return grid, heat


def _initial_temperature(spec):
    if isinstance(spec, dict):
        return AffineTemperature(spec["origin_temperature_k"], np.array(spec["gradient_k_per_m"], dtype=float))
    return float(spec)


def transient_rectangle_heat(doc) -> HeatInputs:
    """thermal.transient2d on a rectangle, validated: the contract's values (floats), side
    Dirichlet data sampled at the requested times."""
    from .steady_boundary_contract import has_natural_conditions, natural_conditions
    from .transient_thermal_contract import _samples
    name, p = doc.sole_physics()
    times = np.array(doc["study"]["time_s"], dtype=float, copy=True)
    dirichlet = {tag: tuple(_samples(value, times, f"physics.{name}.dirichlet_temperature_k.{tag}"))
                 for tag, value in p["dirichlet_temperature_k"].items()}
    natural = has_natural_conditions(p)
    flux, convection = (natural_conditions(p, f"physics.{name}", p["dirichlet_temperature_k"]) if natural
                        else ({}, {}))
    return HeatInputs(conductivity=float(p["conductivity_w_mk"]), heat_source=float(p.get("heat_source_w_m3", 0.)),
                      dirichlet=dirichlet, outward_flux=flux, convection=convection, boundary_layout=natural,
                      volumetric_heat_capacity=float(p["volumetric_heat_capacity_j_m3k"]), time=times,
                      initial_temperature=_initial_temperature(p["initial_temperature_k"]))


def _material_values(doc, key) -> dict:
    """{material name: value} of the materials that give ``key``, as written."""
    return {m: spec[key] for m, spec in doc["materials"].items() if isinstance(spec, dict) and key in spec}


def region_heat(doc) -> HeatInputs:
    """Steady heat on regions (also the heat stage of region Joule and thermoelastic
    documents), validated: values as written; the adapter converts them."""
    _, p = doc.sole_physics()
    source = p.get("heat_source_w_m3", 0.0)        # a Joule document has none
    return HeatInputs(conductivity=_material_values(doc, "conductivity_w_mk"),
                      heat_source=dict(source) if isinstance(source, dict) else source,
                      dirichlet=dict(p.get("dirichlet_temperature_k", {})),
                      outward_flux=dict(p.get("outward_flux_w_m2", {})),
                      convection={tag: (v["h_w_m2k"], v["ambient_temperature_k"])
                                  for tag, v in p.get("convection", {}).items()})


def transient_region_heat(doc) -> HeatInputs:
    """Transient heat on regions, validated: material values as written, Dirichlet data
    sampled at the requested times; the affine origin is the region corner (H17 a)."""
    from .transient_thermal_contract import _samples
    name, p = doc.sole_physics()
    times = np.array(doc["study"]["time_s"], dtype=float, copy=True)
    dirichlet = {tag: tuple(_samples(value, times, f"physics.{name}.dirichlet_temperature_k.{tag}"))
                 for tag, value in p["dirichlet_temperature_k"].items()}
    source = p["heat_source_w_m3"]
    return HeatInputs(conductivity=_material_values(doc, "conductivity_w_mk"),
                      heat_source=dict(source) if isinstance(source, dict) else source,
                      dirichlet=dirichlet, outward_flux={}, convection={},
                      volumetric_heat_capacity=_material_values(doc, "volumetric_heat_capacity_j_m3k"),
                      time=times, initial_temperature=_initial_temperature(p["initial_temperature_k"]))


def region_origin_m(doc) -> np.ndarray:
    """The lower domain corner of a region document, [x, y] in metres (H17 a)."""
    dom = doc.domain
    return region_corner_m([dom["xmin"], dom["ymin"]], doc.scale)


# -- electric conduction and Joule heating ------------------------------------------------------

@dataclass(frozen=True)
class ElectricInputs:
    """Electric-stage inputs in SI, as written.

    ``conductivity`` (S/m) is a number on a rectangle (None for ``joule.temperature2d``) and
    {material name: number} on regions. ``dirichlet`` maps boundary names to V,
    ``outward_current`` to A/m^2. ``joule.temperature2d`` adds its conductivity model
    (``galerkin.temperature_joule_heating.ConductivityModel``), its initial temperature (K)
    and its iteration options, keyed as galerkin takes them.
    """
    conductivity: object
    dirichlet: dict
    outward_current: dict
    conductivity_model: object = None
    initial_temperature: object = None
    iteration: dict | None = None


def rectangle_electric(doc) -> ElectricInputs:
    """electric.steady2d, joule.steady2d or joule.temperature2d on a rectangle, validated."""
    _, p = doc.sole_physics()
    model = initial = options = None
    if p["type"] == "joule.temperature2d":
        from .electric_joule import _model
        model = _model(p["conductivity_model"], "conductivity_model")
        initial = p["initial_temperature_k"]
        options = dict(p.get("iteration", {}))
        if "temperature_atol_k" in options:
            options["temperature_atol"] = options.pop("temperature_atol_k")
    return ElectricInputs(conductivity=p.get("conductivity_s_m"), dirichlet=dict(p["dirichlet_potential_v"]),
                          outward_current=dict(p.get("outward_current_a_m2", {})), conductivity_model=model,
                          initial_temperature=initial, iteration=options)


def region_electric(doc) -> ElectricInputs:
    """electric.steady2d or joule.steady2d on regions, validated: values as written."""
    _, p = doc.sole_physics()
    return ElectricInputs(conductivity=_material_values(doc, "electrical_conductivity_s_m"),
                          dirichlet=dict(p["dirichlet_potential_v"]),
                          outward_current=dict(p.get("outward_current_a_m2", {})))


# -- mechanics ------------------------------------------------------------------------------------

@dataclass(frozen=True)
class MechanicsInputs:
    """Mechanical-stage inputs in SI, as written.

    ``young_modulus`` (Pa), ``poisson_ratio`` and ``thermal_expansion`` (1/K) are numbers on
    a rectangle and {material name: number} on regions. ``displacement`` maps boundary names
    to {component: m}, ``traction`` to [tx, ty] in Pa, ``pressure`` to Pa (regions only);
    ``body_force`` is [fx, fy] in N/m^3. ``thermoelastic`` documents add the stress-free
    ``reference_temperature`` (K); their heat stage has its own ``HeatInputs``.
    """
    thermoelastic: bool
    plane: str
    young_modulus: object
    poisson_ratio: object
    displacement: dict
    traction: dict
    pressure: dict
    body_force: list
    thermal_expansion: object = None
    reference_temperature: object = None


def _mechanics(p, thermoelastic, young_modulus, poisson_ratio, thermal_expansion) -> MechanicsInputs:
    return MechanicsInputs(
        thermoelastic=thermoelastic, plane=p["plane"], young_modulus=young_modulus, poisson_ratio=poisson_ratio,
        displacement={tag: dict(components) for tag, components in p["displacement_m"].items()},
        traction={tag: list(vector) for tag, vector in p.get("traction_pa", {}).items()},
        pressure=dict(p.get("pressure_pa", {})), body_force=list(p.get("body_force_n_m3", [0., 0.])),
        thermal_expansion=thermal_expansion,
        reference_temperature=p["reference_temperature_k"] if thermoelastic else None)


def rectangle_mechanics(doc) -> MechanicsInputs:
    """mechanics.elasticity2d or mechanics.thermoelastic2d on a rectangle, validated."""
    _, p = doc.sole_physics()
    thermoelastic = p["type"] == "mechanics.thermoelastic2d"
    return _mechanics(p, thermoelastic, p["young_modulus_pa"], p["poisson_ratio"],
                      p["thermal_expansion_per_k"] if thermoelastic else None)


def region_mechanics(doc) -> MechanicsInputs:
    """mechanics.elasticity2d or mechanics.thermoelastic2d on regions, validated."""
    _, p = doc.sole_physics()
    thermoelastic = p["type"] == "mechanics.thermoelastic2d"
    return _mechanics(p, thermoelastic, _material_values(doc, "young_modulus_pa"),
                      _material_values(doc, "poisson_ratio"),
                      _material_values(doc, "thermal_expansion_per_k") if thermoelastic else None)


# -- em.modes2d -----------------------------------------------------------------------------------

@dataclass(frozen=True)
class ModesInputs:
    """One em.modes2d solve point in the kernel frame.

    With a scale, ``wavelength`` and the PML thicknesses and bend radius and origin are in
    micrometres, each converted once (``units.length_to_micrometres``); without one (a model
    assembled by hand, which has no micrometre mesh) they are as written. ``num_modes`` is a
    Python int; the rest is as written. ``pml`` and ``bend`` are copies.
    """
    wavelength: object
    boundary: dict
    num_modes: int
    formulation: str
    n_cladding: object
    n_target: object
    pml: dict | None
    bend: dict | None


def modes_inputs(physics: dict, scale=None) -> ModesInputs:
    """The solve point of one em.modes2d physics entry, in micrometres when ``scale`` is given."""
    wavelength = physics["wavelength"]
    pml, bend = copy.deepcopy(physics.get("pml")), copy.deepcopy(physics.get("bend"))
    if scale is not None:
        wavelength = units.to_micrometres(wavelength, scale)

        def um(value):
            return units.length_to_micrometres(value, scale)
        if pml is not None:
            pml["thickness"] = {k: um(v) for k, v in pml["thickness"].items()}
        if bend is not None:
            for key in ("radius", "origin"):
                if key in bend:
                    bend[key] = um(bend[key])
    return ModesInputs(wavelength=wavelength, boundary=dict(physics["boundary"]), num_modes=int(physics["num_modes"]),
                       formulation=physics["formulation"], n_cladding=physics.get("n_cladding"),
                       n_target=physics.get("n_target"), pml=pml, bend=bend)


# -- em.cavity3d ----------------------------------------------------------------------------------

@dataclass(frozen=True)
class CavityInputs:
    """A rectangular cavity in SI.

    ``box`` is the domain (lengths by ``difference``). ``wall_conductivity`` is None (PEC
    walls), a number or {galerkin wall name: number} in S/m. ``materials`` maps names to
    (relative permittivity, relative permeability) as complex numbers under the kernel's
    exp(+j omega t); ``background`` is a material name or ``"vacuum"``; ``boxes`` are the
    shape boxes as ((min, max) per axis in metres from the domain origin, material name).
    ``material_solver`` is True when the complex material cavity solver runs.
    """
    box: RectangleMesh
    num_modes: int
    target_frequency: object
    wall_conductivity: object
    materials: dict
    background: str
    boxes: list
    material_solver: bool


def cavity_inputs(doc) -> CavityInputs:
    """em.cavity3d, validated."""
    from .cavity import _cavity_boundary, _cavity_materials, _cavity_shapes, uses_material_solver
    _, p = doc.sole_physics()
    material_solver = uses_material_solver(doc)
    materials = _cavity_materials(doc.data) if material_solver else {}
    return CavityInputs(box=rectangle_mesh(doc, "difference", axes="xyz"), num_modes=int(p["num_modes"]),
                        target_frequency=p["target_frequency_hz"],
                        wall_conductivity=_cavity_boundary(p["boundary"], "boundary"), materials=materials,
                        background=doc["geometry"]["background"]["material"],
                        boxes=_cavity_shapes(doc, materials) if material_solver else [],
                        material_solver=material_solver)
