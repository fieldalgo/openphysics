# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Surface-current loss: independent limits, convergence and validity gates."""
import importlib.metadata as metadata

import numpy as np
import pytest
from scipy.constants import mu_0
from crosscheck import Stopwatch, emit, make_record, observable, require_tool
from galerkin import annulus_mesh, rectangle_mesh
from sipi import CrossSection, coupled_microstrip, microstrip
from sipi.conductor import surface_impedance, surface_current_factors, surface_conductor_loss

SIGMA = 58e6
F = np.array([1e9, 4e9, 10e9])


def test_parallel_plate_exact_current_return_and_loss():
    width, height = .002, .001
    mesh = rectangle_mesh(width, height, 8, 4)
    result = surface_current_factors(mesh, {'signal':mesh.boundary['top']}, mesh.boundary['bottom'])
    np.testing.assert_allclose(result.parts[:,0,0], [1/width, 1/width], rtol=1e-10)
    np.testing.assert_allclose(result.current_integrals, [[1],[-1]], atol=1e-10, rtol=0)
    np.testing.assert_allclose(result.L_external, [[mu_0*height/width]], rtol=1e-10)
    assert result.current_error < 1e-10
    assert not result.parts.flags.writeable
    with pytest.raises(ValueError):
        result.parts[0,0,0] = 0


def test_coax_surface_integral_refines_toward_exact_signal_plus_return():
    a, b = .5e-3, 2e-3
    exact = (1/a+1/b)/(2*np.pi)
    errors = []
    for nr in (64,128,256):
        mesh = annulus_mesh(a,b,nr,256)
        result = surface_current_factors(mesh, {'inner':mesh.boundary['inner']}, mesh.boundary['outer'])
        errors.append(abs(result.total[0,0]/exact-1))
    assert errors[0] > errors[1] > errors[2]
    assert errors[-1] < .01
    assert result.current_error < .01
    # Check each metal, not just a possibly compensating total error.
    np.testing.assert_allclose(result.parts[:,0,0], [1/(2*np.pi*a),1/(2*np.pi*b)], rtol=.015)


def test_surface_law_scales_and_roughness_changes_only_resistance():
    smooth = surface_impedance(F, conductivity=SIGMA)
    expected = (1+1j)*np.sqrt(np.pi*F*mu_0/SIGMA)
    np.testing.assert_allclose(smooth, expected, rtol=1e-12)
    np.testing.assert_allclose(surface_impedance(F,conductivity=4*SIGMA), smooth/2, rtol=1e-12)
    np.testing.assert_allclose(surface_impedance(F,conductivity=SIGMA,relative_permeability=4), smooth*2, rtol=1e-12)
    delta = 1/np.sqrt(np.pi*F*mu_0*SIGMA)
    rough = surface_impedance(F,conductivity=SIGMA,roughness_rms=1e-6)
    np.testing.assert_allclose(rough.real/smooth.real, 1+2/np.pi*np.arctan(1.4*(1e-6/delta)**2), rtol=1e-12)
    np.testing.assert_array_equal(rough.imag, smooth.imag)
    assert np.all(rough.real > smooth.real)
    assert np.all(rough.real < 2*smooth.real)
    saturated = surface_impedance(F,conductivity=SIGMA,roughness_rms=1e300)
    np.testing.assert_allclose(saturated.real, 2*smooth.real, rtol=1e-12)


def test_surface_law_against_independent_scikit_rf():
    skrf = require_tool('scikit-rf')
    f = np.logspace(3,11,9)
    clock = Stopwatch()
    with clock('openphysics'):
        ours = surface_impedance(f,conductivity=SIGMA)
        depth = 1/(SIGMA*ours.real)
    with clock('reference'):
        resistance = skrf.tlineFunctions.surface_resistivity(f,1/SIGMA,1)
        skin = skrf.tlineFunctions.skin_depth(f,1/SIGMA,1)
    errors = [np.max(abs(ours.real/resistance-1)),np.max(abs(depth/skin-1))]
    record = make_record(case='sipi-surface-impedance',physics='good-conductor half-space',
        api='sipi.conductor.surface_impedance',discretization='analytic surface impedance',
        tool='scikit-rf',tool_discretization='surface_resistivity and skin_depth',
        matched=['frequencies in Hz, conductivity 58 MS/m, relative permeability 1',
                 'smooth half-space, exp(+j omega t)'],
        not_matched=['no PCB geometry, roughness or current-distribution reference'],
        observables=[observable(name,unit,'max relative difference',value,1e-12)
            for name,unit,value in zip(('surface resistance','skin depth'),('ohm','m'),errors)],
        analytical_acceptance='tests/sipi/test_conductor.py: plate and coax independent geometry limits',
        stopwatch=clock)
    record['openphysics']['distribution'] = 'sipi'
    record['openphysics']['version'] = metadata.version('sipi')
    emit(record)
    assert max(errors) < 1e-12


@pytest.fixture(scope='module')
def coupled_results():
    section = coupled_microstrip(width=.5e-3,gap=.3e-3,substrate_height=1e-3,
                                 thickness=.05e-3,eps_r=4)
    opts = dict(conductivity=SIGMA,ground_thickness=35e-6)
    coarse = surface_conductor_loss(section,F,**opts,edge_size=5e-6,far_size=.2e-3,grade=.1)
    fine = surface_conductor_loss(section,F,**opts,edge_size=2.5e-6,far_size=.1e-3,grade=.05)
    return section, coarse, fine


def test_coupled_resistance_refinement_and_return_currents(coupled_results):
    _, coarse, fine = coupled_results
    assert np.max(abs(fine.R-coarse.R))/np.max(abs(fine.R)) < .05
    assert fine.factors.current_error < coarse.factors.current_error < .05
    # Return-plane dissipation must not disappear from differential/coupled cases.
    assert np.all(np.diag(fine.factors.parts[-1]) > 0)
    assert abs(fine.R[0,0,1]) > .01
    np.testing.assert_allclose(fine.R[1]/fine.R[0], 2, rtol=1e-12)
    np.testing.assert_allclose(fine.L_internal[1]/fine.L_internal[0], .5, rtol=1e-12)
    for matrix in (fine.R, fine.L_internal):
        np.testing.assert_allclose(matrix,matrix.swapaxes(1,2),atol=1e-10)
        assert np.min(np.linalg.eigvalsh(matrix)) >= -1e-10


def test_coupled_loss_network_is_reciprocal_passive_and_preserves_inputs(coupled_results):
    section, _, loss = coupled_results
    dielectric = section.analyze(edge_size=2.5e-6,far_size=.1e-3,grade=.05)
    np.testing.assert_allclose(loss.factors.C0,dielectric.C0,rtol=1e-10,atol=0)
    net = loss.network(C=dielectric.C,G=[[0,0],[0,0]],length=.03)
    np.testing.assert_allclose(net.s,net.s.swapaxes(1,2),atol=1e-10)
    assert np.max(np.linalg.svd(net.s,compute_uv=False)) <= 1+1e-10
    assert not loss.R.flags.writeable
    np.testing.assert_array_equal(loss.frequency,F)


def test_underresolved_flux_is_rejected():
    section = coupled_microstrip(width=.5e-3,gap=.3e-3,substrate_height=1e-3,
                                 thickness=.05e-3,eps_r=4)
    with pytest.raises(ValueError,match='flux error'):
        surface_conductor_loss(section,F,conductivity=SIGMA,ground_thickness=35e-6,
                               edge_size=10e-6,far_size=.4e-3,grade=.2)


@pytest.mark.parametrize('changes', [dict(frequency=[0]),dict(frequency=[1e3]),
    dict(ground_thickness=1e-9),dict(conductivity=0),dict(conductivity=True),
    dict(relative_permeability=-1),dict(roughness_rms=-1),dict(frequency=[1e300]),
    dict(frequency=[2e9,1e9]),dict(frequency=[1e9,1e9]),dict(ground_thickness=float('nan'))])
def test_invalid_and_low_frequency_inputs_rejected_before_meshing(monkeypatch,changes):
    section = microstrip(width=.5e-3,substrate_height=1e-3,eps_r=4,thickness=35e-6)
    def forbidden(*args,**kwargs):
        pytest.fail('invalid surface-loss input reached meshing')
    monkeypatch.setattr(CrossSection,'mesh',forbidden)
    args = dict(frequency=F,conductivity=SIGMA,ground_thickness=35e-6)
    args.update(changes)
    with pytest.raises(ValueError):
        surface_conductor_loss(section,**args)


def test_zero_thickness_conductor_rejected():
    section = microstrip(width=.5e-3,substrate_height=1e-3,eps_r=4)
    with pytest.raises(ValueError,match='finite conductors'):
        surface_conductor_loss(section,F,conductivity=SIGMA,ground_thickness=35e-6)
    mesh = rectangle_mesh(1,1,8,8)
    signal = np.flatnonzero((mesh.nodes[:,1] == .5) & (mesh.nodes[:,0] > .25)
                            & (mesh.nodes[:,0] < .75))
    with pytest.raises(ValueError,match='zero-thickness'):
        surface_current_factors(mesh,{'signal':signal},mesh.boundary['bottom'])


def test_overlapping_conductor_boundaries_rejected():
    mesh = rectangle_mesh(1,1,8,8)
    with pytest.raises(ValueError,match='overlap'):
        surface_current_factors(mesh,{'signal':mesh.boundary['bottom']},mesh.boundary['bottom'])
