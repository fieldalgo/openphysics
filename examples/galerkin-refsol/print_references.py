# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Print a few reference values — handy when wiring a solver's validation script."""

from refsol import fiber, slab, benchmarks, metallic

a, n1, n2, lam = 4.0, 1.45, 1.44, 1.55
print(f"Step-index fiber  a={a} um  n1={n1}  n2={n2}  lambda={lam} um   "
      f"V={fiber.v_number(a, n1, n2, lam):.4f}")
for md in fiber.vector_modes(a, n1, n2, lam, l_max=3):
    print(f"  {md.label:5s}  n_eff = {md.neff:.8f}   b = {md.b:.5f}")
print("  scalar LP:", ", ".join(f"{m.label}={m.neff:.8f}" for m in fiber.lp_modes(a, n1, n2, lam)))

print("\nSOI slab  n_f=3.48  n_s=n_c=1.444  d=0.22 um  lambda=1.55 um")
print("  TE:", [f"{n:.6f}" for n in slab.modes(3.48, 1.444, 1.444, 0.22, 1.55, "TE")])
print("  TM:", [f"{n:.6f}" for n in slab.modes(3.48, 1.444, 1.444, 0.22, 1.55, "TM")])

print("\nRectangular waveguide 1 x 0.5, lowest cutoffs k_c^2:")
for kc2, lbl in metallic.rect_waveguide_cutoffs(1.0, 0.5, n_max=3)[:5]:
    print(f"  {lbl}: {kc2:.4f}")

print("\nHadley 2002 rib waveguide (quasi-TE n_eff, +-3e-6):")
for rw in benchmarks.RIB_WAVEGUIDES:
    print(f"  slab {rw.slab_thickness_um:.1f} um -> {rw.neff_quasi_te:.6f}")
