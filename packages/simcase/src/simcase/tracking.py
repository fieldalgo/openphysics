# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Conservative tracking of resolved vector modes on one fixed mesh.

The physical electric L2 product is a continuity metric, not a power or energy
product. Sampled overlap cannot certify behavior between wavelength samples.
"""

import math

import numpy as np
from scipy.optimize import linear_sum_assignment

from galerkin import EdgeSpace, assemble_edge_mass, assemble_mass

from .fields import VectorField


class ModeTrackingError(ValueError):
    """A vector sweep cannot safely identify all requested resolved branches."""


def tracking_settings(num_modes: int, supplied=None) -> dict:
    """Resolve and validate JSON settings, without altering the document.

    ``method`` selects the tracker. The default ``electric-l2-assignment-v1``
    settings are returned without a ``method`` key, exactly as before the
    opt-in ``electric-l2-subspace-v1`` method existed.
    """
    defaults = dict(search_modes=max(2 * num_modes, num_modes + 4), min_overlap=0.8,
                    min_margin=0.1, degeneracy_tolerance=1e-5)
    if supplied is None:
        supplied = {}
    if not isinstance(supplied, dict):
        raise ValueError("study.tracking must be an object")
    from .subspace_tracking import SUBSPACE_METHOD, subspace_settings, tracking_method
    method = tracking_method(supplied)
    if method == SUBSPACE_METHOD:
        return subspace_settings(num_modes, supplied)
    supplied = {k: v for k, v in supplied.items() if k != "method"}
    if set(supplied) - set(defaults):
        raise ValueError(f"unknown study.tracking settings: {sorted(set(supplied) - set(defaults))}")
    settings = defaults | supplied
    for name, value in settings.items():
        try:
            finite = isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)
        except OverflowError:
            finite = False
        if not finite:
            raise ValueError(f"study.tracking.{name} must be a finite number")
    count = settings["search_modes"]
    if count != int(count) or count <= num_modes:
        raise ValueError("study.tracking.search_modes must be an integer greater than num_modes")
    settings["search_modes"] = int(count)
    for name in ("min_overlap", "min_margin"):
        if not 0 < settings[name] <= 1:
            raise ValueError(f"study.tracking.{name} must be in (0, 1]")
    if settings["degeneracy_tolerance"] < 0:
        raise ValueError("study.tracking.degeneracy_tolerance must be non-negative")
    return settings


class ModeTracker:
    """Track the initial requested modes, retaining original eigenfields.

    The edge mass and nodal mass are assembled on the original document mesh.
    VectorField already stores physical Et line integrals and physical Ez, so
    neither beta nor an extra wavelength factor belongs in this product.
    """

    def __init__(self, mesh, num_modes, settings, *, scalar=False, physical_weights=1.0, seed_target=None):
        self.num_modes = num_modes
        self.settings = settings
        self.scalar = scalar
        self.seed_target = seed_target
        self.edge_mass = assemble_edge_mass(EdgeSpace(mesh), physical_weights)
        self.node_mass = assemble_mass(mesh, physical_weights)
        self.previous = None

    def product(self, left, right):
        if self.scalar:
            return left.conj().T @ (self.node_mass @ right)
        return (left.transverse.conj().T @ (self.edge_mass @ right.transverse)
                + left.longitudinal.conj().T @ (self.node_mass @ right.longitudinal))

    def step(self, neff, field, location):
        """Return reordered indices/fields and JSON-safe tracking evidence.

        Degenerate subspaces are deliberately not rotated into invented modes.
        The result is all-or-error: a failed sweep has no supported group index.
        """
        count = len(neff)

        def fail(reason, action):
            raise ModeTrackingError(f"vector sweep at {location}: {reason}; {action}")

        if count < self.num_modes:
            fail(f"requested {self.num_modes} modes, found only {count} guided candidates "
                 "(cutoff or incomplete search)",
                 "check n_cladding and search_modes, narrow the interval or use single studies")
        overlap, margins = None, None
        phase = np.ones(self.num_modes, dtype=complex)
        if self.previous is None:
            selected = np.arange(self.num_modes)
            if self.seed_target is not None:
                selected = np.argsort(abs(neff-self.seed_target))[:self.num_modes]
                selected = selected[np.argsort(-neff[selected].real)]
        else:
            cross = self.product(self.previous, field)
            old_norm = np.diag(self.product(self.previous, self.previous)).real
            new_norm = np.diag(self.product(field, field)).real
            if (not np.isfinite(cross).all() or not np.isfinite(old_norm).all()
                    or not np.isfinite(new_norm).all() or np.any(old_norm <= 0)
                    or np.any(new_norm <= 0)):
                fail("non-finite or zero electric L2 norm", "check the mesh and solved fields")
            scores = np.clip(abs(cross) ** 2 / (old_norm[:, None] * new_norm[None, :]), 0, 1)
            rows, selected = linear_sum_assignment(scores, maximize=True)
            overlap = scores[rows, selected]
            for mode, score in enumerate(overlap):
                if score < self.settings["min_overlap"]:
                    fail(f"mode {mode + 1} has weak overlap {score:.6g} "
                         f"< {self.settings['min_overlap']:g} (lost or unresolved branch)",
                         "reduce the wavelength step or expand search_modes; use single studies near cutoff")
            # Exclude each selected match to measure the best alternative FULL
            # assignment. Row-only runner-up checks needlessly reject some
            # unambiguous global assignments.
            best = float(overlap.sum())
            margins = []
            for mode, column in enumerate(selected):
                alternative = scores.copy()
                alternative[mode, column] = -np.inf
                try:
                    r, c = linear_sum_assignment(alternative, maximize=True)
                    margin = max(0.0, best - float(alternative[r, c].sum()))
                except ValueError:  # no alternative complete assignment exists
                    margin = None
                margins.append(margin)
                if margin is not None and margin < self.settings["min_margin"]:
                    fail(f"mode {mode + 1} has ambiguous assignment margin {margin:.6g} "
                         f"< {self.settings['min_margin']:g}",
                         "reduce the wavelength step or use single studies for unresolved modes")
            phase = np.exp(-1j * np.angle(cross[rows, selected]))

        boundary = count - 1 if self.seed_target is None else int(np.argmax(abs(neff-self.seed_target)))
        for mode, column in enumerate(selected):
            if count >= self.settings["search_modes"] and column == boundary:
                fail(f"mode {mode + 1} reaches the candidate search boundary",
                     "increase study.tracking.search_modes to check for an unseen partner")
            others = np.delete(neff, column)
            if len(others) and np.min(abs(others - neff[column])) <= self.settings["degeneracy_tolerance"]:
                fail(f"mode {mode + 1} is near-degenerate within n_eff tolerance "
                     f"{self.settings['degeneracy_tolerance']:g}",
                     "use single studies; individual branches need degenerate-subspace tracking")

        aligned = field[:, selected] * phase if self.scalar else VectorField(field.edges, field.transverse[:, selected] * phase,
                              field.longitudinal[:, selected] * phase,
                              field.electric[:, selected, :] * phase[None, :, None], field.normalization)
        self.previous = aligned
        evidence = dict(candidate_count=count, candidate_ranks=(selected + 1).tolist(),
                        overlaps=None if overlap is None else overlap.tolist(), margins=margins)
        return neff[selected], aligned, evidence
