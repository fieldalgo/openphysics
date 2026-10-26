# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Solve the same problems with galerkin and scikit-fem and record the differences.

Cases with the same mesh, element and boundary data must give the same discrete
solution: their differences are gated at 1e-9 relative, far above roundoff
(observed 1e-12 or smaller) and far below any discretization error. Cases that
use a different element order or quadrature are reported only. Neither kind is
convergence evidence; the analytical gates of each feature stay as they are.
"""

import numpy as np
import pytest

from crosscheck import Stopwatch, emit, make_record, observable, relative_difference, require_tool
from galerkin.cavity import solve_cavity_box
from galerkin.elasticity import solve_elasticity
from galerkin.mesh import Mesh, rectangle_mesh
from galerkin.thermal import solve_steady_heat
from galerkin.waveguide import solve_modes

SAME = 1e-9  # identical discretizations: relative difference gate


@pytest.fixture(scope="module")
def skfem():
    return require_tool("scikit-fem")


def _reference_mesh(skfem, mesh):
    return skfem.MeshTri(mesh.nodes.T.copy(), mesh.triangles.T.copy())


def _slab(nx=12, ny=6):
    mesh = rectangle_mesh(2.0, 1.0, nx, ny)
    dirichlet = {int(i): 400.0 for i in mesh.boundary["left"]}
    dirichlet.update({int(i): 300.0 for i in mesh.boundary["right"]})
    return mesh, dirichlet


def _skfem_heat(skfem, mesh, element, k, source, dirichlet):
    from skfem.helpers import dot, grad
    basis = skfem.Basis(_reference_mesh(skfem, mesh), element)

    @skfem.BilinearForm
    def conduction(u, v, w):
        return k * dot(grad(u), grad(v))

    @skfem.LinearForm
    def load(v, w):
        return source(w.x) * v

    stiffness, rhs = conduction.assemble(basis), load.assemble(basis)
    fixed = basis.get_dofs(lambda x: (x[0] < 1e-12) | (x[0] > 2.0 - 1e-12)).all()
    x = np.zeros(basis.N)
    coordinates = basis.doflocs[:, fixed]
    x[fixed] = np.where(coordinates[0] < 1.0, 400.0, 300.0)
    solution = skfem.solve(*skfem.condense(stiffness, rhs, x=x, D=fixed))
    return basis, solution


def test_heat_p1_same_mesh(skfem):
    mesh, dirichlet = _slab()
    k, q = 3.0, 50.0
    clock = Stopwatch()
    with clock("openphysics"):
        ours = solve_steady_heat(mesh, conductivity=k, dirichlet=dirichlet, heat_source=q)
    with clock("reference"):
        basis, theirs = _skfem_heat(skfem, mesh, skfem.ElementTriP1(), k, lambda x: q + 0 * x[0],
                                    dirichlet)
    flux = -k * basis.interpolate(theirs).grad.mean(axis=-1).T  # constant per P1 triangle
    emit(make_record(
        case="heat-p1-slab",
        analytical_acceptance="tests/galerkin/test_thermal_independent_validation.py (docs/packages/galerkin/thermal_independent_validation.md)", stopwatch=clock, physics="2D steady heat conduction, uniform source",
        api="galerkin.thermal.solve_steady_heat", discretization="P1 Lagrange triangles",
        tool="scikit-fem", tool_discretization="ElementTriP1",
        matched=["same nodes and triangles (rectangle_mesh 2 m x 1 m, 12 x 6)",
                 "k = 3 W/(m K), Q = 50 W/m^3", "Dirichlet 400 K left, 300 K right",
                 "insulated top and bottom", "exact integration of the constant load"],
        not_matched=[],
        observables=[
            observable("nodal temperature", "K", "max relative difference",
                       relative_difference(ours.temperature, theirs), SAME),
            observable("element heat flux", "W/m^2", "max relative difference",
                       relative_difference(ours.heat_flux, flux), SAME)]))


def test_heat_p2_reference_is_reported(skfem):
    """Different element order and load quadrature: differences are reported only."""
    mesh, dirichlet = _slab()
    k, q0, length = 3.0, 50.0, 2.0

    def source(x):
        return q0 * np.sin(np.pi * x[0] / length)

    def exact(x):
        return 400.0 - 100.0 * x / length + q0 * length**2 / (k * np.pi**2) * np.sin(np.pi * x / length)

    clock = Stopwatch()
    with clock("openphysics"):
        ours = solve_steady_heat(mesh, conductivity=k, dirichlet=dirichlet,
                                 heat_source=lambda p: source(p.T))
    with clock("reference"):
        basis, theirs = _skfem_heat(skfem, mesh, skfem.ElementTriP2(), k, source, dirichlet)
    vertices = basis.nodal_dofs[0]
    scale = np.max(np.abs(exact(mesh.nodes[:, 0])))
    emit(make_record(
        case="heat-p2-reference-slab",
        analytical_acceptance="tests/galerkin/test_thermal_independent_validation.py (docs/packages/galerkin/thermal_independent_validation.md)", stopwatch=clock, physics="2D steady heat conduction, sinusoidal source",
        api="galerkin.thermal.solve_steady_heat", discretization="P1 Lagrange triangles",
        tool="scikit-fem", tool_discretization="ElementTriP2",
        matched=["same nodes and triangles (12 x 6)", "k, source and Dirichlet data"],
        not_matched=["element order (galerkin P1, reference P2)", "load quadrature rule"],
        observables=[
            observable("vertex temperature, galerkin P1 vs reference P2", "K",
                       "max relative difference", relative_difference(ours.temperature, theirs[vertices])),
            observable("vertex temperature, galerkin P1 vs analytical", "K", "max relative error",
                       np.max(np.abs(ours.temperature - exact(mesh.nodes[:, 0]))) / scale),
            observable("vertex temperature, reference P2 vs analytical", "K", "max relative error",
                       np.max(np.abs(theirs[vertices] - exact(mesh.nodes[:, 0]))) / scale)]))


def _skfem_elasticity(skfem, mesh, element, young, poisson, plane, body):
    from skfem.models.elasticity import lame_parameters, linear_elasticity
    lam, mu = lame_parameters(young, poisson)
    if plane == "stress":
        lam = 2 * lam * mu / (lam + 2 * mu)
    basis = skfem.Basis(_reference_mesh(skfem, mesh), skfem.ElementVector(element))

    @skfem.LinearForm
    def load(v, w):
        return body[0] * v[0] + body[1] * v[1]

    fixed = basis.get_dofs(lambda x: x[0] < 1e-12).all()
    solution = skfem.solve(*skfem.condense(linear_elasticity(lam, mu).assemble(basis),
                                           load.assemble(basis), D=fixed))
    return basis, solution


@pytest.mark.parametrize("plane", ["strain", "stress"])
def test_elasticity_p1_same_mesh(skfem, plane):
    mesh = rectangle_mesh(2.0, 0.5, 16, 4)
    young, poisson, body = 2.0e11, 0.3, (0.0, -7.8e4)
    dirichlet = {(int(i), c): 0.0 for i in mesh.boundary["left"] for c in (0, 1)}
    clock = Stopwatch()
    with clock("openphysics"):
        ours = solve_elasticity(mesh, young_modulus=young, poisson_ratio=poisson, plane=plane,
                                dirichlet=dirichlet, body_force=body)
    with clock("reference"):
        basis, theirs = _skfem_elasticity(skfem, mesh, skfem.ElementTriP1(), young, poisson, plane, body)
    displacement = theirs[basis.nodal_dofs].T
    emit(make_record(
        case=f"elasticity-p1-plane-{plane}-cantilever",
        analytical_acceptance="tests/galerkin/test_elasticity2d_independent_validation.py (docs/packages/galerkin/elasticity2d_independent_validation.md)", stopwatch=clock,
        physics=f"2D linear elasticity, plane {plane}, clamped left edge, gravity load",
        api="galerkin.elasticity.solve_elasticity", discretization="P1 Lagrange triangles",
        tool="scikit-fem", tool_discretization="ElementVector(ElementTriP1), linear_elasticity",
        matched=["same nodes and triangles (rectangle_mesh 2 m x 0.5 m, 16 x 4)",
                 "E = 200 GPa, nu = 0.3", f"plane {plane} constitutive law",
                 "both components fixed on the left edge", "body force (0, -7.8e4) N/m^3"],
        not_matched=[],
        observables=[observable("nodal displacement", "m", "max relative difference",
                                relative_difference(ours.displacement, displacement), SAME)]))


def test_elasticity_p2_reference_is_reported(skfem):
    mesh = rectangle_mesh(2.0, 0.5, 16, 4)
    young, poisson, body = 2.0e11, 0.3, (0.0, -7.8e4)
    dirichlet = {(int(i), c): 0.0 for i in mesh.boundary["left"] for c in (0, 1)}
    clock = Stopwatch()
    with clock("openphysics"):
        ours = solve_elasticity(mesh, young_modulus=young, poisson_ratio=poisson, plane="stress",
                                dirichlet=dirichlet, body_force=body)
    with clock("reference"):
        basis, theirs = _skfem_elasticity(skfem, mesh, skfem.ElementTriP2(), young, poisson, "stress", body)
    tip = int(np.argmin(np.hypot(mesh.nodes[:, 0] - 2.0, mesh.nodes[:, 1] - 0.25)))
    ours_tip = ours.displacement[tip, 1]
    theirs_tip = theirs[basis.nodal_dofs[1, tip]]
    emit(make_record(
        case="elasticity-p2-reference-cantilever",
        analytical_acceptance="tests/galerkin/test_elasticity2d_independent_validation.py (docs/packages/galerkin/elasticity2d_independent_validation.md)", stopwatch=clock,
        physics="2D linear elasticity, plane stress, clamped left edge, gravity load",
        api="galerkin.elasticity.solve_elasticity", discretization="P1 Lagrange triangles",
        tool="scikit-fem", tool_discretization="ElementVector(ElementTriP2), linear_elasticity",
        matched=["same nodes and triangles (16 x 4)", "material, load and clamping"],
        not_matched=["element order (galerkin P1, reference P2); P1 is stiffer in bending"],
        observables=[observable("tip deflection at (2, 0.25), galerkin P1 vs reference P2", "m",
                                "relative difference", abs(ours_tip - theirs_tip) / abs(theirs_tip))]))


@pytest.mark.parametrize("loss", [0., .03])
def test_vector_waveguide_modes_same_mesh(skfem, loss):
    import scipy.linalg as la
    from skfem.helpers import curl, dot, grad
    width, height = 4.0, 3.0
    grid = rectangle_mesh(width, height, 16, 12)
    mesh = Mesh(grid.nodes - [width / 2, height / 2], grid.triangles, grid.boundary,
                grid.boundary_edges)
    centroids = mesh.nodes[mesh.triangles].mean(axis=1)
    core = (np.abs(centroids[:, 0]) < 0.8) & (np.abs(centroids[:, 1]) < 0.5)
    eps = np.where(core, 3.48**2, 1.44**2)
    if loss:
        eps = eps - 1j * loss * core
    k0 = 2 * np.pi / 1.55
    clock = Stopwatch()
    with clock("openphysics"):
        n_eff, _, _, _ = solve_modes(mesh, eps, k0, 3.48, num_modes=4)

    basis = skfem.Basis(_reference_mesh(skfem, mesh), skfem.ElementTriN1() * skfem.ElementTriP1())
    eps_q = np.repeat(eps[:, None], basis.default_parameters()["x"].shape[-1], axis=1)

    @skfem.BilinearForm(dtype=complex if loss else float)
    def left(et, ez, vt, vz, w):
        return curl(et) * curl(vt) - k0**2 * w.eps * dot(et, vt)

    @skfem.BilinearForm(dtype=complex if loss else float)
    def right(et, ez, vt, vz, w):
        return (dot(et, vt) + dot(et, grad(vz)) + dot(grad(ez), vt) + dot(grad(ez), grad(vz))
                - k0**2 * w.eps * ez * vz)

    with clock("reference"):
        free = basis.complement_dofs(basis.get_dofs().all())
        a = left.assemble(basis, eps=eps_q)[free][:, free].toarray()
        b = right.assemble(basis, eps=eps_q)[free][:, free].toarray()
        lam = la.eigvals(a, b)
    lam = lam[np.isfinite(lam)]
    reference = np.sqrt(-lam.astype(complex)) / k0 if loss else np.sqrt(np.clip(-lam.real, 0, None)) / k0
    reference = reference[(reference.real > 1.44) & (reference.real < 3.48)]
    reference = reference[np.argsort(-reference.real)][:4]
    emit(make_record(
        case="waveguide-vector-rect-core-lossy" if loss else "waveguide-vector-rect-core",
        analytical_acceptance="tests/simcase/test_lossy_modes.py" if loss else "tests/galerkin/test_hadley.py and tests/galerkin/test_fiber_modes.py (published and closed-form mode indices)", stopwatch=clock,
        physics="2D full-vector dielectric waveguide modes (Si core 1.6 x 1.0 in SiO2, 1.55 um)",
        api="galerkin.waveguide.solve_modes",
        discretization="lowest-order Nedelec (E_t) x P1 (E_z), beta^2 formulation",
        tool="scikit-fem", tool_discretization="ElementTriN1 * ElementTriP1, same bilinear forms",
        matched=["same nodes and triangles (4 x 3 window, 16 x 12)", f"piecewise-constant eps; core Im epsilon = {-loss}",
                 "PEC on the whole outer boundary (tangential E_t and E_z)", "same generalized eigenproblem"],
        not_matched=["eigensolver (galerkin shift-invert ARPACK, reference dense QZ)"],
        observables=[observable("effective index, four highest guided modes", "1",
                                "max relative difference", relative_difference(n_eff, reference),
                                SAME)] + ([observable("imaginary effective index", "1", "max relative difference",
                                                      relative_difference(n_eff.imag, reference.imag), SAME)] if loss else [])))


def test_pec_cavity_eigenvalues_same_mesh(skfem):
    import scipy.linalg as la
    from skfem.helpers import curl, dot
    lengths, cells = (1.0, 0.7, 0.5), (4, 3, 2)
    clock = Stopwatch()
    with clock("openphysics"):
        ours = solve_cavity_box(lengths, cells, num_modes=8, target_frequency_hz=1e8)
    mesh = skfem.MeshTet(ours.mesh.nodes.T.copy(), ours.mesh.tets.T.copy())
    basis = skfem.Basis(mesh, skfem.ElementTetN0())

    @skfem.BilinearForm
    def curlcurl(u, v, w):
        return dot(curl(u), curl(v))

    @skfem.BilinearForm
    def mass(u, v, w):
        return dot(u, v)

    with clock("reference"):
        free = basis.complement_dofs(basis.get_dofs().all())
        values = la.eigh(curlcurl.assemble(basis)[free][:, free].toarray(),
                         mass.assemble(basis)[free][:, free].toarray(), eigvals_only=True)
    reference = np.sort(values[values > 1e-6 * np.pi**2])[:8]
    emit(make_record(
        case="cavity-pec-box",
        analytical_acceptance="tests/galerkin/test_cavity3d_validation.py (docs/packages/galerkin/cavity_solver.md)", stopwatch=clock, physics="3D vacuum PEC box resonances (1 x 0.7 x 0.5 m)",
        api="galerkin.cavity.solve_cavity_box", discretization="lowest-order Nedelec tetrahedra",
        tool="scikit-fem", tool_discretization="ElementTetN0",
        matched=["same nodes and tetrahedra (the returned SI mesh, 4 x 3 x 2 cells)",
                 "PEC on all six walls", "curl-curl and mass forms"],
        not_matched=["eigensolver (galerkin dense or shift-invert with gradient projection, "
                     "reference dense with a kernel cut-off)"],
        observables=[observable("eigenvalue k^2, lowest eight", "m^-2", "max relative difference",
                                relative_difference(np.sort(ours.eigenvalues_m2), reference), SAME)]))


def test_scalar_absorbing_waveguide_same_mesh(skfem):
    import scipy.linalg as la
    from skfem.helpers import dot, grad
    from simcase.physics_em_modes2d import solve
    mesh = rectangle_mesh(2., 1., 12, 8)
    eps, k0 = 4.-.1j, 2*np.pi/1.55
    clock = Stopwatch()
    with clock("openphysics"):
        ours = solve(mesh, np.full(mesh.num_triangles, eps), 1.55,
                     dict(left="pec", right="pec", top="pec", bottom="pec"), 2)["neff"]
    basis = skfem.Basis(_reference_mesh(skfem, mesh), skfem.ElementTriP1())

    @skfem.BilinearForm(dtype=complex)
    def left(u, v, w):
        return k0**2*eps*u*v-dot(grad(u), grad(v))

    @skfem.BilinearForm
    def mass(u, v, w):
        return u*v

    with clock("reference"):
        free = basis.complement_dofs(basis.get_dofs().all())
        a = left.assemble(basis)[free][:, free].toarray()
        b = mass.assemble(basis)[free][:, free].toarray()
        values = la.eigvals(a, b)
        reference = np.sqrt(values.astype(complex))/k0
        reference = reference[np.argsort(-reference.real)][:2]
    emit(make_record(case="waveguide-scalar-rectangle-lossy", physics="scalar absorbing rectangle, PEC walls",
                     api="simcase.physics_em_modes2d.solve", discretization="P1 triangles",
                     tool="scikit-fem", tool_discretization="ElementTriP1",
                     analytical_acceptance="tests/simcase/test_lossy_modes.py",
                     stopwatch=clock, matched=["same mesh, PEC walls, epsilon=4-.1i, wavelength=1.55"],
                     not_matched=["sparse ARPACK versus dense QZ"],
                     observables=[observable("complex effective index", "1", "max relative difference",
                                             relative_difference(ours, reference), SAME),
                                  observable("imaginary effective index", "1", "max relative difference",
                                             relative_difference(ours.imag, reference.imag), SAME)]))
