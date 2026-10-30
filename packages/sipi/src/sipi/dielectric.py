# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Passive dielectric models and frequency-by-frequency quasi-static extraction.

Relative permittivity uses exp(+j omega t), hence nonpositive imaginary part.
Analytical relaxation models do not establish a material's measured validity
range. Tabulated samples interpolate in log frequency without extrapolation;
sampled passivity alone does not establish causality.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass
from types import MappingProxyType

import numpy as np
from scipy.constants import epsilon_0, mu_0

from .network import _frequencies, _real, _scalar, rlgc_network
from .quasistatic import capacitance_matrix

__all__ = ['ConstantDielectric', 'DebyeDielectric', 'WidebandDielectric',
           'TabulatedDielectric', 'dielectric_to_dict', 'dielectric_from_dict',
           'DielectricSweep', 'dispersive_line']


def _eps(value):
    result = _scalar('relative permittivity', value)
    if result < 1:
        raise ValueError('relative permittivity must be >= 1')
    return result


def _samples(frequency):
    f = _real('frequency', frequency)
    if f.ndim > 1 or not f.size or np.any(f < 0):
        raise ValueError('frequency must be a scalar or nonempty 1D array in Hz, >= 0')
    return f


def _vector(name, value, *, zero=False):
    a = _real(name, value)
    if a.ndim != 1 or not len(a) or np.any(a < 0 if zero else a <= 0):
        raise ValueError(f'{name} must be a nonempty 1D array with valid positive bounds')
    return tuple(map(float, a))


@dataclass(frozen=True)
class ConstantDielectric:
    """Frequency-invariant eps_r*(1-j*tan_delta); no broadband causality claim."""
    eps_r: float
    tan_delta: float = 0.0

    def __post_init__(self):
        object.__setattr__(self, 'eps_r', _eps(self.eps_r))
        object.__setattr__(self, 'tan_delta', _scalar('tan_delta', self.tan_delta, zero=True))
        if not np.isfinite(self.eps_r*self.tan_delta):
            raise ValueError('dielectric loss must be finite')

    def permittivity(self, frequency):
        f = _samples(frequency)
        return np.full(f.shape, self.eps_r*(1-1j*self.tan_delta), dtype=complex)


@dataclass(frozen=True)
class DebyeDielectric:
    """eps_inf + sum(strength / (1+j*f/relaxation_hz)), nonnegative strengths."""
    eps_inf: float
    strengths: tuple[float, ...]
    relaxation_hz: tuple[float, ...]

    def __post_init__(self):
        object.__setattr__(self, 'eps_inf', _eps(self.eps_inf))
        object.__setattr__(self, 'strengths', _vector('strengths', self.strengths, zero=True))
        object.__setattr__(self, 'relaxation_hz', _vector('relaxation_hz', self.relaxation_hz))
        if len(self.strengths) != len(self.relaxation_hz):
            raise ValueError('strengths and relaxation_hz must have equal lengths')
        if not np.isfinite(self.eps_inf + sum(self.strengths)):
            raise ValueError('static relative permittivity must be finite')

    def permittivity(self, frequency):
        f = _samples(frequency)
        result = np.full(f.shape, self.eps_inf, dtype=complex)
        for strength, pole in zip(self.strengths, self.relaxation_hz):
            # Normalize before squaring: even hypot(pole,f) can overflow.
            scale = np.maximum(pole, f)
            a, b = pole/scale, f/scale
            result += strength*(a*a-1j*a*b)/(a*a+b*b)
        return result


@dataclass(frozen=True)
class WidebandDielectric:
    """Finite-band log relaxation (Svensson/Djordjevic), calibrated at one f.

    low_hz/high_hz are relaxation rolloffs, not a measured validity interval.
    The reference frequency must lie between them; calibration must leave
    eps_inf >= 1. tan_delta_ref=0 gives a constant lossless dielectric.
    """
    eps_ref: float
    tan_delta_ref: float
    reference_hz: float
    low_hz: float = 1e3
    high_hz: float = 1e12

    def __post_init__(self):
        object.__setattr__(self, 'eps_ref', _eps(self.eps_ref))
        object.__setattr__(self, 'tan_delta_ref', _scalar('tan_delta_ref', self.tan_delta_ref, zero=True))
        for name in ('reference_hz', 'low_hz', 'high_hz'):
            object.__setattr__(self, name, _scalar(name, getattr(self, name)))
        if not self.low_hz < self.high_hz or not self.low_hz <= self.reference_hz <= self.high_hz:
            raise ValueError('require low_hz < high_hz and reference_hz inside that interval')
        strength, eps_inf = self._calibration()
        if not np.isfinite(strength) or not np.isfinite(eps_inf) or eps_inf < 1:
            raise ValueError('calibration must yield finite strength and eps_inf >= 1')

    def _band(self, f):
        def log_hypot(pole):
            scale = np.maximum(pole, f)
            return np.log(scale)+.5*np.log1p((np.minimum(pole, f)/scale)**2)
        real = log_hypot(self.high_hz)-log_hypot(self.low_hz)
        imag = np.arctan2(f, self.high_hz)-np.arctan2(f, self.low_hz)
        return real + 1j*imag

    def _calibration(self):
        if self.tan_delta_ref == 0:
            return 0.0, self.eps_ref
        k = self._band(self.reference_hz)
        if k.imag >= 0:
            raise ValueError('relaxation band cannot be resolved at reference_hz')
        strength = self.eps_ref*self.tan_delta_ref / -k.imag
        return strength, self.eps_ref-strength*k.real

    def permittivity(self, frequency):
        f = _samples(frequency)
        strength, eps_inf = self._calibration()
        return eps_inf + strength*self._band(f)


@dataclass(frozen=True)
class TabulatedDielectric:
    """Positive-Hz table; linear eps' and eps'' interpolation versus log(f).

    Both endpoints are included. Extrapolation and DC evaluation are rejected.
    Interpolating passive samples does not imply a causal broadband model.
    """
    frequency: tuple[float, ...]
    eps_r: tuple[float, ...]
    tan_delta: tuple[float, ...]

    def __post_init__(self):
        f = _vector('frequency', self.frequency)
        eps = _vector('eps_r', self.eps_r)
        loss = _vector('tan_delta', self.tan_delta, zero=True)
        if len(f) < 2 or len(eps) != len(f) or len(loss) != len(f) or np.any(np.diff(f) <= 0):
            raise ValueError('table needs equal-length arrays and at least two increasing frequencies')
        if min(eps) < 1 or not np.all(np.isfinite(np.asarray(eps)*loss)):
            raise ValueError('table needs eps_r >= 1 and finite dielectric loss')
        for name, value in (('frequency', f), ('eps_r', eps), ('tan_delta', loss)):
            object.__setattr__(self, name, value)

    def permittivity(self, frequency):
        f = _samples(frequency)
        if np.any(f < self.frequency[0]) or np.any(f > self.frequency[-1]):
            raise ValueError('frequency lies outside the dielectric table; extrapolation is disabled')
        x, xp = np.log(f), np.log(self.frequency)
        return (np.interp(x, xp, self.eps_r)
                - 1j*np.interp(x, xp, np.asarray(self.eps_r)*self.tan_delta))


_MODELS = {'constant': ConstantDielectric, 'debye': DebyeDielectric,
           'wideband': WidebandDielectric, 'table': TabulatedDielectric}


def dielectric_to_dict(model):
    """Versioned, JSON-safe model input; no code paths or implicit units."""
    for kind, cls in _MODELS.items():
        if type(model) is cls:
            parameters = {k: list(v) if isinstance(v, tuple) else v for k, v in asdict(model).items()}
            return dict(schema='sipi.dielectric/1', kind=kind, parameters=parameters)
    raise ValueError('unsupported dielectric model')


def dielectric_from_dict(value):
    """Read exact keys; frequencies are Hz and permittivity is relative."""
    if not isinstance(value, dict) or set(value) != {'schema', 'kind', 'parameters'}:
        raise ValueError('dielectric document needs exactly schema, kind and parameters')
    kind = value['kind']
    if value['schema'] != 'sipi.dielectric/1' or not isinstance(kind, str) or kind not in _MODELS:
        raise ValueError('unsupported dielectric schema or kind')
    cls, parameters = _MODELS[kind], value['parameters']
    if not isinstance(parameters, dict) or set(parameters) != set(cls.__dataclass_fields__):
        raise ValueError('dielectric parameters must contain every declared field and no extras')
    return cls(**parameters)


@dataclass(frozen=True)
class DielectricSweep:
    """Sampled complex capacitance and external inductance on one fixed mesh.

    C_complex=C-j*C_loss in F/m; G=2*pi*f*C_loss. R and internal conductor L
    are not extracted here. Arrays are copied/read-only. Layer permittivities
    preserve the actual complex samples used for every solve.
    """
    frequency: np.ndarray
    names: tuple[str, ...]
    C_complex: np.ndarray
    C0: np.ndarray
    L: np.ndarray
    layer_permittivity: Mapping

    def __post_init__(self):
        f = _frequencies(self.frequency)
        names = tuple(self.names)
        if not names or any(not isinstance(n, str) or not n for n in names) or len(set(names)) != len(names):
            raise ValueError('signal names must be unique nonempty strings')
        object.__setattr__(self, 'names', names)
        n = len(names)
        for key, value, shape, dtype in (
                ('frequency', f, (len(f),), float),
                ('C_complex', self.C_complex, (len(f), n, n), complex),
                ('C0', self.C0, (n, n), float), ('L', self.L, (n, n), float)):
            a = np.array(value, dtype=dtype, copy=True)
            if a.shape != shape or not np.all(np.isfinite(a)):
                raise ValueError(f'{key} has invalid shape or nonfinite values')
            a.setflags(write=False)
            object.__setattr__(self, key, a)
        samples = {}
        for key, value in self.layer_permittivity.items():
            a = np.array(value, dtype=complex, copy=True)
            if a.shape != f.shape or not np.all(np.isfinite(a)) or np.any(a.real < 1) or np.any(a.imag > 0):
                raise ValueError('invalid layer permittivity samples')
            a.setflags(write=False)
            samples[key] = a
        object.__setattr__(self, 'layer_permittivity', MappingProxyType(samples))

    @property
    def C(self):
        return self.C_complex.real

    @property
    def G(self):
        return -2*np.pi*self.frequency[:, None, None]*self.C_complex.imag

    def network(self, *, length, R, z_ref=50.0):
        """Use explicit conductor R with extracted frequency-dependent C/G."""
        return rlgc_network(self.frequency, R=R, L=self.L, G=self.G, C=self.C,
                            length=length, z_ref=z_ref, names=self.names)


def dispersive_line(section, frequency, *, materials, **mesh_options):
    """Solve the complex electrostatic problem at each frequency on one mesh.

    materials maps existing layer names to supported dielectric models. Other
    layers retain their constant eps_r/tan_delta. Unknown layers, invalid models
    and table range errors fail before meshing. Existing section/doc APIs and
    constant-material extraction are unchanged. There is no wavelength-dependent
    field correction or conductor-current solve in this quasi-TEM formulation.
    """
    f, samples = _material_samples(section, frequency, materials)
    return _dispersive_from_mesh(section.mesh(**mesh_options), f, samples)


def _material_samples(section, frequency, materials):
    """Validate and sample before any geometry work; shared by input documents."""
    f = _frequencies(frequency)
    if not isinstance(materials, Mapping):
        raise ValueError('materials must map layer names to dielectric models')
    layers = {layer.name: layer for layer in section.layers}
    if not set(materials) <= set(layers):
        raise ValueError('materials contains an unknown layer name')
    samples = {}
    for name, layer in layers.items():
        model = materials.get(name, ConstantDielectric(layer.eps_r, layer.tan_delta))
        dielectric_to_dict(model)  # Enforce the supported, serializable contract.
        samples[name] = model.permittivity(f)
        if not np.all(np.isfinite(samples[name])):
            raise ValueError('dielectric evaluation produced nonfinite samples')
    return f, samples


def _dispersive_from_mesh(meshed, f, samples, *, c0=None):
    """Internal composition on an already validated, shared dielectric mesh."""
    mesh, signals, ground = meshed.mesh, meshed.signals, meshed.ground
    if c0 is None:
        c0 = capacitance_matrix(mesh, 1.0, signals, ground)
    inductance = mu_0*epsilon_0*np.linalg.inv(c0)
    regions = [mesh.region_names[r] for r in mesh.regions]
    complex_c = []
    for index in range(len(f)):
        eps = np.array([samples[name][index] for name in regions])
        complex_c.append(capacitance_matrix(mesh, eps, signals, ground))
    return DielectricSweep(f, tuple(signals), complex_c, c0, inductance, samples)
