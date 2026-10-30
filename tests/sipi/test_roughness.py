# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Causal surface law, independent spectral integral and line input contract."""
from dataclasses import FrozenInstanceError

import numpy as np
import pytest
from scipy.constants import mu_0
from scipy.integrate import quad

from galerkin import annulus_mesh
from sipi import CrossSection, CrossSectionDocument, coupled_microstrip
from sipi.conductor import surface_impedance, surface_current_factors, surface_conductor_loss
from sipi.line_model import TransmissionLineDocument
from sipi.roughness import CausalHuray

SIGMA = 58e6
F = np.array([1e9,4e9,10e9])
MODEL = CausalHuray([.5e-6,1.5e-6],[1.2,.3])
MESH = dict(edge_size=5e-6,far_size=.2e-3,grade=.1)


def geometry():
    return CrossSectionDocument(coupled_microstrip(width=.5e-3,gap=.3e-3,
        substrate_height=1e-3,thickness=50e-6,eps_r=4),mesh=MESH)


def line(roughness=None, **changes):
    metal = dict(kind='surface',conductivity=SIGMA,ground_thickness=35e-6,
                 relative_permeability=1,roughness=roughness or dict(kind='causal-huray',
                     radii_m=list(MODEL.radii_m),surface_ratios=list(MODEL.surface_ratios)))
    args = dict(cross_section=geometry(),frequency=F,materials={},conductor=metal,
                length=.03,schema='sipi.transmission-line/2')
    args.update(changes)
    return TransmissionLineDocument(**args)


@pytest.mark.parametrize('omega_tau',np.logspace(-6,6,7))
def test_causal_factor_against_independent_positive_relaxation_integral(omega_tau):
    # Spectral representation of q/(1+q): integrate stable first-order
    # responses with positive weights, not another evaluation of sqrt(s).
    z = 1j*omega_tau
    def integrand(theta):
        return (2/np.pi)*z/(z+np.tan(theta)**2)
    reference = quad(lambda t: integrand(t).real,0,np.pi/2,epsabs=1e-12,epsrel=1e-12)[0]
    reference += 1j*quad(lambda t: integrand(t).imag,0,np.pi/2,epsabs=1e-12,epsrel=1e-12)[0]
    radius,ratio = .7e-6,2.4
    delta = radius*np.sqrt(2/omega_tau)
    actual = CausalHuray([radius],[ratio]).factor([delta])[0]
    np.testing.assert_allclose(actual,1+1.5*ratio*reference,rtol=1e-10,atol=1e-10)


def test_huray_real_loss_identity_and_complex_constitutive_law():
    f = np.logspace(2,11,37)
    delta = 1/np.sqrt(np.pi*f*mu_0*SIGMA)
    smooth = surface_impedance(f,conductivity=SIGMA)
    rough = surface_impedance(f,conductivity=SIGMA,roughness=MODEL)
    ratio = np.ones(f.size)
    for radius,area in zip(MODEL.radii_m,MODEL.surface_ratios):
        ratio += 1.5*area/(1+delta/radius+.5*(delta/radius)**2)
    np.testing.assert_allclose(rough.real/smooth.real,ratio,rtol=1e-12,atol=0)
    np.testing.assert_allclose(rough/smooth,MODEL.factor(delta),rtol=1e-12,atol=0)
    assert np.all(rough.imag > smooth.imag)
    assert np.all(rough.real > smooth.real)
    # A loss-only correction or multiplying smooth Z by the real loss ratio
    # cannot reproduce this distinct reactance.
    assert np.max(abs(rough.imag/rough.real-1)) > .1


def test_zero_area_limits_and_extreme_finite_scale_are_stable():
    zero = CausalHuray([1e-300,1e300],[0,0])
    np.testing.assert_array_equal(zero.factor([1e-300,1,1e300]),np.ones(3,dtype=complex))
    np.testing.assert_array_equal(surface_impedance(F,conductivity=SIGMA,roughness=zero),
                                  surface_impedance(F,conductivity=SIGMA))
    model = CausalHuray([1],[2])
    factor = model.factor([1e300,1e-300])
    np.testing.assert_allclose(factor,[1,4],rtol=1e-12,atol=1e-12)
    # Independent low-frequency extra inductance per square -> sum K*mu*a.
    f = np.array([1e-10,1e-8])
    dz = surface_impedance(f,conductivity=SIGMA,roughness=MODEL)-surface_impedance(f,conductivity=SIGMA)
    expected = sum(1.5*r*mu_0*a for a,r in zip(MODEL.radii_m,MODEL.surface_ratios))
    np.testing.assert_allclose(dz.imag/(2*np.pi*f),expected,rtol=1e-5)
    # Avoid cancellation of Re(H)-Im(H) for large, near-equal terms.
    enormous = CausalHuray([1e-20],[1e200])
    r,x = enormous._impedance_factors([1])
    np.testing.assert_allclose(r,[3e160],rtol=1e-12)
    np.testing.assert_allclose(x,[3e180],rtol=1e-12)
    assert np.all(np.isfinite(enormous.factor([1])))
    largest = CausalHuray([1],[1e308])
    np.testing.assert_allclose(largest.factor([1e-300]).real,[1.5e308],rtol=1e-12)


def test_permeability_conductivity_and_radius_dimensional_scaling():
    base = surface_impedance(F,conductivity=SIGMA,roughness=MODEL)
    scaled = CausalHuray(np.array(MODEL.radii_m)/2,MODEL.surface_ratios)
    np.testing.assert_allclose(surface_impedance(F,conductivity=4*SIGMA,roughness=scaled),
                                base/2,rtol=1e-12)
    np.testing.assert_allclose(surface_impedance(F,conductivity=SIGMA,
        relative_permeability=4,roughness=scaled),base*2,rtol=1e-12)


@pytest.mark.parametrize('radii,ratios',[
    ([],[]),([0],[1]),([-1],[1]),([1],[-1]),([True],[1]),([1],[True]),
    ([None],[1]),([1],[None]),([float('inf')],[1]),([1],[float('nan')]),
    ([1],[1.3e308]),([1,2],[1]),([[1]],[[1]]),('1',[1]),([1],'1'),
    ([1]*65,[1]*65),([1,2],[1e308,1e308]),
])
def test_invalid_populations(radii,ratios):
    with pytest.raises(ValueError):
        CausalHuray(radii,ratios)


@pytest.mark.parametrize('delta',[[],[0],[-1],[True],[None],[float('inf')],[[1]],'1'])
def test_invalid_depth(delta):
    with pytest.raises(ValueError):
        MODEL.factor(delta)


def test_models_are_snapshots_and_cannot_mix_corrections():
    a,r = [1e-6],[2]
    model = CausalHuray(a,r)
    a[0],r[0] = 9,9
    assert model.radii_m == (1e-6,) and model.surface_ratios == (2,)
    with pytest.raises(FrozenInstanceError):
        model.radii_m = (2,)
    with pytest.raises(ValueError,match='either'):
        surface_impedance(F,conductivity=SIGMA,roughness=MODEL,roughness_rms=1e-6)
    with pytest.raises(TypeError,match='CausalHuray'):
        surface_impedance(F,conductivity=SIGMA,roughness={})
    with pytest.raises(ValueError,match='represented'):
        surface_impedance(F,conductivity=SIGMA,relative_permeability=1e200,
                           roughness=CausalHuray([1],[1e308]))


def test_coax_rough_r_and_internal_l_converge_to_analytic_geometry():
    a,b = .5e-3,2e-3
    zs = surface_impedance(F,conductivity=SIGMA,roughness=MODEL)
    exact_geometry = (1/a+1/b)/(2*np.pi)
    exact_r = zs.real*exact_geometry
    exact_l = zs.imag/(2*np.pi*F)*exact_geometry
    errors_r,errors_l = [],[]
    for nr in (64,128,256):
        mesh = annulus_mesh(a,b,nr,256)
        factors = surface_current_factors(mesh,{'inner':mesh.boundary['inner']},mesh.boundary['outer'])
        errors_r.append(np.max(abs(zs.real*factors.total[0,0]/exact_r-1)))
        errors_l.append(np.max(abs(zs.imag/(2*np.pi*F)*factors.total[0,0]/exact_l-1)))
    for errors in (errors_r,errors_l):
        assert errors[0] > errors[1] > errors[2]
        assert errors[-1] < .01


@pytest.fixture(scope='module')
def solved():
    doc = line()
    return doc,doc.analyze()


def test_line_roundtrip_shared_mesh_and_independent_surface_api(solved,monkeypatch):
    doc,result = solved
    calls = []
    original = CrossSection.mesh
    def counted(self,**kwargs):
        calls.append(kwargs)
        return original(self,**kwargs)
    monkeypatch.setattr(CrossSection,'mesh',counted)
    restored = TransmissionLineDocument.loads(doc.dumps())
    rerun = restored.analyze()
    assert len(calls) == 1
    assert restored.dumps() == doc.dumps() == result.input_json
    for name in ('R','L','G','C'):
        np.testing.assert_allclose(getattr(result,name),getattr(rerun,name),rtol=1e-12,atol=0)
    np.testing.assert_allclose(result.network.s,rerun.network.s,rtol=0,atol=1e-10)
    direct = surface_conductor_loss(doc.cross_section.section,F,conductivity=SIGMA,
        ground_thickness=35e-6,roughness=MODEL,**MESH)
    np.testing.assert_allclose(result.R,direct.R,rtol=1e-10,atol=0)
    np.testing.assert_allclose(result.L,result.dielectric.L+direct.L_internal,rtol=1e-10,atol=0)
    smooth = surface_impedance(F,conductivity=SIGMA)
    rough = surface_impedance(F,conductivity=SIGMA,roughness=MODEL)
    np.testing.assert_allclose(result.conductor.roughness_factor,rough.real/smooth.real,rtol=1e-12)
    np.testing.assert_array_equal(result.dielectric.C0,result.conductor.factors.C0)
    np.testing.assert_allclose(result.network.s,result.network.s.swapaxes(1,2),rtol=0,atol=1e-10)
    assert np.max(np.linalg.svd(result.network.s,compute_uv=False)) <= 1+1e-10
    raw = doc.to_dict()
    raw['conductor']['roughness']['radii_m'][0] = 1
    assert restored.dumps() == doc.dumps()


def test_coupled_r_and_internal_l_refinement(solved):
    doc,coarse = solved
    fine = surface_conductor_loss(doc.cross_section.section,F,conductivity=SIGMA,
        ground_thickness=35e-6,roughness=MODEL,edge_size=2.5e-6,far_size=.1e-3,grade=.05)
    for a,b in ((coarse.R,fine.R),(coarse.conductor.L_internal,fine.L_internal)):
        assert np.max(abs(a-b))/np.max(abs(b)) < .05
    assert fine.factors.current_error < coarse.conductor.factors.current_error < .05


@pytest.mark.parametrize('rms',[0,1e-6])
def test_v2_smooth_and_hammerstad_reproduce_legacy_v1(rms):
    roughness = {'kind':'smooth'} if rms == 0 else {'kind':'hammerstad','rms_m':rms}
    v2 = line(roughness)
    raw = v2.to_dict()
    raw['schema'] = 'sipi.transmission-line/1'
    raw['conductor'].pop('roughness')
    raw['conductor']['roughness_rms'] = rms
    v1 = TransmissionLineDocument.from_dict(raw)
    assert TransmissionLineDocument.loads(v1.dumps()).to_dict()['schema'] == raw['schema']
    a,b = v1.analyze(),v2.analyze()
    for name in ('R','L','G','C'):
        np.testing.assert_array_equal(getattr(a,name),getattr(b,name))
    np.testing.assert_array_equal(a.network.s,b.network.s)


@pytest.mark.parametrize('mutate',[
    lambda d:d.update(schema='sipi.transmission-line/3'),
    lambda d:d['conductor'].update(roughness_rms=0),
    lambda d:d['conductor'].pop('roughness'),
    lambda d:d['conductor'].update(roughness=None),
    lambda d:d['conductor']['roughness'].update(rms_m=0),
    lambda d:d['conductor']['roughness'].update(kind='huray'),
    lambda d:d['conductor']['roughness'].update(radii_m=[True,1e-6]),
    lambda d:d['conductor']['roughness'].update(surface_ratios=None),
    lambda d:d['conductor'].update(roughness={'kind':'hammerstad','rms_m':None}),
    lambda d:d['conductor'].update(roughness={'kind':'smooth','rms_m':0}),
    lambda d:d.update(schema='sipi.transmission-line/1'),
    lambda d:d.update(frequency_hz=[0,1e9]),
    lambda d:d.update(frequency_hz=[1e3,1e6]),
])
def test_invalid_v2_rejected_before_meshing(monkeypatch,mutate):
    raw = line().to_dict()
    def forbidden(*args,**kwargs):
        pytest.fail('invalid input reached meshing')
    monkeypatch.setattr(CrossSection,'mesh',forbidden)
    mutate(raw)
    with pytest.raises(ValueError):
        TransmissionLineDocument.from_dict(raw)


def test_perfect_v2_preserves_version_and_duplicate_fields_rejected():
    doc = line(conductor={'kind':'perfect'},frequency=[0,1e9])
    assert doc.to_dict()['schema'] == 'sipi.transmission-line/2'
    assert TransmissionLineDocument.loads(doc.dumps()).dumps() == doc.dumps()
    for bad in ('"radii_m": null','"radii_m": [NaN]',
                '"radii_m": [1e-6], "radii_m": [2e-6]'):
        text = line().dumps()
        start = text.index('"radii_m"')
        end = text.index(']',start)+1
        with pytest.raises(ValueError):
            TransmissionLineDocument.loads(text[:start]+bad+text[end:])
