"""M3a against published benchmarks: Hadley (2002).

Unit square, wavelength 1.5, a square core [0,0.5]^2 in one corner, PEC on two
sides and PMC (the natural, do-nothing condition for this formulation) on the
other two. Reference effective indices are quoted to +-1e-8 in

    G. R. Hadley, J. Lightwave Technol. 20(7), 1210-1218 (2002)

That uncertainty is the reference's, not a target: a lowest-order method on a
uniform mesh is limited by its own discretization long before 1e-8, and one of
the four cases is limited by something more interesting than that — see below.
"""

import functools

import numpy as np
import pytest

from galerkin import rectangle_mesh, solve_modes, from_mesher
from conftest import rate

# Case 3 has the high-index region wrapping a re-entrant dielectric corner, and
# its field singularity is strong enough to halve the convergence order. That is
# the phenomenon Hadley's paper exists to treat, so it is recorded rather than
# asserted away.
SECOND_ORDER_CASES = (0, 1, 2)


def _solve_corner(case, n):
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
    err = abs(_solve_corner(case, 48) - case.neff) / case.neff
    assert err < 1e-4, (
        f"case {index} (eps {case.eps_core}/{case.eps_clad}, PEC "
        f"{case.pec_sides}): {err:.2e} from the published value")


@pytest.mark.slow
@pytest.mark.parametrize("index", SECOND_ORDER_CASES)
def test_dielectric_corner_converges_at_second_order(refsol, index):
    case = refsol.benchmarks.DIELECTRIC_CORNERS[index]
    errors = [abs(_solve_corner(case, n) - case.neff) / case.neff for n in (24, 48, 96)]
    assert rate(errors)[-1] > 1.8, f"case {index}: rates {rate(errors)}"


@pytest.mark.slow
def test_reentrant_corner_converges_but_only_at_first_order(refsol):
    """The one case that does not reach second order, pinned down rather than
    excused: it still converges monotonically, just at about order one."""
    case = refsol.benchmarks.DIELECTRIC_CORNERS[3]
    errors = [abs(_solve_corner(case, n) - case.neff) / case.neff for n in (48, 96, 144)]
    assert errors[0] > errors[1] > errors[2], f"not converging: {errors}"
    observed = rate(errors, refinement=2.0)[0]
    assert 0.5 < observed < 1.8, (
        f"expected roughly first order from the re-entrant corner, got {observed:.2f}"
        " — if this has improved, the tolerance above should be tightened")


# ---------------------- the rib waveguide family (8 cases) -------------------
meshine = pytest.importorskip("meshine")

SIZE_CORE, SIZE_FAR = 0.12, 1.0
SLABS = (0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7)


@functools.lru_cache(maxsize=None)
def _solve_rib_cached(slab, core_width, core_thickness, n_core, n_sub, n_cov,
                      wavelength, size_core, size_far):
    from meshine import shapes, generate
    domain, namer = shapes.rib_waveguide(
        slab_thickness=slab, core_width=core_width,
        core_thickness=core_thickness, size_core=size_core, size_far=size_far)
    mesh = from_mesher(generate(domain, namer, min_angle=28))
    eps = mesh.by_region({"core": n_core ** 2, "box": n_sub ** 2,
                          "clad": n_cov ** 2})
    k0 = 2.0 * np.pi / wavelength
    pec = np.unique(np.concatenate(list(mesh.boundary.values())))
    n_eff, _, _, _ = solve_modes(mesh, eps, k0, n_target=n_core, num_modes=6,
                                 pec_nodes=pec)
    guided = np.sort(n_eff[(n_eff > n_sub) & (n_eff < n_core)])[::-1]
    assert len(guided), f"no guided mode; raw {n_eff[:4]}"
    return float(guided[0])


def _solve_rib(case, size_core, size_far):
    return _solve_rib_cached(case.slab_thickness_um, case.rib_width_um,
                             case.core_thickness_um, case.n_core,
                             case.n_substrate, case.n_cover,
                             case.wavelength_um, size_core, size_far)


def _rib_case(refsol, slab):
    matches = [c for c in refsol.benchmarks.RIB_WAVEGUIDES
               if c.slab_thickness_um == slab]
    assert matches, f"refsol has no rib case with slab {slab}"
    return matches[0]


@pytest.mark.parametrize("slab", SLABS)
def test_rib_waveguide_matches_the_published_value(refsol, slab):
    """All eight of the tabulated slab thicknesses, from the strip waveguide
    (slab 0) to the nearly-planar 0.7 um case."""
    case = _rib_case(refsol, slab)
    value = _solve_rib(case, SIZE_CORE, SIZE_FAR)
    rel = abs(value - case.neff_quasi_te) / case.neff_quasi_te
    assert rel < 2e-4, (
        f"slab {slab}: {value:.7f} vs Hadley's {case.neff_quasi_te} ({rel:.2e})")


def test_rib_family_reproduces_the_published_trend(refsol):
    """A per-case tolerance can be met while the family trend is wrong. The
    published indices rise monotonically with slab thickness by only 2e-3 in
    total, so reproducing the ORDER is a sharper test than any single value."""
    cases = [_rib_case(refsol, s) for s in SLABS]
    computed = [_solve_rib(c, SIZE_CORE, SIZE_FAR) for c in cases]
    published = [c.neff_quasi_te for c in cases]
    assert all(b > a for a, b in zip(computed, computed[1:])), (
        f"not monotonic in slab thickness: {computed}")
    # the published spread across the family is 2.08e-3; the computed one is
    # reproduced to 9.4e-5, which is the difference of two per-case errors of
    # about 1e-4 each rather than an independent quantity
    spread_ok = abs((computed[-1] - computed[0]) - (published[-1] - published[0]))
    assert spread_ok < 1.5e-4, (
        f"spread across the family {computed[-1]-computed[0]:.6f} vs published "
        f"{published[-1]-published[0]:.6f}")


@pytest.mark.slow
def test_rib_waveguide_error_falls_under_refinement(refsol):
    """meshine's size control is a target, not a uniform halving, so what can be
    asserted is that refining helps — the clean second-order ladder lives on the
    structured meshes galerkin builds itself."""
    case = _rib_case(refsol, 0.3)
    errors = [abs(_solve_rib(case, sc, sf) - case.neff_quasi_te)
              / case.neff_quasi_te
              for sc, sf in ((0.20, 1.6), (0.12, 1.0), (0.08, 0.7))]
    assert errors[-1] < errors[0] / 2, f"refinement did not help: {errors}"
    assert errors[-1] < 1e-4, f"finest mesh still {errors[-1]:.2e} off"
