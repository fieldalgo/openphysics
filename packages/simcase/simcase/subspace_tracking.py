# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Opt-in tracking of isolated fixed-rank clusters of vector modes.

The default ``electric-l2-assignment-v1`` method tracks individual modes and
rejects near-degenerate partners. This module is used only when a document asks
for ``study.tracking.method = "electric-l2-subspace-v1"``. It tracks the span of
each selected cluster of nearby effective indices, not individual members.

Three objects are kept apart:

* raw eigenpairs: the solver's fields and their individual ``n_eff``;
* clusters: groups of nearby candidates, isolated from every other observed
  candidate (nearness does not prove an exact degeneracy);
* transport frames: electric-L2-orthonormal bases of each cluster span aligned
  with the previous frame. Frame columns are not eigenmodes and never carry an
  individual ``n_eff`` or group index.

The electric L2 product is a continuity metric on one fixed mesh, not a power or
energy product. Sampled overlaps cannot certify behavior between samples, and a
finite candidate search cannot certify that no partner was missed.
"""

from __future__ import annotations

import math

import numpy as np
from scipy.optimize import linear_sum_assignment

from galerkin import EdgeSpace, assemble_edge_mass, assemble_mass

from .fields import VectorField
from .tracking import ModeTrackingError

ASSIGNMENT_METHOD = "electric-l2-assignment-v1"
SUBSPACE_METHOD = "electric-l2-subspace-v1"
METHODS = (ASSIGNMENT_METHOD, SUBSPACE_METHOD)

# Numerical guards for the small Gram matrices. They detect rank loss and
# metric failure; they are not physical accuracy claims. A Gram condition number
# above GRAM_CONDITION_MAX would amplify roundoff in the whitened frame by about
# that factor, so such a cluster is refused instead of reduced or pseudo-inverted.
GRAM_CONDITION_MAX = 1e8
HERMITIAN_DEFECT_MAX = 1e-10      # relative Frobenius defect of G - G^H
ORTHONORMAL_DEFECT_MAX = 1e-8     # max |Q^H W Q - I| after whitening
SINGULAR_EXCURSION_MAX = 1e-8     # tolerated roundoff of sigma^2 above one

_FORBIDDEN = -1e6                 # assignment cost of a rank-mismatched pair


def _finite_number(value) -> bool:
    try:
        return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)
    except OverflowError:
        return False


def subspace_settings(num_modes: int, supplied: dict) -> dict:
    """Resolve and validate the opt-in subspace settings.

    ``cluster_span_max`` and ``external_gap_min`` have no default: an absolute
    n_eff threshold depends on the guide, mesh and wavelength interval, and no
    universal value is known.
    """
    allowed = {"method", "search_modes", "cluster_span_max", "external_gap_min", "min_overlap", "min_margin"}
    if "degeneracy_tolerance" in supplied:
        raise ValueError("study.tracking.degeneracy_tolerance belongs to the electric-l2-assignment-v1 method; "
                         "electric-l2-subspace-v1 uses cluster_span_max and external_gap_min instead")
    unknown = set(supplied) - allowed
    if unknown:
        raise ValueError(f"unknown study.tracking settings: {sorted(unknown)}")
    missing = [name for name in ("cluster_span_max", "external_gap_min") if name not in supplied]
    if missing:
        raise ValueError(f"study.tracking.method {SUBSPACE_METHOD!r} needs explicit {', '.join(missing)} "
                         "(absolute n_eff values; there is no universal default)")
    defaults = dict(search_modes=max(2 * num_modes, num_modes + 4), min_overlap=0.8, min_margin=0.1)
    settings = defaults | {k: v for k, v in supplied.items() if k != "method"}
    for name, value in settings.items():
        if not _finite_number(value):
            raise ValueError(f"study.tracking.{name} must be a finite number")
    count = settings["search_modes"]
    if count != int(count) or count <= num_modes:
        raise ValueError("study.tracking.search_modes must be an integer greater than num_modes")
    settings["search_modes"] = int(count)
    for name in ("min_overlap", "min_margin"):
        if not 0 < settings[name] <= 1:
            raise ValueError(f"study.tracking.{name} must be in (0, 1]")
    if settings["cluster_span_max"] <= 0:
        raise ValueError("study.tracking.cluster_span_max must be positive")
    if settings["external_gap_min"] <= settings["cluster_span_max"]:
        raise ValueError("study.tracking.external_gap_min must be greater than cluster_span_max")
    return dict(method=SUBSPACE_METHOD, **{k: settings[k] for k in
                ("search_modes", "cluster_span_max", "external_gap_min", "min_overlap", "min_margin")})


def tracking_method(supplied) -> str:
    """The requested tracking method name, validating only its type and value."""
    if supplied is None:
        return ASSIGNMENT_METHOD
    if not isinstance(supplied, dict):
        raise ValueError("study.tracking must be an object")
    method = supplied.get("method", ASSIGNMENT_METHOD)
    if method not in METHODS:
        raise ValueError(f"study.tracking.method must be one of {list(METHODS)}")
    return method


# -- partition ---------------------------------------------------------------

def partition(neff: np.ndarray, span_max: float) -> list[tuple[int, int]]:
    """Connected components of candidates joined by gaps <= span_max.

    ``neff`` must be sorted in descending order. Returns half-open index ranges.
    A component may be wider than span_max (a chain of near neighbours); callers
    refuse such components rather than silently splitting or merging them.
    """
    if len(neff) == 0:
        return []
    bounds, start = [], 0
    for i in range(1, len(neff)):
        if neff[i - 1] - neff[i] > span_max:
            bounds.append((start, i))
            start = i
    bounds.append((start, len(neff)))
    return bounds


def _component_evidence(neff, component, components, saturated, settings):
    """Span, isolation and lower-guard evidence of one component, plus failures."""
    start, stop = component
    span = float(neff[start] - neff[stop - 1])
    upper = float(neff[start - 1] - neff[start]) if start > 0 else None
    lower = float(neff[stop - 1] - neff[stop]) if stop < len(neff) else None
    problems = []
    if span > settings["cluster_span_max"]:
        problems.append(f"span {span:.6g} exceeds cluster_span_max {settings['cluster_span_max']:g} "
                        "(chained near neighbours)")
    for side, gap in (("upper", upper), ("lower", lower)):
        if gap is not None and gap <= settings["external_gap_min"]:
            problems.append(f"{side} gap {gap:.6g} is not above external_gap_min "
                            f"{settings['external_gap_min']:g} (ambiguous isolation)")
    if lower is None:
        why = "the candidate budget is exhausted" if saturated else "no lower guided candidate was found"
        problems.append(f"no observed lower guard candidate ({why}; search boundary unresolved)")
    evidence = dict(candidate_ranks=list(range(start + 1, stop + 1)), rank=stop - start, span=span,
                    upper_gap=upper, lower_gap=lower, lower_guard_rank=stop + 1 if lower is not None else None)
    return evidence, problems


# -- metric ------------------------------------------------------------------

class ElectricMetric:
    """Electric L2 product on the original document mesh: W = diag(M_edge, M_node)."""

    def __init__(self, mesh):
        self.edge_mass = assemble_edge_mass(EdgeSpace(mesh))
        self.node_mass = assemble_mass(mesh)

    def product(self, left: VectorField, right: VectorField) -> np.ndarray:
        return (left.transverse.conj().T @ (self.edge_mass @ right.transverse)
                + left.longitudinal.conj().T @ (self.node_mass @ right.longitudinal))


def columns(field: VectorField, transform: np.ndarray) -> VectorField:
    """Apply one coefficient matrix to every field component consistently."""
    transform = np.asarray(transform)
    return VectorField(field.edges, field.transverse @ transform, field.longitudinal @ transform,
                       np.einsum("tmc,mk->tkc", field.electric, transform))


def whiten(gram: np.ndarray) -> tuple[np.ndarray, dict]:
    """Return H = G^(-1/2) for a Hermitian positive definite Gram matrix.

    Rank deficiency and ill conditioning are failures (ValueError). No
    pseudoinverse hides a missing direction.
    """
    gram = np.asarray(gram, dtype=complex)
    if gram.ndim != 2 or gram.shape[0] != gram.shape[1] or gram.shape[0] == 0:
        raise ValueError("Gram matrix must be square and non-empty")
    if not np.isfinite(gram).all():
        raise ValueError("non-finite electric L2 Gram matrix")
    scale = np.linalg.norm(gram)
    if scale == 0:
        raise ValueError("zero electric L2 Gram matrix")
    defect = float(np.linalg.norm(gram - gram.conj().T) / scale)
    if defect > HERMITIAN_DEFECT_MAX:
        raise ValueError(f"electric L2 Gram matrix is not Hermitian (relative defect {defect:.3g})")
    gram = (gram + gram.conj().T) / 2
    values, vectors = np.linalg.eigh(gram)
    if values[0] <= 0 or values[-1] / values[0] > GRAM_CONDITION_MAX:
        condition = math.inf if values[0] <= 0 else float(values[-1] / values[0])
        raise ValueError(f"cluster fields are rank deficient or ill conditioned (Gram condition {condition:.3g} "
                         f"> {GRAM_CONDITION_MAX:g})")
    inverse_root = (vectors / np.sqrt(values)) @ vectors.conj().T
    orthonormal = inverse_root.conj().T @ gram @ inverse_root
    orthonormal_defect = float(np.abs(orthonormal - np.eye(len(values))).max())
    if orthonormal_defect > ORTHONORMAL_DEFECT_MAX:
        raise ValueError(f"whitened cluster frame is not orthonormal (defect {orthonormal_defect:.3g})")
    return inverse_root, dict(gram_condition=float(values[-1] / values[0]),
                              orthonormal_defect=orthonormal_defect)


def principal_values(cross: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """SVD of the whitened cross Gram P^H W Q = L diag(sigma) V^H.

    Returns (sigma^2 descending, L, V^H). sigma are the cosines of principal
    angles. Roundoff excursions above one are clipped only within
    SINGULAR_EXCURSION_MAX; larger ones indicate a metric or whitening failure.
    """
    if not np.isfinite(cross).all():
        raise ValueError("non-finite cross Gram matrix")
    left, sigma, right_h = np.linalg.svd(cross)
    squared = sigma ** 2
    if squared.size and squared.max() > 1 + SINGULAR_EXCURSION_MAX:
        raise ValueError(f"principal value {squared.max():.12g} exceeds one: frames are not orthonormal")
    return np.clip(squared, 0.0, 1.0), left, right_h


def assign_clusters(scores: np.ndarray, allowed: np.ndarray):
    """Maximum-score injective assignment of previous clusters to current ones.

    ``scores[i, j]`` is the mean squared principal value of previous cluster i
    against current candidate j, and ``allowed`` marks equal-rank pairs. Returns
    (columns, margins); a column is None when no allowed complete assignment
    exists. A margin is the score loss of the best complete assignment that
    excludes the chosen pair, or None when no such alternative exists.
    """
    rows = scores.shape[0]
    if scores.shape[1] < rows:
        return None, None
    cost = np.where(allowed, scores, _FORBIDDEN)
    r, c = linear_sum_assignment(cost, maximize=True)
    if not allowed[r, c].all():
        return None, None
    best = float(cost[r, c].sum())
    margins = []
    for i, j in zip(r, c):
        alternative = cost.copy()
        alternative[i, j] = _FORBIDDEN
        ar, ac = linear_sum_assignment(alternative, maximize=True)
        if not (allowed[ar, ac] & ~((ar == i) & (ac == j))).all():
            margins.append(None)
        else:
            margins.append(max(0.0, best - float(alternative[ar, ac].sum())))
    return c, margins


# -- tracker -----------------------------------------------------------------

class SubspaceTracker:
    """Track the clusters of the first requested vectors across samples.

    ``step`` is transactional: the complete next state is computed and checked
    before any previous frame or cluster is replaced. A failure raises
    ModeTrackingError and leaves no successful partial sweep.
    """

    def __init__(self, mesh, num_modes: int, settings: dict):
        self.num_modes = num_modes
        self.settings = settings
        self.metric = ElectricMetric(mesh)
        self.previous: list[VectorField] | None = None      # one W-orthonormal frame per cluster
        self.ranks: list[int] | None = None

    def _fail(self, location, reason, action):
        raise ModeTrackingError(f"vector subspace sweep at {location}: {reason}; {action}")

    def _whitened(self, field, start, stop, location, label):
        raw = columns(field, np.eye(field.transverse.shape[1])[:, start:stop])
        try:
            inverse_root, diagnostics = whiten(self.metric.product(raw, raw))
        except ValueError as exc:
            self._fail(location, f"{label}: {exc}", "check the mesh and solved fields")
        return raw, inverse_root, columns(raw, inverse_root), diagnostics

    def step(self, neff, field: VectorField, location: str):
        """Return (raw n_eff, raw fields, frame transform, cluster offsets, evidence).

        Raw columns are selected candidates in seed cluster order, members in
        descending local n_eff. The transform is block diagonal (no mixing
        between clusters): frame = raw @ transform.
        """
        neff = np.asarray(neff, dtype=float)
        count = len(neff)
        settings = self.settings
        if count and not (np.isfinite(neff).all() and np.all(np.diff(neff) <= 0)):
            self._fail(location, "candidate n_eff values are not finite and descending", "check the solver output")
        saturated = count >= settings["search_modes"]
        components = partition(neff, settings["cluster_span_max"])
        if self.previous is None:
            chosen = self._seed(neff, components, saturated, location)
            scores = margins = principal = None
        else:
            chosen, scores, margins, principal = self._match(neff, field, components, saturated, location)

        raw_parts, transforms, frames, cluster_evidence = [], [], [], []
        for n, (start, stop) in enumerate(chosen):
            evidence, problems = _component_evidence(neff, (start, stop), components, saturated, settings)
            if problems:
                self._fail(location, f"cluster {n + 1} (candidate ranks {start + 1}-{stop}): " + "; ".join(problems),
                           "adjust cluster_span_max/external_gap_min, increase search_modes or narrow the interval")
            raw, inverse_root, whitened, diagnostics = self._whitened(field, start, stop, location,
                                                                      f"cluster {n + 1}")
            if self.previous is None:
                rotation = np.eye(stop - start)       # seed orientation is arbitrary
            else:
                cross = self.metric.product(self.previous[n], whitened)
                _, left, right_h = principal_values(cross)
                rotation = right_h.conj().T @ left.conj().T
            transform = inverse_root @ rotation
            raw_parts.append(raw)
            transforms.append(transform)
            frames.append(columns(raw, transform))
            evidence.update(diagnostics)
            if principal is not None:
                evidence.update(principal_squared=principal[n].tolist(), min_principal_squared=float(principal[n][-1]),
                                score=scores[n], margin=margins[n],
                                sin_max_angle=float(math.sqrt(max(0.0, 1.0 - principal[n][-1]))))
            cluster_evidence.append(evidence)

        selected = np.concatenate([np.arange(a, b) for a, b in chosen])
        offsets = np.concatenate([[0], np.cumsum([b - a for a, b in chosen])])
        block = np.zeros((len(selected), len(selected)), dtype=complex)
        for n, transform in enumerate(transforms):
            block[offsets[n]:offsets[n + 1], offsets[n]:offsets[n + 1]] = transform
        raw_field = columns(field, np.eye(count)[:, selected])
        # commit only after every check passed
        self.previous = frames
        self.ranks = [b - a for a, b in chosen]
        evidence = dict(candidate_count=count, saturated=bool(saturated),
                        candidate_ranks=(selected + 1).tolist(), clusters=cluster_evidence)
        return neff[selected], raw_field, block, offsets, evidence

    def _seed(self, neff, components, saturated, location):
        target = self.num_modes
        if len(neff) < target:
            self._fail(location, f"requested {target} vectors, found only {len(neff)} guided candidates "
                       "(cutoff or incomplete search)",
                       "check n_cladding and search_modes, narrow the interval or use single studies")
        chosen = []
        for start, stop in components:
            if start >= target:
                break
            if stop > target:
                self._fail(location, f"the first {target} vectors cut the observed cluster at candidate ranks "
                           f"{start + 1}-{stop}; include all {stop} vectors or fewer ({start})",
                           "set num_modes to a complete cluster boundary; a cluster member is never chosen alone")
            chosen.append((start, stop))
        return chosen

    def _match(self, neff, field, components, saturated, location):
        candidates = []                  # current components with valid, whitened frames
        for start, stop in components:
            if stop - start not in self.ranks:
                continue
            raw = columns(field, np.eye(field.transverse.shape[1])[:, start:stop])
            try:
                inverse_root, _ = whiten(self.metric.product(raw, raw))
            except ValueError:
                continue                 # an unusable candidate cannot be a match
            candidates.append(((start, stop), columns(raw, inverse_root)))
        observed = [b - a for a, b in components]
        if not candidates:
            self._fail(location, f"no candidate cluster has a tracked rank {self.ranks} (observed component ranks "
                       f"{observed})", "reduce the wavelength step, adjust cluster_span_max or increase search_modes")
        scores = np.zeros((len(self.previous), len(candidates)))
        allowed = np.zeros_like(scores, dtype=bool)
        spectra = {}
        for i, frame in enumerate(self.previous):
            for j, ((start, stop), whitened) in enumerate(candidates):
                if stop - start != self.ranks[i]:
                    continue
                try:
                    squared, _, _ = principal_values(self.metric.product(frame, whitened))
                except ValueError as exc:
                    self._fail(location, f"cluster {i + 1}: {exc}", "check the mesh and solved fields")
                scores[i, j] = squared.mean()
                allowed[i, j] = True
                spectra[i, j] = squared
        picked, margins = assign_clusters(scores, allowed)
        if picked is None:
            self._fail(location, f"no complete equal-rank assignment for tracked ranks {self.ranks} "
                       f"(observed component ranks {observed})",
                       "a cluster lost or gained a member, or merged with a neighbour; reduce the wavelength step")
        chosen, principal, chosen_scores = [], [], []
        for i, j in enumerate(picked):
            squared = spectra[i, j]
            if squared[-1] < self.settings["min_overlap"]:
                self._fail(location, f"cluster {i + 1} has weakest principal value squared {squared[-1]:.6g} "
                           f"< min_overlap {self.settings['min_overlap']:g} (mean {squared.mean():.6g}; "
                           "a direction was lost)", "reduce the wavelength step or expand search_modes")
            if margins[i] is not None and margins[i] < self.settings["min_margin"]:
                self._fail(location, f"cluster {i + 1} has ambiguous assignment margin {margins[i]:.6g} "
                           f"< min_margin {self.settings['min_margin']:g}", "reduce the wavelength step")
            chosen.append(candidates[j][0])
            principal.append(squared)
            chosen_scores.append(float(squared.mean()))
        return chosen, chosen_scores, margins, principal
