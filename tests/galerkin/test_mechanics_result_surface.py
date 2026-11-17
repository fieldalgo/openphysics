# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Check P3-11 of the galerkin step for the mechanics, thermoelastic and workflow results.

For each public result class (galerkin step, L2 commit 8): every field is a registry name with a
``result`` place or a structural name (Appendix A); ``.units`` maps exactly the registry-named
fields to the registry's canonical units; the results are planar, so every nodal force and the
strain energy are ``_per_depth`` and asking for the total's name raises AttributeError that says
why. ElasticityResult, the workflow aggregate and the transient records are frozen;
ThermoelasticResult stays mutable (tests assign to its fields). The
temperature snapshot is a frozen record whose ``units`` field replaces length_unit and
temperature_unit. refsol's mechanics records get the field-name clause (they carry no ``.units``).
"""
import dataclasses
from types import MappingProxyType

import numpy as np
import pytest

import api_scan
from galerkin.elasticity import ElasticityResult, solve_elasticity
from galerkin.mesh import rectangle_mesh
from galerkin.thermal_mechanical import SteadyThermoelasticResult, solve_steady_thermoelasticity
from galerkin.thermoelasticity import (TemperatureSnapshot, ThermoelasticResult, freeze_temperature,
                                       solve_thermoelasticity)
from galerkin.transient_heat import solve_transient_heat
from galerkin.transient_thermal_mechanical import (TransientThermoelasticResult, TransientThermoelasticStep,
                                                   solve_transient_thermoelasticity)

RESULTS = (ElasticityResult, ThermoelasticResult, SteadyThermoelasticResult, TransientThermoelasticStep,
           TransientThermoelasticResult)
FROZEN = (ElasticityResult, SteadyThermoelasticResult, TransientThermoelasticStep, TransientThermoelasticResult)
#: the canonical units of a force or an energy per metre of depth
PER_DEPTH_UNITS = {"N/m", "J/m"}
MATERIAL = dict(youngs_modulus=70e9, poisson_ratio=0.3, plane="strain")
THERMAL = dict(linear_expansion_coefficient=12e-6, stress_free_temperature=293.15)


@pytest.fixture(scope="module")
def rules():
    return api_scan.load_rules()


def _fields(cls):
    return [f.name for f in dataclasses.fields(cls)]


@pytest.mark.parametrize("cls", RESULTS)
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


@pytest.mark.parametrize("cls", RESULTS)
def test_planar_forces_and_energy_are_per_depth(cls):
    rates = [name for name, unit in cls.UNITS.items() if unit in PER_DEPTH_UNITS]
    # the workflow and step records hold their forces in ``mechanics`` (a ThermoelasticResult)
    assert bool(rates) == (cls in (ElasticityResult, ThermoelasticResult))
    assert all(name.endswith("_per_depth") for name in rates)
    assert all(cls.UNITS[name] in PER_DEPTH_UNITS for name in cls.UNITS if name.endswith("_per_depth"))
    assert cls.BASIS == "planar"


def _solves():
    n = 4
    mesh = rectangle_mesh(1.0, 1.0, n, n)
    supports = {(0, 0): 0.0, (0, 1): 0.0, (n, 1): 0.0}
    elastic = solve_elasticity(mesh, **MATERIAL, prescribed_displacement=supports, traction={"right": (1e6, 0.0)})
    snapshot = freeze_temperature(mesh, temperature=np.full(mesh.num_nodes, 313.15))
    thermoelastic = solve_thermoelasticity(mesh, snapshot, **MATERIAL, **THERMAL, prescribed_displacement=supports)
    hot = {int(i): 303.15 for i in mesh.boundary["left"]}
    steady = solve_steady_thermoelasticity(mesh, thermal_conductivity=10.0, prescribed_temperature=hot,
                                           **MATERIAL, **THERMAL, prescribed_displacement=supports)
    heat = solve_transient_heat(mesh, thermal_conductivity=2.0, volumetric_heat_capacity=4.0, time=[0.0, 0.5, 1.0],
                                initial_temperature=np.full(mesh.num_nodes, 300.0), prescribed_temperature={},
                                heat_source_density=8.0)
    transient = solve_transient_thermoelasticity(mesh, heat, **MATERIAL, **THERMAL, prescribed_displacement=supports)
    return {ElasticityResult: elastic, ThermoelasticResult: thermoelastic, SteadyThermoelasticResult: steady,
            TransientThermoelasticStep: transient.steps[-1], TransientThermoelasticResult: transient,
            TemperatureSnapshot: snapshot}


def test_solvers_return_their_classes_with_units():
    for cls, result in _solves().items():
        assert type(result) is cls
        if cls is TemperatureSnapshot:
            continue
        assert dict(result.units) == dict(cls.UNITS)
        with pytest.raises(TypeError):
            result.units["displacement"] = "mm"                          # read-only


def test_the_total_name_raises_attribute_error_that_says_why():
    results = _solves()
    for cls, total, unit in ((ElasticityResult, "reaction_force", "N/m"),
                             (ElasticityResult, "applied_force", "N/m"),
                             (ThermoelasticResult, "strain_energy", "J/m"),
                             (ThermoelasticResult, "thermal_equivalent_force", "N/m"),
                             (ThermoelasticResult, "applied_body_force", "N/m")):
        with pytest.raises(AttributeError, match="per metre of depth") as info:
            getattr(results[cls], total)
        assert f"'{total}_per_depth', in {unit}" in str(info.value)
    with pytest.raises(AttributeError, match="no attribute 'no_such_field'"):
        getattr(results[ElasticityResult], "no_such_field")
    # the names before the galerkin step
    for cls, old in ((ElasticityResult, "load"), (ElasticityResult, "reaction"), (ElasticityResult, "residual"),
                     (ThermoelasticResult, "total_strain"), (ThermoelasticResult, "sigma_zz"),
                     (ThermoelasticResult, "epsilon_zz"), (ThermoelasticResult, "load_external"),
                     (ThermoelasticResult, "load_thermal"), (ThermoelasticResult, "load_total"),
                     (ThermoelasticResult, "physical_elastic_energy"),
                     (ThermoelasticResult, "reference_temperature_k"), (ThermoelasticResult, "young_modulus"),
                     (TransientThermoelasticStep, "time_s"), (TransientThermoelasticResult, "time_s"),
                     (TemperatureSnapshot, "temperature_k"), (TemperatureSnapshot, "length_unit"),
                     (TemperatureSnapshot, "temperature_unit")):
        assert not hasattr(results[cls], old), (cls.__name__, old)


def test_the_transient_result_reads_its_steps():
    transient = _solves()[TransientThermoelasticResult]
    assert transient.time_indices == tuple(step.time_index for step in transient.steps) == (0, 1, 2)
    assert transient.time == tuple(step.time for step in transient.steps) == (0.0, 0.5, 1.0)


def test_frozen_results_refuse_assignment():
    for cls, result in _solves().items():
        if cls is TemperatureSnapshot:
            continue
        assert getattr(cls, "__dataclass_params__").frozen == (cls in FROZEN), cls.__name__
        name = _fields(cls)[1]
        if cls in FROZEN:
            with pytest.raises(dataclasses.FrozenInstanceError):
                setattr(result, name, getattr(result, name))
        else:
            setattr(result, name, getattr(result, name))


def test_the_snapshot_record(rules):
    snapshot = _solves()[TemperatureSnapshot]
    assert getattr(TemperatureSnapshot, "__dataclass_params__").frozen
    for name in _fields(TemperatureSnapshot):
        assert (api_scan.structural_entry(name, TemperatureSnapshot.__module__, rules) is not None
                or "result" in rules.registry[name][0]), name
    assert isinstance(snapshot.units, MappingProxyType)
    assert dict(snapshot.units) == {"nodes": "m", "temperature": "K"}
    assert rules.registry["temperature"][1] == snapshot.units["temperature"]
    with pytest.raises(TypeError):
        snapshot.units["temperature"] = "C"
    with pytest.raises(dataclasses.FrozenInstanceError):
        snapshot.units = {"nodes": "m", "temperature": "K"}
    assert snapshot.schema_version == 1
    np.testing.assert_array_equal(snapshot.temperature, 313.15)
    with pytest.raises(ValueError):
        snapshot.temperature.flags.writeable = True


@pytest.mark.parametrize("module, name", [
    ("refsol.elasticity", "ElasticityFields"), ("refsol.elasticity_traction", "TractionFields"),
    ("refsol.elasticity_multilayer", "LayeredElasticFields"), ("refsol.elasticity_multilayer", "CylinderFields"),
    ("refsol.bimetal", "BimetalCurvature"), ("refsol.bimetal", "StripFields"),
    ("refsol.thermoelasticity", "ThermoelasticState"), ("refsol.thermoelasticity", "ThermoelasticField"),
    ("refsol.thermoelastic_traction", "TractionState")])
def test_refsol_mechanics_fields_are_registry_or_structural_names(module, name, rules):
    import importlib
    cls = getattr(importlib.import_module(module), name)
    # CylinderFields._coefficients: A_i (1) and B_i (m^2) together, no registry name (rule R(2))
    assert {f for f in _fields(cls) if f.startswith("_")} == ({"_coefficients"} if name == "CylinderFields" else set())
    for field in (f for f in _fields(cls) if not f.startswith("_")):
        assert api_scan.structural_entry(field, module, rules) is not None or field in rules.registry, \
            f"{name}.{field}"
