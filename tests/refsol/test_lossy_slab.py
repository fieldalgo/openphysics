# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Self-checks of the complex-permittivity slab reference.

Independent physics used here: the lossless ``refsol.slab`` roots and TE
profile, first-order material perturbation theory (Snyder & Love 1983, ch. 18:
``delta beta = omega eps0 int delta_eps |E|^2 dx / (4 P)``), interface and
layer equations by finite differences, and the exponential dependence of the
leakage rate on the tunnelling distance.
"""

import math

import numpy as np
import pytest
from scipy.integrate import quad

from refsol import lossy_slab as ls, slab

WL = 1.55
K0 = 2 * math.pi / WL
SOI = dict(n_f=3.48, n_s=1.444, n_c=1.444, d=0.22, wavelength=WL)
THICK = dict(n_f=1.5, n_s=1.0, n_c=1.2, d=5.0, wavelength=1.0)          # several modes, asymmetric


def three_layer_eps(n_f, n_s, n_c):
    return np.array([complex(n_s) ** 2, complex(n_f) ** 2, complex(n_c) ** 2])


@pytest.mark.parametrize("case", [SOI, THICK])
@pytest.mark.parametrize("pol", ["TE", "TM"])
def test_lossless_limit_equals_the_real_slab_reference(case, pol):
    expected = slab.modes(case["n_f"], case["n_s"], case["n_c"], case["d"], case["wavelength"], pol)
    got = ls.three_layer_modes(pol=pol, **case)
    assert len(got) == len(expected) >= 1
    for g, e in zip(got, expected):
        assert g.imag == 0 and abs(g.real - e) <= 1e-13 * e
    # the characteristic function vanishes at the atan-equation roots, which brentq
    # located to xtol = 1e-14: |F| is bounded by |F'| * 1e-14 with |F'| ~ k0 d
    eps = three_layer_eps(case["n_f"], case["n_s"], case["n_c"])
    k0d = 2 * math.pi * case["d"] / case["wavelength"]
    for e in expected:
        assert abs(ls.characteristic(e, eps, [case["d"]], case["wavelength"], pol)) < 1e-13 * k0d


@pytest.mark.parametrize("case", [SOI, THICK])
@pytest.mark.parametrize("pol", ["TE", "TM"])
@pytest.mark.parametrize("where", ["film", "substrate", "all"])
def test_lossy_roots_have_small_residual_and_passive_sign(case, pol, where):
    loss = {"film": (0.02, 0, 0), "substrate": (0, 0.01, 0), "all": (0.02, 0.01, 0.005)}[where]
    n_f, n_s, n_c = (complex(n, -k) for n, k in zip((case["n_f"], case["n_s"], case["n_c"]), loss))
    got = ls.three_layer_modes(n_f, n_s, n_c, case["d"], case["wavelength"], pol)
    lossless = slab.modes(case["n_f"], case["n_s"], case["n_c"], case["d"], case["wavelength"], pol)
    assert len(got) == len(lossless)
    eps = three_layer_eps(n_f, n_s, n_c)
    k0d = 2 * math.pi * case["d"] / case["wavelength"]
    for n in got:
        assert n.imag < 0
        # |F| is O(k0 d) in size for a thick slab; the normalized residual is scale-free
        assert abs(ls.characteristic(n, eps, [case["d"]], case["wavelength"], pol)) <= 1e-12 * max(1.0, k0d)
        assert ls.residual(n, eps, [case["d"]], case["wavelength"], pol) <= 1e-12
    # a far-off guess converges to the same root
    again = ls.solve(eps, [case["d"]], case["wavelength"], got[0] + 0.01 + 0.002j, pol)
    assert abs(again - got[0]) < 1e-12


def test_more_loss_gives_more_attenuation_and_continuation_is_consistent():
    values = [ls.three_layer_modes(3.48 - 1j * k, 1.444, 1.444, 0.22, WL, "TE")[0] for k in (1e-3, 1e-2, 5e-2)]
    assert values[0].imag > values[1].imag > values[2].imag
    # more steps along the path land on the same root
    fine = ls.three_layer_modes(3.48 - 0.05j, 1.444, 1.444, 0.22, WL, "TE", steps=40)[0]
    assert abs(fine - values[2]) < 1e-12


def te_confinement(neff, eps_real, d, wavelength, layer):
    """Fraction of int |E_y|^2 inside one layer of the lossless slab, from refsol.slab."""
    n_s, n_f, n_c = np.sqrt(eps_real)
    profile = lambda x: slab.field_te(np.array([x]), neff, n_f, n_s, n_c, d, wavelength)[0] ** 2
    k0 = 2 * math.pi / wavelength
    far = 40 / (k0 * math.sqrt(neff**2 - max(n_s, n_c) ** 2))
    parts = [quad(profile, -d / 2 - far, -d / 2, epsabs=0, epsrel=1e-12)[0],
             quad(profile, -d / 2, d / 2, epsabs=0, epsrel=1e-12)[0],
             quad(profile, d / 2, d / 2 + far, epsabs=0, epsrel=1e-12)[0]]
    return parts[layer] / sum(parts)


@pytest.mark.parametrize("layer", [1, 0])
def test_te_small_loss_matches_first_order_perturbation(layer):
    # delta n_eff = Gamma_layer * delta eps / (2 n_eff) with Gamma the TE confinement factor;
    # Im n_eff is first-order accurate, so its relative error must shrink quadratically.
    n_f, n_s, n_c, d = 2.0, 1.5, 1.0, 1.0
    eps_real = three_layer_eps(n_f, n_s, n_c).real
    n0 = slab.modes(n_f, n_s, n_c, d, 1.0, "TE")[0]
    gamma = te_confinement(n0, eps_real, d, 1.0, layer)
    errors = []
    for kappa in (1e-3, 1e-4):
        indices = [n_s, n_f, n_c]
        indices[layer] = complex(indices[layer], -kappa)
        n = ls.three_layer_modes(indices[1], indices[0], indices[2], d, 1.0, "TE")[0]
        delta_eps = indices[layer] ** 2 - indices[layer].real ** 2
        predicted = gamma * delta_eps.imag / (2 * n0)
        errors.append(abs(n.imag / predicted - 1))
    assert errors[0] < 1e-5
    assert errors[0] / errors[1] > 30          # second order: expected about 100


def tm_perturbation(neff, eps, d, wavelength, delta_eps):
    """First-order delta n_eff for a TM mode from the lossless H_y profile:
    int delta_eps (n^2 |H|^2 + |H'/k0|^2) / eps^2 dx / (2 n int |H|^2 / eps dx)."""
    k0 = 2 * math.pi / wavelength
    far = 40 / (k0 * math.sqrt(neff**2 - max(eps[0], eps[2])))
    limits = [(-far, 0.0), (0.0, d), (d, d + far)]
    numerator = denominator = 0.0

    def h(x):
        return ls.field(np.array([x]), neff, eps, [d], wavelength, "TM")[0].real

    def dh(x):
        # Richardson-extrapolated central difference that never crosses an interface
        step = min(1e-4, 0.5 * min(abs(x), abs(x - d)))
        if step == 0:
            return 0.0
        coarse = (h(x + step) - h(x - step)) / (2 * step)
        fine = (h(x + step / 2) - h(x - step / 2)) / step
        return (4 * fine - coarse) / 3

    for j, (a, b) in enumerate(limits):
        energy = quad(lambda x: (neff**2 * h(x) ** 2 + (dh(x) / k0) ** 2) / eps[j] ** 2,
                      a, b, epsabs=0, epsrel=1e-11, limit=400)[0]
        numerator += delta_eps[j] * energy
        denominator += quad(lambda x: h(x) ** 2, a, b, epsabs=0, epsrel=1e-11, limit=400)[0] / eps[j]
    return numerator / (2 * neff * denominator)


def test_tm_small_loss_matches_first_order_perturbation():
    n_f, n_s, n_c, d = 2.0, 1.5, 1.0, 1.0
    eps = three_layer_eps(n_f, n_s, n_c).real
    n0 = slab.modes(n_f, n_s, n_c, d, 1.0, "TM")[0]
    errors = []
    for kappa in (1e-3, 1e-4):
        nf = complex(n_f, -kappa)
        n = ls.three_layer_modes(nf, n_s, n_c, d, 1.0, "TM")[0]
        delta = np.array([0.0, nf**2 - n_f**2, 0.0])
        predicted = tm_perturbation(n0, eps, d, 1.0, delta)
        errors.append(abs(n.imag / predicted.imag - 1))
    assert errors[0] < 1e-5
    assert errors[0] / errors[1] > 30          # second order: expected about 100


@pytest.mark.parametrize("pol", ["TE", "TM"])
def test_field_satisfies_interface_and_layer_equations(pol):
    n_f, n_s, n_c, d = 3.48 - 0.01j, 1.444 - 0.002j, 1.0, 0.22
    eps = three_layer_eps(n_f, n_s, n_c)
    n = ls.three_layer_modes(n_f, n_s, n_c, d, WL, pol)[0]
    w = np.ones(3) if pol == "TE" else eps
    h = 1e-7
    for face, (jl, jr) in ((0.0, (0, 1)), (d, (1, 2))):
        left = ls.field(np.array([face - h, face - 2 * h, face - 3 * h]), n, eps, [d], WL, pol)
        right = ls.field(np.array([face + h, face + 2 * h, face + 3 * h]), n, eps, [d], WL, pol)
        phi_l = 3 * left[0] - 3 * left[1] + left[2]           # quadratic extrapolation to the face
        phi_r = 3 * right[0] - 3 * right[1] + right[2]
        assert abs(phi_l - phi_r) < 1e-9 * abs(phi_r)
        dl = -(3 * left[0] - 4 * left[1] + left[2]) / (2 * h)
        dr = (3 * right[0] - 4 * right[1] + right[2]) / (2 * h)
        assert abs(dl / w[jl] - dr / w[jr]) < 1e-5 * max(abs(dr / w[jr]), 1.0)
    # phi'' + k0^2 (eps - n^2) phi = 0 inside every region
    for j, x0 in ((0, -0.3), (1, 0.1), (2, 0.5)):
        step = 1e-4
        phi = ls.field(np.array([x0 - step, x0, x0 + step]), n, eps, [d], WL, pol)
        second = (phi[0] - 2 * phi[1] + phi[2]) / step**2
        assert abs(second + K0**2 * (eps[j] - n * n) * phi[1]) < 1e-5 * abs(K0**2 * phi[1])
    # bound: both exterior fields decay away from the film
    far = ls.field(np.array([-0.5, -1.0, d + 0.5, d + 1.0]), n, eps, [d], WL, pol)
    assert abs(far[1]) < abs(far[0]) and abs(far[3]) < abs(far[2])


LEAKY = dict(n_f=3.48, n_gap=1.444, n_sub=3.48, d=0.22, wavelength=WL)


@pytest.mark.parametrize("pol", ["TE", "TM"])
def test_leaky_mode_radiates_into_the_substrate(pol):
    gap = 0.25
    n = ls.substrate_leaky_mode(gap=gap, pol=pol, **LEAKY)
    eps = np.array([1.444**2, 3.48**2, 1.444**2, 3.48**2])
    branches = ("decay", "outgoing")
    assert n.imag < 0
    assert abs(ls.characteristic(n, eps, [0.22, gap], WL, pol, branches)) <= 1e-12
    assert ls.residual(n, eps, [0.22, gap], WL, pol, branches) <= 1e-12
    bound = slab.modes(3.48, 1.444, 1.444, 0.22, WL, pol)[0]
    assert abs(n.real - bound) < 0.02
    # outgoing branch: Re Q_sub > 0 and, for an attenuated mode, Im Q_sub > 0 (growing improper field)
    q = ls.exterior_root(eps[-1], n, "outgoing")
    assert q.real > 0 and q.imag > 0
    x = 0.22 + gap + np.array([0.0, 1.0, 2.0])
    magnitude = abs(ls.field(x, n, eps, [0.22, gap], WL, pol, branches))
    assert magnitude[0] < magnitude[1] < magnitude[2]
    cover = abs(ls.field(np.array([-0.5, -1.0]), n, eps, [0.22, gap], WL, pol, branches))
    assert cover[1] < cover[0]


def test_leakage_rate_decays_exponentially_with_the_tunnelling_distance():
    # Through a thick low-index gap the leakage scales as exp(-2 k0 gamma gap), gamma the
    # bound mode's evanescent decay rate (WKB tunnelling, Hu & Menyuk 2009 sec. 4).
    bound = slab.modes(3.48, 1.444, 1.444, 0.22, WL, "TE")[0]
    gamma = math.sqrt(bound**2 - 1.444**2)
    gaps = np.array([0.5, 0.6, 0.7])
    loss = np.array([-ls.substrate_leaky_mode(gap=g, pol="TE", **LEAKY).imag for g in gaps])
    assert np.all(loss > 0) and loss[0] > loss[1] > loss[2]
    slopes = np.diff(np.log(loss)) / np.diff(gaps)
    np.testing.assert_allclose(slopes, -2 * K0 * gamma, rtol=0.03)


def test_leaky_root_is_independent_of_the_continuation_path():
    coarse = ls.substrate_leaky_mode(gap=0.25, pol="TE", steps=6, **LEAKY)
    fine = ls.substrate_leaky_mode(gap=0.25, pol="TE", steps=30, **LEAKY)
    assert abs(coarse - fine) < 1e-12
    direct = ls.solve(np.array([1.444**2, 3.48**2, 1.444**2, 3.48**2]), [0.22, 0.25], WL,
                      coarse + 0.003 - 0.001j, "TE", ("decay", "outgoing"))
    assert abs(direct - coarse) < 1e-12


def test_invalid_inputs_are_refused():
    with pytest.raises(ValueError, match="Im <= 0"):
        ls.three_layer_modes(3.48 + 0.01j, 1.444, 1.444, 0.22, WL)
    with pytest.raises(ValueError, match="must guide"):
        ls.three_layer_modes(1.4, 1.444, 1.444, 0.22, WL)
    with pytest.raises(ValueError, match="branches"):
        ls.characteristic(2.8, [1, 4, 1], [0.2], WL, "TE", ("decay", "inward"))
    with pytest.raises(ValueError, match="thickness"):
        ls.characteristic(2.8, [1, 4, 1], [0.2, 0.3], WL)
    with pytest.raises(ValueError, match="pol"):
        ls.characteristic(2.8, [1, 4, 1], [0.2], WL, "TEM")
    with pytest.raises(ValueError, match="exceed"):
        ls.substrate_leaky_mode(3.48, 1.444, 1.5, 0.22, 0.25, WL)
    with pytest.raises(RuntimeError, match="no root"):
        ls.solve([1.444**2, 3.48**2, 1.444**2], [0.22], WL, 5.0 + 3.0j, "TE", max_newton=0, tol=1e-300)
