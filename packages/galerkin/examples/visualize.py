"""M1 figures.

1) coax_validation.png     — coaxial cable: potential + field, FEM vs analytical
2) convergence.png         — L2 error under mesh refinement (slope-2 check)
3) capacitor_fringing.png  — fringing field of a parallel-plate capacitor
"""

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.tri as mtri

from galerkin import (annulus_mesh, rectangle_mesh, assemble_stiffness,
                      assemble_load, solve_dirichlet, element_gradient)
from coax_convergence import A, B, exact, solve_on

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


# ---------- 1) coaxial-cable validation ----------
mesh, V = solve_on(32, 192)
tri = mtri.Triangulation(mesh.nodes[:, 0], mesh.nodes[:, 1], mesh.triangles)

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4.6))

pc = ax1.tripcolor(tri, V, shading="gouraud", cmap="viridis")
E = -element_gradient(mesh, V)
cent = mesh.nodes[mesh.triangles].mean(axis=1)
step = 97
ax1.quiver(cent[::step, 0], cent[::step, 1], E[::step, 0], E[::step, 1],
           color="white", width=0.004, scale=12)
ax1.set_aspect("equal"); ax1.grid(False)
ax1.set_title("Potential V and field E (coaxial cable)", fontsize=12)
fig.colorbar(pc, ax=ax1, label="V")

r = np.sqrt((mesh.nodes ** 2).sum(axis=1))
order = np.argsort(r)
rr = np.linspace(A, B, 200)
ax2.plot(rr, np.log(B / rr) / np.log(B / A), color=GRAY_REF, lw=2.5,
         label="analytical  V(r) = ln(b/r)/ln(b/a)")
sel = order[::37]
ax2.plot(r[sel], V[sel], "o", ms=5, mfc="none", mec=ACCENT, mew=1.6,
         label="FEM")
ax2.set_xlabel("r"); ax2.set_ylabel("V")
ax2.set_title("Radial potential: FEM vs analytical", fontsize=12)
ax2.legend(frameon=False)

fig.tight_layout()
fig.savefig("coax_validation.png", dpi=160)
plt.close(fig)

# ---------- 2) convergence plot ----------
d = np.load("coax_convergence.npz")
h, err = d["h"], d["err"]

fig, ax = plt.subplots(figsize=(6.2, 4.6))
ref = err[0] * (h / h[0]) ** 2
ax.loglog(h, ref, "--", color=GRAY_REF, lw=1.8, label="slope 2 (theory)")
ax.loglog(h, err, "o-", color=ACCENT, lw=2, ms=7, mfc="white", mew=1.8,
          label="L2 error")
for hi, ei in zip(h, err):
    ax.annotate(f"{ei:.1e}", (hi, ei), textcoords="offset points",
                xytext=(8, -12), fontsize=8.5, color=MUTED)
ax.set_xlabel("element size h"); ax.set_ylabel("L2 error")
ax.set_title("Mesh convergence — P1, theoretical rate 2", fontsize=12)
ax.legend(frameon=False)
fig.tight_layout()
fig.savefig("convergence.png", dpi=160)
plt.close(fig)

# ---------- 3) parallel-plate fringing field ----------
W, H, nx, ny = 2.0, 1.0, 240, 120
m = rectangle_mesh(W, H, nx, ny)

def node_id(i, j):
    return j * (nx + 1) + i

# Plates: y = 0.45, 0.55 / x in [0.7, 1.3], chosen to coincide with grid lines
i0, i1 = int(0.7 / W * nx), int(1.3 / W * nx)
j_lo, j_hi = int(0.45 / H * ny), int(0.55 / H * ny)
plate_lo = np.array([node_id(i, j_lo) for i in range(i0, i1 + 1)])
plate_hi = np.array([node_id(i, j_hi) for i in range(i0, i1 + 1)])
outer = np.unique(np.concatenate([m.boundary[k] for k in m.boundary]))

K = assemble_stiffness(m)
f = assemble_load(m)
Vc = solve_dirichlet(K, f, {
    tuple(plate_hi): 1.0,
    tuple(plate_lo): -1.0,
    tuple(outer): 0.0,
})

# Structured grid, so reshape to (ny+1, nx+1) and use streamplot
Vg = Vc.reshape(ny + 1, nx + 1)
xg = np.linspace(0, W, nx + 1)
yg = np.linspace(0, H, ny + 1)
dVdy, dVdx = np.gradient(Vg, yg, xg)
Ex, Ey = -dVdx, -dVdy

fig, ax = plt.subplots(figsize=(9.5, 5))
cf = ax.contourf(xg, yg, Vg, levels=41, cmap="RdBu_r")
ax.streamplot(xg, yg, Ex, Ey, color=INK, linewidth=0.7, density=1.3,
              arrowsize=0.9)
ax.plot([xg[i0], xg[i1]], [yg[j_hi]] * 2, color=INK, lw=3.5)
ax.plot([xg[i0], xg[i1]], [yg[j_lo]] * 2, color=INK, lw=3.5)
ax.annotate("+1 V", (xg[i1] + 0.03, yg[j_hi]), va="center", fontsize=10)
ax.annotate("-1 V", (xg[i1] + 0.03, yg[j_lo]), va="center", fontsize=10)
ax.set_aspect("equal"); ax.grid(False)
ax.set_title("Parallel-plate capacitor — fringing field (potential + field lines)",
             fontsize=12)
fig.colorbar(cf, ax=ax, label="V", shrink=0.85)
fig.tight_layout()
fig.savefig("capacitor_fringing.png", dpi=160)
plt.close(fig)

print("saved: coax_validation.png, convergence.png, capacitor_fringing.png")
