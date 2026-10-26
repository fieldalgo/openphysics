# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Quasi-static (quasi-TEM) per-unit-length parameters of a multiconductor line.

A transmission line whose conductors run along z and whose cross-section is
small against the wavelength carries a quasi-TEM wave. Its per-unit-length
capacitance and inductance follow from two 2D electrostatic problems on the
cross-section (Paul, *Analysis of Multiconductor Transmission Lines*, ch. 5):

    div(eps grad V) = 0   outside the conductors,   V = V_k on conductor k

- C  (F/m): Maxwell capacitance matrix with the real dielectrics.
- C0 (F/m): the same matrix with every dielectric replaced by vacuum.
- L  (H/m): L = mu0 eps0 C0^{-1}, exact for TEM lines in homogeneous
            non-magnetic media and the standard quasi-TEM approximation
            otherwise.
- G  (S/m): a lossy dielectric eps0 eps_r (1 - j tan d) makes the solved
            capacitance complex, C_c = C - j C_loss, and G = omega C_loss.
            With a frequency-independent tan d, C_loss is one number per
            entry and G grows linearly with frequency.

Conductor loss R is not computed here: it needs the current distribution on
the conductor surfaces and the skin depth, a separate formulation.

The capacitance entries come from the discrete energy, C_ij = eps0 V_i^T K V_j,
where V_j is the solved potential with conductor j at 1 V and every other
conductor (and the ground) at 0 V. The matrix is symmetric by construction and
equal to the charge read from the residual K V on each conductor.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.constants import c as SPEED_OF_LIGHT
from scipy.constants import epsilon_0, mu_0

from galerkin import Mesh, assemble_stiffness, solve_dirichlet

__all__ = ["LineParameters", "capacitance_matrix", "line_parameters"]


def _node_set(name, nodes, num_nodes):
    idx = np.unique(np.asarray(nodes, dtype=int).ravel())
    if idx.size == 0:
        raise ValueError(f"conductor {name!r} has no mesh nodes")
    if idx.min() < 0 or idx.max() >= num_nodes:
        raise ValueError(f"conductor {name!r} refers to nodes outside the mesh")
    return idx


def capacitance_matrix(mesh: Mesh, eps_r, signals: dict, ground) -> np.ndarray:
    """Maxwell capacitance matrix (F/m) of the signal conductors.

    mesh:    galerkin ``Mesh`` of the dielectric around the conductors, in metres
    eps_r:   relative permittivity, a scalar or one value per triangle; complex
             values eps' (1 - j tan d) give a complex matrix C - j C_loss
    signals: {name: node indices} for each signal conductor, in matrix order
    ground:  node indices held at 0 V (reference conductors). Mesh boundary
             nodes in neither set are insulated (zero normal D).
    """
    if not signals:
        raise ValueError("at least one signal conductor is needed")
    n = mesh.num_nodes
    ground_idx = _node_set("ground", ground, n)
    sets = [_node_set(name, nodes, n) for name, nodes in signals.items()]
    seen = ground_idx
    for name, idx in zip(signals, sets):
        if np.intersect1d(seen, idx).size:
            raise ValueError(f"conductor {name!r} shares mesh nodes with another conductor "
                             "or the ground; conductors must not touch")
        seen = np.union1d(seen, idx)

    eps_r = np.asarray(eps_r)
    if eps_r.ndim not in (0, 1) or (eps_r.ndim == 1 and eps_r.shape[0] != mesh.num_triangles):
        raise ValueError("eps_r must be a scalar or one value per triangle")
    if not np.all(np.isfinite(eps_r)) or np.any(np.real(eps_r) <= 0):
        raise ValueError("eps_r must be finite with a positive real part")
    if np.any(np.imag(eps_r) > 0):
        raise ValueError("a passive dielectric has Im(eps_r) <= 0 (eps' (1 - j tan d))")

    K = assemble_stiffness(mesh, eps_r)
    zero = np.zeros(n, dtype=K.dtype)
    potentials = []
    for j in range(len(sets)):
        bc = {tuple(ground_idx): 0.0}
        for k, idx in enumerate(sets):
            bc[tuple(idx)] = 1.0 if k == j else 0.0
        potentials.append(solve_dirichlet(K, zero, bc))
    V = np.stack(potentials, axis=1)
    C = epsilon_0 * (V.T @ (K @ V))
    return 0.5 * (C + C.T)


@dataclass(frozen=True)
class LineParameters:
    """Per-unit-length parameters of an N-conductor quasi-TEM line.

    names:   signal conductor names, the row/column order of every matrix
    C:       capacitance matrix with the dielectrics (F/m)
    C0:      capacitance matrix in vacuum (F/m)
    L:       inductance matrix (H/m)
    C_loss:  loss part of the complex capacitance (F/m); G = 2 pi f C_loss
    """

    names: tuple[str, ...]
    C: np.ndarray
    C0: np.ndarray
    L: np.ndarray
    C_loss: np.ndarray

    def G(self, frequency: float) -> np.ndarray:
        """Conductance matrix (S/m) at ``frequency`` (Hz), constant tan d."""
        return 2.0 * np.pi * float(frequency) * self.C_loss

    def _single(self):
        if len(self.names) != 1:
            raise ValueError("this quantity is defined for a single signal conductor; "
                             "use modes() or even_odd() for coupled lines")
        return self.C[0, 0], self.C0[0, 0], self.L[0, 0]

    @property
    def z0(self) -> float:
        """Characteristic impedance (ohm) of a single lossless line."""
        C, _, L = self._single()
        return float(np.sqrt(L / C))

    @property
    def eps_eff(self) -> float:
        """Effective relative permittivity C / C0 of a single line."""
        C, C0, _ = self._single()
        return float(C / C0)

    @property
    def phase_velocity(self) -> float:
        """Phase velocity (m/s) of a single lossless line."""
        return SPEED_OF_LIGHT / np.sqrt(self.eps_eff)

    @property
    def delay(self) -> float:
        """Propagation delay per unit length (s/m) of a single lossless line."""
        return 1.0 / self.phase_velocity

    def loss_tangent(self) -> float:
        """Effective loss tangent C_loss / C of a single line."""
        C, _, _ = self._single()
        return float(self.C_loss[0, 0] / C)

    def modes(self):
        """Lossless quasi-TEM modes: (eps_eff per mode, voltage eigenvectors).

        Voltage modes solve (L C) v = v / u^2 with phase velocity u; the modal
        effective permittivity is (c / u)^2. Modes are sorted from slowest.
        """
        w, vecs = np.linalg.eig(self.L @ self.C)
        eps = np.real(w) * SPEED_OF_LIGHT ** 2
        order = np.argsort(eps)[::-1]
        return eps[order], np.real(vecs[:, order])

    def even_odd(self, rtol: float = 1e-2) -> dict:
        """Even/odd-mode parameters of a symmetric coupled pair.

        Requires two signal conductors with equal self terms to ``rtol``. A
        mesh is not mirror-symmetric, so the two self terms of a symmetric
        geometry differ by the discretization error; their mean is used.
        Returns impedances in ohm: z_even, z_odd, z_diff = 2 z_odd and
        z_common = z_even / 2, and eps_eff_even, eps_eff_odd.
        """
        if len(self.names) != 2:
            raise ValueError("even/odd modes need exactly two signal conductors")
        for M, label in ((self.C, "C"), (self.C0, "C0")):
            if not np.isclose(M[0, 0], M[1, 1], rtol=rtol, atol=0.0):
                raise ValueError(f"the pair is not symmetric: {label}[0,0] != {label}[1,1]")
        def self_term(M):
            return 0.5 * (M[0, 0] + M[1, 1])

        out = {}
        for mode, sign in (("even", 1.0), ("odd", -1.0)):
            Cm = self_term(self.C) + sign * self.C[0, 1]
            C0m = self_term(self.C0) + sign * self.C0[0, 1]
            Lm = self_term(self.L) + sign * self.L[0, 1]
            out[f"z_{mode}"] = float(np.sqrt(Lm / Cm))
            out[f"eps_eff_{mode}"] = float(Cm / C0m)
        out["z_diff"] = 2.0 * out["z_odd"]
        out["z_common"] = 0.5 * out["z_even"]
        return out


def line_parameters(mesh: Mesh, eps_r, signals: dict, ground,
                    tan_delta=0.0) -> LineParameters:
    """Solve C, C0, L and C_loss on one mesh.

    eps_r and tan_delta are scalars or one value per triangle. The dielectric
    is eps0 eps_r (1 - j tan_delta); the vacuum problem uses eps_r = 1.
    """
    eps_r = np.asarray(eps_r, dtype=float)
    tan_delta = np.asarray(tan_delta, dtype=float)
    if np.any(tan_delta < 0) or not np.all(np.isfinite(tan_delta)):
        raise ValueError("tan_delta must be finite and >= 0")
    lossy = np.any(tan_delta > 0)
    eps = eps_r * (1.0 - 1j * tan_delta) if lossy else eps_r
    Cc = capacitance_matrix(mesh, eps, signals, ground)
    C0 = capacitance_matrix(mesh, 1.0, signals, ground)
    L = mu_0 * epsilon_0 * np.linalg.inv(C0)
    return LineParameters(names=tuple(signals), C=np.real(Cc), C0=C0, L=L,
                          C_loss=-np.imag(Cc) if lossy else np.zeros_like(C0))
