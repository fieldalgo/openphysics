"""M3b figures: cavity mode fields in 3D, the exact spectrum, and convergence."""

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.tri as mtri

from cavity_modes import solve_cavity, exact_spectrum, A_BOX, B_BOX, C_BOX
from galerkin import eval_edge_field_3d

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

d = np.load("cavity_modes.npz")
mesh, space, free, vals, vecs = solve_cavity(15, 12, 9)
cent = mesh.nodes[mesh.tets].mean(axis=1)
vol = mesh.volumes()


def field(i):
    dofs = np.zeros(space.num_edges)
    dofs[free] = vecs[:, i]
    E = eval_edge_field_3d(space, dofs)
    return E / np.abs(E).max()


def lattice(nb):
    """One element per cell of a coarse nb x nb x nb lattice, for readable arrows."""
    L = np.array([A_BOX, B_BOX, C_BOX])
    b = np.clip((cent / L * nb).astype(int), 0, nb - 1)
    _, first = np.unique(b[:, 0] * nb * nb + b[:, 1] * nb + b[:, 2], return_index=True)
    return first


fig = plt.figure(figsize=(13.6, 9.2))
gs = fig.add_gridspec(2, 2, height_ratios=[1.05, 0.85], hspace=0.30, wspace=0.24)

# ---------- (a) TM110 through the volume: E is vertical everywhere ----------
ax = fig.add_subplot(gs[0, 0], projection="3d")
E = field(0)
r = [[0, A_BOX], [0, B_BOX], [0, C_BOX]]
for i in range(3):
    for a in r[(i + 1) % 3]:
        for b in r[(i + 2) % 3]:
            seg = np.zeros((2, 3))
            seg[:, i] = r[i]; seg[:, (i + 1) % 3] = a; seg[:, (i + 2) % 3] = b
            ax.plot(*seg.T, color=MUTED, lw=0.9, alpha=0.55)
sel = lattice(7)
mag = np.linalg.norm(E[sel], axis=1)
keep = sel[mag > 0.12 * mag.max()]
m2 = np.linalg.norm(E[keep], axis=1); m2 /= m2.max()
ax.quiver(cent[keep, 0], cent[keep, 1], cent[keep, 2],
          E[keep, 0], E[keep, 1], E[keep, 2], length=0.30, normalize=False,
          color=plt.cm.viridis(m2), lw=1.6, arrow_length_ratio=0.35)
ax.set_box_aspect((A_BOX, B_BOX, C_BOX))
ax.set_xlabel("x"); ax.set_ylabel("y"); ax.set_zlabel("z")
inp = np.sum(vol * np.sum(E[:, :2] ** 2, axis=1)) / np.sum(vol * np.sum(E ** 2, axis=1))
ax.set_title(f"TM110  —  k² = {vals[0]:.4f}\n"
             f"E is vertical everywhere; the in-plane energy is {inp:.1%}, "
             f"and falls as O(h²)", fontsize=11.5)
ax.grid(False)
ax.view_init(elev=20, azim=-62)

# ---------- (b) TE111 on the mid-plane, where E_z vanishes exactly ----------
ax = fig.add_subplot(gs[0, 1])
E = field(3)
slab = np.abs(cent[:, 2] - C_BOX / 2) < 0.045
tri = mtri.Triangulation(cent[slab, 0], cent[slab, 1])
mag = np.linalg.norm(E[slab], axis=1); mag = mag / mag.max()
pc = ax.tricontourf(tri, mag, levels=22, cmap="magma")
q = lattice(9)
q = q[np.abs(cent[q, 2] - C_BOX / 2) < 0.045]      # the same slab as the colour map
Eq = E[q] / np.linalg.norm(E[q], axis=1).max()
ax.quiver(cent[q, 0], cent[q, 1], Eq[:, 0], Eq[:, 1], color="white",
          width=0.008, scale=9)
ax.set_aspect("equal"); ax.grid(False)
ax.set_xlabel("x"); ax.set_ylabel("y")
ax.set_title(f"TE111 on z = c/2  —  k² = {vals[3]:.4f}\n"
             f"cos(pi z/c) vanishes here, so the arrows are the whole field",
             fontsize=11.5)
fig.colorbar(pc, ax=ax, label="|E| (normalised)", shrink=0.82)

# ---------- (c) spectrum ----------
ax = fig.add_subplot(gs[1, 0])
ex = exact_spectrum()[:5]
for i, (k2, mult, labels) in enumerate(ex):
    ax.axvline(k2, color=GRAY_REF, lw=1.1, zorder=1)
    ax.annotate("/".join(labels) + (f"  (x{mult})" if mult > 1 else ""),
                (k2, 2.46 if i % 2 else 2.22), ha="center", fontsize=8.6, color=MUTED)
ax.plot(d["exact"][:6], np.full(6, 2.0), "|", ms=17, mew=2.4, color=INK)
ax.plot(d["fem"][:6], np.full(6, 1.0), "o", ms=8, mfc="white", mec=BLUE, mew=2)
ax.set_yticks([1.0, 2.0]); ax.set_yticklabels(["M3b FEM", "exact"], fontsize=10)
ax.set_ylim(0.40, 2.92); ax.set_xlim(22, 58)
ax.set_xlabel("resonant wavenumber squared  k²")
ax.set_title("Cavity spectrum — nothing spurious in between", fontsize=12.5)
ax.annotate("the kernel of the discrete curl has dimension exactly the number of\n"
            "interior nodes, so there is no room for a spurious mode to hide",
            (0.5, 0.05), xycoords="axes fraction", ha="center", fontsize=8.8,
            color=MUTED)
ax.grid(axis="y", visible=False)

# ---------- (d) convergence and the degeneracy artefact ----------
ax = fig.add_subplot(gs[1, 1])
h, err, split, labels = d["h"], d["err"], d["split"], d["labels"]
ax.loglog(h, err[0, 0] * (h / h[0]) ** 2, "--", color=GRAY_REF, lw=1.7,
          label="slope 2 (theory)")
for j, col in zip(range(3), (BLUE, "#7c3aed", "#0891b2")):
    ax.loglog(h, err[:, j], "o-", color=col, lw=1.8, ms=6, mfc="white", mew=1.6,
              label=f"{labels[j]} eigenvalue")
ax.loglog(h, split / d["exact"][3], "s--", color=ORANGE, lw=1.8, ms=6,
          mfc="white", mew=1.6, label="TE111/TM111 split (mesh artefact)")
ax.set_xlabel("element size h"); ax.set_ylabel("relative error")
ax.set_title("Second order — and the split degeneracy is an O(h²) artefact",
             fontsize=12)
ax.legend(frameon=False, fontsize=8.6, loc="lower right")

fig.savefig("cavity_modes.png", dpi=160, bbox_inches="tight")
plt.close(fig)
print("saved: cavity_modes.png")
