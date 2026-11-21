# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""refsol's public API against the units convention: the API units scan.

The rule, the module lists and the structural names are shared with galerkin and physmat
in tests/_support/ (api_scan.py and its JSON files). This file holds refsol's part:
api_units_allowlist.json next to it is empty (since L3 commit 13; physmat's since L1
commit 3) and may not grow, so no public callable may violate the rule. Every refsol module is public. docs/development.md describes the scan.
"""
from pathlib import Path

import pytest

import api_scan

PACKAGE = "refsol"
ALLOWLIST = Path(__file__).with_name("api_units_allowlist.json")

# Valid calls for the TypeError clause, keyed "module:callable": each returns the callable
# and keyword arguments that make a valid call. A module needs them once it has no
# allowlist entries and takes a quantity.
P2 = [[0.1, 0.2], [0.3, 0.4]]
SLAB = dict(length=1.0, thermal_conductivity=2.5, volumetric_heat_capacity=4.0)


def _case(module, name, **kwargs):
    """A case calling ``module.name`` (``Class.method`` on an instance from ``_instances``)."""
    def make():
        import importlib
        mod = importlib.import_module(f"refsol.{module}")
        if "." in name:
            cls, method = name.split(".")
            return getattr(_instances(mod)[cls], method), kwargs
        return getattr(mod, name), kwargs
    return make


def _instances(mod):
    import numpy as np
    from refsol import transient_heat_multilayer as ml, transient_heat_robin as rb
    if mod is ml:
        return {"LayeredWall": ml.LayeredWall(position=[0., .01, .03], thermal_conductivity=[45., .5],
                                              volumetric_heat_capacity=[3.6e6, 1.2e6])}
    return {"ConvectiveSlab": rb.ConvectiveSlab(**SLAB, heat_transfer_coefficient=5.0, ambient_temperature=300.0,
                                                initial_temperature=350.0),
            "FluxSlab": rb.FluxSlab(**SLAB, inward_heat_flux=100.0, initial_temperature=300.0),
            "PeriodicAmbientSlab": rb.PeriodicAmbientSlab(**SLAB, heat_transfer_coefficient=5.0,
                                                          ambient_temperature=300.0, temperature_difference=20.0,
                                                          angular_frequency=2*np.pi)}


_HEAT = [
    ("thermal", "slab", dict(points=P2, length=1.0, thermal_conductivity=2.0, prescribed_temperature=(300.0, 310.0))),
    ("thermal", "sine_manufactured", dict(points=P2, length=(1.0, 1.0), thermal_conductivity=1.0,
                                          reference_temperature=300.0, temperature_difference=1.0)),
    ("thermal3d", "sine_product", dict(points=[[0.1, 0.2, 0.3]], length=(1.0, 1.0, 1.0), thermal_conductivity=1.0,
                                       reference_temperature=300.0, temperature_difference=1.0)),
    ("thermal3d", "layered_slab", dict(points=[[0.0, 0.0, 0.5]], position=[0.0, 1.0], thermal_conductivity=[1.0],
                                       prescribed_temperature=(300.0, 310.0))),
    ("thermal_boundary", "dirichlet_robin_slab", dict(length=1.0, thermal_conductivity=2.5, prescribed_temperature=320.0,
                                                      heat_source_density=5.0, inward_heat_flux=-0.7,
                                                      heat_transfer_coefficient=10.0, ambient_temperature=300.0)),
    ("thermal_boundary", "robin_only_slab", dict(length=1.0, thermal_conductivity=2.5, heat_transfer_coefficient=(8.0, 12.0),
                                                 ambient_temperature=(300.0, 310.0), heat_source_density=5.0,
                                                 inward_heat_flux=(-0.7, 0.2))),
    ("thermal_boundary", "sine_flux", dict(points=P2, thermal_conductivity=2.5)),
    ("thermal_boundary", "sine_source", dict(points=P2, thermal_conductivity=2.5)),
    ("thermal_convection", "ConvectionRectangle", dict(length=(0.6, 1.0), thermal_conductivity=52.0,
                                                       heat_transfer_coefficient=750.0, prescribed_temperature=373.15,
                                                       ambient_temperature=273.15)),
    ("thermal_multilayer", "layered_slab", dict(points=[[0.01, 0.0]], position=[0.0, 0.02, 0.05],
                                                thermal_conductivity=[15.0, 0.8], prescribed_temperature=(420.0, 300.0),
                                                heat_source_density=[2e5, -3e4])),
    ("thermal_multilayer", "composite_cylinder", dict(points=[[0.012, 0.0]], position=[0.01, 0.015, 0.03],
                                                      thermal_conductivity=[50.0, 0.25],
                                                      prescribed_temperature=(500.0, 310.0),
                                                      heat_source_density=[1e6, 0.0])),
    ("transient_heat", "uniform_insulated", dict(points=P2, time=2.0, volumetric_heat_capacity=4.0, heat_source_density=-8.0,
                                                 initial_temperature=300.0, initial_time=0.0)),
    ("transient_heat", "moving_affine", dict(points=P2, time=0.2, thermal_conductivity=2.5, volumetric_heat_capacity=4.0,
                                             initial_time=0.0)),
    ("transient_heat", "sine_manufactured", dict(points=P2, time=0.5, thermal_conductivity=2.5, volumetric_heat_capacity=4.0)),
    ("transient_heat", "p1_matrices", dict(nodes=[[0.0, 0.0], [1.0, 0.0], [0.0, 1.0]], triangles=[[0, 1, 2]],
                                           thermal_conductivity=1.0, volumetric_heat_capacity=4.0)),
    ("transient_heat", "backward_euler_amplitude", dict(decay_rate=2.0, time=[0.0, 0.1, 0.3])),
    ("transient_heat_multilayer", "LayeredWall", dict(position=[0.0, 0.01, 0.03], thermal_conductivity=[45.0, 0.5],
                                                      volumetric_heat_capacity=[3.6e6, 1.2e6])),
    ("transient_heat_multilayer", "LayeredWall.fields", dict(points=[[0.01, 0.0]], time=1.0, prescribed_temperature=(400.0, 300.0),
                                                             temperature_difference=[60.0, -25.0])),
    ("transient_heat_multilayer", "LayeredWall.source_amplitudes", dict(initial_temperature=300.0,
                                                                        heat_source_density=[2e5, 5e4], terms=3)),
    ("transient_heat_multilayer", "LayeredWall.source_driven", dict(points=[[0.01, 0.0]], time=1.0, initial_temperature=300.0,
                                                                    heat_source_density=[2e5, 5e4], terms=3)),
    ("transient_heat_robin", "ConvectiveSlab", dict(SLAB, heat_transfer_coefficient=5.0, ambient_temperature=300.0,
                                                    initial_temperature=350.0)),
    ("transient_heat_robin", "ConvectiveSlab.temperature", dict(points=[0.5], time=0.2, relative_tolerance=1e-13)),
    ("transient_heat_robin", "ConvectiveSlab.outward_heat_flux", dict(time=0.2, relative_tolerance=1e-13)),
    ("transient_heat_robin", "FluxSlab", dict(SLAB, inward_heat_flux=100.0, initial_temperature=300.0)),
    ("transient_heat_robin", "FluxSlab.temperature", dict(points=[0.5], time=0.2, relative_tolerance=1e-13)),
    ("transient_heat_robin", "FluxSlab.mean_temperature", dict(time=0.2)),
    ("transient_heat_robin", "PeriodicAmbientSlab", dict(SLAB, heat_transfer_coefficient=5.0, ambient_temperature=300.0,
                                                         temperature_difference=20.0, angular_frequency=6.0)),
    ("transient_heat_robin", "PeriodicAmbientSlab.discrete_wavenumber", dict(time_step=0.01)),
    ("transient_heat_robin", "PeriodicAmbientSlab.complex_amplitude", dict(points=[0.5], time_step=0.01)),
    ("transient_heat_robin", "PeriodicAmbientSlab.ambient", dict(time=0.3)),
    ("transient_heat_robin", "PeriodicAmbientSlab.temperature", dict(points=[0.5], time=0.3)),
    ("transient_heat_robin", "PeriodicAmbientSlab.outward_heat_flux", dict(time=0.3)),
]
_JOULE_LAW = dict(prescribed_temperature=(300.0, 300.0), reference_conductivity=1.0,
                  conductivity_temperature_coefficient=-0.005, reference_temperature=300.0, thermal_conductivity=1.0)
_JOULE = [
    ("joule_slab", "constant_conductivity", dict(length=1.0, prescribed_electric_potential=(1.0, 0.0),
                                                 prescribed_temperature=(300.0, 310.0), electrical_conductivity=1.0,
                                                 thermal_conductivity=1.0, reference_temperature=300.0)),
    ("joule_slab", "voltage_driven", dict(_JOULE_LAW, length=1.0, prescribed_electric_potential=(1.0, 0.0))),
    ("joule_slab", "drop_scale", dict(reference_conductivity=1.0, conductivity_temperature_coefficient=0.5,
                                      thermal_conductivity=1.0)),
    ("joule_slab", "fold_current", dict(_JOULE_LAW, length=1.0)),
    ("joule_slab", "current_driven", dict(_JOULE_LAW, length=1.0, current_density=1.0,
                                          prescribed_electric_potential=0.0)),
]
_ELASTIC = dict(youngs_modulus=70e9, poisson_ratio=0.3, plane="stress")
_THERMOELASTIC = dict(_ELASTIC, stress_free_temperature=300.0, linear_expansion_coefficient=2e-5)
_STRIP = dict(thickness=[1e-3, 2e-3], youngs_modulus=[70e9, 200e9], poisson_ratio=[0.3, 0.3],
              linear_expansion_coefficient=[23e-6, 12e-6], temperature_change=80.0, length=0.02)
_PAIRS = dict(thickness=(1e-3, 2e-3), youngs_modulus=(70e9, 200e9), linear_expansion_coefficient=(23e-6, 12e-6),
              temperature_change=80.0)
_NORMALS = [[1.0, 0.0], [0.0, 1.0]]
_MECHANICS = [
    ("bimetal", "curvature", dict(thickness=[1e-3, 2e-3], youngs_modulus=[70e9, 200e9],
                                  linear_expansion_coefficient=[23e-6, 12e-6], temperature_change=80.0)),
    ("bimetal", "timoshenko_curvature", _PAIRS),
    ("bimetal", "villarceau_curvature", _PAIRS),
    ("bimetal", "stoney_uniaxial_curvature", dict(thickness=(1e-6, 5e-4), youngs_modulus=170e9, stress=1e8)),
    ("bimetal", "strip_fields", dict(_STRIP, points=[[5e-4, 0.01]])),
    ("bimetal", "end_traction", dict(_STRIP, points=[[5e-4, 0.0]], normals=[[0.0, -1.0]])),
    ("elasticity", "stress_from_strain", dict(_ELASTIC, strain=[[1e-4, 2e-4, 3e-4]])),
    ("elasticity", "affine", dict(_ELASTIC, points=P2, displacement_gradient=[[1e-4, 2e-5], [0.0, -3e-5]],
                                  displacement=(1e-6, 0.0))),
    ("elasticity", "sine_manufactured", dict(_ELASTIC, points=P2)),
    ("elasticity_multilayer", "laminate_axial", dict(points=[[0.1, 0.004]], position=[0.0, 0.003, 0.008],
                                                     youngs_modulus=[70e9, 200e9], poisson_ratio=[0.3, 0.25],
                                                     strain_xx=1e-3, plane="strain")),
    ("elasticity_multilayer", "series_bar", dict(points=[[0.004, 0.1]], position=[0.0, 0.003, 0.008],
                                                 youngs_modulus=[70e9, 200e9], poisson_ratio=[0.0, 0.0],
                                                 stress_xx=1e6, plane="stress")),
    ("elasticity_multilayer", "composite_cylinder", dict(points=[[0.012, 0.0]], position=[0.01, 0.015, 0.03],
                                                         youngs_modulus=[70e9, 200e9], poisson_ratio=[0.3, 0.25],
                                                         plane="strain", gauge_pressure=(1e6, 0.0),
                                                         linear_expansion_coefficient=[2e-5, 1e-5],
                                                         temperature_change=[[10.0, 0.0], [10.0, 0.0]])),
    ("elasticity_traction", "traction_from_stress", dict(normals=_NORMALS, stress=[[1e6, 2e6, 3e6], [1e6, 2e6, 3e6]])),
    ("elasticity_traction", "uniaxial", dict(_ELASTIC, points=P2, stress_xx=1e6)),
    ("elasticity_traction", "shear", dict(_ELASTIC, points=P2, stress_xy=1e6)),
    ("elasticity_traction", "polynomial_manufactured", dict(_ELASTIC, points=P2)),
    ("elasticity_traction", "polynomial_traction", dict(_ELASTIC, points=P2, normals=_NORMALS)),
    ("elasticity_traction", "polynomial_resultants", _ELASTIC),
    ("thermoelastic_traction", "parent_state", dict(_THERMOELASTIC, strain=[[1e-4, 2e-4, 3e-4]], temperature=[320.0])),
    ("thermoelastic_traction", "traction_from_stress", dict(normals=_NORMALS, stress=[[[1e6, 0.0, 0.0], [0.0, 2e6, 0.0],
                                                                                      [0.0, 0.0, 0.0]]] * 2)),
    ("thermoelastic_traction", "uniform_combined", dict(_THERMOELASTIC, points=P2, temperature_change=20.0,
                                                        stress=(8e6, -2e6, 3e6), displacement=(2e-5, -1e-5))),
    ("thermoelastic_traction", "polynomial_manufactured", dict(_THERMOELASTIC, points=P2)),
    ("thermoelasticity", "state_from_3d", dict(_THERMOELASTIC, strain=[[1e-4, 2e-4, 3e-4]], temperature=[320.0])),
    ("thermoelasticity", "uniform_free", dict(_THERMOELASTIC, points=P2, temperature_change=20.0)),
    ("thermoelasticity", "uniform_constrained", dict(_THERMOELASTIC, points=P2, temperature_change=20.0)),
    ("thermoelasticity", "linear_temperature", dict(_THERMOELASTIC, points=P2, temperature_change=10.0,
                                                    temperature_gradient=20.0)),
    ("thermoelasticity", "sine_manufactured", dict(_THERMOELASTIC, points=P2, temperature_difference=20.0,
                                                   displacement=(1e-4, 6e-5), length=(1.0, 1.0))),
]
_COAX = dict(position=(1.0, 3.0), prescribed_electric_potential=(1.0, 0.0))
_ELECTROSTATICS = [
    ("electrostatics", "coax_capacitance", dict(position=(1.0, 3.0), relative_permittivity=2.2 + 0.044j)),
    ("electrostatics", "two_layer_plate_capacitance", dict(thickness=(3e-4, 7e-4), relative_permittivity=(2.0, 5.0),
                                                           length=2e-3)),
    # re-exported by refsol.electrostatics (their own module, metallic, is clean since L3 commit 12)
    ("metallic", "coax_potential", dict(_COAX, points=P2)),
    ("metallic", "coax_field_magnitude", dict(_COAX, points=P2)),
]
_SOI = dict(refractive_index=(1.444, 3.48, 1.444), thickness=0.22e-6, vacuum_wavelength=1.55e-6)
_LOSSY = dict(relative_permittivity=[1.444 ** 2, 3.48 ** 2 + 0.07j, 1.444 ** 2], thickness=[0.22e-6],
              vacuum_wavelength=1.55e-6)
_BENT = dict(refractive_index=(1.444, 3.48, 1.444), thickness=0.22e-6, bend_radius=2e-6, vacuum_wavelength=1.55e-6)
_EM_PLANAR = [
    ("slab", "modes", dict(_SOI, mode_count=5)),
    ("slab", "num_modes_symmetric", dict(_SOI)),
    ("slab", "field_te", dict(_SOI, points=[0.0, 0.2e-6], effective_index=2.85)),
    ("lossy_slab", "exterior_root", dict(relative_permittivity=1.444 ** 2, effective_index=2.85 + 0.01j,
                                         branch="decay")),
    ("lossy_slab", "characteristic", dict(_LOSSY, effective_index=2.85 + 0.01j)),
    ("lossy_slab", "residual", dict(_LOSSY, effective_index=2.85 + 0.01j)),
    ("lossy_slab", "solve", dict(_LOSSY, target_effective_index=2.85 + 0.01j, relative_tolerance=1e-10,
                                 iteration_limit=12)),
    ("lossy_slab", "continued_root", dict(path=lambda t: ([1.444 ** 2, 3.48 ** 2 + 0.07j * t, 1.444 ** 2],
                                                          [0.22e-6]),
                                          vacuum_wavelength=1.55e-6, effective_index=2.8517, subdivision_count=2,
                                          relative_tolerance=1e-10)),
    ("lossy_slab", "three_layer_modes", dict(_SOI, mode_count=1, subdivision_count=2, relative_tolerance=1e-10)),
    ("lossy_slab", "substrate_leaky_mode", dict(refractive_index=(1.444, 3.48, 1.444, 3.48),
                                                thickness=(0.22e-6, 0.25e-6), vacuum_wavelength=1.55e-6, mode_index=0,
                                                subdivision_count=12, relative_tolerance=1e-10)),
    ("lossy_slab", "field", dict(_LOSSY, points=[0.0, 0.1e-6], effective_index=2.85 + 0.01j)),
    ("bent_slab", "characteristic", dict(_BENT, effective_index=3.0 + 1e-9j)),
    ("bent_slab", "residual", dict(_BENT, effective_index=3.0 + 1e-9j)),
    ("bent_slab", "mode", dict(_BENT, mode_index=0, target_effective_index=3.013, relative_tolerance=1e-10)),
]
_FIBER = dict(radius=4e-6, refractive_index=(1.45, 1.44), vacuum_wavelength=1.55e-6)
_EM_FIBER = [
    ("fiber", "v_number", dict(_FIBER)),
    ("fiber", "lp_modes", dict(_FIBER, l_max=1)),
    ("fiber", "vector_modes", dict(_FIBER, l_max=1)),
    ("fiber", "fundamental_neff", dict(_FIBER)),
    ("fiber", "vector_group_index", dict(_FIBER, label="HE11")),
    ("fiber", "vector_mode_field", dict(_FIBER, points=[[1e-6, 0.5e-6]], label="HE11", polarization=1)),
]
_CYLINDER = dict(vacuum_angular_wavenumber=3.14e6, radius=1e-6)
_EM_SCATTERING = [
    ("scattering", "incident", dict(points=[[2e-6, 0.5e-6]], vacuum_angular_wavenumber=3.14e6)),
    ("scattering", "scattered", dict(_CYLINDER, points=[[2e-6, 0.5e-6]], terms=20)),
    ("scattering", "total", dict(_CYLINDER, points=[[0.5e-6, 0.0], [2e-6, 0.5e-6]], kind="dielectric",
                                 refractive_index=1.5 + 0.01j, terms=20)),
    ("scattering", "scattering_width", dict(_CYLINDER, kind="dielectric", refractive_index=1.5, terms=20)),
    ("benchmarks", "rib_neff", dict(thickness=0.3e-6)),
]
_BOX = (1.0, 0.8, 0.6)
_EM_CAVITY = [
    ("cavity", "rectangular_cavity_modes", dict(box_size=_BOX, frequency_limit=4e8)),
    ("material_cavity", "quality_factor", dict(resonant_frequency=1.5e8 - 6e5j)),
    ("material_cavity", "complex_frequency_from_eigenvalue", dict(wavenumber_squared=10.6 - 0.08j)),
    ("material_cavity", "uniformly_filled_eigenvalue", dict(wavenumber_squared=19.7, relative_permittivity=4 + 0.04j,
                                                            relative_permeability=1.0)),
    ("material_cavity", "dielectric_loss_quality_factor", dict(loss_tangent=0.01)),
    ("material_cavity", "slab_loaded_cavity_modes", dict(box_size=_BOX, thickness=0.3, frequency_limit=2e8,
                                                         relative_permittivity=(4 + 0.04j, 1.0),
                                                         relative_permeability=(1.0, 1.0), scan_samples=400,
                                                         subdivision_count=4)),
    ("wall_loss", "wall_loss_modes", dict(box_size=_BOX, frequency_limit=3e8, electrical_conductivity=5.8e7,
                                          relative_permittivity=1.0, relative_permeability=1.0)),
    ("wall_loss", "pozar_te101_quality_factor", dict(box_size=(0.02286, 0.01016, 0.02), electrical_conductivity=5.8e7)),
    ("metallic", "rect_waveguide_cutoffs", dict(box_size=(1.0, 0.5))),
    ("metallic", "rect_cavity_resonances", dict(box_size=_BOX)),
]
# L2 commit 6 emptied refsol's eight heat modules, L2 commit 7 joule_slab, L2 commit 8 the six mechanics and
# thermoelastic modules, L3 commit 10 electrostatics, L3 commit 11c slab, lossy_slab and bent_slab, L3 commit
# 11d fiber, L3 commit 11e scattering and benchmarks and L3 commit 12 cavity, material_cavity, wall_loss and
# metallic: each callable that takes a quantity has a case.
STRING_CASES = {f"refsol.{module}:{name}": _case(module, name, **kwargs)
                for module, name, kwargs in _HEAT + _JOULE + _MECHANICS + _ELECTROSTATICS + _EM_PLANAR + _EM_FIBER
                + _EM_SCATTERING + _EM_CAVITY}


@pytest.fixture(scope="module")
def rules():
    return api_scan.load_rules()


def test_public_parameters_match_the_allowlist(rules):
    problems = api_scan.allowlist_problems(PACKAGE, ALLOWLIST, rules)
    assert not problems, "\n".join(problems)


def test_allowlist_is_canonical_and_never_grows():
    problems = api_scan.allowlist_format_problems(PACKAGE, ALLOWLIST)
    assert not problems, "\n".join(problems)


def test_refsol_allowlist_is_empty_and_its_clauses_apply(rules):
    # P3-3 at L3 commit 13: no refsol entry is left and none may be added, so every scanned public module is
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
    assert rules.internal[PACKAGE] == ()


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


def test_the_one_scoped_removed_name(rules):
    # L3 commit 11d: radius is a registry name since L3 commit 11d0, and refsol.fiber takes it (the core radius);
    # bent_slab's former radius (bend_radius since 11c) stays asserted absent from refsol.bent_slab, where it was
    assert [(r.package, r.kind, r.name, r.scope) for r in rules.removed if r.scope] == [
        ("refsol", "parameter", "radius", ("refsol.bent_slab",))]
    assert "api" in rules.registry["radius"][0]
    assert "refsol.bent_slab" in api_scan.clean_modules(PACKAGE, ALLOWLIST, rules)
