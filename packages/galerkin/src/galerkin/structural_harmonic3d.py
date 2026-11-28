# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Steady-state harmonic response of a supported tetrahedral solid in SI units."""
from dataclasses import dataclass
from types import MappingProxyType

import numpy as np
from scipy import linalg, sparse
from scipy.sparse.linalg import LinearOperator, onenormest, splu

from . import _elasticity3d
from ._public import ResultSurface, refuse_text
from ._tetra_materials import region_property
from .core.checks import finite_scalar, real_array

__all__ = ["StructuralHarmonic3DResult", "solve_structural_harmonic_3d"]


@dataclass(frozen=True, eq=False)
class StructuralHarmonic3DResult(ResultSurface):
    """Input frequencies, complex nodal displacements, elastic stresses and support forces.

    The leading axis follows the input frequency order. Displacements and reactions
    have shape (F, N, 3), stresses (F, T, 3, 3), and free-equation residuals (F,).
    """

    frequency: np.ndarray
    displacement: np.ndarray
    stress: np.ndarray
    reaction_force: np.ndarray
    relative_residual: np.ndarray

    BASIS = "3d"
    UNITS = MappingProxyType({"frequency": "Hz", "displacement": "m", "stress": "Pa",
                              "reaction_force": "N", "relative_residual": "1"})


def _nonnegative_scalar(value, name):
    if value is None:
        return 0.0
    scalar = finite_scalar(value, name)
    if scalar < 0:
        raise ValueError(f"{name} must be nonnegative")
    return scalar


def _inverse_one_norm(factor):
    size = factor.shape[0]
    if size <= 32:
        return linalg.norm(factor.solve(np.eye(size)), 1)
    # The deterministic one-column estimator starts with ones, which can
    # be orthogonal to an antisymmetric mode. Right multiplication by a
    # diagonal of unit phases preserves the inverse one-norm and gives that
    # first probe distinct phases on the DOFs without using global RNG state.
    phase = np.exp(2j * np.pi * np.random.default_rng(0).random(size))
    inverse = LinearOperator(factor.shape, dtype=complex,
                             matvec=lambda x: factor.solve(phase * x.ravel()),
                             rmatvec=lambda x: phase.conj() * factor.solve(x.ravel(), trans="H"))
    return onenormest(inverse, t=1)


def _solve_free(stiffness, mass, k_weight, m_weight, force, hz):
    dynamic = k_weight * stiffness + m_weight * mass
    # Scale with the *uncancelled* stiffness and inertia. At a one-DOF
    # resonance a rounded K - omega² M may be nonzero and have condition
    # number one, even though all its significant digits have cancelled.
    diagonal = abs(k_weight) * stiffness.diagonal() + abs(m_weight) * mass.diagonal()
    if not np.all(np.isfinite(diagonal) & (diagonal > 0)) or not np.all(np.isfinite(dynamic.data)):
        raise ValueError(f"nonfinite or degenerate structural dynamic stiffness at {hz:g} Hz")
    scale = 1 / np.sqrt(diagonal)
    scaling = sparse.diags(scale)
    matrix = (scaling @ dynamic @ scaling).tocsc()
    try:
        factor = splu(matrix)
    except RuntimeError as exc:
        raise ValueError(f"singular structural dynamic stiffness at {hz:g} Hz") from exc

    if k_weight.imag == 0 and m_weight.imag == 0:
        # Check uniqueness independently of loading, including unloaded
        # resonant modes. The diagonal scaling also handles mixed materials.
        if _inverse_one_norm(factor) * (64 * np.finfo(float).eps) >= 1:
            raise ValueError(f"numerically singular structural dynamic stiffness at {hz:g} Hz")
    return scale * factor.solve(scale * force)


def solve_structural_harmonic_3d(mesh, *, youngs_modulus, poisson_ratio, mass_density,
                                 prescribed_displacement, frequency, body_force_density=None,
                                 traction=None, mass_proportional_damping_coefficient=None,
                                 stiffness_proportional_damping_coefficient=None):
    """Solve [K - omega² M - i omega (alpha M + beta K)] u = f on free components.

    Use a Mesh3D in metres and a nonempty 1D sequence of nonnegative frequencies
    in Hz. Young's modulus (Pa), Poisson ratio and density (kg/m³) may be scalars
    or region mappings. Prescribe zero displacement for enough (node, component)
    pairs to remove the rigid motions of each connected solid.

    The constant volume load (N/m³) and the traction (Pa) on each exterior face
    tag are Cartesian phasors under exp(-i omega t). The Rayleigh coefficients
    alpha (1/s) and beta (s) are nonnegative; None means zero damping for that
    coefficient. Stress is the elastic Cauchy stress.
    Reactions include damping, inertia and external loads on constrained components.
    An undamped frequency with a numerically singular system raises ValueError.
    """
    for name, value in (("youngs_modulus", youngs_modulus), ("poisson_ratio", poisson_ratio),
                        ("mass_density", mass_density), ("prescribed_displacement", prescribed_displacement),
                        ("frequency", frequency), ("body_force_density", body_force_density),
                        ("traction", traction),
                        ("mass_proportional_damping_coefficient", mass_proportional_damping_coefficient),
                        ("stiffness_proportional_damping_coefficient", stiffness_proportional_damping_coefficient)):
        refuse_text(name, value)
    frequencies = real_array(frequency, "frequency")
    if frequencies.ndim != 1 or not frequencies.size or np.any(frequencies < 0):
        raise ValueError("frequency must be a nonempty 1D array of nonnegative frequencies in Hz")
    alpha = _nonnegative_scalar(mass_proportional_damping_coefficient, "mass_proportional_damping_coefficient")
    beta = _nonnegative_scalar(stiffness_proportional_damping_coefficient, "stiffness_proportional_damping_coefficient")
    gradients, volumes = _elasticity3d.element_geometry(mesh)
    _, _, shear, lame = _elasticity3d.elastic_moduli(mesh, youngs_modulus, poisson_ratio)
    density = region_property(mesh, mass_density, "mass_density", positive=True)
    fixed, free = _elasticity3d.supported_dofs(mesh, prescribed_displacement)
    force = _elasticity3d.applied_load(mesh, volumes, body_force_density, traction, complex_amplitude=True).ravel()
    stiffness = _elasticity3d.stiffness_matrix(mesh, gradients, volumes, shear, lame)[:, free]
    mass = _elasticity3d.mass_matrix(mesh, density)[:, free]
    k_free, m_free, f_free = stiffness[free], mass[free], force[free]

    count = frequencies.size
    displacement = np.zeros((count, mesh.num_nodes, 3), dtype=complex)
    stress = np.empty((count, mesh.num_tets, 3, 3), dtype=complex)
    reaction = np.zeros_like(displacement)
    relative = np.zeros(count)
    for j, hz in enumerate(frequencies):
        omega = 2 * np.pi * hz
        k_weight = 1 - 1j * (omega * beta)
        m_weight = -omega * omega - 1j * (omega * alpha)
        if not np.isfinite(k_weight) or not np.isfinite(m_weight):
            raise ValueError(f"frequency or damping exceeds floating-point range at {hz:g} Hz")
        if free.size:
            u = _solve_free(k_free, m_free, k_weight, m_weight, f_free, hz)
            displacement[j].ravel()[free] = u
        else:
            u = np.empty(0, dtype=complex)
        elastic = k_weight * (stiffness @ u)
        inertial = m_weight * (mass @ u)
        residual = elastic + inertial - force
        reaction[j].ravel()[fixed] = residual[fixed]
        _, stress[j] = _elasticity3d.strain_stress(mesh, displacement[j], gradients, shear, lame)
        if not all(np.all(np.isfinite(field)) for field in (u, residual, stress[j])):
            raise ValueError(f"structural harmonic solve produced nonfinite results at {hz:g} Hz")
        denominator = linalg.norm(elastic[free]) + linalg.norm(inertial[free]) + linalg.norm(f_free)
        if not np.isfinite(denominator):
            raise ValueError(f"structural harmonic force norm exceeds floating-point range at {hz:g} Hz")
        if denominator:
            relative[j] = linalg.norm(residual[free]) / denominator
        if not np.isfinite(relative[j]) or relative[j] > 1e-6:
            raise ValueError(f"structural harmonic residual exceeds 1e-6 at {hz:g} Hz")
    return StructuralHarmonic3DResult(frequencies, displacement, stress, reaction, relative)
