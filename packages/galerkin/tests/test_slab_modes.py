# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""The 1D limit: a planar slab waveguide, against refsol.slab.

A slab has no structure across x, so it is the cheapest problem that still
exercises the full vector formulation — and the polarizations separate exactly,
which makes it a sharp test of the side-wall boundary conditions.

Modelling a 1D slab in a 2D cross-section solver means a narrow strip, and the
SIDE WALLS select the polarization:

    PEC on the side walls   n x E = 0 there, so E_y and E_z vanish and only the
                            x-invariant TE family (E_x alone) survives
    PMC (left unconstrained) the natural condition, which admits E_y and E_z and
                            gives the TM family instead

Getting that backwards returns a perfectly converged answer to the wrong problem,
so both are checked against their own reference.

Note which direction limits the accuracy: for TE it is the mesh across the strip,
not along it. The TE field varies only in y, yet its error is governed by h_x —
the Whitney basis couples the directions through each triangle's diagonal. The
convergence study therefore refines both directions together; refining y alone
stalls at 3.6e-4.
"""

import numpy as np
import pytest

from galerkin import rectangle_mesh, solve_modes
from conftest import assert_second_order

N_FILM, N_CLAD, THICKNESS, WAVELENGTH = 3.48, 1.444, 0.22, 1.55   # SOI, 220 nm
K0 = 2.0 * np.pi / WAVELENGTH
WIDTH, PAD = 0.1, 1.5                     # strip width, cladding either side
HEIGHT = 2 * PAD + THICKNESS

WALLS = {"TE": ("top", "bottom", "left", "right"),   # electric side walls
         "TM": ("top", "bottom")}                    # magnetic side walls


def solve(pol, scale):
    mesh = rectangle_mesh(WIDTH, HEIGHT, 2 * scale, 161 * scale)
    centroid = mesh.nodes[mesh.triangles].mean(axis=1)
    film = (centroid[:, 1] > PAD) & (centroid[:, 1] < PAD + THICKNESS)
    eps = np.where(film, N_FILM ** 2, N_CLAD ** 2)
    pec = np.unique(np.concatenate([mesh.boundary[w] for w in WALLS[pol]]))
    n_eff, space, et, ez = solve_modes(mesh, eps, K0, n_target=N_FILM,
                                       num_modes=6, pec_nodes=pec)
    guided = np.sort(n_eff[(n_eff > N_CLAD) & (n_eff < N_FILM)])[::-1]
    assert len(guided), f"{pol}: no guided mode; raw {np.sort(n_eff)[::-1][:4]}"
    return mesh, space, et, guided[0]


@pytest.mark.parametrize("pol", ["TE", "TM"])
def test_fundamental_slab_mode(refsol, pol):
    reference = refsol.slab.modes(n_f=N_FILM, n_s=N_CLAD, n_c=N_CLAD,
                                  d=THICKNESS, wavelength=WAVELENGTH, pol=pol)[0]
    _, _, _, value = solve(pol, 2)
    rel = abs(value - reference) / reference
    assert rel < 1e-3, f"{pol}0: {value:.9f} vs {reference:.9f} ({rel:.2e})"


@pytest.mark.parametrize("pol", ["TE", "TM"])
def test_the_side_walls_really_do_select_the_polarization(refsol, pol):
    """The mode found under each side-wall condition must be the one intended,
    checked by where its energy sits rather than by which number came out."""
    from galerkin import eval_edge_field

    mesh, space, et, _ = solve(pol, 1)
    E = eval_edge_field(space, et[0])
    area = mesh.areas()
    share_x = (np.sum(area * E[:, 0] ** 2)
               / np.sum(area * (E[:, 0] ** 2 + E[:, 1] ** 2)))
    if pol == "TE":
        assert share_x > 0.99, f"TE mode is only {share_x:.3f} E_x"
    else:
        assert share_x < 0.01, f"TM mode is {share_x:.3f} E_x, should be ~0"


@pytest.mark.parametrize("pol", ["TE", "TM"])
def test_slab_mode_converges_at_second_order(refsol, pol):
    reference = refsol.slab.modes(n_f=N_FILM, n_s=N_CLAD, n_c=N_CLAD,
                                  d=THICKNESS, wavelength=WAVELENGTH, pol=pol)[0]
    errors = [abs(solve(pol, s)[3] - reference) / reference for s in (1, 2, 4)]
    assert_second_order(errors, name=f"{pol}0 slab mode")
