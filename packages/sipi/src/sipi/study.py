# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Reproducible impedance studies; no resampling or removal of failed rows."""
from __future__ import annotations

from dataclasses import dataclass
from inspect import signature
from itertools import product
import json
from types import MappingProxyType

import numpy as np

from . import templates
from .document import CrossSectionDocument, _keys, _unique_object

__all__ = ['ImpedanceStudyDocument', 'StudyRow', 'ImpedanceStudy']

_TEMPLATES = {name: getattr(templates, name) for name in
              ('microstrip', 'stripline', 'coupled_microstrip', 'grounded_coplanar', 'coated_microstrip')}


def _numbers(value):
    raw = np.asarray(value)
    if (raw.dtype.kind not in 'iuf' or not np.all(np.isfinite(raw))
            or any(isinstance(x, (bool, np.bool_)) for x in np.asarray(value, dtype=object).flat)):
        raise ValueError('expected finite real numbers, not booleans')
    return np.array(raw, dtype=float)


def _scalar(value, *, positive=False):
    raw = _numbers(value)
    if raw.ndim or (positive and raw <= 0):
        raise ValueError('expected a finite scalar' + (' > 0' if positive else ''))
    return float(raw)


def _integer(value, lo, hi):
    if type(value) is not int or not lo <= value <= hi:
        raise ValueError(f'expected an integer in [{lo}, {hi}]')
    return value


def _copy(value):
    try:
        text = json.dumps(value, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise ValueError('study input must contain finite JSON values') from exc
    return json.loads(text)


def _parameters(data, values):
    params = dict(data['parameters'])
    params.update(zip((v['name'] for v in data['sampling']['variables']), map(float, values)))
    if data['fixed_pitch_m'] is not None:
        params['gap'] = data['fixed_pitch_m']-params['width']
    return params


@dataclass(frozen=True)
class StudyRow:
    index: int
    parameters: object
    document: CrossSectionDocument | None
    impedance: float | None
    error_type: str | None
    error: str | None

    def __post_init__(self):
        object.__setattr__(self, 'parameters', MappingProxyType(dict(self.parameters)))

    @property
    def complete(self):
        return self.error is None


@dataclass(frozen=True)
class ImpedanceStudy:
    input_json: str
    quantity: str
    rows: tuple[StudyRow, ...]
    summary: object | None

    def __post_init__(self):
        object.__setattr__(self, 'rows', tuple(self.rows))
        if self.summary is not None:
            object.__setattr__(self, 'summary', MappingProxyType(dict(self.summary)))

    @property
    def failed(self):
        return sum(not row.complete for row in self.rows)


class ImpedanceStudyDocument:
    """Strict sipi.impedance-study/1, five templates and resolved nominal mesh.

    Sampling is separate from expensive FEM evaluation. Normal samples are
    unbounded: invalid physical inputs remain failed rows, never resampled.
    Fixed pitch applies only to the symmetric coupled_microstrip template.
    """
    def __init__(self, template, parameters, *, sampling, quantity, mesh=None, fixed_pitch_m=None):
        self._data = self._validate(dict(schema='sipi.impedance-study/1', template=template,
            parameters=parameters, sampling=sampling, quantity=quantity,
            mesh={} if mesh is None else mesh, fixed_pitch_m=fixed_pitch_m))

    @staticmethod
    def _validate(data):
        data = _copy(data)
        _keys(data, ('schema', 'template', 'parameters', 'sampling', 'quantity', 'mesh',
                     'fixed_pitch_m'), where='impedance study')
        if data['schema'] != 'sipi.impedance-study/1':
            raise ValueError('unsupported impedance-study schema')
        template = data['template']
        if not isinstance(template, str) or template not in _TEMPLATES:
            raise ValueError('unsupported study template')
        factory = _TEMPLATES[template]
        if not isinstance(data['parameters'], dict):
            raise ValueError('parameters must be a template argument object')
        try:
            bound = signature(factory).bind(**data['parameters'])
        except TypeError as exc:
            raise ValueError('unknown or missing template parameters') from exc
        bound.apply_defaults()
        parameters = {k: None if v is None else _scalar(v) for k, v in bound.arguments.items()}
        section = factory(**parameters)
        if not isinstance(data['mesh'], dict):
            raise ValueError('mesh must be an object')
        doc = CrossSectionDocument(section, mesh=data['mesh'])
        mesh = section.mesh_settings(**doc.mesh_options)
        quantity = 'z_diff' if template == 'coupled_microstrip' else 'z0'
        if data['quantity'] != quantity:
            raise ValueError(f'this template requires quantity={quantity}')
        sampling = data['sampling']
        if not isinstance(sampling, dict):
            raise ValueError('sampling must be an object')
        kind = sampling.get('kind')
        if kind not in ('sweep', 'corners', 'uniform', 'normal'):
            raise ValueError('unsupported sampling kind')
        required = ['kind', 'variables']
        if kind != 'corners':
            required.append('count')
        if kind in ('uniform', 'normal'):
            required.append('seed')
        if kind == 'normal':
            required.append('correlation')
        _keys(sampling, required, where='sampling')
        variables = sampling['variables']
        if not isinstance(variables, list) or not 1 <= len(variables) <= 8:
            raise ValueError('use 1 to 8 independent variables')
        if kind == 'sweep' and len(variables) != 1:
            raise ValueError('sweep needs exactly one variable')
        names = []
        for variable in variables:
            fields = ('name', 'mean', 'std') if kind == 'normal' else ('name', 'lower', 'upper')
            _keys(variable, fields, where='variable')
            name = variable['name']
            if not isinstance(name, str) or name not in parameters or name in names:
                raise ValueError('variables must be distinct template parameter names')
            names.append(name)
            for key in fields[1:]:
                variable[key] = _scalar(variable[key], positive=key == 'std')
            if kind != 'normal' and variable['lower'] >= variable['upper']:
                raise ValueError('variable lower must be below upper')
        if kind != 'corners':
            sampling['count'] = _integer(sampling['count'], 2, 10000)
        if kind in ('uniform', 'normal'):
            sampling['seed'] = _integer(sampling['seed'], 0, 2**32-1)
        if kind == 'normal':
            c = _numbers(sampling['correlation'])
            n = len(names)
            if (c.shape != (n, n) or np.max(abs(c-c.T)) > 1e-12
                    or np.max(abs(c.diagonal()-1)) > 1e-12 or np.max(abs(c)) > 1+1e-12):
                raise ValueError('correlation must be symmetric with unit diagonal')
            c = (c+c.T)/2
            if np.linalg.eigvalsh(c)[0] < -1e-12:
                raise ValueError('correlation must be positive semidefinite')
            sampling['correlation'] = c.tolist()
        pitch = data['fixed_pitch_m']
        if pitch is not None:
            pitch = _scalar(pitch, positive=True)
            if template != 'coupled_microstrip' or 'width' not in names or 'gap' in names:
                raise ValueError('fixed pitch requires coupled_microstrip width sampling, without gap sampling')
            if abs(parameters['width']+parameters['gap']-pitch) > 1e-12*pitch:
                raise ValueError('nominal width + gap must equal fixed pitch')
        canonical = dict(schema=data['schema'], template=template, parameters=parameters,
                         quantity=quantity, mesh=mesh, sampling=sampling, fixed_pitch_m=pitch)
        # Check the requested finite bounds before any solves. This does not
        # establish worst-case impedance or validate an unbounded normal domain.
        if kind != 'normal':
            bounds = [(v['lower'], v['upper']) for v in variables]
            for corner in product(*bounds):
                factory(**_parameters(canonical, corner))
        return canonical

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

    def samples(self):
        """Read-only (samples, independent variables), in listed variable order."""
        s = self._data['sampling']
        variables = s['variables']
        if s['kind'] == 'normal':
            mean = np.array([v['mean'] for v in variables])
            std = np.array([v['std'] for v in variables])
            eigenvalues, vectors = np.linalg.eigh(s['correlation'])
            # Only accepted roundoff negatives (>=-1e-12) are clipped.
            root = (vectors*np.sqrt(np.maximum(eigenvalues, 0)))@vectors.T
            rng = np.random.Generator(np.random.PCG64(s['seed']))
            samples = mean+(rng.standard_normal((s['count'], len(variables)))@root.T)*std
        else:
            low, high = np.array([(v['lower'], v['upper']) for v in variables]).T
            if s['kind'] == 'corners':
                samples = np.array(list(product(*zip(low, high))))
            elif s['kind'] == 'sweep':
                samples = np.linspace(low, high, s['count'])
            else:
                rng = np.random.Generator(np.random.PCG64(s['seed']))
                samples = rng.uniform(low, high, size=(s['count'], len(variables)))
        if not np.all(np.isfinite(samples)):
            raise ValueError('sampling overflow; rescale distribution parameters')
        samples.setflags(write=False)
        return samples

    def sample_parameters(self):
        """Fresh full template arguments per sample, including any derived gap."""
        return [_parameters(self._data, row) for row in self.samples()]

    def analyze(self, *, max_evaluations=128):
        """Evaluate every planned sample, retaining errors; no partial statistics.

        max_evaluations is a caller's explicit budget, checked before any solve.
        The nominal resolved mesh is shared as settings, not as one geometric
        mesh. Geometry is remeshed per row; no per-row convergence is inferred.
        """
        budget = _integer(max_evaluations, 2, 10000)
        parameters = self.sample_parameters()
        if len(parameters) > budget:
            raise ValueError('sample count exceeds max_evaluations before any solve')
        data, rows = self._data, []
        for i, values in enumerate(parameters):
            doc = None
            try:
                section = _TEMPLATES[data['template']](**values)
                doc = CrossSectionDocument(section, mesh=data['mesh'])
                line = doc.analyze()
                value = float(line.z0 if data['quantity'] == 'z0' else line.even_odd()['z_diff'])
                if not np.isfinite(value) or value <= 0:
                    raise ValueError('solver returned a nonpositive or nonfinite impedance')
                rows.append(StudyRow(i, values, doc, value, None, None))
            except Exception as exc:
                rows.append(StudyRow(i, values, doc, None, type(exc).__name__, str(exc)))
        summary = None
        if all(row.complete for row in rows):
            z = np.array([row.impedance for row in rows])
            summary = dict(minimum=float(z.min()), maximum=float(z.max()), mean=float(z.mean()),
                           sample_std=float(z.std(ddof=1)), p05=float(np.quantile(z, .05, method='linear')),
                           p95=float(np.quantile(z, .95, method='linear')))
        return ImpedanceStudy(self.dumps(), data['quantity'], tuple(rows), summary)
