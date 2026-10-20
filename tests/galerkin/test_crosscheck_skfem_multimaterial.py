# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Per-region materials solved with galerkin and scikit-fem on the same meshes.

Every case uses the same nodes, triangles, per-triangle material values,
loads and constraints in both tools, so the discrete solutions must agree;
differences are gated at 1e-9 relative (observed 1.6e-12 or smaller). This is
code-to-code evidence only: the analytical per-region gates in
test_*_multimaterial.py and docs/packages/galerkin/multimaterial.md are
unchanged, and agreement between the tools is not convergence evidence.
"""

import numpy as np
import pytest

from crosscheck import Stopwatch, emit, make_record, observable, relative_difference, require_tool
from galerkin.elasticity import solve_elasticity
from galerkin.mesh import layered_rectangle_mesh
from galerkin.thermal import solve_steady_heat
from galerkin.thermoelasticity import freeze_temperature, solve_thermoelasticity
from galerkin.transient_heat import solve_transient_heat

SAME = 1e-9  # identical discretizations: relative difference gate
ACCEPTANCE = "tests/galerkin/test_{}_multimaterial.py (docs/packages/galerkin/multimaterial.md)"
NAMES = ["copper", "insulation", "steel"]


@pytest.fixture(scope="module")
def skfem():
    return require_tool("scikit-fem")


def _wall():
    """Three layers 20/30/10 mm, 20 mm high, interfaces on mesh lines."""
    return layered_rectangle_mesh([.02, .05, .06], .02, [4, 6, 2], 4, NAMES)


def _per_triangle(mesh, values):
    return mesh.by_region(dict(zip(NAMES, values)))


def _basis(skfem, mesh, element):
    return skfem.Basis(skfem.MeshTri(mesh.nodes.T.copy(), mesh.triangles.T.copy()), element)


def _field(basis, values):
    """Per-triangle constants at every quadrature point of basis."""
    return np.repeat(np.asarray(values, dtype=float)[:, None], basis.X.shape[1], axis=1)


def _dofs_on(basis, nodes):
    """Global dofs of the given mesh nodes (all components for a vector element)."""
    return basis.nodal_dofs[:, nodes].ravel()


def _skfem_heat_forms(skfem):
    from skfem.helpers import dot, grad

    @skfem.BilinearForm
    def conduction(u, v, w):
        return w.k * dot(grad(u), grad(v))

    @skfem.BilinearForm
    def capacity(u, v, w):
        return w.c * u * v

    @skfem.LinearForm
    def source(v, w):
        return w.q * v

    return conduction, capacity, source


def test_heat_p1_three_region_wall_same_mesh(skfem):
    mesh = _wall()
    k, q = [15., .8, 45.], [2e5, -3e4, 6e5]
    left, right = mesh.boundary["left"], mesh.boundary["right"]
    dirichlet = {int(i): 420. for i in left} | {int(i): 300. for i in right}
    clock = Stopwatch()
    with clock("openphysics"):
        ours = solve_steady_heat(mesh, conductivity=dict(zip(NAMES, k)), dirichlet=dirichlet,
                                 heat_source=dict(zip(NAMES, q)))
    conduction, _, source = _skfem_heat_forms(skfem)
    with clock("reference"):
        basis = _basis(skfem, mesh, skfem.ElementTriP1())
        kt, qt = _per_triangle(mesh, k), _per_triangle(mesh, q)
        A = conduction.assemble(basis, k=_field(basis, kt))
        b = source.assemble(basis, q=_field(basis, qt))
        x = np.zeros(basis.N)
        x[left], x[right] = 420., 300.
        fixed = np.concatenate([left, right])
        theirs = skfem.solve(*skfem.condense(A, b, x=x, D=fixed))
    flux = -(kt[:, None] * basis.interpolate(theirs).grad[:, :, 0].T)
    emit(make_record(
        case="heat-p1-three-region-wall", analytical_acceptance=ACCEPTANCE.format("thermal"),
        stopwatch=clock, physics="2D steady heat conduction, per-region k and Q",
        api="galerkin.thermal.solve_steady_heat", discretization="P1 Lagrange triangles",
        tool="scikit-fem", tool_discretization="ElementTriP1, per-triangle k and Q",
        matched=["same nodes and triangles (layered_rectangle_mesh 20/30/10 mm x 20 mm, [4, 6, 2] x 4)",
                 "k = 15/0.8/45 W/(m K), Q = 2e5/-3e4/6e5 W/m^3 by region",
                 "Dirichlet 420 K left, 300 K right", "insulated top and bottom",
                 "exact integration of the piecewise-constant load"],
        not_matched=[],
        observables=[
            observable("nodal temperature", "K", "max relative difference",
                       relative_difference(ours.temperature, theirs), SAME),
            observable("element heat flux", "W/m^2", "max relative difference",
                       relative_difference(ours.heat_flux, flux), SAME)]))


def _lame(e, nu, plane):
    lam, mu = e * nu / ((1 + nu) * (1 - 2 * nu)), e / (2 * (1 + nu))
    if plane == "stress":
        lam = 2 * lam * mu / (lam + 2 * mu)
    return lam, mu


def _skfem_mechanics(skfem, mesh, plane, e, nu, *, body=(0., 0.), thermal=None):
    """P1 plane elasticity with per-triangle E, nu and an optional thermal stress.

    thermal: per-triangle beta*(mean T - Tref) with beta = E alpha/(1-nu) (plane
    stress) or E alpha/(1-2 nu) (plane strain); its load is beta dT div v.
    """
    from skfem.helpers import ddot, div, eye, sym_grad, trace

    @skfem.BilinearForm
    def elastic(u, v, w):
        eps = sym_grad(u)
        return ddot(2. * w.mu * eps + w.lam * eye(trace(eps), 2), sym_grad(v))

    @skfem.LinearForm
    def load(v, w):
        return body[0] * v[0] + body[1] * v[1] + w.s * div(v)

    basis = _basis(skfem, mesh, skfem.ElementVector(skfem.ElementTriP1()))
    lam, mu = _lame(e, nu, plane)
    K = elastic.assemble(basis, lam=_field(basis, lam), mu=_field(basis, mu))
    f = load.assemble(basis, s=_field(basis, np.zeros(len(e)) if thermal is None else thermal))
    fixed = _dofs_on(basis, mesh.boundary["left"])
    u = skfem.solve(*skfem.condense(K, f, D=fixed))
    grad = basis.interpolate(u).grad[:, :, :, 0]           # (2 comps, 2 dirs, M), constant on P1
    exx, eyy, gxy = grad[0, 0], grad[1, 1], grad[0, 1] + grad[1, 0]
    s = np.zeros(len(e)) if thermal is None else thermal
    stress = np.column_stack([(lam + 2 * mu) * exx + lam * eyy - s, lam * exx + (lam + 2 * mu) * eyy - s,
                              mu * gxy])
    return u[basis.nodal_dofs].T, stress


@pytest.mark.parametrize("plane", ["strain", "stress"])
def test_elasticity_p1_three_region_bar_same_mesh(skfem, plane):
    mesh = _wall()
    e, nu, body = [1.2e11, 5e9, 2e11], [.34, .2, .29], (0., -8e4)
    dirichlet = {(int(i), c): 0. for i in mesh.boundary["left"] for c in (0, 1)}
    clock = Stopwatch()
    with clock("openphysics"):
        ours = solve_elasticity(mesh, young_modulus=dict(zip(NAMES, e)), poisson_ratio=dict(zip(NAMES, nu)),
                                plane=plane, dirichlet=dirichlet, body_force=body)
    with clock("reference"):
        displacement, stress = _skfem_mechanics(skfem, mesh, plane, _per_triangle(mesh, e),
                                                _per_triangle(mesh, nu), body=body)
    emit(make_record(
        case=f"elasticity-p1-plane-{plane}-three-region-bar",
        analytical_acceptance=ACCEPTANCE.format("elasticity"), stopwatch=clock,
        physics=f"2D linear elasticity, plane {plane}, per-region E and nu, clamped left edge, gravity load",
        api="galerkin.elasticity.solve_elasticity", discretization="P1 Lagrange triangles",
        tool="scikit-fem", tool_discretization="ElementVector(ElementTriP1), per-triangle Lame parameters",
        matched=["same nodes and triangles as the heat case",
                 "E = 120/5/200 GPa, nu = 0.34/0.2/0.29 by region", f"plane {plane} constitutive law",
                 "both components fixed on the left edge", "body force (0, -8e4) N/m^3"],
        not_matched=[],
        observables=[
            observable("nodal displacement", "m", "max relative difference",
                       relative_difference(ours.displacement, displacement), SAME),
            observable("element stress (sxx, syy, sxy)", "Pa", "max relative difference",
                       relative_difference(ours.stress, stress), SAME)]))


@pytest.mark.parametrize("plane", ["strain", "stress"])
def test_thermoelasticity_p1_three_region_bar_same_mesh(skfem, plane):
    mesh = _wall()
    e, nu, alpha, tref = [1.2e11, 5e9, 2e11], [.34, .2, .29], [1.7e-5, 6e-5, 1.2e-5], 293.15
    x, y = mesh.nodes.T
    temperature = 300. + 2e3 * x + 4e4 * y**2
    dirichlet = {(int(i), c): 0. for i in mesh.boundary["left"] for c in (0, 1)}
    clock = Stopwatch()
    with clock("openphysics"):
        ours = solve_thermoelasticity(mesh, freeze_temperature(mesh, temperature), reference_temperature_k=tref,
                                      thermal_expansion_per_k=dict(zip(NAMES, alpha)),
                                      young_modulus=dict(zip(NAMES, e)), poisson_ratio=dict(zip(NAMES, nu)),
                                      plane=plane, dirichlet=dirichlet)
    with clock("reference"):
        et, nut, at = (_per_triangle(mesh, v) for v in (e, nu, alpha))
        beta = et * at / ((1 - nut) if plane == "stress" else (1 - 2 * nut))
        mean = temperature[mesh.triangles].mean(axis=1)
        displacement, stress = _skfem_mechanics(skfem, mesh, plane, et, nut, thermal=beta * (mean - tref))
    emit(make_record(
        case=f"thermoelasticity-p1-plane-{plane}-three-region-bar",
        analytical_acceptance=ACCEPTANCE.format("thermoelastic"), stopwatch=clock,
        physics=f"2D thermoelasticity under a prescribed nodal temperature, plane {plane}, per-region alpha, E, nu",
        api="galerkin.thermoelasticity.solve_thermoelasticity", discretization="P1 Lagrange triangles",
        tool="scikit-fem",
        tool_discretization="ElementVector(ElementTriP1); thermal load beta (T_h - Tref) div v, per-triangle beta",
        matched=["same nodes and triangles as the heat case", "E, nu as the elasticity case",
                 "alpha = 1.7e-5/6e-5/1.2e-5 1/K by region", "nodal T = 300 + 2e3 x + 4e4 y^2 K, Tref = 293.15 K",
                 "both components fixed on the left edge, no body force or traction"],
        not_matched=[],
        observables=[
            observable("nodal displacement", "m", "max relative difference",
                       relative_difference(ours.displacement, displacement), SAME),
            observable("element stress (sxx, syy, sxy)", "Pa", "max relative difference",
                       relative_difference(ours.stress, stress), SAME)]))


def test_transient_heat_p1_three_region_wall_same_mesh(skfem):
    mesh = _wall()
    k, c, q = [15., .8, 45.], [3.4e6, 1.2e6, 3.6e6], [2e5, -3e4, 6e5]
    times = np.array([0., .5, 1., 2., 3.5, 5., 7.5, 10.])
    left, right = mesh.boundary["left"], mesh.boundary["right"]
    initial = np.full(len(mesh.nodes), 300.)
    initial[left] = 420.
    dirichlet = {int(i): 420. for i in left} | {int(i): 300. for i in right}
    clock = Stopwatch()
    with clock("openphysics"):
        ours = solve_transient_heat(mesh, conductivity=dict(zip(NAMES, k)),
                                    volumetric_heat_capacity=dict(zip(NAMES, c)),
                                    heat_source=dict(zip(NAMES, q)), time_s=times,
                                    initial_temperature_k=initial, dirichlet=dirichlet)
    conduction, capacity, source = _skfem_heat_forms(skfem)
    with clock("reference"):
        basis = _basis(skfem, mesh, skfem.ElementTriP1())
        K = conduction.assemble(basis, k=_field(basis, _per_triangle(mesh, k)))
        M = capacity.assemble(basis, c=_field(basis, _per_triangle(mesh, c)))
        f = source.assemble(basis, q=_field(basis, _per_triangle(mesh, q)))
        fixed = np.concatenate([left, right])
        history = [initial.copy()]
        for dt in np.diff(times):
            x = np.zeros(basis.N)
            x[left], x[right] = 420., 300.
            history.append(skfem.solve(*skfem.condense((M / dt + K).tocsr(), f + M @ history[-1] / dt,
                                                       x=x, D=fixed)))
        theirs = np.array(history)
    emit(make_record(
        case="transient-heat-p1-three-region-wall", analytical_acceptance=ACCEPTANCE.format("transient_heat"),
        stopwatch=clock, physics="2D transient heat, backward Euler, per-region k, c and Q",
        api="galerkin.transient_heat.solve_transient_heat",
        discretization="P1 Lagrange triangles, consistent mass, backward Euler",
        tool="scikit-fem",
        tool_discretization="ElementTriP1 stiffness and consistent mass, backward Euler written in the test",
        matched=["same nodes and triangles as the heat case", "k and Q as the heat case",
                 "c = 3.4e6/1.2e6/3.6e6 J/(m^3 K) by region",
                 "uniform 300 K start with the left nodes at 420 K", "Dirichlet 420 K left, 300 K right",
                 "same unequal steps: 0, 0.5, 1, 2, 3.5, 5, 7.5, 10 s"],
        not_matched=["linear solver (galerkin factorization with its offsets and refinement, reference "
                     "scikit-fem condense and solve)"],
        observables=[observable("nodal temperature at every stored time", "K", "max relative difference",
                                relative_difference(ours.temperature_k, theirs), SAME)]))
