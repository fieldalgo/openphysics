# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Installed prescribed-temperature mechanical-stage consumers, not convergence gates."""
from pathlib import Path
import subprocess
import sys

import numpy as np
import pytest

import galerkin.thermoelasticity as engine
import refsol.thermoelasticity as reference
from galerkin.mesh import Mesh, rectangle_mesh

E, NU, ALPHA, THETA, TREF = 70e9, .3, 12e-6, 20., 293.15


def material(plane, **changes):
    return dict(young_modulus=E, poisson_ratio=NU, plane=plane,
                thermal_expansion_per_k=ALPHA, reference_temperature_k=TREF) | changes


def close(actual, expected, scale, rtol=1e-10, atol=1e-12):
    assert np.isfinite(scale) and scale > 0
    np.testing.assert_allclose(np.asarray(actual)/scale, np.asarray(expected)/scale,
                               rtol=rtol, atol=atol)


def original_3d(ex, ey, gamma, a, plane):
    """Direct isotropic 3D law with total sigma_zz=0 or epsilon_zz=0."""
    mu = E/(2*(1+NU))
    lam = E*NU/((1+NU)*(1-2*NU))
    ez = ((1+NU)*a-NU*(ex+ey))/(1-NU) if plane == 'stress' else 0.
    elastic = np.array([[ex-a, gamma/2, 0.], [gamma/2, ey-a, 0.], [0., 0., ez-a]])
    stress = 2*mu*elastic+lam*np.trace(elastic)*np.eye(3)
    energy = .5*np.sum(elastic*stress)
    return stress, ez, energy


def supports(n=4):
    return {(0, 0): 0., (0, 1): 0., (n, 1): 0.}


def solve(mesh, temp, plane, bc=None, **changes):
    return engine.solve_thermoelasticity(mesh, engine.freeze_temperature(mesh, temp),
        dirichlet=supports() if bc is None else bc, **material(plane, **changes))


def test_thermoelastic_modules_are_installed():
    for module in (engine, reference):
        assert Path(module.__file__).resolve().is_relative_to(Path(sys.prefix).resolve())


@pytest.mark.parametrize('plane', ['stress', 'strain'])
@pytest.mark.parametrize('theta,alpha', [(20., ALPHA), (-20., ALPHA), (20., -ALPHA)])
def test_free_uniform_original_3d_law(plane, theta, alpha):
    mesh = rectangle_mesh(1., 1., 4, 4)
    a = alpha*theta
    factor = 1. if plane == 'stress' else 1+NU
    expected_stress, ez, energy = original_3d(factor*a, factor*a, 0., a, plane)
    r = solve(mesh, np.full(mesh.num_nodes, TREF+theta), plane,
              thermal_expansion_per_k=alpha)
    close(r.displacement, factor*a*mesh.nodes, abs(a))
    close(r.total_strain, np.broadcast_to([factor*a, factor*a, 0.], r.total_strain.shape), abs(a))
    close(r.thermal_strain, np.broadcast_to([a, a, 0.], r.thermal_strain.shape), abs(a))
    close(r.elastic_strain, r.total_strain-r.thermal_strain, abs(a))
    close(r.stress, np.broadcast_to([expected_stress[0, 0], expected_stress[1, 1], 0.], r.stress.shape), E*abs(a))
    close(r.sigma_zz, expected_stress[2, 2], E*abs(a))
    close(r.epsilon_zz, ez, abs(a))
    # Normalize zero energy by the nonzero thermal eigenstrain energy scale,
    # never by absolute Kelvin temperature or by the computed answer.
    close(r.physical_elastic_energy, energy, E*a*a)
    close(r.reaction, 0., E*abs(a))
    close(r.load_external, 0., E*abs(a))
    close(r.load_thermal.sum(axis=0), 0., E*abs(a))
    ref = reference.uniform_free(mesh.nodes, theta, **material(plane, thermal_expansion_per_k=alpha))
    close(ref.displacement, factor*a*mesh.nodes, abs(a))
    close(ref.sigma_zz, expected_stress[2, 2], E*abs(a))
    close(ref.energy_density, energy, E*a*a)
    if theta == 20. and alpha == ALPHA:
        close(energy, 0. if plane == 'stress' else 2016., E*a*a)
        close(expected_stress[2, 2], 0. if plane == 'stress' else -16.8e6, E*a)


@pytest.mark.parametrize('plane', ['stress', 'strain'])
def test_constrained_uniform_reactions_and_physical_energy(plane):
    mesh = rectangle_mesh(1., 1., 4, 4)
    boundary = np.unique(np.concatenate(list(mesh.boundary.values())))
    bc = {(int(i), c): 0. for i in boundary for c in (0, 1)}
    r = solve(mesh, np.full(mesh.num_nodes, TREF+THETA), plane, bc)
    a = ALPHA*THETA
    stress, ez, energy = original_3d(0., 0., 0., a, plane)
    close(r.displacement, 0., a)
    close(r.stress, np.broadcast_to([stress[0, 0], stress[1, 1], 0.], r.stress.shape), E*a)
    close(r.sigma_zz, stress[2, 2], E*a)
    close(r.epsilon_zz, ez, a)
    close(r.physical_elastic_energy, energy, E*a*a)
    expected = np.zeros_like(mesh.nodes)
    for axis, side, normal in ((0, 0., (-1., 0.)), (0, 1., (1., 0.)),
                               (1, 0., (0., -1.)), (1, 1., (0., 1.))):
        nodes = np.flatnonzero(mesh.nodes[:, axis] == side)
        ordered = nodes[np.argsort(mesh.nodes[nodes, 1-axis])]
        traction = stress[:2, :2] @ normal
        for i, j in zip(ordered[:-1], ordered[1:]):
            force = traction*np.linalg.norm(mesh.nodes[j]-mesh.nodes[i])/2
            expected[i] += force
            expected[j] += force
    close(r.reaction, expected, E*a)
    close((r.reaction+r.load_external).sum(axis=0), 0., E*a)
    close(np.sum(mesh.nodes[:, 0]*r.reaction[:, 1]-mesh.nodes[:, 1]*r.reaction[:, 0]), 0., E*a)
    ref = reference.uniform_constrained(mesh.nodes, **material(plane))
    close(ref.energy_density, energy, E*a*a)


@pytest.mark.parametrize('plane', ['stress', 'strain'])
def test_temperature_reference_shift(plane):
    mesh = rectangle_mesh(1., 1., 4, 4)
    temp = TREF+THETA+3*mesh.nodes[:, 0]
    first = solve(mesh, temp, plane)
    shifted = solve(mesh, temp+1000., plane, reference_temperature_k=TREF+1000.)
    for field in ('displacement', 'stress', 'sigma_zz', 'reaction', 'load_thermal'):
        scale = ALPHA*THETA if field == 'displacement' else E*ALPHA*THETA
        close(getattr(shifted, field), getattr(first, field), scale)
    close(shifted.physical_elastic_energy, first.physical_elastic_energy, E*(ALPHA*THETA)**2)


@pytest.mark.parametrize('plane', ['stress', 'strain'])
def test_zero_alpha_mechanical_load_and_energy(plane):
    mesh = rectangle_mesh(1., 1., 4, 4)
    # Prescribed affine displacement fixes an independent nonzero mechanical
    # strain/energy scale even though alpha is zero.
    strain = np.array([1e-4, -2e-5, 0.])
    bc = {(int(i), c): strain[c]*mesh.nodes[i, c]
          for i in np.unique(np.concatenate(list(mesh.boundary.values()))) for c in (0, 1)}
    r = solve(mesh, np.linspace(0., 1000., mesh.num_nodes), plane, bc,
              thermal_expansion_per_k=0.)
    stress, ez, energy = original_3d(*strain, 0., plane)
    close(r.displacement, mesh.nodes*strain[:2], 1e-4)
    close(r.stress, np.broadcast_to([stress[0, 0], stress[1, 1], 0.], r.stress.shape), E*1e-4)
    close(r.physical_elastic_energy, energy, E*1e-8)
    assert np.all(r.load_thermal == 0.)
    close(np.sum(r.displacement*r.reaction), 2*energy, E*1e-8)


def test_snapshot_copied_mesh_and_immutable_kelvin_data():
    mesh = rectangle_mesh(1., 1., 4, 4)
    temp = np.full(mesh.num_nodes, TREF+THETA)
    snapshot = engine.freeze_temperature(mesh, temp)
    copied = Mesh(mesh.nodes.copy(), mesh.triangles.copy(), {k: v.copy() for k, v in mesh.boundary.items()})
    temp[:] = 0.
    assert np.all(snapshot.temperature_k == TREF+THETA)
    for array in (snapshot.nodes, snapshot.triangles, snapshot.temperature_k):
        with pytest.raises(ValueError):
            array.flags.writeable = True
    r = engine.solve_thermoelasticity(copied, snapshot, dirichlet=supports(), **material('strain'))
    close(r.displacement, (1+NU)*ALPHA*THETA*mesh.nodes, ALPHA*THETA)


@pytest.mark.parametrize('mutation', ['coordinates', 'scale', 'order', 'unit', 'length_unit', 'schema'])
def test_stale_snapshot_or_unit_metadata_rejected(mutation):
    mesh = rectangle_mesh(1., 1., 4, 4)
    snapshot = engine.freeze_temperature(mesh, np.full(mesh.num_nodes, TREF+THETA))
    if mutation == 'coordinates':
        mesh.nodes[1, 0] += .01
    elif mutation == 'scale':
        mesh.nodes *= .001
    elif mutation == 'order':
        mesh.nodes[[0, 1]] = mesh.nodes[[1, 0]]
    else:
        name, value = {'unit': ('temperature_unit', 'C'), 'length_unit': ('length_unit', 'mm'),
                       'schema': ('schema_version', 2)}[mutation]
        object.__setattr__(snapshot, name, value)
    with pytest.raises(ValueError):
        engine.solve_thermoelasticity(mesh, snapshot, dirichlet=supports(), **material('stress'))


@pytest.mark.parametrize('bad', ['negative', 'nan', 'complex', 'scalar', 'column'])
def test_invalid_absolute_kelvin_input(bad):
    mesh = rectangle_mesh(1., 1., 4, 4)
    values = {'negative': np.full(mesh.num_nodes, -1.), 'nan': np.full(mesh.num_nodes, np.nan),
              'complex': np.full(mesh.num_nodes, 300.+1j), 'scalar': 300.,
              'column': np.full((mesh.num_nodes, 1), 300.)}
    with pytest.raises(ValueError):
        engine.freeze_temperature(mesh, values[bad])


@pytest.mark.parametrize('bad', [-1., np.nan, np.inf])
def test_invalid_reference_kelvin_rejected(bad):
    mesh = rectangle_mesh(1., 1., 4, 4)
    with pytest.raises(ValueError):
        solve(mesh, np.full(mesh.num_nodes, 300.), 'stress', reference_temperature_k=bad)


def test_unconstrained_rigid_mode_rejected():
    mesh = rectangle_mesh(1., 1., 4, 4)
    with pytest.raises(ValueError):
        solve(mesh, np.full(mesh.num_nodes, TREF+THETA), 'stress', {})


def test_actual_english_example():
    example = Path(__file__).resolve().parents[1]/'examples/prescribed_temperature_thermoelasticity.py'
    completed = subprocess.run([sys.executable, '-I', str(example)], cwd=example.parent,
                               text=True, capture_output=True, check=True)
    assert 'Prescribed P1 temperature mechanical stage; no heat solve' in completed.stdout
    energy = float(completed.stdout.split('physical elastic energy [J/m]:')[1].splitlines()[0])
    zz = float(completed.stdout.split('centroid sigma_zz [Pa]:')[1].splitlines()[0])
    close(energy, 2016., E*(ALPHA*THETA)**2)
    close(zz, -16.8e6, E*ALPHA*THETA)
