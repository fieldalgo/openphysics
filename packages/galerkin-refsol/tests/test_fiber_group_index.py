# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""The implicit vector-fiber group index against independent root refinement.

The oracle (analytic partials of the dispersion residual) and the check
(Richardson-extrapolated central differences of separately refined roots) share
only the residual equation, not a derivative implementation.
"""

import numpy as np
import pytest

from refsol import fiber

A, N1, N2 = 4.0, 1.45, 1.44


def _root(label, wavelength, n1, n2):
    return next(md.neff for md in fiber.vector_modes(A, n1, n2, wavelength, l_max=3) if md.label == label)


def _refined_derivative(label, wavelength, materials):
    """Richardson extrapolation of central differences of refined roots."""
    def neff(wl):
        return _root(label, wl, *materials(wl)[:2])
    slopes = [(neff(wavelength + h) - neff(wavelength - h)) / (2 * h) for h in (4e-3, 2e-3)]
    return (4 * slopes[1] - slopes[0]) / 3


def _constant(wl):
    return N1, N2, 0.0, 0.0


def _sellmeier(wl):
    """Core 1 + 1.1 l^2/(l^2 - 0.01); cladding a fixed fraction of it."""
    n1 = np.sqrt(1 + 1.1 * wl ** 2 / (wl ** 2 - 0.01))
    dn1 = -1.1 * 0.01 * wl / (n1 * (wl ** 2 - 0.01) ** 2)
    return n1, 0.993 * n1, dn1, 0.993 * dn1


@pytest.mark.parametrize("family, l", [("TE", 0), ("TM", 0), ("HE", 1), ("HE", 2)])
def test_analytic_partials_match_central_differences_of_the_residual(family, l):
    args = dict(n=1.443, wavelength=1.55, n1=N1, n2=N2)
    _, partials = fiber._vector_residual_and_partials(family, l, a=A, **args)
    for name, value in partials.items():
        step = 1e-7 * args[name]
        plus, minus = dict(args), dict(args)
        plus[name] += step
        minus[name] -= step
        fd = (fiber._vector_residual_and_partials(family, l, a=A, **plus)[0]
              - fiber._vector_residual_and_partials(family, l, a=A, **minus)[0]) / (2 * step)
        assert value == pytest.approx(fd, rel=1e-6), name


@pytest.mark.parametrize("label", ["HE11", "TE01", "TM01", "HE21"])
@pytest.mark.parametrize("materials", [_constant, _sellmeier], ids=["constant", "sellmeier"])
def test_group_index_matches_independent_root_refinement(label, materials):
    wl = 1.55
    n1, n2, dn1, dn2 = materials(wl)
    neff, ng = fiber.vector_group_index(A, n1, n2, wl, label, dn1, dn2)
    assert neff == pytest.approx(_root(label, wl, n1, n2), abs=1e-14)
    assert ng == pytest.approx(neff - wl * _refined_derivative(label, wl, materials), abs=1e-9)


def test_te01_tm01_he21_group_indices_are_distinct():
    """Physically split families keep distinct group indices (not one LP11 value)."""
    values = [fiber.vector_group_index(A, N1, N2, 1.55, label)[1] for label in ("TE01", "TM01", "HE21")]
    assert min(abs(x - y) for i, x in enumerate(values) for y in values[i + 1:]) > 1e-6


def test_material_dispersion_raises_the_group_index():
    n1, n2, dn1, dn2 = _sellmeier(1.55)
    plain = fiber.vector_group_index(A, n1, n2, 1.55, "HE11")[1]
    dispersive = fiber.vector_group_index(A, n1, n2, 1.55, "HE11", dn1, dn2)[1]
    assert dispersive > plain


def test_scale_invariance_of_the_nondispersive_group_index():
    """n_eff depends only on a/lambda, so scaling both leaves n_g unchanged."""
    one = fiber.vector_group_index(A, N1, N2, 1.55, "HE11")
    other = fiber.vector_group_index(A * 1e3, N1, N2, 1.55e3, "HE11")
    np.testing.assert_allclose(other, one, rtol=1e-12)


def test_refuses_unguided_and_near_cutoff_modes():
    with pytest.raises(ValueError, match="not guided"):
        fiber.vector_group_index(A, N1, N2, 1.55, "EH11")
    # TE01 cuts off at the first zero of J0, V = 2.40483; place V just above it.
    wl = 2 * np.pi * A * np.sqrt(N1 ** 2 - N2 ** 2) / 2.40484
    with pytest.raises(ValueError, match="cutoff|not guided"):
        fiber.vector_group_index(A, N1, N2, wl, "TE01")
