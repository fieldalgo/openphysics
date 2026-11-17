# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Check P3-11 of the galerkin step for the mode result: the result surface.

WaveguideModes (galerkin step, L3 commit 11b): every field is a registry name with a ``result``
place or a structural name (Appendix A); ``.units`` maps exactly the registry-named fields to the
registry's canonical units; a mode's quantities belong to the cross-section, which is neither a
planar per-depth result nor an axisymmetric one, so no field is ``_per_depth``; the result is
frozen and refuses assignment, and the kernel's names are not attributes of it.
"""
import dataclasses

import numpy as np
import pytest

import api_scan
from galerkin.mesh import rectangle_mesh
from galerkin.waveguide import WaveguideModes, solve_waveguide_modes


@pytest.fixture(scope="module")
def rules():
    return api_scan.load_rules()


@pytest.fixture(scope="module")
def result():
    mesh = rectangle_mesh(2e-6, 1e-6, 16, 8)
    centre = mesh.nodes[mesh.triangles].mean(axis=1)
    core = (np.abs(centre[:, 0] - 1e-6) < 0.4e-6) & (np.abs(centre[:, 1] - 0.5e-6) < 0.2e-6)
    return solve_waveguide_modes(mesh, relative_permittivity=np.where(core, 12.0, 2.1), vacuum_wavelength=1.55e-6,
                                 target_effective_index=3.4, search_mode_count=4)


def _fields():
    return [f.name for f in dataclasses.fields(WaveguideModes)]


def test_fields_are_registry_or_structural_names_and_units_are_canonical(rules):
    registry_fields = []
    for name in _fields():
        structural = api_scan.structural_entry(name, WaveguideModes.__module__, rules)
        quantity = rules.registry.get(name)
        assert structural is not None or quantity is not None, name
        if structural is None:
            places, unit = quantity
            assert "result" in places, f"{name} has no result place"
            registry_fields.append(name)
    assert {n for n in _fields() if n not in registry_fields} == {"space"}
    assert set(WaveguideModes.UNITS) == set(registry_fields)
    for name, unit in WaveguideModes.UNITS.items():
        assert unit == rules.registry[name][1], (name, unit)


def test_cross_section_quantities_are_not_per_depth():
    assert not [name for name in _fields() if name.endswith("_per_depth")]
    assert set(WaveguideModes.UNITS) == {"effective_index", "unnormalized_electric_field_line_integral",
                                         "unnormalized_electric_field_z", "vacuum_angular_wavenumber",
                                         "relative_permittivity", "relative_permeability"}


def test_the_solver_returns_the_class_with_units(result):
    assert type(result) is WaveguideModes
    assert dict(result.units) == dict(WaveguideModes.UNITS)
    with pytest.raises(TypeError):
        result.units["effective_index"] = "m"                        # read-only
    count = len(result.effective_index)
    assert count >= 1
    assert result.unnormalized_electric_field_line_integral.shape == (count, result.space.num_edges)
    assert result.unnormalized_electric_field_z.shape == (count, result.space.mesh.num_nodes)
    assert result.vacuum_angular_wavenumber == 2 * np.pi / 1.55e-6
    # the kernel's names (solve_modes returns n_eff, space, et, ez with E_z = 1j * ez) are not the result's
    for old in ("n_eff", "et", "ez", "k0", "eps_r", "mu_r"):
        assert not hasattr(result, old), old


def test_the_result_is_frozen(result):
    assert WaveguideModes.__dataclass_params__.frozen
    for name in _fields():
        with pytest.raises(dataclasses.FrozenInstanceError):
            setattr(result, name, getattr(result, name))
