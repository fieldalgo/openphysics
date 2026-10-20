# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Generate the Hadley (2002) rib-waveguide cross-section mesh and plot it.

Run:  PYTHONPATH=src python3 examples/hadley_rib_mesh.py
Writes hadley_rib_mesh.png next to this script.
"""

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from gmshio import generate, geo, to_fem2d

fig, axes = plt.subplots(1, 2, figsize=(12, 4.2))
for ax, t in zip(axes, (0.0, 0.3)):
    fem = to_fem2d(generate(geo.rib_waveguide(slab_thickness=t, lc_core=0.1, lc_far=0.6), dim=2, verbosity=0))
    colors = np.array([0.15, 0.55, 0.9])[fem.regions]
    ax.tripcolor(fem.nodes[:, 0], fem.nodes[:, 1], fem.triangles, facecolors=colors,
                 cmap="Blues", vmin=0, vmax=1, edgecolors="k", linewidth=0.15)
    for name, edges in fem.boundary_edges.items():
        seg = fem.nodes[edges]
        ax.plot(seg[:, :, 0].T, seg[:, :, 1].T, color="crimson", lw=1.2)
    ax.set_aspect("equal")
    ax.set_xlim(-4, 4)
    ax.set_ylim(-1.5, 2.0)
    ax.set_title(f"slab thickness {t} um   ({len(fem.triangles)} triangles, "
                 f"core area {fem.region_area('core'):.3f})")
    ax.set_xlabel("x (um)")
    ax.set_ylabel("y (um)")
fig.suptitle("Hadley 2002 rib waveguide: n=3.44 core / 3.40 substrate / 1.0 air, width 3 um, thickness 1 um")
fig.tight_layout()
out = Path(__file__).with_name("hadley_rib_mesh.png")
fig.savefig(out, dpi=130)
print("wrote", out)
