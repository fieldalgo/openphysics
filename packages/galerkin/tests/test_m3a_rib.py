"""M3a on an unstructured mesh: Hadley's rib waveguide.

The geometry has re-entrant dielectric corners where the rib meets the slab, and
the reference (femwell's tabulation of Hadley 2002, stated to 3e-6) is a
published number rather than a closed form. Both facts matter for what can be
asserted: the achievable accuracy here is a few times 1e-5, set by the corners
and by lowest-order elements, not by the reference.

The mesh comes from `meshine`, which grades element size by region, so this also
exercises the adapter on a mesh galerkin did not build.
"""

import numpy as np
import pytest

from galerkin import from_mesher, solve_modes

meshine = pytest.importorskip("meshine")

SLAB = 0.3


def solve(case, size_core, size_far):
    from meshine import shapes, generate
    domain, namer = shapes.rib_waveguide(
        slab_thickness=case.slab_thickness_um, core_width=case.rib_width_um,
        core_thickness=case.core_thickness_um, size_core=size_core,
        size_far=size_far)
    mesh = from_mesher(generate(domain, namer, min_angle=28))
    eps = mesh.by_region({"core": case.n_core ** 2,
                          "box": case.n_substrate ** 2,
                          "clad": case.n_cover ** 2})
    k0 = 2.0 * np.pi / case.wavelength_um
    pec = np.unique(np.concatenate(list(mesh.boundary.values())))
    n_eff, _, _, _ = solve_modes(mesh, eps, k0, n_target=case.n_core,
                                 num_modes=6, pec_nodes=pec)
    guided = np.sort(n_eff[(n_eff > case.n_substrate)
                           & (n_eff < case.n_core)])[::-1]
    assert len(guided), f"no guided mode; raw {n_eff[:4]}"
    return guided[0]


def _case(refsol, slab):
    return [c for c in refsol.benchmarks.RIB_WAVEGUIDES
            if c.slab_thickness_um == slab][0]


def test_rib_waveguide_matches_the_published_value(refsol):
    case = _case(refsol, SLAB)
    err = abs(solve(case, 0.1, 0.8) - case.neff_quasi_te) / case.neff_quasi_te
    assert err < 2e-4, f"{err:.2e} from Hadley's {case.neff_quasi_te}"


@pytest.mark.slow
def test_rib_waveguide_error_falls_under_refinement(refsol):
    """meshine's size control is a target, not a uniform halving, so what can be
    asserted is that refining helps — the clean second-order ladder lives on the
    structured meshes galerkin builds itself."""
    case = _case(refsol, SLAB)
    errors = [abs(solve(case, sc, sf) - case.neff_quasi_te) / case.neff_quasi_te
              for sc, sf in ((0.15, 1.2), (0.10, 0.8), (0.07, 0.6))]
    assert errors[-1] < errors[0] / 2, f"refinement did not help: {errors}"
    assert errors[-1] < 1e-4, f"finest mesh still {errors[-1]:.2e} off"
