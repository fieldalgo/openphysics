# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Saved circuit inputs, analytical DC and composition of existing engines."""
import json

import numpy as np
import pytest

from sipi import CrossSectionDocument, LineNetwork, microstrip
from sipi.circuit_document import CircuitDocument
from sipi.line_model import TransmissionLineDocument
from sipi.termination import loaded_crosstalk, terminate_network
from sipi.volume_line import VolumeLineDocument


def rlgc():
    return dict(schema='sipi.circuit/1',
        network=dict(kind='rlgc', frequency_hz=[0, 1e6, 1e9], R=[[10]], L=[[400e-9]],
                     G=[[0]], C=[[100e-12]], length_m=1, reference_ohms=50, names=['signal']),
        excitation=dict(kind='sources', voltages={'near:signal': 1}),
        terminations={'near:signal': 50, 'far:signal': 100})


def test_rlgc_roundtrip_and_dc_analytic():
    original = CircuitDocument.from_dict(rlgc())
    restored = CircuitDocument.loads(original.dumps())
    assert restored.dumps() == original.dumps()
    out = restored.analyze()
    assert out.input_json == restored.dumps()
    assert out.extraction is None and out.crosstalk is None
    np.testing.assert_allclose(out.response.voltage[0], [110/160, 100/160], rtol=1e-10)
    np.testing.assert_allclose(out.response.current[0], [1/160, -1/160], rtol=1e-10)
    np.testing.assert_allclose(out.response.network_power[0], 10/160**2, rtol=1e-10)


def test_nonreciprocal_touchstone_crosstalk_and_complex_loads():
    s = np.arange(1, 33).reshape(2, 4, 4)/100+0.01j
    net = LineNetwork([1e6, 1e9], s, [25, 50, 75, 100], ('a', 'n', 'through', 'f'))
    doc = CircuitDocument(dict(kind='touchstone', text=net.touchstone(), ports=4,
                              port_names=list(net.port_names)),
        excitation=dict(kind='crosstalk', aggressor='a', near_victim='n', far_victim='f'),
        terminations={'a': {'real': [25, 30], 'imag': [10, -10]}, 'f': 125})
    out = CircuitDocument.loads(doc.dumps()).analyze()
    direct = loaded_crosstalk(net, aggressor='a', near_victim='n', far_victim='f',
                             terminations={'a': [25+10j, 30-10j], 'f': 125})
    np.testing.assert_allclose(out.network.s, net.s, rtol=0, atol=1e-12)
    np.testing.assert_allclose(out.crosstalk.next_ratio, direct.next_ratio, rtol=0, atol=1e-12)
    np.testing.assert_allclose(out.crosstalk.fext_ratio, direct.fext_ratio, rtol=0, atol=1e-12)
    np.testing.assert_allclose(out.response.current, direct.response.current, rtol=1e-10)
    assert out.response is out.crosstalk.response


def test_frequency_array_complex_sources():
    data = rlgc()
    data['excitation']['voltages'] = {'near:signal': {'real': [1, 2, 3], 'imag': [0, 1, -1]},
                                    'far:signal': {'real': 0, 'imag': .25}}
    result = CircuitDocument.from_dict(data).analyze()
    np.testing.assert_array_equal(result.response.source_voltages[:, 0], [1, 2+1j, 3-1j])
    np.testing.assert_array_equal(result.response.source_voltages[:, 1], [.25j]*3)


@pytest.mark.parametrize('kind', ['transmission-line', 'volume-line'])
def test_nested_geometry_model_preserved_and_direct_composition(kind):
    section = microstrip(width=.4e-3, substrate_height=.5e-3, thickness=.1e-3,
                         eps_r=4, tan_delta=.02, air_height=.5e-3, box_width=2e-3)
    cross = CrossSectionDocument(section)
    if kind == 'transmission-line':
        nested = TransmissionLineDocument(cross, [0, 1e3], materials={},
                                           conductor={'kind': 'perfect'}, length=.1)
    else:
        nested = VolumeLineDocument(cross, [0, 1e3], materials={}, conductivity=58e6, length=.1,
            mesh=dict(ground_thickness=.1e-3, padding=2e-3, metal_size=50e-6,
                      far_size=.5e-3, grade=.2, min_angle=28))
    names = ['near:'+section.traces[0].name, 'far:'+section.traces[0].name]
    doc = CircuitDocument(dict(kind=kind, document=nested.to_dict()),
        excitation=dict(kind='sources', voltages={names[0]: 1}), terminations={names[1]: 100})
    restored = CircuitDocument.loads(doc.dumps())
    assert restored.to_dict()['network']['document'] == nested.to_dict()
    out = restored.analyze()
    direct = nested.analyze()
    response = terminate_network(direct.network, source_voltages={names[0]: 1},
                                 terminations={names[1]: 100})
    assert out.extraction is not None
    np.testing.assert_allclose(out.network.s, direct.network.s, rtol=0, atol=1e-12)
    np.testing.assert_allclose(out.response.voltage, response.voltage, rtol=1e-10)
    np.testing.assert_allclose(out.response.current, response.current, rtol=1e-10)


def test_no_mesh_before_bad_port_rejection(monkeypatch):
    cross = CrossSectionDocument(microstrip(width=.4e-3, substrate_height=.5e-3, eps_r=4))
    nested = TransmissionLineDocument(cross, [1e3], materials={}, conductor={'kind': 'perfect'}, length=.1)
    def forbidden(*args, **kwargs):
        pytest.fail('invalid port reached a mesh/solve')
    monkeypatch.setattr(TransmissionLineDocument, 'analyze', forbidden)
    with pytest.raises(ValueError, match='unknown network port'):
        CircuitDocument(dict(kind='transmission-line', document=nested.to_dict()),
            excitation=dict(kind='sources', voltages={'wrong': 1}), terminations={})


@pytest.mark.parametrize('value', [True, '1', None, float('inf'), complex(1, 2), [1, 2],
    [1, True, 2], [[1], [2], [3]], {'real': 1}, {'real': 1, 'imag': None}, {'real': 1, 'imag': 0, 'extra': 1},
    {'real': 1, 'imag': [0, 0, 0]}, {'real': [1, 1, 1], 'imag': [0, False, 0]}])
def test_reject_invalid_complex_inputs(value):
    data = rlgc()
    data['excitation']['voltages']['near:signal'] = value
    with pytest.raises(ValueError):
        CircuitDocument.from_dict(data)


@pytest.mark.parametrize('edit', [
    lambda d: d.update(schema='sipi.circuit/2'),
    lambda d: d.update(extra=True),
    lambda d: d['network'].update(kind='url'),
    lambda d: d['network'].update(R=[[True]]),
    lambda d: d['network'].update(names=None),
    lambda d: d['network'].update(names='signal'),
    lambda d: d['network'].update(extra=0),
    lambda d: d.update(excitation={}),
    lambda d: d['excitation'].update(voltages={}),
    lambda d: d['excitation'].update(voltages={'wrong': 1}),
    lambda d: d['excitation'].update(extra=True),
    lambda d: d.update(terminations=[]),
    lambda d: d.update(terminations={'wrong': 50}),
    lambda d: d.update(terminations={'far:signal': -1}),
    lambda d: d.update(terminations={'far:signal': {'real': -1, 'imag': 3}}),
    lambda d: d.update(excitation=dict(kind='crosstalk', aggressor='near:signal',
                                      near_victim='near:signal', far_victim='far:signal')),
])
def test_reject_invalid_contract(edit):
    data = rlgc()
    edit(data)
    with pytest.raises(ValueError):
        CircuitDocument.from_dict(data)


@pytest.mark.parametrize('text', ['{"schema":"sipi.circuit/1","schema":"sipi.circuit/1"}',
                                  '{"network":{"kind":"rlgc","kind":"rlgc"}}',
                                  '{"x":NaN}', '{"x":Infinity}', '{"x":-Infinity}'])
def test_duplicate_and_nonfinite_json_rejected(text):
    with pytest.raises(ValueError):
        CircuitDocument.loads(text)


def test_constructor_and_accessors_isolate_inputs():
    data = rlgc()
    doc = CircuitDocument.from_dict(data)
    before = doc.dumps()
    data['network']['R'][0][0] = 99
    copy_out = doc.to_dict()
    copy_out['excitation']['voltages']['near:signal']['real'] = 99
    assert doc.dumps() == before
    assert json.loads(before)['network']['R'] == [[10]]


def test_nested_skin_depth_failure_preserved():
    cross = CrossSectionDocument(microstrip(width=.4e-3, substrate_height=.5e-3,
        thickness=.1e-3, eps_r=4, air_height=.5e-3, box_width=2e-3))
    nested = VolumeLineDocument(cross, [1e12], materials={}, conductivity=58e6, length=.1,
        mesh=dict(ground_thickness=.1e-3, padding=2e-3, metal_size=50e-6,
                  far_size=.5e-3, grade=.2, min_angle=28))
    name = 'near:'+cross.section.traces[0].name
    doc = CircuitDocument(dict(kind='volume-line', document=nested.to_dict()),
                           excitation=dict(kind='sources', voltages={name: 1}), terminations={})
    with pytest.raises(ValueError, match='skin'):
        doc.analyze()


def test_numeric_keys_are_not_silently_relabelled():
    data = rlgc()
    data['network']['names'] = ['0']
    data['excitation']['voltages'] = {0: 1}
    with pytest.raises(ValueError, match='finite JSON'):
        CircuitDocument.from_dict(data)


@pytest.mark.parametrize('ports,names', [(None, ['a', 'b']), (True, ['a']),
                                        (2, None), (3, ['a', 'b'])])
def test_touchstone_requires_explicit_port_count_and_names(ports, names):
    net = LineNetwork([1e6], [[[0, .5], [.5, 0]]], 50, ('a', 'b'))
    with pytest.raises(ValueError):
        CircuitDocument(dict(kind='touchstone', text=net.touchstone(), ports=ports, port_names=names),
                           excitation=dict(kind='sources', voltages={'a': 1}), terminations={})
