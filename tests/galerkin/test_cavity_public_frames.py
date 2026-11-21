# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Check P3-5 of the galerkin step for the cavities: the public SI functions against the solver body.

The cases are two em.cavity3d documents of the units batch (P2-1): ``cavity_lossy_slab``
(examples/simcase: a lossy slab and 58 MS/m walls) and ``cavity_wall_conductivity``
(tools/units_batch/fixtures/v03: the same slab, one conducting wall). simcase runs each through
galerkin's public ``solve_material_cavity_box`` (route S, D2), and the test records that call: its
SI inputs (lengths in m, materials under exp(-i omega t)) and the public result.

- **Same frame, bitwise.** The private body ``_solve_material_cavity_box`` on the same inputs through
  ``to_kernel`` (each region's corners as its (low, high) bounds, its constants ``to_kernel``'d): every
  complex output of the public result is ``to_public`` of the body's, and every real one is the body's,
  byte for byte (dtype, shape and bytes); the quality factor is the same double as Re f / (-2 Im f).
- **What simcase saves is the public result.** Its saved arrays are the public result's fields, byte for
  byte, with no conversion in simcase.
- **Cross frame, under route S.** The cavity inputs are already SI, so there is no second (micrometre)
  frame to compare with: the cross-frame comparison is check P3-1's bit identity of the saved documents
  (these two among them) against the baseline, which conjugated the solver's exp(+j omega t) results in
  simcase itself.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

import galerkin
import simcase
from galerkin._conventions import to_kernel, to_public
from galerkin.material_cavity import _KernelRegion, _solve_material_cavity_box

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tools" / "units_batch" / "fixtures" / "v03"
CASES = {"cavity_lossy_slab": ROOT / "examples" / "simcase" / "cavity_lossy_slab.json",
         "cavity_wall_conductivity": FIXTURES / "cavity_wall_conductivity.json"}
#: public field -> the body's field, and whether the field is complex (to_public) or real (as it is)
FIELDS = {"resonant_frequency": ("frequencies_hz", True), "wavenumber_squared": ("eigenvalues_m2", True),
          "mass_normalized_electric_field_line_integral": ("edge_coefficients", True),
          "mass_normalized_electric_field": ("electric_field", True),
          "relative_permittivity": ("tet_relative_permittivity", True),
          "relative_permeability": ("tet_relative_permeability", True),
          "quality_factor": ("quality_factors", False), "relative_residual": ("relative_residuals", False),
          "pec_edges": ("pec_edge_ids", False), "iteration_count": ("fixed_point_iterations", False)}


def public_call(path):
    """simcase's run of one document: the keyword arguments of its public cavity call and the result."""
    calls = []
    solve = galerkin.solve_material_cavity_box

    def recording(**kwargs):
        result = solve(**kwargs)
        calls.append((kwargs, result))
        return result
    galerkin.solve_material_cavity_box = recording
    try:
        run = simcase.run(simcase.Document.from_dict(json.loads(Path(path).read_text(encoding="utf-8"))), False)
    finally:
        galerkin.solve_material_cavity_box = solve
    assert len(calls) == 1, len(calls)
    return run, *calls[0]


def body_on_the_same_inputs(kwargs):
    """``_solve_material_cavity_box`` on the public call's SI inputs through ``to_kernel``."""
    regions = [_KernelRegion(tuple(zip(r.lower_corner_position, r.upper_corner_position)),
                             to_kernel(r.relative_permittivity), to_kernel(r.relative_permeability))
               for r in kwargs["regions"]]
    return _solve_material_cavity_box(kwargs["box_size"], kwargs["subdivision_count"], regions=regions,
                                      num_modes=kwargs["mode_count"], target_frequency_hz=kwargs["target_frequency"],
                                      wall_conductivity_s_per_m=kwargs["electrical_conductivity"])


def _bits(a, b):
    a, b = np.asarray(a), np.asarray(b)
    return a.dtype == b.dtype and a.shape == b.shape and a.tobytes() == b.tobytes()


@pytest.fixture(scope="module", params=sorted(CASES))
def case(request):
    run, kwargs, public = public_call(CASES[request.param])
    return request.param, run, kwargs, public


def test_the_cases_are_lossy_material_cavities_with_conducting_walls(case):
    name, run, kwargs, public = case
    assert run.complex_layout and type(public) is galerkin.MaterialCavityResult
    assert [r.relative_permittivity for r in kwargs["regions"]] == [4 + 0.04j]      # Im >= 0: a loss
    assert kwargs["electrical_conductivity"] == (5.8e7 if name == "cavity_lossy_slab" else {"z1": 1e6})
    assert not public.lossless and np.all(public.resonant_frequency.imag < 0)


def test_same_frame_public_outputs_are_to_public_of_the_body_bitwise(case):
    name, run, kwargs, public = case
    body = body_on_the_same_inputs(kwargs)
    for field, (former, complex_value) in FIELDS.items():
        expected = getattr(body, former)
        assert _bits(getattr(public, field), to_public(expected) if complex_value else expected), field
        assert np.iscomplexobj(expected) == complex_value, field
    assert _bits(public.quality_factor, public.resonant_frequency.real / (-2 * public.resonant_frequency.imag))
    assert np.array_equal(public.mesh.nodes, body.mesh.nodes) and np.array_equal(public.space.edges, body.space.edges)
    assert dict(public.electrical_conductivity) == body.wall_conductivity_s_per_m
    assert (public.mode_count, public.target_frequency, public.lossless) == (
        body.requested_modes, body.target_frequency_hz, body.lossless)


def test_simcase_saves_the_public_result_as_it_is(case):
    name, run, kwargs, public = case
    arrays = run.arrays()
    saved_as = {"pec_edge_ids": "pec_edges"}           # the one saved name that is not the field's
    for saved in ("resonant_frequency", "wavenumber_squared", "quality_factor",
                  "mass_normalized_electric_field_line_integral", "mass_normalized_electric_field", "relative_residual",
                  "relative_permittivity", "relative_permeability", "pec_edge_ids", "iteration_count"):
        assert _bits(arrays[saved], getattr(public, saved_as.get(saved, saved))), saved
    origin = np.array(simcase.views.cavity_inputs(run.doc).box.origin)
    assert _bits(arrays["node_coordinates"], public.mesh.nodes + origin)               # D14: simcase translates
