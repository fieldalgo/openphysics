# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""galerkin's public API against the units convention: the API units scan.

The rule, the module lists and the structural names are shared with refsol and physmat
in tests/_support/ (api_scan.py and its JSON files). This file holds galerkin's part:
api_units_allowlist.json next to it lists today's violations, and entries may only be
removed. docs/development.md describes the scan.
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


STRING_CASES = {"galerkin.thermal:solve_steady_heat": _steady_heat,
                "galerkin.transient_heat:solve_transient_heat": _transient_heat,
                "galerkin.thermal3d:solve_steady_heat_3d": _steady_heat_3d,
                "galerkin.transient_heat:TransientHeatStepError": _step_error,
                # L2 commit 7 emptied electric, joule_heating and temperature_joule_heating
                "galerkin.electric:solve_steady_electric": _steady_electric,
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
                "galerkin.shape:MotionStep": _motion_step_record}


@pytest.fixture(scope="module")
def rules():
    return api_scan.load_rules()


def test_public_parameters_match_the_allowlist(rules):
    problems = api_scan.allowlist_problems(PACKAGE, ALLOWLIST, rules)
    assert not problems, "\n".join(problems)


def test_allowlist_is_canonical_and_never_grows():
    problems = api_scan.allowlist_format_problems(PACKAGE, ALLOWLIST)
    assert not problems, "\n".join(problems)


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
                   "solver": ["solve_dirichlet"]}
MOVED_HELPERS = {"elasticity": ["lame", "constitutive", "element_materials", "element_constitutive",
                                "stiffness_and_stress", "stress_of", "body_load", "check_solution", "displacement",
                                "at_fixed", "vector_stiffness"],
                 "thermoelasticity": ["verify_snapshot", "thermal_coefficient", "physical_energy"],
                 "thermal": ["scalar_boundary_system"], "thermal3d": ["source_load_3d", "dirichlet_from_faces"],
                 "materials": ["region_property"],
                 "shape": ["solve_steady_heat_moving", "solve_transient_heat_moving", "solve_steady_electric_moving",
                           "solve_elasticity_moving", "solve_thermoelasticity_moving",
                           "solve_steady_thermoelasticity_moving"]}


HEAT_KERNELS = {"scalar_boundary_system", "source_load_3d", "dirichlet_from_faces"}
# L2 commit 8: the mechanics helpers and the moving-mesh solves left the clean modules for the package-private
# galerkin._mechanics_kernels and galerkin._moving
DEFINING = {**{n: "galerkin._heat_kernels" for n in HEAT_KERNELS},
            **{n: "galerkin._mechanics_kernels" for n in MOVED_HELPERS["elasticity"] + MOVED_HELPERS["thermoelasticity"]},
            **{n: "galerkin._moving" for n in MOVED_HELPERS["shape"]}}


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
    assert removed == set(kernels.__all__) - {"region_property"}      # galerkin.materials was never public
    assert "galerkin.kernels" in rules.internal[PACKAGE]


def test_star_import_gives_the_public_names():
    namespace = {}
    exec("from galerkin import *", namespace)
    names = set(namespace) - {"__builtins__"}
    # 78 before L2 commit 4: its 8 kernels left, and so did the submodules assembly3d and solver, which the
    # top-level imports no longer bind.
    assert len(names) == 68 and {"Mesh", "solve_modes", "scalar_effective_area", "core", "waveguide"} <= names
    assert not names & {"assemble_stiffness", "solve_dirichlet", "tet_gradients", "assembly3d", "solver", "kernels"}
