"""M2 figures.

1) scattering_field.png      — cylinder scattering: Re(u_total) and |u_total|
2) scattering_validation.png — angular scattered field FEM vs series
                               + waveguide convergence
"""

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.tri as mtri

from cylinder_scattering import (solve, u_inc, u_scat_exact,
                                 A_CYL, R_OUT, K_WAVE)

INK = "#1a1f2e"
MUTED = "#6b7280"
ACCENT = "#2563eb"
GRAY_REF = "#9ca3af"

plt.rcParams.update({
    "figure.facecolor": "white", "axes.facecolor": "white",
    "axes.edgecolor": MUTED, "axes.labelcolor": INK,
    "xtick.color": MUTED, "ytick.color": MUTED, "text.color": INK,
    "axes.spines.top": False, "axes.spines.right": False,
    "font.size": 11, "axes.grid": True, "grid.color": "#e5e7eb",
    "grid.linewidth": 0.6, "axes.unicode_minus": False,
})

mesh, u_s = solve()
x, y = mesh.nodes[:, 0], mesh.nodes[:, 1]
u_t = u_s + u_inc(x, y)
tri = mtri.Triangulation(x, y, mesh.triangles)

# ---------- 1) wave fields ----------
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12.5, 5.6))

vmax = 2.0
pc1 = ax1.tripcolor(tri, u_t.real, shading="gouraud", cmap="RdBu_r",
                    vmin=-vmax, vmax=vmax)
pc2 = ax2.tripcolor(tri, np.abs(u_t), shading="gouraud", cmap="viridis",
                    vmin=0, vmax=vmax)
for ax, pc, title, cbl in [(ax1, pc1, "Re(u) — instantaneous field", "Re(u)"),
                           (ax2, pc2, "|u| — standing wave & shadow", "|u|")]:
    circ = plt.Circle((0, 0), A_CYL, facecolor="#d1d5db", edgecolor=INK,
                      lw=1.5, zorder=5)
    ax.add_patch(circ)
    ax.set_aspect("equal"); ax.grid(False)
    ax.set_title(title, fontsize=12)
    ax.set_xlim(-R_OUT, R_OUT); ax.set_ylim(-R_OUT, R_OUT)
    fig.colorbar(pc, ax=ax, label=cbl, shrink=0.85)
ax1.annotate("incident wave ->", (-3.8, 3.5), fontsize=11, color=INK)
fig.suptitle(f"Plane-wave scattering off a cylinder (ka = {K_WAVE*A_CYL:.2f})",
             fontsize=13, y=0.98)
fig.tight_layout()
fig.savefig("scattering_field.png", dpi=160)
plt.close(fig)

# ---------- 2) validation ----------
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11.5, 4.6))

# |u_s|(theta) on the ring r = 2: FEM vs series
r_probe = 2.0
r_all = np.sqrt(x ** 2 + y ** 2)
ring = np.abs(r_all - r_probe) < 1e-9  # structured mesh has an exact r=2 ring
th = np.arctan2(y[ring], x[ring])
order = np.argsort(th)
th_s = th[order]
us_fem = np.abs(u_s[ring][order])

th_fine = np.linspace(-np.pi, np.pi, 400)
ex = np.abs(u_scat_exact(r_probe * np.cos(th_fine), r_probe * np.sin(th_fine)))
ax1.plot(np.degrees(th_fine), ex, color=GRAY_REF, lw=2.5, label="series solution")
ax1.plot(np.degrees(th_s[::12]), us_fem[::12], "o", ms=5, mfc="none",
         mec=ACCENT, mew=1.6, label="FEM")
ax1.set_xlabel("theta (deg) — 0 = shadow direction"); ax1.set_ylabel("|u_s|")
ax1.set_title(f"Angular scattered field (r = {r_probe})", fontsize=12)
ax1.legend(frameon=False)

# waveguide convergence
d = np.load("waveguide_convergence.npz")
h, err = d["h"], d["err"]
ref = err[0] * (h / h[0]) ** 2
ax2.loglog(h, ref, "--", color=GRAY_REF, lw=1.8, label="slope 2 (theory)")
ax2.loglog(h, err, "o-", color=ACCENT, lw=2, ms=7, mfc="white", mew=1.8,
           label="L2 error")
ax2.set_xlabel("element size h"); ax2.set_ylabel("L2 error")
ax2.set_title("Guided plane wave — second order confirmed", fontsize=12)
ax2.legend(frameon=False)

fig.tight_layout()
fig.savefig("scattering_validation.png", dpi=160)
plt.close(fig)

print("saved: scattering_field.png, scattering_validation.png")
