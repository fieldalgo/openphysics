# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Matched metal/dielectric geometry, independent C and strict saved inputs."""
import copy
import importlib.metadata as metadata
import json

import numpy as np
import pytest
from scipy.constants import epsilon_0

from crosscheck import Stopwatch,emit,make_record,observable,require_tool
from galerkin import disk_mesh
from sipi import CrossSection,Layer,Trace,CrossSectionDocument,microstrip
from sipi.conductor_mesh import MeshedConductors,mesh_conductor_section
from sipi.dielectric import ConstantDielectric,DebyeDielectric,TabulatedDielectric,dispersive_line
from sipi.quasistatic import capacitance_matrix
from sipi.volume_line import VolumeLineDocument,dielectric_view,volume_line

SIGMA = 58e6
MESH = dict(ground_thickness=.1e-3,padding=2e-3,metal_size=50e-6,
            far_size=.5e-3,grade=.2,min_angle=28.)
FINE = dict(MESH,metal_size=25e-6,far_size=.25e-3,grade=.1)


def section(taper=False):
    return microstrip(width=.4e-3,top_width=.2e-3 if taper else None,
        substrate_height=.5e-3,thickness=.1e-3,eps_r=4,tan_delta=.02,
        air_height=.5e-3,box_width=2e-3)


def document(cs=None,mesh=None):
    return VolumeLineDocument(CrossSectionDocument(section() if cs is None else cs),
        [0,1e3,1e5],materials={},mesh=MESH if mesh is None else mesh,
        conductivity=SIGMA,length=.1)


def coax(nr=8,nt=128):
    a,b,c = .5e-3,1.5e-3,2e-3
    mesh = disk_mesh([a,b,c,3e-3],[nr,nr,nr,4],nt)
    ids = lambda region:np.flatnonzero(mesh.regions == region)
    volume = MeshedConductors(mesh,{'inner':ids(0)},ids(2),mesh.boundary['outer'],{},
                             {'dielectric':ids(1)})
    return volume,2*np.pi*epsilon_0/np.log(b/a)


def test_coax_complex_capacitance_analytic_and_same_volume_series():
    volume,exact = coax(32,256)
    f = [0,1e3,1e5]
    material = DebyeDielectric(2,[2],[1e4])
    result = volume_line(volume,f,materials={'dielectric':material},conductivity=SIGMA,length=.1)
    expected = exact*material.permittivity(f)
    error = np.max(abs(result.C_complex[:,0,0]/expected-1))
    previous = []
    for nr in (8,16):
        v,_ = coax(nr,256)
        electric,signals,ground,_ = dielectric_view(v)
        previous.append(float(abs(capacitance_matrix(electric,1.,signals,ground)[0,0]/exact-1)))
    assert previous[0] > previous[1] > error
    assert error < .001
    electric,signals,ground,_ = dielectric_view(volume)
    c0 = capacitance_matrix(electric,1.,signals,ground)
    np.testing.assert_allclose(result.C_complex,material.permittivity(f)[:,None,None]*c0,
                               rtol=1e-10,atol=0)
    direct = volume.impedance(f,conductivity=SIGMA)
    np.testing.assert_allclose(result.R,direct.R,rtol=1e-12,atol=0)
    np.testing.assert_allclose(result.L,direct.L,rtol=1e-12,atol=0)
    np.testing.assert_allclose(result.network.s,result.network.s.swapaxes(1,2),atol=1e-10)
    assert np.max(np.linalg.svd(result.network.s,compute_uv=False)) <= 1+1e-10
    assert not result.C.flags.writeable
    # Correct DC series-resistance network, not an ideal-through placeholder.
    rdc = result.R[0,0,0]*.1
    assert result.network.s[0,1,0] == pytest.approx(100/(100+rdc),rel=1e-12)


def test_independent_complex_electric_assembly_on_matched_volume():
    skfem = require_tool('scikit-fem')
    from skfem.helpers import dot,grad
    from scipy.sparse.linalg import spsolve
    volume,_ = coax()
    material = ConstantDielectric(4,.02)
    clock = Stopwatch()
    with clock('openphysics'):
        result = volume_line(volume,[1e4],materials={'dielectric':material},conductivity=SIGMA,length=.1)
    mesh,signals,ground,triangles = dielectric_view(volume)
    eps = np.ones(volume.mesh.num_triangles,dtype=complex)
    eps[volume.layer_triangles['dielectric']] = material.permittivity(1e4)
    with clock('reference'):
        basis = skfem.Basis(skfem.MeshTri(mesh.nodes.T,mesh.triangles.T),skfem.ElementTriP1())
        @skfem.BilinearForm(dtype=complex)
        def form(u,v,w):
            return w.eps*dot(grad(u),grad(v))
        k = skfem.asm(form,basis,eps=eps[triangles,None])
        potential = np.zeros(mesh.num_nodes,dtype=complex)
        potential[signals['inner']] = 1
        fixed = np.r_[signals['inner'],ground]
        free = np.setdiff1d(np.arange(mesh.num_nodes),fixed)
        potential[free] = spsolve(k[free][:,free],-(k@potential)[free])
        reference = epsilon_0*(potential@(k@potential))
    error = float(abs(result.C_complex[0,0,0]/reference-1))
    record = make_record(case='sipi-volume-line',physics='matched electrostatic conductor capacitance',
        api='sipi.volume_line.volume_line',discretization='P1 electric submesh of conductor volume mesh',
        tool='scikit-fem',tool_discretization='independent complex P1 form and Dirichlet solve',
        matched=['same dielectric triangles and metal surfaces, eps=4*(1-j*.02)',
                 'inner 1V, return 0V, electric exterior zero normal D, 10 kHz'],
        not_matched=['same-mesh electric agreement does not establish boundary or mesh convergence'],
        observables=[observable('complex capacitance','F/m','relative difference',error,1e-9)],
        analytical_acceptance='tests/sipi/test_volume_line.py: coax capacitance and finite-box refinement',
        stopwatch=clock)
    record['openphysics']['distribution']='sipi'
    record['openphysics']['version']=metadata.version('sipi')
    emit(record)
    assert error < 1e-9


def test_material_interfaces_areas_and_identical_electrode_coordinates():
    # Two layers meet inside a taper: both interface pieces must be conforming.
    cs = CrossSection([Layer('lower',.55e-3,4),Layer('upper',.45e-3,2)],
        [Trace('signal',0,.4e-3,.5e-3,.1e-3,top_width=.2e-3)],2e-3)
    volume = mesh_conductor_section(cs,**MESH,dielectric_interfaces=True)
    areas = volume.mesh.areas()
    for layer,y0,y1 in zip(cs.layers,[0,.55e-3],[.55e-3,1e-3]):
        trace = cs.traces[0]
        lo,hi = max(y0,trace.y),min(y1,trace.y1)
        occupied = (hi-lo)*(trace.width_at(lo)+trace.width_at(hi))/2 if hi>lo else 0
        ids = volume.layer_triangles[layer.name]
        assert areas[ids].sum() == pytest.approx(cs.width*(y1-y0)-occupied,rel=1e-10)
        coordinates = volume.mesh.nodes[volume.mesh.triangles[ids]]
        assert coordinates[:,:,1].min() >= y0-1e-14
        assert coordinates[:,:,1].max() <= y1+1e-14
        assert abs(coordinates[:,:,0]).max() <= cs.width/2+1e-14
    mesh,signals,ground,triangles = dielectric_view(volume)
    surviving = set(map(tuple,mesh.nodes))
    for ids,electrode in [(volume.signals['signal'],signals['signal']),(volume.ground,ground)]:
        original = set(map(tuple,volume.mesh.nodes[np.unique(volume.mesh.triangles[ids])]))
        assert set(map(tuple,mesh.nodes[electrode])) == original & surviving
    assert mesh.num_triangles+len(volume.ground)+len(volume.signals['signal']) == volume.mesh.num_triangles


def test_finite_box_mesh_and_outer_boundary_convergence():
    coarse = document().analyze()
    fine = document(mesh=FINE).analyze()
    finest_mesh = dict(FINE,metal_size=12.5e-6,far_size=.125e-3,grade=.05)
    finest = document(mesh=finest_mesh).analyze()
    enlarged = document(mesh=dict(finest_mesh,padding=4e-3)).analyze()
    for name in ('C','G'):
        a,b,c,d = (getattr(result,name) for result in (coarse,fine,finest,enlarged))
        error1 = np.max(abs(a-b))/np.max(abs(b))
        error2 = np.max(abs(b-c))/np.max(abs(c))
        print(name,dict(coarse_fine=float(error1),fine_finest=float(error2),
                       padding=float(np.max(abs(c-d))/np.max(abs(d)))))
        assert error2 < error1
        assert error2 < .01
        assert np.max(abs(c-d))/np.max(abs(d)) < .02


def test_closed_ground_box_agrees_with_existing_dielectric_solver():
    cs = CrossSection([Layer('dielectric',1e-3,4)],
        [Trace('signal',0,.4e-3,.45e-3,.1e-3)],2e-3,top='ground',sides='ground')
    material = DebyeDielectric(2,[2],[1e4])
    volume = mesh_conductor_section(cs,**FINE,dielectric_interfaces=True)
    actual = volume_line(volume,[0,1e3,1e5],materials={'dielectric':material},
                         conductivity=SIGMA,length=.1)
    existing = dispersive_line(cs,[0,1e3,1e5],materials={'dielectric':material},
                                edge_size=10e-6,far_size=.1e-3,grade=.1)
    assert np.max(abs(actual.C_complex-existing.C_complex))/np.max(abs(existing.C_complex)) < .01


@pytest.mark.parametrize('taper',[False,True])
def test_json_reproduction_snapshot_and_one_geometry_mesh(monkeypatch,taper):
    import sipi.volume_line as implementation
    doc = document(section(taper))
    raw = doc.to_dict()
    expected = copy.deepcopy(raw)
    restored = VolumeLineDocument.loads(doc.dumps())
    raw['mesh']['padding'] = 999
    raw['cross_section']['schema'] = 'invalid'
    assert doc.to_dict() == expected == restored.to_dict()
    original = implementation.mesh_conductor_section
    calls = []
    def tracked(*a,**k):
        calls.append(True)
        return original(*a,**k)
    monkeypatch.setattr(implementation,'mesh_conductor_section',tracked)
    a,b = doc.analyze(),restored.analyze()
    assert len(calls) == 2
    assert a.input_json == doc.dumps()
    for name in ('R','L','G','C'):
        np.testing.assert_allclose(getattr(a,name),getattr(b,name),rtol=1e-12,atol=0)
    np.testing.assert_allclose(a.network.s,b.network.s,atol=1e-10,rtol=0)
    assert expected['cross_section']['schema'] == ('sipi.cross-section/2' if taper else 'sipi.cross-section/1')


def test_rectangular_v2_input_keeps_its_version():
    data = document().to_dict()
    data['cross_section']['schema'] = 'sipi.cross-section/2'
    for trace in data['cross_section']['traces']:
        trace['top_width'] = trace['width']
    assert VolumeLineDocument.from_dict(data).to_dict()['cross_section']['schema'] == 'sipi.cross-section/2'


@pytest.mark.parametrize('change',[('schema','sipi.volume-line/2'),('extra',1),
    ('frequency_hz',[True]),('frequency_hz',[-1]),('reference_ohms',0),('length_m',-1),
    ('mesh',dict(MESH,padding=0)),('mesh',dict(MESH,grade=True)),
    ('mesh',dict(MESH,min_angle=34)),('mesh',dict(MESH,far_size=1e-6)),
    ('conductor',dict(conductivity=0,relative_permeability=1)),('materials',{'unknown':{}})])
def test_invalid_document_fails_before_meshing(monkeypatch,change):
    import sipi.volume_line as implementation
    def forbidden(*a,**k):
        pytest.fail('invalid document reached meshing')
    monkeypatch.setattr(implementation,'mesh_conductor_section',forbidden)
    data = document().to_dict();data[change[0]]=change[1]
    with pytest.raises((ValueError,TypeError)):
        VolumeLineDocument.from_dict(data).analyze()


def test_table_dc_duplicate_nonfinite_and_foreign_mesh_are_rejected():
    data = document().to_dict()
    with pytest.raises(ValueError):
        VolumeLineDocument.loads(document().dumps().replace('"length_m": 0.1','"length_m": 0.1, "length_m": 1'))
    with pytest.raises(ValueError):
        VolumeLineDocument.loads(document().dumps().replace('"length_m": 0.1','"length_m": NaN'))
    with pytest.raises(ValueError):
        VolumeLineDocument(CrossSectionDocument(section()),[0,1e5],
            materials={'substrate':TabulatedDielectric([1e3,1e5],[4,3],[.02,.02])},
            mesh=MESH,conductivity=SIGMA,length=.1)
    data['cross_section']['mesh']={'edge_size':1e-5}
    with pytest.raises(ValueError,match='mesh must be empty'):
        VolumeLineDocument.from_dict(data)


def test_missing_or_overlapping_dielectric_regions_do_not_solve():
    volume,_ = coax()
    with pytest.raises(ValueError,match='every dielectric layer'):
        volume_line(volume,[0],materials={},conductivity=SIGMA,length=.1)
    invalid = MeshedConductors(volume.mesh,dict(volume.signals),volume.ground,
        volume.magnetic_boundary,{}, {'dielectric':volume.ground})
    with pytest.raises(ValueError,match='outside metal'):
        volume_line(invalid,[0],materials={'dielectric':ConstantDielectric(4)},conductivity=SIGMA,length=.1)


@pytest.mark.parametrize('indices',[[1.5,2.5],[True,2]])
def test_volume_snapshot_does_not_silently_convert_region_indices(indices):
    volume,_ = coax()
    with pytest.raises(ValueError,match='integer index'):
        MeshedConductors(volume.mesh,{'inner':indices},volume.ground,
            volume.magnetic_boundary,{},dict(volume.layer_triangles))
    with pytest.raises(ValueError,match='integer index'):
        MeshedConductors(volume.mesh,dict(volume.signals),volume.ground,
            volume.magnetic_boundary,{}, {'dielectric':indices})


def test_asymmetric_coupled_volume_line_keeps_full_port_order():
    cs = CrossSection([Layer('substrate',.5e-3,4,.02),Layer('air',.5e-3)],
        [Trace('narrow',-.35e-3,.2e-3,.5e-3,.1e-3),
         Trace('wide',.35e-3,.4e-3,.5e-3,.1e-3)],2e-3)
    result = document(cs).analyze()
    assert result.names == ('narrow','wide')
    assert result.R.shape == result.L.shape == result.C.shape == result.G.shape == (3,2,2)
    assert result.network.s.shape == (3,4,4)
    assert result.R[0,0,0] > result.R[0,1,1]
    assert result.C[0,0,1] < 0
    np.testing.assert_allclose(result.network.s,result.network.s.swapaxes(1,2),atol=1e-10)
    assert np.max(np.linalg.svd(result.network.s,compute_uv=False)) <= 1+1e-10
