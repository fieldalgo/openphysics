"""M3-prep figures: spectrum comparison + TE10 mode field + eigenvalue convergence."""

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.tri as mtri

from waveguide_modes import solve_nedelec, exact_cutoffs, A_WG, B_WG
from galerkin import eval_edge_field

INK = "#1a1f2e"; MUTED = "#6b7280"
BLUE = "#2563eb"; ORANGE = "#d97706"; GRAY_REF = "#9ca3af"

plt.rcParams.update({
    "figure.facecolor": "white", "axes.facecolor": "white",
    "axes.edgecolor": MUTED, "axes.labelcolor": INK,
    "xtick.color": MUTED, "ytick.color": MUTED, "text.color": INK,
    "axes.spines.top": False, "axes.spines.right": False,
    "font.size": 11, "axes.grid": True, "grid.color": "#e5e7eb",
    "grid.linewidth": 0.6, "axes.unicode_minus": False,
})

d = np.load("waveguide_modes.npz")
exact = d["exact"]; labels = d["labels"]
ned = d["nedelec"]; nod = d["nodal"]

fig = plt.figure(figsize=(12.5, 8.2))
gs = fig.add_gridspec(2, 2, height_ratios=[1.0, 1.15], hspace=0.42, wspace=0.28)

# ---------- (top) spectrum comparison ----------
ax = fig.add_subplot(gs[0, :])
xmax = 95
shown = {}
for v, lbl in zip(exact, labels):
    if v < xmax:
        key = round(float(v), 6)
        if key in shown:
            shown[key] += "/" + lbl
        else:
            shown[key] = lbl
            ax.axvline(v, color=GRAY_REF, lw=1.2, zorder=1)
for v, lbl in shown.items():
    ax.annotate(lbl, (v, 2.62), ha="center", fontsize=9.5, color=MUTED)
ax.plot(ned[ned < xmax], np.full(np.sum(ned < xmax), 2.0), "o", ms=9,
        mfc="white", mec=BLUE, mew=2, zorder=3, label="Nedelec (edge)")
ax.plot(nod[nod < xmax], np.full(np.sum(nod < xmax), 1.0), "x", ms=9,
        color=ORANGE, mew=2.2, zorder=3, label="vector P1 (nodal)")
ax.set_yticks([1.0, 2.0])
ax.set_yticklabels(["nodal\n(wrong)", "edge\n(right)"], fontsize=10)
ax.set_ylim(0.4, 2.9)
ax.set_xlim(0, xmax)
ax.set_xlabel("eigenvalue k_c^2  (vertical lines = analytical)")
ax.set_title("Waveguide cutoff spectrum — nodal elements invent spurious modes",
             fontsize=12.5)
ax.annotate("both methods asked for 14 eigenvalues near k_c^2 = 60 —\n"
            "edge elements land on physical modes; nodal elements return junk",
            (0.985, 0.06), xycoords="axes fraction", ha="right", fontsize=9,
            color=MUTED)
ax.grid(axis="y", visible=False)

# ---------- (bottom left) TE10 mode field ----------
ax = fig.add_subplot(gs[1, 0])
mesh, space, free, vals, vecs = solve_nedelec(60, 30, k=6, sigma=12.0)
idx = np.argmin(np.abs(vals - exact[0]))
dofs = np.zeros(space.num_edges)
dofs[free] = vecs[:, idx]
E = eval_edge_field(space, dofs)
E /= np.abs(E).max()
cent = mesh.nodes[mesh.triangles].mean(axis=1)
tri = mtri.Triangulation(mesh.nodes[:, 0], mesh.nodes[:, 1], mesh.triangles)

mag = np.linalg.norm(E, axis=1)
pc = ax.tripcolor(tri, facecolors=mag, cmap="viridis")
step = 53
ax.quiver(cent[::step, 0], cent[::step, 1], E[::step, 0], E[::step, 1],
          color="white", width=0.005, scale=14)
ax.set_aspect("equal"); ax.grid(False)
ax.set_title(f"TE10 mode  (k_c^2 = {vals[idx]:.3f}, exact {exact[0]:.3f})",
             fontsize=12)
fig.colorbar(pc, ax=ax, label="|E| (normalized)", shrink=0.8)

# ---------- (bottom right) eigenvalue convergence ----------
ax = fig.add_subplot(gs[1, 1])
h, err = d["h"], d["err"]
ref = err[0] * (h / h[0]) ** 2
ax.loglog(h, ref, "--", color=GRAY_REF, lw=1.8, label="slope 2 (theory)")
ax.loglog(h, err, "o-", color=BLUE, lw=2, ms=7, mfc="white", mew=1.8,
          label="TE10 eigenvalue rel. error")
ax.set_xlabel("element size h"); ax.set_ylabel("relative error")
ax.set_title("TE10 eigenvalue convergence — second order", fontsize=12)
ax.legend(frameon=False)

fig.savefig("waveguide_modes.png", dpi=160, bbox_inches="tight")
plt.close(fig)
print("saved: waveguide_modes.png")
