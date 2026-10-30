# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Versioned, strict JSON input for native and browser cross-section consumers."""

from __future__ import annotations

import json
import math
from numbers import Real

from .crosssection import CrossSection, Layer, Trace
from .polygons import PolygonTrace, DielectricRegion, _vertices

__all__ = ['CrossSectionDocument']
_SCHEMA = 'sipi.cross-section/1'
_TAPER_SCHEMA = 'sipi.cross-section/2'
_POLYGON_SCHEMA = 'sipi.cross-section/3'


def _trace(row):
    values = {k: v for k, v in row.items() if k != 'kind'}
    return PolygonTrace(**values) if row.get('kind') == 'polygon' else Trace(**values)


def _keys(value, required, optional=(), *, where):
    if not isinstance(value, dict):
        raise ValueError(f'{where} must be an object')
    if set(value) - set(required) - set(optional) or set(required) - set(value):
        raise ValueError(f'{where} has missing or unknown fields')


def _number(value, where):
    if isinstance(value, bool) or not isinstance(value, Real) or not math.isfinite(value):
        raise ValueError(f'{where} must be a finite real number')
    return float(value)


def _name(value, where):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f'{where} must be a nonempty string')
    return value


def _mesh(value):
    _keys(value, (), ('edge_size', 'far_size', 'grade', 'min_angle'), where='mesh')
    result = {k: _number(v, 'mesh.'+k) for k, v in value.items()}
    for k in ('edge_size', 'far_size'):
        if k in result and result[k] <= 0:
            raise ValueError(f'mesh.{k} must be > 0')
    if 'grade' in result and result['grade'] < 0:
        raise ValueError('mesh.grade must be >= 0')
    if 'min_angle' in result and not 0 < result['min_angle'] < 34:
        raise ValueError('mesh.min_angle must be in (0, 34) degrees')
    return result


def _unique_object(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise ValueError(f'duplicate JSON field: {key}')
        out[key] = value
    return out


class CrossSectionDocument:
    """A validated input snapshot with all lengths in metres.

    Construction copies the section and mesh options; accessors return fresh
    values. Results are deliberately not stored in the input document.
    """

    def __init__(self, section: CrossSection, *, mesh=None):
        if not isinstance(section, CrossSection):
            raise TypeError('section must be a CrossSection')
        data = dict(schema=_SCHEMA, length_unit='m',
                    layers=[dict(name=l.name, thickness=l.thickness, eps_r=l.eps_r,
                                 tan_delta=l.tan_delta) for l in section.layers],
                    traces=[(dict(kind='polygon', name=t.name, vertices=t.vertices, ground=t.ground)
                             if isinstance(t, PolygonTrace) else
                             dict(name=t.name, x=t.x, width=t.width, y=t.y,
                                  thickness=t.thickness, ground=t.ground)) for t in section.traces],
                    box=dict(width=section.width, bottom=section.bottom,
                             top=section.top, sides=section.sides),
                    mesh={} if mesh is None else mesh)
        if section.polygonal:
            data['schema'] = _POLYGON_SCHEMA
            data['dielectric_regions'] = [dict(name=r.name, vertices=r.vertices, eps_r=r.eps_r,
                                               tan_delta=r.tan_delta) for r in section.dielectric_regions]
            for row, trace in zip(data['traces'], section.traces):
                if isinstance(trace, Trace):
                    row['kind'] = 'trapezoid'
                    row['top_width'] = trace.width if trace.top_width is None else trace.top_width
        elif any(t.tapered for t in section.traces):
            data['schema'] = _TAPER_SCHEMA
            for row, trace in zip(data['traces'], section.traces):
                row['top_width'] = trace.width if trace.top_width is None else trace.top_width
        # Use the same strict path for Python-created and decoded input.
        self._data = self._validate(data)

    @staticmethod
    def _validate(data):
        if not isinstance(data, dict):
            raise ValueError('document must be an object')
        polygonal = data.get('schema') == _POLYGON_SCHEMA
        required = ('schema', 'length_unit', 'layers', 'traces', 'box', 'mesh')
        _keys(data, (*required, 'dielectric_regions') if polygonal else required, where='document')
        if data['schema'] not in (_SCHEMA, _TAPER_SCHEMA, _POLYGON_SCHEMA) or data['length_unit'] != 'm':
            raise ValueError('unsupported schema or length_unit; expected sipi.cross-section/1, /2 or /3 and m')
        layers, traces = [], []
        for kind, fields, output in (
                ('layers', ('name', 'thickness', 'eps_r', 'tan_delta'), layers),
                ('traces', ('name', 'x', 'width', 'y', 'thickness', 'ground'), traces)):
            if kind == 'traces' and data['schema'] == _TAPER_SCHEMA:
                fields = (*fields, 'top_width')
            if not isinstance(data[kind], list) or not data[kind]:
                raise ValueError(f'{kind} must be a nonempty array')
            for row in data[kind]:
                row_fields = fields
                if kind == 'traces' and polygonal:
                    if not isinstance(row, dict) or row.get('kind') not in ('polygon', 'trapezoid'):
                        raise ValueError('trace kind must be polygon or trapezoid')
                    row_fields = (('kind', 'name', 'vertices', 'ground') if row['kind'] == 'polygon'
                                  else (*fields, 'kind', 'top_width'))
                _keys(row, row_fields, where=kind)
                cleaned = {}
                for key in row_fields:
                    if key == 'kind':
                        cleaned[key] = row[key]
                    elif key == 'vertices':
                        cleaned[key] = [list(point) for point in _vertices(row[key])]
                    elif key == 'name':
                        cleaned[key] = _name(row[key], kind+'.name')
                    elif key == 'ground':
                        if type(row[key]) is not bool:
                            raise ValueError('traces.ground must be a boolean')
                        cleaned[key] = row[key]
                    else:
                        cleaned[key] = _number(row[key], kind+'.'+key)
                output.append(cleaned)
        regions = []
        if polygonal:
            if not isinstance(data['dielectric_regions'], list):
                raise ValueError('dielectric_regions must be an array')
            for row in data['dielectric_regions']:
                _keys(row, ('name', 'vertices', 'eps_r', 'tan_delta'), where='dielectric region')
                regions.append(dict(name=_name(row['name'], 'region.name'),
                    vertices=[list(point) for point in _vertices(row['vertices'])],
                    eps_r=_number(row['eps_r'], 'region.eps_r'),
                    tan_delta=_number(row['tan_delta'], 'region.tan_delta')))
        box = data['box']
        _keys(box, ('width', 'bottom', 'top', 'sides'), where='box')
        cleaned_box = dict(width=_number(box['width'], 'box.width'))
        for key in ('bottom', 'top', 'sides'):
            if not isinstance(box[key], str) or box[key] not in ('open', 'ground'):
                raise ValueError(f'box.{key} must be open or ground')
            cleaned_box[key] = box[key]
        options = _mesh(data['mesh'])
        section = CrossSection([Layer(**l) for l in layers], [_trace(t) for t in traces],
                               dielectric_regions=[DielectricRegion(**r) for r in regions], **cleaned_box)
        # Resolve defaults too, so inconsistent explicit settings fail before meshing.
        section.mesh_settings(**options)
        result = dict(schema=data['schema'], length_unit='m', layers=layers, traces=traces,
                      box=cleaned_box, mesh=options)
        if polygonal:
            result['dielectric_regions'] = regions
        return result

    @classmethod
    def from_dict(cls, data):
        """Validate a document object. Unknown fields and versions are errors."""
        obj = cls.__new__(cls)
        obj._data = cls._validate(data)
        return obj

    @classmethod
    def loads(cls, text):
        """Decode JSON, rejecting duplicate fields and nonfinite numbers."""
        def reject(value):
            raise ValueError(f'nonfinite JSON number: {value}')
        return cls.from_dict(json.loads(text, object_pairs_hook=_unique_object,
                                       parse_constant=reject))

    def to_dict(self):
        """Return a fresh plain JSON-compatible object."""
        return json.loads(self.dumps())

    def dumps(self):
        """Encode deterministic JSON; never write a file implicitly."""
        return json.dumps(self._data, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False)

    @property
    def section(self):
        """Rebuild the exact cross-section without meshing it."""
        data = self._data
        return CrossSection([Layer(**l) for l in data['layers']],
                            [_trace(t) for t in data['traces']],
                            dielectric_regions=[DielectricRegion(**r)
                                                for r in data.get('dielectric_regions', [])], **data['box'])

    @property
    def mesh_options(self):
        return dict(self._data['mesh'])

    def analyze(self):
        """Run the ordinary SIPI engine on this input snapshot."""
        return self.section.analyze(**self.mesh_options)
