# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""DC and Bessel limits, current/power identities and independent MQS assembly."""
import importlib.metadata as metadata

import numpy as np
import pytest
from scipy.constants import mu_0
from scipy.special import iv,kv
from crosscheck import Stopwatch, emit, make_record, observable, require_tool
from galerkin import disk_mesh, rectangle_mesh
from sipi.conductor_diffusion import conductor_impedance

SIGMA = 58e6
F = np.array([0,100,1e4,1e6])
A,B,C = .5e-3,1.5e-3,2e-3


def coax_mesh(nr=16,nt=256,outer=3e-3):
    mesh = disk_mesh([A,B,C,outer],[nr,nr,nr,8],nt)
    return mesh,dict(signals={'inner':np.flatnonzero(mesh.regions == 0)},
                     ground=np.flatnonzero(mesh.regions == 2),conductivity=SIGMA,
                     magnetic_boundary=mesh.boundary['outer'])


def exact_coax(f):
    # Independent cylindrical diffusion solution: solid centre, finite tube.
    # E'=j*omega*mu*H, H(b)=I/(2*pi*b), H(c)=0 in the return conductor.
    f = np.asarray(f)
    k = np.sqrt(2j*np.pi*f*mu_0*SIGMA)
    inner = k/(2*np.pi*A*SIGMA)*iv(0,k*A)/iv(1,k*A)
    outer = k/(2*np.pi*B*SIGMA)*(iv(0,k*B)*kv(1,k*C)+iv(1,k*C)*kv(0,k*B))
    outer /= iv(1,k*C)*kv(1,k*B)-iv(1,k*B)*kv(1,k*C)
    return inner+outer+2j*np.pi*f*(mu_0/(2*np.pi)*np.log(B/A))


@pytest.fixture(scope='module')
def coax_refinement():
    results = []
    for nr in (16,32,64):
        mesh,args = coax_mesh(nr)
        results.append(conductor_impedance(mesh,F,**args))
    return results


def test_coax_dc_and_full_skin_bessel_convergence(coax_refinement):
    exact = exact_coax(F[1:])
    errors = []
    for result in coax_refinement:
        error_r = np.max(abs(result.R[1:,0,0]/exact.real-1))
        error_l = np.max(abs(result.L[1:,0,0]/(exact.imag/(2*np.pi*F[1:]))-1))
        errors.append(max(error_r,error_l))
    assert errors[0] > errors[1] > errors[2]
    assert errors[-1] < .01
    finest = coax_refinement[-1]
    rdc = 1/(SIGMA*np.pi*A*A)+1/(SIGMA*np.pi*(C*C-B*B))
    assert abs(finest.R[0,0,0]/rdc-1) < .001  # Circle-to-polygon geometry error.
    np.testing.assert_allclose(finest.L[0],finest.L[1],rtol=.01)
    assert finest.R[-1,0,0] > finest.R[0,0,0]
    assert finest.L[-1,0,0] < finest.L[0,0,0]
    assert np.max(abs(finest.Z[1:,0,0]/exact-1)) < .01


def test_coax_conservation_and_outer_domain(coax_refinement):
    result = coax_refinement[-1]
    assert np.max(result.current_error) < 1e-10
    assert np.max(result.power_error) < 1e-9
    assert np.max(result.magnetic_energy_error) < 1e-9
    assert np.max(result.max_edge_over_skin_depth) <= 1
    assert np.isinf(result.skin_depth[0])
    assert not result.Z.flags.writeable and not result.L.flags.writeable
    mesh,args = coax_mesh(16,outer=6e-3)
    enlarged = conductor_impedance(mesh,F,**args)
    # A coaxial return confines its magnetic field; outer-region changes vanish.
    np.testing.assert_allclose(enlarged.Z,coax_refinement[0].Z,rtol=1e-9,atol=0)


def rectangular_groups():
    mesh = rectangle_mesh(6e-3,4e-3,60,40)
    centres = mesh.nodes[mesh.triangles].mean(axis=1)
    x,y = centres.T
    signal1 = np.flatnonzero((x>1e-3)&(x<2e-3)&(y>2e-3)&(y<2.5e-3))
    signal2 = np.flatnonzero((x>4e-3)&(x<5e-3)&(y>2e-3)&(y<2.5e-3))
    ground = np.flatnonzero((x>1e-3)&(x<5e-3)&(y>.5e-3)&(y<1e-3))
    boundary = np.unique(np.concatenate(list(mesh.boundary.values())))
    return mesh,dict(signals={'left':signal1,'right':signal2},ground=ground,
                    conductivity=SIGMA,magnetic_boundary=boundary)


def test_dc_rectangles_exact_resistance_and_ac_proximity_fields():
    mesh,args = rectangular_groups()
    f = [0,1e3,1e5]
    result = conductor_impedance(mesh,f,**args,keep_fields=True)
    signal_r,ground_r = 1/(SIGMA*.5e-6),1/(SIGMA*2e-6)
    exact = np.diag([signal_r,signal_r])+ground_r*np.ones((2,2))
    np.testing.assert_allclose(result.R[0],exact,rtol=1e-10,atol=0)
    np.testing.assert_allclose(result.Z,result.Z.swapaxes(1,2),rtol=1e-10,atol=0)
    for matrix in (result.R,result.L):
        scale = np.max(abs(matrix),axis=(1,2))
        assert np.all(np.linalg.eigvalsh(matrix)[:,0] >= -1e-10*scale)
    target = np.vstack((np.eye(2),-np.ones((1,2))))
    np.testing.assert_allclose(result.current_integrals,np.broadcast_to(target,(3,3,2)),atol=1e-10)
    signal = args['signals']['left']
    np.testing.assert_allclose(result.current_density[0,signal,0],1/.5e-6,rtol=1e-10)
    assert np.ptp(abs(result.current_density[-1,signal,0])) > .1*(1/.5e-6)
    assert result.R[-1,0,0] > result.R[0,0,0]
    np.testing.assert_array_equal(result.vector_potential[:,args['magnetic_boundary']],0)
    # This supplied C/G exercises propagation; it is not a dielectric extraction.
    c = np.array([[100,-10],[-10,100]])*1e-12
    net = result.network(C=c,G=np.zeros((2,2)),length=.02)
    np.testing.assert_allclose(net.s,net.s.swapaxes(1,2),atol=1e-10)
    assert np.max(np.linalg.svd(net.s,compute_uv=False)) <= 1+1e-10


def test_independent_skfem_augmented_current_constraint_system():
    skfem = require_tool('scikit-fem')
    from skfem.helpers import dot,grad
    from scipy.sparse import bmat,csc_matrix
    from scipy.sparse.linalg import spsolve
    mesh,args = coax_mesh(4,32)
    frequency = 1e4
    omega = 2*np.pi*frequency
    clock = Stopwatch()
    with clock('openphysics'):
        result = conductor_impedance(mesh,[frequency],**args)
    with clock('reference'):
        basis = skfem.Basis(skfem.MeshTri(mesh.nodes.T,mesh.triangles.T),skfem.ElementTriP1())
        @skfem.BilinearForm
        def stiffness(u,v,w):
            return dot(grad(u),grad(v))/mu_0
        @skfem.BilinearForm
        def mass(u,v,w):
            return w.sigma*u*v
        @skfem.LinearForm
        def load(v,w):
            return w.sigma*v
        coefficients = np.where((mesh.regions == 0)|(mesh.regions == 2),SIGMA,0.)
        k = skfem.asm(stiffness,basis)
        m = skfem.asm(mass,basis,sigma=coefficients[:,None])
        q = np.column_stack([skfem.asm(load,basis,sigma=np.where(mesh.regions == group,SIGMA,0.)[:,None])
                             for group in (0,2)])
        d = np.diag(q.sum(axis=0))
        free = np.setdiff1d(np.arange(basis.N),args['magnetic_boundary'])
        q = q[free]
        operator = bmat([[k[free][:,free]+1j*omega*m[free][:,free],csc_matrix(-q)],
                         [csc_matrix(-1j*omega*q.T),csc_matrix(d)]],format='csc')
        solved = spsolve(operator,np.r_[np.zeros(len(free)),1.,-1.])
        reference = solved[-2]-solved[-1]
    error = float(abs(result.Z[0,0,0]/reference-1))
    record = make_record(case='sipi-conductor-diffusion',physics='longitudinal magnetoquasistatic diffusion',
        api='sipi.conductor_diffusion.conductor_impedance',discretization='P1 volume fields and current Schur system',
        tool='scikit-fem',tool_discretization='independent P1 forms and augmented current-constraint solve',
        matched=['same mesh, scalar conductivity and permeability, 10 kHz',
                 'solid inner conductor, finite return tube, Az=0 outer nodes',
                 'unit inner current, negative unit return, exp(+j omega t)'],
        not_matched=['same-mesh agreement does not establish mesh or domain convergence'],
        observables=[observable('series impedance','ohm/m','relative difference',error,1e-9)],
        analytical_acceptance='tests/sipi/test_conductor_diffusion.py: DC rectangles and independent coax Bessel convergence',
        stopwatch=clock)
    record['openphysics']['distribution'] = 'sipi'
    record['openphysics']['version'] = metadata.version('sipi')
    emit(record)
    assert error < 1e-9


@pytest.mark.parametrize('change', [dict(frequency=[-1]),dict(frequency=[1,1]),
    dict(frequency=[True]),dict(conductivity=0),dict(conductivity=True),
    dict(relative_permeability=-1),dict(keep_fields='yes'),dict(frequency=[1e20])])
def test_invalid_material_and_frequency_inputs_fail_before_assembly(monkeypatch,change):
    import sipi.conductor_diffusion as implementation
    mesh,args = coax_mesh(4,32)
    def forbidden(*a,**k):
        pytest.fail('invalid input reached assembly')
    monkeypatch.setattr(implementation,'assemble_load',forbidden)
    args.update(frequency=[0]);args.update(change)
    with pytest.raises(ValueError):
        conductor_impedance(mesh,**args)


@pytest.mark.parametrize('what', ['overlap','touch','float','bool','duplicate','empty','outside','boundary'])
def test_invalid_region_and_boundary_indices(what):
    mesh,args = coax_mesh(4,32)
    if what == 'overlap':
        args['ground'] = args['signals']['inner']
    elif what == 'touch':
        args['ground'] = np.flatnonzero(mesh.regions == 1)
    elif what == 'float':
        args['signals']['inner'] = [0.5,1.5]
    elif what == 'bool':
        args['signals']['inner'] = [True,2]
    elif what == 'duplicate':
        args['signals']['inner'] = [0,0]
    elif what == 'empty':
        args['ground'] = []
    elif what == 'outside':
        args['ground'] = [mesh.num_triangles]
    elif what == 'boundary':
        args['magnetic_boundary'] = [0]
    with pytest.raises(ValueError):
        conductor_impedance(mesh,[0],**args)


def test_skin_unresolved_mesh_is_rejected_before_assembly(monkeypatch):
    import sipi.conductor_diffusion as implementation
    mesh,args = coax_mesh(4,32)
    def forbidden(*a,**k):
        pytest.fail('under-resolved metal mesh reached assembly')
    monkeypatch.setattr(implementation,'assemble_load',forbidden)
    with pytest.raises(ValueError,match='skin depth'):
        conductor_impedance(mesh,[1e6],**args)
