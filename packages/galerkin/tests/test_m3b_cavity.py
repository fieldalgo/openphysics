"""M3b: 3D Maxwell — a rectangular PEC cavity, graded against refsol.metallic.

Three things are checked, in increasing order of how much they would cost to get
wrong: that the discrete complex is exact (an integer identity), that no spurious
mode appears between the physical ones, and that the resonances converge at
second order.
"""

import numpy as np
import pytest
import scipy.sparse as sp
import scipy.sparse.linalg as spla

from galerkin import (box_mesh, EdgeSpace3D, assemble_curlcurl_3d,
                      assemble_edge_mass_3d, assemble_edge_grad_3d,
                      assemble_stiffness_3d)
from conftest import rate


def _system(nx, ny, nz, a=1.0, b=1.0, d=1.0):
    mesh = box_mesh(a, b, d, nx, ny, nz)
    space = EdgeSpace3D(mesh)
    S = assemble_curlcurl_3d(space)
    M = assemble_edge_mass_3d(space)
    free = np.setdiff1d(np.arange(space.num_edges), space.boundary_edge_ids())
    interior_nodes = mesh.num_nodes - len(mesh.boundary_nodes())
    return (mesh, space, free, S[free][:, free].tocsc(),
            M[free][:, free].tocsc(), interior_nodes)


def _resonances(nx, ny, nz, sigma, nev=18, **box):
    _, _, free, S, M, _ = _system(nx, ny, nz, **box)
    vals = np.sort(spla.eigsh(S, k=nev, M=M, sigma=sigma, which="LM",
                              v0=np.ones(S.shape[0]),
                              ncv=min(S.shape[0], max(6 * nev, 90)),
                              maxiter=50000, return_eigenvectors=False))
    scale = np.abs(vals).max()
    return np.sort(vals[np.abs(vals) > 1e-6 * scale])


def _clusters(pairs, take=3):
    out = []
    for k2, label in pairs:
        if out and abs(out[-1][0] - k2) < 1e-9:
            out[-1][1] += 1
            out[-1][2].append(label)
        else:
            out.append([k2, 1, [label]])
    return out[:take]


def test_unit_cube_lowest_resonance_is_a_triple(refsol):
    """The claim worth checking before any solver runs: on a unit cube the lowest
    k^2 is 2 pi^2 with THREE modes, and the next is 3 pi^2."""
    cl = _clusters(refsol.metallic.rect_cavity_resonances(1.0, 1.0, 1.0, n_max=3))
    assert abs(cl[0][0] - 2 * np.pi ** 2) < 1e-9 and cl[0][1] == 3
    assert sorted(cl[0][2]) == ["TE011", "TE101", "TM110"]
    assert abs(cl[1][0] - 3 * np.pi ** 2) < 1e-9 and cl[1][1] == 2


def test_discrete_complex_is_exact():
    """dim ker(curl) equals the number of interior nodes, exactly. This is what
    leaves no room for a spurious zero mode; it is an integer, not a tolerance."""
    for shape in ((2, 2, 2), (3, 3, 2), (4, 3, 3)):
        _, _, _, S, _, interior = _system(*shape)
        w = np.linalg.eigvalsh(S.toarray())
        assert int((w < 1e-9 * w.max()).sum()) == interior, \
            f"{shape}: kernel dimension does not match the interior node count"


def test_whitney_identities_hold_in_3d():
    mesh = box_mesh(1.0, 0.8, 0.6, 3, 3, 2)
    space = EdgeSpace3D(mesh)
    c = 0.5 + np.arange(mesh.num_tets) % 7
    S = assemble_curlcurl_3d(space, c)
    Mt = assemble_edge_mass_3d(space, c)
    G = assemble_edge_grad_3d(space, c)
    K = assemble_stiffness_3d(mesh, c)
    e = np.arange(space.num_edges)
    lo, hi = space.edges[:, 0], space.edges[:, 1]
    C = sp.coo_matrix((np.r_[np.ones(len(e)), -np.ones(len(e))],
                       (np.r_[e, e], np.r_[hi, lo])),
                      shape=(space.num_edges, mesh.num_nodes)).tocsr()
    for name, resid, scale in (("G - M_t C", abs(G - Mt @ C).max(), abs(G).max()),
                               ("S C", abs(S @ C).max(), abs(S).max()),
                               ("K - C^T M_t C", abs(K - C.T @ Mt @ C).max(),
                                abs(K).max())):
        assert resid < 1e-11 * scale, f"{name}: {resid/scale:.2e} relative"


def test_no_spurious_mode_between_the_physical_ones(refsol):
    exact = _clusters(refsol.metallic.rect_cavity_resonances(1.0, 1.0, 1.0, n_max=3))
    flat = [k for k, mult, _ in exact for _ in range(mult)]
    got = _resonances(8, 8, 8, sigma=1.3 * exact[0][0])[:len(flat)]
    for value in got:
        nearest = min(abs(value - k) / k for k in flat)
        assert nearest < 0.05, (
            f"{value:.4f} sits between the analytic resonances "
            f"{[round(k, 4) for k in sorted(set(flat))]} — spurious mode")


@pytest.mark.slow
def test_unit_cube_resonances_converge_at_second_order(refsol):
    """Halving the mesh must quarter the error.

    Every low resonance of a cube is degenerate, and those degeneracies are
    accidental — the point group of a box is abelian, so no mesh can protect
    them. Each cluster is therefore compared through its mean, which is the
    mesh-independent quantity.
    """
    exact = _clusters(refsol.metallic.rect_cavity_resonances(1.0, 1.0, 1.0, n_max=3))
    errors = []
    for n in (6, 12):
        got = _resonances(n, n, n, sigma=1.3 * exact[0][0])
        at, row = 0, []
        for k2, mult, _ in exact:
            row.append(abs(got[at:at + mult].mean() - k2) / k2)
            at += mult
        errors.append(row)
    errors = np.array(errors)
    for j, (k2, mult, labels) in enumerate(exact):
        r = np.log(errors[0, j] / errors[1, j]) / np.log(2)
        assert r > 1.8, (
            f"{'/'.join(labels)} (k^2={k2:.4f}, multiplicity {mult}): order "
            f"{r:.2f}, errors {errors[:, j]}")


def test_the_example_agrees_with_the_answer_key(refsol):
    """examples/cavity_modes.py enumerates the spectrum itself, so that the
    example runs without the test extra. Two independent enumerations of the same
    thing are only useful if something checks they still agree."""
    import cavity_modes

    mine = cavity_modes.exact_spectrum()
    theirs = _clusters(refsol.metallic.rect_cavity_resonances(
        cavity_modes.A_BOX, cavity_modes.B_BOX, cavity_modes.C_BOX, n_max=3),
        take=8)
    for (k_mine, mult_mine, labels_mine), (k_ref, mult_ref, labels_ref) in zip(
            mine[:8], theirs):
        # the example rounds its cluster keys to eight decimals to group
        # numerically equal eigenvalues, so agreement is exact to that rounding
        assert abs(k_mine - k_ref) < 1e-7, f"{k_mine} vs {k_ref}"
        assert mult_mine == mult_ref, (
            f"k^2={k_ref:.6f}: example says multiplicity {mult_mine}, refsol "
            f"says {mult_ref}")
        assert sorted(labels_mine) == sorted(labels_ref)
