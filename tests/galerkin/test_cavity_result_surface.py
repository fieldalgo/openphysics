# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Check P3-11 of the galerkin step for the cavity results: the result surface.

CavityResult and MaterialCavityResult (galerkin step, L3 commit 12): every field is a registry name with
a ``result`` place or a structural name (Appendix A); ``.units`` maps exactly the registry-named fields to
the registry's canonical units; a cavity's quantities are 3D totals, so no field is ``_per_depth``; both
results are frozen and refuse assignment (D14), and the solver's former field names are not attributes.
"""
import dataclasses

import numpy as np
import pytest

import api_scan
from galerkin.cavity import CavityResult, solve_cavity_box
from galerkin.material_cavity import CavityMaterialRegion, MaterialCavityResult, solve_material_cavity_box

#: the structural fields of each result (Appendix A): the mesh and edge space, the PEC edge ids and face tags,
#: the gradient-kernel count and, for the material solver, the lossless flag
STRUCTURAL = {CavityResult: {"mesh", "space", "pec_edges", "pec_faces", "gradient_kernel_dimension"},
              MaterialCavityResult: {"mesh", "space", "pec_edges", "gradient_kernel_dimension", "lossless"}}
#: the solver's former field names (the private bodies' records keep them)
FORMER = ("frequencies_hz", "resonant_frequencies_hz", "eigenvalues_m2", "edge_coefficients", "electric_field",
          "relative_residuals", "pec_edge_ids", "requested_modes", "target_frequency_hz", "pec_face_tags",
          "quality_factors", "tet_relative_permittivity", "tet_relative_permeability", "wall_conductivity_s_per_m",
          "fixed_point_iterations")


@pytest.fixture(scope="module")
def rules():
    return api_scan.load_rules()


@pytest.fixture(scope="module")
def results():
    vacuum = solve_cavity_box(box_size=(1.0, 0.8, 0.6), subdivision_count=(2, 2, 2), mode_count=2,
                              target_frequency=2.2e8)
    region = CavityMaterialRegion(lower_corner_position=(0.0, 0.0, 0.0), upper_corner_position=(1.0, 0.8, 0.3),
                                  relative_permittivity=4 + 0.04j)
    material = solve_material_cavity_box(box_size=(1.0, 0.8, 0.6), subdivision_count=(2, 2, 2), regions=[region],
                                         mode_count=2, target_frequency=1.5e8, electrical_conductivity={"z1": 1e6})
    return {CavityResult: vacuum, MaterialCavityResult: material}


def _fields(cls):
    return [f.name for f in dataclasses.fields(cls)]


@pytest.mark.parametrize("cls", [CavityResult, MaterialCavityResult], ids=lambda c: c.__name__)
def test_fields_are_registry_or_structural_names_and_units_are_canonical(rules, cls):
    registry_fields = []
    for name in _fields(cls):
        structural = api_scan.structural_entry(name, cls.__module__, rules)
        quantity = rules.registry.get(name)
        assert structural is not None or quantity is not None, name
        if structural is None:
            places, unit = quantity
            assert "result" in places, f"{name} has no result place"
            registry_fields.append(name)
    assert {n for n in _fields(cls) if n not in registry_fields} == STRUCTURAL[cls]
    assert set(cls.UNITS) == set(registry_fields)
    for name, unit in cls.UNITS.items():
        assert unit == rules.registry[name][1], (name, unit)


@pytest.mark.parametrize("cls", [CavityResult, MaterialCavityResult], ids=lambda c: c.__name__)
def test_cavity_quantities_are_3d_totals_not_per_depth(cls):
    assert not [name for name in _fields(cls) if name.endswith("_per_depth")]
    assert {"resonant_frequency", "wavenumber_squared", "mass_normalized_electric_field_line_integral",
            "mass_normalized_electric_field", "relative_residual", "mode_count", "target_frequency"} <= set(cls.UNITS)


@pytest.mark.parametrize("cls", [CavityResult, MaterialCavityResult], ids=lambda c: c.__name__)
def test_the_solvers_return_the_class_with_units(results, cls):
    result = results[cls]
    assert type(result) is cls
    assert dict(result.units) == dict(cls.UNITS)
    with pytest.raises(TypeError):
        result.units["resonant_frequency"] = "rad/s"                       # read-only
    count = result.mode_count
    assert result.resonant_frequency.shape == result.wavenumber_squared.shape == (count,)
    assert result.mass_normalized_electric_field_line_integral.shape == (result.space.num_edges, count)
    assert result.mass_normalized_electric_field.shape == (count, result.mesh.num_tets, 3)
    assert (result.search, result.cluster_completeness, result.mode_count_policy) == (
        "near_target", "not_certified", "exact_count_may_split_cluster")
    for old in FORMER:
        assert not hasattr(result, old), old
    if cls is MaterialCavityResult:
        assert result.time_convention == "exp(-i omega t)"
        assert result.relative_permittivity.shape == result.relative_permeability.shape == (result.mesh.num_tets,)
        assert dict(result.electrical_conductivity) == {"x0": None, "x1": None, "y0": None, "y1": None, "z0": None,
                                                       "z1": 1e6}
        with pytest.raises(TypeError):
            result.electrical_conductivity["z1"] = 1.0                    # read-only
    else:
        assert result.pec_faces == ("x0", "x1", "y0", "y1", "z0", "z1")
        assert np.isrealobj(result.resonant_frequency)


@pytest.mark.parametrize("cls", [CavityResult, MaterialCavityResult], ids=lambda c: c.__name__)
def test_the_result_is_frozen(results, cls):
    result = results[cls]
    assert cls.__dataclass_params__.frozen
    for name in _fields(cls):
        with pytest.raises(dataclasses.FrozenInstanceError):
            setattr(result, name, getattr(result, name))
