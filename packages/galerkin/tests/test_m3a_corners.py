"""M3a against a published benchmark: Hadley's dielectric-corner problems.

Unit square, wavelength 1.5, a square core [0,0.5]^2 in one corner, PEC on two
sides and PMC (the natural, do-nothing condition for this formulation) on the
other two. Reference effective indices are quoted to +-1e-8 in

    G. R. Hadley, J. Lightwave Technol. 20(7), 1210-1218 (2002)

That uncertainty is the reference's, not a target: a lowest-order method on a
uniform mesh is limited by its own discretization long before 1e-8, and one of
the four cases is limited by something more interesting than that — see below.
"""

import numpy as np
import pytest

from galerkin import rectangle_mesh, solve_modes
from conftest import rate

# Case 3 has the high-index region wrapping a re-entrant dielectric corner, and
# its field singularity is strong enough to halve the convergence order. That is
# the phenomenon Hadley's paper exists to treat, so it is recorded rather than
# asserted away.
SECOND_ORDER_CASES = (0, 1, 2)


def solve(case, n):
    w, h = case.domain
    cw, ch = case.core_box
    k0 = 2.0 * np.pi / case.wavelength
    mesh = rectangle_mesh(w, h, n, n)
    c = mesh.nodes[mesh.triangles].mean(axis=1)
    eps = np.where((c[:, 0] < cw) & (c[:, 1] < ch), case.eps_core, case.eps_clad)
    pec = np.unique(np.concatenate([mesh.boundary[s] for s in case.pec_sides]))
    n_hi = np.sqrt(max(case.eps_core, case.eps_clad))
    n_lo = np.sqrt(min(case.eps_core, case.eps_clad))
    n_eff, _, _, _ = solve_modes(mesh, eps, k0, n_target=n_hi, num_modes=8,
                                 pec_nodes=pec)
    guided = np.sort(n_eff[(n_eff > n_lo) & (n_eff < n_hi)])[::-1]
    assert len(guided), f"no guided mode in ({n_lo:.3f}, {n_hi:.3f})"
    return guided[0]


@pytest.mark.parametrize("index", range(4))
def test_dielectric_corner_effective_index(refsol, index):
    case = refsol.benchmarks.DIELECTRIC_CORNERS[index]
    err = abs(solve(case, 48) - case.neff) / case.neff
    assert err < 1e-4, (
        f"case {index} (eps {case.eps_core}/{case.eps_clad}, PEC "
        f"{case.pec_sides}): {err:.2e} from the published value")


@pytest.mark.slow
@pytest.mark.parametrize("index", SECOND_ORDER_CASES)
def test_dielectric_corner_converges_at_second_order(refsol, index):
    case = refsol.benchmarks.DIELECTRIC_CORNERS[index]
    errors = [abs(solve(case, n) - case.neff) / case.neff for n in (24, 48, 96)]
    assert rate(errors)[-1] > 1.8, f"case {index}: rates {rate(errors)}"


@pytest.mark.slow
def test_reentrant_corner_converges_but_only_at_first_order(refsol):
    """The one case that does not reach second order, pinned down rather than
    excused: it still converges monotonically, just at about order one."""
    case = refsol.benchmarks.DIELECTRIC_CORNERS[3]
    errors = [abs(solve(case, n) - case.neff) / case.neff for n in (48, 96, 144)]
    assert errors[0] > errors[1] > errors[2], f"not converging: {errors}"
    observed = rate(errors, refinement=2.0)[0]
    assert 0.5 < observed < 1.8, (
        f"expected roughly first order from the re-entrant corner, got {observed:.2f}"
        " — if this has improved, the tolerance above should be tightened")
