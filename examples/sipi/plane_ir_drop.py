# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""DC voltage drop on a 1 oz copper power plane feeding two loads.

Run from the repository root:  python examples/sipi/plane_ir_drop.py

A 60 x 40 mm plane, 35 um thick, is fed at 1.0 V by a regulator pad near one
corner. A processor draws 10 A and a memory device 3 A through their pads. A
rectangular cutout between them forces current around it.
"""

from sipi import PowerPlane, Sink, Source, circle, rectangle_outline

plane = PowerPlane(
    rectangle_outline(0, 0, 60e-3, 40e-3),
    thickness=35e-6,
    holes=[rectangle_outline(25e-3, 10e-3, 32e-3, 32e-3)],
    sources=[Source("vrm", circle((6e-3, 6e-3), 2e-3), voltage=1.0)],
    sinks=[Sink("cpu", circle((48e-3, 26e-3), 3e-3), current=10.0),
           Sink("mem", circle((50e-3, 8e-3), 1.5e-3), current=3.0)])
result = plane.solve()

for name in ("cpu", "mem"):
    t = result.terminals[name]
    print(f"{name}: mean {t['mean']:.4f} V (min {t['min']:.4f}), "
          f"drop {result.drop(name) * 1e3:.1f} mV, "
          f"R {result.resistance(name) * 1e3:.2f} mohm")
print(f"regulator current {result.terminals['vrm']['current']:.3f} A")
print(f"plane loss {result.power_loss:.3f} W")
print(f"peak current density {result.max_current_density / 1e6:.1f} A/mm^2 "
      f"({result.mesh.num_nodes} nodes)")
