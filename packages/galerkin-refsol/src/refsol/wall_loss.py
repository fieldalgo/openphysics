# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Conductor-loss quality factor of a homogeneous rectangular cavity (perturbation).

Each wall is a good conductor of conductivity sigma (S/m) with surface resistance
``Rs = sqrt(omega*mu0/(2*sigma))``. The fields are the lossless PEC standing waves

    Ex = Ax cos(kx x) sin(ky y) sin(kz z)   (and cyclic permutations),

with ``k_i = n_i pi / L_i`` and ``A . k = 0``. To first order in ``Rs/eta``:

    Q_c = omega * W / P_c,   W = (mu/2) int |H|^2 dV,   P_c = (Rs/2) sum_walls int |H_t|^2 dS.

For three positive indices the two polarizations are degenerate. Wall loss is a
quadratic form in A; its eigenvectors on the transverse amplitude plane are the
perturbed polarizations, so both Q values are returned. A Leontovich wall has
``Zs = (1 + j) Rs`` under ``exp(+j*omega*t)``; its reactance lowers the real
frequency by the same amount as the loss raises the imaginary part:

    omega = omega0 * (1 + (j - 1) / (2 Q_c))   (first order).

No mesh or FEM code is used; all integrals are closed-form products of
``int sin^2`` and ``int cos^2`` over each side.
"""

from __future__ import annotations

from dataclasses import dataclass
import math

from .cavity import C0

MU0 = 1.25663706212e-6  # vacuum permeability (CODATA 2018), H/m
WALLS = ("x0", "x1", "y0", "y1", "z0", "z1")


@dataclass(frozen=True)
class WallLossMode:
    """One polarization of mode (m, n, p): frequency, Q_c and its amplitude vector."""

    indices: tuple[int, int, int]
    polarization: tuple[float, float, float]
    frequency_hz: float
    quality_factor: float
    complex_frequency_hz: complex


def _positive(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not (
            math.isfinite(value) and value > 0):
        raise ValueError(f"{name} must be a finite positive real number")
    return float(value)


def _conductivities(value):
    if isinstance(value, dict):
        unknown = set(value) - set(WALLS)
        if unknown:
            raise ValueError(f"unknown walls {sorted(unknown)}; use {WALLS}")
        return {w: (None if value.get(w) is None else _positive(value[w], f"sigma[{w}]"))
                for w in WALLS}
    sigma = _positive(value, "wall_conductivity_s_per_m")
    return dict.fromkeys(WALLS, sigma)


def _integral(k, length, kind):
    """int_0^L sin^2(kx) or cos^2(kx) dx for k = n pi / L."""
    if k == 0:
        return 0.0 if kind == "sin" else length
    return length / 2


def _h_components(amplitude, k):
    """Curl of E per component: H_i is proportional to c_i times one trig product.

    Returns coefficients c (curl E = c_i * trig) and, per component, which axes
    carry a sine (the others carry a cosine). Factor -1/(j omega mu) is omitted.
    """
    ax, ay, az = amplitude
    kx, ky, kz = k
    # E_x ~ cos sin sin, E_y ~ sin cos sin, E_z ~ sin sin cos.
    # (curl E)_x = dEz/dy - dEy/dz ~ sin(x) cos(y) cos(z)
    cx = az * ky - ay * kz
    cy = ax * kz - az * kx      # ~ cos(x) sin(y) cos(z)
    cz = ay * kx - ax * ky      # ~ cos(x) cos(y) sin(z)
    sines = ((True, False, False), (False, True, False), (False, False, True))
    return (cx, cy, cz), sines


def _quadratic_forms(lengths, k, conductivities, rs_scale):
    """Volume |curl E|^2 and Rs-weighted wall |curl E_t|^2 as 3x3 forms in A."""
    basis = ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))
    coefficients = [_h_components(e, k)[0] for e in basis]  # coefficients[a][i]
    sines = _h_components(basis[0], k)[1]
    volume = [[0.0] * 3 for _ in range(3)]
    wall = [[0.0] * 3 for _ in range(3)]
    for i in range(3):
        factor = 1.0
        for axis in range(3):
            factor *= _integral(k[axis], lengths[axis], "sin" if sines[i][axis] else "cos")
        loss = 0.0
        for axis in range(3):
            if axis == i or sines[i][axis]:
                continue          # normal component, or tangential component vanishing there
            face = 1.0
            for other in range(3):
                if other != axis:
                    face *= _integral(k[other], lengths[other],
                                      "sin" if sines[i][other] else "cos")
            for side in (0, 1):
                sigma = conductivities[WALLS[2 * axis + side]]
                if sigma is not None:
                    loss += face / math.sqrt(sigma)   # cos^2 = 1 on both sides
        for a in range(3):
            for b in range(3):
                product = coefficients[a][i] * coefficients[b][i]
                volume[a][b] += product * factor
                wall[a][b] += product * loss * rs_scale
    return volume, wall


def wall_loss_modes(lengths_m, max_frequency_hz, wall_conductivity_s_per_m, *,
                    relative_permittivity=1.0, relative_permeability=1.0):
    """Conductor-loss Q of every mode at or below the ceiling, with real ``eps_r, mu_r``.

    ``wall_conductivity_s_per_m`` is one conductivity for all walls or a dict over
    ``WALLS`` ('x0', 'x1', ... 'z1'); a missing or None wall is a perfect conductor.
    The filling only rescales k (``omega = c0 k / sqrt(eps_r mu_r)``) and the energy.
    """
    try:
        lengths = tuple(_positive(v, "lengths_m") for v in lengths_m)
    except TypeError as exc:
        raise ValueError("lengths_m must contain three positive lengths") from exc
    if len(lengths) != 3:
        raise ValueError("lengths_m must contain three positive lengths")
    ceiling = _positive(max_frequency_hz, "max_frequency_hz")
    sigma = _conductivities(wall_conductivity_s_per_m)
    eps = _positive(relative_permittivity, "relative_permittivity")
    mu = _positive(relative_permeability, "relative_permeability")
    speed = C0 / math.sqrt(eps * mu)
    bounds = [int(2 * ceiling * L / speed) + 1 for L in lengths]
    modes = []
    for indices in ((m, n, p) for m in range(bounds[0] + 1) for n in range(bounds[1] + 1)
                    for p in range(bounds[2] + 1)):
        if sum(i > 0 for i in indices) < 2:
            continue
        k = tuple(i * math.pi / L for i, L in zip(indices, lengths))
        wavenumber = math.sqrt(sum(v * v for v in k))
        frequency = speed * wavenumber / (2 * math.pi)
        if frequency > ceiling * (1 + 1e-14):
            continue
        omega = 2 * math.pi * frequency
        # Rs = sqrt(omega mu0 / (2 sigma)); the 1/sqrt(sigma) factor is in the wall form.
        volume, wall = _quadratic_forms(lengths, k, sigma, math.sqrt(omega * MU0 / 2))
        plane = _transverse_basis(k, indices)
        reduced_volume = _project(volume, plane)
        reduced_wall = _project(wall, plane)
        # Q = omega mu0 mu int|curlE|^2 / (Rs-weighted wall |curlE_t|^2): the common
        # 1/(omega mu)^2 between H and curl E cancels.
        for weight, vector in _generalized_eigen(reduced_wall, reduced_volume):
            amplitude = [sum(vector[j] * plane[j][a] for j in range(len(plane)))
                         for a in range(3)]
            norm = math.sqrt(sum(v * v for v in amplitude))
            amplitude = tuple(v / norm for v in amplitude)
            q = math.inf if weight == 0 else omega * MU0 * mu / weight
            shift = 0 if q == math.inf else 1 / (2 * q)
            modes.append(WallLossMode(indices, amplitude, frequency, q,
                                      complex(frequency * (1 - shift), frequency * shift)))
    return sorted(modes, key=lambda m: (m.frequency_hz, m.indices, m.quality_factor))


def _transverse_basis(k, indices):
    """Orthonormal basis of the admissible amplitude plane (A . k = 0, zero-index rule)."""
    positive = [axis for axis in range(3) if indices[axis] > 0]
    if len(positive) == 2:
        zero = next(axis for axis in range(3) if indices[axis] == 0)
        vector = [0.0, 0.0, 0.0]
        vector[zero] = 1.0
        return [tuple(vector)]
    norm = math.sqrt(sum(v * v for v in k))
    unit = [v / norm for v in k]
    seed = min(range(3), key=lambda a: abs(unit[a]))
    first = [-unit[a] * unit[seed] for a in range(3)]
    first[seed] += 1.0
    length = math.sqrt(sum(v * v for v in first))
    first = [v / length for v in first]
    second = [unit[1] * first[2] - unit[2] * first[1],
              unit[2] * first[0] - unit[0] * first[2],
              unit[0] * first[1] - unit[1] * first[0]]
    return [tuple(first), tuple(second)]


def _project(form, plane):
    return [[sum(plane[i][a] * form[a][b] * plane[j][b] for a in range(3) for b in range(3))
             for j in range(len(plane))] for i in range(len(plane))]


def _generalized_eigen(loss, energy):
    """Eigenpairs of loss v = w energy v for 1x1 or symmetric positive 2x2 forms."""
    if len(loss) == 1:
        return [(loss[0][0] / energy[0][0], (1.0,))]
    # Cholesky of the energy form, then a symmetric 2x2 eigenproblem.
    l11 = math.sqrt(energy[0][0])
    l21 = energy[1][0] / l11
    l22 = math.sqrt(energy[1][1] - l21 * l21)
    inv = [[1 / l11, 0.0], [-l21 / (l11 * l22), 1 / l22]]
    c = [[sum(inv[i][a] * loss[a][b] * inv[j][b] for a in range(2) for b in range(2))
          for j in range(2)] for i in range(2)]
    mean, half = (c[0][0] + c[1][1]) / 2, (c[0][0] - c[1][1]) / 2
    radius = math.hypot(half, c[0][1])
    if radius <= 1e-14 * max(abs(mean), 1e-300):
        directions = ([1.0, 0.0], [0.0, 1.0])      # isotropic loss: any basis
        values = (mean, mean)
    elif abs(c[0][1]) > 1e-15 * radius:
        values = (mean - radius, mean + radius)
        directions = tuple([c[0][1], v - c[0][0]] for v in values)
    else:
        values = (c[0][0], c[1][1])
        directions = ([1.0, 0.0], [0.0, 1.0])
    pairs = []
    for value, y in zip(values, directions):
        x1 = y[1] / l22                               # x = L^-T y
        x0 = (y[0] - l21 * x1) / l11
        pairs.append((value, (x0, x1)))
    return pairs


def pozar_te101_quality_factor(a_m, b_m, d_m, wall_conductivity_s_per_m):
    """Textbook TE101 Q_c of an air-filled a x b x d box (b the field direction).

    Q_c = (k a d)^3 b eta0 / (2 pi^2 Rs) / (2 a^3 b + 2 b d^3 + a^3 d + a d^3)
    (D. M. Pozar, Microwave Engineering, 4th ed., eq. 6.46).
    """
    a, b, d = (_positive(v, "length") for v in (a_m, b_m, d_m))
    sigma = _positive(wall_conductivity_s_per_m, "wall_conductivity_s_per_m")
    k = math.pi * math.sqrt(1 / a**2 + 1 / d**2)
    omega = C0 * k
    rs = math.sqrt(omega * MU0 / (2 * sigma))
    eta0 = MU0 * C0
    return (k * a * d) ** 3 * b * eta0 / (2 * math.pi**2 * rs) / (
        2 * a**3 * b + 2 * b * d**3 + a**3 * d + a * d**3)
