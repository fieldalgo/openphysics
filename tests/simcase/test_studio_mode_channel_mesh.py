# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""The guided / leaky notes of open-boundary modes across the core mesh and the wavelength (slice
S3): gates G6 and G7 of the design draft, pre-registered there before the implementation (measured
on main 2318e5f, Linux, except where marked blind). G1 to G5 and G8 are
test_studio_mode_channel_gate.py.

- G6: G1 (T16, every edge open, the default targets, 4 modes) and G2 (the template, every edge
  open, 2 modes) at core mesh 20 nm and 60 nm: modes 1 and 2 keep their category at 30 nm (T16
  leaky into Substrate, the template guided). Blind: T16's mode 3 at 60 nm (not measured before the
  gate) must also be leaky into Substrate. T16's mode 3 at 20 nm is reported, not gated.
- G7 (blind): G1 at 1400 nm and 1700 nm: modes 1 and 2 are leaky into Substrate, with the indices of
  the run's wavelength (slice S1).

Modes are taken in Studio's order (Re n_eff, highest first): the draft's Re n_eff values at 20 and
60 nm (T16 2.44199 / 2.43264 and 1.77460 / 1.76655, template 2.44404 / 2.43494 and 1.77131 / 1.76430)
are printed beside them, not gated. The gain bound of each mode (G8 covers G1 to G5) is reported.
"""
from __future__ import annotations

import pytest

import mode_channel_fixtures as G
from open_boundary_fixtures import ALL


def _modes(out, count, kind, regions, which):
    assert len(out["channel"]) >= count, (which, out["channel"])
    for c in out["channel"][:count]:
        assert c["kind"] == kind, (which, c)
        assert [r["name"] for r in c["regions"]] == regions, (which, c)


@pytest.mark.slow
@pytest.mark.parametrize("mesh", [20, 60])
def test_g6_t16_keeps_its_category_at_core_mesh_20_and_60_nm(tmp_path, mesh):
    record, seconds = G.studio_run(G.build("strip_substrate", 4, core_mesh=mesh), "strip_substrate", ALL, core_mesh=mesh)
    out = G.notes(record, tmp_path)
    G.show(f"G6 T16 at core mesh {mesh} nm, {len(record['field']['triangles'])} triangles", out, seconds)
    _modes(out, 2, "leaky", ["Substrate"], f"G6 T16 {mesh} nm")
    if mesh == 60:
        # blind: mode 3 at 60 nm
        _modes(out, 3, "leaky", ["Substrate"], "G6 T16 mode 3 at 60 nm (blind)")


@pytest.mark.slow
@pytest.mark.parametrize("mesh", [20, 60])
def test_g6_the_template_keeps_its_category_at_core_mesh_20_and_60_nm(tmp_path, mesh):
    record, seconds = G.studio_run(G.build("template", 2, core_mesh=mesh), "template", ALL, core_mesh=mesh)
    out = G.notes(record, tmp_path)
    G.show(f"G6 template at core mesh {mesh} nm", out, seconds)
    _modes(out, 2, "guided", ["the silica background"], f"G6 template {mesh} nm")


@pytest.mark.slow
@pytest.mark.parametrize("wavelength", [1400, 1700])
def test_g7_t16_is_leaky_into_the_substrate_at_1400_and_1700_nm(tmp_path, wavelength):
    record, seconds = G.studio_run(G.build("strip_substrate", 4, wavelength=wavelength), "strip_substrate", ALL, wavelength=wavelength)
    assert record["settings"]["vacuum_wavelength"] == f"{wavelength} nm"
    out = G.notes(record, tmp_path)
    G.show(f"G7 T16 at {wavelength} nm (blind)", out, seconds)
    _modes(out, 2, "leaky", ["Substrate"], f"G7 {wavelength} nm (blind)")
