# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Exact tapered geometry, rectangular limits, mesh and material contracts."""
import os
import numpy as np
import pytest
from scipy.constants import epsilon_0
from sipi import CrossSection, CrossSectionDocument, Layer, Trace, microstrip, stripline
from sipi.templates import coated_microstrip

MESH = dict(edge_size=5e-6, far_size=.25e-3, grade=.15)


def section(bottom=.6e-3, top=.3e-3):
    return CrossSection([Layer('dielectric', 2e-3, 4)],
        [Trace('signal', 0, bottom, .8e-3, .4e-3, top_width=top)], 6e-3, top='ground')


def test_rectangular_limit_preserves_exact_mesh_and_parameters():
    plain = stripline(width=.6e-3, plane_spacing=2e-3, eps_r=4, thickness=.4e-3, box_width=6e-3)
    explicit = section(.6e-3, .6e-3)
    a, b = plain.mesh(**MESH), explicit.mesh(**MESH)
    np.testing.assert_array_equal(a.mesh.nodes, b.mesh.nodes)
    np.testing.assert_array_equal(a.mesh.triangles, b.mesh.triangles)
    np.testing.assert_array_equal(a.line_parameters().C, b.line_parameters().C)
    assert CrossSectionDocument(explicit).to_dict()['schema'] == 'sipi.cross-section/1'


def test_exact_hole_area_interface_materials_and_boundary_nodes():
    cs = CrossSection([Layer('lower', 1e-3, 4), Layer('upper', 1e-3, 6)],
        [Trace('signal', 0, .6e-3, .8e-3, .4e-3, top_width=.3e-3)], 4e-3, top='ground')
    m = cs.mesh(**MESH)
    points = m.mesh.nodes[m.mesh.triangles]
    a, b = points[:, 1]-points[:, 0], points[:, 2]-points[:, 0]
    area = np.abs(a[:, 0]*b[:, 1]-a[:, 1]*b[:, 0])/2
    expected = cs.width*cs.height-(.6e-3+.3e-3)*.4e-3/2
    assert area.sum() == pytest.approx(expected, rel=1e-12)
    centres = points.mean(axis=1)
    trace = cs.traces[0]
    assert not np.any((centres[:, 1] > trace.y) & (centres[:, 1] < trace.y1)
                      & (abs(centres[:, 0]) < trace.width_at(centres[:, 1])/2))
    np.testing.assert_array_equal(m.eps_r, np.where(centres[:, 1] < 1e-3, 4, 6))
    # No triangle straddles the material interface except for its boundary vertices.
    assert not np.any((points[:, :, 1].min(axis=1) < 1e-3-1e-12)
                      & (points[:, :, 1].max(axis=1) > 1e-3+1e-12))
    boundary = m.mesh.nodes[m.signals['signal']]
    assert len(boundary) > 4
    np.testing.assert_allclose(trace.distance(boundary[:, 0], boundary[:, 1]), 0, atol=1e-12)


def test_tapered_distance_and_nonoverlapping_bounding_boxes():
    a = Trace('a', 0, 1, 1, 1, top_width=.2)
    np.testing.assert_allclose(a.distance([0, 0, .6], [1.5, .5, 1]), [0, .5, .1])
    b = Trace('b', .75, .2, 1, 1, top_width=1)
    CrossSection([Layer('d', 3, 4)], [a,b], 4, top='ground')
    with pytest.raises(ValueError, match='overlap'):
        CrossSection([Layer('d', 3, 4)], [a, Trace('b', .55, .2, 1, 1, top_width=1)], 4)
    with pytest.raises(ValueError, match='side walls'):
        CrossSection([Layer('d', 3, 4)], [Trace('s', 0, .1, 1, 1, top_width=4)], 4)


@pytest.mark.parametrize('value', [0, -1, float('nan'), float('inf'), True, '0.1'])
def test_invalid_top_width(value):
    with pytest.raises(ValueError):
        Trace('s', 0, .5, 1, .1, top_width=value)


def test_zero_thickness_taper_is_rejected():
    with pytest.raises(ValueError, match='zero-thickness'):
        Trace('s', 0, .5, 1, top_width=.4)


def test_v2_roundtrip_is_strict_and_v1_unchanged():
    doc = CrossSectionDocument(section(), mesh=MESH)
    raw = doc.to_dict()
    assert raw['schema'] == 'sipi.cross-section/2'
    restored = CrossSectionDocument.loads(doc.dumps())
    assert restored.to_dict() == raw
    np.testing.assert_array_equal(doc.analyze().C, restored.analyze().C)
    assert restored.section.traces[0].top_width == .3e-3
    raw['schema'] = 'sipi.cross-section/1'
    with pytest.raises(ValueError, match='unknown'):
        CrossSectionDocument.from_dict(raw)
    raw['schema'] = 'sipi.cross-section/2'
    del raw['traces'][0]['top_width']
    with pytest.raises(ValueError, match='missing'):
        CrossSectionDocument.from_dict(raw)


def test_reflection_convergence_homogeneous_limit_and_capacitance_bounds():
    fine = {**MESH, 'edge_size':MESH['edge_size']/2,
             'far_size':MESH['far_size']/2, 'grade':MESH['grade']/2}
    coarse = section().analyze(**MESH)
    refined = section().analyze(**fine)
    reflected = section(.3e-3, .6e-3).analyze(**fine)
    print({"coarse_z0":coarse.z0,"refined_z0":refined.z0,"reflection_z0":reflected.z0})
    assert abs(coarse.z0/refined.z0-1) <= .005
    assert abs(reflected.z0/refined.z0-1) <= .005
    np.testing.assert_allclose(refined.C/refined.C0, 4, rtol=1e-9)
    narrow, wide = section(.3e-3, .3e-3).analyze(**fine), section(.6e-3, .6e-3).analyze(**fine)
    assert narrow.C[0, 0] < refined.C[0, 0] < wide.C[0, 0]


def test_coating_limit_and_capacitance_increase():
    kw=dict(width=.6e-3, substrate_height=1e-3, eps_r=4, thickness=.1e-3,
            top_width=.4e-3, coating_height=.2e-3, air_height=2e-3, box_width=6e-3)
    air = coated_microstrip(**kw, coating_eps_r=1).analyze(**MESH)
    coated = coated_microstrip(**kw, coating_eps_r=3.5).analyze(**MESH)
    uncoated = microstrip(width=kw['width'],substrate_height=kw['substrate_height'],eps_r=4,
                          thickness=kw['thickness'],top_width=kw['top_width'],
                          air_height=2.2e-3,box_width=6e-3).analyze(**MESH)
    print({"air_coating_z0":air.z0,"uncoated_z0":uncoated.z0,"coated_z0":coated.z0})
    assert abs(air.z0/uncoated.z0-1) <= .005
    assert coated.C[0, 0] > air.C[0, 0]
    assert coated.z0 < air.z0
    with pytest.raises(ValueError, match='exceed'):
        coated_microstrip(**{**kw,'coating_height':.1e-3},coating_eps_r=3)


def test_taper_and_thin_signal_share_layered_domain():
    cs=CrossSection([Layer('d', 2e-3, 4)],
        [Trace('taper',-.5e-3,.5e-3,.8e-3,.3e-3,top_width=.3e-3),
         Trace('thin',.5e-3,.3e-3,1e-3)],4e-3,top='ground')
    mesh=cs.mesh(**MESH)
    thin=mesh.mesh.nodes[mesh.signals['thin']]
    assert len(thin) > 2
    np.testing.assert_allclose(thin[:,1],1e-3,atol=1e-12)
    p=mesh.line_parameters()
    assert p.C[0,1]<0 and np.all(np.linalg.eigvalsh(p.C)>0)


def test_independent_skfem_same_mesh_capacitance():
    if os.environ.get('OPENPHYSICS_REQUIRE_CROSSCHECK') == '1':
        import skfem
    else:
        skfem = pytest.importorskip('skfem')
    from skfem.helpers import dot, grad
    # Two asymmetric tapered conductors, interface inside their thickness.
    cs=CrossSection([Layer('a',1e-3,4,.01),Layer('b',1e-3,6,.03)],
        [Trace('p',-.5e-3,.6e-3,.8e-3,.4e-3,top_width=.3e-3),
         Trace('n',.5e-3,.4e-3,.8e-3,.4e-3,top_width=.6e-3)],4e-3,top='ground')
    m=cs.mesh(**MESH)
    basis=skfem.Basis(skfem.MeshTri(m.mesh.nodes.T,m.mesh.triangles.T),skfem.ElementTriP1())
    @skfem.BilinearForm(dtype=np.complex128)
    def form(u,v,w):
        return w.eps*dot(grad(u),grad(v))
    k=skfem.asm(form,basis,eps=(m.eps_r*(1-1j*m.tan_delta))[:,None])
    fixed=np.unique(np.concatenate([m.ground,*m.signals.values()]))
    potentials=[]
    for signal in m.signals.values():
        boundary=np.zeros(basis.N,dtype=complex);boundary[signal]=1
        potentials.append(skfem.solve(*skfem.condense(k,np.zeros(basis.N,dtype=complex),x=boundary,D=fixed)))
    v=np.stack(potentials,axis=1)
    reference=epsilon_0*(v.T@(k@v))
    line=m.line_parameters()
    observed=line.C-1j*line.C_loss
    error = float(np.max(abs(observed-reference))/np.max(abs(reference)))
    print({"scikit_fem_version":skfem.__version__,"C_relative_difference":error})
    assert error <= 1e-9
