"""Dispersive material contracts, exact limits and independent field/network checks."""
import json
import importlib.metadata as metadata

import numpy as np
import pytest
from scipy.constants import epsilon_0
from crosscheck import Stopwatch, emit, make_record, observable, require_tool

from sipi import CrossSection, Layer, Trace, coupled_microstrip, stripline
from sipi.dielectric import (ConstantDielectric, DebyeDielectric, WidebandDielectric,
    TabulatedDielectric, dielectric_to_dict, dielectric_from_dict, dispersive_line)

MESH = dict(edge_size=10e-6, far_size=.4e-3, grade=.2)


def test_debye_exact_pole_dc_and_high_frequency_limits():
    model = DebyeDielectric(2, [3, 1], [1e6, 1e9])
    f = np.array([0, 1e3, 1e6, 1e9, 1e15])
    exact = 2+3/(1+1j*f/1e6)+1/(1+1j*f/1e9)
    np.testing.assert_allclose(model.permittivity(f), exact, rtol=1e-12, atol=0)
    assert model.permittivity(0) == 6
    assert DebyeDielectric(2, [3], [1e6]).permittivity(1e6) == pytest.approx(3.5-1.5j, rel=1e-12)
    assert abs(model.permittivity(1e30)-2) < 1e-12
    assert np.all(model.permittivity(f).imag <= 0)


def test_wideband_reference_passivity_rolloffs_and_zero_loss():
    model = WidebandDielectric(4, .02, 1e9)
    assert model.permittivity(1e9) == pytest.approx(4-.08j, rel=1e-12)
    f = np.r_[0, np.logspace(-3, 30, 51)]
    eps = model.permittivity(f)
    assert np.all(np.isfinite(eps)) and np.all(eps.real >= 1) and np.all(eps.imag <= 0)
    assert eps[0].imag == 0
    assert abs(eps[-1].imag) < 1e-12
    assert np.all(np.diff(eps.real) <= 1e-14)
    np.testing.assert_array_equal(WidebandDielectric(4, 0, 1e9).permittivity(f), np.full(len(f), 4))


def test_finite_scaled_debye_pole_avoids_hypot_overflow():
    model = DebyeDielectric(2, [3], [1.7e308])
    assert model.permittivity(1.7e308) == pytest.approx(3.5-1.5j, rel=1e-12)


def test_wideband_is_invariant_under_common_frequency_scale():
    standard = WidebandDielectric(4,.02,10,1,17)
    scaled = WidebandDielectric(4,.02,1e308,1e307,1.7e308)
    np.testing.assert_allclose(scaled.permittivity([0,1e307,1e308,1.7e308]),
                               standard.permittivity([0,1,10,17]), rtol=1e-12, atol=0)


def test_tabulated_complex_interpolation_and_no_extrapolation():
    table = TabulatedDielectric([1e6, 1e8, 1e10], [5, 4, 3], [.02, .03, .04])
    np.testing.assert_allclose(table.permittivity([1e6, 1e7, 1e8]),
                               [5-.1j, 4.5-.11j, 4-.12j], rtol=1e-12, atol=0)
    assert table.permittivity(1e10) == pytest.approx(3-.12j, rel=1e-12)
    for value in (0, 1e5, 1e11):
        with pytest.raises(ValueError, match='extrapolation'):
            table.permittivity(value)


@pytest.mark.parametrize('model', [ConstantDielectric(4, .02), DebyeDielectric(2, [2, 1], [1e6, 1e9]),
    WidebandDielectric(4, .02, 1e9), TabulatedDielectric([1e6, 1e9], [4, 3], [.01, .02])])
def test_versioned_material_json_roundtrip_and_exact_fields(model):
    raw = json.loads(json.dumps(dielectric_to_dict(model), allow_nan=False))
    restored = dielectric_from_dict(raw)
    assert restored == model
    np.testing.assert_array_equal(restored.permittivity([1e6, 1e9]), model.permittivity([1e6, 1e9]))
    with pytest.raises(ValueError):
        dielectric_from_dict({**raw, 'extra': 1})
    with pytest.raises(ValueError):
        dielectric_from_dict({**raw, 'schema': 'sipi.dielectric/2'})
    with pytest.raises(ValueError):
        dielectric_from_dict({**raw, 'parameters': {**raw['parameters'], 'extra': 1}})
    del raw['parameters'][next(iter(raw['parameters']))]
    with pytest.raises(ValueError):
        dielectric_from_dict(raw)


@pytest.mark.parametrize('factory', [
    lambda: ConstantDielectric(True), lambda: ConstantDielectric(.9),
    lambda: ConstantDielectric(4, -.01), lambda: ConstantDielectric(4, float('nan')),
    lambda: DebyeDielectric(2, [-1], [1e6]), lambda: DebyeDielectric(2, [1], [0]),
    lambda: DebyeDielectric(2, [1], [1e6, 1e9]), lambda: DebyeDielectric(2, [True], [1e6]),
    lambda: WidebandDielectric(4, .8, 1e9), lambda: WidebandDielectric(4, .02, 1e9, 1e10, 1e12),
    lambda: WidebandDielectric(4, .02, 1e9, 1e12, 1e3),
    lambda: TabulatedDielectric([1e6, 1e6], [4, 4], [0, 0]),
    lambda: TabulatedDielectric([0, 1e6], [4, 4], [0, 0]),
    lambda: TabulatedDielectric([1e6, 1e9], [4, .9], [0, 0]),
    lambda: TabulatedDielectric([1e6, 1e9], [4, 4], [0, -.01]),
])
def test_invalid_materials_are_rejected(factory):
    with pytest.raises(ValueError):
        factory()


@pytest.mark.parametrize('frequency', [True, [True, 1e9], [-1], [float('inf')], [], [[1e9]], ['1e9']])
def test_invalid_frequency_samples_are_rejected(frequency):
    with pytest.raises(ValueError):
        WidebandDielectric(4, .02, 1e9).permittivity(frequency)


def test_constant_reproduces_existing_extraction_and_homogeneous_debye_scaling():
    section = stripline(width=.5e-3, plane_spacing=1e-3, eps_r=4, tan_delta=.02)
    native = section.analyze(**MESH)
    constant = dispersive_line(section, [0, 1e6, 1e9], materials={}, **MESH)
    np.testing.assert_allclose(constant.C_complex, np.broadcast_to(native.C-1j*native.C_loss, (3,1,1)), rtol=1e-10)
    np.testing.assert_allclose(constant.L, native.L, rtol=1e-10)
    for i, f in enumerate(constant.frequency):
        np.testing.assert_allclose(constant.G[i], native.G(f), rtol=1e-10, atol=0)
    model = DebyeDielectric(2, [2], [1e9])
    result = dispersive_line(section, [0, 1e6, 1e9, 1e12], materials={'dielectric': model}, **MESH)
    np.testing.assert_allclose(result.C_complex, model.permittivity(result.frequency)[:,None,None]*result.C0,
                               rtol=1e-10, atol=0)
    with pytest.raises(ValueError):
        result.C_complex[0,0,0] = 1
    with pytest.raises(ValueError):
        result.layer_permittivity['dielectric'][0] = 1
    with pytest.raises(TypeError):
        result.layer_permittivity['air'] = np.ones(4)
    net = result.network(length=.1, R=[[0]])
    np.testing.assert_allclose(net.s, net.s.swapaxes(1,2), atol=1e-10, rtol=0)
    assert np.max(np.linalg.svd(net.s, compute_uv=False)) <= 1+1e-10
    # Independent scalar ABCD from the homogeneous complex TEM solution.
    f = result.frequency
    z = np.sqrt(result.L[0,0]/result.C_complex[:,0,0])
    gamma = 2j*np.pi*f*np.sqrt(result.L[0,0]*result.C_complex[:,0,0])
    a, b = np.cosh(gamma*.1), np.sinh(gamma*.1)
    denominator = 2*a+b*(z/50+50/z)
    np.testing.assert_allclose(net.s[:,1,0], 2/denominator, atol=1e-10, rtol=0)
    np.testing.assert_allclose(net.s[:,0,0], b*(z/50-50/z)/denominator, atol=1e-10, rtol=0)


def test_invalid_sweep_is_rejected_before_meshing(monkeypatch):
    section = stripline(width=.5e-3, plane_spacing=1e-3, eps_r=4)
    def forbidden(**kwargs):
        pytest.fail('Invalid material request reached the mesh')
    monkeypatch.setattr(section, 'mesh', forbidden)
    for f, materials in [([1e9], {'unknown': ConstantDielectric(4)}),
                         ([1e9], {'dielectric': object()}),
                         ([1e9,1e6], {}),
                         ([0,1e9], {'dielectric': TabulatedDielectric([1e6,1e9],[4,3],[0,0])})]:
        with pytest.raises(ValueError):
            dispersive_line(section, f, materials=materials)


def test_inhomogeneous_refinement_and_passive_coupled_network():
    section = coupled_microstrip(width=.5e-3, gap=.3e-3, substrate_height=1e-3, eps_r=4, thickness=.05e-3)
    kwargs = dict(frequency=[1e6, 1e9, 1e11], materials={'substrate': WidebandDielectric(4,.02,1e9)})
    coarse = dispersive_line(section, **kwargs, **MESH)
    refined = dispersive_line(section, **kwargs, edge_size=MESH['edge_size']/2,
                              far_size=MESH['far_size']/2, grade=MESH['grade']/2)
    change = np.max(abs(coarse.C_complex-refined.C_complex))/np.max(abs(refined.C_complex))
    print({'complex_C_mesh_change':float(change)})
    assert change < .01
    net = refined.network(length=.01, R=np.zeros((2,2)))
    np.testing.assert_allclose(net.s, net.s.swapaxes(1,2), atol=1e-10, rtol=0)
    assert np.max(np.linalg.svd(net.s, compute_uv=False)) <= 1+1e-10


def test_independent_skrf_wideband_dielectric():
    skrf = require_tool('scikit-rf')
    clock = Stopwatch()
    model = WidebandDielectric(4.2,.018,2e9,1e3,1e12)
    f = np.r_[0,np.logspace(0,15,43)]
    # Public method depends only on its arguments, independent of line geometry.
    with clock('reference'):
        expected, _ = skrf.media.MLine.analyse_dielectric(None, 4.2,.018,1e3,1e12,2e9,f,'djordjevicsvensson')
    with clock('openphysics'):
        actual = model.permittivity(f)
    error = np.max(abs(actual-expected))/np.max(abs(expected))
    print({'scikit_rf':skrf.__version__, 'relative_eps_difference':float(error)})
    record = make_record(case='sipi-wideband-dielectric', physics='passive log-relaxation dielectric',
        api='sipi.dielectric.WidebandDielectric', discretization='scaled log-magnitude and phase',
        tool='scikit-rf', tool_discretization='MLine.analyse_dielectric direct complex logarithm',
        matched=['eps_ref4.2, tan_delta.018 at2GHz, rolloffs1kHz/1THz, same frequency samples'], not_matched=[],
        observables=[observable('complex relative permittivity','1','max relative difference',error,1e-12)],
        analytical_acceptance='test_dielectric.py reference point, passivity and limits; no measured-material claim',
        stopwatch=clock)
    record['openphysics'].update(distribution='sipi',version=metadata.version('sipi'))
    emit(record)
    assert error <= 1e-12


def test_independent_skfem_frequency_dependent_layered_complex_capacitance():
    skfem = require_tool('scikit-fem')
    clock = Stopwatch()
    from skfem.helpers import dot, grad
    section = CrossSection([Layer('lower',1e-3,4),Layer('upper',1e-3,2)],
        [Trace('a',-.5e-3,.5e-3,1e-3),Trace('b',.5e-3,.3e-3,1e-3)],4e-3,top='ground')
    models = {'lower':DebyeDielectric(2,[3],[1e8]), 'upper':WidebandDielectric(3,.03,1e9)}
    with clock('openphysics'):
        result = dispersive_line(section,[1e6,1e8,1e10],materials=models,**MESH)
    m = section.mesh(**MESH)
    basis = skfem.Basis(skfem.MeshTri(m.mesh.nodes.T,m.mesh.triangles.T),skfem.ElementTriP1())
    @skfem.BilinearForm(dtype=np.complex128)
    def form(u,v,w):
        return w.eps*dot(grad(u),grad(v))
    fixed = np.unique(np.concatenate([m.ground,*m.signals.values()]))
    errors=[]
    for i, f in enumerate(result.frequency):
        eps = np.array([models[m.mesh.region_names[r]].permittivity(f) for r in m.mesh.regions])
        with clock('reference'):
            k = skfem.asm(form,basis,eps=eps[:,None])
            potentials=[]
            for signal in m.signals.values():
                boundary=np.zeros(basis.N,dtype=complex);boundary[signal]=1
                potentials.append(skfem.solve(*skfem.condense(k,np.zeros(basis.N,dtype=complex),x=boundary,D=fixed)))
            v=np.stack(potentials,axis=1)
            expected=epsilon_0*(v.T@(k@v))
        errors.append(float(np.max(abs(result.C_complex[i]-expected))/np.max(abs(expected))))
    print({'scikit_fem':skfem.__version__, 'C_relative_difference':errors})
    record = make_record(case='sipi-layered-dielectric-sweep',physics='layered complex electrostatics',
        api='sipi.dielectric.dispersive_line',discretization='fixed P1 triangular mesh, complex energy C',
        tool='scikit-fem',tool_discretization='independent P1 assembly, condense/solve and complex energy',
        matched=['identical mesh, conductor/ground nodes and per-element complex permittivity',
                 '1MHz,100MHz,10GHz; two asymmetric signal conductors'],
        not_matched=['independent discretization convergence; tested separately'],
        observables=[observable('complex capacitance','F/m','max relative difference',max(errors),1e-9)],
        analytical_acceptance='test_dielectric.py homogeneous TEM and1% separate mesh-refinement gate',stopwatch=clock)
    record['openphysics'].update(distribution='sipi',version=metadata.version('sipi'))
    emit(record)
    assert max(errors) <= 1e-9
