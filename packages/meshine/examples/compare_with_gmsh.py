# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Side-by-side: meshine vs Gmsh (via gmshio) on the Hadley rib waveguide.

Run:  PYTHONPATH=src:../gmshio/src python3 examples/compare_with_gmsh.py
Requires gmshio and a gmsh executable for the right-hand panel; the left
panel is produced regardless.
"""

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from meshine import generate, shapes


def stats(nodes, tris, regions):
    p = nodes[tris]
    L = np.stack([np.linalg.norm(p[:, 2] - p[:, 1], axis=1), np.linalg.norm(p[:, 0] - p[:, 2], axis=1),
                  np.linalg.norm(p[:, 1] - p[:, 0], axis=1)], 1)
    a, b, c = L.T
    A = 0.5 * np.abs((p[:, 1, 0] - p[:, 0, 0]) * (p[:, 2, 1] - p[:, 0, 1]) - (p[:, 2, 0] - p[:, 0, 0]) * (p[:, 1, 1] - p[:, 0, 1]))
    q = 2 * (A / (0.5 * (a + b + c))) / (a * b * c / (4 * A))
    cosines = np.stack([(b**2 + c**2 - a**2) / (2*b*c), (a**2 + c**2 - b**2) / (2*a*c), (a**2 + b**2 - c**2) / (2*a*b)], 1)
    ang = np.degrees(np.arccos(np.clip(cosines, -1, 1)))
    return dict(n=len(tris), min_angle=ang.min(), max_angle=ang.max(), q_mean=q.mean(), q_min=q.min(),
                core_area=A[regions == 0].sum())


def draw(ax, nodes, tris, regions, edges, title):
    ax.tripcolor(nodes[:, 0], nodes[:, 1], tris, facecolors=np.array([0.15, 0.55, 0.9])[regions],
                 cmap="Blues", vmin=0, vmax=1, edgecolors="k", linewidth=0.15)
    for arr in edges.values():
        seg = nodes[arr]
        ax.plot(seg[:, :, 0].T, seg[:, :, 1].T, color="crimson", lw=1.2)
    ax.set_aspect("equal"); ax.set_xlim(-3.5, 3.5); ax.set_ylim(-1.5, 2.0)
    ax.set_title(title, fontsize=10); ax.set_xlabel("x (um)"); ax.set_ylabel("y (um)")


fig, axes = plt.subplots(1, 2, figsize=(13, 4.4))

d, namer = shapes.rib_waveguide(slab_thickness=0.3, size_core=0.1, size_far=0.6)
m = generate(d, namer, size_fn=shapes.size_graded(0.1, 0.6, 3.0, center=(0, 0.5)))
s = stats(m.nodes, m.triangles, m.regions)
draw(axes[0], m.nodes, m.triangles, m.regions, m.boundary_edges,
     f"meshine  {s['n']} tri, angles {s['min_angle']:.1f}-{s['max_angle']:.1f}, q mean {s['q_mean']:.2f}, core {s['core_area']:.3f}")
print("meshine:", s)

try:
    from gmshio import generate as ggen, geo, to_fem2d
    f = to_fem2d(ggen(geo.rib_waveguide(slab_thickness=0.3, lc_core=0.1, lc_far=0.6), dim=2, verbosity=0))
    s = stats(f.nodes, f.triangles, f.regions)
    draw(axes[1], f.nodes, f.triangles, f.regions, f.boundary_edges,
         f"Gmsh  {s['n']} tri, angles {s['min_angle']:.1f}-{s['max_angle']:.1f}, q mean {s['q_mean']:.2f}, core {s['core_area']:.3f}")
    print("gmsh:   ", s)
except Exception as exc:  # gmshio or gmsh missing
    axes[1].text(0.5, 0.5, f"gmsh unavailable\n{exc}", ha="center", va="center", transform=axes[1].transAxes)
    axes[1].set_axis_off()

fig.suptitle("Hadley rib waveguide, slab 0.3 um: own mesher vs Gmsh")
fig.tight_layout()
out = Path(__file__).with_name("compare_with_gmsh.png")
fig.savefig(out, dpi=130)
print("wrote", out)
