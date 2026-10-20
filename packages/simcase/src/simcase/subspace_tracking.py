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

# Numerical guards for the small Gram matrices. They separate roundoff from rank
# loss or metric failure; they are not physical accuracy claims. The budget is
# derived in docs/packages/simcase/vector_subspace_tracking.md ("Numerical guards"); in short,
# with unit roundoff u, cluster rank r, Gram condition kappa, N degrees of
# freedom and product cancellation rho (ElectricMetric.cancellation: the largest
# sum |x||W||x| / x^H W x over the cluster fields; about 1 to 3 on shape-regular
# meshes, larger on very flat elements):
#
# * G = U^H W U is a sum of sparse products. Its Hermitian defect is roundoff of
#   order sqrt(N) u, growing with rho (measured below 1e-11 for rho up to 4e5),
#   far below HERMITIAN_DEFECT_MAX; a wrong metric gives a defect of order one.
# * The orthonormality defect of a formed frame Q = U H, measured as
#   max |Q^H W Q - I| with a fresh product, is within
#   frame_defect_budget(r, kappa, N, rho) = 8 r u (kappa + sqrt(N) + rho). The
#   kappa term comes from the backward-stable eigendecomposition and from the
#   Gram roundoff amplified by H = G^(-1/2); the sqrt(N) and rho terms are the
#   product roundoff.
# * GRAM_CONDITION_MAX = 1e6 keeps that budget below ORTHONORMAL_DEFECT_MAX
#   (8.5e-9 at r = 8, N = 1e6, rho = 2e5), so a defect refusal signals a
#   failure, not roundoff, unless rho is far above that. The earlier limit 1e8
#   allowed budgets near 1e-6, so the defect guard, not the stated limit,
#   refused such clusters.
# * Principal values may exceed one only through the measured defects of the
#   two formed frames: sigma_max^2 <= (1 + r d_P)(1 + r d_Q). The remaining SVD
#   and cross-product roundoff, of order u (r + sqrt(N)), is covered by
#   SINGULAR_ROUNDOFF for N up to about 1e7.
#
# Defects are measured on the frames that are actually formed and compared.
# Measuring H^H G H against the Gram matrix G it was computed from misses the
# Gram roundoff amplified by kappa and refused identical spans near kappa 1e6.
GRAM_CONDITION_MAX = 1e6
HERMITIAN_DEFECT_MAX = 1e-10      # relative Frobenius defect of G - G^H
ORTHONORMAL_DEFECT_MAX = 1e-8     # max |Q^H W Q - I| of a formed frame
SINGULAR_ROUNDOFF = 1e-12         # SVD/product roundoff allowance on sigma^2
UNIT_ROUNDOFF = float(np.finfo(float).eps) / 2
FRAME_DEFECT_FACTOR = 8.0


def frame_defect_budget(rank: int, condition: float, size: int, cancellation: float = 1.0) -> float:
    """Roundoff budget of max |Q^H W Q - I| for a whitened frame Q formed from N = size DOFs.

    ``cancellation`` is ElectricMetric.cancellation of the fields the frame was formed from.
    """
    return FRAME_DEFECT_FACTOR * rank * UNIT_ROUNDOFF * (condition + math.sqrt(size) + cancellation)


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


def _component_evidence(neff, component, saturated, settings):
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
        why = ("the candidate budget is exhausted" if saturated else
               "no lower guided candidate was found within the search (the mesh may also cap the candidate count)")
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
        self._absolute = None

    def cancellation(self, field: VectorField) -> float:
        """Largest sum |x||W||x| / x^H W x over the columns: how much the product's terms cancel.

        Rounding of the product grows with it. Smooth fields on shape-regular meshes
        give about 1 to 3; oscillating fields on very flat elements give much more.
        """
        if self._absolute is None:
            self._absolute = (abs(self.edge_mass), abs(self.node_mass))
        edge, node = self._absolute
        transverse, longitudinal = np.abs(field.transverse), np.abs(field.longitudinal)
        terms = (np.einsum("ij,ij->j", transverse, edge @ transverse)
                 + np.einsum("ij,ij->j", longitudinal, node @ longitudinal))
        norms = np.real(np.einsum("ij,ij->j", field.transverse.conj(), self.edge_mass @ field.transverse)
                        + np.einsum("ij,ij->j", field.longitudinal.conj(), self.node_mass @ field.longitudinal))
        return float((terms / norms).max())

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


def frame_defect(metric: ElectricMetric, frame: VectorField) -> float:
    """Orthonormality defect max |F^H W F - I| of a formed frame, from a fresh product."""
    gram = metric.product(frame, frame)
    return float(np.abs(gram - np.eye(gram.shape[0])).max())


def excursion_bound(rank: int, defect_previous: float, defect_current: float) -> float:
    """Largest roundoff excursion of sigma^2 above one implied by measured frame defects.

    The defects must be measured on the formed frames (frame_defect).
    """
    return (1 + rank * defect_previous) * (1 + rank * defect_current) - 1 + SINGULAR_ROUNDOFF


def principal_values(cross: np.ndarray, excursion_max: float = SINGULAR_ROUNDOFF
                     ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """SVD of the whitened cross Gram P^H W Q = L diag(sigma) V^H.

    Returns (sigma^2 descending, L, V^H). sigma are the cosines of principal
    angles. Roundoff excursions above one are clipped only within
    ``excursion_max`` (see excursion_bound); larger ones indicate a metric or
    whitening failure.
    """
    if not np.isfinite(cross).all():
        raise ValueError("non-finite cross Gram matrix")
    left, sigma, right_h = np.linalg.svd(cross)
    squared = sigma ** 2
    if squared.size and squared.max() > 1 + excursion_max:
        raise ValueError(f"principal value {squared.max():.12g} exceeds one: frames are not orthonormal")
    return np.clip(squared, 0.0, 1.0), left, right_h


def projection_sin_max_angle(metric: ElectricMetric, previous: VectorField, current: VectorField,
                             cross: np.ndarray) -> float:
    """sin of the largest principal angle from the projection residual.

    With orthonormal frames P and Q and C = P^H W Q, the residual R = Q - P C
    satisfies R^H W R = I - C^H C, whose largest eigenvalue is sin^2(theta_max).
    Forming R directly avoids the cancellation in sqrt(1 - sigma^2) at small
    angles.
    """
    residual = VectorField(current.edges, current.transverse - previous.transverse @ cross,
                           current.longitudinal - previous.longitudinal @ cross,
                           current.electric - np.einsum("tmc,mk->tkc", previous.electric, cross))
    gram = metric.product(residual, residual)
    return float(math.sqrt(max(0.0, np.linalg.eigvalsh((gram + gram.conj().T) / 2)[-1])))


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
        self.previous_defects: list[float] | None = None     # their defects, measured on the formed frames
        self.ranks: list[int] | None = None

    def _fail(self, location, reason, action):
        raise ModeTrackingError(f"vector subspace sweep at {location}: {reason}; {action}")

    def _formed(self, raw, transform, condition, location, label):
        """Form raw @ transform and measure its orthonormality defect with a fresh product."""
        frame = columns(raw, transform)
        defect = frame_defect(self.metric, frame)
        if defect > ORTHONORMAL_DEFECT_MAX:
            size = frame.transverse.shape[0] + frame.longitudinal.shape[0]
            budget = frame_defect_budget(transform.shape[1], condition, size, self.metric.cancellation(raw))
            self._fail(location, f"{label}: formed frame is not orthonormal (defect {defect:.3g} > "
                       f"{ORTHONORMAL_DEFECT_MAX:g}; roundoff budget {budget:.3g})", "check the mesh and solved fields")
        return frame, defect

    def _whitened(self, field, start, stop, location, label):
        raw = columns(field, np.eye(field.transverse.shape[1])[:, start:stop])
        try:
            inverse_root, diagnostics = whiten(self.metric.product(raw, raw))
        except ValueError as exc:
            self._fail(location, f"{label}: {exc}", "check the mesh and solved fields")
        whitened, defect = self._formed(raw, inverse_root, diagnostics["gram_condition"], location, label)
        return raw, inverse_root, whitened, dict(diagnostics, orthonormal_defect=defect)

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
            chosen = self._seed(neff, components, location)
            scores = margins = principal = None
        else:
            chosen, scores, margins, principal = self._match(neff, field, components, saturated, location)

        raw_parts, transforms, frames, cluster_evidence = [], [], [], []
        for n, (start, stop) in enumerate(chosen):
            evidence, problems = _component_evidence(neff, (start, stop), saturated, settings)
            if problems:
                self._fail(location, f"cluster {n + 1} (candidate ranks {start + 1}-{stop}): " + "; ".join(problems),
                           "adjust cluster_span_max/external_gap_min, increase search_modes or narrow the interval")
            raw, inverse_root, whitened, diagnostics = self._whitened(field, start, stop, location,
                                                                      f"cluster {n + 1}")
            sin_max = None
            if self.previous is None:
                rotation = np.eye(stop - start)       # seed orientation is arbitrary
            else:
                cross = self.metric.product(self.previous[n], whitened)
                bound = excursion_bound(stop - start, self.previous_defects[n], diagnostics["orthonormal_defect"])
                _, left, right_h = principal_values(cross, bound)
                rotation = right_h.conj().T @ left.conj().T
                sin_max = projection_sin_max_angle(self.metric, self.previous[n], whitened, cross)
            transform = inverse_root @ rotation
            frame, defect = self._formed(raw, transform, diagnostics["gram_condition"], location, f"cluster {n + 1}")
            raw_parts.append(raw)
            transforms.append(transform)
            frames.append(frame)
            evidence.update(diagnostics, orthonormal_defect=defect)       # defect of the committed frame
            if principal is not None:
                evidence.update(principal_squared=principal[n].tolist(), min_principal_squared=float(principal[n][-1]),
                                score=scores[n], margin=margins[n],
                                sin_max_angle=sin_max)
            cluster_evidence.append(evidence)

        selected = np.concatenate([np.arange(a, b) for a, b in chosen])
        offsets = np.concatenate([[0], np.cumsum([b - a for a, b in chosen])])
        block = np.zeros((len(selected), len(selected)), dtype=complex)
        for n, transform in enumerate(transforms):
            block[offsets[n]:offsets[n + 1], offsets[n]:offsets[n + 1]] = transform
        raw_field = columns(field, np.eye(count)[:, selected])
        # commit only after every check passed
        self.previous = frames
        self.previous_defects = [c["orthonormal_defect"] for c in cluster_evidence]
        self.ranks = [b - a for a, b in chosen]
        evidence = dict(candidate_count=count, saturated=bool(saturated),
                        candidate_ranks=(selected + 1).tolist(), clusters=cluster_evidence)
        return neff[selected], raw_field, block, offsets, evidence

    def _seed(self, neff, components, location):
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
                inverse_root, whitening = whiten(self.metric.product(raw, raw))
            except ValueError as exc:
                # A candidate of a tracked rank that cannot be whitened might be the true
                # continuation; dropping it would hide that from the assignment and margins.
                self._fail(location, f"candidate cluster at ranks {start + 1}-{stop}: {exc}",
                           "check the mesh and solved fields")
            whitened, defect = self._formed(raw, inverse_root, whitening["gram_condition"], location,
                                            f"candidate cluster at ranks {start + 1}-{stop}")
            candidates.append(((start, stop), whitened, defect))
        observed = [b - a for a, b in components]
        if not candidates:
            self._fail(location, f"no candidate cluster has a tracked rank {self.ranks} (observed component ranks "
                       f"{observed})", "reduce the wavelength step, adjust cluster_span_max or increase search_modes")
        scores = np.zeros((len(self.previous), len(candidates)))
        allowed = np.zeros_like(scores, dtype=bool)
        spectra = {}
        for i, frame in enumerate(self.previous):
            for j, ((start, stop), whitened, defect) in enumerate(candidates):
                if stop - start != self.ranks[i]:
                    continue
                bound = excursion_bound(stop - start, self.previous_defects[i], defect)
                try:
                    squared, _, _ = principal_values(self.metric.product(frame, whitened), bound)
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
                           f"a direction was lost, or the partition changed: tracked ranks {self.ranks}, "
                           f"observed component ranks {observed})",
                           "reduce the wavelength step, expand search_modes or check cluster_span_max")
            if margins[i] is not None and margins[i] < self.settings["min_margin"]:
                self._fail(location, f"cluster {i + 1} has ambiguous assignment margin {margins[i]:.6g} "
                           f"< min_margin {self.settings['min_margin']:g}", "reduce the wavelength step")
            chosen.append(candidates[j][0])
            principal.append(squared)
            chosen_scores.append(float(squared.mean()))
        return chosen, chosen_scores, margins, principal
