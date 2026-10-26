# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""sipi against independent closed-form references (V1-V5 of the validation record).

V1 two-layer parallel plate: exact in P1 (piecewise-linear potential).
V2 coaxial line: exact C = 2 pi eps / ln(b/a); mesh convergence.
V3 zero-thickness stripline: Cohn's exact conformal map.
V4 zero-thickness edge-coupled stripline: Cohn's exact even/odd conformal maps.
V5 zero-thickness microstrip: Hammerstad & Jensen (1980) closed form, quoted
   accuracy 0.01-0.03 % (Z0) and 0.2 % (eps_eff); compared at 1 %.

The free-space impedance is eta0 = sqrt(mu0/eps0) = 376.730 ohm. The textbook
120 pi (376.991) is 6.9e-4 too large and would bias every comparison here.
"""

import numpy as np
import pytest
from scipy.constants import epsilon_0, mu_0
from scipy.special import ellipk, ellipkm1

from galerkin import from_mesher
from meshine import Circle, Domain, generate, rectangle
from sipi import CrossSection, Layer, Trace, capacitance_matrix, line_parameters

ETA0 = np.sqrt(mu_0 / epsilon_0)


def k_ratio(k):
    """K(k) / K(k') with modulus k (scipy takes m = k^2; ellipkm1(m) = K at 1 - m)."""
    return ellipk(k * k) / ellipkm1(k * k)


def stripline_z0(w, b, eps_r):
    k = 1.0 / np.cosh(np.pi * w / (2.0 * b))
    return ETA0 / (4.0 * np.sqrt(eps_r)) * k_ratio(k)


def coupled_stripline_z(w, s, b, eps_r):
    t1 = np.tanh(np.pi * w / (2.0 * b))
    t2 = np.tanh(np.pi * (w + s) / (2.0 * b))
    ke, ko = t1 * t2, t1 / t2
    scale = ETA0 / (4.0 * np.sqrt(eps_r))
    return scale / k_ratio(ke), scale / k_ratio(ko)


def hammerstad_jensen(u, eps_r):
    """Zero-thickness microstrip (Z0, eps_eff), Hammerstad & Jensen, MTT-S 1980."""
    f = 6.0 + (2.0 * np.pi - 6.0) * np.exp(-(30.666 / u) ** 0.7528)
    z_air = ETA0 / (2.0 * np.pi) * np.log(f / u + np.sqrt(1.0 + 4.0 / u ** 2))
    a = (1.0 + np.log((u ** 4 + (u / 52.0) ** 2) / (u ** 4 + 0.432)) / 49.0
         + np.log(1.0 + (u / 18.1) ** 3) / 18.7)
    b = 0.564 * ((eps_r - 0.9) / (eps_r + 3.0)) ** 0.053
    eps_eff = (eps_r + 1.0) / 2.0 + (eps_r - 1.0) / 2.0 * (1.0 + 10.0 / u) ** (-a * b)
    return z_air / np.sqrt(eps_eff), eps_eff


def test_reference_formulas_agree_with_simpler_textbook_forms():
    # Guards against transcription errors. Pozar's microstrip design formulas
    # (Microwave Engineering, 4th ed., eqs. 3.195-3.196) are a coarser fit of
    # the same curve and agree with Hammerstad-Jensen to about 1 %.
    for u, eps_r in ((1.0, 4.3), (2.0, 9.8), (4.0, 2.2)):
        eps_pozar = (eps_r + 1) / 2 + (eps_r - 1) / 2 / np.sqrt(1 + 12 / u)
        z_pozar = ETA0 / (np.sqrt(eps_pozar) * (u + 1.393 + 0.667 * np.log(u + 1.444)))
        z, eps = hammerstad_jensen(u, eps_r)
        assert eps == pytest.approx(eps_pozar, rel=1e-2)
        assert z == pytest.approx(z_pozar, rel=1.5e-2)
    # A wide stripline tends to two parallel-plate capacitors plus fringing.
    w, b = 20.0, 1.0
    assert stripline_z0(w, b, 1.0) < ETA0 * b / (4 * w)
    assert stripline_z0(w, b, 1.0) == pytest.approx(ETA0 * b / (4 * w), rel=0.1)


def test_v1_two_layer_parallel_plate_is_exact():
    width, d1, d2 = 2.0e-3, 0.3e-3, 0.7e-3
    eps1, eps2, tan1, tan2 = 2.0, 5.0, 0.01, 0.002
    d = Domain(size=0.15e-3)
    d.add_region("a", rectangle(0, 0, width, d1))
    d.add_region("b", rectangle(0, d1, width, d1 + d2))
    mesh = from_mesher(generate(d, "outer"))
    y = mesh.nodes[:, 1]
    top = np.flatnonzero(np.isclose(y, d1 + d2, rtol=0, atol=1e-12))
    bottom = np.flatnonzero(np.isclose(y, 0.0, rtol=0, atol=1e-12))
    names = mesh.region_names
    eps_r = np.array([eps1 if names[r] == "a" else eps2 for r in mesh.regions])
    tan = np.array([tan1 if names[r] == "a" else tan2 for r in mesh.regions])

    p = line_parameters(mesh, eps_r, {"plate": top}, bottom, tan_delta=tan)
    e1, e2 = eps1 * (1 - 1j * tan1), eps2 * (1 - 1j * tan2)
    exact = epsilon_0 * width / (d1 / e1 + d2 / e2)
    exact0 = epsilon_0 * width / (d1 + d2)
    assert p.C[0, 0] == pytest.approx(exact.real, rel=1e-9)
    assert p.C_loss[0, 0] == pytest.approx(-exact.imag, rel=1e-9)
    assert p.C0[0, 0] == pytest.approx(exact0, rel=1e-9)
    assert p.eps_eff == pytest.approx(exact.real / exact0, rel=1e-9)
    assert p.G(1e9)[0, 0] == pytest.approx(2 * np.pi * 1e9 * -exact.imag, rel=1e-9)
    assert p.L[0, 0] == pytest.approx(mu_0 * (d1 + d2) / width, rel=1e-9)


def _coax(a, b, size):
    d = Domain(size=size)
    d.add_region("dielectric", Circle((0.0, 0.0), b, n=64), holes=[Circle((0.0, 0.0), a, n=32)])
    mesh = from_mesher(generate(d, lambda mid: "inner" if np.hypot(*mid) < 0.5 * (a + b) else "outer"))
    return mesh


def test_v2_coax_converges_to_exact_capacitance():
    a, b, eps_r = 0.5e-3, 1.5e-3, 2.2
    c_exact = 2 * np.pi * epsilon_0 * eps_r / np.log(b / a)
    z_exact = ETA0 / (2 * np.pi * np.sqrt(eps_r)) * np.log(b / a)
    errors, sizes = [], []
    for size in (0.2e-3, 0.1e-3, 0.05e-3):
        mesh = _coax(a, b, size)
        p = line_parameters(mesh, eps_r, {"inner": mesh.boundary["inner"]}, mesh.boundary["outer"])
        errors.append(abs(p.C[0, 0] / c_exact - 1))
        sizes.append(size)
        assert p.eps_eff == pytest.approx(eps_r, rel=1e-12)
    assert errors[-1] <= 1e-3
    assert abs(p.z0 / z_exact - 1) <= 1e-3
    order = np.polyfit(np.log(sizes), np.log(errors), 1)[0]
    assert order >= 1.5


def _stripline(w, b, eps_r, traces=None, width_factor=12.0):
    traces = traces or [Trace("s", 0.0, w, b / 2)]
    return CrossSection([Layer("lower", b / 2, eps_r), Layer("upper", b / 2, eps_r)],
                        traces, width=width_factor * b, bottom="ground", top="ground")


def test_v3_stripline_matches_cohn_and_improves_with_refinement():
    w, b, eps_r = 0.5e-3, 1.0e-3, 4.0
    exact = stripline_z0(w, b, eps_r)
    cs = _stripline(w, b, eps_r)
    errors = []
    for s in (1, 2, 4):
        p = cs.analyze(edge_size=8e-6 / s ** 2, grade=0.3 / s, far_size=b / (4 * s))
        errors.append(abs(p.z0 / exact - 1))
        assert p.eps_eff == pytest.approx(eps_r, rel=1e-12)
    assert errors[-1] <= 5e-3
    assert errors[0] > errors[1] > errors[2]


def test_v4_coupled_stripline_matches_cohn_even_odd():
    w, s, b, eps_r = 0.4e-3, 0.3e-3, 1.0e-3, 3.5
    traces = [Trace("p", -(w + s) / 2, w, b / 2), Trace("n", (w + s) / 2, w, b / 2)]
    p = _stripline(w, b, eps_r, traces).analyze(edge_size=2e-6, grade=0.15, far_size=b / 8)
    z_even, z_odd = coupled_stripline_z(w, s, b, eps_r)
    eo = p.even_odd()
    assert eo["z_even"] == pytest.approx(z_even, rel=5e-3)
    assert eo["z_odd"] == pytest.approx(z_odd, rel=5e-3)
    assert eo["z_diff"] == pytest.approx(2 * z_odd, rel=5e-3)
    assert eo["eps_eff_even"] == pytest.approx(eps_r, rel=1e-9)
    assert eo["eps_eff_odd"] == pytest.approx(eps_r, rel=1e-9)


@pytest.mark.parametrize("eps_r", [4.3, 9.8])
@pytest.mark.parametrize("u", [0.5, 1.0, 2.0])
def test_v5_microstrip_matches_hammerstad_jensen(u, eps_r):
    h = 1e-3
    z_ref, eps_ref = hammerstad_jensen(u, eps_r)
    results = {}
    for bc in ("open", "ground"):
        cs = CrossSection([Layer("substrate", h, eps_r), Layer("air", 20 * h)],
                          [Trace("s", 0.0, u * h, h)], width=40 * h, top=bc, sides=bc)
        results[bc] = cs.analyze(edge_size=u * h / 100, grade=0.15, far_size=2 * h)
        assert results[bc].z0 == pytest.approx(z_ref, rel=1e-2)
        assert results[bc].eps_eff == pytest.approx(eps_ref, rel=1e-2)
    # The two boundary closures bracket the open-space answer; their spread
    # is the truncation uncertainty of this box.
    assert abs(results["open"].z0 / results["ground"].z0 - 1) <= 1e-2
