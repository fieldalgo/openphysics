# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Public PEC cavity API: independent spectra, constraints and fixed error gates."""

from itertools import product

import numpy as np
import pytest
import scipy.linalg as la
import scipy.sparse as sp
import scipy.sparse.linalg as spla

from galerkin import (CavityResult, solve_cavity_box,
                      assemble_curlcurl_3d, assemble_edge_mass_3d,
                      eval_edge_field_3d)
import galerkin.cavity as cavity

C0 = 299792458.0


def _amplitude_spectrum(lengths, n_max=4):
    """Two positive indices give one transverse amplitude; three give two."""
    values = []
    for indices in product(range(n_max + 1), repeat=3):
        multiplicity = max(sum(i > 0 for i in indices) - 1, 0)
        values.extend([np.pi**2 * sum((i / a)**2 for i, a in zip(indices, lengths))]
                      * multiplicity)
    return np.sort(values)


def _constrained_system(space):
    free = np.setdiff1d(np.arange(space.num_edges), space.boundary_edge_ids())
    stiffness = assemble_curlcurl_3d(space)[free][:, free].tocsc()
    mass = assemble_edge_mass_3d(space)[free][:, free].tocsc()
    return space, free, stiffness, mass


def _check_result(result):
    """Reassemble on the returned SI mesh, without private normalization helpers."""
    assert isinstance(result, CavityResult)
    q, space = result.edge_coefficients, result.space
    count = result.requested_modes
    assert space.mesh is result.mesh
    assert q.shape == (space.num_edges, count)
    assert result.electric_field.shape == (count, result.mesh.num_tets, 3)
    assert result.search == "near_target"
    assert result.cluster_completeness == "not_certified"
    assert result.mode_count_policy == "exact_count_may_split_cluster"
    assert np.all(result.eigenvalues_m2 > 0)
    assert np.all(np.diff(result.frequencies_hz) >= 0)
    np.testing.assert_allclose(result.frequencies_hz,
                               C0 / (2 * np.pi) * np.sqrt(result.eigenvalues_m2), rtol=1e-12)
    # Independently identify wall edges by their common Cartesian wall, not by
    # the solver's boundary-face routine or by both endpoints being boundary nodes.
    endpoints = result.mesh.nodes[space.edges]
    walls = np.zeros(space.num_edges, dtype=bool)
    for axis in range(3):
        for position in (0, result.mesh.nodes[:, axis].max()):
            walls |= np.all(endpoints[:, :, axis] == position, axis=1)
    np.testing.assert_array_equal(result.pec_edge_ids, np.flatnonzero(walls))
    assert np.count_nonzero(q[walls]) == 0
    free = np.flatnonzero(~walls)
    stiffness = assemble_curlcurl_3d(space)[free][:, free]
    mass_full = assemble_edge_mass_3d(space)
    mass = mass_full[free][:, free]
    np.testing.assert_allclose(q.T @ mass_full @ q, np.eye(count), atol=1e-8)
    left, right = stiffness @ q[free], (mass @ q[free]) * result.eigenvalues_m2
    residual = np.linalg.norm(left - right, axis=0) / (
        np.linalg.norm(left, axis=0) + np.linalg.norm(right, axis=0))
    assert residual.max() < 1e-9
    np.testing.assert_allclose(result.relative_residuals, residual, atol=1e-12)
    fields = np.stack([eval_edge_field_3d(space, v) for v in q.T])
    assert np.linalg.norm(fields - result.electric_field) / np.linalg.norm(fields) < 1e-12
    assert np.all(q[np.argmax(abs(q), axis=0), np.arange(count)] > 0)
    # Incidence is assembled independently from endpoint orientations.
    boundary_nodes = np.unique(space.edges[walls])
    interior = np.setdiff1d(np.arange(result.mesh.num_nodes), boundary_nodes)
    rows = np.arange(len(free))
    incidence = sp.coo_matrix((np.r_[-np.ones(len(free)), np.ones(len(free))],
                              (np.r_[rows, rows], np.r_[space.edges[free, 0],
                                                       space.edges[free, 1]])),
                             shape=(len(free), result.mesh.num_nodes)).tocsc()[:, interior]
    if len(interior):
        gram = incidence.T @ mass @ incidence
        coupling = incidence.T @ mass @ q[free]
        gradient_norm2 = np.sum(coupling * spla.spsolve(gram, coupling), axis=0)
        assert np.sqrt(np.maximum(gradient_norm2, 0)).max() < 1e-9


@pytest.mark.parametrize("lengths", [(1, 1, 1), (1, .8, .6)])
def test_independent_transverse_amplitude_count_matches_refsol(lengths, refsol):
    exact = _amplitude_spectrum(lengths)
    reference = [pair[0] for pair in refsol.metallic.rect_cavity_resonances(*lengths, n_max=4)]
    np.testing.assert_allclose(exact, reference, rtol=1e-13)
    if lengths == (1, 1, 1):
        np.testing.assert_allclose(exact[:11] / np.pi**2, [2]*3 + [3]*2 + [5]*6)


@pytest.mark.parametrize("n,target,count", [(2, 210e6, 5), (3, 450e6, 7),
                                           (4, 210e6, 6), (4, 450e6, 5)])
def test_near_target_matches_complete_discrete_spectrum(n, target, count):
    lengths = (1, .8, .6)
    result = solve_cavity_box(lengths, (n, n, n), num_modes=count, target_frequency_hz=target)
    _, _, stiffness, mass = _constrained_system(result.space)
    values = la.eigvalsh(stiffness.toarray(), mass.toarray())
    assert np.count_nonzero(abs(values) < 1e-7) == (n - 1)**3
    physical = values[values > 1e-7]
    sigma = (2 * np.pi * target / C0)**2
    expected = np.sort(physical[np.argsort(abs(physical - sigma))[:count]])
    np.testing.assert_allclose(result.eigenvalues_m2, expected, rtol=1e-10, atol=1e-10)
    if target == 450e6:
        assert result.eigenvalues_m2.min() > physical[0] * 1.5
    _check_result(result)


def test_low_target_keeps_physical_candidates_and_cluster_multiplicity():
    # A target below the fundamental must not spend its candidate budget on
    # the 343-dimensional gradient kernel. Request three complete cube clusters.
    result = solve_cavity_box((1, 1, 1), (8, 8, 8), num_modes=11, target_frequency_hz=210e6)
    groups = [np.count_nonzero((result.eigenvalues_m2 / np.pi**2 > lo)
                               & (result.eigenvalues_m2 / np.pi**2 < hi))
              for lo, hi in ((1, 2.5), (2.5, 4), (4, 5.5))]
    assert groups == [3, 2, 6]
    _check_result(result)
    # Exact counts may cut the six-member cluster; metadata makes no completeness claim.
    partial = solve_cavity_box((1, 1, 1), (8, 8, 8), num_modes=6, target_frequency_hz=210e6)
    assert len(partial.frequencies_hz) == 6
    _check_result(partial)


def test_interior_edge_between_wall_nodes_remains_free():
    result = solve_cavity_box((1, 1, 1), (1, 1, 1), num_modes=1, target_frequency_hz=210e6)
    # All eight vertices are boundary vertices, but the body diagonal is free.
    assert len(result.mesh.boundary_nodes()) == result.mesh.num_nodes
    assert np.count_nonzero(result.edge_coefficients) == 1
    _check_result(result)
    with pytest.raises(RuntimeError, match="physical degrees of freedom"):
        solve_cavity_box((1, 1, 1), (1, 1, 1), num_modes=2, target_frequency_hz=210e6)


@pytest.mark.parametrize("cells", [(2, 2, 2), (2, 3, 4), (3, 3, 3), (4, 4, 4)])
def test_alternating_mesh_is_conforming_and_preserves_cells_and_reflections(cells):
    lengths = np.array([1., .8, .6])
    result = solve_cavity_box(lengths, cells, num_modes=1, target_frequency_hz=240e6)
    mesh = result.mesh
    assert mesh.num_nodes == np.prod(np.array(cells) + 1)
    assert mesh.num_tets == 6 * np.prod(cells)
    np.testing.assert_allclose(mesh.volumes(), np.prod(lengths)/(6*np.prod(cells)), rtol=1e-13)
    grid = np.rint(mesh.nodes / lengths * cells).astype(int)
    local = grid[mesh.tets]
    lower = local.min(axis=1)
    assert np.all(local.max(axis=1) - lower == 1)
    _, per_cell = np.unique(lower, axis=0, return_counts=True)
    np.testing.assert_array_equal(per_cell, np.full(np.prod(cells), 6))
    faces = np.concatenate([mesh.tets[:, face] for face in
                            ([0, 1, 2], [0, 1, 3], [0, 2, 3], [1, 2, 3])])
    faces, counts = np.unique(np.sort(faces, axis=1), axis=0, return_counts=True)
    assert set(counts) == {1, 2}
    nx, ny, nz = cells
    assert np.count_nonzero(counts == 1) == 4 * (nx*ny + nx*nz + ny*nz)
    wall_faces = grid[faces[counts == 1]]
    on_wall = np.zeros(len(wall_faces), dtype=bool)
    for axis in range(3):
        on_wall |= np.all(wall_faces[:, :, axis] == 0, axis=1)
        on_wall |= np.all(wall_faces[:, :, axis] == cells[axis], axis=1)
    assert on_wall.all()
    assert mesh.num_nodes - result.space.num_edges + len(faces) - mesh.num_tets == 1
    topology = set(map(tuple, np.sort(mesh.tets, axis=1)))
    for axis, n in enumerate(cells):
        if n % 2 == 0:
            reflected = grid.copy()
            reflected[:, axis] = n - reflected[:, axis]
            ids = np.ravel_multi_index(reflected.T, tuple(np.array(cells) + 1))
            assert set(map(tuple, np.sort(ids[mesh.tets], axis=1))) == topology


def _analytic_111_overlap(result, quadrature_order=5):
    """Integrate with the exact two-dimensional transverse standing-wave space.

    Tensor Gauss integration mapped to a tetrahedron is independent of the
    assembly and centroid evaluator. Both analytic vectors have unit L2 norm.
    Singular values compare subspaces, without assigning TE/TM labels to a
    possibly rotated or split discrete doublet.
    """
    mesh, space = result.mesh, result.space
    lengths = mesh.nodes.max(axis=0)
    wavevector = np.pi / lengths
    amplitudes = la.null_space(wavevector[None, :]) * np.sqrt(8 / np.prod(lengths))
    points = mesh.nodes[mesh.tets]
    affine = np.concatenate([np.ones((mesh.num_tets, 4, 1)), points], axis=2)
    gradients = np.linalg.inv(affine)[:, 1:, :].transpose(0, 2, 1)
    jacobian = abs(np.linalg.det(points[:, 1:] - points[:, :1]))
    local_edges = ((0, 1), (0, 2), (0, 3), (1, 2), (1, 3), (2, 3))
    coefficients = result.edge_coefficients[space.tet_edges, 3:5] * space.signs[:, :, None]
    gauss, weights = np.polynomial.legendre.leggauss(quadrature_order)
    gauss, weights = (gauss + 1)/2, weights/2
    overlap = np.zeros((2, 2))
    for i, j, k in product(range(quadrature_order), repeat=3):
        s, t, u = gauss[[i, j, k]]
        bary = np.array([(1-s)*(1-t)*(1-u), s, (1-s)*t, (1-s)*(1-t)*u])
        position = np.einsum("i,tij->tj", bary, points)
        sn, cs = np.sin(position * wavevector), np.cos(position * wavevector)
        factors = np.column_stack([cs[:, 0]*sn[:, 1]*sn[:, 2],
                                   sn[:, 0]*cs[:, 1]*sn[:, 2],
                                   sn[:, 0]*sn[:, 1]*cs[:, 2]])
        exact = factors[:, :, None] * amplitudes[None, :, :]
        basis = np.stack([bary[a]*gradients[:, b] - bary[b]*gradients[:, a]
                          for a, b in local_edges], axis=1)
        numerical = np.einsum("ted,tek->tdk", basis, coefficients)
        weight = weights[i]*weights[j]*weights[k]*(1-s)**2*(1-t)*jacobian
        overlap += np.einsum("tdi,tdj,t->ij", numerical, exact, weight)
    return la.svdvals(overlap)


def test_111_eigenspace_and_expanded_search_keep_both_polarizations():
    lengths = (1, .8, .6)
    target = C0/(2*np.pi) * np.sqrt(1.3 * _amplitude_spectrum(lengths)[0])
    errors = []
    for n in (4, 8):
        result = solve_cavity_box(lengths, (n,)*3, num_modes=5, target_frequency_hz=target)
        singular = _analytic_111_overlap(result)
        assert np.max(singular) <= 1 + 1e-9
        errors.append(np.sqrt(np.maximum(1 - np.mean(singular**2), 0)))
    assert singular.min() > .95
    assert errors[-1] < errors[0]
    # A second quadrature order rules out integration error explaining the overlap.
    np.testing.assert_allclose(_analytic_111_overlap(result, 6), singular, atol=1e-9, rtol=0)
    expanded = solve_cavity_box(lengths, (8,)*3, num_modes=11, target_frequency_hz=target)
    np.testing.assert_allclose(expanded.eigenvalues_m2[:5], result.eigenvalues_m2, rtol=1e-10)
    mass = assemble_edge_mass_3d(result.space)
    cross = result.edge_coefficients[:, 3:5].T @ mass @ expanded.edge_coefficients[:, 3:5]
    assert la.svdvals(cross).min() > 1 - 1e-8


@pytest.mark.parametrize("scale", [1e-9, 1e-6, 1e3])
def test_physical_scaling_preserves_spectrum_and_degenerate_subspace(scale):
    base = solve_cavity_box((1, 1, 1), (4, 4, 4), num_modes=5, target_frequency_hz=210e6)
    scaled = solve_cavity_box((scale,)*3, (4, 4, 4), num_modes=5,
                               target_frequency_hz=210e6 / scale)
    np.testing.assert_allclose(scaled.frequencies_hz * scale, base.frequencies_hz, rtol=1e-9)
    np.testing.assert_allclose(scaled.eigenvalues_m2 * scale**2, base.eigenvalues_m2, rtol=1e-9)
    np.testing.assert_allclose(scaled.mesh.nodes / scale, base.mesh.nodes, atol=1e-15)
    np.testing.assert_array_equal(scaled.space.edges, base.space.edges)
    mass = assemble_edge_mass_3d(base.space)
    overlap = base.edge_coefficients.T @ mass @ (scaled.edge_coefficients * np.sqrt(scale))
    assert la.svdvals(overlap).min() > 1 - 1e-7
    _check_result(scaled)


@pytest.mark.parametrize("argument,value", [
    ("lengths_m", (1, 0, 1)), ("lengths_m", (1, np.inf, 1)),
    ("lengths_m", (1, np.nan, 1)), ("lengths_m", (1, True, 1)),
    ("lengths_m", (1, 1)), ("lengths_m", None), ("lengths_m", (1e-200,)*3),
    ("subdivisions", (1, 2.0, 3)), ("subdivisions", (1, False, 3)),
    ("subdivisions", (1, -1, 3)), ("subdivisions", (1, 1, 1, 1)),
    ("num_modes", 0), ("num_modes", True), ("num_modes", 1.5),
    ("target_frequency_hz", 0), ("target_frequency_hz", np.inf),
    ("target_frequency_hz", np.nan), ("target_frequency_hz", "210e6"),
    ("target_frequency_hz", True), ("target_frequency_hz", 1+2j),
])
def test_invalid_arguments_are_rejected(argument, value):
    kwargs = dict(lengths_m=(1, 1, 1), subdivisions=(2, 2, 2), num_modes=1,
                  target_frequency_hz=210e6)
    kwargs[argument] = value
    with pytest.raises(ValueError):
        solve_cavity_box(**kwargs)


def test_target_is_required():
    with pytest.raises(TypeError, match="target_frequency_hz"):
        solve_cavity_box((1, 1, 1), (2, 2, 2))


def test_nonconvergence_does_not_return_partial_arpack_result(monkeypatch):
    def failed(*args, **kwargs):
        raise spla.ArpackNoConvergence("injected nonconvergence", np.array([20.]),
                                       np.zeros((args[0].shape[0], 1)))
    monkeypatch.setattr(cavity.spla, "eigsh", failed)
    with pytest.raises(RuntimeError, match="nonconvergence"):
        solve_cavity_box((1, 1, 1), (4, 4, 4), num_modes=1, target_frequency_hz=210e6)


@pytest.mark.parametrize("failure", ["insufficient", "residual", "orthogonality", "factorization"])
def test_failed_numerical_checks_do_not_return_results(monkeypatch, failure):
    original = cavity.spla.eigsh

    def damaged(*args, **kwargs):
        if failure == "factorization":
            raise RuntimeError("injected factorization failure")
        values, vectors = original(*args, **kwargs)
        if failure == "insufficient":
            return values[:1], vectors[:, :1]
        if failure == "residual":
            values *= 1.01
        if failure == "orthogonality":
            vectors[:, 1] = vectors[:, 0]
        return values, vectors

    monkeypatch.setattr(cavity.spla, "eigsh", damaged)
    match = {"insufficient": "found only", "residual": "residual",
             "orthogonality": "orthogonality", "factorization": "factorization"}[failure]
    with pytest.raises(RuntimeError, match=match):
        solve_cavity_box((1, 1, 1), (4, 4, 4), num_modes=5, target_frequency_hz=210e6)


@pytest.mark.slow
@pytest.mark.parametrize("lengths,multiplicities", [((1, 1, 1), (3, 2, 6)),
                                                  ((1, .8, .6), (1, 1, 1, 2))])
def test_fixed_three_mesh_cluster_convergence(lengths, multiplicities, refsol):
    """Keep the declared 4/8/16 sequence and >1.8 gate, including any failures.

    Complete analytic clusters are requested. A finite reference enumeration
    suffices here: any omitted index >=5 has k^2 >=(5*pi/max(lengths))^2,
    strictly above the band being compared. This is not a production-search guarantee.
    """
    count = sum(multiplicities)
    reference = _amplitude_spectrum(lengths)[:count]
    np.testing.assert_allclose(reference, [p[0] for p in
        refsol.metallic.rect_cavity_resonances(*lengths, n_max=4)][:count], rtol=1e-13)
    boundaries = np.cumsum(multiplicities)[:-1]
    exact_groups = np.split(reference, boundaries)
    errors, widths = [], []
    for n in (4, 8, 16):
        target = C0 / (2 * np.pi) * np.sqrt(1.3 * reference[0])
        result = solve_cavity_box(lengths, (n,)*3, num_modes=count, target_frequency_hz=target)
        groups = np.split(result.eigenvalues_m2, boundaries)
        errors.append([abs(got.mean()/exact[0] - 1) for got, exact in zip(groups, exact_groups)])
        widths.append([np.ptp(got)/exact[0] for got, exact in zip(groups, exact_groups)])
    errors, widths = np.asarray(errors), np.asarray(widths)
    rates = np.log2(errors[-2] / errors[-1])
    print(f"box={lengths}, mean_errors={errors.tolist()}, widths={widths.tolist()}, rates={rates}")
    assert np.all(np.diff(errors, axis=0) < 0), f"nonmonotone cluster errors: {errors}"
    assert np.all(rates > 1.8), f"cluster mean order {rates}; errors {errors}"
    split = widths[-1] > 1e-10
    assert np.all(np.log2(widths[-2, split] / widths[-1, split]) > 1.8)
    assert np.max(abs(np.sqrt(result.eigenvalues_m2 / reference) - 1)) < .01
