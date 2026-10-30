# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Reproducible shared-mesh material/conductor/network composition."""
import json

import numpy as np
import pytest
from sipi import CrossSection, CrossSectionDocument, coupled_microstrip, stripline
from sipi.conductor import surface_conductor_loss
from sipi.dielectric import WidebandDielectric, TabulatedDielectric, dispersive_line
from sipi.line_model import TransmissionLineDocument

F = np.array([1e9,4e9,10e9])
MESH = dict(edge_size=5e-6,far_size=.2e-3,grade=.1)
METAL = dict(kind='surface',conductivity=58e6,ground_thickness=35e-6,
             relative_permeability=1,roughness_rms=1e-6)


def section_doc():
    return CrossSectionDocument(coupled_microstrip(width=.5e-3,gap=.3e-3,
        substrate_height=1e-3,thickness=50e-6,eps_r=4),mesh=MESH)


def document(**changes):
    values = dict(cross_section=section_doc(),frequency=F,
                  materials={'substrate':WidebandDielectric(4,.02,1e9)},
                  conductor=METAL,length=.03,z_ref=50)
    values.update(changes)
    return TransmissionLineDocument(**values)


@pytest.fixture(scope='module')
def solved():
    doc = document()
    return doc,doc.analyze()


def test_roundtrip_reproduces_all_matrices_and_network(solved):
    doc, result = solved
    restored = TransmissionLineDocument.loads(doc.dumps())
    assert restored.to_dict() == doc.to_dict()
    rerun = restored.analyze()
    for name in ('R','L','G','C'):
        np.testing.assert_allclose(getattr(result,name),getattr(rerun,name),rtol=1e-12,atol=0)
        assert not getattr(result,name).flags.writeable
    np.testing.assert_allclose(result.network.s,rerun.network.s,rtol=0,atol=1e-10)
    assert result.input_json == doc.dumps()
    assert set(result.mesh_settings) == {'edge_size','far_size','grade','min_angle'}
    assert result.names == result.conductor.factors.names
    np.testing.assert_array_equal(result.dielectric.C0,result.conductor.factors.C0)


def test_shared_result_matches_individual_public_extraction_apis(solved):
    doc, result = solved
    section = doc.cross_section.section
    mesh = doc.cross_section.mesh_options
    dielectric = dispersive_line(section,F,materials={'substrate':WidebandDielectric(4,.02,1e9)},**mesh)
    metal = {k:v for k,v in METAL.items() if k != 'kind'}
    conductor = surface_conductor_loss(section,F,**metal,**mesh)
    np.testing.assert_allclose(result.R,conductor.R,rtol=1e-10,atol=0)
    np.testing.assert_allclose(result.L,dielectric.L+conductor.L_internal,rtol=1e-10,atol=0)
    np.testing.assert_allclose(result.C,dielectric.C,rtol=1e-10,atol=0)
    np.testing.assert_allclose(result.G,dielectric.G,rtol=1e-10,atol=0)
    independent_composition = conductor.network(C=dielectric.C,G=dielectric.G,length=.03)
    np.testing.assert_allclose(result.network.s,independent_composition.s,rtol=0,atol=1e-10)
    np.testing.assert_allclose(result.network.s,result.network.s.swapaxes(1,2),rtol=0,atol=1e-10)
    assert np.max(np.linalg.svd(result.network.s,compute_uv=False)) <= 1+1e-10


def test_only_one_mesh_is_built_for_both_extractions(monkeypatch):
    original = CrossSection.mesh
    calls = []
    def counted(self,**kwargs):
        calls.append(kwargs)
        return original(self,**kwargs)
    monkeypatch.setattr(CrossSection,'mesh',counted)
    result = document().analyze()
    assert len(calls) == 1
    assert calls[0] == dict(result.mesh_settings)


def test_perfect_metal_scalar_against_independent_abcd_and_dc():
    cs = CrossSectionDocument(stripline(width=.5e-3,plane_spacing=1e-3,eps_r=4),mesh=MESH)
    doc = document(cross_section=cs,frequency=[0,1e7,1e9],materials={},
                   conductor={'kind':'perfect'},length=.017)
    result = doc.analyze()
    assert result.conductor is None
    np.testing.assert_array_equal(result.R,np.zeros_like(result.R))
    np.testing.assert_array_equal(result.G,np.zeros_like(result.G))
    np.testing.assert_allclose(result.network.s[0],[[0,1],[1,0]],atol=1e-10)
    f = result.frequency[1:]
    l,c = result.L[1:,0,0],result.C[1:,0,0]
    gamma = 2j*np.pi*f*np.sqrt(l*c)
    z = np.sqrt(l/c)
    a,b,cc = np.cosh(gamma*.017),z*np.sinh(gamma*.017),np.sinh(gamma*.017)/z
    den = 2*a+b/50+cc*50
    np.testing.assert_allclose(result.network.s[1:,1,0],2/den,rtol=0,atol=1e-10)
    np.testing.assert_allclose(result.network.s[1:,0,0],(b/50-cc*50)/den,rtol=0,atol=1e-10)


def test_input_snapshot_and_resolved_mesh_are_isolated():
    frequencies,metal = F.copy(),METAL.copy()
    doc = document(frequency=frequencies,conductor=metal)
    text = doc.dumps()
    frequencies[0] = 0
    metal['conductivity'] = 0
    raw = doc.to_dict()
    raw['cross_section']['traces'][0]['width'] = 0
    raw['materials']['substrate']['parameters']['eps_ref'] = 999
    assert doc.dumps() == text
    assert doc.cross_section.mesh_options == dict(MESH,min_angle=28)
    # Omitted geometry settings resolve into numeric saved fields too.
    automatic = document(cross_section=CrossSectionDocument(section_doc().section))
    assert set(automatic.to_dict()['cross_section']['mesh']) == {'edge_size','far_size','grade','min_angle'}


@pytest.mark.parametrize('mutate',[
    lambda d:d.update(schema='sipi.transmission-line/2'),
    lambda d:d.update(units='mm'),
    lambda d:d.pop('conductor'),
    lambda d:d.update(conductor={'kind':'perfect','conductivity':58e6}),
    lambda d:d['conductor'].pop('roughness_rms'),
    lambda d:d['conductor'].update(kind='automatic'),
    lambda d:d['conductor'].update(ground_thickness=1e-10),
    lambda d:d.update(frequency_hz=[0,1e9]),
    lambda d:d.update(frequency_hz=[1e9,1e9]),
    lambda d:d.update(frequency_hz=[True,1e9]),
    lambda d:d.update(length_m=-1),
    lambda d:d.update(reference_ohms=0),
    lambda d:d['materials'].update(missing=d['materials']['substrate']),
    lambda d:d['materials']['substrate'].update(schema='sipi.dielectric/999'),
    lambda d:d['cross_section'].update(length_unit='mm'),
])
def test_invalid_document_is_rejected_before_meshing(monkeypatch,mutate):
    raw = document().to_dict()
    def forbidden(*args,**kwargs):
        pytest.fail('invalid document reached meshing')
    monkeypatch.setattr(CrossSection,'mesh',forbidden)
    mutate(raw)
    with pytest.raises(ValueError):
        TransmissionLineDocument.from_dict(raw)


def test_tables_are_preflighted_and_metal_choice_is_mandatory(monkeypatch):
    def forbidden(*args,**kwargs):
        pytest.fail('invalid document reached meshing')
    monkeypatch.setattr(CrossSection,'mesh',forbidden)
    with pytest.raises(ValueError,match='extrapolation'):
        document(materials={'substrate':TabulatedDielectric([1e9,4e9],[4,3],[.01,.02])})
    with pytest.raises(TypeError):
        TransmissionLineDocument(section_doc(),F,materials={},length=.03)


def test_duplicate_nonfinite_and_nonobject_json_are_rejected():
    text = document().dumps()
    for raw in ('[]','null',text.replace('"length_m": 0.03','"length_m": NaN'),
                text.replace('"length_m": 0.03','"length_m": 0.03, "length_m": 0.02'),
                text.replace('"conductivity": 58000000.0','"conductivity": 1, "conductivity": 2')):
        with pytest.raises(ValueError):
            TransmissionLineDocument.loads(raw)
    assert json.loads(text)['schema'] == 'sipi.transmission-line/1'


def test_tapered_geometry_json_v2_preserved():
    raw = section_doc().to_dict()
    raw['schema'] = 'sipi.cross-section/2'
    for trace in raw['traces']:
        trace['top_width'] = trace['width']*.8
    doc = document(cross_section=CrossSectionDocument.from_dict(raw))
    restored = TransmissionLineDocument.loads(doc.dumps())
    assert restored.cross_section.to_dict()['schema'] == 'sipi.cross-section/2'
    assert restored.cross_section.section.traces[0].top_width == .4e-3


def test_explicit_rectangular_v2_does_not_silently_change_schema():
    raw = section_doc().to_dict()
    raw['schema'] = 'sipi.cross-section/2'
    for trace in raw['traces']:
        trace['top_width'] = trace['width']
    doc = document(cross_section=CrossSectionDocument.from_dict(raw))
    saved = doc.to_dict()['cross_section']
    assert saved['schema'] == 'sipi.cross-section/2'
    assert saved['traces'] == raw['traces']
