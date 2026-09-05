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

__all__ = ["FiberModes", "solve_fiber", "solve_lp", "cutoff_V"]


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
    W = np.asarray(W, dtype=float)
    X = np.asarray(X, dtype=float)
    inf_res = _kve_d(l, W) / kve(l, W)
    fin = np.isfinite(X)
    if not np.any(fin):
        return inf_res
    # tau = e^{2(W - X)} <= 1 folds the growing I_l branch in without overflow.
    Xs = np.where(fin, X, W + 1.0)      # dummy keeps the arithmetic finite
    tau = np.exp(2.0 * (W - Xs))
    cX = ive(l, Xs) if kind == "K" else _ive_d(l, Xs)
    dX = kve(l, Xs) if kind == "K" else _kve_d(l, Xs)
    num = _kve_d(l, W) * cX - tau * _ive_d(l, W) * dX
    den = kve(l, W) * cX - tau * ive(l, W) * dX
    return np.where(fin, num / den, inf_res)


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

def _scan_grid(n_lin=40001, n_log=4000, lo=1e-13, hi=1.0 - 1e-14):
    """Composite bracketing grid on b in (0, 1).

    Uniform in the bulk, geometric towards both endpoints: modes crowd towards
    b -> 0 just above cutoff and towards b -> 1 deep in the guided regime, and a
    purely uniform grid can merge two sign changes into one interval there.
    """
    return np.unique(np.concatenate([
        np.geomspace(lo, 1e-3, n_log),
        np.linspace(1e-3, 1.0 - 1e-3, n_lin),
        1.0 - np.geomspace(1e-14, 1e-3, n_log)[::-1],
        [hi]]))


def _roots_in_b(f, grid=None, polish="brentq"):
    """All sign-change roots of f on b in (0, 1).

    The multiplied characteristic functions are pole-free on (0, 1), so every
    sign change is a genuine mode; the grid's only job is to separate
    neighbouring modes into brackets.
    """
    bs = _scan_grid() if grid is None else grid
    with np.errstate(all="ignore"):
        fs = np.asarray(f(bs), dtype=float) if _vectorizable(f) \
            else np.asarray([f(x) for x in bs], dtype=float)
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
        # l = 0: the two decoupled families. m counts from the MOST confined
        # root downwards (m = 1 is the largest b), the standard convention.
        for fam, f in (("TE", _char_te), ("TM", _char_tm)):
            rts = _roots_in_b(lambda x, f=f: f(x, V, nc, ncl, R_over_a),
                              polish=polish)
            for m, b in enumerate(np.sort(rts)[::-1], start=1):
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

    # -- PEC-truncated domain ---------------------------------------------
    def mode_truncated(self, family, l, b_inf, R_over_a, span=0.25):
        """n_eff of the same mode when the cladding is cut off by a PEC wall at R.

        Solves the *same* characteristic equation with the cladding radial
        function replaced by the exact PEC-terminated combination, so this is
        the number a FEM computation on a disc of radius R converges to — the
        truncation error is isolated from the discretization error.
        Bracketed around the infinite-cladding root, expanding until it brackets.
        """
        V, nc, ncl = self.V, self.n_co, self.n_cl
        if family == "TE":
            f = lambda x: _char_te(x, V, nc, ncl, R_over_a)
        elif family == "TM":
            f = lambda x: _char_tm(x, V, nc, ncl, R_over_a)
        else:
            f = lambda x: _char_vector(x, V, l, nc, ncl, R_over_a)
        d = 1e-9
        while d < span:
            lo, hi = max(b_inf - d, 1e-12), min(b_inf + d, 1 - 1e-13)
            with np.errstate(all="ignore"):
                flo, fhi = f(lo), f(hi)
            if np.isfinite(flo) and np.isfinite(fhi) and flo * fhi < 0:
                b = brentq(f, lo, hi, xtol=1e-16, rtol=8.9e-16, maxiter=200)
                return b, self.neff(b)
            d *= 3.0
        return np.nan, np.nan

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


def cutoff_V(family, l, m, n_co, n_cl, Vmax=30.0):
    """Exact vector cutoff V (where b -> 0) — the contrast-dependent formulae.

    TE0m, TM0m : J_0(V) = 0
    EH_lm      : J_l(V) = 0
    HE_1m      : J_1(V) = 0  (m >= 2);  HE_11 has no cutoff (V = 0)
    HE_lm, l>=2: [(n_co^2/n_cl^2) + 1] J_{l-1}(V) = (V/(l-1)) J_l(V)
                 -> reduces to V J_0(V) = 0 when n_co -> n_cl, i.e. the familiar
                    scalar LP cutoff, but moves to larger V at high contrast.
    """
    from scipy.special import jn_zeros
    if family in ("TE", "TM"):
        return jn_zeros(0, m)[m - 1]
    if family == "EH":
        return jn_zeros(l, m)[m - 1]
    if family == "HE" and l == 1:
        return 0.0 if m == 1 else jn_zeros(1, m - 1)[m - 2]
    r = (n_co / n_cl) ** 2
    g = lambda V: (r + 1.0) * jv(l - 1, V) - V * jv(l, V) / (l - 1)
    zs = jn_zeros(l - 1, m + 3)
    lo = 1e-6 if m == 1 else zs[m - 2]
    xs = np.linspace(lo + 1e-9, min(zs[m - 1] - 1e-9, Vmax), 20000)
    fs = g(xs)
    i = np.where(np.sign(fs[:-1]) * np.sign(fs[1:]) < 0)[0]
    return brentq(g, xs[i[0]], xs[i[0] + 1], xtol=1e-15) if len(i) else np.nan
