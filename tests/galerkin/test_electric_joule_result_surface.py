# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Check P3-11 of the galerkin step for the electric and Joule results: the result surface.

For each public electric and Joule result class (galerkin step, L2 commit 7): every field is a
registry name with a ``result`` place or a structural name (Appendix A); ``.units`` maps exactly
the registry-named fields to the registry's canonical units; the results are planar (these
solvers have no axisymmetric form), so every nodal or integrated rate is ``_per_depth`` and asking
for the total's name raises AttributeError that says why; the results are frozen and refuse
assignment. refsol's Joule slab gets the field-name clause (it carries no ``.units``).
"""
import dataclasses

import numpy as np
import pytest

import api_scan
from galerkin.electric import SteadyElectricResult, solve_steady_electric
from galerkin.joule_heating import SteadyJouleHeatResult, solve_steady_joule_heat
from galerkin.mesh import rectangle_mesh
from galerkin.temperature_joule_heating import (ConductivityModel, JouleIteration, TemperatureJouleHeatResult,
                                                solve_temperature_joule_heat)

RESULTS = (SteadyElectricResult, SteadyJouleHeatResult, TemperatureJouleHeatResult, JouleIteration)
#: frozen: no caller or test assigns to their fields (SteadyJouleHeatResult newly, L2 commit 7; the
#: others were frozen before)
FROZEN = RESULTS
#: the canonical units of a rate per metre of depth
PER_DEPTH_UNITS = {"W/m", "A/m"}


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
def test_planar_rates_are_per_depth(cls):
    rates = [name for name, unit in cls.UNITS.items() if unit in PER_DEPTH_UNITS]
    # TemperatureJouleHeatResult holds its rates in ``coupled`` (a SteadyJouleHeatResult)
    assert bool(rates) == (cls is not TemperatureJouleHeatResult)
    assert all(name.endswith("_per_depth") for name in rates)
    assert all(cls.UNITS[name] in PER_DEPTH_UNITS for name in cls.UNITS if name.endswith("_per_depth"))
    assert cls.BASIS == "planar"


def _solves():
    mesh = rectangle_mesh(1.0, 0.25, 4, 2)
    left = {int(i): 0.0 for i in mesh.boundary["left"]}
    held = {int(i): 300.0 for i in np.r_[mesh.boundary["left"], mesh.boundary["right"]]}
    electric = solve_steady_electric(mesh, electrical_conductivity=2.0, prescribed_electric_potential=left,
                                     inward_current_density={"right": -1.0})
    joule = solve_steady_joule_heat(mesh, electrical_result=electric, thermal_conductivity=1.0,
                                    prescribed_temperature=held)
    coupled = solve_temperature_joule_heat(
        mesh, electrical_conductivity=ConductivityModel(lambda t: 2.0 / (1 + 0.01 * (t - 300)), (250.0, 900.0)),
        thermal_conductivity=1.0, prescribed_electric_potential=left, prescribed_temperature=held,
        initial_temperature=300.0, temperature_tolerance=1e-8, inward_current_density={"right": -1.0},
        relaxation_factor=1.0)
    return {SteadyElectricResult: electric, SteadyJouleHeatResult: joule, TemperatureJouleHeatResult: coupled,
            JouleIteration: coupled.history[-1]}


def test_solvers_return_their_classes_with_units():
    for cls, result in _solves().items():
        assert type(result) is cls
        assert dict(result.units) == dict(cls.UNITS)
        with pytest.raises(TypeError):
            result.units["joule_power_per_depth"] = "W"                # read-only


def test_the_total_name_raises_attribute_error_that_says_why():
    results = _solves()
    for cls, total, unit in ((SteadyElectricResult, "joule_power", "W/m"),
                             (SteadyElectricResult, "reaction_current", "A/m"),
                             (SteadyJouleHeatResult, "generated_heat_rate", "W/m"),
                             (JouleIteration, "maximum_residual_current", "A/m")):
        with pytest.raises(AttributeError, match="per metre of depth") as info:
            getattr(results[cls], total)
        assert f"'{total}_per_depth', in {unit}" in str(info.value)
    with pytest.raises(AttributeError, match="no attribute 'no_such_field'"):
        getattr(results[SteadyElectricResult], "no_such_field")
    # the names before the galerkin step
    assert not hasattr(results[SteadyElectricResult], "potential")
    assert not hasattr(results[SteadyJouleHeatResult], "source_power_per_length")
    assert not hasattr(results[TemperatureJouleHeatResult], "evaluated_temperature")
    assert not hasattr(results[JouleIteration], "temperature_defect")


def test_frozen_results_refuse_assignment():
    for cls, result in _solves().items():
        assert getattr(cls, "__dataclass_params__").frozen == (cls in FROZEN), cls.__name__
        name = _fields(cls)[1]
        with pytest.raises(dataclasses.FrozenInstanceError):
            setattr(result, name, getattr(result, name))


def test_refsol_joule_slab_fields_are_registry_or_structural_names(rules):
    from refsol.joule_slab import JouleSlab
    public = [name for name in _fields(JouleSlab) if not name.startswith("_")]
    # private: _joule_power (W/m^2 per face area, no registry name; rule R(2)) and the oriented solution
    assert set(_fields(JouleSlab)) - set(public) == {"_joule_power", "_scaled"}
    for name in public:
        assert api_scan.structural_entry(name, JouleSlab.__module__, rules) is not None or name in rules.registry, \
            f"JouleSlab.{name}"
