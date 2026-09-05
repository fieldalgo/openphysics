"""Independent verification of examples/fiber_modes_exact.py.

Five independent gates:
  1. 4x4 boundary-matching determinant (a completely different algebraic route:
     no hand-eliminated 2x2 product, just det of the tangential-continuity
     matrix) must vanish at the roots and reproduce them.
  2. mpmath at 50 digits (independent Bessel implementation + independent
     root finder) must reproduce n_eff.
  3. Exact identity  TE0m == LP1m  (the TE equation is index-independent and is
     algebraically the scalar LP_1m equation).
  4. Weak-guidance limit: as Delta -> 0 the vector n_eff of TE01/TM01/HE21 must
     collapse onto LP11 with an error O(Delta).
  5. b(V) sanity: cutoffs at the Bessel zeros (b -> 0), b -> 1 as V -> inf,
     b monotone increasing in V, and mode count vs V.
Plus the PEC-truncation study: the same characteristic equation with the exact
truncated cladding basis, giving n_eff(R) that a finite FEM domain converges to.
"""
import numpy as np
from scipy.optimize import brentq
from scipy.special import jv, jvp, iv, ivp, kv, kvp, kve, ive

import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fiber_modes_exact import FiberModes, _char_vector, _char_te, _char_tm, _char_lp

A, NCO, NCL, WL = 0.8, 1.45, 1.0, 1.55
F = FiberModes(A, NCO, NCL, WL)
V = F.V
MODES = F.vector_modes()

print("=" * 78)
print(f"FIBER  a={A} um  n_co={NCO}  n_cl={NCL}  lambda={WL} um   V={V:.12f}")
print("=" * 78)

# ---------------------------------------------------------------- gate 1
# 4x4 determinant of the tangential-continuity system.
# Unknowns (A_E, B_H, C_E, D_H) with E_z = A J_l(ur), H_z = i B J_l(ur) inside,
# E_z = C K_l(wr), H_z = i D K_l(wr) outside (the i makes the system real).
#   E_phi = -(beta l/(k^2 r)) E_z + (omega mu0/k^2) h'
#   H_phi/i = -(beta l/(k^2 r)) h  + (omega eps/k^2) E_z'
def det4(b, l):
    u = V * np.sqrt(1 - b) / A
    w = V * np.sqrt(b) / A
    k0 = F.k0
    beta = k0 * F.neff(b)
    k1s, k2s = u * u, -w * w                      # kappa^2 in core / cladding
    U, W = u * A, w * A
    Jl, Jlp = jv(l, U), jvp(l, U, 1)
    Kl, Klp = kve(l, W), (-0.5 * (kve(l - 1, W) + kve(l + 1, W)))  # both x e^W
    M = np.zeros((4, 4))
    # E_z continuity
    M[0] = [Jl, 0, -Kl, 0]
    # H_z continuity
    M[1] = [0, Jl, 0, -Kl]
    # E_phi continuity
    M[2] = [-beta * l / (k1s * A) * Jl, k0 * u / k1s * Jlp,
            beta * l / (k2s * A) * Kl, -k0 * w / k2s * Klp]
    # H_phi continuity  (omega eps = k0 n^2 in units where omega mu0 = k0)
    M[3] = [k0 * NCO ** 2 * u / k1s * Jlp, -beta * l / (k1s * A) * Jl,
            -k0 * NCL ** 2 * w / k2s * Klp, beta * l / (k2s * A) * Kl]
    # row-normalize so the determinant is a clean O(1) residual
    M /= np.abs(M).max(axis=1)[:, None]
    return np.linalg.det(M)


print("\n[1] 4x4 tangential-continuity determinant at the roots, and re-solved")
print(f"    {'mode':7s} {'det(M) at root':>16s} {'b (2x2 route)':>18s} "
      f"{'b (4x4 route)':>18s} {'|db|':>10s}")
for lab, l, b, ne in MODES:
    d = det4(b, l)
    lo, hi = b - 2e-3, b + 2e-3
    b4 = brentq(lambda x: det4(x, l), lo, hi, xtol=1e-16, rtol=8.9e-16)
    print(f"    {lab:7s} {d:16.3e} {b:18.14f} {b4:18.14f} {abs(b-b4):10.2e}")

# ---------------------------------------------------------------- gate 2
print("\n[2] mpmath, 50 digits, independent Bessel + independent bisection")
try:
    import mpmath as mp
    mp.mp.dps = 50
    Vm = mp.mpf(2) * mp.pi / mp.mpf(str(WL)) * mp.mpf(str(A)) * \
        mp.sqrt(mp.mpf(str(NCO)) ** 2 - mp.mpf(str(NCL)) ** 2)
    nco2, ncl2 = mp.mpf(str(NCO)) ** 2, mp.mpf(str(NCL)) ** 2

    def fm(b, l, fam):
        b = mp.mpf(b)
        U, W = Vm * mp.sqrt(1 - b), Vm * mp.sqrt(b)
        # derivatives via the recurrences (mpmath besselk has no derivative arg)
        Jp = (mp.besselj(l - 1, U) - mp.besselj(l + 1, U)) / 2
        Kp = -(mp.besselk(l - 1, W) + mp.besselk(l + 1, W)) / 2
        RJ = Jp / (U * mp.besselj(l, U))
        RK = Kp / (W * mp.besselk(l, W))
        if fam == "TE":
            return RJ + RK
        if fam == "TM":
            return nco2 * RJ + ncl2 * RK
        return (RJ + RK) * (nco2 * RJ + ncl2 * RK) - l ** 2 * \
            (1 / U ** 2 + 1 / W ** 2) * (nco2 / U ** 2 + ncl2 / W ** 2)

    print(f"    {'mode':7s} {'n_eff (double)':>20s} {'n_eff (mp, 50 dps)':>24s} "
          f"{'|diff|':>10s}")
    mpvals = {}
    for lab, l, b, ne in MODES:
        fam = lab[:2] if l == 0 else "HY"
        lo, hi = mp.mpf(float(b)) - mp.mpf('1e-4'), mp.mpf(float(b)) + mp.mpf('1e-4')
        r = mp.findroot(lambda x: fm(x, l, fam), (lo, hi), solver='bisect',
                        tol=mp.mpf(10) ** -45, maxsteps=400)
        nem = mp.sqrt(ncl2 + r * (nco2 - ncl2))
        mpvals[lab] = nem
        print(f"    {lab:7s} {ne:20.15f}   {mp.nstr(nem, 20):>22s} "
              f"{float(abs(mp.mpf(float(ne)) - nem)):10.2e}")
    print("    mp n_eff to 25 digits:")
    for lab in mpvals:
        print(f"      {lab:7s} {mp.nstr(mpvals[lab], 25)}")
except ImportError:
    print("    mpmath unavailable — skipped")

# ---------------------------------------------------------------- gate 3
print("\n[3] exact identity TE0m == LP1m (independent of the index contrast)")
te = [m for m in MODES if m[0].startswith("TE")]
lp = [m for m in F.lp_modes() if m[0].startswith("LP1")]
for (l1, _, b1, n1), (l2, _, b2, n2) in zip(te, lp):
    print(f"    {l1} b={b1:.16f}   {l2} b={b2:.16f}   |db|={abs(b1-b2):.2e}")

# ---------------------------------------------------------------- gate 4
print("\n[4] weak-guidance limit: vector triplet -> LP11, error must scale ~Delta")
print(f"    {'Delta':>10s} {'V':>8s} {'max|n_vec-n_LP11|':>20s} {'/Delta':>10s}")
for nclad in [1.0, 1.4, 1.44, 1.4490, 1.44990, 1.449990]:
    Fw = FiberModes(A, NCO, nclad, WL)
    if Fw.V < 2.5:                     # keep V fixed in the LP11 window
        aw = A * 3.405081070 / (Fw.k0 * A * Fw.NA) * 1.0
        Fw = FiberModes(3.405081070 / (Fw.k0 * Fw.NA), NCO, nclad, WL)
    ms = {m[0]: m[3] for m in Fw.vector_modes()}
    lp11 = [m[3] for m in Fw.lp_modes() if m[0] == "LP11"][0]
    trip = [ms[k] for k in ("TE01", "TM01", "HE21") if k in ms]
    err = max(abs(t - lp11) for t in trip)
    print(f"    {Fw.Delta:10.3e} {Fw.V:8.4f} {err:20.3e} {err/Fw.Delta:10.4f}")

# ---------------------------------------------------------------- gate 5
print("\n[5] b(V): cutoffs, monotonicity, V->inf")
from scipy.special import jn_zeros
print(f"    J0 zeros (TE01/TM01/HE21 cutoff): {jn_zeros(0,2)}")
print(f"    J1 zeros (EH11/HE31/HE12 cutoff): {jn_zeros(1,2)}")
print(f"    {'V':>8s}  " + "  ".join(f"{k:>12s}" for k in
                                     ("HE11", "TE01", "TM01", "HE21", "#modes")))
for Vt in [1.0, 2.0, 2.40, 2.4048255577, 2.42, 2.6, 3.0, 3.405081, 3.80,
           3.8317059702, 5.0, 10.0, 40.0, 200.0]:
    at = Vt / (F.k0 * F.NA)
    Ft = FiberModes(at, NCO, NCL, WL)
    d = {m[0]: m[2] for m in Ft.vector_modes(l_max=8)}
    row = "  ".join(f"{d.get(k, float('nan')):12.9f}"
                    for k in ("HE11", "TE01", "TM01", "HE21"))
    print(f"    {Vt:8.4f}  {row}  {len(d):12d}")

mono = True
Vs = np.linspace(2.5, 3.8, 40)
prev = -1
for Vt in Vs:
    Ft = FiberModes(Vt / (F.k0 * F.NA), NCO, NCL, WL)
    bb = [m[2] for m in Ft.vector_modes(l_max=3) if m[0] == "HE21"][0]
    mono &= bb > prev
    prev = bb
print(f"    b_HE21(V) monotone increasing on [2.5, 3.8]: {mono}")

# published-formula cross-check of the scalar LP01 curve
print("\n    Rudolf-Neumann fit b ~ (1.1428 - 0.996/V)^2 (valid 1.5<V<2.5):")
for Vt in [1.5, 2.0, 2.4, 2.5]:
    Ft = FiberModes(Vt / (F.k0 * F.NA), NCO, NCL, WL)
    bex = [m[2] for m in Ft.lp_modes(l_max=1) if m[0] == "LP01"][0]
    bfit = (1.1428 - 0.996 / Vt) ** 2
    print(f"      V={Vt:4.2f}  exact b={bex:.6f}  fit={bfit:.6f}  "
          f"rel={abs(bex-bfit)/bex:.2%}")

# ---------------------------------------------------------------- truncation
print("\n" + "=" * 78)
print("PEC TRUNCATION: exact n_eff of the fiber inside a PEC cylinder r = R")
print("=" * 78)
print("  Cladding basis K_l(wr)I_l(wR)-I_l(wr)K_l(wR)  (E_z branch, E_z(R)=0)")
print("             and K_l(wr)I_l'(wR)-I_l(wr)K_l'(wR) (H_z branch, E_phi(R)=0)")
print(f"\n  {'R/a':>6s}  " + "  ".join(f"{k:>13s}" for k in
                                      ("HE11", "TE01", "TM01", "HE21")))
ref = {m[0]: m[3] for m in MODES}
rows = []
for Ra in [2, 3, 4, 5, 6, 8, 10, 12, 15, 20, 25, 30]:
    d = {m[0]: m[3] for m in F.vector_modes(l_max=3, R_over_a=Ra)}
    e = {k: abs(d[k] - ref[k]) for k in ref if k in d}
    rows.append((Ra, e))
    print(f"  {Ra:6d}  " + "  ".join(f"{e.get(k, float('nan')):13.3e}"
                                     for k in ("HE11", "TE01", "TM01", "HE21")))
print("\n  decay constants W/a (field ~ e^{-(W/a) r}):")
for lab, l, b, ne in MODES:
    W = V * np.sqrt(b)
    print(f"    {lab:7s} W={W:8.5f}   1/e length = {1/W:6.4f} a   "
          f"e^-2W(R/a-1) at R=10a: {np.exp(-2*W*9):.2e}")
print("\n  fitted decay of the truncation error, log|dn| vs R/a:")
for k in ("HE11", "TE01", "TM01", "HE21"):
    x = np.array([r for r, e in rows if 4 <= r <= 20 and e.get(k, 0) > 1e-15])
    y = np.log(np.array([e[k] for r, e in rows if 4 <= r <= 20 and e.get(k, 0) > 1e-15]))
    if len(x) > 2:
        s = np.polyfit(x, y, 1)[0]
        W = V * np.sqrt([m[2] for m in MODES if m[0] == k][0])
        print(f"    {k:7s} slope = {s:8.4f} per (R/a)   -2W = {-2*W:8.4f}")
