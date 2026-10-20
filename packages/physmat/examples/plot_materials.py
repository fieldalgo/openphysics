# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Plot built-in dispersion curves and a Drude-Lorentz fit of gold.

Run:  PYTHONPATH=src python3 examples/plot_materials.py
"""

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

import physmat

fig, axes = plt.subplots(1, 3, figsize=(15, 4.3))

ax = axes[0]
for name in ("SiO2", "Si3N4", "Al2O3", "MgF2", "LiNbO3"):
    m = physmat.get(name)
    lo, hi = m.range_um
    wl = np.linspace(max(lo, 0.3), min(hi, 3.0), 300)
    ax.plot(wl, m.n(wl), label=f"{name}  ({m.source.split(',')[0]})")
ax.set_xlabel("wavelength (um)"); ax.set_ylabel("n"); ax.set_title("dielectrics: Sellmeier-type formulas")
ax.legend(fontsize=7)

ax = axes[1]
m = physmat.get("Si"); wl = np.linspace(1.36, 5.0, 200)
ax.plot(wl, m.n(wl), color="C0", label="Si n (Salzberg-Villa 1957, IR)")
m = physmat.get("Si_visible"); wl = np.linspace(0.3, 1.45, 200)
ax.plot(wl, m.n(wl), color="C1", label="Si n (Green 2008)")
g = physmat.get("GaAs"); wg = np.linspace(1.0, 5.0, 200)
ax.plot(wg, g.n(wg), color="C3", label="GaAs n (Skauli 2003)")
ax.set_ylim(3.3, 7); ax.set_xlabel("wavelength (um)"); ax.set_ylabel("n"); ax.set_title("semiconductors")
ax2 = ax.twinx()
ax2.semilogy(wl, m.k(wl), "--", color="C2", label="Si k (Green 2008), right axis")
ax2.set_ylim(1e-9, 10); ax2.set_ylabel("k")
h1, l1 = ax.get_legend_handles_labels(); h2, l2 = ax2.get_legend_handles_labels()
ax.legend(h1 + h2, l1 + l2, fontsize=7, loc="upper right")

ax = axes[2]
au = physmat.get("Au")
wl = np.linspace(0.4, 1.0, 200)
eps = au.eps(wl)
fit = physmat.fit_drude_lorentz(au.optical, np.linspace(0.4, 1.0, 60), n_lorentz=2)
ef = fit.model.eps(wl)
ax.plot(wl, eps.real, "o", ms=3, color="C0", label="Re eps, Johnson & Christy 1972")
ax.plot(wl, eps.imag, "o", ms=3, color="C1", label="Im eps")
ax.plot(wl, ef.real, "-", color="C0", label=f"Drude + 2 Lorentz fit (rms {fit.rms_eps:.2f})")
ax.plot(wl, ef.imag, "-", color="C1")
ax.set_xlabel("wavelength (um)"); ax.set_ylabel("permittivity"); ax.set_title("gold: table and pole fit")
ax.legend(fontsize=7)

fig.suptitle("physmat built-in materials (data via refractiveindex.info, CC0)")
fig.tight_layout()
out = Path(__file__).with_name("materials.png")
fig.savefig(out, dpi=130)
print("wrote", out)
print("fit parameters [eps_inf, wp, f0, G0, (f, w, G)...]:", np.round(fit.model.parameters(), 4))
