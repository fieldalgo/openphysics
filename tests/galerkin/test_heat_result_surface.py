# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Check P3-11 of the galerkin step for the heat results: the result surface.

For each public heat result class (galerkin step, L2 commit 6): every field is a registry
name with a ``result`` place or a structural name (Appendix A); ``.units`` maps exactly the
registry-named fields to the registry's canonical units; planar results carry the
``_per_depth`` rates and axisymmetric and 3D results the totals, and asking those for a
per-depth field raises AttributeError that says why; results marked frozen refuse
assignment. refsol's heat result classes get the field-name clause (they carry no
``.units``).
"""
import dataclasses

import numpy as np
import pytest

import api_scan
from galerkin.mesh import rectangle_mesh
from galerkin.mesh3d import box_mesh
from galerkin.thermal import (AxisymmetricSteadyHeatResult, PlanarSteadyHeatResult, SteadyHeatResult,
                              solve_steady_heat)
from galerkin.thermal3d import SteadyHeat3DResult, solve_steady_heat_3d
from galerkin.transient_heat import (AxisymmetricTransientHeatResult, PlanarTransientHeatResult,
                                     TransientHeatResult, solve_transient_heat)

PLANAR = (PlanarSteadyHeatResult, PlanarTransientHeatResult)
TOTALS = (AxisymmetricSteadyHeatResult, AxisymmetricTransientHeatResult, SteadyHeat3DResult)
#: frozen: no caller or test assigns to their fields. The steady 2D results stay mutable:
#: tests/simcase/test_thermal_simcase_independent_validation.py assigns solution.heat_flux and
#: tests/simcase/test_steady_boundary_runtime.py sets solution fields to check simcase's save guards.
FROZEN = (PlanarTransientHeatResult, AxisymmetricTransientHeatResult, SteadyHeat3DResult)


@pytest.fixture(scope="module")
def rules():
    return api_scan.load_rules()


def _fields(cls):
    return [f.name for f in dataclasses.fields(cls)]


@pytest.mark.parametrize("cls", PLANAR + TOTALS)
def test_fields_are_registry_or_structural_names_and_units_are_canonical(cls, rules):
    registry_fields = []
    for name in _fields(cls):
        structural = api_scan.structural_entry(name, cls.__module__, rules)
        quantity = rules.registry.get(name)
        assert structural is not None or quantity is not None, f"{cls.__name__}.{name}"
        if structural is None:
            places, unit = quantity
            assert "result" in places, f"{cls.__name__}.{name} has no result place"
            registry_fields.append(name)
    assert set(cls.UNITS) == set(registry_fields), cls.__name__
    for name, unit in cls.UNITS.items():
        assert unit == rules.registry[name][1], (cls.__name__, name, unit)


@pytest.mark.parametrize("cls", PLANAR)
def test_planar_rates_are_per_depth(cls):
    rates = [n for n in _fields(cls) if "heat_rate" in n or n.startswith(("stored_heat", "thermal_energy"))]
    assert rates and all(n.endswith("_per_depth") for n in rates)
    assert cls.coordinate_system == "cartesian"


@pytest.mark.parametrize("cls", TOTALS)
def test_axisymmetric_and_3d_rates_are_totals(cls):
    assert not any(n.endswith("_per_depth") for n in _fields(cls))


def _solves():
    mesh = rectangle_mesh(1.0, 1.0, 2, 2)
    right = {int(i): 300.0 for i in np.unique(mesh.boundary["right"])}
    steady = dict(thermal_conductivity=2.0, prescribed_temperature=right, heat_source_density=5.0,
                  inward_heat_flux={"top": 3.0})
    transient = dict(thermal_conductivity=2.0, volumetric_heat_capacity=3.0, time=np.array([0.0, 1.0]),
                     initial_temperature=np.full(mesh.num_nodes, 300.0), prescribed_temperature=right,
                     heat_source_density=5.0, inward_heat_flux={"top": 3.0})
    box = box_mesh(1.0, 1.0, 1.0, 1, 1, 1)
    return {PlanarSteadyHeatResult: solve_steady_heat(mesh, **steady),
            AxisymmetricSteadyHeatResult: solve_steady_heat(mesh, **steady, coordinate_system="axisymmetric"),
            PlanarTransientHeatResult: solve_transient_heat(mesh, **transient),
            AxisymmetricTransientHeatResult: solve_transient_heat(mesh, **transient, coordinate_system="axisymmetric"),
            SteadyHeat3DResult: solve_steady_heat_3d(box, thermal_conductivity=2.0, prescribed_temperature={0: 300.0},
                                                     heat_source_density=5.0)}


def test_solvers_return_the_class_of_their_coordinate_system_with_units():
    for cls, result in _solves().items():
        assert type(result) is cls
        assert dict(result.units) == dict(cls.UNITS)
        with pytest.raises(TypeError):
            result.units["temperature"] = "degC"                   # read-only
    results = _solves()
    assert isinstance(results[PlanarSteadyHeatResult], SteadyHeatResult)
    assert isinstance(results[AxisymmetricTransientHeatResult], TransientHeatResult)


def test_the_wrong_basis_raises_attribute_error_that_says_why():
    results = _solves()
    for cls in TOTALS:
        result = results[cls]
        with pytest.raises(AttributeError, match="totals in W") as info:
            getattr(result, "generated_heat_rate_per_depth")
        assert "'generated_heat_rate'" in str(info.value)
    for cls in PLANAR:
        with pytest.raises(AttributeError, match="per metre of depth"):
            getattr(results[cls], "generated_heat_rate")
    with pytest.raises(AttributeError, match="no attribute 'no_such_field'"):
        getattr(results[PlanarSteadyHeatResult], "no_such_field")
    assert not hasattr(results[PlanarSteadyHeatResult], "load")       # the names before the galerkin step
    assert not hasattr(results[PlanarTransientHeatResult], "temperature_k")


def test_frozen_results_refuse_assignment_and_the_rest_are_listed():
    results = _solves()
    for cls, result in results.items():
        params = getattr(cls, "__dataclass_params__")
        assert params.frozen == (cls in FROZEN), cls.__name__
        if cls in FROZEN:
            with pytest.raises(dataclasses.FrozenInstanceError):
                result.temperature = result.temperature


REFSOL_HEAT_RESULTS = {("refsol.thermal", "HeatFields"), ("refsol.thermal3d", "HeatFields3D"),
                       ("refsol.thermal_boundary", "BoundarySlab"), ("refsol.thermal_convection", "ConvectionFields"),
                       ("refsol.thermal_convection", "PublishedTarget"),
                       ("refsol.thermal_multilayer", "LayeredHeatFields"),
                       ("refsol.transient_heat", "TransientHeatFields"),
                       ("refsol.transient_heat_multilayer", "LayeredTransientFields"),
                       ("refsol.transient_heat_robin", "SlabTemperature")}
#: fields of refsol's heat results that are neither: the closed-form coefficients of BoundarySlab
#: (a in K, b in K/m), the series truncation bound of SlabTemperature (K) and PublishedTarget's
#: provenance text. Each has no registry name; refsol's results carry no .units yet.
REFSOL_UNNAMED = {("BoundarySlab", "a"), ("BoundarySlab", "b"), ("SlabTemperature", "truncation_bound"),
                  ("PublishedTarget", "source")}


def test_refsol_heat_result_fields_are_registry_or_structural_names(rules):
    import importlib
    seen = set()
    for module, name in sorted(REFSOL_HEAT_RESULTS):
        cls = getattr(importlib.import_module(module), name)
        for field in _fields(cls):
            if (name, field) in REFSOL_UNNAMED:
                seen.add((name, field))
                continue
            assert api_scan.structural_entry(field, module, rules) is not None or field in rules.registry, \
                f"{module}.{name}.{field}"
    assert seen == REFSOL_UNNAMED
