# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""The one place galerkin converts a complex value between its public and its kernels' convention.

Private (rule 5 of the galerkin step). galerkin's public complex values follow exp(-i omega t):
a passive loss is Im(relative_permittivity) >= 0, Im(effective_index) >= 0, a decaying resonance
has Im(resonant_frequency) < 0. The kernels keep the convention they compute in, exp(+i omega t)
(electrostatics, waveguide, mode_coordinates, mode_overlap, material_cavity); a value changes
convention only here, so the conjugations elsewhere in galerkin are mathematics (Hermitian
products, phase fixes), each listed with its reason by the repository's conventions test (P3-4).
``radial_pml_coeffs`` already computes in exp(-i omega t) and is never converted.

A public complex output is ``to_public(kernel(to_kernel(x)))``, never re-derived in exp(-i omega t):
the kernels are conjugation-equivariant in value but not in the sign of a zero imaginary part.

- ``to_kernel(x)``, a public input into the kernel convention:
  - a Python or NumPy complex scalar: ``complex(x.real, 0.0 - x.imag)``;
  - a NumPy complex array: ``out = np.empty(x.shape, complex); out.real = x.real;
    out.imag = 0.0 - x.imag``. It keeps a -0.0 real part (``x.real + 1j*(...)`` would not), and an
    imaginary part of +-0.0 reaches the kernel as +0.0 (``np.conj`` would give -0.0 for +0.0,
    which moves saved bytes: map M2 4.3);
  - a JAX or PyTorch complex array: ``xp.conj(x)``, so derivatives pass.
- ``to_public(y)``, a kernel output into the public convention: ``np.conj(y)`` for a NumPy array
  or scalar (a Python complex stays a Python complex), ``xp.conj(y)`` for a JAX or PyTorch array.

Anything that is not complex (a real number or array, None, a mapping, an object) is returned as
it is: real values have no convention, so real inputs and outputs keep their exact doubles and
types. The bit rules hold for NumPy and scalar values; no simcase path is live.
"""
import numpy as np

from .core.backend import is_live, namespace

__all__ = ["to_kernel", "to_public"]


def _complex_scalar(value) -> bool:
    return isinstance(value, (complex, np.complexfloating))


def _complex_array(value) -> bool:
    return isinstance(value, np.ndarray) and value.dtype.kind == "c"


def _complex_live(value) -> bool:
    if not is_live(value):
        return False
    xp = namespace(value)
    return xp.isdtype(value.dtype, "complex floating")


def to_kernel(x):
    """``x`` (exp(-i omega t)) in the kernels' exp(+i omega t) convention: Im negated as ``0.0 - Im``."""
    if _complex_scalar(x):
        return complex(x.real, 0.0 - x.imag)
    if _complex_array(x):
        out = np.empty(x.shape, complex)
        out.real = x.real
        out.imag = 0.0 - x.imag
        return out
    if _complex_live(x):
        return namespace(x).conj(x)
    return x


def to_public(y):
    """``y`` (a kernel's exp(+i omega t) value) in the public exp(-i omega t) convention: ``conj``."""
    if type(y) is complex:
        return complex(np.conj(y))
    if _complex_scalar(y) or _complex_array(y):
        return np.conj(y)
    if _complex_live(y):
        return namespace(y).conj(y)
    return y
