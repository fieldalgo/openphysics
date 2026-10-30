# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Uniform passive multiconductor lines; exp(+j omega t), SI units.

RLGC are inputs, not a conductor-loss or dispersive-material extraction model.
Port order is all near conductors followed by all far conductors. Currents at
both ends point into the network; positive transmission has negative phase.
"""
from __future__ import annotations

from dataclasses import dataclass
from numbers import Real

import numpy as np
from scipy.linalg import expm

__all__ = ['LineNetwork', 'rlgc_network', 'quasistatic_network']


def _real(name, value):
    raw = np.asarray(value)
    if (raw.dtype.kind not in 'iuf' or not np.all(np.isfinite(raw))
            or any(isinstance(x, (bool, np.bool_))
                   for x in np.asarray(value, dtype=object).flat)):
        raise ValueError(f'{name} must contain finite real numbers (not booleans)')
    return np.array(raw, dtype=float, copy=True)


def _scalar(name, value, *, zero=False):
    if isinstance(value, bool) or not isinstance(value, Real) or not np.isfinite(value):
        raise ValueError(f'{name} must be a finite real scalar')
    if value < 0 or (value == 0 and not zero):
        raise ValueError(f'{name} must be {">= 0" if zero else "> 0"}')
    return float(value)


def _frequencies(value):
    f = _real('frequency', value)
    if f.ndim != 1 or not len(f) or np.any(f < 0) or np.any(np.diff(f) <= 0):
        raise ValueError('frequency must be a nonempty increasing array in Hz, >= 0')
    return f


def _matrix(name, value, count, n=None):
    m = _real(name, value)
    if m.ndim == 2:
        m = np.broadcast_to(m, (count, *m.shape)).copy()
    if m.ndim != 3 or m.shape[0] != count or m.shape[1] != m.shape[2] or m.shape[1] == 0:
        raise ValueError(f'{name} needs shape (N,N) or (frequencies,N,N)')
    if n is not None and m.shape[1] != n:
        raise ValueError('R, L, G and C must have the same conductor count')
    for row in m:
        scale = np.max(np.abs(row))
        if np.max(np.abs(row-row.T)) > 1e-12*scale:
            raise ValueError(f'{name} must be symmetric')
        eigenvalues = np.linalg.eigvalsh((row+row.T)/2)
        if name in ('L', 'C'):
            if eigenvalues[0] <= 0:
                raise ValueError(f'{name} must be positive definite')
        elif eigenvalues[0] < -1e-12*scale:
            raise ValueError(f'{name} must be positive semidefinite')
    return (m + m.swapaxes(-1, -2))/2


@dataclass(frozen=True)
class LineNetwork:
    """Frequency samples and power-normalized S, with positive real port Z.

    Arrays are copied and made read-only. ``port_names`` documents order;
    ``basis`` is either single-ended or mixed-mode. No passivity/causality claim
    is inferred for arbitrary externally constructed S arrays.
    """
    frequency: np.ndarray
    s: np.ndarray
    z_ref: np.ndarray
    port_names: tuple[str, ...]
    basis: str = 'single-ended'

    def __post_init__(self):
        f = _frequencies(self.frequency)
        s = np.array(self.s, dtype=complex, copy=True)
        names = tuple(self.port_names)
        n = len(names)
        if (not n or any(not isinstance(x, str) or not x.strip() or '\n' in x or '\r' in x
                         for x in names) or len(set(names)) != n):
            raise ValueError('port_names must be unique nonempty single-line strings')
        if s.shape != (len(f), n, n) or not np.all(np.isfinite(s)):
            raise ValueError('s must be finite with shape (frequencies,ports,ports)')
        z = _real('z_ref', self.z_ref)
        if z.ndim == 0:
            z = np.full(n, float(z))
        if z.shape != (n,) or np.any(z <= 0):
            raise ValueError('z_ref must be positive, scalar or one real value per port')
        if self.basis not in ('single-ended', 'mixed-mode'):
            raise ValueError('unsupported port basis')
        for key, value in (('frequency', f), ('s', s), ('z_ref', z)):
            value.setflags(write=False)
            object.__setattr__(self, key, value)
        object.__setattr__(self, 'port_names', names)

    def mixed_mode(self):
        """Convert near+/near-/far+/far- to d_near,d_far,c_near,c_far.

        Requires four single-ended ports with the same reference impedance.
        Differential reference is 2 Zref; common reference is Zref/2.
        """
        if (self.basis != 'single-ended' or len(self.port_names) != 4
                or not np.all(self.z_ref == self.z_ref[0])):
            raise ValueError('mixed_mode needs four equal-reference single-ended ports')
        u = np.array([[1, -1, 0, 0], [0, 0, 1, -1],
                      [1, 1, 0, 0], [0, 0, 1, 1]])/np.sqrt(2)
        return LineNetwork(self.frequency, u @ self.s @ u.T,
                           self.z_ref[0]*np.array([2, 2, .5, .5]),
                           ('d_near', 'd_far', 'c_near', 'c_far'), 'mixed-mode')

    def touchstone(self):
        """Return Touchstone 2.0 text (Hz, S, real/imaginary, full matrix).

        Single-ended networks only. Mixed-mode export requires additional
        ordering metadata and is deliberately rejected. No file is written.
        Use a .sNp file name with N equal to the number of ports.
        """
        if self.basis != 'single-ended':
            raise ValueError('Touchstone export currently requires single-ended ports')
        n = len(self.port_names)
        rows = ['[Version] 2.0', f'# Hz S RI R {self.z_ref[0]:.17g}',
                f'[Number of Ports] {n}', f'[Number of Frequencies] {len(self.frequency)}',
                '[Reference] ' + ' '.join(f'{x:.17g}' for x in self.z_ref),
                '[Matrix Format] Full']
        if n == 2:
            rows.append('[Two-Port Data Order] 21_12')
        rows.extend(f'! Port {i+1}: {name}'.encode('ascii', errors='backslashreplace').decode('ascii')
                    for i, name in enumerate(self.port_names))
        rows.append('[Network Data]')
        for f, s in zip(self.frequency, self.s):
            # Touchstone's two-port order is S11,S21,S12,S22; N>=3 is row-major.
            flat = s.T.ravel() if n == 2 else s.ravel()
            rows.append(' '.join([f'{f:.17g}', *(f'{x:.17g}' for v in flat
                                                for x in (v.real, v.imag))]))
        rows.append('[End]')
        return '\n'.join(rows)+'\n'


def _cascade(a, b):
    """Connect a's far ports to b's near ports in the same conductor order."""
    n = len(a)//2
    a11, a12, a21, a22 = a[:n, :n], a[:n, n:], a[n:, :n], a[n:, n:]
    b11, b12, b21, b22 = b[:n, :n], b[:n, n:], b[n:, :n], b[n:, n:]
    xy = np.linalg.solve(np.eye(n)-b11@a22, np.hstack((b11@a21, b12)))
    x, y = xy[:, :n], xy[:, n:]
    return np.block([[a11+a12@x, a12@y],
                     [b21@(a21+a22@x), b22+b21@a22@y]])


def rlgc_network(frequency, *, R, L, G, C, length, z_ref=50.0, names=None):
    """S of a reciprocal passive uniform N-conductor transmission line.

    frequency: increasing 1D Hz samples, including DC if desired.
    R,L,G,C: real symmetric (N,N) or (F,N,N), in ohm/m,H/m,S/m,F/m.
    L,C must be positive definite; R,G positive semidefinite. Only roundoff
    (1e-12 relative matrix scale) in symmetry/semidefiniteness is allowed.
    length: metres, >=0. z_ref: one positive real ohm value for all ports.
    names: N conductor names; port order near names, then far names.

    expm is evaluated on a short normalized section and cascaded by doubling,
    avoiding exponentially growing transfer matrices for highly lossy lines.
    Frequency sampling does not establish causality, material validity or the
    quasi-TEM approximation. Supply the actual applicable RLGC model.
    """
    f = _frequencies(frequency)
    length = _scalar('length', length, zero=True)
    z_ref = _scalar('z_ref', z_ref)
    l = _matrix('L', L, len(f))
    n = l.shape[1]
    r, g, c = (_matrix(key, value, len(f), n) for key, value in
               (('R', R), ('G', G), ('C', C)))
    names = tuple(str(i+1) for i in range(n)) if names is None else tuple(names)
    if (len(names) != n or any(not isinstance(x, str) or not x.strip()
                              or '\n' in x or '\r' in x for x in names)
            or len(set(names)) != n):
        raise ValueError('names must have one unique single-line string per conductor')
    ports = tuple('near:'+x for x in names) + tuple('far:'+x for x in names)
    eye, zero = np.eye(n), np.zeros((n, n))
    result = []
    for i, freq in enumerate(f):
        z = (r[i]+2j*np.pi*freq*l[i])/z_ref
        y = (g[i]+2j*np.pi*freq*c[i])*z_ref
        with np.errstate(over='ignore', invalid='ignore'):
            generator = np.block([[zero, z], [y, zero]])*length
            norm = np.linalg.norm(generator, ord=1)
        if not np.isfinite(norm) or norm > 2**50:
            raise ValueError('electrical length is too large for reliable evaluation')
        doubles = max(0, int(np.ceil(np.log2(norm)))) if norm else 0
        t = expm(generator/(2**doubles))
        a, b, c1, d = t[:n, :n], t[:n, n:], t[n:, :n], t[n:, n:]
        lower = np.linalg.solve(a+b+c1+d, np.hstack((2*eye, -(a-b+c1-d))))
        s21, s22 = lower[:, :n], lower[:, n:]
        s = np.block([[(a+b)@s21-eye, (a+b)@s22+a-b], [s21, s22]])
        for _ in range(doubles):
            s = _cascade(s, s)
        if not np.all(np.isfinite(s)):
            raise ValueError('network calculation produced nonfinite values')
        result.append(s)
    return LineNetwork(f, result, z_ref, ports)


def quasistatic_network(parameters, frequency, *, length, R, z_ref=50.0):
    """Use extracted C/L and G(f)=2*pi*f*C_loss with explicit conductor R.

    R=0 (as an N by N zero matrix) explicitly selects a perfect conductor.
    The extraction does not supply skin effect, roughness or material dispersion.
    """
    from .quasistatic import LineParameters
    if not isinstance(parameters, LineParameters):
        raise TypeError('parameters must be LineParameters')
    f = _frequencies(frequency)
    g = np.array([parameters.G(x) for x in f])
    return rlgc_network(f, R=R, L=parameters.L, G=g, C=parameters.C,
                        length=length, z_ref=z_ref, names=parameters.names)
