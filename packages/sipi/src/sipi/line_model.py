# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""One reproducible input for geometry, materials, RLGC and uniform-line S.

The constitutive models keep their own validity limits. A document is not a
claim that quasi-TEM, surface perturbation or a material fit applies physically.
"""
from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

import numpy as np

from .document import CrossSectionDocument, _keys, _unique_object
from .dielectric import (DielectricSweep, dielectric_from_dict, dielectric_to_dict,
                         _material_samples, _dispersive_from_mesh)
from .conductor import ConductorLoss, _surface_samples, _surface_from_mesh
from .roughness import CausalHuray
from .network import LineNetwork, _frequencies, _scalar, rlgc_network

__all__ = ['TransmissionLineDocument', 'TransmissionLineResult']


def _roughness(value):
    if not isinstance(value, dict):
        raise ValueError('roughness must explicitly select smooth, hammerstad or causal-huray')
    kind = value.get('kind')
    if kind == 'smooth':
        _keys(value, ('kind',), where='roughness')
        return {'kind':'smooth'}, 0.0, None
    if kind == 'hammerstad':
        _keys(value, ('kind','rms_m'), where='roughness')
        rms = _scalar('rms_m',value['rms_m'],zero=True)
        return {'kind':kind,'rms_m':rms}, rms, None
    if kind == 'causal-huray':
        _keys(value, ('kind','radii_m','surface_ratios'), where='roughness')
        model = CausalHuray(value['radii_m'],value['surface_ratios'])
        return dict(kind=kind,radii_m=list(model.radii_m),
                    surface_ratios=list(model.surface_ratios)), 0.0, model
    raise ValueError('unknown roughness kind')


def _conductor(value, section, frequency, schema):
    if not isinstance(value, dict):
        raise ValueError('conductor must explicitly select perfect or surface')
    kind = value.get('kind')
    if kind == 'perfect':
        _keys(value, ('kind',), where='conductor')
        return {'kind':'perfect'}, None
    if kind != 'surface':
        raise ValueError('conductor.kind must be perfect or surface')
    roughness_key = 'roughness_rms' if schema == 'sipi.transmission-line/1' else 'roughness'
    _keys(value, ('kind','conductivity','ground_thickness','relative_permeability',roughness_key),
          where='conductor')
    cleaned = {'kind':'surface'}
    for key in ('conductivity','ground_thickness','relative_permeability'):
        cleaned[key] = _scalar('conductor.'+key, value[key])
    if roughness_key == 'roughness_rms':
        rms = _scalar('conductor.roughness_rms',value['roughness_rms'],zero=True)
        cleaned['roughness_rms'], model = rms, None
    else:
        cleaned['roughness'], rms, model = _roughness(value['roughness'])
    samples = _surface_samples(section, frequency, cleaned['conductivity'],
        cleaned['ground_thickness'], cleaned['relative_permeability'], rms, model)
    return cleaned, samples


def _frozen(value):
    out = np.array(value, dtype=float, copy=True)
    out.setflags(write=False)
    return out


@dataclass(frozen=True)
class TransmissionLineResult:
    """A shared-mesh solve with retained inputs and extraction diagnostics.

    R/L/G/C properties are (F,N,N) SI matrices. A perfect conductor explicitly
    selects R=0 and internal L=0. A supplied result object is not a validation
    certificate; these fields retain the outputs of the actual extraction APIs.
    """
    dielectric: DielectricSweep
    conductor: ConductorLoss | None
    network: LineNetwork
    input_json: str
    mesh_settings: Mapping

    def __post_init__(self):
        object.__setattr__(self, 'mesh_settings', MappingProxyType(dict(self.mesh_settings)))

    @property
    def frequency(self):
        return self.dielectric.frequency

    @property
    def names(self):
        return self.dielectric.names

    @property
    def R(self):
        if self.conductor is not None:
            return self.conductor.R
        return _frozen(np.zeros_like(self.dielectric.C))

    @property
    def L(self):
        internal = 0 if self.conductor is None else self.conductor.L_internal
        return _frozen(np.broadcast_to(self.dielectric.L, self.dielectric.C.shape)+internal)

    @property
    def G(self):
        return _frozen(self.dielectric.G)

    @property
    def C(self):
        return self.dielectric.C


class TransmissionLineDocument:
    """Strict sipi.transmission-line/1 or /2; no file I/O or implicit metal.

    cross_section is a CrossSectionDocument. materials maps existing layer
    names to supported dielectric model objects; other layers stay constant.
    conductor is an explicit {'kind':'perfect'} or a complete surface record.
    Geometry mesh defaults are resolved and saved at construction. Accessors
    return fresh inputs; mutating caller dictionaries cannot change the solve.
    Version 1 remains the constructor default; version 2 explicitly selects a
    roughness object instead of the legacy surface roughness_rms field.
    """
    def __init__(self, cross_section, frequency, *, materials, conductor, length, z_ref=50.0,
                 schema='sipi.transmission-line/1'):
        if not isinstance(cross_section, CrossSectionDocument):
            raise TypeError('cross_section must be a CrossSectionDocument')
        if not isinstance(materials, Mapping):
            raise ValueError('materials must map layer names to dielectric models')
        data = dict(schema=schema, cross_section=cross_section.to_dict(),
            frequency_hz=_frequencies(frequency).tolist(),
            materials={k:dielectric_to_dict(v) for k,v in materials.items()},
            conductor=conductor, length_m=length, reference_ohms=z_ref)
        self._data = self._validate(data)

    @staticmethod
    def _validate(data):
        _keys(data, ('schema','cross_section','frequency_hz','materials','conductor',
                     'length_m','reference_ohms'), where='transmission line')
        if data['schema'] not in ('sipi.transmission-line/1','sipi.transmission-line/2'):
            raise ValueError('unsupported transmission-line schema')
        doc = CrossSectionDocument.from_dict(data['cross_section'])
        section = doc.section
        # Store resolved geometry settings so future defaults do not change the input.
        geometry = doc.to_dict()
        geometry['mesh'] = section.mesh_settings(**doc.mesh_options)
        doc = CrossSectionDocument.from_dict(geometry)
        f = _frequencies(data['frequency_hz'])
        length = _scalar('length_m',data['length_m'],zero=True)
        reference = _scalar('reference_ohms',data['reference_ohms'])
        if not isinstance(data['materials'],dict):
            raise ValueError('materials must be an object keyed by layer name')
        materials = {name:dielectric_from_dict(value) for name,value in data['materials'].items()}
        _material_samples(section,f,materials)  # Includes table range, before meshing.
        conductor, _ = _conductor(data['conductor'],section,f,data['schema'])
        return dict(schema=data['schema'], cross_section=doc.to_dict(),
            frequency_hz=f.tolist(), materials={k:dielectric_to_dict(v) for k,v in materials.items()},
            conductor=conductor, length_m=length, reference_ohms=reference)

    @classmethod
    def from_dict(cls, data):
        out = cls.__new__(cls)
        out._data = cls._validate(data)
        return out

    @classmethod
    def loads(cls, text):
        def reject(value):
            raise ValueError(f'nonfinite JSON number: {value}')
        return cls.from_dict(json.loads(text,object_pairs_hook=_unique_object,parse_constant=reject))

    def dumps(self):
        """Canonical input JSON; never writes a file or stores computed results."""
        return json.dumps(self._data,sort_keys=True,indent=2,ensure_ascii=False,allow_nan=False)

    def to_dict(self):
        return json.loads(self.dumps())

    @property
    def cross_section(self):
        return CrossSectionDocument.from_dict(self.to_dict()['cross_section'])

    def analyze(self):
        """Mesh once, extract matched RLGC and propagate the uniform line."""
        data = self.to_dict()
        doc = CrossSectionDocument.from_dict(data['cross_section'])
        section = doc.section
        materials = {k:dielectric_from_dict(v) for k,v in data['materials'].items()}
        f, samples = _material_samples(section,data['frequency_hz'],materials)
        _, metal_samples = _conductor(data['conductor'],section,f,data['schema'])
        meshed = section.mesh(**doc.mesh_options)
        loss = None if metal_samples is None else _surface_from_mesh(meshed,*metal_samples)
        c0 = None if loss is None else loss.factors.C0
        dielectric = _dispersive_from_mesh(meshed,f,samples,c0=c0)
        resistance = np.zeros_like(dielectric.C) if loss is None else loss.R
        inductance = dielectric.L if loss is None else dielectric.L+loss.L_internal
        net = rlgc_network(f,R=resistance,L=inductance,G=dielectric.G,C=dielectric.C,
                          length=data['length_m'],z_ref=data['reference_ohms'],names=dielectric.names)
        return TransmissionLineResult(dielectric,loss,net,self.dumps(),doc.mesh_options)
