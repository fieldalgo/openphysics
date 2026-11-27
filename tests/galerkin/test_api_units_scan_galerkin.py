# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""galerkin's public API against the units convention: the API units scan.

The rule, the module lists and the structural names are shared with refsol and physmat
in tests/_support/ (api_scan.py and its JSON files). This file holds galerkin's part:
api_units_allowlist.json next to it is empty (since L3 commit 13; physmat's since L1
commit 3) and may not grow, so no public callable may violate the rule. docs/development.md describes the scan.
"""
import importlib.util
from pathlib import Path

import pytest

import api_scan

PACKAGE = "galerkin"
ALLOWLIST = Path(__file__).with_name("api_units_allowlist.json")

# Valid calls for the TypeError clause, keyed "module:callable": each returns the callable
# and keyword arguments that make a valid call. A module needs them once it has no
# allowlist entries and takes a quantity.


def _steady_heat():
    from galerkin.mesh import rectangle_mesh
    from galerkin.thermal import solve_steady_heat
    mesh = rectangle_mesh(1.0, 1.0, 2, 2)
    return solve_steady_heat, dict(mesh=mesh, thermal_conductivity=2.0, prescribed_temperature={0: 300.0},
                                   heat_source_density=5.0, inward_heat_flux={"right": 3.0})


def _transient_heat():
    import numpy as np
    from galerkin.mesh import rectangle_mesh
    from galerkin.transient_heat import solve_transient_heat
    mesh = rectangle_mesh(1.0, 1.0, 2, 2)
    return solve_transient_heat, dict(mesh=mesh, thermal_conductivity=2.0, volumetric_heat_capacity=3.0,
                                      time=np.array([0.0, 1.0]), initial_temperature=np.full(9, 300.0),
                                      prescribed_temperature={0: 300.0}, heat_source_density=5.0,
                                      inward_heat_flux={"right": 3.0})


def _steady_heat_3d():
    from galerkin.mesh3d import box_mesh
    from galerkin.thermal3d import solve_steady_heat_3d
    mesh = box_mesh(1.0, 1.0, 1.0, 1, 1, 1)
    return solve_steady_heat_3d, dict(mesh=mesh, thermal_conductivity=2.0, prescribed_temperature={0: 300.0},
                                      heat_source_density=5.0)


def _step_error():
    from galerkin.transient_heat import TransientHeatStepError
    return TransientHeatStepError, dict(time_index=1, time=0.5)


def _electric_inputs():
    from galerkin.mesh import rectangle_mesh
    mesh = rectangle_mesh(1.0, 1.0, 2, 2)
    left = {int(i): 1.0 for i in mesh.boundary["left"]}
    return mesh, dict(mesh=mesh, electrical_conductivity=2.0, prescribed_electric_potential=left,
                      inward_current_density={"right": -3.0})


def _steady_electric():
    from galerkin.electric import solve_steady_electric
    return solve_steady_electric, _electric_inputs()[1]


def _steady_electric_3d():
    from galerkin import box_mesh
    from galerkin.electric3d import solve_steady_electric_3d
    return solve_steady_electric_3d, dict(mesh=box_mesh(1., 1., 1., 1, 1, 1),
                                         electrical_conductivity=2.,
                                         prescribed_electric_potential={"x0": 0., "x1": 1.})


def _steady_joule_heat():
    from galerkin.electric import solve_steady_electric
    from galerkin.joule_heating import solve_steady_joule_heat
    mesh, kwargs = _electric_inputs()
    electric = solve_steady_electric(**kwargs)
    return solve_steady_joule_heat, dict(mesh=mesh, electrical_result=electric, thermal_conductivity=5.0,
                                         prescribed_temperature={0: 300.0}, inward_heat_flux={"top": 2.0})


def _temperature_joule_heat():
    from galerkin.temperature_joule_heating import ConductivityModel, solve_temperature_joule_heat
    mesh, kwargs = _electric_inputs()
    right = {int(i): 300.0 for i in mesh.boundary["right"]}
    return solve_temperature_joule_heat, dict(
        mesh=mesh, electrical_conductivity=ConductivityModel(lambda t: 2.0 / (1 + 0.01 * (t - 300)), (250.0, 900.0)),
        thermal_conductivity=5.0, prescribed_electric_potential=kwargs["prescribed_electric_potential"],
        prescribed_temperature=right, initial_temperature=300.0, temperature_tolerance=1e-8,
        inward_current_density={"right": -3.0}, inward_heat_flux={"top": 2.0}, relaxation_factor=1.0,
        relative_tolerance=1e-10, iteration_limit=100)


def _convergence_error():
    from galerkin.temperature_joule_heating import JouleConvergenceError
    return JouleConvergenceError, dict(reason="maximum iterations exceeded", history=(), temperature=[300.0, 301.0])


def _square():
    from galerkin.mesh import rectangle_mesh
    return rectangle_mesh(1.0, 1.0, 2, 2)


_ELASTIC = dict(youngs_modulus=70e9, poisson_ratio=0.3, plane="stress")


def _held(mesh):
    return {(int(i), c): 0.0 for i in mesh.boundary["left"] for c in (0, 1)}


def _constitutive_matrix():
    from galerkin.elasticity import constitutive_matrix
    return constitutive_matrix, dict(_ELASTIC)


def _elasticity():
    from galerkin.elasticity import solve_elasticity
    mesh = _square()
    return solve_elasticity, dict(_ELASTIC, mesh=mesh, prescribed_displacement=_held(mesh),
                                  body_force_density=(0.0, -1e3), traction={"right": (1e5, 0.0)})


def _snapshot():
    import numpy as np
    from galerkin.thermoelasticity import TemperatureSnapshot
    mesh = _square()
    return TemperatureSnapshot, dict(nodes=mesh.nodes, triangles=mesh.triangles, temperature=np.full(9, 310.0))


def _freeze():
    import numpy as np
    from galerkin.thermoelasticity import freeze_temperature
    return freeze_temperature, dict(mesh=_square(), temperature=np.full(9, 310.0))


def _thermoelasticity():
    import numpy as np
    from galerkin.thermoelasticity import freeze_temperature, solve_thermoelasticity
    mesh = _square()
    return solve_thermoelasticity, dict(_ELASTIC, mesh=mesh,
                                        temperature_snapshot=freeze_temperature(mesh, temperature=np.full(9, 310.0)),
                                        stress_free_temperature=300.0, linear_expansion_coefficient=2e-5,
                                        prescribed_displacement=_held(mesh), body_force_density=(0.0, -1e3),
                                        traction={"right": (1e5, 0.0)})


def _steady_thermoelasticity():
    from galerkin.thermal_mechanical import solve_steady_thermoelasticity
    mesh = _square()
    return solve_steady_thermoelasticity, dict(_ELASTIC, mesh=mesh, thermal_conductivity=2.0,
                                               prescribed_temperature={int(i): 310.0 for i in mesh.boundary["left"]},
                                               heat_source_density=5.0, linear_expansion_coefficient=2e-5,
                                               stress_free_temperature=300.0, prescribed_displacement=_held(mesh),
                                               body_force_density=(0.0, -1e3))


def _transient_thermoelasticity():
    from galerkin.transient_thermal_mechanical import solve_transient_thermoelasticity
    solve_transient_heat, kwargs = _transient_heat()
    heat = solve_transient_heat(**kwargs)
    return solve_transient_thermoelasticity, dict(_ELASTIC, mesh=kwargs["mesh"], heat=heat,
                                                  linear_expansion_coefficient=2e-5, stress_free_temperature=300.0,
                                                  prescribed_displacement=_held(kwargs["mesh"]),
                                                  body_force_density=(0.0, -1e3))


def _transient_thermoelastic_error():
    from galerkin.transient_thermal_mechanical import TransientThermoelasticError
    return TransientThermoelasticError, dict(stage="mechanics", time_index=1, time=0.5)


def _mesh_motion():
    import numpy as np
    from galerkin.shape import MeshMotion
    return MeshMotion, dict(design_velocity=np.zeros((9, 2)), t=0.0)


def _admissible_interval():
    import numpy as np
    from galerkin.shape import admissible_interval
    return admissible_interval, dict(mesh=_square(), design_velocity=np.zeros((9, 2)))


def _motion_step_record():
    import numpy as np
    from galerkin.shape import MotionStep
    mesh = _square()
    return MotionStep, dict(xp=np, t=0.0, design_velocity=np.zeros((9, 2)), moved=mesh)


def _coax_conductors():
    from galerkin.mesh import annulus_mesh
    mesh = annulus_mesh(1.0, 3.0, 2, 12)
    return mesh, mesh.boundary["inner"], mesh.boundary["outer"]


def _electrostatics():
    from galerkin.electrostatics import solve_electrostatics
    mesh, inner, outer = _coax_conductors()
    return solve_electrostatics, dict(mesh=mesh, relative_permittivity=2.2 + 0.044j,
                                      conductors={"inner": (inner, 1.0)}, ground=outer, free_charge_density=1e-6)


def _capacitance():
    from galerkin.electrostatics import capacitance_matrix
    mesh, inner, outer = _coax_conductors()
    return capacitance_matrix, dict(mesh=mesh, relative_permittivity=2.2, conductors={"inner": inner}, ground=outer)


def _waveguide_modes():
    from galerkin.mesh import rectangle_mesh
    from galerkin.waveguide import solve_waveguide_modes
    mesh = rectangle_mesh(2e-6, 1e-6, 8, 4)
    return solve_waveguide_modes, dict(mesh=mesh, relative_permittivity=2.25 + 0.01j, vacuum_wavelength=1.55e-6,
                                       target_effective_index=1.4, search_mode_count=2, relative_permeability=1.0)


def _degenerate_branches():
    import jax
    jax.config.update("jax_enable_x64", True)
    import numpy as np
    from galerkin.mesh import rectangle_mesh
    from galerkin.shape import MeshMotion
    from galerkin.waveguide import degenerate_branch_derivatives
    mesh = rectangle_mesh(2e-6, 1e-6, 8, 4)
    motion = MeshMotion(design_velocity=np.zeros((mesh.num_nodes, 2)), t=jax.numpy.asarray(0.0))
    return degenerate_branch_derivatives, dict(mesh=mesh, relative_permittivity=2.25, vacuum_wavelength=1.55e-6,
                                               target_effective_index=1.4, search_mode_count=2,
                                               relative_permeability=1.0, motion=motion, relative_tolerance=1e-8)


def _modal_pml():
    from galerkin.waveguide import ModalPML
    return ModalPML, dict(pml_thickness={"left": 2e-7, "right": 2e-7}, pml_strength=3.0, pml_order=2)


def _bend():
    from galerkin.waveguide import Bend
    return Bend, dict(bend_radius=1e-5, bend_origin=0.0)


def _cavity_box():
    from galerkin.cavity import solve_cavity_box
    return solve_cavity_box, dict(box_size=(1.0, 0.8, 0.6), subdivision_count=(2, 2, 2), mode_count=1,
                                  target_frequency=2.2e8)


def _cavity():
    from galerkin.cavity import solve_cavity
    from galerkin.mesh3d import box_mesh
    return solve_cavity, dict(mesh=box_mesh(1.0, 0.8, 0.6, 2, 2, 2), mode_count=1, target_frequency=2.2e8)


def _material_region():
    from galerkin.material_cavity import CavityMaterialRegion
    return CavityMaterialRegion, dict(lower_corner_position=(0.0, 0.0, 0.0), upper_corner_position=(1.0, 0.8, 0.3),
                                      relative_permittivity=4.0 + 0.04j, relative_permeability=1.0)


def _material_cavity_box():
    from galerkin.material_cavity import solve_material_cavity_box
    region, kwargs = _material_region()
    return solve_material_cavity_box, dict(box_size=(1.0, 0.8, 0.6), subdivision_count=(2, 2, 2),
                                           regions=[region(**kwargs)], mode_count=1, target_frequency=1.5e8,
                                           electrical_conductivity={"z1": 1e6})


def _material_cavity():
    from galerkin.material_cavity import solve_material_cavity
    from galerkin.mesh3d import box_mesh
    return solve_material_cavity, dict(mesh=box_mesh(1.0, 0.8, 0.6, 2, 2, 2), relative_permittivity={"domain": 4.0},
                                       relative_permeability={"domain": 1.0 + 0.01j},
                                       electrical_conductivity={"z1": 1e6}, mode_count=1, target_frequency=0.8e8)


def _panel(name, polygons, **kwargs):
    """A valid call of a galerkin.panel_electrostatics solver on a small case of tests/galerkin/test_panel_electrostatics.py."""
    def case():
        from galerkin import panel_electrostatics
        return getattr(panel_electrostatics, name), dict(polygons=polygons, box_size=(0.008, 0.002), **kwargs)
    return case


_SQUARE = [[0.0038, 0.000975], [0.0042, 0.000975], [0.0042, 0.001025], [0.0038, 0.001025]]
_SECOND = [[0.0045, 0.000975], [0.0049, 0.000975], [0.0049, 0.001025], [0.0045, 0.001025]]
_THREE = [[[0.003425, 0.0006], [0.003775, 0.0006], [0.00375, 0.00065], [0.00345, 0.00065]],
          [[0.00425, 0.0011], [0.00465, 0.0011], [0.004675, 0.00116], [0.004225, 0.00116]],
          [[0.0039, 0.00155], [0.0041, 0.00155], [0.00409, 0.00159], [0.00391, 0.00159]]]
#: the smallest admitted harmonic corner solve of _THREE (16 subdivisions); each takes about 27 s
_PANEL_CASES = {
    "solve_grounded_rectangle": _panel("solve_grounded_rectangle", [_SQUARE], panels_per_edge=8),
    "solve_two_ground_rectangle": _panel("solve_two_ground_rectangle", [_SQUARE], panels_per_edge=8),
    "solve_two_ground_rectangle_edges": _panel("solve_two_ground_rectangle_edges", [_SQUARE], panels_per_edge=8),
    "solve_two_ground_corner_rectangle_edges": _panel("solve_two_ground_corner_rectangle_edges", [_SQUARE],
                                                      panels_per_edge=16),
    "solve_two_ground_linear_corner_rectangle_edges": _panel("solve_two_ground_linear_corner_rectangle_edges",
                                                             [_SQUARE], panels_per_edge=16),
    "solve_two_ground_harmonic_corner_three_active_edges": _panel(
        "solve_two_ground_harmonic_corner_three_active_edges", _THREE, panels_per_edge=16),
    "solve_two_ground_harmonic_corner_guard_edges": _panel(
        "solve_two_ground_harmonic_corner_guard_edges", _THREE, panels_per_edge=16, signal_indices=(0, 1)),
    "solve_two_ground_harmonic_corner_single_active_edges": _panel(
        "solve_two_ground_harmonic_corner_single_active_edges", _THREE, panels_per_edge=16, signal_index=2),
    "solve_open_rectangle": _panel("solve_open_rectangle", [_SQUARE, _SECOND], panels_per_edge=8,
                                   ground_indices=(1,)),
}

STRING_CASES = {"galerkin.thermal:solve_steady_heat": _steady_heat,
                "galerkin.transient_heat:solve_transient_heat": _transient_heat,
                "galerkin.thermal3d:solve_steady_heat_3d": _steady_heat_3d,
                "galerkin.transient_heat:TransientHeatStepError": _step_error,
                # L2 commit 7 emptied electric, joule_heating and temperature_joule_heating
                "galerkin.electric:solve_steady_electric": _steady_electric,
                "galerkin.electric3d:solve_steady_electric_3d": _steady_electric_3d,
                "galerkin.joule_heating:solve_steady_joule_heat": _steady_joule_heat,
                "galerkin.temperature_joule_heating:solve_temperature_joule_heat": _temperature_joule_heat,
                "galerkin.temperature_joule_heating:JouleConvergenceError": _convergence_error,
                # L2 commit 8 emptied elasticity, thermoelasticity, the two workflows, shape and coupling (whose
                # parameters are all structural)
                "galerkin.elasticity:constitutive_matrix": _constitutive_matrix,
                "galerkin.elasticity:solve_elasticity": _elasticity,
                "galerkin.thermoelasticity:TemperatureSnapshot": _snapshot,
                "galerkin.thermoelasticity:freeze_temperature": _freeze,
                "galerkin.thermoelasticity:solve_thermoelasticity": _thermoelasticity,
                "galerkin.thermal_mechanical:solve_steady_thermoelasticity": _steady_thermoelasticity,
                "galerkin.transient_thermal_mechanical:solve_transient_thermoelasticity": _transient_thermoelasticity,
                "galerkin.transient_thermal_mechanical:TransientThermoelasticError": _transient_thermoelastic_error,
                "galerkin.shape:MeshMotion": _mesh_motion,
                "galerkin.shape:admissible_interval": _admissible_interval,
                "galerkin.shape:MotionStep": _motion_step_record,
                # L3 commit 10 emptied electrostatics
                "galerkin.electrostatics:solve_electrostatics": _electrostatics,
                "galerkin.electrostatics:capacitance_matrix": _capacitance,
                # L3 commit 11b: the public mode functions (the others take no quantity)
                "galerkin.waveguide:solve_waveguide_modes": _waveguide_modes,
                # shape-derivative follow-up 4 (2026-11-21): the branch slopes of degenerate modes
                "galerkin.waveguide:degenerate_branch_derivatives": _degenerate_branches,
                "galerkin.waveguide:ModalPML": _modal_pml,
                "galerkin.waveguide:Bend": _bend,
                # L3 commit 12: the public cavity functions in SI
                "galerkin.cavity:solve_cavity_box": _cavity_box,
                "galerkin.cavity:solve_cavity": _cavity,
                "galerkin.material_cavity:CavityMaterialRegion": _material_region,
                "galerkin.material_cavity:solve_material_cavity_box": _material_cavity_box,
                "galerkin.material_cavity:solve_material_cavity": _material_cavity,
                # panel API (2026-11-26): the public panel solvers in SI (box_size is their one quantity)
                **{f"galerkin.panel_electrostatics:{name}": case for name, case in _PANEL_CASES.items()}}


@pytest.fixture(scope="module")
def rules():
    return api_scan.load_rules()


def test_public_parameters_match_the_allowlist(rules):
    problems = api_scan.allowlist_problems(PACKAGE, ALLOWLIST, rules)
    assert not problems, "\n".join(problems)


def test_allowlist_is_canonical_and_never_grows():
    problems = api_scan.allowlist_format_problems(PACKAGE, ALLOWLIST)
    assert not problems, "\n".join(problems)


def test_galerkin_allowlist_is_empty_and_its_clauses_apply(rules):
    # P3-3 at L3 commit 13: no galerkin entry is left and none may be added, so every scanned public module is
    # clean and the removed-name and string clauses apply to all of them
    # (test_clean_modules_refuse_strings_and_removed_names).
    assert api_scan.load_allowlist(ALLOWLIST) == []
    assert api_scan.BASELINE_COUNTS[PACKAGE] == 0
    scanned = sorted(m.__name__ for m in api_scan.scanned_modules(PACKAGE, rules))
    assert scanned
    assert sorted(api_scan.clean_modules(PACKAGE, ALLOWLIST, rules)) == scanned


def test_every_module_is_public_or_internal(rules):
    problems = api_scan.module_problems(PACKAGE, rules)
    assert not problems, "\n".join(problems)


def test_public_modules_export_only_their_own_callables(rules):
    _, foreign = api_scan.package_items(PACKAGE, rules)
    assert not foreign, "\n".join(foreign)


def test_listed_result_classes_exist(rules):
    # Their constructors are outside the scan; their field names are check P3-11's job.
    problems = api_scan.result_class_problems(PACKAGE, rules)
    assert not problems, "\n".join(problems)


def test_clean_modules_refuse_strings_and_removed_names(rules):
    problems = api_scan.string_refusal_problems(PACKAGE, ALLOWLIST, rules, STRING_CASES)
    problems += api_scan.removed_name_problems(PACKAGE, ALLOWLIST, rules)
    assert not problems, "\n".join(problems)


def test_public_names_are_not_kernel_names(rules):
    # galerkin.kernels exists since L2 commit 4: the public names and objects are disjoint from its own (D7).
    problems = api_scan.kernel_disjointness(PACKAGE, rules)
    assert problems is not None and importlib.util.find_spec("galerkin.kernels") is not None
    assert not problems, "\n".join(problems)


# L2 commit 4 (Appendix D, D21): the top-level assembly and solve kernels and the physics modules' helpers left
# the public API for the internal galerkin.kernels, which re-exports them unchanged from their modules.
MOVED_TOP_LEVEL = {"assembly": ["assemble_stiffness", "assemble_mass", "assemble_boundary_mass", "assemble_load"],
                   "assembly3d": ["tet_gradients", "assemble_stiffness_3d", "assemble_mass_3d"],
                   "solver": ["solve_dirichlet"],
                   # L3 commit 11 (Appendix D): the em kernels; simcase's em.modes2d calls them (route K, D1)
                   "edge": ["assemble_curlcurl", "assemble_edge_mass", "assemble_edge_grad", "eval_edge_field"],
                   "edge3d": ["assemble_curlcurl_3d", "assemble_edge_mass_3d", "assemble_edge_grad_3d",
                              "eval_edge_field_3d"],
                   "waveguide": ["solve_modes", "assemble_mode_system"],
                   "pml": ["radial_pml_coeffs"],
                   "mode_overlap": ["vector_power", "vector_cross_power", "vector_field_overlap", "normalize_vector",
                                    "coupling_efficiency", "confinement_factor", "overlap_matrix", "centroid_field",
                                    "interpolate_vector_field", "effective_area", "scalar_power", "scalar_overlap",
                                    "normalize_scalar", "scalar_coupling_efficiency", "scalar_confinement_factor",
                                    "scalar_effective_area"]}
MOVED_HELPERS = {"elasticity": ["lame", "constitutive", "element_materials", "element_constitutive",
                                "stiffness_and_stress", "stress_of", "body_load", "check_solution", "displacement",
                                "at_fixed", "vector_stiffness"],
                 "thermoelasticity": ["verify_snapshot", "thermal_coefficient", "physical_energy"],
                 "thermal": ["scalar_boundary_system"], "thermal3d": ["source_load_3d", "dirichlet_from_faces"],
                 "materials": ["region_property"],
                 "shape": ["solve_steady_heat_moving", "solve_transient_heat_moving", "solve_steady_electric_moving",
                           "solve_elasticity_moving", "solve_thermoelasticity_moving",
                           "solve_steady_thermoelasticity_moving"],
                 # L3 commit 11: the internal galerkin.mode_coordinates was never public (no removed name; its
                 # module name is also bound on galerkin once imported)
                 "mode_coordinates": ["mode_coordinates", "scalar_coordinate_system", "solve_scalar_coordinates"]}
NEVER_PUBLIC = {"region_property", *MOVED_HELPERS["mode_coordinates"]}


HEAT_KERNELS = {"scalar_boundary_system", "source_load_3d", "dirichlet_from_faces"}
# L2 commit 8: the mechanics helpers and the moving-mesh solves left the clean modules for the package-private
# galerkin._mechanics_kernels and galerkin._moving
DEFINING = {**{n: "galerkin._heat_kernels" for n in HEAT_KERNELS},
            **{n: "galerkin._mechanics_kernels" for n in MOVED_HELPERS["elasticity"] + MOVED_HELPERS["thermoelasticity"]},
            **{n: "galerkin._moving" for n in MOVED_HELPERS["shape"]},
            # L3 commit 11: galerkin.waveguide is the public mode module; its kernels moved to a package-private one
            **{n: "galerkin._waveguide_kernels" for n in MOVED_TOP_LEVEL["waveguide"]}}


def test_kernels_reexport_the_moved_names_unchanged(rules):
    import galerkin
    import galerkin.kernels as kernels
    moved = {**MOVED_TOP_LEVEL, **MOVED_HELPERS}
    assert sorted(kernels.__all__) == sorted(n for names in moved.values() for n in names)
    for module, names in moved.items():
        for name in names:
            # L2 commits 6 and 8: the heat and mechanics helpers and the moving-mesh solves moved to package-private
            # modules (the clean modules hold no removed name); galerkin.kernels re-exports them from there
            defining = importlib.import_module(DEFINING.get(name, f"galerkin.{module}"))
            assert getattr(kernels, name) is getattr(defining, name), name
    for name in (n for names in MOVED_TOP_LEVEL.values() for n in names):
        assert name not in galerkin.__all__ and not hasattr(galerkin, name), name
    public = {n for m in rules.public[PACKAGE] for n in api_scan.public_names(importlib.import_module(m))}
    assert not public & set(kernels.__all__)
    removed = {r.name for r in rules.removed if r.package == PACKAGE and r.kind == "name"}
    # galerkin.materials and galerkin.mode_coordinates were never public
    assert removed == set(kernels.__all__) - NEVER_PUBLIC
    assert "galerkin.kernels" in rules.internal[PACKAGE]


#: spec 4.3: the public mode functions and spec objects, defined in galerkin.waveguide and re-exported at the top level
PUBLIC_MODE_NAMES = {"solve_waveguide_modes", "WaveguideModes", "ModalPML", "Bend", "mode_power", "cross_power",
                     "field_overlap", "mode_coupling_efficiency", "mode_confinement_factor", "mode_effective_area"}


def test_public_mode_names_are_hosted_by_waveguide_and_re_exported(rules):
    import galerkin
    import galerkin.kernels as kernels
    import galerkin.waveguide as waveguide
    assert PUBLIC_MODE_NAMES <= set(waveguide.__all__) and PUBLIC_MODE_NAMES <= set(galerkin.__all__)
    for name in PUBLIC_MODE_NAMES:
        assert getattr(galerkin, name) is getattr(waveguide, name), name
        assert getattr(waveguide, name).__module__ == "galerkin.waveguide", name
        assert not hasattr(kernels, name), name                     # D7: distinct names ...
    for name in kernels.__all__:
        assert all(getattr(kernels, name) is not getattr(waveguide, n) for n in waveguide.__all__), name  # ... objects


def test_star_import_gives_the_public_names():
    namespace = {}
    exec("from galerkin import *", namespace)
    names = set(namespace) - {"__builtins__"}
    # 78 before L2 commit 4: its 8 kernels left, and so did the submodules assembly3d and solver, which the
    # top-level imports no longer bind. 68 before L3 commit 11a: its 27 em kernels left, and so did the
    # submodules assembly, mode_overlap, pml and waveguide, which the top-level imports no longer bind (37).
    # L3 commit 11b adds the 10 public mode names and binds assembly, mode_overlap and waveguide again
    # (mode_coordinates too, which is not listed: its name is a kernel's).
    assert len(names) == 50 and {"Mesh", "EdgeSpace", "EdgeSpace3D", "core", "edge", "waveguide"} <= names
    assert PUBLIC_MODE_NAMES <= names and "mode_coordinates" not in names
    assert not names & {"assemble_stiffness", "solve_dirichlet", "tet_gradients", "assembly3d", "solver", "kernels"}
    assert not names & {n for k in ("edge", "edge3d", "waveguide", "pml", "mode_overlap") for n in MOVED_TOP_LEVEL[k]}
