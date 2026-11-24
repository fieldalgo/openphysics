# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Self integrals for the first two static wedge radial current branches.

Internal module, consistent units: not part of galerkin's public API (the ``__all__``
of its public modules).

These explicit primitives do not change an existing panel basis or solver.
"""
from functools import lru_cache
import math

from scipy.special import zeta

from .laplace_corner import length as _length, power as _power, frozen as _frozen
from .laplace_corner import power_panel_gram, power_panel_self_log

__all__ = ["power_panel_harmonic_gram", "power_panel_harmonic_self_log"]


@lru_cache(maxsize=1)
def _self_series_coefficients():
    # Expansion about p=1. Positive coefficients avoid cancellation of the
    # digamma difference when a nonzero cross moment is close to uniform.
    return tuple((2.0**k - 1.0) * float(zeta(k + 1, 2))
                 for k in range(1, 65))


def power_panel_harmonic_gram(length, exponent):
    """Immutable 2x2 squared-current Gram, with entries in inverse metres.

    For u=s/h, rho_a=a/h*u**(a-1), phi0=rho_p and
    phi1=sqrt(3)*(rho_(2p)-rho_p). Their masses are [1,0].
    Require finite positive h and p in (0.5,1] for square-integrable
    current. The second mode is a static wedge branch, not a frequency
    harmonic. At p=1 it equals the zero-mean linear density.
    """
    h, p = _length(length), _power(exponent)
    zero = power_panel_gram(h, p)
    cross = zero * (math.sqrt(3) * (p - 1) / (3*p - 1))
    diagonal = zero * (3*(4*p*p - 3*p + 1) / ((4*p - 1)*(3*p - 1)))
    if (not all(map(math.isfinite, (zero, cross, diagonal)))
            or min(zero, diagonal) <= 0 or (p != 1 and cross == 0)):
        raise ValueError("harmonic squared-current Gram is not representable")
    return _frozen([[zero, cross], [cross, diagonal]]).reshape(2, 2)


def power_panel_harmonic_self_log(length, exponent):
    """Immutable self log-distance block for the static harmonic basis.

    Use the phi0/phi1 and ordering of power_panel_harmonic_gram.
    The kernel is log(|s-t| / 1 metre); entries are dimensionless.
    Only entry00 changes under uniform length scaling. Evaluate the
    analytically cancelled cross and 11 moments using 64 positive series
    terms. On p in (0.5,1], the omitted scalar series is below 8.14e-20.
    No small nonzero cross moment is rounded to zero deliberately.
    Interactions, field solving and boundary-error estimates are separate.
    """
    h, p = _length(length), _power(exponent)
    zero = power_panel_self_log(h, p)
    delta = 1 - p
    moment = delta * math.fsum(c * delta**k for k, c
                              in enumerate(_self_series_coefficients()))
    cross, diagonal = moment / math.sqrt(3), moment - .75/p
    if (not all(map(math.isfinite, (zero, cross, diagonal)))
            or (p != 1 and cross == 0)):
        raise ValueError("harmonic self log integral is not representable")
    return _frozen([[zero, cross], [cross, diagonal]]).reshape(2, 2)
