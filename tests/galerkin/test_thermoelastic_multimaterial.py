# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Per-region thermoelasticity and heat-to-mechanics coupling.

References: refsol.elasticity_multilayer.composite_cylinder (exact Lamé with a
per-layer temperature change a_i + b_i ln(r/r0)) and
refsol.thermal_multilayer.composite_cylinder (exact layered conduction). Both
import no engine code.
"""
import numpy as np
import pytest

from galerkin.mesh import layered_annulus_mesh, layered_rectangle_mesh
from galerkin.thermal_mechanical import WorkflowStageError, solve_steady_thermoelasticity
from galerkin.thermoelasticity import freeze_temperature, solve_thermoelasticity
from galerkin.transient_heat import solve_transient_heat
from galerkin.transient_thermal_mechanical import solve_transient_thermoelasticity
from refsol import elasticity_multilayer, thermal_multilayer

NAMES = ['steel', 'polymer', 'aluminium']
R0, EDGES = .02, [.03, .045, .05]
E, NU = [200e9, 3e9, 70e9], [.3, .38, .33]
ALPHA = [1.2e-5, 7e-5, 2.3e-5]
K = [45., .25, 200.]
TREF = 293.


def _by_name(values, names=NAMES):
    return dict(zip(names, values))


def _mesh(n):
    return layered_annulus_mesh(R0, EDGES, [2*n, 3*n, n], 24*n, NAMES)


def _supports(n):
    nt = 24*n
    return {(0, 1): 0., (nt//2, 1): 0., (nt//4, 0): 0.}


def _quadrature(mesh):
    x, w = np.polynomial.legendre.leggauss(8)
    x, w = (x+1)/2, w/2
    a, b = np.meshgrid(x, x, indexing='ij')
    bary = np.stack([(1-a)*(1-b), a, (1-a)*b], axis=-1).reshape(-1, 3)
    weights = (2*w[:, None]*w[None, :]*(1-a)).ravel()
    points = np.einsum('qi,tij->tqj', bary, mesh.nodes[mesh.triangles])
    weight = mesh.areas()[:, None]*weights[None, :]
    return bary, points, weight, np.repeat(mesh.regions, len(weights))


def _errors(mesh, mechanics, reference):
    """Displacement, in-plane stress and sigma_zz L2 errors (8x8 Duffy)."""
    bary, points, weight, layer = _quadrature(mesh)
    exact = reference(points.reshape(-1, 2), layer)
    uh = np.einsum('qi,tid->tqd', bary, mechanics.displacement[mesh.triangles])
    du = uh-exact.displacement.reshape(uh.shape)
    ds = mechanics.stress[:, None, :]-exact.stress.reshape(*uh.shape[:2], 3)
    dz = mechanics.sigma_zz[:, None]-exact.out_of_plane_stress.reshape(uh.shape[:2])
    return (np.sqrt(np.sum(weight[..., None]*du**2)), np.sqrt(np.sum(weight[..., None]*ds**2)),
            np.sqrt(np.sum(weight*dz**2)))


def _orders(e):
    e = np.asarray(e)
    return np.log2(e[:-1]/e[1:])


def _material_kw(plane):
    return dict(young_modulus=_by_name(E), poisson_ratio=_by_name(NU),
                thermal_expansion_per_k=_by_name(ALPHA), plane=plane)


def test_uniform_mappings_match_the_scalar_mechanical_stage():
    mesh = layered_rectangle_mesh([.3, 1.], .5, [3, 5], 4, ['a', 'b'])
    temperature = 300.+40*mesh.nodes[:, 0]+15*mesh.nodes[:, 1]**2
    snap = freeze_temperature(mesh, temperature)
    bc = {(int(i), c): 0. for i in mesh.boundary['left'] for c in (0, 1)}
    common = dict(reference_temperature_k=TREF, plane='strain', dirichlet=bc,
                  traction={'right': [1e6, 0.]})
    scalar = solve_thermoelasticity(mesh, snap, thermal_expansion_per_k=1.2e-5,
                                    young_modulus=70e9, poisson_ratio=.33, **common)
    for kw in (dict(thermal_expansion_per_k={'a': 1.2e-5, 'b': 1.2e-5}, young_modulus=70e9, poisson_ratio=.33),
               dict(thermal_expansion_per_k={'a': 1.2e-5, 'b': 1.2e-5}, young_modulus={'a': 70e9, 'b': 70e9},
                    poisson_ratio={'a': .33, 'b': .33})):
        mapped = solve_thermoelasticity(mesh, snap, **kw, **common)
        for field in ('displacement', 'total_strain', 'thermal_strain', 'stress', 'sigma_zz',
                      'epsilon_zz', 'load_thermal', 'reaction'):
            a, b = getattr(mapped, field), getattr(scalar, field)
            np.testing.assert_allclose(a, b, rtol=1e-12, atol=1e-12*max(np.max(abs(b)), 1e-300))
        np.testing.assert_allclose(mapped.physical_elastic_energy, scalar.physical_elastic_energy, rtol=1e-12)
        assert isinstance(mapped.thermal_expansion_per_k, dict)
    assert scalar.young_modulus == 70e9


def test_scalar_materials_beside_a_mapping_are_recorded_as_python_floats():
    """A scalar given next to a mapping is recorded as float, never the caller's object."""
    mesh = layered_rectangle_mesh([.3, 1.], .5, [2, 2], 2, ['a', 'b'])
    snap = freeze_temperature(mesh, np.full(len(mesh.nodes), 320.))
    bc = {(int(i), c): 0. for i in mesh.boundary['left'] for c in (0, 1)}
    E0 = np.array(70e9)
    r = solve_thermoelasticity(mesh, snap, reference_temperature_k=TREF, plane='strain', dirichlet=bc,
                               thermal_expansion_per_k={'a': 1e-5, 'b': 2e-5}, young_modulus=E0,
                               poisson_ratio=np.float32(.25))
    assert type(r.young_modulus) is float and r.young_modulus == 70e9
    assert type(r.poisson_ratio) is float and r.poisson_ratio == float(np.float32(.25))
    assert r.thermal_expansion_per_k == {'a': 1e-5, 'b': 2e-5}
    E0[...] = 1.
    assert r.young_modulus == 70e9
    r = solve_thermoelasticity(mesh, snap, reference_temperature_k=TREF, plane='strain', dirichlet=bc,
                               thermal_expansion_per_k=1e-5, young_modulus={'a': 70e9, 'b': 70e9},
                               poisson_ratio=0)
    assert type(r.thermal_expansion_per_k) is float and type(r.poisson_ratio) is float


@pytest.mark.slow
@pytest.mark.parametrize('plane', ['stress', 'strain'])
def test_expansion_mismatch_composite_cylinder_converges(plane):
    # Uniform heating by 120 K; free inner and outer surfaces. All stress comes
    # from the alpha mismatch between the bonded shells.
    errors = []
    reference = lambda p, i: elasticity_multilayer.composite_cylinder(
        p, inner_radius=R0, interfaces=EDGES, young_moduli=E, poisson_ratios=NU, plane=plane,
        thermal_expansions=ALPHA, temperature_change=[[120., 0.]]*3, layer=i)
    peak = np.max(abs(reference(np.array([[.03, 0.], [.0451, 0.]]), np.array([0, 2])).hoop_stress))
    for n in (1, 2, 4, 8):
        mesh = _mesh(n)
        snap = freeze_temperature(mesh, np.full(len(mesh.nodes), TREF+120.))
        r = solve_thermoelasticity(mesh, snap, reference_temperature_k=TREF, dirichlet=_supports(n),
                                   **_material_kw(plane))
        errors.append(_errors(mesh, r, reference))
        assert np.max(abs(r.reaction)) < 1e-9*peak*R0
    errors = np.array(errors)
    print(plane, 'mismatch errors (u, stress, szz)', errors.tolist(), _orders(errors[:, 0]),
          _orders(errors[:, 1]), _orders(errors[:, 2]) if plane == 'strain' else '')
    assert np.all(_orders(errors[:, 0])[-2:] >= 1.8)
    assert np.all(_orders(errors[:, 1])[-2:] >= .9)
    if plane == 'strain':
        assert np.all(_orders(errors[:, 2])[-2:] >= .9)
    else:
        assert np.all(errors[:, 2] == 0)


def _temperature_rows(t_in, t_out):
    """Exact layered conduction T = a_i + b_i ln(r/R0), as rows (a_i - Tref, b_i)."""
    rows = []
    for i, (lo, hi) in enumerate(zip([R0]+EDGES[:-1], EDGES)):
        r = np.array([lo+.25*(hi-lo), lo+.75*(hi-lo)])
        t = thermal_multilayer.composite_cylinder(np.column_stack([r, 0*r]), inner_radius=R0,
            interfaces=EDGES, conductivities=K, inner_temperature=t_in, outer_temperature=t_out,
            layer=np.array([i, i])).temperature
        b = (t[1]-t[0])/np.log(r[1]/r[0])
        rows.append([t[0]-b*np.log(r[0]/R0)-TREF, b])
    return np.array(rows)


@pytest.mark.slow
@pytest.mark.parametrize('plane', ['stress', 'strain'])
def test_coupled_heat_to_mechanics_composite_cylinder_converges(plane):
    rows = _temperature_rows(420., 300.)
    reference = lambda p, i: elasticity_multilayer.composite_cylinder(
        p, inner_radius=R0, interfaces=EDGES, young_moduli=E, poisson_ratios=NU, plane=plane,
        thermal_expansions=ALPHA, temperature_change=rows, layer=i)
    errors, t_err = [], []
    for n in (1, 2, 4, 8):
        mesh = _mesh(n)
        nt = 24*n
        heat_bc = {int(i): 420. for i in mesh.boundary['inner']}
        heat_bc.update({int(i): 300. for i in mesh.boundary['outer']})
        result = solve_steady_thermoelasticity(
            mesh, units={'length': 'm', 'temperature': 'K'}, conductivity=_by_name(K),
            thermal_dirichlet=heat_bc, reference_temperature_k=TREF,
            mechanical_dirichlet=_supports(n), **_material_kw(plane))
        bary, points, weight, layer = _quadrature(result.reference_mesh)
        exact_t = thermal_multilayer.composite_cylinder(points.reshape(-1, 2), inner_radius=R0,
            interfaces=EDGES, conductivities=K, inner_temperature=420., outer_temperature=300.,
            layer=layer).temperature
        th = np.einsum('qi,ti->tq', bary, result.heat.temperature[mesh.triangles])
        t_err.append(np.sqrt(np.sum(weight*(th-exact_t.reshape(th.shape))**2)))
        errors.append(_errors(result.reference_mesh, result.mechanics, reference))
        assert result.manifest['inputs']['materials']['young_modulus_pa'] == dict(sorted(_by_name(E).items()))
        assert nt % 4 == 0
    errors = np.array(errors)
    print(plane, 'coupled T', t_err, _orders(t_err), 'errors (u, stress, szz)', errors.tolist(),
          _orders(errors[:, 0]), _orders(errors[:, 1]), _orders(errors[:, 2]) if plane == 'strain' else '')
    assert np.all(_orders(t_err)[-2:] >= 1.8)
    assert np.all(_orders(errors[:, 0])[-2:] >= 1.8)
    assert np.all(_orders(errors[:, 1])[-2:] >= .9)
    if plane == 'strain':
        assert np.all(_orders(errors[:, 2])[-2:] >= .9)


def test_transient_mechanics_steps_equal_the_static_per_region_solve():
    mesh = layered_rectangle_mesh([.02, .05], .02, [2, 3], 3, ['a', 'b'])
    initial = np.full(len(mesh.nodes), 300.)
    heat = solve_transient_heat(mesh, conductivity=2., volumetric_heat_capacity=4e6,
                                time_s=[0., 5., 10.], initial_temperature_k=initial,
                                dirichlet={int(i): (lambda t: 300.+50*t/10.) for i in mesh.boundary['left']})
    bc = {(int(i), c): 0. for i in mesh.boundary['left'] for c in (0, 1)}
    materials = dict(young_modulus={'a': 200e9, 'b': 70e9}, poisson_ratio={'a': .3, 'b': .33},
                     thermal_expansion_per_k={'a': 1.2e-5, 'b': 2.3e-5}, plane='stress')
    result = solve_transient_thermoelasticity(mesh, heat, units={'length': 'm', 'time': 's', 'temperature': 'K'},
                                              reference_temperature_k=300., mechanical_dirichlet=bc, **materials)
    for step in result.steps:
        direct = solve_thermoelasticity(mesh, step.temperature_snapshot, reference_temperature_k=300.,
                                        dirichlet=bc, **materials)
        np.testing.assert_array_equal(step.mechanics.displacement, direct.displacement)
        np.testing.assert_array_equal(step.mechanics.stress, direct.stress)
    assert np.max(abs(result.steps[-1].mechanics.stress)) > 0


def _two():
    return layered_rectangle_mesh([.5, 1.], 1., [1, 1], 1, ['a', 'b'])


@pytest.mark.parametrize('bad', [dict(thermal_expansion_per_k={'a': 1e-5}),
                                 dict(thermal_expansion_per_k={'a': 1e-5, 'b': np.nan}),
                                 dict(young_modulus={'a': 1e9, 'b': -1.}),
                                 dict(poisson_ratio={'a': .3, 'b': .5}),
                                 dict(thermal_expansion_per_k={'a': 1e-5, 'z': 1e-5}),
                                 dict(thermal_expansion_per_k={'a': 1e-5, 'b': 1e-5}, plane='auto')])
def test_invalid_region_thermoelastic_materials(bad):
    mesh = _two()
    snap = freeze_temperature(mesh, np.full(len(mesh.nodes), 350.))
    bc = {(int(i), c): 0. for i in mesh.boundary['left'] for c in (0, 1)}
    kw = dict(reference_temperature_k=300., thermal_expansion_per_k=1e-5, young_modulus=1e9,
              poisson_ratio=.3, plane='stress', dirichlet=bc)
    kw.update(bad)
    with pytest.raises(ValueError):
        solve_thermoelasticity(mesh, snap, **kw)


@pytest.mark.parametrize('bad', [dict(conductivity={'a': 1.}), dict(conductivity={'a': 1., 'b': 0.}),
                                 dict(young_modulus={'a': 1e9, 'b': 0.}), dict(heat_source={'a': 1., 'q': 1.})])
def test_workflow_rejects_invalid_region_inputs_at_the_input_stage(bad):
    mesh = _two()
    kw = dict(units={'length': 'm', 'temperature': 'K'}, conductivity=1., young_modulus=1e9,
              poisson_ratio=.3, plane='stress', thermal_expansion_per_k=1e-5, reference_temperature_k=300.,
              thermal_dirichlet={int(i): 300. for i in mesh.boundary['left']},
              mechanical_dirichlet={(int(i), c): 0. for i in mesh.boundary['left'] for c in (0, 1)})
    kw.update(bad)
    with pytest.raises(WorkflowStageError) as info:
        solve_steady_thermoelasticity(mesh, **kw)
    assert info.value.stage == 'input'
