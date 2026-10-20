# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Check galerkin's element definitions and element matrices against symfem.

symfem builds finite elements symbolically from their definitions (polynomial
space and degrees of freedom) and integrates in exact rational arithmetic with
sympy. It is the reference DefElement uses to verify other libraries. Here it
supplies, on small meshes with rational coordinates and scrambled node numbers:

- the P1 Lagrange basis on triangles and tetrahedra;
- the lowest-order Nedelec (first kind) basis on triangles and tetrahedra,
  mapped to each physical cell by symfem's covariant Piola map.

Before any comparison the test fixes the conventions independently of both
codes: with each cell's vertices passed to symfem in ascending global node id,
every symfem edge function must have unit circulation along its own edge,
directed from the lower to the higher node id, and zero circulation along the
other edges. Those line integrals are computed here with sympy, exactly. They
come out as the identity matrix, so symfem's degrees of freedom are galerkin's
(unit-tangent circulation, low node -> high node) with no sign or scale change,
and the global matrices can be compared entry by entry.

Same definitions must give the same numbers: the relative differences are gated
at 1e-12 (roundoff of float64 against exact rationals is about 1e-15). This is
code-to-code evidence about element definitions, not convergence evidence.
"""

import numpy as np
import pytest

from crosscheck import Stopwatch, emit, make_record, observable, relative_difference, require_tool
from galerkin import Mesh
from galerkin.assembly import assemble_mass, assemble_stiffness
from galerkin.assembly3d import assemble_mass_3d, assemble_stiffness_3d, tet_gradients
from galerkin.edge import (EdgeSpace, assemble_curlcurl, assemble_edge_grad, assemble_edge_mass,
                           eval_edge_field)
from galerkin.edge3d import (EdgeSpace3D, assemble_curlcurl_3d, assemble_edge_grad_3d,
                             assemble_edge_mass_3d, eval_edge_field_3d)
from galerkin.mesh3d import Mesh3D
from galerkin.postprocess import element_gradient

SAME_ELEMENT = 1e-12  # same element definition: relative difference gate
EXACT = 0.0           # exact rational checks (convention and nodality): no tolerance


@pytest.fixture(scope="module")
def symfem():
    return require_tool("symfem")


def _r(value):
    import sympy
    return sympy.Rational(value)


def _mesh2d():
    """Seven nodes, six triangles: obtuse, thin and clockwise cells, scrambled ids."""
    pts = [("0", "0"), ("2", "0"), ("2", "1"), ("0", "3/2"), ("4/5", "3/5"),
           ("7/2", "5/2"), ("1/10", "-1/2")]
    tris = [[4, 0, 1], [1, 2, 4], [2, 3, 4], [3, 0, 4], [2, 5, 3], [0, 6, 1]]
    perm = [3, 6, 0, 5, 1, 4, 2]            # old id -> new id
    exact = [None] * len(pts)
    for old, new in enumerate(perm):
        exact[new] = tuple(_r(c) for c in pts[old])
    cells = [[perm[v] for v in tri] for tri in tris]
    return exact, cells


def _mesh3d():
    """Four tetrahedra around one interior edge, distorted ring, scrambled ids."""
    pts = [("0", "0", "0"), ("1/6", "-1/7", "4/3"), ("1", "0", "1/5"), ("1/7", "1", "1/2"),
           ("-1", "1/9", "1/3"), ("1/4", "-1", "2/3")]
    tets = [[0, 1, 2, 3], [0, 1, 3, 4], [1, 0, 5, 4], [0, 1, 2, 5]]
    perm = [4, 1, 5, 0, 3, 2]
    exact = [None] * len(pts)
    for old, new in enumerate(perm):
        exact[new] = tuple(_r(c) for c in pts[old])
    cells = [[perm[v] for v in tet] for tet in tets]
    return exact, cells


def _as_float(exact):
    return np.array([[float(c) for c in p] for p in exact])


def _scalar_curl_2d(f):
    from symfem.symbols import x
    return f[1].diff(x[0]) - f[0].diff(x[1])


def _circulation(f, a, b):
    """Exact int_0^1 f(a + s (b - a)) . (b - a) ds: circulation along a -> b, unit tangent."""
    import sympy
    from symfem.symbols import x
    s = sympy.Symbol("s")
    path = {x[i]: a[i] + s * (b[i] - a[i]) for i in range(len(a))}
    integrand = sum(sympy.sympify(f[i].as_sympy()).subs(path) * (b[i] - a[i])
                    for i in range(len(a)))
    return sympy.integrate(sympy.expand(integrand), (s, 0, 1))


class SymfemCells:
    """Global P1 and Nedelec matrices assembled from symfem's mapped bases."""

    def __init__(self, symfem, exact, cells, cell_type):
        self.symfem, self.exact, self.cells, self.cell_type = symfem, exact, cells, cell_type
        self.dim = len(exact[0])
        self.circulation_error = 0      # max |circulation matrix - identity| over all cells
        self.nodality_error = 0         # max |phi_i(v_j) - delta_ij| over all cells
        self.min_measure = None
        self.p1_stiff, self.p1_mass = {}, {}
        self.curlcurl, self.edge_mass, self.edge_grad = {}, {}, {}
        self.p1_grad, self.edge_centroid = {}, {}
        for index, cell in enumerate(cells):
            self._cell(index, cell)

    def _cell(self, index, cell):
        import sympy
        from symfem.symbols import x
        symfem = self.symfem
        order = sorted(cell)                       # ascending global id -> symfem local order
        verts = tuple(self.exact[n] for n in order)
        ref = symfem.create_reference(self.cell_type, verts)
        measure = ref.volume()
        self.min_measure = measure if self.min_measure is None else min(self.min_measure, measure)
        lagrange = symfem.create_element(self.cell_type, "Lagrange", 1).map_to_cell(verts)
        nedelec = symfem.create_element(self.cell_type, "Nedelec", 0).map_to_cell(verts)
        local_edges = symfem.create_reference(self.cell_type).edges

        # Conventions, checked exactly before anything is compared.
        for i, phi in enumerate(lagrange):
            for j, v in enumerate(verts):
                value = sympy.sympify(phi.as_sympy()).subs({x[k]: v[k] for k in range(self.dim)})
                self.nodality_error = max(self.nodality_error, abs(value - (i == j)))
        for e, (a, b) in enumerate(local_edges):
            for f, w in enumerate(nedelec):
                value = _circulation(w, verts[a], verts[b])
                self.circulation_error = max(self.circulation_error, abs(value - (e == f)))

        edges = [(order[a], order[b]) for a, b in local_edges]   # low -> high global id
        centroid = {x[k]: sum(v[k] for v in verts) / len(verts) for k in range(self.dim)}
        if self.dim == 2:
            curls = [_scalar_curl_2d(w) for w in nedelec]
            curl_dot = lambda p, q: p * q
        else:
            curls = [w.curl() for w in nedelec]
            curl_dot = lambda p, q: p.dot(q)
        grads = [phi.grad(self.dim) for phi in lagrange]

        def add(store, key, value):
            store[key] = store.get(key, 0) + value

        for i, n in enumerate(order):
            add(self.p1_grad, (n, index), np.array([float(c) for c in grads[i].as_sympy()]))
            for j, m in enumerate(order):
                if j < i:
                    continue
                k = grads[i].dot(grads[j]).integral(ref)
                mass = (lagrange[i] * lagrange[j]).integral(ref)
                for key in {(n, m), (m, n)}:
                    add(self.p1_stiff, key, k)
                    add(self.p1_mass, key, mass)
        for e, edge in enumerate(edges):
            value = sympy.sympify(nedelec[e].as_sympy())
            add(self.edge_centroid, (edge, index),
                np.array([float(sympy.sympify(c).subs(centroid)) for c in value]))
            for f, other in enumerate(edges):
                if f >= e:
                    s_value = curl_dot(curls[e], curls[f]).integral(ref)
                    m_value = nedelec[e].dot(nedelec[f]).integral(ref)
                    for key in {(edge, other), (other, edge)}:
                        add(self.curlcurl, key, s_value)
                        add(self.edge_mass, key, m_value)
            for j, n in enumerate(order):
                add(self.edge_grad, (edge, n), nedelec[e].dot(grads[j]).integral(ref))


def _dense(entries, rows, cols):
    out = np.zeros((len(rows), len(cols)))
    for (r, c), value in entries.items():
        out[rows[r], cols[c]] = float(value)
    return out


def _orientation_facts(space_edges, signs):
    """galerkin's global edges must run low -> high, and the mesh must exercise both signs."""
    edges = np.asarray(space_edges)
    assert np.all(edges[:, 0] < edges[:, 1]), "global edges must be directed low -> high node id"
    assert np.any(signs < 0) and np.any(signs > 0), "the mesh must contain both local orientations"


def test_p1_and_nedelec_triangles_match_symfem(symfem):
    exact, cells = _mesh2d()
    clock = Stopwatch()
    with clock("openphysics"):
        mesh = Mesh(_as_float(exact), np.array(cells), boundary={})
        space = EdgeSpace(mesh)
        K, M = assemble_stiffness(mesh).toarray(), assemble_mass(mesh).toarray()
        S, Me = assemble_curlcurl(space).toarray(), assemble_edge_mass(space).toarray()
        G = assemble_edge_grad(space).toarray()
        unit_nodes = np.eye(mesh.num_nodes)
        p1_grad = np.stack([element_gradient(mesh, unit_nodes[n]) for n in range(mesh.num_nodes)])
        unit_edges = np.eye(space.num_edges)
        centroid = np.stack([eval_edge_field(space, unit_edges[e]) for e in range(space.num_edges)])
    with clock("reference"):
        ref = SymfemCells(symfem, exact, cells, "triangle")
    _orientation_facts(space.edges, space.signs)
    # galerkin reorders clockwise triangles in place; cell indices stay the same.
    assert ref.min_measure > 0

    nodes = {n: n for n in range(mesh.num_nodes)}
    edges = {tuple(int(v) for v in edge): i for i, edge in enumerate(space.edges)}
    assert set(edges) == {key[0] for key in ref.curlcurl}
    grad_ref = np.zeros_like(p1_grad)
    for (n, t), value in ref.p1_grad.items():
        grad_ref[n, t] = value
    centroid_ref = np.zeros_like(centroid)
    for (edge, t), value in ref.edge_centroid.items():
        centroid_ref[edges[edge], t] = value

    observables = [
        observable("circulation of each Nedelec function along each edge, low -> high id, minus identity",
                   "1", "max abs (exact rational)", float(ref.circulation_error), EXACT),
        observable("P1 basis at the vertices minus Kronecker delta", "1", "max abs (exact rational)",
                   float(ref.nodality_error), EXACT),
        observable("P1 basis gradient per triangle", "1/m", "max abs difference / max abs reference",
                   relative_difference(p1_grad, grad_ref), SAME_ELEMENT),
        observable("P1 stiffness matrix", "1", "max abs difference / max abs reference",
                   relative_difference(K, _dense(ref.p1_stiff, nodes, nodes)), SAME_ELEMENT),
        observable("P1 mass matrix", "m^2", "max abs difference / max abs reference",
                   relative_difference(M, _dense(ref.p1_mass, nodes, nodes)), SAME_ELEMENT),
        observable("Nedelec basis at triangle centroids", "1/m", "max abs difference / max abs reference",
                   relative_difference(centroid, centroid_ref), SAME_ELEMENT),
        observable("Nedelec curl-curl matrix", "1/m^2", "max abs difference / max abs reference",
                   relative_difference(S, _dense(ref.curlcurl, edges, edges)), SAME_ELEMENT),
        observable("Nedelec mass matrix", "1", "max abs difference / max abs reference",
                   relative_difference(Me, _dense(ref.edge_mass, edges, edges)), SAME_ELEMENT),
        observable("Nedelec x P1 gradient coupling matrix", "1/m", "max abs difference / max abs reference",
                   relative_difference(G, _dense(ref.edge_grad, edges, nodes)), SAME_ELEMENT),
    ]
    emit(make_record(
        case="elements-p1-nedelec-triangles",
        physics="element definitions: P1 Lagrange and lowest-order Nedelec (first kind) on triangles",
        api="galerkin.assembly.assemble_stiffness/assemble_mass, galerkin.postprocess.element_gradient, "
            "galerkin.edge.EdgeSpace/assemble_curlcurl/assemble_edge_mass/assemble_edge_grad/eval_edge_field",
        discretization="P1 Lagrange triangles; Whitney edge elements, edges directed low -> high node id",
        tool="symfem", tool_discretization='create_element("triangle", "Lagrange", 1) and '
                                           '("triangle", "Nedelec", 0), map_to_cell, exact sympy integrals',
        matched=["same 7 nodes (rational coordinates) and 6 triangles, node ids scrambled",
                 "obtuse, thin and clockwise triangles included",
                 "symfem vertices passed in ascending global node id",
                 "unit coefficients",
                 "Nedelec degrees of freedom: unit-tangent circulation, low -> high node id "
                 "(checked exactly; identity, no sign or scale conversion)"],
        not_matched=["galerkin evaluates in float64, symfem in exact rationals",
                     "P1 load vector (galerkin uses a one-point centroid rule) and boundary mass not compared"],
        observables=observables,
        analytical_acceptance="tests/galerkin/test_electrostatics.py, tests/galerkin/test_edge_elements.py",
        stopwatch=clock))


def test_p1_and_nedelec_tetrahedra_match_symfem(symfem):
    exact, cells = _mesh3d()
    clock = Stopwatch()
    with clock("openphysics"):
        mesh = Mesh3D(_as_float(exact), np.array(cells))
        space = EdgeSpace3D(mesh)
        K, M = assemble_stiffness_3d(mesh).toarray(), assemble_mass_3d(mesh).toarray()
        S, Me = assemble_curlcurl_3d(space).toarray(), assemble_edge_mass_3d(space).toarray()
        G = assemble_edge_grad_3d(space).toarray()
        grads, _ = tet_gradients(mesh)
        unit_edges = np.eye(space.num_edges)
        centroid = np.stack([eval_edge_field_3d(space, unit_edges[e])
                             for e in range(space.num_edges)])
    with clock("reference"):
        ref = SymfemCells(symfem, exact, cells, "tetrahedron")
    _orientation_facts(space.edges, space.signs)
    assert ref.min_measure > 0

    nodes = {n: n for n in range(mesh.num_nodes)}
    edges = {tuple(int(v) for v in edge): i for i, edge in enumerate(space.edges)}
    assert set(edges) == {key[0] for key in ref.curlcurl}
    # Barycentric gradients of each tetrahedron, indexed by global node id.
    p1_grad = np.zeros((mesh.num_nodes, mesh.num_tets, 3))
    for t, tet in enumerate(mesh.tets):
        p1_grad[tet, t] = grads[t]
    grad_ref = np.zeros_like(p1_grad)
    for (n, t), value in ref.p1_grad.items():
        grad_ref[n, t] = value
    centroid_ref = np.zeros_like(centroid)
    for (edge, t), value in ref.edge_centroid.items():
        centroid_ref[edges[edge], t] = value

    observables = [
        observable("circulation of each Nedelec function along each edge, low -> high id, minus identity",
                   "1", "max abs (exact rational)", float(ref.circulation_error), EXACT),
        observable("P1 basis at the vertices minus Kronecker delta", "1", "max abs (exact rational)",
                   float(ref.nodality_error), EXACT),
        observable("P1 basis gradient per tetrahedron", "1/m", "max abs difference / max abs reference",
                   relative_difference(p1_grad, grad_ref), SAME_ELEMENT),
        observable("P1 stiffness matrix", "m", "max abs difference / max abs reference",
                   relative_difference(K, _dense(ref.p1_stiff, nodes, nodes)), SAME_ELEMENT),
        observable("P1 mass matrix", "m^3", "max abs difference / max abs reference",
                   relative_difference(M, _dense(ref.p1_mass, nodes, nodes)), SAME_ELEMENT),
        observable("Nedelec basis at tetrahedron centroids", "1/m", "max abs difference / max abs reference",
                   relative_difference(centroid, centroid_ref), SAME_ELEMENT),
        observable("Nedelec curl-curl matrix", "1/m", "max abs difference / max abs reference",
                   relative_difference(S, _dense(ref.curlcurl, edges, edges)), SAME_ELEMENT),
        observable("Nedelec mass matrix", "m", "max abs difference / max abs reference",
                   relative_difference(Me, _dense(ref.edge_mass, edges, edges)), SAME_ELEMENT),
        observable("Nedelec x P1 gradient coupling matrix", "1", "max abs difference / max abs reference",
                   relative_difference(G, _dense(ref.edge_grad, edges, nodes)), SAME_ELEMENT),
    ]
    emit(make_record(
        case="elements-p1-nedelec-tetrahedra",
        physics="element definitions: P1 Lagrange and lowest-order Nedelec (first kind) on tetrahedra",
        api="galerkin.assembly3d.assemble_stiffness_3d/assemble_mass_3d/tet_gradients, "
            "galerkin.edge3d.EdgeSpace3D/assemble_curlcurl_3d/assemble_edge_mass_3d/"
            "assemble_edge_grad_3d/eval_edge_field_3d",
        discretization="P1 Lagrange tetrahedra; Whitney edge elements, edges directed low -> high node id",
        tool="symfem", tool_discretization='create_element("tetrahedron", "Lagrange", 1) and '
                                           '("tetrahedron", "Nedelec", 0), map_to_cell, exact sympy integrals',
        matched=["same 6 nodes (rational coordinates) and 4 tetrahedra around one interior edge, "
                 "node ids scrambled",
                 "symfem vertices passed in ascending global node id",
                 "unit coefficients",
                 "Nedelec degrees of freedom: unit-tangent circulation, low -> high node id "
                 "(checked exactly; identity, no sign or scale conversion)"],
        not_matched=["galerkin evaluates in float64, symfem in exact rationals"],
        observables=observables,
        analytical_acceptance="tests/galerkin/test_cavity_modes.py, tests/galerkin/test_cavity3d_validation.py",
        stopwatch=clock))
