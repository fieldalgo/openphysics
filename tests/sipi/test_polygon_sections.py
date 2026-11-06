# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Polygon topology, material conformity, independent fields and saved inputs."""
import copy

import numpy as np
import pytest
from scipy.constants import epsilon_0
from shapely.geometry import Polygon

from crosscheck import require_tool, Stopwatch, emit, make_record, observable
from sipi import CrossSection, CrossSectionDocument, Layer, Trace, PolygonTrace, DielectricRegion
from sipi.dielectric import ConstantDielectric, DebyeDielectric, dispersive_line
from sipi.conductor_mesh import mesh_conductor_section
from sipi.volume_line import VolumeLineDocument
from sipi.line_model import TransmissionLineDocument

MESH = dict(edge_size=10e-6, far_size=.2e-3, grade=.15)
FINE = dict(edge_size=5e-6, far_size=.1e-3, grade=.075)
VOLUME = dict(ground_thickness=.1e-3, padding=1e-3, metal_size=40e-6,
              far_size=.3e-3, grade=.2, min_angle=28.)
SIGMA = 58e6


def section(mask=True, mirror=False):
    # A reentrant corner and a sloped face, crossing the layer boundary.
    vertices = np.array([[-.35,.8],[.35,.8],[.25,1.2],[0,1.2],[0,1.05],[-.35,1.05]])*1e-3
    region = np.array([[-.6,.7],[.6,.7],[.6,1.4],[-.6,1.4]])*1e-3
    if mirror:
        vertices[:,0] *= -1
        region[:,0] *= -1
    return CrossSection([Layer('lower',1e-3,4,.01),Layer('upper',1e-3,2,.02)],
        [PolygonTrace('signal',vertices)],4e-3,top='ground',
        dielectric_regions=[DielectricRegion('mask',region,3,.03)] if mask else [])


def areas(mesh):
    p=mesh.nodes[mesh.triangles]
    a,b=p[:,1]-p[:,0],p[:,2]-p[:,0]
    return np.abs(a[:,0]*b[:,1]-a[:,1]*b[:,0])/2


@pytest.mark.parametrize('vertices',[
    [(0,0),(1,1),(0,1),(1,0)], [(0,0),(1,0),(2,0)],
    [(0,0),(1,0),(1,1),(0,0)], [(0,0),(True,0),(1,1)],
    [(0,0),(1,float('nan')),(1,1)], [(0,0),(1,0)], [[1],[2],[3]], None,
])
def test_invalid_polygon(vertices):
    with pytest.raises(ValueError):
        PolygonTrace('signal',vertices)


def test_geometry_is_immutable_and_orientation_independent():
    points=[[-1,1],[1,1],[1,2],[-1,2]]
    a=PolygonTrace('a',points)
    points[0][0]=-99
    assert a.vertices[0] == (-1,1)
    b=PolygonTrace('b',a.vertices[::-1])
    np.testing.assert_allclose(a.distance([0,2,0],[1.5,1.5,0]),[0,1,1])
    np.testing.assert_array_equal(a.distance([0,2],[1.5,1.5]),b.distance([0,2],[1.5,1.5]))
    assert a.minimum_dimension == 1


def test_topology_and_material_names_are_unambiguous():
    a=PolygonTrace('a',[[-1,1],[0,1],[0,2],[-1,2]])
    b=PolygonTrace('b',[[0,1],[1,1],[1,2],[0,2]])
    with pytest.raises(ValueError,match='touch or overlap'):
        CrossSection([Layer('d',3)], [a,b],4)
    for regions in (
        [DielectricRegion('d',[[-1,0],[1,0],[1,1],[-1,1]])],
        [DielectricRegion('outside',[[-3,0],[1,0],[1,1],[-3,1]])],
        [DielectricRegion('buried',a.vertices)],
        [DielectricRegion('one',[[-1,0],[1,0],[1,1.5],[-1,1.5]]),
         DielectricRegion('two',[[-1,.5],[1,.5],[1,1.8],[-1,1.8]])],
    ):
        with pytest.raises(ValueError):
            CrossSection([Layer('d',3)], [a],4,dielectric_regions=regions)
    # Bounding boxes overlap, but the conductors themselves do not.
    notch=PolygonTrace('notch',[[-1,1],[1,1],[1,2],[.5,2],[.5,1.5],[-1,1.5]])
    other=Trace('other',-.3,.5,1.7,.1)
    CrossSection([Layer('d',3)],[notch,other],4)


def test_exact_area_material_boundaries_and_polygon_boundary_nodes():
    cs=section()
    m=cs.mesh(**MESH)
    a=areas(m.mesh)
    expected=cs.width*cs.height-Polygon(cs.traces[0].vertices).area
    assert a.sum() == pytest.approx(expected,rel=1e-12)
    mask=Polygon(cs.dielectric_regions[0].vertices).difference(Polygon(cs.traces[0].vertices))
    labels=np.asarray(m.mesh.region_names)[m.mesh.regions]
    assert a[labels=='mask'].sum() == pytest.approx(mask.area,rel=1e-12)
    for nodes,label in zip(m.mesh.nodes[m.mesh.triangles],labels):
        triangle=Polygon(nodes)
        overlap=triangle.intersection(mask).area
        assert overlap == pytest.approx(triangle.area if label=='mask' else 0,abs=1e-20)
        if label in ('lower','upper'):
            assert nodes[:,1].max() <= 1e-3+1e-12 if label=='lower' else nodes[:,1].min() >= 1e-3-1e-12
    p=m.mesh.nodes[m.signals['signal']]
    np.testing.assert_allclose(cs.traces[0].distance(p[:,0],p[:,1]),0,atol=1e-12)
    assert set(m.eps_r)=={2,3,4}


def test_polygon_rectangular_limit_convergence_reflection_and_homogeneous_scaling():
    t=Trace('signal',0,.6e-3,.8e-3,.4e-3)
    rect=CrossSection([Layer('d',2e-3,4)],[t],4e-3,top='ground')
    polygon=CrossSection(rect.layers,[PolygonTrace('signal',t.corners())],4e-3,top='ground')
    a,b=rect.analyze(**FINE),polygon.analyze(**FINE)
    assert abs(a.z0/b.z0-1)<.005
    np.testing.assert_allclose(b.C/b.C0,4,rtol=1e-9)
    coarse,fine,reflected=[cs.analyze(**mesh) for cs,mesh in
        ((section(),MESH),(section(),FINE),(section(mirror=True),FINE))]
    print(dict(rect_z0=a.z0,polygon_z0=b.z0,coarse_z0=coarse.z0,fine_z0=fine.z0,reflected_z0=reflected.z0))
    assert abs(coarse.z0/fine.z0-1)<.005
    assert abs(reflected.z0/fine.z0-1)<.005


def test_thin_strip_crosses_local_material_and_polygon_domain():
    cs=CrossSection([Layer('d',2e-3,4)],
        [Trace('thin',-.6e-3,.4e-3,1e-3),
         PolygonTrace('solid',[[.3e-3,.8e-3],[.7e-3,.8e-3],[.5e-3,1.2e-3]])],4e-3,
        dielectric_regions=[DielectricRegion('local',[[-.6e-3,.5e-3],[0,.5e-3],[0,1.5e-3],[-.6e-3,1.5e-3]],2)])
    m=cs.mesh(**MESH)
    p=m.mesh.nodes[m.signals['thin']]
    assert p[:,0].min()==pytest.approx(-.8e-3)
    assert p[:,0].max()==pytest.approx(-.4e-3)
    np.testing.assert_allclose(p[:,1],1e-3,atol=1e-12)
    line=m.line_parameters()
    assert line.C[0,1]<0
    assert np.min(np.linalg.eigvalsh(line.C))>0


def test_json_v3_strict_roundtrip_and_nested_dispersive_line():
    doc=CrossSectionDocument(section(),mesh=MESH)
    raw=doc.to_dict()
    assert raw['schema']=='sipi.cross-section/3'
    assert CrossSectionDocument.loads(doc.dumps()).to_dict()==raw
    np.testing.assert_array_equal(doc.analyze().C,CrossSectionDocument.loads(doc.dumps()).analyze().C)
    for change in ('missing','extra','kind','bool','version'):
        invalid=copy.deepcopy(raw)
        if change=='missing': del invalid['dielectric_regions']
        if change=='extra': invalid['traces'][0]['width']=1
        if change=='kind': invalid['traces'][0]['kind']='circle'
        if change=='bool': invalid['traces'][0]['vertices'][0][0]=True
        if change=='version': invalid['schema']='sipi.cross-section/4'
        with pytest.raises(ValueError): CrossSectionDocument.from_dict(invalid)
    model=DebyeDielectric(2,[1],[1e8])
    line=TransmissionLineDocument(doc,[1e7,1e9],materials={'mask':model},
        conductor={'kind':'perfect'},length=.1)
    restored=TransmissionLineDocument.loads(line.dumps())
    assert restored.cross_section.to_dict()==line.cross_section.to_dict()
    result=restored.analyze()
    np.testing.assert_allclose(result.dielectric.layer_permittivity['mask'],model.permittivity(result.frequency))
    assert np.all(result.G[:,0,0]>0)


def test_independent_complex_fields_with_local_material():
    skfem=require_tool('scikit-fem')
    from skfem.helpers import dot,grad
    m=section().mesh(**MESH)
    clock=Stopwatch()
    with clock('reference'):
        basis=skfem.Basis(skfem.MeshTri(m.mesh.nodes.T,m.mesh.triangles.T),skfem.ElementTriP1())
        @skfem.BilinearForm(dtype=complex)
        def form(u,v,w): return w.eps*dot(grad(u),grad(v))
        k=skfem.asm(form,basis,eps=(m.eps_r*(1-1j*m.tan_delta))[:,None])
        boundary=np.zeros(basis.N,dtype=complex)
        boundary[m.signals['signal']]=1
        fixed=np.unique(np.r_[m.ground,m.signals['signal']])
        v=skfem.solve(*skfem.condense(k,np.zeros(basis.N,dtype=complex),x=boundary,D=fixed))
        reference=epsilon_0*(v@(k@v))
    with clock('openphysics'):
        result=m.line_parameters()
        observed=(result.C-1j*result.C_loss)[0,0]
    error=abs(observed/reference-1)
    print(dict(skfem=skfem.__version__,complex_C_relative_error=float(error)))
    record=make_record(case='sipi-polygon-mask',physics='complex polygonal cross-section capacitance',
        api='sipi.CrossSection.analyze',discretization='conforming P1 dielectric mesh with local polygon mask',
        tool='scikit-fem',tool_discretization='independent complex P1 assembly and Dirichlet solve',
        matched=['same triangles, eps=4/2/3, tan_delta=.01/.02/.03',
                 'concave signal at 1 V, top/bottom at 0 V, insulated side walls'],
        not_matched=['same-mesh comparison does not establish mesh or domain convergence'],
        observables=[observable('complex capacitance','F/m','relative difference',error,1e-9)],
        analytical_acceptance='tests/sipi/test_polygon_sections.py: homogeneous scaling, area, DC and refinement',
        stopwatch=clock)
    import importlib.metadata as metadata
    record['openphysics'].update(distribution='sipi',version=metadata.version('sipi'))
    emit(record)
    assert error<1e-9


def test_matched_volume_exact_metal_and_mask_areas_dc_and_saved_materials():
    cs=section()
    v=mesh_conductor_section(cs,**VOLUME,dielectric_interfaces=True)
    a=areas(v.mesh)
    metal_area=Polygon(cs.traces[0].vertices).area
    mask_area=Polygon(cs.dielectric_regions[0].vertices).area-metal_area
    assert a[v.signals['signal']].sum()==pytest.approx(metal_area,rel=1e-12)
    assert a[v.layer_triangles['mask']].sum()==pytest.approx(mask_area,rel=1e-12)
    ground_area=2*cs.width*VOLUME['ground_thickness']
    assert a[v.ground].sum()==pytest.approx(ground_area,rel=1e-12)
    r=v.impedance([0],conductivity=SIGMA).R[0,0,0]
    assert r==pytest.approx((1/metal_area+1/ground_area)/SIGMA,rel=1e-9)
    doc=VolumeLineDocument(CrossSectionDocument(cs),[0],materials={'mask':ConstantDielectric(3,.03)},
        mesh=VOLUME,conductivity=SIGMA,length=.1)
    restored=VolumeLineDocument.loads(doc.dumps())
    assert restored.to_dict()==doc.to_dict()
    result=restored.analyze()
    assert result.R[0,0,0]==pytest.approx(r,rel=1e-12)
    assert result.C_complex[0,0,0].real>0 and result.C_complex[0,0,0].imag<0


def test_surface_mask_sides_top_and_gap_are_exact_and_serializable():
    from sipi.templates import coupled_microstrip, with_surface_mask
    cs=coupled_microstrip(width=.4e-3,gap=.2e-3,substrate_height=1e-3,eps_r=4,
                         thickness=.1e-3,air_height=1e-3,box_width=4e-3)
    coated=with_surface_mask(cs,thickness=.03e-3,eps_r=3.5,tan_delta=.03)
    assert [r.name for r in coated.dielectric_regions]==['mask_1','mask_2']
    # Below the common bottom face is bare substrate; top and both sides have
    # exactly 30 um coating. The middle of the inter-trace gap remains air.
    from shapely.geometry import Point
    left=Polygon(coated.dielectric_regions[0].vertices)
    assert left.bounds==pytest.approx((-.53e-3,1e-3,-.07e-3,1.13e-3))
    assert not left.covers(Point(0,1.05e-3))
    filled=with_surface_mask(cs,thickness=.03e-3,eps_r=3.5,gap_fill_height=.08e-3)
    assert len(filled.dielectric_regions)==1
    assert Polygon(filled.dielectric_regions[0].vertices).covers(Point(0,1.05e-3))
    a,b,c=[s.analyze(**MESH) for s in (cs,coated,filled)]
    assert np.min(np.linalg.eigvalsh(b.C-a.C))>0
    assert np.min(np.linalg.eigvalsh(c.C-b.C))>0
    doc=CrossSectionDocument(filled,mesh=MESH)
    assert doc.to_dict()['traces'][0]['kind']=='trapezoid'
    assert CrossSectionDocument.loads(doc.dumps()).to_dict()==doc.to_dict()
    # Removing the permittivity contrast recovers the uncoated result, up to
    # independent meshes, rather than changing the conductor or layer geometry.
    air=with_surface_mask(cs,thickness=.03e-3,eps_r=1,gap_fill_height=.08e-3).analyze(**MESH)
    assert np.max(abs(air.C-a.C))/np.max(abs(a.C))<.005


def test_additional_stripline_families_symmetry_and_limits():
    from sipi.templates import stripline, offset_stripline, coupled_stripline, broadside_stripline
    kw=dict(width=.4e-3,plane_spacing=2e-3,eps_r=4,thickness=.1e-3,box_width=4e-3)
    a=stripline(**kw).mesh(**MESH)
    b=offset_stripline(**kw,trace_height=.95e-3).mesh(**MESH)
    np.testing.assert_array_equal(a.mesh.nodes,b.mesh.nodes)
    np.testing.assert_array_equal(a.mesh.triangles,b.mesh.triangles)
    near=offset_stripline(**kw,trace_height=.3e-3).analyze(**MESH)
    assert near.z0<a.line_parameters().z0
    for cs in (coupled_stripline(**kw,gap=.3e-3),broadside_stripline(**kw,gap=.3e-3)):
        p=cs.analyze(**MESH)
        assert p.C[0,1]<0
        np.testing.assert_allclose(p.C[0,0],p.C[1,1],rtol=.005)
        np.testing.assert_allclose(p.C/p.C0,4,rtol=1e-9)
    with pytest.raises(ValueError): broadside_stripline(**kw,gap=2e-3)


@pytest.mark.parametrize('change',[dict(thickness=0),dict(eps_r=.5),dict(gap_fill_height=-1),
                                    dict(thickness=2e-3)])
def test_mask_invalid_inputs_are_rejected(change):
    from sipi.templates import microstrip,with_surface_mask
    base=microstrip(width=.4e-3,substrate_height=1e-3,eps_r=4,thickness=.1e-3,
                    air_height=1e-3,box_width=4e-3)
    with pytest.raises(ValueError):
        with_surface_mask(base,**dict(dict(thickness=.03e-3,eps_r=3),**change))


def test_polygon_surface_loss_uses_true_clearance_and_keeps_current_gate():
    from sipi.conductor import surface_conductor_loss
    cs=section()
    # Uniform scalar surface impedance remains supported on polygon boundaries.
    result=surface_conductor_loss(cs,[1e9],conductivity=SIGMA,ground_thickness=.1e-3,**FINE)
    assert result.R[0,0,0]>0
    assert result.factors.current_error<.05
    needle=PolygonTrace('needle',[[-.2e-3,1e-3],[.2e-3,1e-3],[.2e-3,1e-3+1e-8]])
    thin=CrossSection(cs.layers,[needle],cs.width)
    with pytest.raises(ValueError,match='skin depth'):
        surface_conductor_loss(thin,[1e9],conductivity=SIGMA,ground_thickness=.1e-3,**FINE)


def test_material_names_cannot_alias_volume_metals_and_closed_reference_groups():
    cs=CrossSection([Layer('__sipi_metal_0',2e-3,4)],
        [PolygonTrace('signal',[[-.2e-3,.8e-3],[.2e-3,.8e-3],[0,1.2e-3]]),
         PolygonTrace('ground',[[.5e-3,.8e-3],[.8e-3,.8e-3],[.8e-3,1.2e-3]],ground=True)],
        4e-3,top='ground',sides='ground')
    v=mesh_conductor_section(cs,**VOLUME,dielectric_interfaces=True)
    a=areas(v.mesh)
    metal=[Polygon(t.vertices).area for t in cs.traces]
    expected=metal[1]+2*cs.width*VOLUME['ground_thickness']+2*VOLUME['ground_thickness']*(cs.height+2*VOLUME['ground_thickness'])
    assert a[v.ground].sum()==pytest.approx(expected,rel=1e-12)
    assert a[v.layer_triangles['__sipi_metal_0']].sum()==pytest.approx(cs.width*cs.height-sum(metal),rel=1e-12)
    assert not np.intersect1d(v.layer_triangles['__sipi_metal_0'],v.signals['signal']).size
    # Magnetic-only partition must retain the identical metal areas.
    magnetic=mesh_conductor_section(cs,**VOLUME)
    assert areas(magnetic.mesh)[magnetic.ground].sum()==pytest.approx(expected,rel=1e-12)


def test_explicit_v3_rectangular_document_retains_version_and_rejects_hybrid_fields():
    base=CrossSection([Layer('d',2e-3,4)],[Trace('signal',0,.4e-3,1e-3,.1e-3)],4e-3)
    raw=CrossSectionDocument(base).to_dict()
    raw.update(schema='sipi.cross-section/3',dielectric_regions=[])
    raw['traces'][0].update(kind='trapezoid',top_width=.4e-3)
    assert CrossSectionDocument.from_dict(raw).to_dict()==raw
    raw['traces'][0]['vertices']=[[0,0],[1,0],[0,1]]
    with pytest.raises(ValueError): CrossSectionDocument.from_dict(raw)
