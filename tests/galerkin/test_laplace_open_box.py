# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Neumann-wall rectangle panels: analytic, series and independent P2 references."""
import numpy as np
import pytest
from crosscheck import require_tool
import galerkin.laplace_open_box as module
from galerkin.laplace_open_box import solve_open_rectangle as solve
from meshine import Domain, rectangle, generate


def ngon(center, radius, count):
    theta = 2 * np.pi * (np.arange(count) + .5) / count
    return np.asarray(center) + radius * np.column_stack((np.cos(theta), np.sin(theta)))


def box(x0, x1, y0, y1):
    return np.array([[x0, y0], [x1, y0], [x1, y1], [x0, y1]])


def centered(values):
    """Remove every term f(target)+g(source); what zero total charge can observe."""
    return values - values.mean(0, keepdims=True) - values.mean(1, keepdims=True) + values.mean()


def series(targets, sources, width, height, modes):
    """Independent x-cosine expansion of 2*pi*G_N with closed-form y dependence."""
    x, y = targets[:, None, 0], targets[:, None, 1]
    xs, ys = sources[None, :, 0], sources[None, :, 1]
    low, high = np.minimum(y, ys), np.maximum(y, ys)
    out = (-high + (y * y + ys * ys) / (2 * height)) / width
    for n in range(1, modes + 1):
        k = n * np.pi / width
        y_part = (np.exp(-k * (high - low)) * (1 + np.exp(-2 * k * low)) * (1 + np.exp(-2 * k * (height - high)))
                  / (2 * k * (1 - np.exp(-2 * k * height))))
        out = out + 2 / width * np.cos(k * x) * np.cos(k * xs) * y_part
    return 2 * np.pi * out


@pytest.mark.parametrize('width,height', [(1, 1), (1, .25), (.25, 1), (1, 1 / 16)])
def test_kernel_matches_independent_cosine_series(width, height):
    rng = np.random.default_rng(7)
    targets = rng.uniform(.01, .99, (9, 2)) * [width, height]
    sources = rng.uniform(.01, .99, (7, 2)) * [width, height]
    assert np.min(abs(targets[:, None, 1] - sources[None, :, 1])) > 1e-3 * height
    ours = centered(module.point_kernel(targets, sources, width, height))
    reference = centered(series(targets, sources, width, height, modes=40000))
    assert np.max(abs(ours - reference)) / np.max(abs(reference)) < 1e-12


def test_kernel_has_zero_wall_flux_for_a_neutral_pair_and_unit_source_flux():
    width, height, step = 1., .4, 1e-4
    sources = np.array([[.3, .1], [.7, .33]])

    def pair(points):
        values = module.point_kernel(points, sources, width, height)
        return values[:, 0] - values[:, 1]
    y = np.linspace(.02, .38, 7)
    x = np.linspace(.02, .98, 7)
    for wall, normal in [(np.c_[0 * y, y], [1, 0]), (np.c_[width + 0 * y, y], [-1, 0]),
                         (np.c_[x, 0 * x], [0, 1]), (np.c_[x, height + 0 * x], [0, -1])]:
        n = step * np.asarray(normal, float)
        derivative = (-3 * pair(wall) + 4 * pair(wall + n) - pair(wall + 2 * n)) / (2 * step)
        assert np.max(abs(derivative)) < 1e-6
    theta = np.linspace(0, 2 * np.pi, 400, endpoint=False)
    ring = np.column_stack((np.cos(theta), np.sin(theta)))
    radial = (pair(sources[0] + 0.01001 * ring) - pair(sources[0] + 0.00999 * ring)) / 2e-5
    assert abs(radial.mean() * 2 * np.pi * 0.01 / (-2 * np.pi) - 1) < 1e-6


def two_wires(box_scale, sides, radius=.02, distance=.1):
    s = 1 / box_scale
    return [ngon([.5 - distance / 2 * s, .5], radius * s, sides), ngon([.5 + distance / 2 * s, .5], radius * s, sides)]


def test_two_circular_wires_converge_to_the_free_space_capacitance():
    exact = np.pi / np.arccosh(.1 / (2 * .02))
    errors = []
    for scale in (1., 2., 4.):
        result = solve(two_wires(scale, 128), width=1., height=1., grounds=[1], panels_per_edge=2)
        errors.append(result.capacitance_per_permittivity[0, 0] / exact - 1)
        assert result.charge_sum_error <= 1e-10 and result.matrix_refinement_error <= 1e-10
    assert abs(errors[0]) > abs(errors[1]) > abs(errors[2]) and abs(errors[2]) < 1e-3, errors
    # Box error ~ 1/L^2 and polygon error ~ 1/n^2: extrapolating both recovers pi/acosh(d/2a).
    values = {(scale, sides): solve(two_wires(scale, sides), width=1., height=1., grounds=[1],
                                    panels_per_edge=2 if sides == 128 else 1).capacitance_per_permittivity[0, 0]
              for scale in (8., 16.) for sides in (128, 256)}
    polygon = {scale: (4 * values[scale, 256] - values[scale, 128]) / 3 for scale in (8., 16.)}
    assert abs((4 * polygon[16.] - polygon[8.]) / 3 / exact - 1) < 1e-6


def thin_wire_capacitance(first, second, radius, mirror_x, mirror_y):
    """Two thin wires next to Neumann walls through the origin (same-sign images)."""
    def images(p):
        out = [p]
        if mirror_x:
            out.append(p * [-1, 1])
        if mirror_y:
            out.append(p * [1, -1])
        if mirror_x and mirror_y:
            out.append(-p)
        return out

    def potential(target, source, own):
        return sum(-np.log(radius) if own and k == 0 else -np.log(np.linalg.norm(target - image))
                   for k, image in enumerate(images(source)))
    return 2 * np.pi / (potential(first, first, True) + potential(second, second, True)
                        - 2 * potential(first, second, False))


@pytest.mark.parametrize('mirror_x', [False, True], ids=['bottom-wall', 'corner'])
def test_thin_wires_near_walls_match_image_charges_on_wall_scaled_boxes(mirror_x):
    radius, scale = .00025, 8.
    first = np.array([.02 if mirror_x else 0., .03])
    second = first + [.1, 0]
    shift = np.array([0. if mirror_x else .5, 0.])
    polygons = [ngon(shift + first / scale, radius / scale, 128), ngon(shift + second / scale, radius / scale, 128)]
    result = solve(polygons, width=1., height=1., grounds=[1], panels_per_edge=2)
    assert result.smooth_interpolation_boxes > 1
    reference = thin_wire_capacitance(first, second, radius, mirror_x, True)
    assert abs(result.capacitance_per_permittivity[0, 0] / reference - 1) < 2e-4


def coplanar():
    """Unbacked coplanar line: a 0.3 mm signal between 1 mm grounds, 0.2 mm gaps, 4 mm square box."""
    y0, y1 = 2.2e-3, 2.235e-3
    return [box(1.85e-3, 2.15e-3, y0, y1), box(.65e-3, 1.65e-3, y0, y1), box(2.35e-3, 3.35e-3, y0, y1)], 4e-3, 4.235e-3


def test_unbacked_coplanar_capacitance_against_independent_quadratic_volume():
    sk = require_tool('scikit-fem')
    from skfem.helpers import dot, grad
    polygons, width, height = coplanar()
    result = solve(polygons, width=width, height=height, grounds=[1, 2], panels_per_edge=64, interpolation_degree=12)
    ours = result.capacitance_per_permittivity[0, 0]
    assert result.smooth_interpolation_boxes > 1
    corners = np.concatenate(polygons)
    errors = []
    for near in (4e-6, 2e-6, 1e-6):
        def size(x, y, near=near):  # graded toward the conductor corners
            distance = np.min(np.hypot(x[..., None] - corners[:, 0], y[..., None] - corners[:, 1]), axis=-1)
            return np.minimum(2e-4, near + .25 * distance)
        domain = Domain(size=2e-4)
        domain.add_region('vacuum', rectangle(0., 0., width, height), holes=polygons)
        mesh = generate(domain, size_fn=size, smooth=0, candidate_order='stable')
        m = sk.MeshTri(mesh.nodes.T.copy(), mesh.triangles.T.copy())
        basis = sk.Basis(m, sk.ElementTriP2())
        facets = m.boundary_facets()
        mid = m.p[:, m.facets[:, facets]].mean(axis=1).T

        def on(polygon):
            low, high = polygon.min(axis=0) - 1e-12, polygon.max(axis=0) + 1e-12
            return facets[np.all((mid > low) & (mid < high), axis=1)]
        signal = basis.get_dofs(facets=on(polygons[0])).all()
        grounded = np.concatenate([basis.get_dofs(facets=on(p)).all() for p in polygons[1:]])

        @sk.BilinearForm
        def laplace(u, v, w):
            return dot(grad(u), grad(v))
        K = laplace.assemble(basis)
        x = np.zeros(basis.N)
        x[signal] = 1.
        x = sk.solve(*sk.condense(K, np.zeros(basis.N), x=x, D=np.unique(np.concatenate((signal, grounded)))))
        errors.append(abs(float(x @ (K @ x)) / ours - 1))
    assert errors[-1] < errors[0] and errors[-1] < 1e-3, errors


def test_result_contract_currents_and_panel_refinement():
    polygons, width, height = coplanar()
    result = solve(polygons, width=width, height=height, grounds=(2, 1), panels_per_edge=32)
    assert result.signal_indices == (0,) and result.ground_indices == (1, 2)
    assert result.current_gram.shape == (3, 1, 1) and result.current_integrals.shape == (3, 1)
    assert result.current_integrals[0, 0] == pytest.approx(1, abs=1e-10)
    assert result.current_integrals[1:].sum() == pytest.approx(-1, abs=1e-10)
    # Symmetric grounds share the return equally.
    assert result.current_integrals[1, 0] == pytest.approx(result.current_integrals[2, 0], rel=1e-9)
    assert result.current_gram[1, 0, 0] == pytest.approx(result.current_gram[2, 0, 0], rel=1e-9)
    assert max(result.charge_sum_error, result.residual_error, result.reciprocity_error,
               result.current_error, result.matrix_refinement_error) <= 1e-10
    with pytest.raises(ValueError):
        result.capacitance_per_permittivity[0, 0] = 1.
    finer = solve(polygons, width=width, height=height, grounds=[1, 2], panels_per_edge=64)
    assert abs(finer.capacitance_per_permittivity[0, 0] / result.capacitance_per_permittivity[0, 0] - 1) < 1e-4
    assert abs(finer.current_gram[0, 0, 0] / result.current_gram[0, 0, 0] - 1) < 1e-2


def test_separable_kernel_terms_do_not_change_the_solution(monkeypatch):
    polygons, width, height = coplanar()
    original = solve(polygons, width=width, height=height, grounds=[1, 2], panels_per_edge=16)
    smooth = module.smooth_neumann

    def shifted(targets, sources, w, h, images):
        return smooth(targets, sources, w, h, images) + 3 * targets[:, None, 0] ** 2 + 3 * sources[None, :, 0] ** 2 + 5.
    monkeypatch.setattr(module, 'smooth_neumann', shifted)
    moved = solve(polygons, width=width, height=height, grounds=[1, 2], panels_per_edge=16)
    assert np.max(abs(moved.capacitance_per_permittivity - original.capacitance_per_permittivity)) < 1e-12 * abs(
        original.capacitance_per_permittivity).max()
    assert np.max(abs(moved.current_gram - original.current_gram)) < 1e-9 * abs(original.current_gram).max()


def test_coupled_signals_are_reciprocal_and_positive_definite():
    y0, y1 = 2.2e-3, 2.235e-3
    polygons = [box(1.6e-3, 1.9e-3, y0, y1), box(2.1e-3, 2.4e-3, y0, y1),
                box(.4e-3, 1.4e-3, y0, y1), box(2.6e-3, 3.6e-3, y0, y1)]
    result = solve(polygons, width=4e-3, height=4.235e-3, grounds=[2, 3], panels_per_edge=32)
    c = result.capacitance_per_permittivity
    assert c.shape == (2, 2) and c[0, 1] < 0 and np.all(np.linalg.eigvalsh(c) > 0)
    assert c[0, 0] == pytest.approx(c[1, 1], rel=1e-9)
    assert np.allclose(result.current_integrals[:2], np.eye(2), atol=1e-10)


@pytest.mark.parametrize('grounds,message', [
    ([], 'at least one'), ([0, 1, 2], 'at least one conductor must be a signal'), ([3], 'distinct conductor indices'),
    ([1, 1], 'at least one distinct'), ([True], 'distinct conductor indices'), ('1', 'sequence'), (1, 'sequence')])
def test_ground_selection_is_explicit(grounds, message):
    polygons, width, height = coplanar()
    with pytest.raises(ValueError, match=message):
        solve(polygons, width=width, height=height, grounds=grounds, panels_per_edge=4)


def test_admission_bounds_are_explicit():
    polygons, width, height = coplanar()
    with pytest.raises(ValueError, match=r'width/height must lie in \[0.25, 16\]'):
        solve(polygons, width=width, height=width / 16.0001, grounds=[1, 2], panels_per_edge=4)
    with pytest.raises(ValueError, match='interpolation_degree'):
        solve(polygons, width=width, height=height, grounds=[1, 2], interpolation_degree=13)
    with pytest.raises(ValueError, match='too close to the walls'):
        solve([box(1e-3, 3e-3, 1e-6, 2e-6), box(1e-3, 3e-3, 1e-3, 1.1e-3)], width=width, height=height,
              grounds=[1], panels_per_edge=4)


def test_unresolved_interpolation_is_refused(monkeypatch):
    polygons, width, height = coplanar()
    original = module._matrix

    def noisy(*args, degree, **kwargs):
        matrix, reciprocity = original(*args, degree=degree, **kwargs)
        return (matrix * (1 + 1e-9) if degree == 10 else matrix), reciprocity
    monkeypatch.setattr(module, '_matrix', noisy)
    with pytest.raises(ValueError, match='did not converge'):
        solve(polygons, width=width, height=height, grounds=[1, 2], panels_per_edge=8)
