# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Installed sipi consumer contract, copied outside the checkout by the wheel gates.

Exercises the documented public API of the installed ``sipi`` wheel on tiny
cross-sections: the stripline and microstrip templates, a hand-built section,
the JSON ``CrossSectionDocument`` and a DC power plane. sipi has no command-line
entry point; the API and the JSON document are its public surface. The physical
checks reuse the closed-form references of ``tests/sipi`` (Cohn 1954,
Hammerstad and Jensen 1980) on coarse meshes with loose, stated bounds; the
sharp convergence criteria stay in the source suite. Every case ran in under a
second on Linux. Missing APIs are failures, never optional skips.
"""

import importlib.metadata
import json
from pathlib import Path
import sys

import numpy as np
import pytest
from scipy.constants import epsilon_0, mu_0
from scipy.special import ellipk, ellipkm1

import galerkin
import meshine
import sipi
from sipi import (COPPER_CONDUCTIVITY, CrossSection, CrossSectionDocument, Layer, LineParameters,
                  PowerPlane, Sink, Source, Trace, edge, microstrip, rectangle_outline, stripline)

ETA0 = float(np.sqrt(mu_0 / epsilon_0))   # 376.730 ohm, as in every reference used here


def cohn_stripline_z0(w, b, eps_r):
    """Zero-thickness stripline, Cohn's exact conformal map (IRE Trans. MTT 2(2), 1954)."""
    k = 1.0 / np.cosh(np.pi * w / (2.0 * b))
    return ETA0 / (4.0 * np.sqrt(eps_r)) * ellipk(k * k) / ellipkm1(k * k)


def hammerstad_jensen(u, eps_r):
    """Zero-thickness microstrip (Z0, eps_eff), Hammerstad and Jensen, MTT-S 1980."""
    f = 6.0 + (2.0 * np.pi - 6.0) * np.exp(-(30.666 / u) ** 0.7528)
    z_air = ETA0 / (2.0 * np.pi) * np.log(f / u + np.sqrt(1.0 + 4.0 / u ** 2))
    a = (1.0 + np.log((u ** 4 + (u / 52.0) ** 2) / (u ** 4 + 0.432)) / 49.0
         + np.log(1.0 + (u / 18.1) ** 3) / 18.7)
    b = 0.564 * ((eps_r - 0.9) / (eps_r + 3.0)) ** 0.053
    eps_eff = (eps_r + 1.0) / 2.0 + (eps_r - 1.0) / 2.0 * (1.0 + 10.0 / u) ** (-a * b)
    return z_air / np.sqrt(eps_eff), eps_eff


# V3 geometry of the validation record: w/b = 0.5, eps_r = 4, Z0 = 50.216 ohm.
W, B, EPS_R = 0.5e-3, 1.0e-3, 4.0
COARSE = dict(edge_size=8e-6, grade=0.3, far_size=B / 4)   # the coarsest V3 mesh, -1.0 % measured


def stripline_section(tan_delta=0.0):
    return CrossSection([Layer("lower", B / 2, EPS_R, tan_delta), Layer("upper", B / 2, EPS_R, tan_delta)],
                        [Trace("s", 0.0, W, B / 2)], width=12 * B, bottom="ground", top="ground")


def test_documented_public_api_is_installed():
    prefix = Path(sys.prefix).resolve()
    for module in (sipi, galerkin, meshine):
        assert Path(module.__file__).resolve().is_relative_to(prefix), module.__name__
    assert sipi.__version__ == importlib.metadata.version("sipi")
    for name in sipi.__all__:
        assert hasattr(sipi, name), name


def test_stripline_matches_cohn_on_a_coarse_mesh():
    exact = cohn_stripline_z0(W, B, EPS_R)
    line = stripline_section().analyze(**COARSE)
    assert isinstance(line, LineParameters) and line.names == ("s",)
    # Coarse mesh: 2 % is loose against the -1.0 % measured at this size, 0.5 % at the finest.
    assert line.z0 == pytest.approx(exact, rel=2e-2), (line.z0, exact)
    # Homogeneous dielectric: C = eps_r C0 exactly, so eps_eff is exact in P1.
    assert line.eps_eff == pytest.approx(EPS_R, rel=1e-9)
    np.testing.assert_allclose(line.C, EPS_R * line.C0, rtol=1e-9)
    # Documented definitions: L = mu0 eps0 inv(C0) and z0 = sqrt(L / C).
    np.testing.assert_allclose(line.L, mu_0 * epsilon_0 / line.C0, rtol=1e-12)
    assert line.z0 == pytest.approx(np.sqrt(line.L[0, 0] / line.C[0, 0]), rel=1e-12)
    assert line.delay == pytest.approx(np.sqrt(EPS_R) / 299792458.0, rel=1e-9)
    # The conforming solution approaches the exact capacitance from above, so
    # the impedance of a finite-element line lies below Cohn's value.
    assert line.z0 < exact


def test_stripline_template_matches_the_hand_built_section():
    template = stripline(width=W, plane_spacing=B, eps_r=EPS_R)
    assert template.top == "ground" and template.bottom == "ground"
    assert template.width == 12 * B and len(template.traces) == 1
    assert template.traces[0].y == B / 2 and template.traces[0].thickness == 0.0
    line = template.analyze()   # default mesh rule of the documentation
    assert line.z0 == pytest.approx(cohn_stripline_z0(W, B, EPS_R), rel=1e-2)   # -0.42 % measured
    assert line.eps_eff == pytest.approx(EPS_R, rel=1e-9)


def test_microstrip_template_matches_hammerstad_jensen():
    h = 1e-3
    z_ref, eps_ref = hammerstad_jensen(1.0, 4.3)
    line = microstrip(width=h, substrate_height=h, eps_r=4.3).analyze()
    # Default box (20 h wide, 10 h of air) and mesh; the reference itself is
    # quoted to 0.03 % (Z0) and 0.2 % (eps_eff). Measured +0.07 % and +0.74 %.
    assert line.z0 == pytest.approx(z_ref, rel=1e-2), (line.z0, z_ref)
    assert line.eps_eff == pytest.approx(eps_ref, rel=2e-2), (line.eps_eff, eps_ref)
    assert 1.0 < line.eps_eff < 4.3


def test_dielectric_loss_is_linear_in_frequency():
    tan_delta = 0.02
    line = stripline_section(tan_delta).analyze(**COARSE)
    # Every dielectric is lossy with the same tan_delta: the effective loss tangent is exact.
    assert line.loss_tangent() == pytest.approx(tan_delta, rel=1e-9)
    np.testing.assert_allclose(line.G(2e9), 2 * line.G(1e9), rtol=1e-12)
    np.testing.assert_allclose(line.G(1e9), 2 * np.pi * 1e9 * line.C_loss, rtol=1e-12)
    lossless = stripline_section().analyze(**COARSE)
    np.testing.assert_allclose(line.C, lossless.C, rtol=1e-12)
    assert np.all(lossless.C_loss == 0)


def test_json_document_round_trip_reproduces_the_analysis(tmp_path):
    section = stripline_section()
    document = CrossSectionDocument(section, mesh=COARSE)
    path = tmp_path / "stripline.json"
    path.write_text(document.dumps(), encoding="utf-8")
    loaded = CrossSectionDocument.loads(path.read_text(encoding="utf-8"))
    assert loaded.to_dict() == document.to_dict()
    assert loaded.to_dict()["schema"] == "sipi.cross-section/1"
    assert loaded.to_dict()["length_unit"] == "m"
    assert loaded.mesh_options == COARSE
    direct = section.analyze(**COARSE)
    replayed = loaded.analyze()
    assert replayed.z0 == pytest.approx(direct.z0, rel=1e-12)
    np.testing.assert_allclose(replayed.C, direct.C, rtol=1e-12)
    # Unknown fields and other units are errors, not silently ignored input.
    data = json.loads(path.read_text(encoding="utf-8"))
    with pytest.raises(ValueError):
        CrossSectionDocument.from_dict({**data, "comment": "not allowed"})
    with pytest.raises(ValueError):
        CrossSectionDocument.from_dict({**data, "length_unit": "mm"})


def test_power_plane_strip_matches_the_exact_resistance():
    length, width, thickness, current = 50e-3, 5e-3, 35e-6, 2.0
    plane = PowerPlane(rectangle_outline(0.0, 0.0, length, width), thickness=thickness,
                       sources=[Source("vrm", edge((0.0, 0.0), (0.0, width)), voltage=1.0)],
                       sinks=[Sink("load", edge((length, 0.0), (length, width)), current=current)])
    result = plane.solve()
    # Uniform current along a strip is linear in x, so P1 reproduces it exactly.
    resistance = length / (COPPER_CONDUCTIVITY * thickness * width)
    assert result.resistance("load") == pytest.approx(resistance, rel=1e-9)
    assert result.drop("load") == pytest.approx(current * resistance, rel=1e-9)
    assert result.power_loss == pytest.approx(current ** 2 * resistance, rel=1e-9)
    assert result.terminals["load"]["current"] == pytest.approx(-current, rel=1e-9)
    assert result.terminals["vrm"]["current"] == pytest.approx(current, rel=1e-9)
    assert np.all(np.isfinite(result.potential)) and result.potential.max() <= 1.0 + 1e-12
