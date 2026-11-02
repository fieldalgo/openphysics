# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Boundary loads and boundary terms solved with galerkin and scikit-fem on the same meshes.

Three boundary formulations that the other comparison modules do not cover:
prescribed outward heat flux and convection (Robin) edges of
galerkin.thermal.solve_steady_heat, Cartesian traction edges of
galerkin.elasticity.solve_elasticity, and the first-order absorbing (Robin)
boundary of the Helmholtz assembly (assemble_boundary_mass with a complex
coefficient). Every case uses the same nodes, triangles, coefficients and
boundary data in both tools, and the reference selects the very same edges by
their node pairs, so the discrete systems must agree; differences are gated
at 1e-9 relative. Boundary data are polynomials of degree <= 3, so galerkin's
four-point Gauss edge rule and the reference's order-7 facet quadrature both
integrate them exactly. This is code-to-code evidence only; the analytical
gates of each feature are unchanged, and agreement is not convergence evidence.
"""

import numpy as np
import pytest

from crosscheck import Stopwatch, emit, make_record, observable, relative_difference, require_tool
from galerkin import (annulus_mesh, assemble_boundary_mass, assemble_mass, assemble_stiffness,
                      solve_dirichlet)
from galerkin.elasticity import solve_elasticity
from galerkin.mesh import rectangle_mesh
from galerkin.thermal import solve_steady_heat

SAME = 1e-9  # identical discretizations: relative difference gate
FACET_ORDER = 7  # reference facet quadrature; exact for the polynomial boundary data below


@pytest.fixture(scope="module")
def skfem():
    return require_tool("scikit-fem")


def _reference_mesh(skfem, mesh):
    return skfem.MeshTri(mesh.nodes.T.copy(), mesh.triangles.T.copy())


def _facets(reference_mesh, edges):
    """Reference facet indices of galerkin's edges, matched by their node pairs."""
    lookup = {tuple(f): i for i, f in enumerate(reference_mesh.facets.T)}
    return np.array([lookup[tuple(sorted(map(int, e)))] for e in edges])


def _dense(matrix):
    return np.asarray(matrix.todense())


# --- steady heat: outward flux and convection -----------------------------------------------

HEAT = dict(k=2.5, q=5.0, h_right=10.0, ambient_right=300.0, g_right=0.7, h_left=8.0,
            ambient_left=320.0, t_left=320.0)


def _g_top(x, y, nx, ny):
    """Outward flux on the top edge, W/m^2: a quadratic in x plus a constant vector . n."""
    return 0.3 + 0.9 * x - 0.4 * x**2 + 2.0 * nx - 1.5 * ny


def _h_bottom(x, y):
    return 4.0 + 3.0 * x  # W/(m^2 K)


def _ambient_bottom(x, y):
    return 290.0 + 20.0 * x - 10.0 * x**2  # K


def _heat_data(mesh, case):
    """galerkin's boundary arguments: edge-tag keyed scalars and (points, normals) callbacks."""
    flux = {"right": HEAT["g_right"],
            "top": lambda p, n: _g_top(p[:, 0], p[:, 1], n[:, 0], n[:, 1])}
    convection = {"right": (HEAT["h_right"], HEAT["ambient_right"]),
                  "bottom": (lambda p, n: _h_bottom(p[:, 0], p[:, 1]),
                             lambda p, n: _ambient_bottom(p[:, 0], p[:, 1]))}
    if case == "robin":
        convection["left"] = (HEAT["h_left"], HEAT["ambient_left"])
        dirichlet = {}
    else:
        dirichlet = {int(i): HEAT["t_left"] for i in mesh.boundary["left"]}
    return dirichlet, flux, convection


def _skfem_heat(skfem, mesh, case):
    """Independent P1 assembly of K + H, fQ + B - G with the same edges and data."""
    from skfem.helpers import dot, grad
    m = _reference_mesh(skfem, mesh)
    basis = skfem.Basis(m, skfem.ElementTriP1())
    k, q = HEAT["k"], HEAT["q"]

    @skfem.BilinearForm
    def conduction(u, v, w):
        return k * dot(grad(u), grad(v))

    @skfem.LinearForm
    def source(v, w):
        return q * v

    def facet_basis(tag):
        return skfem.FacetBasis(m, skfem.ElementTriP1(), facets=_facets(m, mesh.boundary_edges[tag]),
                                intorder=FACET_ORDER)

    @skfem.LinearForm
    def flux_right(v, w):
        return HEAT["g_right"] * v

    @skfem.LinearForm
    def flux_top(v, w):
        return _g_top(w.x[0], w.x[1], w.n[0], w.n[1]) * v

    @skfem.BilinearForm
    def robin_right(u, v, w):
        return HEAT["h_right"] * u * v

    @skfem.LinearForm
    def ambient_right(v, w):
        return HEAT["h_right"] * HEAT["ambient_right"] * v

    @skfem.BilinearForm
    def robin_bottom(u, v, w):
        return _h_bottom(w.x[0], w.x[1]) * u * v

    @skfem.LinearForm
    def ambient_bottom(v, w):
        return _h_bottom(w.x[0], w.x[1]) * _ambient_bottom(w.x[0], w.x[1]) * v

    @skfem.BilinearForm
    def robin_left(u, v, w):
        return HEAT["h_left"] * u * v

    @skfem.LinearForm
    def ambient_left(v, w):
        return HEAT["h_left"] * HEAT["ambient_left"] * v

    K = conduction.assemble(basis)
    f = source.assemble(basis)
    right, top, bottom = facet_basis("right"), facet_basis("top"), facet_basis("bottom")
    G = flux_right.assemble(right) + flux_top.assemble(top)
    H_right = robin_right.assemble(right)
    H = (H_right + robin_bottom.assemble(bottom)).tocsr()
    B = ambient_right.assemble(right) + ambient_bottom.assemble(bottom)
    if case == "robin":
        left = facet_basis("left")
        H = (H + robin_left.assemble(left)).tocsr()
        B = B + ambient_left.assemble(left)
    A = (K + H).tocsr()
    rhs = f + B - G
    fixed = np.array([], dtype=int) if case == "robin" else np.asarray(mesh.boundary["left"])
    if len(fixed):
        x = np.zeros(basis.N)
        x[fixed] = HEAT["t_left"]
        T = skfem.solve(*skfem.condense(A, rhs, x=x, D=fixed))
    else:
        T = skfem.solve(A, rhs)
    flux = -k * basis.interpolate(T).grad[:, :, 0].T  # constant per P1 triangle
    reaction = np.zeros(basis.N)
    reaction[fixed] = (A @ T - rhs)[fixed]
    return dict(K=K, H_right=H_right, f=f, G=G, B=B, rhs=rhs, T=T, flux=flux,
                C=H @ T - B, reaction=reaction, fixed=fixed)


@pytest.mark.parametrize("case", ["mixed", "robin"])
def test_heat_p1_flux_robin_same_mesh(skfem, case):
    mesh = rectangle_mesh(1.0, 0.8, 10, 8)
    dirichlet, flux, convection = _heat_data(mesh, case)
    clock = Stopwatch()
    with clock("openphysics"):
        ours = solve_steady_heat(mesh, conductivity=HEAT["k"], dirichlet=dirichlet,
                                 heat_source=HEAT["q"], outward_flux=flux, convection=convection)
        K = assemble_stiffness(mesh, HEAT["k"])
        H_right = assemble_boundary_mass(mesh, mesh.boundary_edges["right"], HEAT["h_right"])
    with clock("reference"):
        theirs = _skfem_heat(skfem, mesh, case)
    observables = [
        observable("nodal temperature", "K", "max relative difference",
                   relative_difference(ours.temperature, theirs["T"]), SAME),
        observable("element heat flux", "W/m^2", "max relative difference",
                   relative_difference(ours.heat_flux, theirs["flux"]), SAME),
        observable("stiffness matrix K (assemble_stiffness)", "W/K", "max relative difference",
                   relative_difference(_dense(K), _dense(theirs["K"])), SAME),
        observable("Robin boundary mass H on the right edge (assemble_boundary_mass)", "W/K",
                   "max relative difference", relative_difference(_dense(H_right), _dense(theirs["H_right"])),
                   SAME),
        observable("volumetric load fQ", "W/m", "max relative difference",
                   relative_difference(ours.load, theirs["f"]), SAME),
        observable("prescribed outward load G", "W/m", "max relative difference",
                   relative_difference(ours.prescribed_outward_load, theirs["G"]), SAME),
        observable("ambient load B", "W/m", "max relative difference",
                   relative_difference(ours.ambient_load, theirs["B"]), SAME),
        observable("system right-hand side fQ + B - G", "W/m", "max relative difference",
                   relative_difference(ours.system_rhs, theirs["rhs"]), SAME),
        observable("convective outward rate C = H T - B", "W/m", "max relative difference",
                   relative_difference(ours.convective_outward, theirs["C"]), SAME)]
    if case == "mixed":
        observables.append(observable("reaction at the Dirichlet nodes", "W/m", "max relative difference",
                                      relative_difference(ours.reaction, theirs["reaction"]), SAME))
    anchor = ("Dirichlet 320 K on the left edge" if case == "mixed"
              else "no Dirichlet node; convection h = 8 W/(m^2 K), ambient 320 K on the left edge")
    emit(make_record(
        case=f"heat-p1-flux-robin-{case}-slab",
        analytical_acceptance="tests/galerkin/test_thermal_boundary.py (docs/packages/galerkin/thermal_flux_robin.md)",
        stopwatch=clock,
        physics="2D steady heat conduction with prescribed outward flux and convection edges"
                + (", Robin support only" if case == "robin" else ", mixed Dirichlet and Robin"),
        api="galerkin.thermal.solve_steady_heat (and assemble_stiffness, assemble_boundary_mass)",
        discretization="P1 Lagrange triangles, four-point Gauss edge rule",
        tool="scikit-fem", tool_discretization=f"ElementTriP1, FacetBasis intorder {FACET_ORDER}",
        matched=["same nodes and triangles (rectangle_mesh 1 m x 0.8 m, 10 x 8)",
                 "same edges selected by node pairs for every tag",
                 "k = 2.5 W/(m K), Q = 5 W/m^3 (constant: exact in both load rules)", anchor,
                 "outward flux 0.7 W/m^2 on the right edge; on the top edge a quadratic in x plus a constant vector dotted with the outward normal",
                 "convection h = 10 W/(m^2 K), ambient 300 K on the right edge; h linear and ambient quadratic in x on the bottom edge",
                 "flux and convection share the right edge (additive)",
                 "polynomial boundary data of degree <= 3: both edge rules exact"],
        not_matched=["absolute temperature offset: galerkin solves for the increment from a per-component anchor "
                     "and adds it back; the reference solves the absolute system"],
        observables=observables))


# --- elasticity: Cartesian traction edges ---------------------------------------------------

ELASTIC = dict(e=70000.0, nu=0.3, body=(0.0, -2.0), t_right=(123.0, 45.0), u_left_y=2e-4)


def _t_top(x, y, nx, ny):
    """Top-edge traction, Pa: a pressure -(50 + 30 x) n plus a polynomial Cartesian part."""
    p = 50.0 + 30.0 * x
    return -p * nx + 20.0 * y, -p * ny + 10.0 * x * y


def _lame(e, nu, plane):
    lam, mu = e * nu / ((1 + nu) * (1 - 2 * nu)), e / (2 * (1 + nu))
    if plane == "stress":
        lam = 2 * lam * mu / (lam + 2 * mu)
    return lam, mu


def _skfem_elasticity(skfem, mesh, plane):
    """Independent P1 vector assembly with body force, two traction edges and nonzero Dirichlet data."""
    from skfem.helpers import ddot, eye, sym_grad, trace
    m = _reference_mesh(skfem, mesh)
    element = skfem.ElementVector(skfem.ElementTriP1())
    basis = skfem.Basis(m, element)
    lam, mu = _lame(ELASTIC["e"], ELASTIC["nu"], plane)
    body, t_right = ELASTIC["body"], ELASTIC["t_right"]

    @skfem.BilinearForm
    def elastic(u, v, w):
        eps = sym_grad(u)
        return ddot(2.0 * mu * eps + lam * eye(trace(eps), 2), sym_grad(v))

    @skfem.LinearForm
    def body_load(v, w):
        return body[0] * v[0] + body[1] * v[1]

    @skfem.LinearForm
    def traction_right(v, w):
        return t_right[0] * v[0] + t_right[1] * v[1]

    @skfem.LinearForm
    def traction_top(v, w):
        tx, ty = _t_top(w.x[0], w.x[1], w.n[0], w.n[1])
        return tx * v[0] + ty * v[1]

    def facet_basis(tag):
        return skfem.FacetBasis(m, element, facets=_facets(m, mesh.boundary_edges[tag]), intorder=FACET_ORDER)

    K = elastic.assemble(basis)
    f = body_load.assemble(basis) + traction_right.assemble(facet_basis("right")) \
        + traction_top.assemble(facet_basis("top"))
    left = np.asarray(mesh.boundary["left"])
    fixed = basis.nodal_dofs[:, left].ravel()
    x = np.zeros(basis.N)
    x[basis.nodal_dofs[1, left]] = ELASTIC["u_left_y"]
    u = skfem.solve(*skfem.condense(K, f, x=x, D=fixed))
    residual = K @ u - f
    reaction = np.zeros(basis.N)
    reaction[fixed] = residual[fixed]
    grad = basis.interpolate(u).grad[:, :, :, 0]  # (2 comps, 2 dirs, M), constant on P1
    exx, eyy, gxy = grad[0, 0], grad[1, 1], grad[0, 1] + grad[1, 0]
    stress = np.column_stack([(lam + 2 * mu) * exx + lam * eyy, lam * exx + (lam + 2 * mu) * eyy, mu * gxy])
    return dict(u=u[basis.nodal_dofs].T, load=f[basis.nodal_dofs].T, reaction=reaction[basis.nodal_dofs].T,
                stress=stress, energy=0.5 * u @ (K @ u))


@pytest.mark.parametrize("plane", ["strain", "stress"])
def test_elasticity_p1_traction_same_mesh(skfem, plane):
    mesh = rectangle_mesh(1.2, 0.7, 12, 7)
    left = mesh.boundary["left"]
    dirichlet = {(int(i), 0): 0.0 for i in left} | {(int(i), 1): ELASTIC["u_left_y"] for i in left}
    traction = {"right": ELASTIC["t_right"],
                "top": lambda p, n: np.column_stack(_t_top(p[:, 0], p[:, 1], n[:, 0], n[:, 1]))}
    clock = Stopwatch()
    with clock("openphysics"):
        ours = solve_elasticity(mesh, young_modulus=ELASTIC["e"], poisson_ratio=ELASTIC["nu"], plane=plane,
                                dirichlet=dirichlet, body_force=ELASTIC["body"], traction=traction)
        energy = 0.5 * np.sum(ours.displacement * (ours.load + ours.reaction))
    with clock("reference"):
        theirs = _skfem_elasticity(skfem, mesh, plane)
    emit(make_record(
        case=f"elasticity-p1-plane-{plane}-traction-plate",
        analytical_acceptance="tests/galerkin/test_elasticity_traction.py (docs/packages/galerkin/elasticity_traction.md)",
        stopwatch=clock,
        physics=f"2D linear elasticity, plane {plane}, body force, two traction edges, nonzero prescribed displacement",
        api="galerkin.elasticity.solve_elasticity", discretization="P1 Lagrange triangles, four-point Gauss edge rule",
        tool="scikit-fem",
        tool_discretization=f"ElementVector(ElementTriP1), FacetBasis intorder {FACET_ORDER} traction loads",
        matched=["same nodes and triangles (rectangle_mesh 1.2 m x 0.7 m, 12 x 7)",
                 "same edges selected by node pairs for the right and top tags",
                 "E = 70 kPa, nu = 0.3", f"plane {plane} constitutive law", "body force (0, -2) N/m^3",
                 "traction (123, 45) Pa on the right edge; on the top edge -(50 + 30 x) n plus (20 y, 10 x y) Pa",
                 "left edge: u_x = 0, u_y = 2e-4 m prescribed (nonzero Dirichlet data)",
                 "polynomial traction of degree <= 2: both edge rules exact"],
        not_matched=[],
        observables=[
            observable("nodal displacement", "m", "max relative difference",
                       relative_difference(ours.displacement, theirs["u"]), SAME),
            observable("element stress (sxx, syy, sxy)", "Pa", "max relative difference",
                       relative_difference(ours.stress, theirs["stress"]), SAME),
            observable("body plus traction load", "N/m", "max relative difference",
                       relative_difference(ours.load, theirs["load"]), SAME),
            observable("reaction at the prescribed DOFs", "N/m", "max relative difference",
                       relative_difference(ours.reaction, theirs["reaction"]), SAME),
            observable("strain energy 0.5 u . (load + reaction) vs 0.5 u . K u", "J/m", "relative difference",
                       abs(energy - theirs["energy"]) / abs(theirs["energy"]), SAME)]))


# --- Helmholtz: first-order absorbing boundary ----------------------------------------------

A_CYL, R_OUT, K_SCAT = 1.0, 4.0, np.pi


def test_helmholtz_p1_absorbing_boundary_same_mesh(skfem):
    """Scattered field of a sound-soft cylinder with the curvature-corrected first-order
    absorbing condition du/dn = (ik - 1/(2R)) u on the outer circle, as in test_helmholtz.py."""
    from skfem.helpers import dot, grad
    mesh = annulus_mesh(A_CYL, R_OUT, 10, 40)
    inner, outer_edges = mesh.boundary["inner"], mesh.boundary_edges["outer"]
    gamma = 1j * K_SCAT - 1.0 / (2.0 * R_OUT)
    g = -np.exp(1j * K_SCAT * mesh.nodes[inner, 0])  # u_s = -u_inc on the scatterer
    clock = Stopwatch()
    with clock("openphysics"):
        B = assemble_boundary_mass(mesh, outer_edges)
        A = (assemble_stiffness(mesh) - K_SCAT**2 * assemble_mass(mesh) - gamma * B).tocsr()
        ours = solve_dirichlet(A, np.zeros(mesh.num_nodes, dtype=complex), {tuple(inner): g})
    m = _reference_mesh(skfem, mesh)
    basis = skfem.Basis(m, skfem.ElementTriP1())
    outer = skfem.FacetBasis(m, skfem.ElementTriP1(), facets=_facets(m, outer_edges))

    @skfem.BilinearForm
    def helmholtz(u, v, w):
        return dot(grad(u), grad(v)) - K_SCAT**2 * u * v

    @skfem.BilinearForm
    def boundary_mass(u, v, w):
        return u * v

    with clock("reference"):
        B_ref = boundary_mass.assemble(outer)
        A_ref = (helmholtz.assemble(basis) - gamma * B_ref).tocsr()
        x = np.zeros(basis.N, dtype=complex)
        x[inner] = g
        theirs = skfem.solve(*skfem.condense(A_ref, np.zeros(basis.N, dtype=complex), x=x, D=inner))
    emit(make_record(
        case="helmholtz-p1-abc-cylinder",
        analytical_acceptance="tests/galerkin/test_helmholtz.py (docs/packages/galerkin/milestone_validation.md)",
        stopwatch=clock,
        physics="2D Helmholtz scattering off a sound-soft cylinder (k = pi, a = 1 m, R = 4 m), "
                "curvature-corrected first-order absorbing boundary",
        api="galerkin.assemble_stiffness, assemble_mass, assemble_boundary_mass, solve_dirichlet",
        discretization="P1 Lagrange triangles; absorbing term -(ik - 1/(2R)) B on the outer edges",
        tool="scikit-fem", tool_discretization="ElementTriP1, FacetBasis boundary mass on the same edges",
        matched=["same nodes and triangles (annulus_mesh 1 m to 4 m, 10 x 40)",
                 "same outer edges selected by node pairs", "k = pi (wavelength 2 m)",
                 "Dirichlet u_s = -exp(i k x) on the inner circle",
                 "complex Robin coefficient gamma = i k - 1/(2 R) on the outer polygon",
                 "same weak form K - k^2 M - gamma B"],
        not_matched=[],
        observables=[
            observable("complex scattered field", "1", "max relative difference",
                       relative_difference(ours, theirs), SAME),
            observable("imaginary part of the scattered field", "1", "max relative difference",
                       relative_difference(ours.imag, theirs.imag), SAME),
            observable("absorbing boundary mass B (assemble_boundary_mass)", "m", "max relative difference",
                       relative_difference(_dense(B), _dense(B_ref)), SAME),
            observable("boundary energy integral |u_s|^2 ds on the absorbing circle", "m",
                       "relative difference",
                       abs(np.vdot(ours, B @ ours).real - np.vdot(theirs, B_ref @ theirs).real)
                       / abs(np.vdot(theirs, B_ref @ theirs).real), SAME)]))
