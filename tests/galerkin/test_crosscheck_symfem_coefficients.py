# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Element matrices with per-cell, tensor and complex coefficients against symfem.

test_crosscheck_symfem_elements.py fixes the element conventions and checks the
unit-coefficient matrices. This module reuses its meshes and conventions and
checks the coefficient handling: each cell gets its own exact coefficient, a
scalar, a non-symmetric tensor or a complex value, and the reference integrates

    K_ij = int grad phi_i . (C grad phi_j)      M_ij = int c phi_i phi_j
    S_ef = int c (curl W_e) . (curl W_f)        N_ef = int W_e . (C W_f)
    G_en = int W_e . (C grad phi_n)

cell by cell in exact rational (complex rational) arithmetic. A non-symmetric
tensor fixes which side of C each function sits on. Every coefficient form the
public assembly functions accept is compared, through the public functions and
through galerkin.core.kernels with galerkin.core.forms, so the check stays
independent of which of the two builds the other.

Relative differences are gated at 1e-12 as in the unit-coefficient test
(float64 against exact values is about 1e-16; the coefficients themselves are
rounded to float64 once).
"""

import numpy as np
import pytest

from crosscheck import Stopwatch, emit, make_record, observable, relative_difference, require_tool
from galerkin import Mesh
from galerkin.assembly import assemble_mass, assemble_stiffness
from galerkin.assembly3d import assemble_mass_3d, assemble_stiffness_3d
from galerkin.core import forms, kernels
from galerkin.edge import EdgeSpace, assemble_curlcurl, assemble_edge_grad, assemble_edge_mass
from galerkin.edge3d import (EdgeSpace3D, assemble_curlcurl_3d, assemble_edge_grad_3d,
                             assemble_edge_mass_3d)
from galerkin.mesh3d import Mesh3D
from test_crosscheck_symfem_elements import _as_float, _mesh2d, _mesh3d

SAME_ELEMENT = 1e-12


@pytest.fixture(scope="module")
def symfem():
    return require_tool("symfem")


def _coefficients(cells, dim):
    """Exact per-cell coefficients: positive scalars, non-symmetric tensors, complex scalars and tensors."""
    import sympy
    R, I = sympy.Rational, sympy.I
    n = len(cells)
    scalar = [R(3 + 2 * t, 2 + t % 3) for t in range(n)]
    tensor = [sympy.Matrix(dim, dim, lambda k, l: R(1 + t + 2 * k + (l if k <= l else -l), 3 + k + l)
                           + (R(1 + t, 2) if k == l else 0))
              for t in range(n)]
    complex_scalar = [scalar[t] - I * R(1 + t, 5) for t in range(n)]
    complex_tensor = [tensor[t] - I * sympy.Matrix(dim, dim, lambda k, l: R(t + k + 1, 4 + l))
                      for t in range(n)]
    return {"cells": scalar, "tensor": tensor, "complex cells": complex_scalar,
            "complex tensor": complex_tensor}


def _numbers(values):
    """float64 or complex128 array of exact per-cell values (scalars or matrices)."""
    import sympy
    rows = [np.array(sympy.Matrix(v).tolist() if hasattr(v, "shape") else v, dtype=complex)
            for v in values]
    out = np.array(rows)
    return out.real.copy() if not np.any(out.imag) else out


class SymfemComponents:
    """Per-cell component integrals, so any per-cell coefficient can be applied exactly.

    For each cell t: P[t][i, j, k, l] = int d_k phi_i d_l phi_j (the gradients are
    constant, so this is their product times the cell measure), mass[t][i, j] and
    curl[t][e, f] = int curl W_e . curl W_f. On triangles N[t][e, f, k, l] =
    int W_e,k W_f,l and G[t][e, n, k, l] = int W_e,k d_l phi_n, for tensor
    coefficients; on tetrahedra, where the public functions take scalars only,
    N[t][e, f] = int W_e . W_f and G[t][e, n] = int W_e . grad phi_n. Local
    numbering is by ascending global node id with edges directed low -> high id
    (the conventions the unit-coefficient test checks exactly).
    """

    def __init__(self, symfem, exact, cells, cell_type):
        self.dim = len(exact[0])
        self.tensor_edges = self.dim == 2
        self.cells, self.orders, self.edges = cells, [], []
        self.P, self.mass, self.N, self.curl, self.G = [], [], [], [], []
        for cell in cells:
            self._cell(symfem, exact, cell, cell_type)

    def _cell(self, symfem, exact, cell, cell_type):
        import sympy
        from symfem.symbols import x
        d = self.dim
        order = sorted(cell)
        verts = tuple(exact[n] for n in order)
        ref = symfem.create_reference(cell_type, verts)
        lagrange = symfem.create_element(cell_type, "Lagrange", 1).map_to_cell(verts)
        nedelec = symfem.create_element(cell_type, "Nedelec", 0).map_to_cell(verts)
        local_edges = symfem.create_reference(cell_type).edges
        grads = [phi.grad(d) for phi in lagrange]
        if d == 2:
            curls = [w[1].diff(x[0]) - w[0].diff(x[1]) for w in nedelec]
            curl_dot = lambda p, q: p * q
        else:
            curls = [w.curl() for w in nedelec]
            curl_dot = lambda p, q: p.dot(q)
        nv, ne = len(lagrange), len(nedelec)
        self.orders.append(order)
        self.edges.append([(order[a], order[b]) for a, b in local_edges])
        measure = ref.volume()
        g = [[sympy.sympify(grads[i][k].as_sympy()) for k in range(d)] for i in range(nv)]
        assert all(c.free_symbols == set() for row in g for c in row), "P1 gradients must be constant"
        self.P.append({(i, j, k, l): g[i][k] * g[j][l] * measure
                       for i in range(nv) for j in range(nv) for k in range(d) for l in range(d)})
        self.mass.append({(i, j): (lagrange[i] * lagrange[j]).integral(ref)
                          for i in range(nv) for j in range(nv)})
        curl = {}
        for e in range(ne):
            for f in range(e, ne):
                curl[e, f] = curl[f, e] = curl_dot(curls[e], curls[f]).integral(ref)
        self.curl.append(curl)
        N, G = {}, {}
        if self.tensor_edges:
            for e in range(ne):
                for f in range(e, ne):
                    for k in range(d):
                        for l in range(d):
                            N[e, f, k, l] = N[f, e, l, k] = (nedelec[e][k] * nedelec[f][l]).integral(ref)
            for e in range(ne):
                mean = [(nedelec[e][k]).integral(ref) for k in range(d)]   # gradients are constant
                for n in range(nv):
                    for k in range(d):
                        for l in range(d):
                            G[e, n, k, l] = mean[k] * g[n][l]
        else:
            for e in range(ne):
                for f in range(e, ne):
                    N[e, f] = N[f, e] = nedelec[e].dot(nedelec[f]).integral(ref)
                mean = [(nedelec[e][k]).integral(ref) for k in range(d)]
                for n in range(nv):
                    G[e, n] = sum(mean[k] * g[n][k] for k in range(d))
        self.N.append(N)
        self.G.append(G)

    @staticmethod
    def _apply(c, comp, k, l):
        """Weight of component (k, l) for coefficient c: C_kl for a tensor, c delta_kl for a scalar."""
        if hasattr(c, "shape"):
            return c[k, l]
        return c if k == l else 0

    def _global(self, rows, cols, local, coefficient, rows_of, cols_of, tensor_form):
        out = np.zeros((len(rows), len(cols)), dtype=complex)
        d = self.dim
        for t in range(len(self.cells)):
            c = coefficient[t]
            row_ids, col_ids = rows_of(t), cols_of(t)
            for a, ra in enumerate(row_ids):
                for b, cb in enumerate(col_ids):
                    if tensor_form:
                        value = sum(self._apply(c, None, k, l) * local[t][(a, b, k, l)]
                                    for k in range(d) for l in range(d))
                    else:
                        value = c * local[t][(a, b)]
                    out[rows[ra], cols[cb]] += complex(value)
        return out.real.copy() if not np.any(out.imag) else out

    def stiffness(self, nodes, c):
        return self._global(nodes, nodes, self.P, c, lambda t: self.orders[t], lambda t: self.orders[t], True)

    def mass_matrix(self, nodes, c):
        return self._global(nodes, nodes, self.mass, c, lambda t: self.orders[t], lambda t: self.orders[t],
                            False)

    def curlcurl(self, edges, c):
        return self._global(edges, edges, self.curl, c, lambda t: self.edges[t], lambda t: self.edges[t],
                            False)

    def edge_mass(self, edges, c):
        return self._global(edges, edges, self.N, c, lambda t: self.edges[t], lambda t: self.edges[t],
                            self.tensor_edges)

    def edge_grad(self, edges, nodes, c):
        return self._global(edges, nodes, self.G, c, lambda t: self.edges[t], lambda t: self.orders[t],
                            self.tensor_edges)


def _core(row_dofs, col_dofs, element, shape):
    return forms.matrix(row_dofs, col_dofs, element, shape).to_scipy().toarray()


# (observable, unit, kinds) per assembled matrix; kinds are the coefficient forms the
# public function accepts.
TRIANGLE_MATRICES = [
    ("P1 stiffness", "1", ("cells", "tensor", "complex cells", "complex tensor")),
    ("P1 mass", "m^2", ("cells", "complex cells")),
    ("Nedelec curl-curl", "1/m^2", ("cells", "complex cells")),
    ("Nedelec mass", "1", ("cells", "tensor", "complex cells", "complex tensor")),
    ("Nedelec x P1 gradient coupling", "1/m", ("cells", "tensor", "complex cells", "complex tensor")),
]
TETRAHEDRON_MATRICES = [
    ("P1 stiffness", "m", ("cells", "tensor")),
    ("P1 mass", "m^3", ("cells",)),
    ("Nedelec curl-curl", "1/m", ("cells",)),
    ("Nedelec mass", "m", ("cells",)),
    ("Nedelec x P1 gradient coupling", "1", ("cells",)),
]


def _compare(name, unit, kinds, galerkin_public, galerkin_core, reference, coefficients):
    out = []
    for kind in kinds:
        exact = coefficients[kind]
        numbers = _numbers(exact)
        expected = reference(exact)
        for route, build in (("public", galerkin_public), ("core", galerkin_core)):
            got = build(numbers)
            assert got.shape == expected.shape
            out.append(observable(f"{name}, {kind} coefficient ({route} assembly)", unit,
                                  "max abs difference / max abs reference",
                                  relative_difference(got, expected), SAME_ELEMENT))
    return out


def test_triangle_matrices_with_coefficients_match_symfem(symfem):
    exact, cells = _mesh2d()
    clock = Stopwatch()
    mesh = Mesh(_as_float(exact), np.array(cells), boundary={})
    space = EdgeSpace(mesh)
    with clock("reference"):
        ref = SymfemComponents(symfem, exact, cells, "triangle")
    coefficients = _coefficients(cells, 2)
    nodes = {n: n for n in range(mesh.num_nodes)}
    edges = {tuple(int(v) for v in edge): i for i, edge in enumerate(space.edges)}
    n2, e2, en = (mesh.num_nodes,) * 2, (space.num_edges,) * 2, (space.num_edges, mesh.num_nodes)
    tn, te = mesh.triangles, space.tri_edges
    routes = {
        "P1 stiffness": (lambda c: assemble_stiffness(mesh, c).toarray(),
                         lambda c: _core(tn, tn, kernels.p1_stiffness(mesh, c), n2),
                         lambda c: ref.stiffness(nodes, c)),
        "P1 mass": (lambda c: assemble_mass(mesh, c).toarray(),
                    lambda c: _core(tn, tn, kernels.p1_mass(mesh, c), n2),
                    lambda c: ref.mass_matrix(nodes, c)),
        "Nedelec curl-curl": (lambda c: assemble_curlcurl(space, c).toarray(),
                              lambda c: _core(te, te, kernels.nedelec_curlcurl(space, c), e2),
                              lambda c: ref.curlcurl(edges, c)),
        "Nedelec mass": (lambda c: assemble_edge_mass(space, c).toarray(),
                         lambda c: _core(te, te, kernels.nedelec_mass(space, c), e2),
                         lambda c: ref.edge_mass(edges, c)),
        "Nedelec x P1 gradient coupling": (lambda c: assemble_edge_grad(space, c).toarray(),
                                           lambda c: _core(te, tn, kernels.nedelec_grad(space, c), en),
                                           lambda c: ref.edge_grad(edges, nodes, c)),
    }
    with clock("openphysics"):
        observables = [o for name, unit, kinds in TRIANGLE_MATRICES
                       for o in _compare(name, unit, kinds, *routes[name], coefficients)]
    emit(make_record(
        case="elements-coefficients-triangles",
        physics="element matrices of P1 Lagrange and lowest-order Nedelec triangles with per-cell coefficients",
        api="galerkin.assembly.assemble_stiffness/assemble_mass, galerkin.edge.assemble_curlcurl/"
            "assemble_edge_mass/assemble_edge_grad, galerkin.core.kernels with galerkin.core.forms.matrix",
        discretization="P1 Lagrange triangles; Whitney edge elements, edges directed low -> high node id",
        tool="symfem", tool_discretization='create_element("triangle", "Lagrange", 1) and '
                                           '("triangle", "Nedelec", 0), map_to_cell, exact sympy integrals '
                                           'of basis components, contracted with exact coefficients',
        matched=["the 7-node, 6-triangle mesh of test_crosscheck_symfem_elements.py (conventions checked there)",
                 "per-cell rational coefficients: scalars, non-symmetric 2x2 tensors, complex scalars "
                 "and complex tensors, wherever the public function accepts that form"],
        not_matched=["galerkin evaluates in float64 with coefficients rounded to float64 once, "
                     "symfem in exact (complex) rationals"],
        observables=observables,
        analytical_acceptance="tests/galerkin/test_electrostatics.py, tests/galerkin/test_edge_elements.py",
        stopwatch=clock))


def test_tetrahedron_matrices_with_coefficients_match_symfem(symfem):
    exact, cells = _mesh3d()
    clock = Stopwatch()
    mesh = Mesh3D(_as_float(exact), np.array(cells))
    space = EdgeSpace3D(mesh)
    with clock("reference"):
        ref = SymfemComponents(symfem, exact, cells, "tetrahedron")
    coefficients = _coefficients(cells, 3)
    nodes = {n: n for n in range(mesh.num_nodes)}
    edges = {tuple(int(v) for v in edge): i for i, edge in enumerate(space.edges)}
    n2, e2, en = (mesh.num_nodes,) * 2, (space.num_edges,) * 2, (space.num_edges, mesh.num_nodes)
    tn, te = mesh.tets, space.tet_edges
    routes = {
        "P1 stiffness": (lambda c: assemble_stiffness_3d(mesh, c).toarray(),
                         lambda c: _core(tn, tn, kernels.tet_stiffness(mesh, c), n2),
                         lambda c: ref.stiffness(nodes, c)),
        "P1 mass": (lambda c: assemble_mass_3d(mesh, c).toarray(),
                    lambda c: _core(tn, tn, kernels.tet_mass(mesh, c), n2),
                    lambda c: ref.mass_matrix(nodes, c)),
        "Nedelec curl-curl": (lambda c: assemble_curlcurl_3d(space, c).toarray(),
                              lambda c: _core(te, te, kernels.nedelec3d_curlcurl(space, c), e2),
                              lambda c: ref.curlcurl(edges, c)),
        "Nedelec mass": (lambda c: assemble_edge_mass_3d(space, c).toarray(),
                         lambda c: _core(te, te, kernels.nedelec3d_mass(space, c), e2),
                         lambda c: ref.edge_mass(edges, c)),
        "Nedelec x P1 gradient coupling": (lambda c: assemble_edge_grad_3d(space, c).toarray(),
                                           lambda c: _core(te, tn, kernels.nedelec3d_grad(space, c), en),
                                           lambda c: ref.edge_grad(edges, nodes, c)),
    }
    with clock("openphysics"):
        observables = [o for name, unit, kinds in TETRAHEDRON_MATRICES
                       for o in _compare(name, unit, kinds, *routes[name], coefficients)]
    emit(make_record(
        case="elements-coefficients-tetrahedra",
        physics="element matrices of P1 Lagrange and lowest-order Nedelec tetrahedra with per-cell coefficients",
        api="galerkin.assembly3d.assemble_stiffness_3d/assemble_mass_3d, galerkin.edge3d.assemble_curlcurl_3d/"
            "assemble_edge_mass_3d/assemble_edge_grad_3d, galerkin.core.kernels with galerkin.core.forms.matrix",
        discretization="P1 Lagrange tetrahedra; Whitney edge elements, edges directed low -> high node id",
        tool="symfem", tool_discretization='create_element("tetrahedron", "Lagrange", 1) and '
                                           '("tetrahedron", "Nedelec", 0), map_to_cell, exact sympy integrals '
                                           'of basis components, contracted with exact coefficients',
        matched=["the 6-node, 4-tetrahedron mesh of test_crosscheck_symfem_elements.py (conventions checked there)",
                 "per-cell rational coefficients: scalars everywhere, non-symmetric 3x3 tensors for the "
                 "P1 stiffness, the only forms the public functions accept"],
        not_matched=["galerkin evaluates in float64 with coefficients rounded to float64 once, "
                     "symfem in exact rationals",
                     "complex coefficients: the public 3D functions take real coefficients only"],
        observables=observables,
        analytical_acceptance="tests/galerkin/test_cavity_modes.py, tests/galerkin/test_cavity3d_validation.py",
        stopwatch=clock))
