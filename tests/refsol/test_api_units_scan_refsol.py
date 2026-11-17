# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""refsol's public API against the units convention: the API units scan.

The rule, the module lists and the structural names are shared with galerkin and physmat
in tests/_support/ (api_scan.py and its JSON files). This file holds refsol's part:
api_units_allowlist.json next to it lists today's violations, and entries may only be
removed. Every refsol module is public. docs/development.md describes the scan.
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
# L2 commit 6 emptied refsol's eight heat modules: each callable that takes a quantity has a case.
STRING_CASES = {f"refsol.{module}:{name}": _case(module, name, **kwargs) for module, name, kwargs in _HEAT}


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
