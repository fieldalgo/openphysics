# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Layered PCB cross-sections with rectangular or centred trapezoidal traces.

A ``CrossSection`` is a stack of dielectric layers between x = -width/2 and
x = +width/2, starting at y = 0 and growing upward. A trace of zero thickness
is a strip on a horizontal line; a finite trace is a solid rectangle or a
centred trapezoid that the mesh leaves out. All
lengths are in metres.

Boundaries of the box:
  bottom  "ground" (a reference plane at y = 0) or "open"
  top     "ground" (a reference plane at the top of the stack) or "open"
  sides   "ground" (grounded walls) or "open"
"open" is an insulating wall (zero normal D). Placing it far from the traces
approximates an unbounded cross-section; the truncation error must be checked
by moving it (see the package documentation).

Microstrip: bottom ground, a substrate layer and an air layer, a trace on the
substrate. Stripline: ground on both sides, the trace between two layers.
"""

from __future__ import annotations

from dataclasses import dataclass
from numbers import Real

import numpy as np

from galerkin import Mesh, from_mesher
from meshine import Domain, generate, rectangle

from .quasistatic import LineParameters, line_parameters

__all__ = ["Layer", "Trace", "CrossSection", "MeshedCrossSection"]

_BOUNDARY = ("ground", "open")


@dataclass(frozen=True)
class Layer:
    """A dielectric layer: thickness (m), relative permittivity, loss tangent."""

    name: str
    thickness: float
    eps_r: float = 1.0
    tan_delta: float = 0.0

    def __post_init__(self):
        if not self.name:
            raise ValueError("a layer needs a name")
        if not (np.isfinite(self.thickness) and self.thickness > 0):
            raise ValueError(f"layer {self.name!r}: thickness must be > 0")
        if not (np.isfinite(self.eps_r) and self.eps_r >= 1.0):
            raise ValueError(f"layer {self.name!r}: eps_r must be >= 1")
        if not (np.isfinite(self.tan_delta) and self.tan_delta >= 0):
            raise ValueError(f"layer {self.name!r}: tan_delta must be >= 0")


@dataclass(frozen=True)
class Trace:
    """A rectangular or centred trapezoidal conductor.

    x:         centre of the trace (m)
    width:     bottom-face width (m)
    y:         bottom face of the trace (m); a zero-thickness trace lies on y
    thickness: 0 for an infinitely thin strip
    ground:    True for a reference conductor held at 0 V (e.g. coplanar ground)
    top_width: optional top-face width (m); None retains a rectangle
    """

    name: str
    x: float
    width: float
    y: float
    thickness: float = 0.0
    ground: bool = False
    top_width: float | None = None

    def __post_init__(self):
        if not self.name:
            raise ValueError("a trace needs a name")
        for label in ("x", "width", "y", "thickness"):
            if not np.isfinite(getattr(self, label)):
                raise ValueError(f"trace {self.name!r}: {label} must be finite")
        if self.width <= 0:
            raise ValueError(f"trace {self.name!r}: width must be > 0")
        if self.thickness < 0:
            raise ValueError(f"trace {self.name!r}: thickness must be >= 0")

        if self.top_width is not None:
            if (isinstance(self.top_width, bool) or not isinstance(self.top_width, Real)
                    or not np.isfinite(self.top_width) or self.top_width <= 0):
                raise ValueError(f"trace {self.name!r}: top_width must be finite and > 0")
            if self.thickness == 0 and self.top_width != self.width:
                raise ValueError('a zero-thickness strip cannot have different top and bottom widths')

    @property
    def tapered(self) -> bool:
        return self.top_width is not None and self.top_width != self.width

    def width_at(self, y):
        """Linear face width at y; clamp beyond the trace's vertical extent."""
        if not self.tapered:
            return np.zeros_like(np.asarray(y, dtype=float)) + self.width
        return self.width + (self.top_width-self.width)*np.clip((np.asarray(y)-self.y)/self.thickness, 0, 1)

    @property
    def xmin(self):
        return self.x - max(self.width, self.top_width or self.width)/2

    @property
    def xmax(self):
        return self.x + max(self.width, self.top_width or self.width)/2

    @property
    def x0(self) -> float:
        return self.x - 0.5 * self.width

    @property
    def x1(self) -> float:
        return self.x + 0.5 * self.width

    @property
    def y1(self) -> float:
        return self.y + self.thickness

    def corners(self) -> np.ndarray:
        if self.thickness == 0:
            return np.array([[self.x0, self.y], [self.x1, self.y]])
        top = self.width if self.top_width is None else self.top_width
        return np.array([[self.x0, self.y], [self.x1, self.y],
                         [self.x+top/2, self.y1], [self.x-top/2, self.y1]])

    def distance(self, x: np.ndarray, y: np.ndarray) -> np.ndarray:
        """Euclidean distance to the conductor (0 inside)."""
        if self.tapered:
            x, y = np.broadcast_arrays(np.asarray(x, dtype=float), np.asarray(y, dtype=float))
            points = np.stack((x, y), axis=-1)
            vertices = self.corners()
            distances = []
            for a, b in zip(vertices, np.roll(vertices, -1, axis=0)):
                edge = b-a
                u = np.clip(np.sum((points-a)*edge, axis=-1)/np.dot(edge, edge), 0, 1)
                distances.append(np.linalg.norm(points-a-u[..., None]*edge, axis=-1))
            inside = (y >= self.y) & (y <= self.y1) & (np.abs(x-self.x) <= self.width_at(y)/2)
            return np.where(inside, 0, np.min(distances, axis=0))
        dx = np.maximum(np.maximum(self.x0 - x, x - self.x1), 0.0)
        dy = np.maximum(np.maximum(self.y - y, y - self.y1), 0.0)
        return np.hypot(dx, dy)


@dataclass(frozen=True)
class MeshedCrossSection:
    """A meshed cross-section ready for ``line_parameters``.

    mesh:      galerkin mesh of the dielectric (traces with thickness are holes)
    eps_r, tan_delta: one value per triangle
    signals:   {trace name: node indices}, in the order traces were given
    ground:    node indices at 0 V (reference planes, grounded walls, ground traces)
    """

    mesh: Mesh
    eps_r: np.ndarray
    tan_delta: np.ndarray
    signals: dict
    ground: np.ndarray

    def line_parameters(self) -> LineParameters:
        return line_parameters(self.mesh, self.eps_r, self.signals, self.ground,
                               tan_delta=self.tan_delta)


class CrossSection:
    """Layered cross-section with rectangular/trapezoidal traces (see module docstring)."""

    def __init__(self, layers, traces, width: float, *, bottom: str = "ground",
                 top: str = "open", sides: str = "open"):
        self.layers = tuple(layers)
        self.traces = tuple(traces)
        self.width = float(width)
        self.bottom, self.top, self.sides = bottom, top, sides
        if not self.layers:
            raise ValueError("at least one layer is needed")
        if not all(isinstance(lay, Layer) for lay in self.layers):
            raise TypeError("layers must be Layer instances")
        if not all(isinstance(t, Trace) for t in self.traces):
            raise TypeError("traces must be Trace instances")
        for label, value in (("bottom", bottom), ("top", top), ("sides", sides)):
            if value not in _BOUNDARY:
                raise ValueError(f"{label} must be one of {_BOUNDARY}, not {value!r}")
        if not (np.isfinite(self.width) and self.width > 0):
            raise ValueError("width must be > 0")
        names = [lay.name for lay in self.layers]
        if len(set(names)) != len(names):
            raise ValueError("layer names must be unique")
        names = [t.name for t in self.traces]
        if len(set(names)) != len(names):
            raise ValueError("trace names must be unique")
        if not any(not t.ground for t in self.traces):
            raise ValueError("at least one signal trace (ground=False) is needed")
        if bottom == "open" and top == "open" and sides == "open" \
                and not any(t.ground for t in self.traces):
            raise ValueError("no reference conductor: ground a boundary or add a ground trace")
        self._check_placement()

    @property
    def height(self) -> float:
        return float(sum(lay.thickness for lay in self.layers))

    def interfaces(self) -> np.ndarray:
        """y of every layer boundary, from 0 to the top of the stack."""
        return np.concatenate([[0.0], np.cumsum([lay.thickness for lay in self.layers])])

    def _check_placement(self):
        half, H = 0.5 * self.width, self.height
        tol = 1e-12 * max(self.width, H)
        for t in self.traces:
            if t.xmin <= -half + tol or t.xmax >= half - tol:
                raise ValueError(f"trace {t.name!r} must lie strictly inside the side walls")
            if t.y <= tol or t.y1 >= H - tol:
                raise ValueError(f"trace {t.name!r} must lie strictly between the bottom "
                                 "and the top of the stack (a trace on a reference plane "
                                 "is that plane)")
        for i, a in enumerate(self.traces):
            for b in self.traces[i + 1:]:
                gap_y = max(a.y - b.y1, b.y - a.y1)
                if a.tapered or b.tapered:
                    # The horizontal gap is affine on the common vertical span;
                    # its minimum is at an endpoint. Bounding boxes alone can
                    # falsely reject two disjoint tapered conductors.
                    low, high = max(a.y, b.y), min(a.y1, b.y1)
                    gap_x = min(abs(a.x-b.x)-(a.width_at(y)+b.width_at(y))/2
                                for y in (low, high))
                else:
                    gap_x = max(a.x0 - b.x1, b.x0 - a.x1)
                if gap_x <= tol and gap_y <= tol:
                    raise ValueError(f"traces {a.name!r} and {b.name!r} touch or overlap")

    def _layer_at(self, y: float) -> Layer:
        edges = self.interfaces()
        k = int(np.clip(np.searchsorted(edges, y, side="right") - 1, 0, len(self.layers) - 1))
        return self.layers[k]

    def _sizes(self, edge_size, far_size):
        features = [lay.thickness for lay in self.layers]
        for t in self.traces:
            features.append(min(t.width, t.top_width or t.width))
        for i, a in enumerate(self.traces):
            for b in self.traces[i + 1:]:
                if a.tapered or b.tapered:
                    # Conservative bounding-box gap can vanish even for disjoint
                    # shapes. Use their exact polygon/segment distance instead.
                    corners_a, corners_b = a.corners(), b.corners()
                    gap = min(np.min(a.distance(corners_b[:, 0], corners_b[:, 1])),
                              np.min(b.distance(corners_a[:, 0], corners_a[:, 1])))
                    features.append(gap)
                else:
                    features.append(max(a.x0 - b.x1, b.x0 - a.x1, a.y - b.y1, b.y - a.y1))
        if edge_size is None:
            edge_size = min(features) / 100.0
            # The conductor interior is excluded from the mesh. Resolve its
            # side face without imposing thickness / 100 along the entire trace.
            for t in self.traces:
                if t.thickness > 0:
                    edge_size = min(edge_size, t.thickness / 10.0)
        if far_size is None:
            far_size = max(self.width, self.height) / 24.0
        if not (edge_size > 0 and far_size >= edge_size):
            raise ValueError("need 0 < edge_size <= far_size")
        return float(edge_size), float(far_size)

    def mesh_settings(self, *, edge_size=None, far_size=None, grade=0.15, min_angle=28.0):
        """Resolve and validate mesh options without generating a mesh.

        Return a fresh dictionary suitable for ``mesh(**settings)``. Lengths
        are metres, grade is dimensionless and min_angle is in degrees.
        """
        for key, value in (('edge_size', edge_size), ('far_size', far_size),
                           ('grade', grade), ('min_angle', min_angle)):
            if value is None and key in ('edge_size', 'far_size'):
                continue
            if isinstance(value, bool) or not isinstance(value, Real) or not np.isfinite(value):
                raise ValueError(f'{key} must be a finite real number')
        edge_size, far_size = self._sizes(edge_size, far_size)
        if grade < 0:
            raise ValueError('grade must be >= 0')
        if not 0 < min_angle < 34:
            raise ValueError('min_angle must be in (0, 34) degrees')
        return dict(edge_size=edge_size, far_size=far_size,
                    grade=float(grade), min_angle=float(min_angle))

    def _tapered_domain(self, ys, far_size):
        """Tile each horizontal slab with exact dielectric quadrilaterals.

        Layer interfaces and every conductor top/bottom split the slabs. The
        affine trace sides become shared constrained segments, including where
        they cross a material interface. Thin strips insert collinear vertices
        into slab boundaries, so their full length is a constrained interface.
        """
        domain = Domain(size=far_size)
        half = self.width/2
        for y0, y1 in zip(ys[:-1], ys[1:]):
            ym = (y0+y1)/2
            solids = sorted((t for t in self.traces if t.thickness > 0 and t.y < ym < t.y1),
                            key=lambda t: t.x)
            left = (-half, -half)
            for trace in [*solids, None]:
                right = (half, half) if trace is None else (
                    trace.x-float(trace.width_at(y0))/2, trace.x-float(trace.width_at(y1))/2)
                bottom_x = [left[0], right[0]]
                top_x = [left[1], right[1]]
                for thin in self.traces:
                    if thin.thickness != 0:
                        continue
                    for y, values, lo, hi in ((y0, bottom_x, left[0], right[0]),
                                              (y1, top_x, left[1], right[1])):
                        if thin.y == y:
                            values.extend(x for x in (thin.x0, thin.x1) if lo < x < hi)
                polygon = [(x, y0) for x in sorted(set(bottom_x))]
                polygon += [(x, y1) for x in sorted(set(top_x), reverse=True)]
                domain.add_region(self._layer_at(ym).name, polygon)
                if trace is not None:
                    left = (trace.x+float(trace.width_at(y0))/2, trace.x+float(trace.width_at(y1))/2)
        return domain

    def mesh(self, *, edge_size: float | None = None, far_size: float | None = None,
             grade: float = 0.15, min_angle: float = 28.0) -> MeshedCrossSection:
        """Mesh the dielectric with refinement toward the trace edges.

        edge_size: target edge length at trace corners (default: the smallest
                   layer thickness, trace width or inter-trace gap / 100,
                   capped at each positive trace thickness / 10).
                   Field singularities sit at these corners. Explicit values
                   override both parts of the default rule.
        far_size:  largest edge length (default: max(width, height) / 24)
        grade:     growth of the edge length per unit distance from the traces

        The defaults stayed within 0.5 % in impedance on the validation cases;
        halve edge_size, grade and far_size together to check convergence.
        """
        settings = self.mesh_settings(edge_size=edge_size, far_size=far_size,
                                      grade=grade, min_angle=min_angle)
        edge_size, far_size = settings['edge_size'], settings['far_size']
        grade, min_angle = settings['grade'], settings['min_angle']
        half = 0.5 * self.width
        xs = {-half, half}
        ys = set(self.interfaces().tolist())
        for t in self.traces:
            xs.update((t.x0, t.x1))
            ys.update((t.y, t.y1))
        xs, ys = np.array(sorted(xs)), np.array(sorted(ys))
        solids = [t for t in self.traces if t.thickness > 0]

        if any(t.tapered for t in self.traces):
            domain = self._tapered_domain(ys, far_size)
        else:
            # Preserve the established rectangular discretization exactly.
            domain = Domain(size=far_size)
            for j in range(len(ys) - 1):
                ym = 0.5 * (ys[j] + ys[j + 1])
                layer = self._layer_at(ym)
                for i in range(len(xs) - 1):
                    xm = 0.5 * (xs[i] + xs[i + 1])
                    if any(t.x0 < xm < t.x1 and t.y < ym < t.y1 for t in solids):
                        continue
                    domain.add_region(layer.name, rectangle(xs[i], ys[j], xs[i + 1], ys[j + 1]))

        corners = np.concatenate([t.corners() for t in self.traces])

        def size_fn(x, y):
            x, y = np.asarray(x, dtype=float), np.asarray(y, dtype=float)
            d_corner = np.min(np.hypot(x[..., None] - corners[:, 0],
                                       y[..., None] - corners[:, 1]), axis=-1)
            d_trace = np.min(np.stack([t.distance(x, y) for t in self.traces]), axis=0)
            h = np.minimum(edge_size + grade * d_corner, 3.0 * edge_size + grade * d_trace)
            return np.minimum(h, far_size)

        tm = generate(domain, "outer", min_angle=min_angle, size_fn=size_fn,
                      candidate_order="stable")
        mesh = from_mesher(tm)

        names = mesh.region_names
        by_name = {lay.name: lay for lay in self.layers}
        eps_r = np.array([by_name[names[r]].eps_r for r in mesh.regions])
        tan_delta = np.array([by_name[names[r]].tan_delta for r in mesh.regions])

        p = mesh.nodes
        tol = 1e-9 * float(np.hypot(self.width, self.height))
        H = self.height
        ground = np.zeros(len(p), dtype=bool)
        if self.bottom == "ground":
            ground |= np.abs(p[:, 1]) <= tol
        if self.top == "ground":
            ground |= np.abs(p[:, 1] - H) <= tol
        if self.sides == "ground":
            ground |= np.abs(np.abs(p[:, 0]) - half) <= tol

        signals = {}
        for t in self.traces:
            on = (t.distance(p[:, 0], p[:, 1]) <= tol) if t.tapered else (
                (p[:, 0] >= t.x0 - tol) & (p[:, 0] <= t.x1 + tol)
                & (p[:, 1] >= t.y - tol) & (p[:, 1] <= t.y1 + tol))
            if not on.any():
                raise RuntimeError(f"trace {t.name!r} received no mesh nodes")
            if t.ground:
                ground |= on
            else:
                signals[t.name] = np.flatnonzero(on)
        return MeshedCrossSection(mesh=mesh, eps_r=eps_r, tan_delta=tan_delta,
                                  signals=signals, ground=np.flatnonzero(ground))

    def analyze(self, **mesh_options) -> LineParameters:
        """Mesh (``mesh`` options) and return the per-unit-length parameters."""
        return self.mesh(**mesh_options).line_parameters()
