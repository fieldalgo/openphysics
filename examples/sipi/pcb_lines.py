# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Impedance of a single microstrip and a differential pair on FR-4.

Run from the repository root:  python examples/sipi/pcb_lines.py

Stack: 35 um copper traces on 0.2 mm FR-4 (eps_r 4.3, tan d 0.02) over a ground
plane, air above. The box is wide and tall enough that moving its open walls
changes Z0 by well under 1 % (check by doubling width and the air layer).
"""

from sipi import CrossSection, Layer, Trace

H, T = 0.2e-3, 35e-6
stack = [Layer("FR-4", H, eps_r=4.3, tan_delta=0.02), Layer("air", 4e-3)]

single = CrossSection(stack, [Trace("sig", 0.0, 0.35e-3, H, T)], width=8e-3).analyze()
print("single microstrip, w = 0.35 mm")
print(f"  Z0      = {single.z0:7.2f} ohm")
print(f"  eps_eff = {single.eps_eff:7.4f}")
print(f"  delay   = {single.delay * 1e12 * 1e-3:7.3f} ps/mm")
print(f"  L       = {single.L[0, 0] * 1e6:7.4f} nH/mm")
print(f"  C       = {single.C[0, 0] * 1e9:7.4f} pF/mm")
print(f"  G(1GHz) = {single.G(1e9)[0, 0] * 1e3:7.3f} mS/m")

w, s = 0.2e-3, 0.2e-3
pair = CrossSection(stack, [Trace("p", -(w + s) / 2, w, H, T),
                            Trace("n", (w + s) / 2, w, H, T)], width=8e-3).analyze()
modes = pair.even_odd()
print("edge-coupled pair, w = s = 0.2 mm")
print(f"  Z_diff  = {modes['z_diff']:7.2f} ohm   (odd-mode eps_eff {modes['eps_eff_odd']:.4f})")
print(f"  Z_comm  = {modes['z_common']:7.2f} ohm   (even-mode eps_eff {modes['eps_eff_even']:.4f})")
