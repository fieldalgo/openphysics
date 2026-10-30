# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Finite passive terminations of real-reference power-wave networks.

Voltages/currents are peak phasors, with currents directed into the network.
No topology, source location or victim port is inferred from port order.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

import numpy as np

from .network import LineNetwork

__all__ = ['TerminatedNetwork', 'Crosstalk', 'terminate_network', 'loaded_crosstalk']


def _snapshot(value):
    result = np.array(value, copy=True)
    result.setflags(write=False)
    return result


def _values(network, values, name, default, *, passive=False):
    if not isinstance(values, Mapping):
        raise ValueError(f'{name} must be a mapping from port names to numbers')
    shape = (len(network.frequency), len(network.port_names))
    result = np.broadcast_to(default, shape).astype(complex).copy()
    for port, value in values.items():
        if not isinstance(port, str) or port not in network.port_names:
            raise ValueError(f'{name} contains an unknown port: {port!r}')
        raw = np.asarray(value)
        if (raw.dtype.kind not in 'iufc' or not np.all(np.isfinite(raw))
                or any(isinstance(x, (bool, np.bool_))
                       for x in np.asarray(value, dtype=object).flat)):
            raise ValueError(f'{name}[{port!r}] needs finite numbers, not booleans')
        if raw.ndim != 0 and raw.shape != (shape[0],):
            raise ValueError(f'{name}[{port!r}] needs a scalar or one value per frequency')
        if passive and np.any(raw.real < 0):
            raise ValueError('terminations must be passive: real part >= 0')
        result[:, network.port_names.index(port)] = raw
    return result


@dataclass(frozen=True)
class TerminatedNetwork:
    """Read-only circuit solution, arrays (frequencies, ports) unless noted.

    ``a,b`` are incident/outgoing power waves. ``voltage,current`` are terminal
    peak phasors in V/A. ``source_voltages`` are Thevenin open-circuit voltages;
    ``terminations`` include the series source impedances, in ohms.
    Condition numbers and normalized residuals have shape (frequencies,).
    Power uses Re(V I*) at DC and Re(V I*)/2 for positive-frequency peak phasors.
    """
    network: LineNetwork
    source_voltages: np.ndarray
    terminations: np.ndarray
    a: np.ndarray
    b: np.ndarray
    voltage: np.ndarray
    current: np.ndarray
    condition_number: np.ndarray
    kvl_residual: np.ndarray
    wave_residual: np.ndarray

    def __post_init__(self):
        for name in ('source_voltages', 'terminations', 'a', 'b', 'voltage', 'current',
                     'condition_number', 'kvl_residual', 'wave_residual'):
            object.__setattr__(self, name, _snapshot(getattr(self, name)))

    @property
    def frequency(self):
        return self.network.frequency

    @property
    def port_names(self):
        return self.network.port_names

    @property
    def basis(self):
        return self.network.basis

    def _power(self, voltage):
        with np.errstate(over='ignore', invalid='ignore'):
            weight = np.where(self.frequency == 0, 1., .5)
            value = weight*np.real(np.sum(voltage*np.conj(self.current), axis=1))
        if not np.all(np.isfinite(value)):
            raise ValueError('average power overflow; rescale the excitation')
        return _snapshot(value)

    @property
    def network_power(self):
        """Net average power into the network (W); arbitrary S may be active."""
        return self._power(self.voltage)

    @property
    def termination_power(self):
        """Average power dissipated in all source/load impedances (W)."""
        return self._power(self.terminations*self.current)

    @property
    def source_power(self):
        """Net average power supplied by ideal Thevenin voltage sources (W)."""
        return self._power(self.source_voltages)


def terminate_network(network, *, source_voltages, terminations=None):
    """Solve a LineNetwork with named Thevenin sources and passive impedances.

    Values are finite complex scalars or arrays of length F. Unspecified source
    voltages are zero; unspecified impedances equal each port's real reference.
    Zero impedance (short) is supported; infinite/open loads are not. Independent
    modal terminations can be applied to a mixed-mode network in that basis.
    Reject condition numbers above 1e12 or circuit residuals above 1e-10.
    """
    if not isinstance(network, LineNetwork):
        raise TypeError('network must be a LineNetwork')
    if not isinstance(source_voltages, Mapping) or not source_voltages:
        raise ValueError('source_voltages must be a nonempty mapping')
    vs = _values(network, source_voltages, 'source_voltages', 0)
    zt = _values(network, {} if terminations is None else terminations,
                 'terminations', network.z_ref, passive=True)
    # Snapshot even externally supplied networks; results retain the solved input.
    net = LineNetwork(network.frequency, network.s, network.z_ref,
                      network.port_names, network.basis)
    root = np.sqrt(net.z_ref)
    with np.errstate(over='ignore', invalid='ignore', divide='ignore'):
        # This equivalent form avoids subtraction of two very large impedances.
        gamma = 1 - 2*(net.z_ref/(zt+net.z_ref))
        drive = (vs/(zt+net.z_ref))*root
        system = np.eye(len(net.port_names)) - gamma[:, :, None]*net.s
    if not np.all(np.isfinite(system)) or not np.all(np.isfinite(drive)):
        raise ValueError('nonfinite terminated system; rescale the input')
    try:
        condition = np.linalg.cond(system)
        if np.any(~np.isfinite(condition)) or np.any(condition > 1e12):
            bad = int(np.flatnonzero(~np.isfinite(condition) | (condition > 1e12))[0])
            raise ValueError(f'ill-conditioned termination at {net.frequency[bad]:g} Hz '
                             f'(condition={condition[bad]:g}, limit=1e12)')
        a = np.linalg.solve(system, drive[..., None])[..., 0]
    except np.linalg.LinAlgError as exc:
        raise ValueError('singular terminated network') from exc
    with np.errstate(over='ignore', invalid='ignore'):
        b = (net.s @ a[..., None])[..., 0]
        voltage = (a+b)*root
        current = (a-b)/root
        drop = zt*current
        kvl_error = vs-voltage-drop
        wave_error = a-gamma*b-drive
    if not all(np.all(np.isfinite(x)) for x in (a, b, voltage, current, drop, kvl_error, wave_error)):
        raise ValueError('nonfinite circuit solution; rescale the input')
    # Infinity-norm backward residuals, evaluated using a max scale to avoid
    # overflow in sums. An exactly zero excitation has exactly zero residual.
    def residual(error, *terms):
        scale = np.maximum.reduce([np.max(np.abs(x), axis=1) for x in terms])
        return np.max(np.abs(error), axis=1)/np.maximum(scale, np.finfo(float).tiny)
    kvl = residual(kvl_error, vs, voltage, drop)
    wave = residual(wave_error, a, gamma*b, drive)
    if np.any(kvl > 1e-10) or np.any(wave > 1e-10):
        raise ValueError('terminated network residual exceeds 1e-10')
    return TerminatedNetwork(net, vs, zt, a, b, voltage, current, condition, kvl, wave)


@dataclass(frozen=True)
class Crosstalk:
    """Victim terminal voltage / actual aggressor incident voltage, complex.

    ``next_ratio`` and ``fext_ratio`` are frequency ratios, not time-domain peaks.
    ``response`` contains the full solution and the explicit source/load inputs.
    """
    response: TerminatedNetwork
    aggressor: str
    near_victim: str
    far_victim: str
    next_ratio: np.ndarray
    fext_ratio: np.ndarray

    def __post_init__(self):
        for name in ('next_ratio', 'fext_ratio'):
            object.__setattr__(self, name, _snapshot(getattr(self, name)))


def loaded_crosstalk(network, *, aggressor, near_victim, far_victim, terminations=None):
    """Excite one named port with a 1 V peak Thevenin source; report NEXT/FEXT.

    Port geometry is the caller's responsibility. With all ports matched and
    equal real references the ratios equal S[near_victim,aggressor] and
    S[far_victim,aggressor]. Unequal references also include voltage scaling.
    Reject incident voltage <=1e-14 V; no normalization of a vanishing drive.
    """
    if not isinstance(network, LineNetwork):
        raise TypeError('network must be a LineNetwork')
    ports = (aggressor, near_victim, far_victim)
    if (any(not isinstance(p, str) or p not in network.port_names for p in ports)
            or len(set(ports)) != 3):
        raise ValueError('aggressor and victim names must be three distinct network ports')
    response = terminate_network(network, source_voltages={aggressor: 1},
                                 terminations=terminations)
    i, near, far = (network.port_names.index(p) for p in ports)
    incident_voltage = np.sqrt(network.z_ref[i])*response.a[:, i]
    if np.any(np.abs(incident_voltage) <= 1e-14):
        raise ValueError('aggressor incident voltage is too small for reliable normalization')
    with np.errstate(over='ignore', invalid='ignore'):
        next_ratio = response.voltage[:, near]/incident_voltage
        fext_ratio = response.voltage[:, far]/incident_voltage
    if not np.all(np.isfinite([next_ratio, fext_ratio])):
        raise ValueError('nonfinite normalized crosstalk')
    return Crosstalk(response, aggressor, near_victim, far_victim, next_ratio, fext_ratio)
