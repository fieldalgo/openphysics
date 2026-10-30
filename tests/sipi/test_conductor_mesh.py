# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Finite reference plates, exact polygon areas and magnetic-domain convergence."""
import numpy as np
import pytest
from sipi import CrossSection,Layer,Trace,microstrip,stripline,grounded_coplanar
from sipi.conductor_mesh import mesh_conductor_section

OPTIONS = dict(ground_thickness=.1e-3,padding=2e-3,metal_size=50e-6,far_size=.5e-3,grade=.2)
SIGMA = 58e6


def section():
    return microstrip(width=.4e-3,substrate_height=.5e-3,thickness=.1e-3,
                      eps_r=4,air_height=.5e-3,box_width=2e-3)


def areas(volume):
    p = volume.mesh.nodes[volume.mesh.triangles]
    a,b = p[:,1]-p[:,0],p[:,2]-p[:,0]
    return (a[:,0]*b[:,1]-a[:,1]*b[:,0])/2


@pytest.mark.parametrize('kind',['surface','taper','stripline','closed','coplanar'])
def test_exact_trace_and_ground_areas_and_dc_resistance(kind):
    cs = section()
    if kind == 'taper':
        cs = microstrip(width=.4e-3,top_width=.2e-3,substrate_height=.5e-3,
            thickness=.1e-3,eps_r=4,air_height=.5e-3,box_width=2e-3)
    if kind == 'stripline':
        cs = stripline(width=.4e-3,plane_spacing=1e-3,thickness=.1e-3,eps_r=4,box_width=2e-3)
    if kind == 'closed':
        cs = CrossSection([Layer('dielectric',1e-3,4)],
            [Trace('signal',0,.4e-3,.45e-3,.1e-3)],2e-3,top='ground',sides='ground')
    if kind == 'coplanar':
        cs = grounded_coplanar(width=.4e-3,gap=.2e-3,ground_width=.3e-3,
            substrate_height=.5e-3,thickness=.1e-3,eps_r=4,air_height=.5e-3,box_width=2e-3)
    volume = mesh_conductor_section(cs,**OPTIONS)
    a = areas(volume)
    metal = lambda t:(t.width+(t.top_width or t.width))*t.thickness/2
    signal_areas = [metal(t) for t in cs.traces if not t.ground]
    thickness = OPTIONS['ground_thickness']
    nplates = int(cs.bottom == 'ground')+int(cs.top == 'ground')
    expected_ground = cs.width*thickness*nplates+sum(metal(t) for t in cs.traces if t.ground)
    if cs.sides == 'ground':
        expected_ground += 2*thickness*(cs.height+thickness*nplates)
    assert a[volume.ground].sum() == pytest.approx(expected_ground,rel=1e-10)
    for ids,expected in zip(volume.signals.values(),signal_areas):
        assert a[ids].sum() == pytest.approx(expected,rel=1e-10)
        assert not np.intersect1d(ids,volume.ground).size
    rdc = np.diag(1/(SIGMA*np.array(signal_areas)))+1/(SIGMA*expected_ground)
    result = volume.impedance([0],conductivity=SIGMA)
    np.testing.assert_allclose(result.R[0],rdc,rtol=1e-10,atol=0)
    assert result.power_error[0] < 1e-9
    assert tuple(volume.signals) == tuple(t.name for t in cs.traces if not t.ground)


def test_microstrip_rl_refinement_and_padding_are_separate():
    coarse = mesh_conductor_section(section(),**OPTIONS).impedance([0,1e5],conductivity=SIGMA)
    refined_options = dict(OPTIONS,metal_size=25e-6,far_size=.25e-3,grade=.1)
    fine = mesh_conductor_section(section(),**refined_options).impedance([0,1e5],conductivity=SIGMA)
    for name in ('R','L'):
        a,b = getattr(coarse,name),getattr(fine,name)
        assert np.max(abs(a-b))/np.max(abs(b)) < .01
    enlarged = mesh_conductor_section(section(),**dict(refined_options,padding=4e-3)).impedance([0,1e5],conductivity=SIGMA)
    assert np.max(abs(enlarged.L-fine.L))/np.max(abs(enlarged.L)) < .02


@pytest.mark.parametrize('change',[dict(ground_thickness=0),dict(padding=-1),
    dict(metal_size=True),dict(metal_size=1e-3),dict(far_size=float('nan')),
    dict(grade=-1),dict(min_angle=34)])
def test_invalid_mesh_inputs_are_rejected_before_generate(monkeypatch,change):
    import sipi.conductor_mesh as implementation
    def forbidden(*a,**k):
        pytest.fail('invalid volume mesh inputs reached generate')
    monkeypatch.setattr(implementation,'generate',forbidden)
    with pytest.raises(ValueError):
        mesh_conductor_section(section(),**dict(OPTIONS,**change))


def test_zero_thickness_strip_is_not_a_metal_volume(monkeypatch):
    import sipi.conductor_mesh as implementation
    def forbidden(*a,**k):
        pytest.fail('zero-thickness strip reached generate')
    monkeypatch.setattr(implementation,'generate',forbidden)
    cs = microstrip(width=.4e-3,substrate_height=.5e-3,eps_r=4)
    with pytest.raises(ValueError,match='finite-thickness'):
        mesh_conductor_section(cs,**OPTIONS)


def test_volume_mesh_is_independent_of_dielectric_permittivity():
    a = mesh_conductor_section(section(),**OPTIONS)
    cs = microstrip(width=.4e-3,substrate_height=.5e-3,thickness=.1e-3,
                   eps_r=8,air_height=.5e-3,box_width=2e-3)
    b = mesh_conductor_section(cs,**OPTIONS)
    np.testing.assert_array_equal(a.mesh.nodes,b.mesh.nodes)
    np.testing.assert_array_equal(a.mesh.triangles,b.mesh.triangles)
