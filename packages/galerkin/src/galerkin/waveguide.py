# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Guided modes of a waveguide cross-section: galerkin's public mode API, in SI and exp(-i omega t).

``solve_waveguide_modes`` solves the full-vector modes of a cross-section (mixed Nedelec edge and
nodal elements; the formulation is in docs/packages/galerkin/waveguide_formulation.md) and returns a
frozen ``WaveguideModes``; ``mode_power``, ``cross_power``, ``field_overlap``,
``mode_coupling_efficiency``, ``mode_confinement_factor`` and ``mode_effective_area`` post-process
its modes. ``ModalPML`` and ``Bend`` describe a perfectly matched layer and a constant-radius bend.
``degenerate_branch_derivatives`` returns, as frozen ``DegenerateModeBranches``, the branch slopes
under a shape motion of degenerate modes, which ``solve_waveguide_modes`` with that motion leaves NaN.

Units and convention
--------------------
Quantities are keyword-only registry names in SI units: the mesh is in metres, the vacuum
wavelength in m (or the vacuum angular wavenumber k0 in rad/m, exactly one of the two; k0 is
``2 * pi / vacuum_wavelength``), the PML thicknesses, bend radius and origin in m.
Complex values follow exp(-i omega t): a passive loss has Im(relative_permittivity) >= 0, and a
forward mode of a lossy guide has Im(effective_index) >= 0 (it decays as exp(-k0 Im(n_eff) z)).
The fields have arbitrary amplitude (the solver's gauge), not unit power.

These functions wrap the kernels of ``galerkin.kernels`` (``solve_modes``, ``mode_coordinates`` and
the mode overlaps), which compute in consistent units and exp(+i omega t), and convert in one place,
``galerkin._conventions``: every complex input reaches a kernel through ``to_kernel`` and every
complex output is ``to_public`` of the kernel's output, never re-derived. The result's
``unnormalized_electric_field_z`` is E_z itself (the kernel's ``ez`` has E_z = 1j * ez, a factor that
changes sign under conjugation), and ``unnormalized_electric_field_line_integral`` holds the line
integrals of E_t along the edges of ``space`` (low to high node id), in m for fields in V/m.

With a ``ModalPML`` or a ``Bend`` the fields are covariant components in the stretched or bent
coordinates; outside the PML of a straight guide they are the physical fields, and for a bend the
physical E_z outside the PML is E_z / h with h = 1 + (x - bend_origin) / bend_radius. ``mode_power``
and the other functions then integrate those components over the whole window, PML included.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any

import numpy as np

from ._conventions import to_kernel, to_public
from ._public import refuse_text
from ._waveguide_kernels import STATIC_ROOT_TOL, solve_modes as _solve_modes
from .core.backend import is_live, to_numpy
from .core.checks import contains_live
from .core.eigen import (DEGENERATE_GAP, DegenerateModeWarning,  # noqa: F401 (DEGENERATE_GAP is read here, as before)
                         StaticFamilyNearCutoffWarning)
from .edge import EdgeSpace
from .mode_coordinates import mode_coordinates as _mode_coordinates
from .mode_overlap import (confinement_factor as _confinement_factor, coupling_efficiency as _coupling_efficiency,
                           effective_area as _effective_area, vector_cross_power as _vector_cross_power,
                           vector_field_overlap as _vector_field_overlap, vector_power as _vector_power)

__all__ = ["STATIC_ROOT_TOL", "DegenerateModeWarning", "StaticFamilyNearCutoffWarning", "ModalPML", "Bend", "WaveguideModes",
           "solve_waveguide_modes", "DegenerateModeBranches", "degenerate_branch_derivatives", "mode_power", "cross_power", "field_overlap", "mode_coupling_efficiency",
           "mode_confinement_factor", "mode_effective_area"]

_SIDES = ("left", "right", "bottom", "top")


def _finite_real(value, name, *, positive=False):
    """A finite real Python or NumPy number as float (``refuse_text`` first: a str is a TypeError)."""
    refuse_text(name, value)
    if contains_live(value):
        raise TypeError(f"{name}: a JAX or PyTorch value carries no derivative here; pass a number")
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, (int, float, np.integer, np.floating)):
        raise ValueError(f"{name} must be a finite real number" + (" > 0" if positive else "") + " in SI units")
    value = float(value)
    if not np.isfinite(value) or (positive and value <= 0):
        raise ValueError(f"{name} must be a finite real number" + (" > 0" if positive else "") + " in SI units")
    return value


@dataclass(frozen=True, kw_only=True)
class ModalPML:
    """A Cartesian perfectly matched layer inside the rectangular window of a mode solve.

    pml_thickness: {side: m} for the sides "left", "right", "bottom" and "top" that carry a layer,
        each > 0 (a side without a layer is left out); the layer is a strip of that width inside the
        mesh, which must resolve it and keep a physical window.
    pml_strength: the dimensionless strength of the coordinate stretch (default 3.0).
    pml_order: the order 2, 3 or 4 of its profile (default 2).

    In exp(-i omega t) the stretch is s = 1 + i pml_strength (depth / pml_thickness)^pml_order; the
    solver builds the coordinate factors itself (in its kernels' convention), so no convention-bearing
    array reaches the caller.
    """

    pml_thickness: Mapping[str, float]
    pml_strength: float = 3.0
    pml_order: int = 2

    def __post_init__(self):
        refuse_text("pml_thickness", self.pml_thickness)
        if not isinstance(self.pml_thickness, Mapping) or not self.pml_thickness \
                or set(self.pml_thickness) - set(_SIDES):
            raise ValueError("pml_thickness must map one or more of 'left', 'right', 'bottom' and 'top' to a "
                             "length in m")
        widths = {side: _finite_real(value, f"pml_thickness[{side!r}]", positive=True)
                  for side, value in self.pml_thickness.items()}
        object.__setattr__(self, "pml_thickness", MappingProxyType(widths))
        object.__setattr__(self, "pml_strength", _finite_real(self.pml_strength, "pml_strength", positive=True))
        refuse_text("pml_order", self.pml_order)
        if isinstance(self.pml_order, (bool, np.bool_)) or not isinstance(self.pml_order, (int, np.integer)) \
                or self.pml_order not in (2, 3, 4):
            raise ValueError("pml_order must be 2, 3 or 4")
        object.__setattr__(self, "pml_order", int(self.pml_order))


@dataclass(frozen=True, kw_only=True)
class Bend:
    """A constant-radius bend of the guide.

    bend_radius: the radius in m of the reference arc, > 0, measured from ``bend_origin`` along
        ``bend_axis``; z = bend_radius * theta is the arc length on it. Every point of the mesh
        must lie at a positive radius.
    bend_origin: the coordinate in m of the bend's centre on ``bend_axis`` (no default).
    bend_axis: "x" (default) or "y", the outward axis of the bend.
    """

    bend_radius: float
    bend_origin: float
    bend_axis: str = "x"

    def __post_init__(self):
        object.__setattr__(self, "bend_radius", _finite_real(self.bend_radius, "bend_radius", positive=True))
        object.__setattr__(self, "bend_origin", _finite_real(self.bend_origin, "bend_origin"))
        if self.bend_axis not in ("x", "y"):
            raise ValueError("bend_axis must be 'x' or 'y'")


@dataclass(frozen=True)
class WaveguideModes:
    """The modes of ``solve_waveguide_modes``, sorted by descending Re(effective_index); frozen.

    effective_index: (m,) beta / k0, real for a lossless guide, complex otherwise (exp(-i omega t):
        Im >= 0 for a forward mode of a passive lossy guide).
    unnormalized_electric_field_line_integral: (m, n_e) complex, the line integral of E_t along each
        edge of ``space`` (from its lower to its higher node id), in m for fields in V/m.
    unnormalized_electric_field_z: (m, n_n) complex, the longitudinal field E_z at the nodes.
    space: the ``EdgeSpace`` of the mesh; ``galerkin.kernels.eval_edge_field`` evaluates E_t on it
        (from the line integrals, in the kernels' convention).
    vacuum_angular_wavenumber: k0 in rad/m.
    relative_permittivity, relative_permeability: the materials of the solve, as given.

    The fields have arbitrary amplitude and phase (the solver's gauge); ``mode_power`` gives the
    power they carry. ``.units`` maps each quantity field to its SI unit.
    """

    effective_index: Any
    unnormalized_electric_field_line_integral: Any
    unnormalized_electric_field_z: Any
    space: EdgeSpace
    vacuum_angular_wavenumber: Any
    relative_permittivity: Any
    relative_permeability: Any = field(default=1.0)

    UNITS = MappingProxyType({"effective_index": "1", "unnormalized_electric_field_line_integral": "m",
                              "unnormalized_electric_field_z": "1", "vacuum_angular_wavenumber": "rad/m",
                              "relative_permittivity": "1", "relative_permeability": "1"})

    @property
    def units(self):
        """{field: canonical SI unit} of every quantity field (read-only)."""
        return self.UNITS


def _material(value, name, count):
    """A relative permittivity or permeability: a number, a (T,) array or a live value; text is a TypeError."""
    refuse_text(name, value)
    if is_live(value):
        return value
    if isinstance(value, (bool, np.bool_)):
        raise ValueError(f"{name} must be a finite number or one per triangle")
    if isinstance(value, (int, float, complex, np.number)):
        if not np.isfinite(value):
            raise ValueError(f"{name} must be finite")
        return value
    if contains_live(value):
        raise TypeError(f"{name}: pass one JAX or PyTorch array, not a list of them")
    a = np.asarray(value)
    if a.dtype.kind not in "iufc" or a.shape not in ((), (count,)):
        raise ValueError(f"{name} must be a finite number or an array of one value per triangle, shape ({count},)")
    if not np.isfinite(a).all():
        raise ValueError(f"{name} must be finite")
    return a


def _wavenumber(vacuum_wavelength, vacuum_angular_wavenumber):
    """k0 in rad/m from exactly one of the two: k0 = 2 pi / vacuum_wavelength."""
    refuse_text("vacuum_wavelength", vacuum_wavelength)
    refuse_text("vacuum_angular_wavenumber", vacuum_angular_wavenumber)
    if (vacuum_wavelength is None) == (vacuum_angular_wavenumber is None):
        raise ValueError("give exactly one of vacuum_wavelength (m) and vacuum_angular_wavenumber (rad/m)")
    name, value = (("vacuum_wavelength", vacuum_wavelength) if vacuum_wavelength is not None
                   else ("vacuum_angular_wavenumber", vacuum_angular_wavenumber))
    if is_live(value):
        number = to_numpy(value)
        if number.shape != () or number.dtype.kind not in "iuf" or not np.isfinite(number) or not number > 0:
            raise ValueError(f"{name} must be a finite real number > 0 in SI units")
    else:
        value = _finite_real(value, name, positive=True)
    return 2 * np.pi / value if name == "vacuum_wavelength" else value


def _target(value):
    refuse_text("target_effective_index", value)
    if contains_live(value):
        raise TypeError("target_effective_index only selects the modes and carries no derivative; pass a number")
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, (int, float, complex, np.number)) \
            or not np.isfinite(value) or not value.real > 0:
        raise ValueError("target_effective_index must be a finite number with a positive real part")
    return value


def solve_waveguide_modes(mesh, *, relative_permittivity, vacuum_wavelength=None, vacuum_angular_wavenumber=None,
                          target_effective_index, search_mode_count, relative_permeability=1.0, pec_nodes=None,
                          pec_edges=None, pml=None, bend=None, motion=None) -> WaveguideModes:
    """Full-vector guided modes of a cross-section with effective index near ``target_effective_index``.

    mesh: a ``Mesh`` in metres.
    relative_permittivity, relative_permeability: a number or one value per triangle, real or complex
        (exp(-i omega t): Im >= 0 is a loss); JAX or PyTorch values give the outputs derivatives.
    vacuum_wavelength (m) or vacuum_angular_wavenumber (rad/m): exactly one; k0 = 2 pi / vacuum_wavelength.
    target_effective_index: the shift of the eigensolve, real or complex; the core index is the
        natural choice, since guided modes lie just below it.
    search_mode_count: how many eigenpairs the shift-invert search computes; static roots
        (beta^2 = 0) and, without a PML, backward or nonfinite roots are dropped, so at most this many
        modes return.
    pec_nodes, pec_edges: the nodes whose E_z and the edges whose tangential E are zero (PEC);
        pec_nodes defaults to every boundary node, pec_edges to the boundary edges with both ends in
        pec_nodes. An open guide is truncated by a PEC wall where the field has died, or by a ``ModalPML``.
    pml: a ``ModalPML``; bend: a ``Bend`` (it needs a ``pml``). Every returned candidate is kept with a
        PML: classifying physical modes is the caller's task.
    motion: ``galerkin.shape.MeshMotion(design_velocity=..., t=...)`` solves on the nodes
        X0 + t design_velocity, with the derivative with respect to a JAX or PyTorch t. With a ``pml``
        the design velocity must be 0 on every node of a PML element (the layer stays put) and
        tangential on the outer faces; with a ``bend`` the window elements move, and their bend factor
        follows the nodes.

    Returns a ``WaveguideModes``. A mode whose eigenvalue lies within a relative ``DEGENERATE_GAP`` of
    another one has NaN derivatives and raises ``DegenerateModeWarning``.
    """
    count = mesh.num_triangles
    eps = _material(relative_permittivity, "relative_permittivity", count)
    mu = _material(relative_permeability, "relative_permeability", count)
    k0 = _wavenumber(vacuum_wavelength, vacuum_angular_wavenumber)
    target = _target(target_effective_index)
    refuse_text("search_mode_count", search_mode_count)
    if isinstance(search_mode_count, (bool, np.bool_)) or not isinstance(search_mode_count, (int, np.integer)) \
            or search_mode_count < 1:
        raise ValueError("search_mode_count must be a positive integer")
    if pml is not None and not isinstance(pml, ModalPML):
        raise TypeError("pml must be a galerkin.ModalPML")
    if bend is not None and not isinstance(bend, Bend):
        raise TypeError("bend must be a galerkin.Bend")
    if bend is not None and pml is None:
        raise ValueError("a bend needs a ModalPML: its coordinates are built with the layer")
    factors = None
    if pml is not None:
        if bend is not None:
            axis = 0 if bend.bend_axis == "x" else 1
            if not bend.bend_radius + mesh.nodes[:, axis].min() - bend.bend_origin > 0:
                raise ValueError("bend_radius and bend_origin must put every node of the mesh at a positive radius")
        # with a motion, the layer is placed on the mesh at the step t; _solve_modes then requires the
        # design velocity to vanish on every node of a PML element, so the factors carry no derivative
        placed = mesh
        if motion is not None:
            from .shape import motion_step
            step = motion_step(mesh, motion)
            # the layer needs the rectangular window: the outer faces may slide along themselves only
            for side, axis in (("left", 0), ("right", 0), ("bottom", 1), ("top", 1)):
                nodes = np.asarray(mesh.boundary.get(side, []), dtype=int)
                moving = nodes[np.asarray(step.design_velocity)[nodes, axis] != 0]
                if len(moving):
                    raise ValueError(f"motion: the design velocity moves {len(moving)} node(s) of the {side} face "
                                     f"along its normal (first {int(moving[0])}); with a pml the outer faces "
                                     "must stay in place")
            placed = step.moved
        coordinates = _mode_coordinates(
            placed, thickness=dict(pml.pml_thickness), strength=pml.pml_strength, order=pml.pml_order,
            bend_radius=None if bend is None else bend.bend_radius,
            bend_axis="x" if bend is None else bend.bend_axis, bend_origin=0.0 if bend is None else bend.bend_origin)
        factors = coordinates.factors
    if motion is not None:
        for name, value in (("relative_permittivity", eps), ("relative_permeability", mu),
                            ("vacuum_wavelength or vacuum_angular_wavenumber", k0)):
            if contains_live(value):
                raise TypeError(f"motion: {name} is a JAX or PyTorch value; with a motion only its t carries a "
                                "derivative")
    n_eff, space, et, ez = _solve_modes(mesh, to_kernel(eps), k0, to_kernel(target), int(search_mode_count),
                                        to_kernel(mu), pec_nodes, pec_edges=pec_edges, coordinate_factors=factors,
                                        motion=motion, **({} if motion is None or bend is None else dict(
                                            coordinate_bend=(bend.bend_radius, bend.bend_axis, bend.bend_origin))))
    return WaveguideModes(to_public(n_eff), to_public(et), to_public(1j * ez), space, k0, eps, mu)


@dataclass(frozen=True)
class DegenerateModeBranches:
    """One group of degenerate modes and the branches a shape motion splits it into.

    ``mode_index``: the indices of the group among the modes ``solve_waveguide_modes`` returns
    for the same inputs; ``effective_index``: their values; ``effective_index_derivative``: the
    slope d n_eff / dt of each branch, largest real part first, per unit of the motion's t (per
    metre when the design velocity is metres per metre); ``mode_combination``
    (len(mode_index), len(mode_index)): column k holds the coefficients of branch k in the
    returned modes of ``mode_index``. Values follow exp(-i omega t), as the modes do.
    """
    mode_index: tuple
    effective_index: np.ndarray
    effective_index_derivative: np.ndarray
    mode_combination: np.ndarray


def degenerate_branch_derivatives(mesh, *, relative_permittivity, vacuum_wavelength=None,
                                  vacuum_angular_wavenumber=None, target_effective_index, search_mode_count,
                                  relative_permeability=1.0, pec_nodes=None, pec_edges=None, motion,
                                  relative_tolerance=DEGENERATE_GAP) -> list:
    """The branch slopes of degenerate modes under a shape motion (decision 2026-11-21).

    ``solve_waveguide_modes(..., motion=motion)`` gives a degenerate mode NaN derivatives: sorted
    effective indices have a kink where two branches cross. Each branch is smooth, and its slope is
    an eigenvalue of the motion's derivative projected onto the degenerate subspace. This takes the
    inputs of ``solve_waveguide_modes`` with a motion (no PML or bend; NumPy material data) and returns
    one ``DegenerateModeBranches`` per group of returned modes whose eigenvalues lie within
    ``relative_tolerance`` (at most 1e-3) of each other, or an empty list. The numbers are NumPy
    values; the slopes are taken in the library of the motion's t.

    A value above DEGENERATE_GAP also groups nearly degenerate modes, such as a symmetric pair a
    mesh splits slightly. Their slopes are then those of the exactly degenerate limit, which the
    modes follow over steps much larger than the split; they are not d n_eff / dt at t of either
    returned mode (``solve_waveguide_modes`` with the motion gives those, without NaN, when the
    split exceeds DEGENERATE_GAP). Refused by name: a group with a member that was not returned
    (raise ``search_mode_count``), a group that chains beyond ``relative_tolerance``, and complex
    slopes on a real problem. ``ElementInversion`` from the motion is raised unchanged.
    """
    from ._waveguide_kernels import degenerate_branch_derivatives as _branches
    from .shape import MeshMotion
    count = mesh.num_triangles
    eps = _material(relative_permittivity, "relative_permittivity", count)
    mu = _material(relative_permeability, "relative_permeability", count)
    k0 = _wavenumber(vacuum_wavelength, vacuum_angular_wavenumber)
    target = _target(target_effective_index)
    refuse_text("search_mode_count", search_mode_count)
    if isinstance(search_mode_count, (bool, np.bool_)) or not isinstance(search_mode_count, (int, np.integer)) \
            or search_mode_count < 1:
        raise ValueError("search_mode_count must be a positive integer")
    refuse_text("relative_tolerance", relative_tolerance)
    if isinstance(relative_tolerance, (bool, np.bool_)) or not isinstance(relative_tolerance,
                                                                          (int, float, np.integer, np.floating)):
        raise TypeError(f"relative_tolerance must be a real number, got {relative_tolerance!r}")
    if not isinstance(motion, MeshMotion):
        raise TypeError("motion must be a MeshMotion (design velocity and a JAX or PyTorch t)")
    for name, value in (("relative_permittivity", eps), ("relative_permeability", mu),
                        ("vacuum_wavelength or vacuum_angular_wavenumber", k0)):
        if contains_live(value):
            raise TypeError(f"motion: {name} is a JAX or PyTorch value; with a motion only its t carries a "
                            "derivative")
    try:
        groups = _branches(mesh, to_kernel(eps), k0, to_kernel(target), int(search_mode_count), motion=motion,
                           mu_r=to_kernel(mu), pec_nodes=pec_nodes, pec_edges=pec_edges,
                           tolerance=float(relative_tolerance))
    except ValueError as exc:
        prefix = "degenerate_branch_derivatives: "
        if type(exc) is not ValueError or not str(exc).startswith(prefix):
            raise                       # ElementInversion and the motion's own refusals, unchanged
        text = re.sub(r"\btolerance\b", "relative_tolerance", str(exc)[len(prefix):])
        raise ValueError(re.sub(r"\bnum_modes\b", "search_mode_count", text)) from exc
    return [DegenerateModeBranches(g.modes, to_public(g.effective_index), to_public(g.slopes),
                                   to_public(g.combinations)) for g in groups]


# -- post-processing ---------------------------------------------------------------------------------------------

def _modes(value, name):
    if not isinstance(value, WaveguideModes):
        raise TypeError(f"{name} must be the WaveguideModes of solve_waveguide_modes")
    return value


def _index(modes, mode, name):
    count = len(modes.effective_index)
    if isinstance(mode, (bool, np.bool_)) or not isinstance(mode, (int, np.integer)) or not 0 <= mode < count:
        raise ValueError(f"{name} must be a mode index in [0, {count})")
    return int(mode)


def _kernel_field(modes, mode):
    """(et, ez, n_eff) of one mode in the kernels' convention: to_kernel of the public values, ez = E_z / 1j."""
    return (to_kernel(modes.unnormalized_electric_field_line_integral[mode]),
            -1j * to_kernel(modes.unnormalized_electric_field_z[mode]),
            to_kernel(modes.effective_index[mode]))


def _same_cross_section(a, b, name_a, name_b):
    ma, mb = a.space.mesh, b.space.mesh
    if ma is not mb and not (ma.nodes.shape == mb.nodes.shape and np.array_equal(ma.nodes, mb.nodes)
                             and np.array_equal(ma.triangles, mb.triangles)):
        raise ValueError(f"{name_a} and {name_b} must be solved on the same mesh")


def mode_power(modes, mode) -> complex:
    """The complex Poynting integral P = 1/2 int (E x H^*) . zhat dA of one mode, in W for fields in V/m.

    Re P is the time-averaged power the mode carries in +z; for a lossless mode Im P is zero up to
    rounding. exp(-i omega t). NumPy values only (``galerkin.kernels.vector_power``).
    """
    modes = _modes(modes, "modes")
    mode = _index(modes, mode, "mode")
    et, ez, n_eff = _kernel_field(modes, mode)
    return to_public(_vector_power(modes.space, et, ez, n_eff, modes.vacuum_angular_wavenumber,
                                   to_kernel(modes.relative_permeability)))


def cross_power(modes_a, mode_a, modes_b, mode_b) -> complex:
    """P_ab = 1/2 int (E_a x H_b^*) . zhat dA, in W for fields in V/m; exp(-i omega t).

    H_b is the magnetic field of mode ``mode_b`` of ``modes_b``, with its permeability. Both solves
    must share the mesh and k0. For a = b this is ``mode_power``. NumPy values only.
    """
    modes_a, modes_b = _modes(modes_a, "modes_a"), _modes(modes_b, "modes_b")
    mode_a, mode_b = _index(modes_a, mode_a, "mode_a"), _index(modes_b, mode_b, "mode_b")
    _same_cross_section(modes_a, modes_b, "modes_a", "modes_b")
    if modes_a.vacuum_angular_wavenumber != modes_b.vacuum_angular_wavenumber:
        raise ValueError("modes_a and modes_b must be solved at the same vacuum wavelength")
    et_a, ez_a, _ = _kernel_field(modes_a, mode_a)
    et_b, ez_b, n_eff_b = _kernel_field(modes_b, mode_b)
    return to_public(_vector_cross_power(modes_b.space, et_a, ez_a, et_b, ez_b, n_eff_b,
                                         modes_b.vacuum_angular_wavenumber, to_kernel(modes_b.relative_permeability)))


def field_overlap(modes_a, mode_a, modes_b, mode_b) -> complex:
    """<E_a, E_b> = int E_a^* . E_b dA over the cross-section, both components, in m^2 for fields in V/m.

    exp(-i omega t). Both solves must share the mesh. NumPy values only.
    """
    modes_a, modes_b = _modes(modes_a, "modes_a"), _modes(modes_b, "modes_b")
    mode_a, mode_b = _index(modes_a, mode_a, "mode_a"), _index(modes_b, mode_b, "mode_b")
    _same_cross_section(modes_a, modes_b, "modes_a", "modes_b")
    et_a, ez_a, _ = _kernel_field(modes_a, mode_a)
    et_b, ez_b, _ = _kernel_field(modes_b, mode_b)
    return to_public(_vector_field_overlap(modes_a.space, et_a, ez_a, et_b, ez_b))


def mode_coupling_efficiency(modes, mode, incident, incident_mode) -> float:
    """eta = |<E_mode, E_in>|^2 / (<E_mode, E_mode> <E_in, E_in>) with the field overlap, both components.

    The incident field is mode ``incident_mode`` of the solve ``incident`` on the same mesh. ``mode``
    may be a sequence of mode indices: eta is then the share of the incident field in their span (a
    degenerate pair). Real and dimensionless. NumPy values only.
    """
    modes, incident = _modes(modes, "modes"), _modes(incident, "incident")
    indices = [_index(modes, m, "mode") for m in (mode if isinstance(mode, Sequence) else [mode])]
    if not indices:
        raise ValueError("mode must name at least one mode")
    incident_mode = _index(incident, incident_mode, "incident_mode")
    _same_cross_section(modes, incident, "modes", "incident")
    parts = [_kernel_field(modes, m) for m in indices]
    et_in, ez_in, _ = _kernel_field(incident, incident_mode)
    et_mode = np.stack([p[0] for p in parts]) if isinstance(mode, Sequence) else parts[0][0]
    ez_mode = np.stack([p[1] for p in parts]) if isinstance(mode, Sequence) else parts[0][1]
    return to_public(_coupling_efficiency(modes.space, et_mode, ez_mode, et_in, ez_in))


def _region_mask(mesh, regions):
    """A triangle mask from region names (a name or a sequence of names) or a mask or index array of triangles."""
    names = [regions] if isinstance(regions, str) else regions
    if isinstance(names, Sequence) and names and all(isinstance(n, str) for n in names):
        if mesh.regions is None or mesh.region_names is None:
            raise ValueError("regions names mesh regions, but the mesh carries no region names")
        unknown = sorted(set(names) - set(mesh.region_names))
        if unknown:
            raise ValueError(f"regions {unknown} are not regions of the mesh ({mesh.region_names})")
        ids = [mesh.region_names.index(n) for n in names]
        return np.isin(mesh.regions, ids)
    return regions


def mode_confinement_factor(modes, mode, regions) -> float:
    """Gamma = int_R Re(eps_r) |E|^2 dA / int Re(eps_r) |E|^2 dA, the energy share of one mode in R.

    regions: a region name or a sequence of names of the mesh, or a boolean mask (T,) or an index
    array of the triangles of R. Both E_t and E_z count; only the real part of the permittivity
    weights the field. Real and dimensionless. NumPy values only.
    """
    modes = _modes(modes, "modes")
    mode = _index(modes, mode, "mode")
    et, ez, _ = _kernel_field(modes, mode)
    return to_public(_confinement_factor(modes.space, et, ez, to_kernel(modes.relative_permittivity),
                                         _region_mask(modes.space.mesh, regions)))


def mode_effective_area(modes, mode, *, include_longitudinal=False) -> float:
    """A_eff = (int |E|^2 dA)^2 / int |E|^4 dA of one mode, in m^2.

    By default |E|^2 = |E_t|^2, the usual transverse definition; with include_longitudinal=True it is
    |E_t|^2 + |E_z|^2. NumPy values only.
    """
    modes = _modes(modes, "modes")
    mode = _index(modes, mode, "mode")
    et, ez, _ = _kernel_field(modes, mode)
    return to_public(_effective_area(modes.space, et, ez, include_longitudinal=include_longitudinal))
