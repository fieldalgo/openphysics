# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""What the geometric queries of the refinement cost, and that bounding them changed no mesh.

* Encroachment. ``meshine.refine`` asked a tree of segment midpoints, for each bad
  triangle's circumcenter, for every midpoint within the radius of the *longest* segment,
  then kept only the pairs strictly inside the diametral circle of their own segment.
  Next to a long segment almost every pair it built was thrown away. ``_encroached`` now
  asks a tree of the candidates, once per segment, with that segment's own radius.

The old implementation is kept here as a private reference. ``generate`` must give the
same mesh, or raise the same error, with it patched back in; nothing is stored, both are
computed here. The pass criteria were fixed before the change, from measurements on its
prototype: the measured values are quoted next to them.
"""

import importlib.util
import math
import random
from pathlib import Path

import numpy as np
import pytest
from scipy.spatial import cKDTree

from meshine import Circle, Domain, box_sides, generate, rectangle, shapes
from meshine import refine

HERE = Path(__file__).resolve().parent


# ---- the implementations before this change, kept as references ----------------------

def _old_encroached(cand, mids, half):
    """The encroachment test as ``generate`` ran it inline: each candidate asks a tree of
    segment midpoints for every one within the largest half-length of all segments."""
    seg_tree = cKDTree(mids)
    hmax = half.max()
    encroaches = np.zeros(len(cand), dtype=bool)
    near_lists = seg_tree.query_ball_point(cand, hmax)
    ci_idx = np.repeat(np.arange(len(cand)), [len(lst) for lst in near_lists])
    si_idx = np.fromiter((si for lst in near_lists for si in lst), dtype=int, count=len(ci_idx))
    if not len(ci_idx):
        return encroaches, np.empty(0, dtype=np.int64)
    dist = np.linalg.norm(cand[ci_idx] - mids[si_idx], axis=1)
    hit = dist < half[si_idx] * (1 - 1e-9)
    encroaches[ci_idx[hit]] = True
    return encroaches, np.unique(si_idx[hit])


OLD = {"_encroached": _old_encroached}


# ---- a spy on the tree queries ---------------------------------------------------------

class QueryLog:
    """Results returned by each ``query_ball_point`` call in ``meshine.refine``, with the
    patched helper the call was made from (None outside every one of them)."""

    def __init__(self):
        self.calls: list[tuple[str | None, int]] = []
        self.inside: list[str] = []

    def largest(self, where=...) -> int:
        counts = [n for at, n in self.calls if where is ... or at == where]
        return max(counts, default=0)


def spy_on_queries(monkeypatch, *helpers) -> QueryLog:
    """Count the results of every tree query ``generate`` makes. ``query_ball_point`` is a
    method of an extension type and cannot be patched on it, so ``meshine.refine.cKDTree``
    is replaced by a counting subclass."""
    log = QueryLog()

    class CountingTree(cKDTree):
        def query_ball_point(self, x, r, *args, **kwargs):
            found = super().query_ball_point(x, r, *args, **kwargs)
            lists = found if getattr(found, "dtype", None) == object else [found]
            log.calls.append((log.inside[-1] if log.inside else None, sum(len(lst) for lst in lists)))
            return found

    monkeypatch.setattr(refine, "cKDTree", CountingTree)
    for name in helpers:
        def tagged(*args, _real=getattr(refine, name), _name=name, **kwargs):
            log.inside.append(_name)
            try:
                return _real(*args, **kwargs)
            finally:
                log.inside.pop()
        monkeypatch.setattr(refine, name, tagged)
    return log


# ---- B2a: the local query against a brute force ----------------------------------------

def brute_force_encroached(cand, mids, half):
    """Every candidate against every segment, with the same strict test."""
    dist = np.linalg.norm(cand[:, None, :] - mids[None, :, :], axis=2)
    hit = dist < half[None, :] * (1 - 1e-9)
    return hit.any(axis=1), np.nonzero(hit.any(axis=0))[0]


def random_encroachment_case(seed):
    """1000 candidates and 300 segments in the unit square, with half-lengths spread over
    two decades (1e-3 to 0.1), so that the largest is far from the typical one.

    Twenty of the segments have their midpoints on x = 0, 0.05 apart, and half-lengths up to
    0.02. Each gets four candidates on its own line y: exactly at the threshold ``half * (1 -
    1e-9)`` on the right and on the left (not encroaching), one ulp inside it (encroaching),
    and exactly at ``half`` (not encroaching). With the midpoint at x = 0 the difference of
    the x coordinates is the offset itself, and sqrt(t * t) == t in binary floating point,
    so the distance the test computes is exactly the offset. No other segment reaches these
    candidates: the other midpoints lie at x >= 0.2."""
    rng = np.random.default_rng(seed)
    mids = np.column_stack([rng.uniform(0.2, 1.0, 300), rng.uniform(0.0, 1.0, 300)])
    half = 10.0 ** rng.uniform(-3.0, -1.0, 300)
    cand = rng.uniform(0.0, 1.0, (1000, 2))
    edge = rng.choice(300, 20, replace=False)
    mids[edge] = np.column_stack([np.zeros(20), 0.025 + 0.05 * np.arange(20)])
    half[edge] = rng.uniform(0.002, 0.02, 20)
    rows = []
    for s in edge:
        threshold = half[s] * (1 - 1e-9)
        inside = np.nextafter(threshold, 0.0)
        for offset in (threshold, -threshold, inside, half[s]):
            rows.append((offset, mids[s, 1], s, offset == inside))
    for k, (x, y, _s, _inside) in enumerate(rows):
        cand[k] = (x, y)
    return cand, mids, half, rows


@pytest.mark.parametrize("seed", range(20))
def test_the_local_encroachment_query_equals_a_brute_force(seed):
    cand, mids, half, rows = random_encroachment_case(seed)
    got_mask, got_ids = refine._encroached(cand, mids, half)
    want_mask, want_ids = brute_force_encroached(cand, mids, half)
    assert np.array_equal(got_mask, want_mask)
    assert np.array_equal(got_ids, want_ids)
    assert 0 < got_mask.sum() < len(cand) and 0 < len(got_ids) < len(mids)      # not vacuous
    # the boundary candidates: their own segment counts them exactly as the strict test says
    for k, (x, y, s, inside) in enumerate(rows):
        dist = np.linalg.norm(cand[k] - mids[s])
        assert dist == abs(x), "the boundary point is not where the test computes it"
        assert (dist < half[s] * (1 - 1e-9)) == inside
        assert got_mask[k] == inside
        if inside:
            assert s in got_ids


# ---- B2b: a long segment beside a finely meshed region -------------------------------

def strip(width, size, max_points=300_000):
    """A strip from x = 1 to 39 of the given width and mesh size, centered in a 40 x 20 box
    of mesh size 1000: the box's sides stay single long segments next to a fine mesh."""
    y0, y1 = 10 - width / 2, 10 + width / 2
    band = [(1, y0), (39, y0), (39, y1), (1, y1)]
    d = Domain(size=1000.0)
    d.add_region("background", rectangle(0, 0, 40, 20), holes=[band], size=1000.0)
    d.add_region("strip", band, size=size)
    return d, {"boundary_names": box_sides(0, 40, 0, 20), "min_angle": 28.0, "max_points": max_points}


def test_the_encroachment_query_stays_local_beside_a_thin_strip(monkeypatch):
    """Pre-registered: the cap error, and at most 100,000 results from any one query.
    Measured: 8,192. With the radius of the longest segment the largest query returned
    8,298,339 and the run peaked at 1.04 GB."""
    log = spy_on_queries(monkeypatch, "_encroached")
    domain, kwargs = strip(0.005, 0.01, max_points=10003)
    with pytest.raises(RuntimeError, match="more than 10003 points"):
        generate(domain, **kwargs)
    assert any(at == "_encroached" for at, _n in log.calls), "the encroachment test was never reached"
    assert log.largest() <= 100_000


# ---- B2c: the same meshes and errors as the old implementations -----------------------

def load_test_module(name):
    """Another test module of this folder, for its input builders."""
    spec = importlib.util.spec_from_file_location(f"_refine_cost_{name}", HERE / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def regular_polygon(cx, cy, r, n):
    return [(cx + r * math.cos(2 * math.pi * k / n), cy + r * math.sin(2 * math.pi * k / n)) for k in range(n)]


def gear(cx, cy, r1, r2, n):
    """An n-point polygon that alternates between radii r1 and r2."""
    return [(cx + (r1 if k % 2 == 0 else r2) * math.cos(2 * math.pi * k / n),
             cy + (r1 if k % 2 == 0 else r2) * math.sin(2 * math.pi * k / n)) for k in range(n)]


def shape_in_box(outline, size=2.0, min_angle=28.0, max_points=300_000):
    d = Domain(size=size)
    d.add_region("background", rectangle(0, 0, 40, 20), holes=[outline])
    d.add_region("shape", outline)
    return d, {"boundary_names": box_sides(0, 40, 0, 20), "min_angle": min_angle, "max_points": max_points}


def small_rectangles(count=64):
    """``count`` squares of side 1 on a 12 x 12 grid over a 40 x 20 box, filled row by row."""
    nx = math.ceil(math.sqrt(2 * count))
    squares = []
    for k in range(count):
        x, y = (k % nx + 0.5) * 40 / nx, (k // nx + 0.5) * 20 / nx
        squares.append(rectangle(x - 0.5, y - 0.5, x + 0.5, y + 0.5))
    d = Domain(size=2.0)
    d.add_region("background", rectangle(0, 0, 40, 20), holes=squares)
    for k, sq in enumerate(squares):
        d.add_region(f"r{k}", sq)
    return d, {"boundary_names": box_sides(0, 40, 0, 20), "min_angle": 28.0}


#: A sawtooth of 254 teeth with tips 10 degrees wide, between x = 2 and 38 on a base at y = 4:
#: 511 points. Every point of its top edge but the valleys at its two ends moves up or down by
#: up to ``ZIGZAG_JITTER`` (seeded), so the 254 acute tips all differ a little.
ZIGZAG_TEETH, ZIGZAG_X, ZIGZAG_BASE, ZIGZAG_TIP = 254, (2.0, 38.0), 4.0, 16.0
ZIGZAG_VALLEY = 15.189996                     # tips of 10 degrees: 2 atan(36 / 508 / 0.810004)
ZIGZAG_JITTER, ZIGZAG_SEED = 0.08100037064948984, 1


def zigzag_points():
    x0, x1 = ZIGZAG_X
    w = (x1 - x0) / ZIGZAG_TEETH
    pts = [[x0, ZIGZAG_BASE], [x1, ZIGZAG_BASE]]
    for i in range(ZIGZAG_TEETH, 0, -1):          # the top edge, from x1 back to x0
        pts += [[x0 + i * w, ZIGZAG_VALLEY], [x0 + (i - 0.5) * w, ZIGZAG_TIP]]
    pts.append([x0, ZIGZAG_VALLEY])
    rng = random.Random(ZIGZAG_SEED)
    for q in pts[3:-1]:
        q[1] += rng.uniform(-ZIGZAG_JITTER, ZIGZAG_JITTER)
    return [tuple(q) for q in pts]


def zigzag():
    """The sawtooth in a 40 x 20 box: mesh size 2, min_angle 33, at most 10,201 points."""
    pts = zigzag_points()
    d = Domain(size=2.0)
    d.add_region("background", rectangle(0, 0, 40, 20), holes=[pts])
    d.add_region("saw", pts)
    return d, {"boundary_names": box_sides(0, 40, 0, 20), "min_angle": 33.0, "max_points": 10201}


def film():
    """A film 30 long and 1e-7 thick across a 30 x 10 box, at most 10,201 points."""
    d = Domain(size=2.0)
    d.add_region("background", rectangle(0, 0, 30, 5))
    d.add_region("film", rectangle(0, 5, 30, 5 + 1e-7))
    d.add_region("background", rectangle(0, 5 + 1e-7, 30, 10))
    return d, {"boundary_names": box_sides(0, 30, 0, 10), "min_angle": 28.0, "max_points": 10201}


def named(pair, **kwargs):
    """(domain, generate keyword arguments) from a (domain, boundary namer) pair."""
    domain, namer = pair
    return domain, {"boundary_names": namer, **kwargs}


def fixture_cases():
    """{name: builder of (domain, generate keyword arguments)}: the inputs the other tests of
    this folder mesh, with the arguments they mesh them with. ``test_mesher`` builds its
    domains inside the tests, so they are repeated here."""
    def square():
        d = Domain(size=0.1)
        d.add_region("sq", rectangle(0, 0, 1, 1))
        return d, {"boundary_names": box_sides(0, 1, 0, 1), "min_angle": 30}

    def graded():
        d = Domain(size=0.5)
        d.add_region("sq", rectangle(-2, -2, 2, 2))
        return d, {"size_fn": shapes.size_graded(0.05, 0.5, 2.0)}

    def annulus():
        d = Domain(size=0.3)
        d.add_region("air", Circle((0, 0), 4.0, n=32), holes=[Circle((0, 0), 1.0, n=24)])
        return d, {"boundary_names": lambda mid: "pec" if np.hypot(*mid) < 2 else "abc"}

    def l_with_hole():
        d = Domain(size=0.1)
        d.add_region("L", [(0, 0), (2, 0), (2, 1), (1, 1), (1, 2), (0, 2)], holes=[rectangle(0.25, 0.25, 0.75, 0.75)])
        return d, {"boundary_names": box_sides(0, 2, 0, 2)}

    def irregular_l(h):
        d = Domain(size=h)
        d.add_region("L", [(0, 0), (2, 0), (2, 1), (1, 1), (1, 2), (0, 2)])
        return d, {"size_fn": lambda x, y: h * (1 + 0.5 * np.sin(3 * x) ** 2)}

    def same_name():
        d = Domain(size=0.3)
        d.add_region("core", rectangle(-1, 0, 1, 0.5), size=0.1)
        d.add_region("clad", [(-3, -2), (3, -2), (3, 0.5), (1, 0.5), (1, 0), (-1, 0), (-1, 0.5), (-3, 0.5)])
        d.add_region("clad", rectangle(-3, 0.5, 3, 2))
        return d, {"boundary_names": box_sides(-3, 3, -2, 2)}

    def fiber(h):
        return shapes.circular_fiber(4.0, 20.0, size_core=h, size_clad=4 * h, n_core=16), {}

    def t_junction(s):
        d = Domain(size=0.3 * s)
        d.add_region("a", rectangle(0, 0, 1 * s, 1 * s))
        d.add_region("b", rectangle(1 * s, 0, 2 * s, 0.5 * s))
        d.add_region("c", rectangle(1 * s, 0.5 * s, 2 * s, 1 * s))
        return d, {"boundary_names": box_sides(0, 2 * s, 0, 1 * s)}

    scale = load_test_module("test_meshine_scale")
    angles = load_test_module("test_small_angles")

    def small(builder, *args, **extra):
        def build():
            d, kwargs = getattr(angles, builder)(*args)
            return d, {"min_angle": angles.MIN_ANGLE, **kwargs, **extra}
        return build

    diagonal = angles.short_edge(1e-8)[0].extent()
    cases = {"unit square": square, "graded square": graded, "annulus": annulus,
             "L with a hole": l_with_hole, "same-name regions": same_name,
             "rib sizes": lambda: named(shapes.rib_waveguide(slab_thickness=0.3, size_core=0.1, size_far=0.8))}
    cases.update({f"rib {t}": lambda t=t: named(shapes.rib_waveguide(slab_thickness=t, size_core=0.15, size_far=0.8),
                                                 min_angle=28) for t in (0.0, 0.3, 0.7)})
    cases.update({f"fiber {h}": lambda h=h: fiber(h) for h in (1.0, 0.5, 0.25)})
    cases.update({f"irregular L {h}": lambda h=h: irregular_l(h) for h in (0.2, 0.1, 0.05)})
    cases.update({f"strip waveguide {label}": lambda s=s: named(scale.strip_waveguide(s), min_angle=28)
                  for label, s in scale.SCALES})
    cases.update({f"T-junction {label}": lambda s=s: t_junction(s) for label, s in scale.SCALES})
    cases.update({f"small angles: {name}": small(build.__name__, *args)
                  for name, (build, *args) in angles.MESHINE_HUNG.items()})
    cases.update({
        "small angles: fan with sizes": small("fan_with_sizes"),
        "small angles: two sharp corners 20 31": small("two_sharp_corners", 20, 31),
        "small angles: two sharp corners 14 20": small("two_sharp_corners", 14, 20),
        "small angles: touching 8-gons": small("touching_circles", 8),
        "small angles: off-edge vertex": small("off_edge_vertex"),
        "small angles: wedge 1 capped": small("wedge", 1.0, max_points=150),
        "small angles: short edge dropped": small("short_edge", 1e-8),
        "small angles: short edge not dropped": small("short_edge", 1e-8, 0.0),
        "small angles: short edge kept": small("short_edge", 2e-7 * diagonal),
        "small angles: notch 10": small("notch", 10),
        "small angles: notch 35": small("notch", 35),
        "small angles: sliver hole": small("sliver_hole"),
        **{f"small angles: corner after short edge {names}": small("corner_after_short_edge", 1e-8, names)
           for names in ("box", "outer")},
        **{f"small angles: short side edge {layout} {length:.3g}": small("short_side_edge", layout, length)
           for layout, length in angles.MESHED_SHORT_EDGES},
    })
    return cases


def corpus():
    """The fixture inputs and the inputs whose cost these changes bound."""
    cases = fixture_cases()
    cases.update({
        "strip 0.2 / 0.06": lambda: strip(0.2, 0.06),
        "1000-gon in a box": lambda: shape_in_box(regular_polygon(10.0, 15.5, 3.5, 1000)),
        "512-point gear": lambda: shape_in_box(gear(20.0, 10.0, 3.5, 3.40, 512)),
        "64 small rectangles": small_rectangles,
        "zigzag 10 degrees": zigzag,
        "film 1e-7": film,
    })
    return cases


CORPUS = corpus()

#: What ``generate`` gives on the inputs added here, so that the comparison cannot pass on two
#: errors where meshes are expected: a mesh (of any size), or the error with this text. The
#: sawtooth may give either.
EXPECTED = {"strip 0.2 / 0.06": "mesh", "1000-gon in a box": "mesh", "512-point gear": "mesh",
            "64 small rectangles": "mesh", "film 1e-7": "more than 10201 points"}


def outcome(build):
    """The mesh ``generate`` makes from ``build()``, or the error it raises."""
    domain, kwargs = build()
    try:
        return generate(domain, **kwargs)
    except (RuntimeError, ValueError) as exc:
        return exc


def assert_same(new, old):
    if isinstance(old, Exception):
        assert type(new) is type(old) and str(new) == str(old), f"{new!r} != {old!r}"
        return
    assert not isinstance(new, Exception), repr(new)
    for field in ("nodes", "triangles", "regions"):
        assert np.array_equal(getattr(new, field), getattr(old, field)), field
        assert getattr(new, field).dtype == getattr(old, field).dtype, field
    assert new.region_names == old.region_names
    for field in ("boundary_edges", "boundary_nodes", "interfaces"):
        a, b = getattr(new, field), getattr(old, field)
        assert list(a) == list(b), field
        assert all(np.array_equal(a[k], b[k]) for k in a), field


@pytest.mark.parametrize("name", list(CORPUS))
def test_the_old_implementations_give_the_same_mesh(monkeypatch, name):
    new = outcome(CORPUS[name])
    with monkeypatch.context() as patched:
        for helper, old in OLD.items():
            patched.setattr(refine, helper, old)
        old = outcome(CORPUS[name])
    assert_same(new, old)
    if EXPECTED.get(name) == "mesh":
        assert not isinstance(new, Exception), repr(new)
    elif name in EXPECTED:
        assert isinstance(new, RuntimeError) and EXPECTED[name] in str(new), repr(new)

