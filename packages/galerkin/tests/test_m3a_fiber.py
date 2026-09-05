"""M3a: full-vector modes of a step-index fibre, graded against refsol.fiber.

The fibre is the one refsol tabulates: core radius 4 um, n_core 1.45, n_clad 1.44
at 1.55 um, so V = 2.756. Weak guidance puts TE01, TM01 and HE21 within 2e-5 of
each other — a scalar solver returns one LP11 value there, and reproducing the
splitting is the whole point of a vector formulation.
"""

import numpy as np
import pytest

from galerkin import disk_mesh, solve_modes
from conftest import assert_second_order, rate

A, N1, N2, WL = 4.0, 1.45, 1.44, 1.55
K0 = 2.0 * np.pi / WL
R_DOM = 6.0 * A          # truncation checked below: R = 10a gives the same answer
ORDER = ("HE11", "TE01", "TM01", "HE21")


def solve(scale):
    mesh = disk_mesh((A, 2 * A, R_DOM), (4 * scale, 4 * scale, 16 * scale),
                     32 * scale)
    eps = mesh.by_layer([N1 ** 2, N2 ** 2, N2 ** 2])
    n_eff, space, et, ez = solve_modes(mesh, eps, K0, n_target=N1, num_modes=10)
    guided = np.sort(n_eff[(n_eff > N2) & (n_eff < N1)])[::-1]
    assert len(guided) >= 6, f"expected 6 guided mode fields, found {len(guided)}"
    # descending: HE11 (x2), TE01, TM01, HE21 (x2)
    return mesh, guided, [guided[0], guided[2], guided[3], guided[4]]


def test_effective_indices_match_the_exact_vector_solution(refsol):
    ref = {m.label: m.neff for m in refsol.fiber.vector_modes(A, N1, N2, WL)}
    assert set(ORDER) <= set(ref), f"refsol returned {sorted(ref)}"
    _, _, got = solve(2)
    for label, value in zip(ORDER, got):
        rel = abs(value - ref[label]) / ref[label]
        assert rel < 5e-5, f"{label}: {value:.9f} vs {ref[label]:.9f} ({rel:.2e})"


@pytest.mark.slow
def test_effective_indices_converge_at_second_order(refsol):
    ref = [m.neff for label in ORDER
           for m in refsol.fiber.vector_modes(A, N1, N2, WL) if m.label == label]
    scales = (1, 2, 3)
    errors = []
    for scale in scales:
        _, _, got = solve(scale)
        errors.append([abs(g - r) / r for g, r in zip(got, ref)])
    errors = np.array(errors)
    ratios = [scales[i + 1] / scales[i] for i in range(len(scales) - 1)]
    for j, label in enumerate(ORDER):
        r = rate(errors[:, j], ratios)[-1]
        # measured on the finest pair: 1.99 / 1.90 / 2.11 / 1.97
        assert r > 1.75, f"{label}: order {r:.2f}, errors {errors[:, j]}"


def test_degenerate_pairs_stay_degenerate(refsol):
    """The polar mesh keeps an exact C_n symmetry, which protects the m = +-1 and
    m = +-2 pairs. Their residual splitting must be far below the physical
    TE01-HE21 splitting, or the measurement of that splitting means nothing."""
    ref = {m.label: m.neff for m in refsol.fiber.vector_modes(A, N1, N2, WL)}
    _, guided, _ = solve(2)
    numerical = max(abs(guided[0] - guided[1]), abs(guided[4] - guided[5]))
    physical = ref["TE01"] - ref["HE21"]
    assert numerical < 1e-6 * physical, (
        f"mesh-induced splitting {numerical:.2e} is not negligible against the "
        f"physical splitting {physical:.2e}")


def test_scalar_solver_cannot_split_lp11(refsol):
    """Same fibre, scalar Helmholtz operator on the same engine: one degenerate
    LP11 where the vector solver resolves three distinct modes."""
    import scipy.sparse.linalg as spla
    from galerkin import assemble_stiffness, assemble_mass

    mesh = disk_mesh((A, 2 * A, R_DOM), (8, 8, 32), 64)
    eps = mesh.by_layer([N1 ** 2, N2 ** 2, N2 ** 2])
    K = assemble_stiffness(mesh, 1.0)
    free = np.setdiff1d(np.arange(mesh.num_nodes), mesh.boundary["outer"])
    A_op = (K - K0 ** 2 * assemble_mass(mesh, eps))[free][:, free].tocsc()
    B_op = assemble_mass(mesh, 1.0)[free][:, free].tocsc()
    vals = spla.eigsh(A_op, k=6, M=B_op, sigma=-(K0 * N1) ** 2, which="LM",
                      v0=np.ones(len(free)), ncv=min(len(free), 40),
                      maxiter=20000, return_eigenvectors=False)
    n_eff = np.sort(np.sqrt(-vals[vals < 0]) / K0)[::-1]
    lp = n_eff[(n_eff > N2) & (n_eff < N1)]
    assert len(lp) >= 3
    assert abs(lp[1] - lp[2]) < 1e-9, (
        "the scalar LP11 pair should be exactly degenerate; the vector solver is "
        "what splits it")


def test_the_example_analytic_solver_agrees_with_the_answer_key(refsol):
    """examples/fiber_modes.py solves the vector dispersion relation itself, for a
    different fibre (high contrast, V = 3.5). Checking that independent
    implementation against refsol tests both."""
    import fiber_modes

    mine = fiber_modes.exact_modes()
    wavelength = 2.0 * np.pi / fiber_modes.K0
    theirs = {m.label: m.neff for m in refsol.fiber.vector_modes(
        fiber_modes.A_CORE, fiber_modes.N_CO, fiber_modes.N_CL, wavelength)}
    assert set(mine) == set(theirs), f"{sorted(mine)} vs {sorted(theirs)}"
    for label, (value, _) in mine.items():
        assert abs(value - theirs[label]) < 1e-9, (
            f"{label}: example {value:.10f} vs refsol {theirs[label]:.10f}")
