# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Strict single-ended Touchstone S input and explicit-condition comparison.

No file/network I/O, guessed port correspondence, impedance renormalization,
extrapolation or material fitting. Arbitrary imported S need not be passive.
"""
from __future__ import annotations

from dataclasses import dataclass
from numbers import Integral
import re

import numpy as np

from .network import LineNetwork

__all__ = ['loads_touchstone', 'NetworkComparison', 'compare_networks']

_UNITS = {'hz':1.,'khz':1e3,'mhz':1e6,'ghz':1e9}
_NUMBER = re.compile(r'[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?\Z')


def _number(value):
    if not _NUMBER.fullmatch(value):
        raise ValueError(f'invalid Touchstone number: {value!r}')
    result = float(value)
    if not np.isfinite(result):
        raise ValueError('Touchstone numbers must be finite')
    return result


def _count(value):
    if not re.fullmatch(r'[0-9]+',value) or int(value) <= 0:
        raise ValueError('Touchstone counts must be positive integers')
    return int(value)


def _options(line):
    unit,form,resistance = 'ghz','ma',50.
    words,seen = line[1:].lower().split(),set()
    i = 0
    while i < len(words):
        word = words[i]
        if word in _UNITS:
            key,unit = 'unit',word
        elif word in ('ri','ma','db'):
            key,form = 'format',word
        elif word in ('s','y','z','h','g'):
            key = 'parameter'
            if word != 's':
                raise ValueError('only Touchstone S parameters are supported')
        elif word == 'r':
            key = 'reference'
            i += 1
            if i == len(words):
                raise ValueError('R needs a positive reference resistance')
            resistance = _number(words[i])
            if resistance <= 0:
                raise ValueError('reference resistance must be positive')
        else:
            raise ValueError(f'unsupported option token: {word!r}')
        if key in seen:
            raise ValueError('duplicate option category')
        seen.add(key)
        i += 1
    return _UNITS[unit],form,resistance


def loads_touchstone(text, *, ports=None, port_names=None):
    """Read strict Touchstone 1.0/2.0 single-ended S samples into LineNetwork.

    Version 1 requires an explicit positive ports count. Version 2 declares it;
    a supplied count must match. Port names are caller-specified in file order,
    or neutral port1,port2,... labels; comments never assign physical pairing.
    RI/MA/DB, real positive per-port references and Full/Lower/Upper matrices
    are supported. Mixed-mode, noise and non-S parameters are rejected.
    """
    if not isinstance(text,str) or any(ord(c)>126 or (ord(c)<32 and c not in '\t\r\n') for c in text):
        raise ValueError('Touchstone input must be ASCII text')
    if ports is not None and (isinstance(ports,bool) or not isinstance(ports,Integral) or ports <= 0):
        raise ValueError('ports must be a positive integer')
    lines = [line.split('!',1)[0].rstrip() for line in text.splitlines()]
    lines = [line for line in lines if line.strip()]
    if not lines:
        raise ValueError('empty Touchstone input')
    version2 = bool(re.fullmatch(r'\[version\][ \t]+2\.0',lines[0],re.I))
    if version2:
        lines = lines[1:]
    elif lines[0].lstrip().startswith('['):
        raise ValueError('unsupported or malformed Touchstone version')
    if not lines or not lines[0].lstrip().startswith('#'):
        raise ValueError('Touchstone option line is required first')
    scale,form,reference = _options(lines[0].lstrip())
    lines = lines[1:]
    metadata,values,rows = {},[],[]
    data,ended,information = not version2,False,False
    pending_reference = False
    for line in lines:
        stripped = line.strip()
        if ended:
            raise ValueError('content after [End]')
        if information:
            if stripped.lower() == '[end information]':
                information = False
            continue
        if stripped.startswith('#'):
            raise ValueError('multiple option lines are not supported')
        if stripped.startswith('['):
            if not version2 or not line.startswith('['):
                raise ValueError('version-2 keywords must start in column one')
            match = re.fullmatch(r'\[([A-Za-z -]+)\](?:[ \t]+(.*))?',line)
            if not match:
                raise ValueError('malformed Touchstone keyword')
            key,arg = match.group(1).lower(),(match.group(2) or '').strip()
            if key != key.strip() or '  ' in key:
                raise ValueError('malformed Touchstone keyword spacing')
            if key in metadata:
                raise ValueError(f'duplicate keyword: {key}')
            if key == 'end':
                if not data or arg:
                    raise ValueError('[End] must follow network data without arguments')
                ended = True
                continue
            if data:
                raise ValueError('only [End] is supported after network data')
            if not metadata and key != 'number of ports':
                raise ValueError('[Number of Ports] must follow the option line')
            if key in ('number of ports','number of frequencies'):
                metadata[key] = _count(arg)
            elif key == 'reference':
                metadata[key] = [_number(v) for v in arg.split()]
            elif key == 'matrix format' and arg.lower() in ('full','lower','upper'):
                metadata[key] = arg.lower()
            elif key == 'two-port data order' and arg.lower() in ('21_12','12_21'):
                metadata[key] = arg.lower()
            elif key == 'begin information' and not arg:
                metadata[key],information = True,True
            elif key == 'network data' and not arg:
                if 'number of frequencies' not in metadata:
                    raise ValueError('[Number of Frequencies] is required before data')
                metadata[key],data = True,True
            else:
                raise ValueError(f'unsupported keyword or argument: {key}')
            pending_reference = key == 'reference'
        elif pending_reference and not data:
            metadata['reference'].extend(_number(v) for v in stripped.split())
        elif data:
            row = [_number(v) for v in stripped.split()]
            values.extend(row)
            rows.append(len(row))
        else:
            raise ValueError('numeric data before [Network Data]')
    if information or (version2 and (not ended or not data)):
        raise ValueError('unterminated Touchstone block')
    n = metadata.get('number of ports',ports)
    if n is None:
        raise ValueError('version 1 requires an explicit ports count')
    if ports is not None and ports != n:
        raise ValueError('ports count does not match the file')
    if version2 and (('two-port data order' in metadata) != (n == 2)):
        raise ValueError('[Two-Port Data Order] is required exactly for two-port files')
    matrix = metadata.get('matrix format','full')
    entries = n*n if matrix == 'full' else n*(n+1)//2
    width = 1+2*entries
    if not values or len(values)%width:
        raise ValueError('incomplete Touchstone frequency record')
    if not version2 and n <= 2 and any(size != width for size in rows):
        raise ValueError('version-1 one/two-port records need one complete row; noise is unsupported')
    count = len(values)//width
    if version2 and count != metadata['number of frequencies']:
        raise ValueError('frequency count does not match the data')
    z = metadata.get('reference',[reference]*n)
    if len(z) != n or np.any(np.asarray(z) <= 0):
        raise ValueError('[Reference] must give one positive resistance per port')
    raw = np.asarray(values).reshape(count,width)
    pairs = raw[:,1:].reshape(count,entries,2)
    with np.errstate(over='ignore',invalid='ignore'):
        if form == 'ri':
            complex_values = pairs[:,:,0]+1j*pairs[:,:,1]
        else:
            magnitude = pairs[:,:,0]
            if form == 'ma' and np.any(magnitude < 0):
                raise ValueError('MA magnitudes cannot be negative')
            if form == 'db':
                magnitude = np.power(10.,magnitude/20)
            complex_values = magnitude*np.exp(1j*np.deg2rad(pairs[:,:,1]))
        frequency = raw[:,0]*scale
    if matrix == 'full':
        s = complex_values.reshape(count,n,n)
        if n == 2 and metadata.get('two-port data order','21_12') == '21_12':
            s = s.swapaxes(1,2)
    else:
        i,j = np.tril_indices(n) if matrix == 'lower' else np.triu_indices(n)
        s = np.empty((count,n,n),dtype=complex)
        s[:,i,j] = complex_values
        s[:,j,i] = complex_values  # Symmetry is transpose, not conjugate transpose.
    names = tuple(f'port{i+1}' for i in range(n)) if port_names is None else tuple(port_names)
    if len(names) != n:
        raise ValueError('port_names count must match the file')
    return LineNetwork(frequency,s,z,names)


@dataclass(frozen=True)
class NetworkComparison:
    """Model-minus-measured complex residual at model frequencies; no fit claim."""
    measured: LineNetwork
    model: LineNetwork
    interpolation: str

    @property
    def delta_s(self):
        result = self.model.s-self.measured.s
        result.setflags(write=False)
        return result

    @property
    def max_abs_error(self):
        return float(np.max(abs(self.delta_s)))


def compare_networks(measured,model,*,interpolation='none'):
    """Align measured samples to model frequencies under explicit conditions.

    Port names/order, basis and real reference impedances must match exactly.
    Default requires each model frequency in the measured samples. Opt-in
    'linear' interpolates real and imaginary S against Hz, within the measured
    range only. It does not establish causality, passivity or sampling adequacy.
    """
    if not isinstance(measured,LineNetwork) or not isinstance(model,LineNetwork):
        raise TypeError('comparison requires LineNetwork inputs')
    if (measured.port_names != model.port_names or measured.basis != model.basis
            or not np.array_equal(measured.z_ref,model.z_ref)):
        raise ValueError('port order, basis and reference impedances must match explicitly')
    if interpolation not in ('none','linear'):
        raise ValueError('interpolation must be none or linear')
    f = model.frequency
    if f[0] < measured.frequency[0] or f[-1] > measured.frequency[-1]:
        raise ValueError('comparison cannot extrapolate measured samples')
    if interpolation == 'none':
        indices = np.searchsorted(measured.frequency,f)
        if not np.array_equal(measured.frequency[indices],f):
            raise ValueError('model frequencies are absent from measured samples')
        s = measured.s[indices]
    else:
        flat = measured.s.reshape(len(measured.frequency),-1)
        s = np.column_stack([np.interp(f,measured.frequency,col.real)
                             +1j*np.interp(f,measured.frequency,col.imag) for col in flat.T])
        s = s.reshape(len(f),len(model.port_names),len(model.port_names))
    aligned = LineNetwork(f,s,measured.z_ref,measured.port_names,measured.basis)
    return NetworkComparison(aligned,model,interpolation)
