# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Versioned, self-contained inputs from line extraction to terminal response.

No file I/O, implicit port mapping, network access or executable expressions.
Existing extraction and termination validity checks remain in force.
"""
from __future__ import annotations

from dataclasses import dataclass
import json

import numpy as np

from .document import _keys, _unique_object
from .network import LineNetwork, rlgc_network
from .termination import Crosstalk, TerminatedNetwork, loaded_crosstalk, terminate_network
from .touchstone import loads_touchstone

__all__ = ['CircuitDocument', 'CircuitResult']


def _json_copy(value):
    try:
        text = json.dumps(value, allow_nan=False)
        def check_keys(item):
            if isinstance(item, dict):
                if any(not isinstance(key, str) for key in item):
                    raise ValueError('JSON object keys must be strings')
                for child in item.values():
                    check_keys(child)
            elif isinstance(item, (list, tuple)):
                for child in item:
                    check_keys(child)
        check_keys(value)
        return json.loads(text)
    except (TypeError, ValueError) as exc:
        raise ValueError('circuit input must contain only finite JSON values') from exc


def _network_input(data):
    if not isinstance(data, dict):
        raise ValueError('network must be an object')
    kind = data.get('kind')
    if kind == 'rlgc':
        _keys(data, ('kind', 'frequency_hz', 'R', 'L', 'G', 'C', 'length_m',
                     'reference_ohms', 'names'), where='RLGC network')
        if not isinstance(data['names'], list):
            raise ValueError('RLGC names must be an explicit array')
        net = rlgc_network(data['frequency_hz'], R=data['R'], L=data['L'],
                           G=data['G'], C=data['C'], length=data['length_m'],
                           z_ref=data['reference_ohms'], names=data['names'])
        return net, data, net.frequency, net.port_names
    if kind == 'touchstone':
        _keys(data, ('kind', 'text', 'ports', 'port_names'), where='Touchstone network')
        if not isinstance(data['port_names'], list):
            raise ValueError('Touchstone port_names must be an explicit array')
        if (type(data['ports']) is not int or data['ports'] <= 0
                or len(data['port_names']) != data['ports']):
            raise ValueError('Touchstone ports must match the explicit names count')
        net = loads_touchstone(data['text'], ports=data['ports'], port_names=data['port_names'])
        return net, data, net.frequency, net.port_names
    if kind in ('transmission-line', 'volume-line'):
        _keys(data, ('kind', 'document'), where='line extraction network')
        if kind == 'transmission-line':
            from .line_model import TransmissionLineDocument
            doc = TransmissionLineDocument.from_dict(data['document'])
        else:
            from .volume_line import VolumeLineDocument
            doc = VolumeLineDocument.from_dict(data['document'])
        canonical = doc.to_dict()
        names = tuple(t.name for t in doc.cross_section.section.traces if not t.ground)
        ports = tuple('near:'+name for name in names) + tuple('far:'+name for name in names)
        return doc, dict(kind=kind, document=canonical), np.array(canonical['frequency_hz']), ports
    raise ValueError('unsupported network kind')


def _complex_value(value, count):
    explicit_complex = isinstance(value, dict)
    if explicit_complex:
        _keys(value, ('real', 'imag'), where='complex value')
        real, imag = value['real'], value['imag']
    else:
        real, imag = value, None
    def component(x):
        raw = np.asarray(x)
        if (raw.dtype.kind not in 'iuf' or not np.all(np.isfinite(raw))
                or any(isinstance(v, (bool, np.bool_)) for v in np.asarray(x, dtype=object).flat)
                or (raw.ndim != 0 and raw.shape != (count,))):
            raise ValueError('complex components need finite real scalars or frequency arrays')
        return np.array(raw, dtype=float)
    re = component(real)
    im = component(imag) if explicit_complex else np.zeros_like(re)
    if im.shape != re.shape:
        raise ValueError('real and imag must have the same shape')
    return re+1j*im, dict(real=re.tolist(), imag=im.tolist())


def _table(data, frequency, ports, *, passive=False):
    if not isinstance(data, dict):
        raise ValueError('source/load values must be objects keyed by port names')
    decoded, canonical = {}, {}
    for name, value in data.items():
        if name not in ports:
            raise ValueError(f'unknown network port: {name!r}')
        number, encoded = _complex_value(value, len(frequency))
        if passive and np.any(number.real < 0):
            raise ValueError('terminations require real part >= 0')
        decoded[name], canonical[name] = number, encoded
    return decoded, canonical


@dataclass(frozen=True)
class CircuitResult:
    """Circuit output with exact canonical input and optional line extraction.

    ``crosstalk`` is present only for a crosstalk excitation. ``extraction`` is
    the existing line result for a geometry-backed input, otherwise None.
    """
    input_json: str
    response: TerminatedNetwork
    crosstalk: Crosstalk | None
    extraction: object | None

    @property
    def network(self):
        return self.response.network


class CircuitDocument:
    """Strict sipi.circuit/1 input snapshot; SI units and peak phasors.

    Build from JSON-compatible dictionaries; complex numbers use {real,imag}.
    Construction validates all port names and counts without creating a mesh.
    Analyze keeps the nested model's mesh, material and skin-depth gates.
    """
    def __init__(self, network, *, excitation, terminations):
        self._data = self._validate(dict(schema='sipi.circuit/1', network=network,
                                         excitation=excitation, terminations=terminations))

    @staticmethod
    def _validate(data):
        # Copies before checking; callers cannot mutate nested documents afterward.
        data = _json_copy(data)
        _keys(data, ('schema', 'network', 'excitation', 'terminations'), where='circuit')
        if data['schema'] != 'sipi.circuit/1':
            raise ValueError('unsupported circuit schema')
        _, network, frequency, ports = _network_input(data['network'])
        excitation = data['excitation']
        if not isinstance(excitation, dict):
            raise ValueError('excitation must be an object')
        if excitation.get('kind') == 'sources':
            _keys(excitation, ('kind', 'voltages'), where='source excitation')
            decoded, canonical = _table(excitation['voltages'], frequency, ports)
            if not decoded:
                raise ValueError('sources excitation needs at least one named voltage')
            excitation = dict(kind='sources', voltages=canonical)
        elif excitation.get('kind') == 'crosstalk':
            keys = ('aggressor', 'near_victim', 'far_victim')
            _keys(excitation, ('kind', *keys), where='crosstalk excitation')
            names = [excitation[k] for k in keys]
            if (any(not isinstance(name, str) or name not in ports for name in names)
                    or len(set(names)) != 3):
                raise ValueError('crosstalk needs three distinct named network ports')
        else:
            raise ValueError('unsupported excitation kind')
        _, terminations = _table(data['terminations'], frequency, ports, passive=True)
        return dict(schema='sipi.circuit/1', network=network,
                    excitation=excitation, terminations=terminations)

    @classmethod
    def from_dict(cls, data):
        out = cls.__new__(cls)
        out._data = cls._validate(data)
        return out

    @classmethod
    def loads(cls, text):
        def reject(value):
            raise ValueError(f'nonfinite JSON number: {value}')
        return cls.from_dict(json.loads(text, object_pairs_hook=_unique_object, parse_constant=reject))

    def dumps(self):
        return json.dumps(self._data, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False)

    def to_dict(self):
        return json.loads(self.dumps())

    def analyze(self):
        data = self.to_dict()
        source, _, frequency, ports = _network_input(data['network'])
        extraction = None if isinstance(source, LineNetwork) else source.analyze()
        network = source if extraction is None else extraction.network
        if tuple(network.port_names) != ports or not np.array_equal(network.frequency, frequency):
            raise ValueError('extraction changed the documented frequency or port order')
        terminations, _ = _table(data['terminations'], frequency, ports, passive=True)
        excitation = data['excitation']
        crosstalk = None
        if excitation['kind'] == 'sources':
            voltages, _ = _table(excitation['voltages'], frequency, ports)
            response = terminate_network(network, source_voltages=voltages, terminations=terminations)
        else:
            crosstalk = loaded_crosstalk(network, aggressor=excitation['aggressor'],
                near_victim=excitation['near_victim'], far_victim=excitation['far_victim'],
                terminations=terminations)
            response = crosstalk.response
        return CircuitResult(self.dumps(), response, crosstalk, extraction)
