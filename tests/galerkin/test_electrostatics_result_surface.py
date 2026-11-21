# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Check P3-11 of the galerkin step for the electrostatic result: the result surface.

ElectrostaticsResult (galerkin step, L3 commit 10): every field is a registry name with a
``result`` place or a structural name (Appendix A); ``.units`` maps exactly the registry-named
fields to the registry's canonical units; the result is planar (the solver has no axisymmetric
form), so every nodal or integrated charge and the energy are ``_per_depth``, and asking for the
total's name raises AttributeError that says why; the result is frozen and refuses assignment.
"""
import dataclasses

import numpy as np
import pytest

import api_scan
from galerkin.electrostatics import ElectrostaticsResult, solve_electrostatics
from galerkin.mesh import annulus_mesh

#: the canonical units of a value per metre of depth: charge and energy
PER_DEPTH_UNITS = {"C/m", "J/m"}


@pytest.fixture(scope="module")
def rules():
    return api_scan.load_rules()


@pytest.fixture(scope="module")
def result():
    mesh = annulus_mesh(1.0, 3.0, 2, 12)
    return solve_electrostatics(mesh, relative_permittivity=2.2, conductors={"inner": (mesh.boundary["inner"], 1.0)},
                                ground=mesh.boundary["outer"], free_charge_density=1e-6)


def _fields():
    return [f.name for f in dataclasses.fields(ElectrostaticsResult)]


def test_fields_are_registry_or_structural_names_and_units_are_canonical(rules):
    registry_fields = []
    for name in _fields():
        structural = api_scan.structural_entry(name, ElectrostaticsResult.__module__, rules)
        quantity = rules.registry.get(name)
        assert structural is not None or quantity is not None, name
        if structural is None:
            places, unit = quantity
            assert "result" in places, f"{name} has no result place"
            registry_fields.append(name)
    assert {n for n in _fields() if n not in registry_fields} == {"mesh", "conductor_node_ids"}
    assert set(ElectrostaticsResult.UNITS) == set(registry_fields)
    for name, unit in ElectrostaticsResult.UNITS.items():
        assert unit == rules.registry[name][1], (name, unit)


def test_planar_charges_and_energy_are_per_depth():
    per_depth = [name for name, unit in ElectrostaticsResult.UNITS.items() if unit in PER_DEPTH_UNITS]
    assert sorted(per_depth) == sorted(["stored_energy_per_depth", "applied_charge_per_depth",
                                        "reaction_charge_per_depth", "residual_charge_per_depth",
                                        "charge_per_depth", "free_charge_per_depth"])
    assert all(name.endswith("_per_depth") for name in per_depth)
    assert ElectrostaticsResult.BASIS == "planar"


def test_the_solver_returns_the_class_with_units(result):
    assert type(result) is ElectrostaticsResult
    assert dict(result.units) == dict(ElectrostaticsResult.UNITS)
    with pytest.raises(TypeError):
        result.units["stored_energy_per_depth"] = "J"                  # read-only
    assert result.free_charge_per_depth > 0 and np.sum(result.applied_charge_per_depth) > 0


def test_the_total_name_raises_attribute_error_that_says_why(result):
    for total, unit in (("stored_energy", "J/m"), ("charge", "C/m"), ("free_charge", "C/m"),
                        ("reaction_charge", "C/m")):
        with pytest.raises(AttributeError, match="charges and energies per metre of depth") as info:
            getattr(result, total)
        assert f"'{total}_per_depth', in {unit}" in str(info.value)
    with pytest.raises(AttributeError, match="no attribute 'no_such_field'"):
        getattr(result, "no_such_field")
    # the names before the galerkin step
    for old in ("potential", "displacement", "energy_per_length", "load", "reaction", "residual", "conductors",
                "total_free_charge"):
        assert not hasattr(result, old), old


def test_the_result_is_frozen(result):
    assert ElectrostaticsResult.__dataclass_params__.frozen
    for name in _fields():
        with pytest.raises(dataclasses.FrozenInstanceError):
            setattr(result, name, getattr(result, name))
