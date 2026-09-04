"""M2.5 figures: ABC vs PML convergence + field decay inside the PML."""

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.tri as mtri

from cylinder_scattering_pml import solve_pml, R0, R_END, A_CYL

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

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12.5, 5.2))

# ---------- convergence comparison ----------
d = np.load("pml_comparison.npz")
h, ea, ep = d["h"], d["err_abc"], d["err_pml"]
ref = ep[0] * (h / h[0]) ** 2
ax1.loglog(h, ref, "--", color=GRAY_REF, lw=1.6, label="slope 2 (theory)")
ax1.loglog(h, ea, "s-", color=ORANGE, lw=2, ms=7, mfc="white", mew=1.8,
           label="first-order ABC")
ax1.loglog(h, ep, "o-", color=BLUE, lw=2, ms=7, mfc="white", mew=1.8,
           label="PML")
ax1.annotate("plateaus at boundary error (~1.1%)", (h[1], ea[1]),
             textcoords="offset points", xytext=(-4, -18), fontsize=9.5,
             color=ORANGE)
ax1.annotate(f"second order continues -> {ep[-1]:.3%}", (h[-1], ep[-1]),
             textcoords="offset points", xytext=(12, -4), fontsize=9.5,
             color=BLUE)
ax1.set_xlabel("element size h"); ax1.set_ylabel("relative L2 error")
ax1.set_title("ABC vs PML — error against the series solution", fontsize=12)
ax1.legend(frameon=False, loc="lower right")

# ---------- decay inside the PML ----------
mesh, u_s = solve_pml(96, 512)
x, y = mesh.nodes[:, 0], mesh.nodes[:, 1]
tri = mtri.Triangulation(x, y, mesh.triangles)
vmax = 1.0
pc = ax2.tripcolor(tri, u_s.real, shading="gouraud", cmap="RdBu_r",
                   vmin=-vmax, vmax=vmax)
ax2.add_patch(plt.Circle((0, 0), A_CYL, facecolor="#d1d5db",
                         edgecolor=INK, lw=1.5, zorder=5))
th = np.linspace(0, 2 * np.pi, 200)
ax2.plot(R0 * np.cos(th), R0 * np.sin(th), "--", color=INK, lw=1.2)
ax2.annotate("PML starts (r = 3)", (R0 * 0.7071, R0 * 0.7071),
             textcoords="offset points", xytext=(8, 8), fontsize=9.5)
ax2.set_aspect("equal"); ax2.grid(False)
ax2.set_xlim(-R_END, R_END); ax2.set_ylim(-R_END, R_END)
ax2.set_title("Re(u_s) — the scattered wave dies inside the PML", fontsize=12)
fig.colorbar(pc, ax=ax2, label="Re(u_s)", shrink=0.85)

fig.tight_layout()
fig.savefig("pml_comparison.png", dpi=160)
plt.close(fig)
print("saved: pml_comparison.png")
