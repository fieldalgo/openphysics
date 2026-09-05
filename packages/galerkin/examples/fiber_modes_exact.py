"""Exact full-vector modes of a step-index circular fiber — the M3a reference.

Physics
-------
A step-index fiber is the only 2D dielectric waveguide whose *vector* modes are
known in closed form, which makes it the analytical gate for M3a. Core radius a,
index n_co for r < a, n_cl for r > a (cladding infinite). Modes vary as
exp(i(l phi + beta z - omega t)).

Because the interface is curved, E_z and H_z do not decouple: matching all four
tangential components (E_z, H_z, E_phi, H_phi) at r = a couples them, and the
guided modes are *hybrid* (HE/EH). Only l = 0 decouples, into TE0m and TM0m.

Notation
--------
    U = a sqrt(n_co^2 k0^2 - beta^2)     transverse wavenumber in the core
    W = a sqrt(beta^2 - n_cl^2 k0^2)     transverse decay rate in the cladding
    V = k0 a sqrt(n_co^2 - n_cl^2)       normalized frequency, V^2 = U^2 + W^2
    n_eff = beta / k0,   b = (n_eff^2 - n_cl^2)/(n_co^2 - n_cl^2) = W^2/V^2

Characteristic equation (derived in the module docstring of the report):

  [ J_l'(U)/(U J_l(U)) + K_l'(W)/(W K_l(W)) ]
  [ n_co^2 J_l'(U)/(U J_l(U)) + n_cl^2 K_l'(W)/(W K_l(W)) ]
      = l^2 (1/U^2 + 1/W^2) (n_co^2/U^2 + n_cl^2/W^2)

with the l = 0 reductions (J_0' = -J_1, K_0' = -K_1)

  TE0m:  J_1(U)/(U J_0(U)) + K_1(W)/(W K_0(W)) = 0
  TM0m:  n_co^2 J_1(U)/(U J_0(U)) + n_cl^2 K_1(W)/(W K_0(W)) = 0

Numerics
--------
Two traps, both handled here:
  * J_l(U) has zeros in (0, V), so the log-derivative form has poles that a naive
    sign-change scan mistakes for roots. We multiply through by (U J_l(U))^2,
    which is pole-free and (checked below) introduces no spurious roots: at a
    zero of J_l the multiplied function equals n_co^2 J_l'(U)^2 (WK)^2 != 0.
  * K_l(W) and I_l(W) under/overflow. Every cladding quantity is used only as a
    logarithmic derivative and is evaluated through the exponentially scaled
    kve/ive, so nothing ever overflows.

The scan variable is b in (0, 1) rather than U, because b is exactly the guided
band: b -> 0 is cutoff, b -> 1 is deep confinement.
"""

from __future__ import annotations

import numpy as np
from scipy.optimize import brentq, toms748
from scipy.special import jv, jvp, ive, kve

__all__ = ["FiberModes", "solve_fiber", "solve_lp"]


# ----------------------------------------------------------------------------
# Scaled Bessel helpers: every cladding function is returned as a *ratio*
# f'(W)/f(W), so the exponential prefactors cancel and nothing overflows.
# ----------------------------------------------------------------------------

def _kve_d(l, x):
    """e^{x} K_l'(x) — from K_l' = -(K_{l-1} + K_{l+1})/2."""
    return -0.5 * (kve(l - 1, x) + kve(l + 1, x))


def _ive_d(l, x):
    """e^{-x} I_l'(x) — from I_l' = (I_{l-1} + I_{l+1})/2."""
    return 0.5 * (ive(l - 1, x) + ive(l + 1, x))


def _clad_logderiv(l, W, X=np.inf, kind="K"):
    """d/dx log f_l(x) at x = W, for the cladding radial function f_l.

    Infinite cladding (X = inf):      f_l = K_l.
    PEC wall at r = R  (X = W R / a):
        kind == "K":  f_l(x) = K_l(x) I_l(X)  - I_l(x) K_l(X)     -> f(X) = 0
        kind == "I":  f_l(x) = K_l(x) I_l'(X) - I_l(x) K_l'(X)    -> f'(X) = 0
    The first is the E_z branch (PEC forces E_z(R) = 0), the second the H_z
    branch (PEC forces E_phi(R) = 0 which, given E_z(R) = 0, is h'(R) = 0).
    """
    if not np.isfinite(X):
        return _kve_d(l, W) / kve(l, W)
    # tau = e^{2(W - X)} <= 1 folds the growing I_l branch in without overflow.
    tau = np.exp(2.0 * (W - X))
    cX = ive(l, X) if kind == "K" else _ive_d(l, X)
    dX = kve(l, X) if kind == "K" else _kve_d(l, X)
    num = _kve_d(l, W) * cX - tau * _ive_d(l, W) * dX
    den = kve(l, W) * cX - tau * ive(l, W) * dX
    return num / den


# ----------------------------------------------------------------------------
# Characteristic functions
# ----------------------------------------------------------------------------

def _char_vector(b, V, l, n_co, n_cl, R_over_a=np.inf):
    """Pole-free hybrid characteristic function; zero <=> guided mode.

    Equals the log-derivative equation multiplied by (U J_l(U))^2.
    """
    b = np.asarray(b, dtype=float)
    W = V * np.sqrt(b)
    U = V * np.sqrt(1.0 - b)
    X = np.inf if not np.isfinite(R_over_a) else W * R_over_a

    aJ = jvp(l, U, 1)          # J_l'(U)
    bJ = U * jv(l, U)          # U J_l(U)   (vanishes at the poles)

    RH = _clad_logderiv(l, W, X, "I") / W      # H_z branch  (E_phi matching)
    RF = _clad_logderiv(l, W, X, "K") / W      # E_z branch  (H_phi matching)

    rhs = (l ** 2) * (1.0 / U ** 2 + 1.0 / W ** 2) \
        * (n_co ** 2 / U ** 2 + n_cl ** 2 / W ** 2)
    return (aJ + RH * bJ) * (n_co ** 2 * aJ + n_cl ** 2 * RF * bJ) - rhs * bJ ** 2


def _char_te(b, V, n_co, n_cl, R_over_a=np.inf):
    """TE0m: J_l'/(U J_l) + K_l'/(W K_l) = 0, multiplied by U J_0(U)."""
    W, U = V * np.sqrt(b), V * np.sqrt(1.0 - b)
    X = np.inf if not np.isfinite(R_over_a) else W * R_over_a
    return jvp(0, U, 1) + _clad_logderiv(0, W, X, "I") / W * (U * jv(0, U))


def _char_tm(b, V, n_co, n_cl, R_over_a=np.inf):
    """TM0m: n_co^2 J_l'/(U J_l) + n_cl^2 K_l'/(W K_l) = 0, x U J_0(U)."""
    W, U = V * np.sqrt(b), V * np.sqrt(1.0 - b)
    X = np.inf if not np.isfinite(R_over_a) else W * R_over_a
    return (n_co ** 2 * jvp(0, U, 1)
            + n_cl ** 2 * _clad_logderiv(0, W, X, "K") / W * (U * jv(0, U)))


def _char_lp(b, V, l):
    """Weakly-guiding scalar LP_lm: U J_{l-1}(U)/J_l(U) + W K_{l-1}(W)/K_l(W) = 0.

    Multiplied by J_l(U) to remove the poles; K ratio via kve (no overflow).
    """
    W, U = V * np.sqrt(b), V * np.sqrt(1.0 - b)
    return U * jv(l - 1, U) + W * (kve(l - 1, W) / kve(l, W)) * jv(l, U)


# ----------------------------------------------------------------------------
# Bracketing + polishing
# ----------------------------------------------------------------------------

def _roots_in_b(f, n_scan=200001, lo=1e-12, hi=1.0 - 1e-13, polish="brentq"):
    """All sign-change roots of f on b in (lo, hi).

    A uniform scan is safe here: the multiplied characteristic functions are
    smooth on (0,1) and each guided mode of a given (l, family) is separated by
    O(1) in b for the V we care about. n_scan is set far above the mode count.
    """
    bs = np.linspace(lo, hi, n_scan)
    with np.errstate(all="ignore"):
        fs = np.asarray([f(x) for x in bs], dtype=float) if not _vectorizable(f) \
            else np.asarray(f(bs), dtype=float)
    ok = np.isfinite(fs)
    idx = np.where(ok[:-1] & ok[1:] & (np.sign(fs[:-1]) * np.sign(fs[1:]) < 0))[0]
    out = []
    for i in idx:
        a_, b_ = bs[i], bs[i + 1]
        if polish == "brentq":
            r = brentq(f, a_, b_, xtol=1e-16, rtol=8.9e-16, maxiter=200)
        else:
            r = toms748(f, a_, b_, xtol=1e-16, rtol=8.9e-16, maxiter=200)
        out.append(r)
    return np.array(out)


def _vectorizable(f):
    try:
        v = f(np.array([0.3, 0.4]))
        return np.ndim(v) == 1
    except Exception:
        return False


# ----------------------------------------------------------------------------
# Public API
# ----------------------------------------------------------------------------

class FiberModes:
    """Step-index fiber; all quantities in the same length unit as a, wl."""

    def __init__(self, a, n_co, n_cl, wl):
        self.a, self.n_co, self.n_cl, self.wl = a, n_co, n_cl, wl
        self.k0 = 2.0 * np.pi / wl
        self.NA = np.sqrt(n_co ** 2 - n_cl ** 2)
        self.V = self.k0 * a * self.NA
        self.Delta = (n_co ** 2 - n_cl ** 2) / (2.0 * n_co ** 2)

    def neff(self, b):
        return np.sqrt(self.n_cl ** 2 + b * (self.n_co ** 2 - self.n_cl ** 2))

    # -- vector modes ------------------------------------------------------
    def vector_modes(self, l_max=6, R_over_a=np.inf, polish="brentq"):
        """[(label, l, b, n_eff)] sorted by decreasing n_eff."""
        V, nc, ncl = self.V, self.n_co, self.n_cl
        out = []
        # l = 0: the two decoupled families
        for fam, f in (("TE", _char_te), ("TM", _char_tm)):
            for m, b in enumerate(
                    _roots_in_b(lambda x, f=f: f(x, V, nc, ncl, R_over_a),
                                polish=polish), start=1):
                out.append((f"{fam}0{m}", 0, b, self.neff(b)))
        # l >= 1: hybrid HE/EH, classified below
        for l in range(1, l_max + 1):
            rts = _roots_in_b(
                lambda x, l=l: _char_vector(x, V, l, nc, ncl, R_over_a),
                polish=polish)
            if len(rts) == 0:
                continue
            fams = [self._classify(l, b, R_over_a) for b in rts]
            # index m within each family, counting from the most confined root
            cnt = {"HE": 0, "EH": 0}
            lab = [None] * len(rts)
            for i in np.argsort(-rts):          # decreasing b == increasing m
                cnt[fams[i]] += 1
                lab[i] = f"{fams[i]}{l}{cnt[fams[i]]}"
            for L, b in zip(lab, rts):
                out.append((L, l, b, self.neff(b)))
        out.sort(key=lambda t: -t[3])
        return out

    def _classify(self, l, b, R_over_a=np.inf):
        """HE vs EH from the sign of the E_z/H_z amplitude ratio at the root.

        From the E_phi matching row,
            A/B = -(omega mu0 / (beta l)) [ Jl'/(U Jl) + Kl'/(W Kl) ] / (1/U^2+1/W^2)
        HE ("magnetic-like", H_z dominant) has the transverse field rotating with
        the same handedness as an l-1 scalar mode; the standard discriminant is
        the sign of that bracket: negative -> HE, positive -> EH.
        """
        V = self.V
        W, U = V * np.sqrt(b), V * np.sqrt(1.0 - b)
        X = np.inf if not np.isfinite(R_over_a) else W * R_over_a
        s = jvp(l, U, 1) / (U * jv(l, U)) + _clad_logderiv(l, W, X, "I") / W
        return "HE" if s < 0 else "EH"

    # -- scalar LP comparison ---------------------------------------------
    def lp_modes(self, l_max=6):
        out = []
        for l in range(0, l_max + 1):
            for m, b in enumerate(
                    _roots_in_b(lambda x, l=l: _char_lp(x, self.V, l)), start=1):
                out.append((f"LP{l}{m}", l, b, self.neff(b)))
        out.sort(key=lambda t: -t[3])
        return out


def solve_fiber(a, n_co, n_cl, wl, **kw):
    return FiberModes(a, n_co, n_cl, wl).vector_modes(**kw)


def solve_lp(a, n_co, n_cl, wl, **kw):
    return FiberModes(a, n_co, n_cl, wl).lp_modes(**kw)


# ----------------------------------------------------------------------------
if __name__ == "__main__":
    np.set_printoptions(precision=12)
    F = FiberModes(a=0.8, n_co=1.45, n_cl=1.0, wl=1.55)
    print(f"a={F.a} um  n_co={F.n_co}  n_cl={F.n_cl}  lambda={F.wl} um")
    print(f"NA={F.NA:.6f}  V={F.V:.9f}  Delta={F.Delta:.6f}")
    print(f"{'mode':8s} {'l':>2s} {'b':>18s} {'n_eff':>18s} {'U':>14s} {'W':>14s}")
    for lab, l, b, ne in F.vector_modes():
        print(f"{lab:8s} {l:2d} {b:18.12f} {ne:18.12f} "
              f"{F.V*np.sqrt(1-b):14.9f} {F.V*np.sqrt(b):14.9f}")
    print()
    for lab, l, b, ne in F.lp_modes():
        print(f"{lab:8s} {l:2d} {b:18.12f} {ne:18.12f}")
