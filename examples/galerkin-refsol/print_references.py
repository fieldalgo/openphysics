# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Print a few reference values — handy when wiring a solver's validation script."""

from refsol import fiber, slab, benchmarks, metallic

# SI registry names: lengths in m, printed in um
a, n1, n2, lam = 4.0e-6, 1.45, 1.44, 1.55e-6      # core radius, indices (core, cladding), vacuum wavelength
fibre = dict(radius=a, refractive_index=(n1, n2), vacuum_wavelength=lam)
print(f"Step-index fiber  a={a * 1e6:.1f} um  n1={n1}  n2={n2}  lambda={lam * 1e6:.2f} um   "
      f"V={fiber.v_number(**fibre):.4f}")
for md in fiber.vector_modes(**fibre, l_max=3):
    b = (md.effective_index ** 2 - n2 ** 2) / (n1 ** 2 - n2 ** 2)    # normalized propagation constant
    print(f"  {md.label:5s}  n_eff = {md.effective_index:.8f}   b = {b:.5f}")
print("  scalar LP:", ", ".join(f"{m.label}={m.effective_index:.8f}" for m in fiber.lp_modes(**fibre)))

d, lam = 0.22e-6, 1.55e-6                          # slab thickness and vacuum wavelength in m
soi = dict(refractive_index=(1.444, 3.48, 1.444), thickness=d, vacuum_wavelength=lam)
print(f"\nSOI slab  n_f=3.48  n_s=n_c=1.444  d={d * 1e6:.2f} um  lambda={lam * 1e6:.2f} um")
print("  TE:", [f"{n:.6f}" for n in slab.modes(**soi, pol="TE")])
print("  TM:", [f"{n:.6f}" for n in slab.modes(**soi, pol="TM")])

print("\nRectangular waveguide 1 m x 0.5 m, lowest cutoffs k_c^2 in 1/m^2:")
for kc2, lbl in metallic.rect_waveguide_cutoffs(box_size=(1.0, 0.5), n_max=3)[:5]:
    print(f"  {lbl}: {kc2:.4f}")

print("\nHadley 2002 rib waveguide (quasi-TE n_eff, +-3e-6):")
for rw in benchmarks.rib_waveguides():
    print(f"  slab {rw.thickness[0] * 1e6:.1f} um -> {rw.effective_index:.6f}")
