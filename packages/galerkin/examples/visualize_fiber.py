# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""M3a figures: vector mode profiles, the LP11 splitting, and n_eff convergence."""

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.tri as mtri

from fiber_modes import solve_vector, exact_modes, A_CORE, N_CO, N_CL, K0
from galerkin import eval_edge_field

INK = "#1a1f2e"; MUTED = "#6b7280"
BLUE = "#2563eb"; ORANGE = "#d97706"; GREEN = "#059669"; GRAY_REF = "#9ca3af"

plt.rcParams.update({
    "figure.facecolor": "white", "axes.facecolor": "white",
    "axes.edgecolor": MUTED, "axes.labelcolor": INK,
    "xtick.color": MUTED, "ytick.color": MUTED, "text.color": INK,
    "axes.spines.top": False, "axes.spines.right": False,
    "font.size": 11, "axes.grid": True, "grid.color": "#e5e7eb",
    "grid.linewidth": 0.6, "axes.unicode_minus": False,
})

d = np.load("fiber_modes.npz")
exact = exact_modes()

mesh, space, n_eff, et, ez = solve_vector((24, 36, 45), 192)
order = np.argsort(n_eff)[::-1]
n_eff, et, ez = n_eff[order], et[order], ez[order]
# descending n_eff: HE11, HE11, TE01, TM01, HE21, HE21
PICK = [(0, "HE11"), (2, "TE01"), (3, "TM01"), (4, "HE21")]

cent = mesh.nodes[mesh.triangles].mean(axis=1)
r_c = np.linalg.norm(cent, axis=1)
th_c = np.arctan2(cent[:, 1], cent[:, 0])
tri = mtri.Triangulation(mesh.nodes[:, 0], mesh.nodes[:, 1], mesh.triangles)
ZOOM = 2.0

# One arrow per polar cell: a raw stride would crowd the centre, where the
# elements are smallest, and starve the rim.
NB_R, NB_T = 7, 22
_rb = np.clip((r_c / ZOOM * NB_R).astype(int), 0, NB_R - 1)
_tb = (((th_c + np.pi) / (2 * np.pi) * NB_T).astype(int)) % NB_T
_, ARROW = np.unique(_rb * NB_T + _tb, return_index=True)
ARROW = ARROW[r_c[ARROW] < ZOOM * 0.95]

fig = plt.figure(figsize=(14.0, 8.6))
gs = fig.add_gridspec(2, 4, height_ratios=[1.0, 0.95], hspace=0.42, wspace=0.34)

# ---------- (top) the four guided modes ----------
for col, (idx, lbl) in enumerate(PICK):
    ax = fig.add_subplot(gs[0, col])
    Et = eval_edge_field(space, et[idx])
    Ez = ez[idx]                                    # physical E_z = 1j * Ez
    mag = np.linalg.norm(Et, axis=1)
    mag = mag / mag.max()
    ax.tripcolor(tri, facecolors=mag, cmap="magma", vmin=0, vmax=1)

    sel = ARROW[mag[ARROW] > 0.05]
    q = Et[sel] / np.linalg.norm(Et[sel], axis=1).max()
    ax.quiver(cent[sel, 0], cent[sel, 1], q[:, 0], q[:, 1],
              color="white", width=0.010, scale=9, alpha=0.95)
    ax.add_patch(plt.Circle((0, 0), A_CORE, fill=False, color="#67e8f9",
                            lw=1.6, ls="--", alpha=0.95))
    ax.set_xlim(-ZOOM, ZOOM); ax.set_ylim(-ZOOM, ZOOM)
    ax.set_aspect("equal"); ax.grid(False)
    ax.set_xticks([]); ax.set_yticks([])
    ez_frac = np.abs(Ez).max() / max(np.linalg.norm(Et, axis=1).max(), 1e-30)
    frac = "0 (TE)" if ez_frac < 1e-8 else f"{ez_frac:.2f}"
    ax.set_title(f"{lbl}\nn_eff = {n_eff[idx]:.6f}\n"
                 f"|E_z|/|E_t| = {frac}", fontsize=11.5)

fig.text(0.5, 0.985, "Step-index fibre — the four guided modes at V = 3.5 "
         "(colour |E_t|, arrows E_t, dashed line the core boundary)",
         ha="center", fontsize=12.5)
fig.text(0.5, 0.957, "the two degenerate pairs, HE11 and HE21, come out of the "
         "eigensolver in an arbitrary orientation — only their n_eff is fixed",
         ha="center", fontsize=9, color=MUTED)

# ---------- (bottom left) the LP11 splitting ----------
ax = fig.add_subplot(gs[1, :2])
sc = d["scalar"]
sc = sc[(sc > N_CL) & (sc < N_CO)]
for i, (lbl, (v, _)) in enumerate(exact.items()):
    ax.axvline(v, color=GRAY_REF, lw=1.1, zorder=1)
    ax.annotate(lbl, (v, 3.60 if i % 2 else 3.35), ha="center",
                fontsize=9.5, color=MUTED)          # stagger: TM01/HE21 nearly coincide
ax.plot(d["exact"], np.full(len(d["exact"]), 3.0), "|", ms=18, mew=2.4, color=INK)
ax.plot(d["fem"], np.full(len(d["fem"]), 2.0), "o", ms=9, mfc="white",
        mec=BLUE, mew=2)
ax.plot(sc, np.full(len(sc), 1.0), "x", ms=10, mew=2.2, color=ORANGE)
ax.set_yticks([1.0, 2.0, 3.0])
ax.set_yticklabels(["scalar (LP)\nsame mesh", "M3a\nfull vector", "exact\nvector"],
                   fontsize=9.5)
ax.set_ylim(0.30, 4.05)
ax.set_xlim(1.09, 1.40)
ax.set_xlabel("effective index  n_eff = beta / k0")
ax.set_title("Scalar theory sees one LP11; the vector solver splits it into three",
             fontsize=12.5)
ax.annotate("one doubly degenerate LP11:\nscalar theory cannot split it",
            (sc[1], 1.0), xytext=(1.205, 0.62), fontsize=8.8, color=ORANGE,
            arrowprops=dict(arrowstyle="->", color=ORANGE, lw=1.1))
ax.annotate(f"LP01 overshoots HE11 by "
            f"{abs(sc[0]-exact['HE11'][0])/exact['HE11'][0]:.1%}",
            (sc[0], 1.0), xytext=(1.288, 1.42), fontsize=8.8, color=ORANGE,
            arrowprops=dict(arrowstyle="->", color=ORANGE, lw=1.1))
ax.annotate("", (exact["TE01"][0], 2.46), (exact["HE21"][0], 2.46),
            arrowprops=dict(arrowstyle="<->", color=BLUE, lw=1.2))
ax.annotate(f"physical splitting {exact['TE01'][0]-exact['HE21'][0]:.3f}",
            ((exact["TE01"][0] + exact["HE21"][0]) / 2, 2.56), ha="center",
            fontsize=8.8, color=BLUE)
ax.grid(axis="y", visible=False)

# ---------- (bottom right) convergence ----------
ax = fig.add_subplot(gs[1, 2:])
h, err = d["h"], d["err"]
ax.loglog(h, err[0] * (h / h[0]) ** 2, "--", color=GRAY_REF, lw=1.8,
          label="slope 2 (theory)")
ax.loglog(h, err, "o-", color=BLUE, lw=2, ms=7, mfc="white", mew=1.8,
          label="HE11 n_eff rel. error")
ax.set_xlabel("element size h in the core"); ax.set_ylabel("relative error")
ax.set_title("Effective index converges at second order", fontsize=12.5)
ax.legend(frameon=False)
ax.annotate("mesh-induced splitting of the\ndegenerate pairs: 1e-14 —\n"
            "twelve orders below the physical\nTE01-HE21 splitting of 6.3e-2",
            (0.97, 0.06), xycoords="axes fraction", ha="right", fontsize=8.5,
            color=MUTED)

fig.savefig("fiber_modes.png", dpi=160, bbox_inches="tight")
plt.close(fig)
print("saved: fiber_modes.png")


# ============================================================================
# Second figure: the dielectric interface. E normal to a material boundary is
# discontinuous — eps E_r is what stays continuous, so E_r jumps by n_co^2/n_cl^2.
# A nodal (fully continuous) vector element cannot represent that at all; edge
# elements represent it exactly, and this is the whole reason M3a uses them.
# ============================================================================
from scipy.special import jv, kv                                    # noqa: E402

nef = exact["TM01"][0]
u = K0 * A_CORE * np.sqrt(N_CO ** 2 - nef ** 2)
w = K0 * A_CORE * np.sqrt(nef ** 2 - N_CL ** 2)
# E_z = J_0(ur/a) inside, (J_0(u)/K_0(w)) K_0(wr/a) outside; E_r ~ -dE_z/dr / kappa^2,
# and K_0' = -K_1 supplies the sign that keeps E_r from flipping across the boundary.
f_in = lambda rr: jv(1, u * rr / A_CORE) / u
f_out = lambda rr: -(jv(0, u) / kv(0, w)) * kv(1, w * rr / A_CORE) / w

Et = eval_edge_field(space, et[3])                                  # TM01
Er = np.abs(Et[:, 0] * np.cos(th_c) + Et[:, 1] * np.sin(th_c))
srt = np.argsort(r_c)
r_s, Er_s = r_c[srt], Er[srt]
scale = np.interp(0.5, r_s, Er_s) / f_in(0.5)                       # one global scale

fig2, (bx, cx) = plt.subplots(1, 2, figsize=(12.6, 4.6),
                              gridspec_kw={"width_ratios": [1.25, 1]})

sel = r_s < 3.0
bx.plot(r_s[sel], Er_s[sel] / scale, ".", ms=2.6, color=BLUE, alpha=0.35,
        label="M3a FEM, one value per element")
rr = np.linspace(1e-3, 0.99999, 300)
bx.plot(rr, f_in(rr), color=INK, lw=2, label="exact (core branch)")
rr = np.linspace(1.00001, 3.0, 300)
bx.plot(rr, f_out(rr), color=INK, lw=2, ls=(0, (5, 2)),
        label="exact (cladding branch)")
bx.axvline(A_CORE, color=ORANGE, lw=1.3, ls=":")
bx.annotate(f"eps E_r is what stays continuous, so |E_r| jumps\n"
            f"by n_co²/n_cl² = {N_CO**2/N_CL**2:.2f} at the core boundary\n"
            f"(measured {f_out(1.0)/f_in(1.0):.4f})",
            (1.0, f_out(1.0)), xytext=(1.42, f_out(1.0) * 0.80),
            fontsize=9.5, color=ORANGE,
            arrowprops=dict(arrowstyle="->", color=ORANGE, lw=1.2))
bx.set_xlabel("radius r / a"); bx.set_ylabel("|E_r|  (TM01, normalised)")
bx.set_title("The radial field is discontinuous at the dielectric interface",
             fontsize=12.5)
bx.legend(frameon=False, fontsize=9)

zoom = (r_s > 0.82) & (r_s < 1.20)
cx.plot(r_s[zoom], Er_s[zoom] / scale, "o", ms=3.4, mfc="none", mec=BLUE,
        mew=1.0, alpha=0.5)
rr = np.linspace(0.82, 0.99999, 200); cx.plot(rr, f_in(rr), color=INK, lw=2)
rr = np.linspace(1.00001, 1.20, 200); cx.plot(rr, f_out(rr), color=INK, lw=2,
                                              ls=(0, (5, 2)))
cx.axvline(A_CORE, color=ORANGE, lw=1.3, ls=":")
cx.set_xlabel("radius r / a")
cx.set_title("Zoom on the jump — the FEM lands on both branches",
             fontsize=12.5)
cx.annotate("a fully continuous (nodal) vector element cannot\n"
            "represent this step at all — which is exactly why the\n"
            "transverse field has to live in H(curl)",
            (0.03, 0.97), xycoords="axes fraction", ha="left", va="top",
            fontsize=8.8, color=MUTED)

fig2.tight_layout()
fig2.savefig("fiber_interface.png", dpi=160, bbox_inches="tight")
plt.close(fig2)
print("saved: fiber_interface.png")
