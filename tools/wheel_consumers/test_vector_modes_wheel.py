# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Installed full-vector and PML waveguide-mode consumer, copied outside the checkout.

Runs the installed ``galerkin.solve_modes`` full-vector formulation on small
slab meshes against the analytic references of the installed ``refsol`` wheel
(``refsol.slab``) and against the outgoing-root dispersion equation of the
leaky slab used by ``tests/galerkin/test_pml_modes.py``, with complex-coordinate
PML from ``galerkin.mode_coordinates``. The ``simcase`` CLI then runs the
shipped ``vector_slab`` example and an open-boundary (PML) variant of it. The
meshes are the coarsest of the source convergence studies and the bounds are
loose and stated; the convergence criteria stay in the source suite. The
whole module ran in about 5 s on Linux. Missing APIs are failures, never skips.
"""

import copy
import json
from pathlib import Path
import subprocess
import sys

import numpy as np
import pytest
from scipy.optimize import root

import galerkin
from galerkin import eval_edge_field, rectangle_mesh, solve_modes
from galerkin.mode_coordinates import mode_coordinates
import refsol
import simcase

# SOI slab of the shipped vector_slab example: 220 nm film, lengths in micrometres.
N_FILM, N_CLAD, THICKNESS, WAVELENGTH = 3.48, 1.444, 0.22, 1.55
K0 = 2.0 * np.pi / WAVELENGTH
WIDTH, PAD = 0.1, 1.5
HEIGHT = 2 * PAD + THICKNESS
# The side walls select the polarization: PEC side walls keep E_x (TE), the
# natural (PMC) side walls admit E_y and E_z (TM).
WALLS = {"TE": ("top", "bottom", "left", "right"), "TM": ("top", "bottom")}


def cli(*args, check=True):
    result = subprocess.run([sys.executable, "-I", "-m", "simcase", *map(str, args)],
                            text=True, encoding="utf-8", capture_output=True)
    if check:
        assert result.returncode == 0, result.stdout + result.stderr
    return result


def slab_reference(pol):
    modes = refsol.slab.modes(n_f=N_FILM, n_s=N_CLAD, n_c=N_CLAD, d=THICKNESS,
                              wavelength=WAVELENGTH, pol=pol)
    assert len(modes) == 1, modes   # single-mode at 220 nm
    return float(modes[0])


def outgoing_root(pol):
    """Leaky TE/TM pole of film 0.22 | gap 0.25 | high-index substrate, by transfer matrix."""
    eps = np.array([N_CLAD ** 2, N_FILM ** 2, N_CLAD ** 2, N_FILM ** 2])

    def residual(z):
        n = complex(*z)
        q = np.sqrt((K0 ** 2 * (eps - n * n)).astype(complex))
        if q[0].imag > 0:      # evanescent left exterior decays
            q[0] = -q[0]
        if q[-1].real < 0:     # propagating substrate is outgoing
            q[-1] = -q[-1]
        weight = eps if pol == "TM" else np.ones(4)
        state = np.array([1.0, 1j * q[0] / weight[0]])
        for j, d in ((1, 0.22), (2, 0.25)):
            c, s = np.cos(q[j] * d), np.sin(q[j] * d)
            state = np.array([[c, weight[j] * s / q[j]], [-q[j] * s / weight[j], c]]) @ state
        r = state[1] + 1j * q[-1] / weight[-1] * state[0]
        return [r.real, r.imag]

    found = root(residual, [2.85 if pol == "TE" else 2.0, -0.01], tol=1e-11)
    assert found.success and np.linalg.norm(residual(found.x)) <= 1e-8, found
    return complex(*found.x)


def leaky_slab_mesh(step, thickness=1.0, pad=1.0):
    breaks = [-pad - thickness, -pad, 0.0, 0.22, 0.47, 0.47 + pad, 0.47 + pad + thickness]
    x = np.concatenate([np.linspace(a, b, int(np.ceil((b - a) / step)) + 1)[:-1]
                        for a, b in zip(breaks[:-1], breaks[1:])] + [[breaks[-1]]])
    mesh = rectangle_mesh(len(x) - 1, 0.1, len(x) - 1, max(2, int(np.ceil(0.1 / step))))
    mesh.nodes[:, 0] = x[mesh.nodes[:, 0].astype(int)]
    centers = mesh.nodes[mesh.triangles, 0].mean(axis=1)
    eps = np.where(((centers > 0) & (centers < 0.22)) | (centers > 0.47), N_FILM ** 2, N_CLAD ** 2)
    return mesh, eps


def test_documented_public_api_is_installed():
    prefix = Path(sys.prefix).resolve()
    for module in (galerkin, refsol, simcase):
        assert Path(module.__file__).resolve().is_relative_to(prefix), module.__name__


@pytest.mark.parametrize("pol", ["TE", "TM"])
def test_full_vector_slab_matches_refsol(pol):
    reference = slab_reference(pol)
    mesh = rectangle_mesh(WIDTH, HEIGHT, 2, 161)
    centroid = mesh.nodes[mesh.triangles].mean(axis=1)
    film = (centroid[:, 1] > PAD) & (centroid[:, 1] < PAD + THICKNESS)
    eps = np.where(film, N_FILM ** 2, N_CLAD ** 2)
    pec = np.unique(np.concatenate([mesh.boundary[w] for w in WALLS[pol]]))
    n_eff, space, et, ez = solve_modes(mesh, eps, K0, n_target=N_FILM, num_modes=6, pec_nodes=pec)
    assert n_eff.shape == (6,) and not np.iscomplexobj(n_eff)   # real materials keep the real path
    assert et.shape == (6, space.num_edges) and ez.shape == (6, mesh.num_nodes)
    assert np.all(np.diff(n_eff) <= 0)
    guided = np.flatnonzero((n_eff > N_CLAD) & (n_eff < N_FILM))
    assert len(guided) == 1, n_eff   # exactly the single reference mode is confined
    # Coarsest mesh of the source convergence study: 8.2e-4 (TE), 1.2e-3 (TM) measured; 1e-3 at twice the resolution.
    assert n_eff[guided[0]] == pytest.approx(reference, rel=5e-3), (pol, n_eff[guided[0]], reference)
    E = eval_edge_field(space, et[guided[0]])
    area = mesh.areas()
    share_x = np.sum(area * np.abs(E[:, 0]) ** 2) / np.sum(area * (np.abs(E[:, 0]) ** 2 + np.abs(E[:, 1]) ** 2))
    assert share_x > 0.99 if pol == "TE" else share_x < 0.01, (pol, share_x)


@pytest.mark.parametrize("pol", ["TE", "TM"])
def test_pml_leaky_slab_matches_the_outgoing_root(pol):
    expected = outgoing_root(pol)
    assert expected.imag < 0   # forward passive attenuation in the exp(+i omega t - i beta z) convention
    mesh, eps = leaky_slab_mesh(0.02)
    coordinates = mode_coordinates(mesh, thickness=dict(left=1.0, right=1.0), strength=3.0)
    assert coordinates.factors.shape == (mesh.num_triangles, 3)
    sides = ("left", "right", "top", "bottom") if pol == "TE" else ("left", "right")
    fixed = np.unique(np.concatenate([mesh.boundary[s] for s in sides]))
    n_eff, space, et, ez = solve_modes(mesh, eps, K0, expected.real, num_modes=6, pec_nodes=fixed,
                                       coordinate_factors=coordinates.factors)
    assert np.iscomplexobj(n_eff) and n_eff.shape == (6,)
    candidate = n_eff[np.argmin(np.abs(n_eff - expected))]
    # Middle mesh of the source study (1.5e-3 TE, 2.5e-3 TM measured; 2e-3 at the finest).
    assert abs(candidate - expected) <= 5e-3, (pol, candidate, expected)
    assert candidate.imag < 0
    # Attenuation itself: 0.7 % (TE) and 1.5 % (TM) measured at this step; 2 % at the finest.
    assert abs((candidate.imag - expected.imag) / expected.imag) <= 5e-2, (pol, candidate, expected)


def test_simcase_cli_vector_slab_and_pml_variant(tmp_path):
    reference = slab_reference("TE")
    example = json.loads(cli("example", "vector_slab").stdout)
    assert example["physics"]["em1"]["formulation"] == "vector"
    model = tmp_path / "vector_slab.json"
    model.write_text(json.dumps(example), encoding="utf-8")
    assert "em.modes2d" in cli("validate", model).stdout
    closed = tmp_path / "closed"
    cli("run", model, "-q", "-o", closed)
    summary = json.loads((closed / "summary.json").read_text(encoding="utf-8"))
    assert summary["formulation"] == "vector" and summary["returned_modes"] == 1
    neff = summary["neff"][0][0]
    assert neff == pytest.approx(reference, rel=5e-3), (neff, reference)   # 1.8e-4 measured
    assert "neff_imag" not in summary   # lossless closed guide keeps the numeric schema

    # Same slab with a complex-coordinate PML on the top and bottom faces: the
    # guided mode must come back with the same real index and no resolvable loss.
    document = copy.deepcopy(example)
    document["physics"]["em1"].update(
        n_target=2.85, pml={"thickness": {"bottom": 0.5, "top": 0.5}, "strength": 3.0,
                            "order": 2, "min_physical_fraction": 0.1})
    pml_model = tmp_path / "vector_slab_pml.json"
    pml_model.write_text(json.dumps(document), encoding="utf-8")
    cli("validate", pml_model)
    opened = tmp_path / "open"
    cli("run", pml_model, "-q", "-o", opened)
    pml_summary = json.loads((opened / "summary.json").read_text(encoding="utf-8"))
    assert pml_summary["mode_result_schema"] == "openphysics.modes2d/2"
    assert pml_summary["neff"][0][0] == pytest.approx(neff, abs=1e-6)
    assert abs(pml_summary["neff_imag"][0][0]) <= 1e-8
    assert abs(pml_summary["propagation_loss_db_cm"][0][0]) <= 1e-3
    [point] = pml_summary["open_boundary"]
    assert point["schema"] == "openphysics.pml-candidates/1"
    assert point["stability"] == "not_checked" and point["selected_candidates"] == [1]
    assert point["length_unit"] == "um" and point["min_physical_fraction"] == 0.1
    selected = [c for c in point["candidates"] if c["selected"]]
    assert len(selected) == 1 and selected[0]["candidate"] == 1
    assert selected[0]["neff_real"] == pml_summary["neff"][0][0]
    assert selected[0]["pencil_residual"] <= 1e-8 and selected[0]["physical_l2_fraction"] > 0.99
    assert selected[0]["attenuation_status"] == "numerically_unresolved"
    assert len(point["candidates"]) >= 6
    with np.load(opened / "fields.npz", allow_pickle=False) as arrays:
        for name in arrays.files:
            assert not arrays[name].dtype.hasobject, name
        assert np.iscomplexobj(arrays["neff"])
        assert arrays["neff"][0][0] == pytest.approx(complex(neff, 0.0), abs=1e-6)
        assert json.loads(arrays["open_boundary_json"].item())[0]["selected_candidates"] == [1]
        for name in ("vector_transverse", "vector_longitudinal", "vector_electric"):
            assert np.all(np.isfinite(arrays[name])), name
