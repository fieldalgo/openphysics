# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Fit measured n,k data to a Drude-Lorentz model.

Time-domain solvers and broadband frequency sweeps need permittivity as a sum
of a few poles rather than a table. ``fit_drude_lorentz`` finds Rakic-form
parameters (eps_inf, wp, f0, G0, (f_j, w_j, G_j)...) that reproduce eps(w)
over the sampled range. Positivity of every damping and oscillator strength
is enforced through bounds, so the result is causal and passive by
construction (Im eps >= 0 for exp(-i w t)).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.optimize import least_squares

from .dispersion import Dispersion, DrudeLorentz, um_to_ev


@dataclass
class FitResult:
    model: DrudeLorentz
    rms_eps: float          # rms error of complex eps over the fitted samples
    max_rel_index: float    # max relative error of the complex index |dn~| / |n~|
    n_samples: int


def fit_drude_lorentz(source: Dispersion, wavelength_um: np.ndarray, n_lorentz: int = 2,
                      eps_inf: float | None = None, drude: bool = True, seed: int = 0,
                      restarts: int = 8) -> FitResult:
    """Fit ``source`` (any Dispersion, typically Tabulated) sampled at ``wavelength_um``.

    n_lorentz : number of Lorentz oscillators
    drude     : include the free-electron (Drude) term — True for metals
    eps_inf   : fix the high-frequency permittivity (default: fitted, >= 1)
    Several random restarts are tried; the best one is returned.
    """
    wl = np.asarray(wavelength_um, dtype=float)
    E = um_to_ev(wl)
    target = source.eps(wl, strict=False)
    scale = np.maximum(np.abs(target), 1.0)
    rng = np.random.default_rng(seed)
    Emin, Emax = E.min(), E.max()

    def unpack(x):
        p = np.empty(4 + 3 * n_lorentz)
        i = 0
        p[0] = eps_inf if eps_inf is not None else x[i]; i += eps_inf is None
        p[1] = x[i]; i += 1                     # wp
        if drude:
            p[2] = 1.0
            p[3] = x[i]; i += 1                 # G0
        else:
            p[2] = 0.0
            p[3] = 1.0
        p[4:] = x[i:]
        return p

    def resid(x):
        m = DrudeLorentz.from_parameters(unpack(x))
        d = (m.eps_of_energy(E) - target) / scale
        return np.concatenate([d.real, d.imag])

    best = None
    for r in range(restarts):
        x0, lo, hi = [], [], []
        if eps_inf is None:
            x0.append(1.0 + rng.uniform(0, 5)); lo.append(1.0); hi.append(50.0)
        x0.append(rng.uniform(1, 15)); lo.append(1e-3); hi.append(60.0)          # wp
        if drude:
            x0.append(rng.uniform(0.01, 0.5)); lo.append(1e-4); hi.append(10.0)  # G0
        for j in range(n_lorentz):
            x0 += [rng.uniform(0.01, 2.0), rng.uniform(Emin, Emax), rng.uniform(0.05, 2.0)]
            lo += [0.0, 0.2 * Emin, 1e-3]
            hi += [50.0, 3.0 * Emax, 20.0]
        try:
            sol = least_squares(resid, x0, bounds=(lo, hi), max_nfev=4000, xtol=1e-12, ftol=1e-12)
        except ValueError:
            continue
        if best is None or sol.cost < best.cost:
            best = sol
    if best is None:
        raise RuntimeError("fit failed")
    model = DrudeLorentz.from_parameters(unpack(best.x), range_um=(float(wl.min()), float(wl.max())),
                                         label=f"DL fit of {source.label or type(source).__name__}")
    eps_fit = model.eps(wl, strict=False)
    rms = float(np.sqrt(np.mean(np.abs(eps_fit - target) ** 2)))
    idx_t, idx_f = source.index(wl, strict=False), model.index(wl, strict=False)
    max_rel = float(np.max(np.abs(idx_f - idx_t) / np.abs(idx_t)))
    return FitResult(model, rms, max_rel, len(wl))
