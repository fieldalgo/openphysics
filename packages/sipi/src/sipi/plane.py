# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""DC voltage drop (IR drop) on a PCB power plane.

A plane is a copper sheet of thickness t and conductivity sigma, with an
outline polygon and holes (cutouts and terminal pads). Being thin, its
potential does not vary through the thickness, so the in-plane problem is

    div(sigma t grad V) = 0   on the copper,

which is galerkin's steady 2D conduction with the sheet thickness as the
extrusion depth (docs: electric_steady2d.md). Terminals are holes:

- a ``Source`` (voltage regulator, VRM) holds its edge at a fixed voltage;
- a ``Sink`` (load) draws its current uniformly over its edge, J.n = I / (P t)
  with P the edge length. A real pad is equipotential with an unknown current
  distribution; the uniform draw is the usual simplification and its effect
  shrinks with pad size relative to the distance to other terminals.

All other edges are insulated. Lengths are metres, conductivity S/m.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from galerkin import Mesh, from_mesher
from galerkin.electric import solve_steady_electric
from meshine import Circle, Domain, generate

__all__ = ["COPPER_CONDUCTIVITY", "circle", "rectangle_outline", "edge", "Source", "Sink",
           "PowerPlane", "IRDropResult"]

#: Annealed copper at 20 °C, the 100 % IACS reference: 58.0 MS/m by definition
#: (1/58 ohm mm^2/m).
COPPER_CONDUCTIVITY = 5.8e7


def circle(center, radius: float, n: int = 32) -> Circle:
    """A circular pad or hole (meshine keeps refined nodes on the true circle)."""
    if not (np.isfinite(radius) and radius > 0):
        raise ValueError("radius must be > 0")
    return Circle((float(center[0]), float(center[1])), float(radius), n=n)


def rectangle_outline(x0: float, y0: float, x1: float, y1: float) -> np.ndarray:
    """Counter-clockwise rectangle vertices, for the outline or a hole."""
    if not (x1 > x0 and y1 > y0):
        raise ValueError("need x1 > x0 and y1 > y0")
    return np.array([[x0, y0], [x1, y0], [x1, y1], [x0, y1]], dtype=float)


@dataclass(frozen=True)
class _Edge:
    p0: tuple
    p1: tuple


def edge(p0, p1) -> _Edge:
    """A straight piece of the outline, from vertex p0 to vertex p1, used as a contact.

    Both points must be vertices of the outline polygon, and the piece must lie
    on one outline side, so that mesh edges between them follow it exactly.
    """
    a, b = np.asarray(p0, dtype=float), np.asarray(p1, dtype=float)
    if a.shape != (2,) or b.shape != (2,) or not np.all(np.isfinite([*a, *b])) or np.allclose(a, b):
        raise ValueError("edge needs two distinct finite (x, y) points")
    return _Edge(tuple(a), tuple(b))


def _segment_distance(a, b, p: np.ndarray) -> np.ndarray:
    a, b = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    ab = b - a
    t = np.clip((p - a) @ ab / (ab @ ab), 0, 1)
    return np.hypot(*(p - (a + t[:, None] * ab)).T)


def _vertices(shape) -> np.ndarray:
    return shape.vertices() if isinstance(shape, Circle) else np.asarray(shape, dtype=float)


def _distance_to_shape(shape, p: np.ndarray) -> np.ndarray:
    """Distance from points (k, 2) to the boundary of a circle or polygon."""
    if isinstance(shape, Circle):
        c = np.asarray(shape.center, dtype=float)
        return np.abs(np.hypot(*(p - c).T) - shape.radius)
    v = _vertices(shape)
    a, b = v, np.roll(v, -1, axis=0)
    ab = b - a
    t = np.clip(np.einsum("kej,ej->ke", p[:, None, :] - a, ab) / np.einsum("ej,ej->e", ab, ab), 0, 1)
    closest = a + t[..., None] * ab
    return np.min(np.hypot(*(p[:, None, :] - closest).transpose(2, 0, 1)), axis=1)


def _is_edge(shape) -> bool:
    return isinstance(shape, _Edge)


def _is_outline(shape) -> bool:
    return isinstance(shape, str) and shape == "outline"


def _scale(shape) -> float:
    if isinstance(shape, Circle):
        return 2.0 * shape.radius
    v = _vertices(shape)
    return float(np.min(np.ptp(v, axis=0)))


@dataclass(frozen=True)
class Source:
    """A terminal held at ``voltage`` (V): a VRM output or a fixed rail feed.

    shape: a hole (``circle`` or polygon) whose edge is the contact, a straight
    piece of the outline (``edge``), or the string "outline" to use the
    plane's whole outer edge.
    """

    name: str
    shape: object
    voltage: float


@dataclass(frozen=True)
class Sink:
    """A terminal drawing ``current`` (A) out of the plane, spread uniformly over its edge.

    shape: as for ``Source``.
    """

    name: str
    shape: object
    current: float


@dataclass(frozen=True)
class IRDropResult:
    """Solution of a PowerPlane.

    mesh:            galerkin mesh of the copper (metres)
    potential:       nodal voltage (V)
    current_density: element current density J (A/m^2), shape (T, 2)
    sheet_current:   element sheet current J t (A/m), shape (T, 2)
    power_loss:      Joule loss in the plane (W)
    terminals:       {name: {"mean", "min", "max": edge voltage (V),
                             "current": current into the plane (A)}}
                     Sources inject positive current; sinks report -current.
    """

    mesh: Mesh
    potential: np.ndarray
    current_density: np.ndarray
    sheet_current: np.ndarray
    power_loss: float
    terminals: dict
    thickness: float

    def drop(self, sink: str, source: str | None = None) -> float:
        """Source voltage minus the mean voltage on ``sink``'s edge (V)."""
        sources = [n for n, t in self.terminals.items() if t["kind"] == "source"]
        if source is None:
            if len(sources) != 1:
                raise ValueError("name the source: the plane has several")
            source = sources[0]
        return self.terminals[source]["mean"] - self.terminals[sink]["mean"]

    def resistance(self, sink: str, source: str | None = None) -> float:
        """Effective DC resistance drop(sink) / current(sink) (ohm)."""
        current = -self.terminals[sink]["current"]
        return self.drop(sink, source) / current

    @property
    def max_current_density(self) -> float:
        """Largest element |J| (A/m^2), for current-crowding checks."""
        return float(np.max(np.hypot(*self.current_density.T)))


class PowerPlane:
    """A copper plane with an outline, holes and terminals (see module docstring).

    outline:      polygon vertices (m) or a ``circle``
    thickness:    copper thickness (m), e.g. 35e-6 for 1 oz
    conductivity: S/m, default annealed copper at 20 °C
    holes:        cutouts (polygons or circles), insulated
    sources, sinks: terminals; each is a hole whose edge is the contact
    """

    def __init__(self, outline, thickness: float, *, conductivity: float = COPPER_CONDUCTIVITY,
                 holes=(), sources=(), sinks=()):
        self.outline = outline if isinstance(outline, Circle) else np.asarray(outline, dtype=float)
        if not isinstance(self.outline, Circle) and (
                self.outline.ndim != 2 or self.outline.shape[1] != 2 or len(self.outline) < 3):
            raise ValueError("outline must be a circle or a polygon of >= 3 (x, y) vertices")
        self.thickness = float(thickness)
        self.conductivity = float(conductivity)
        if not (np.isfinite(self.thickness) and self.thickness > 0):
            raise ValueError("thickness must be > 0")
        if not (np.isfinite(self.conductivity) and self.conductivity > 0):
            raise ValueError("conductivity must be > 0")
        self.holes = tuple(holes)
        self.sources = tuple(sources)
        self.sinks = tuple(sinks)
        if not self.sources:
            raise ValueError("at least one Source is needed to fix the voltage level")
        names = [t.name for t in (*self.sources, *self.sinks)]
        if len(set(names)) != len(names) or "outline" in names or "cutout" in names:
            raise ValueError("terminal names must be unique and not 'outline' or 'cutout'")
        if sum(_is_outline(t.shape) for t in (*self.sources, *self.sinks)) > 1:
            raise ValueError("only one terminal can use the outline as its contact")
        for s in self.sources:
            if not np.isfinite(s.voltage):
                raise ValueError(f"source {s.name!r}: voltage must be finite")
        for s in self.sinks:
            if not (np.isfinite(s.current) and s.current > 0):
                raise ValueError(f"sink {s.name!r}: current must be > 0 (A drawn from the plane)")

    def _outline_name(self):
        """The terminal that uses the whole outline as its contact, else 'outline'."""
        named = [t.name for t in (*self.sources, *self.sinks) if _is_outline(t.shape)]
        return named[0] if named else "outline"

    def _shapes(self):
        """(name, shape) for every hole: terminals by name, cutouts as 'cutout'."""
        return ([(t.name, t.shape) for t in (*self.sources, *self.sinks)
                 if not (_is_outline(t.shape) or _is_edge(t.shape))]
                + [("cutout", h) for h in self.holes])

    def _edge_terminals(self):
        return [(t.name, t.shape) for t in (*self.sources, *self.sinks) if _is_edge(t.shape)]

    def mesh(self, *, edge_size: float | None = None, far_size: float | None = None,
             grade: float = 0.2, min_angle: float = 28.0) -> Mesh:
        """Mesh the copper, refined toward the terminals.

        edge_size: target edge length on terminal edges (default: smallest
                   terminal size / 12)
        far_size:  largest edge length (default: outline extent / 30)
        grade:     growth of the edge length per unit distance from terminals
        """
        shapes = self._shapes()
        extent = float(np.max(np.ptp(_vertices(self.outline), axis=0)))
        terminals = [s for n, s in shapes if n != "cutout"]
        if self._outline_name() != "outline":
            terminals.append(self.outline)
        edge_terms = self._edge_terminals()
        if edge_terms and isinstance(self.outline, Circle):
            raise ValueError("edge terminals need a polygon outline")
        scales = [_scale(s) for s in terminals] + [
            float(np.hypot(*np.subtract(e.p1, e.p0))) for _, e in edge_terms]
        if edge_size is None:
            edge_size = min(scales) / 12.0
        if far_size is None:
            far_size = extent / 30.0
        if not (0 < edge_size <= far_size):
            raise ValueError("need 0 < edge_size <= far_size")

        domain = Domain(size=far_size)
        domain.add_region("copper", self.outline, holes=[s for _, s in shapes])

        def size_fn(x, y):
            p = np.column_stack([np.ravel(x), np.ravel(y)])
            d = np.min(np.stack([_distance_to_shape(s, p) for s in terminals]
                                + [_segment_distance(e.p0, e.p1, p) for _, e in edge_terms]), axis=0)
            return np.minimum(edge_size + grade * d, far_size).reshape(np.shape(x))

        tol = 1e-9 * extent

        def namer(mid):
            p = np.asarray([mid], dtype=float)
            for name, e in edge_terms:
                if _segment_distance(e.p0, e.p1, p)[0] <= tol:
                    return name
            candidates = [(self._outline_name(), self.outline), *shapes]
            dist = [float(_distance_to_shape(s, p)[0]) for _, s in candidates]
            return candidates[int(np.argmin(dist))][0]

        mesh = from_mesher(generate(domain, namer, min_angle=min_angle, size_fn=size_fn,
                                    candidate_order="stable"))
        for name in [t.name for t in (*self.sources, *self.sinks)]:
            if name not in mesh.boundary_edges:
                raise RuntimeError(f"terminal {name!r} received no boundary edges; "
                                   "check that it lies inside the outline and does not overlap a hole")
        return mesh

    def solve(self, **mesh_options) -> IRDropResult:
        """Mesh (``mesh`` options) and solve the DC voltage distribution."""
        mesh = self.mesh(**mesh_options)
        t = self.thickness
        edges = mesh.boundary_edges
        p = mesh.nodes

        def edge_length(tag):
            e = edges[tag]
            return float(np.sum(np.hypot(*(p[e[:, 1]] - p[e[:, 0]]).T)))

        dirichlet = {}
        for s in self.sources:
            for node in np.unique(edges[s.name]):
                dirichlet[int(node)] = float(s.voltage)
        # Galerkin works per metre of depth; with depth t, J.n = I / (P t) carries I.
        outward = {s.name: s.current / (edge_length(s.name) * t) for s in self.sinks}
        r = solve_steady_electric(mesh, conductivity=self.conductivity,
                                  dirichlet=dirichlet, outward_current=outward)

        terminals = {}
        for kind, group in (("source", self.sources), ("sink", self.sinks)):
            for s in group:
                e = edges[s.name]
                lengths = np.hypot(*(p[e[:, 1]] - p[e[:, 0]]).T)
                v = r.potential[e]
                mean = float(np.sum(lengths * v.mean(axis=1)) / np.sum(lengths))
                if kind == "source":
                    current = float(np.sum(r.reaction[np.unique(e)]) * t)
                else:
                    current = -float(s.current)
                terminals[s.name] = {"kind": kind, "mean": mean, "min": float(v.min()),
                                     "max": float(v.max()), "current": current}
        return IRDropResult(mesh=r.mesh, potential=r.potential, current_density=r.current_density,
                            sheet_current=r.current_density * t,
                            power_loss=float(r.joule_power_per_length * t),
                            terminals=terminals, thickness=t)
