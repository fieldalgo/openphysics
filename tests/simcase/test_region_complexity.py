# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""region_complexity counts a raw region document's geometry before Document.from_dict.

Validating a region document resolves the shapes' booleans, and that cost grows with the
boundaries that cross, even under later shapes that hide them. region_complexity reads
the raw JSON: shapes, circles and polygon points from the lengths alone, then, only when
those are within the caller's maxima, the pairs of boundary segments from different
shapes that properly cross (their interiors meet in exactly one point), counted with one
STRtree query.

Pre-registered criteria (fixed before the implementation):
RC-1 the counts equal direct counts on the JSON; malformed input never raises.
RC-2 boundary_crossings equals a brute-force count with shapely ``crosses`` on every
     segment pair from different shapes, on >= 10 seeded random documents and on the
     covered-crossings attack.
RC-3 realistic layouts stay <= 256 crossings (a quarter of a cap of 1024).
RC-4 the covered-crossings attack gives > 1024 crossings in < 0.5 s; the worst case found
     within 64 shapes / 16 circles / 512 polygon points takes < 1 s.
RC-5 scaling every coordinate by 1e-6 and by 1e6 gives the same counts.
RC-6 with a maximum exceeded, boundary_crossings is None and shapely is not called.
Nothing is stored: every expected count is computed here.

Outcomes recorded after the run. RC-2 holds on its corpus but not in general: shapely's
``crosses`` rounds the intersection point it computes and can call a crossing a touch
where an end point lies within rounding of the other segment, while region_complexity
decides each pair with orientation predicates; a review found such documents. The count
is therefore also compared with exact rational arithmetic (``exact_crossings``, not a
pre-registered criterion) on near-degenerate documents. RC-4's times failed: by owner
decision (2026-10-27) its tests check a deterministic work bound that follows from the
caps instead, and only print the times; see the comment under RC-4. RC-5 failed as first
written; see the comment above ``SCALED``.

Added when porting onto the micrometre meshing of region documents, not pre-registered:
region_complexity counts the document's own numbers, and a run resolves the shapes again
on the micrometre copy it meshes; the last test compares the two counts on valid documents.
"""
import copy
import math
import time
from fractions import Fraction

import numpy as np
import pytest
import shapely
from shapely.geometry import LineString

from simcase import Document, RegionComplexity, examples, region_complexity
from simcase import complexity as rc_module
from simcase.geometry import shape_polygon
from simcase.runner import micrometre_document

import region_studio_fixtures as F

STUDIO_MAXIMA = {'max_shapes': 64, 'max_circles': 16, 'max_polygon_points': 512}


def direct_counts(data):
    shapes = data['geometry']['shapes']
    return (len(shapes), sum(1 for s in shapes if isinstance(s, dict) and s.get('type') == 'circle'),
            sum(len(s['points']) for s in shapes
                if isinstance(s, dict) and s.get('type') == 'polygon' and isinstance(s.get('points'), list)))


# ---- an independent count ---------------------------------------------------------------------

def ring_of(shape):
    """The boundary vertices of a valid shape, built without region_complexity: a rect's
    corners, the 128-gon simcase.geometry builds for a circle, a polygon's points."""
    if shape['type'] == 'rect':
        x, y, w, h = (shape[k] for k in ('x', 'y', 'w', 'h'))
        return [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]
    if shape['type'] == 'circle':
        return list(shape_polygon(shape).exterior.coords)[:-1]
    return [tuple(p) for p in shape['points']]


def brute_force_crossings(shapes):
    """Every pair of boundary segments from different shapes, tested with shapely crosses.
    It rounds near a touch (see the module docstring), so it is compared only on documents
    without contacts that rounding decides."""
    lines, owner = [], []
    for k, shape in enumerate(shapes):
        ring = ring_of(shape)
        for a, b in zip(ring, ring[1:] + ring[:1]):
            lines.append(LineString([a, b]))
            owner.append(k)
    lines, owner = np.array(lines, dtype=object), np.array(owner)
    i, j = np.triu_indices(len(lines), 1)
    i, j = i[owner[i] != owner[j]], j[owner[i] != owner[j]]
    total = 0
    for start in range(0, len(i), 500_000):
        total += int(np.count_nonzero(shapely.crosses(lines[i[start:start + 500_000]], lines[j[start:start + 500_000]])))
    return total


def boundary_segments(shapes):
    """(E, 2, 2) segments and (E,) owners of valid shapes, from ``ring_of``."""
    segments, owner = [], []
    for k, shape in enumerate(shapes):
        ring = ring_of(shape)
        segments += [(a, b) for a, b in zip(ring, ring[1:] + ring[:1])]
        owner += [k] * len(ring)
    return np.array(segments, dtype=float).reshape(-1, 2, 2), np.array(owner)


#: Shewchuk's bound on the error of the floating-point orientation determinant (orient2d,
#: stage A): where |det| exceeds it, the sign of the float determinant is the exact sign.
ORIENT_ERRBOUND = (3.0 + 16.0 * 2.0 ** -53) * 2.0 ** -53


def orientation(a, b, c):
    """The exact sign of the orientation of c about the line a -> b, row by row: the float
    determinant where it is clear of its error bound, exact rational arithmetic elsewhere
    (and wherever the products are small enough to have lost precision, or not finite)."""
    left = (b[:, 0] - a[:, 0]) * (c[:, 1] - a[:, 1])
    right = (b[:, 1] - a[:, 1]) * (c[:, 0] - a[:, 0])
    det, bound = left - right, np.abs(left) + np.abs(right)
    sign = np.sign(det).astype(np.int8)
    for k in np.flatnonzero(~((np.abs(det) > ORIENT_ERRBOUND * bound) & (bound > 2.0 ** -900))):
        ax, ay, bx, by, cx, cy = (Fraction(float(v)) for v in (*a[k], *b[k], *c[k]))
        exact = (bx - ax) * (cy - ay) - (by - ay) * (cx - ax)
        sign[k] = (exact > 0) - (exact < 0)
    return sign.astype(np.int16)


def exact_crossings(shapes, chunk=400_000):
    """Every pair of boundary segments from different shapes that properly cross, decided
    with exact orientations: each segment's end points lie strictly on opposite sides of
    the other's line. Independent of GEOS."""
    segments, owner = boundary_segments(shapes)
    i, j = np.triu_indices(len(segments), 1)
    i, j = i[owner[i] != owner[j]], j[owner[i] != owner[j]]
    total = 0
    for start in range(0, len(i), chunk):
        p, q = segments[i[start:start + chunk]], segments[j[start:start + chunk]]
        crossing = ((orientation(p[:, 0], p[:, 1], q[:, 0]) * orientation(p[:, 0], p[:, 1], q[:, 1]) < 0)
                    & (orientation(q[:, 0], q[:, 1], p[:, 0]) * orientation(q[:, 0], q[:, 1], p[:, 1]) < 0))
        total += int(np.count_nonzero(crossing))
    return total


def random_document(seed, contacts=True):
    """Rects, circles and random polygons (self-intersecting ones too) in the steady domain.
    With ``contacts``, shapes on integer coordinates add exact contacts that must not count:
    a shared edge, a collinear overlap, a corner touch, T-junctions, a polygon vertex on an
    edge, and two equal rects; the polygon also crosses a rect edge properly."""
    rng = np.random.default_rng(seed)
    shapes = [F.rect(f'r{k}', float(rng.uniform(0, 35)), float(rng.uniform(0, 17)),
                     float(rng.uniform(0.5, 12)), float(rng.uniform(0.5, 8))) for k in range(int(rng.integers(6, 12)))]
    shapes += [F.circle(f'c{k}', float(rng.uniform(2, 38)), float(rng.uniform(2, 18)), float(rng.uniform(0.5, 5)))
               for k in range(int(rng.integers(2, 5)))]
    for k in range(int(rng.integers(2, 4))):
        n = int(rng.integers(5, 40))
        cx, cy = rng.uniform(5, 35), rng.uniform(4, 16)
        angle, radius = np.sort(rng.uniform(0, 2 * math.pi, n)), rng.uniform(0.5, 6, n)
        if k == 0:
            rng.shuffle(angle)                                   # a self-intersecting polygon
        shapes.append(F.polygon(f'p{k}', zip(cx + radius * np.cos(angle), cy + radius * np.sin(angle))))
    if contacts:
        shapes += [F.rect('e0', 2, 2, 4, 3), F.rect('e1', 6, 2, 3, 3),          # shared edge x = 6
                   F.rect('t0', 3, 5, 2, 2),                                    # on e0's top edge
                   F.rect('k0', 9, 5, 2, 2),                                    # corner touch at (9, 5)
                   F.rect('t1', 2, 0, 1, 2),                                    # T-junctions on e0's bottom
                   F.polygon('v0', [(4, 1), (5, 2), (4, 3)]),                   # vertex on e0's bottom edge
                   F.rect('d0', 30, 15, 2, 2), F.rect('d1', 30, 15, 2, 2)]      # equal rects
    return F.with_shapes(shapes)


SEEDS = range(12)


# ---- RC-1 -----------------------------------------------------------------------------------

def counted_documents():
    return {'steady example': F.steady_example(), 'transient example': F.transient_example(),
            'combs k=63': F.crossing_combs(63), 'covered crossings': F.covered_crossings(),
            '16 circles, 47 rects and a 512-gon': F.circles_rects_polygon(), '8 x 8 grid': F.rect_grid(),
            **{f'random {seed}': random_document(seed) for seed in (0, 1)}}


@pytest.mark.parametrize('name', list(counted_documents()))
def test_rc1_counts_equal_direct_counts(name):
    data = counted_documents()[name]
    before = copy.deepcopy(data)
    got = region_complexity(data)
    assert isinstance(got, RegionComplexity) and isinstance(got, tuple)
    assert got[:3] == direct_counts(data)
    assert type(got.boundary_crossings) is int
    assert data == before                                         # the document is not changed
    assert rc_module._boundary_segments(data['geometry']['shapes'])[2] == {}    # all measured exactly


NAN, INF = float('nan'), float('inf')
MALFORMED_SHAPES = [
    None, 'rect', 3, [1, 2], {}, {'type': 'hexagon'}, {'type': None}, {'type': ['circle']},
    {'type': 'rect', 'x': 0, 'y': 0, 'w': 1},                                     # missing h
    {'type': 'rect', 'x': '0', 'y': 0, 'w': 1, 'h': 1},
    {'type': 'rect', 'x': NAN, 'y': 0, 'w': 1, 'h': 1},
    {'type': 'rect', 'x': 0, 'y': INF, 'w': 1, 'h': 1},
    {'type': 'rect', 'x': True, 'y': 0, 'w': 1, 'h': 1},
    {'type': 'rect', 'x': 10 ** 400, 'y': 0, 'w': 1, 'h': 1},
    {'type': 'rect', 'x': 1e308, 'y': 0, 'w': 1e308, 'h': 1},                    # x + w overflows
    {'type': 'rect', 'x': 1, 'y': 1, 'w': 0, 'h': 0},                            # degenerate
    {'type': 'circle', 'cx': 1, 'cy': 1},
    {'type': 'circle', 'cx': 1, 'cy': 1, 'r': -1}, {'type': 'circle', 'cx': 1, 'cy': 1, 'r': 0},
    {'type': 'circle', 'cx': 1, 'cy': 1, 'r': 'big'}, {'type': 'circle', 'cx': NAN, 'cy': 1, 'r': 1},
    {'type': 'circle', 'cx': 1e308, 'cy': 1, 'r': 1e308},                    # cx + r overflows
    {'type': 'polygon'}, {'type': 'polygon', 'points': None}, {'type': 'polygon', 'points': 'abc'},
    {'type': 'polygon', 'points': {'0': [0, 0]}}, {'type': 'polygon', 'points': []},
    {'type': 'polygon', 'points': [[0, 0], [1, 1]]},
    {'type': 'polygon', 'points': [[0, 0], [1, NAN], [1, 1]]},
    {'type': 'polygon', 'points': [[0, 0], [1, INF], [1, 1]]},
    {'type': 'polygon', 'points': [[0, 0], ['1', 0], [1, 1]]},
    {'type': 'polygon', 'points': [[0, 0], [1], [1, 1]]},
    {'type': 'polygon', 'points': [[0, 0], [1, 0, 0], [1, 1]]},
    {'type': 'polygon', 'points': [[0, 0], None, [1, 1]]},
    {'type': 'polygon', 'points': [[0, 0], [[1], [0]], [1, 1]]},
    {'type': 'polygon', 'points': [[0, 0], [10 ** 400, 0], [1, 1]]},
]
#: Well-formed shapes with coordinates GEOS cannot decide exactly: counted as crossing every
#: segment of every other shape. (shape, its segment count)
OUT_OF_RANGE = [
    ({'type': 'rect', 'x': -1e200, 'y': -1e200, 'w': 2e200, 'h': 2e200}, 4),
    ({'type': 'rect', 'x': 1, 'y': 1, 'w': 1e-200, 'h': 1}, 4),               # x + w rounds to x: in range
    ({'type': 'rect', 'x': 1e-200, 'y': 1, 'w': 1, 'h': 1}, 4),
    ({'type': 'circle', 'cx': 0, 'cy': 0, 'r': 1e200}, 128),
    ({'type': 'circle', 'cx': 1e308, 'cy': 1, 'r': 1e307}, 128),
    ({'type': 'circle', 'cx': 1, 'cy': 1, 'r': 5e-324}, 128),
    ({'type': 'polygon', 'points': [[0, 0], [2.0 ** 600, 0], [1, 1]]}, 3),
    ({'type': 'polygon', 'points': [[0, 0], [1e-300, 1], [1, 1]]}, 3),
]
MALFORMED_DOCUMENTS = [None, [], 'doc', 3, {}, {'geometry': None}, {'geometry': []}, {'geometry': {}},
                       {'geometry': {'shapes': None}}, {'geometry': {'shapes': {}}}, {'geometry': {'shapes': 'x'}},
                       {'geometry': {'shapes': ()}}]


@pytest.mark.parametrize('data', MALFORMED_DOCUMENTS, ids=repr)
def test_rc1_a_document_without_a_shape_list_counts_zero(data):
    assert region_complexity(data) == (0, 0, 0, 0)
    assert region_complexity(data, **STUDIO_MAXIMA) == (0, 0, 0, 0)


def test_rc1_shapes_beyond_the_exact_range_count_every_pair_they_could_cross():
    """Not measured, never an exception: a shape outside EXACT_RANGE adds its segments times
    the segments of every other shape, so an extreme scale cannot hide crossings. The second
    rect is in range (its x + w rounds to x) and is measured as a degenerate rect."""
    valid = random_document(4, contacts=False)
    base = region_complexity(valid).boundary_crossings
    segments = len(rc_module._boundary_segments(valid['geometry']['shapes'])[0])
    for entry, count in OUT_OF_RANGE:
        data = copy.deepcopy(valid)
        data['geometry']['shapes'].append(copy.deepcopy(entry))
        got = region_complexity(data)
        assert got[:3] == direct_counts(data)
        if entry.get('w') == 1e-200:                     # in range: measured, as the brute force does
            assert got.boundary_crossings == brute_force_crossings(data['geometry']['shapes'])
        else:
            assert got.boundary_crossings == base + count * segments, entry
        assert region_complexity({'geometry': {'shapes': [copy.deepcopy(entry)]}}).boundary_crossings == 0
    both = copy.deepcopy(valid)
    both['geometry']['shapes'] += [copy.deepcopy(OUT_OF_RANGE[0][0]), copy.deepcopy(OUT_OF_RANGE[3][0])]
    assert region_complexity(both).boundary_crossings == base + 4 * segments + 128 * segments + 4 * 128


def test_rc1_malformed_entries_are_counted_but_give_no_segment():
    """Each malformed entry alone, and all of them mixed into a valid document: no exception,
    the counts are the direct ones, and the crossings are those of the valid shapes alone."""
    for entry in MALFORMED_SHAPES:
        data = {'geometry': {'shapes': [entry]}}
        assert region_complexity(data) == (*direct_counts(data), 0), entry
    valid = random_document(3)
    mixed = copy.deepcopy(valid)
    for k, entry in enumerate(MALFORMED_SHAPES):
        mixed['geometry']['shapes'].insert(2 * k % len(mixed['geometry']['shapes']), copy.deepcopy(entry))
    got = region_complexity(mixed)
    assert got[:3] == direct_counts(mixed)
    assert got.boundary_crossings == region_complexity(valid).boundary_crossings > 0


# ---- RC-2 -----------------------------------------------------------------------------------

@pytest.mark.parametrize('seed', SEEDS)
def test_rc2_crossings_equal_a_brute_force_on_random_documents(seed):
    shapes = random_document(seed)['geometry']['shapes']
    got = region_complexity({'geometry': {'shapes': shapes}}).boundary_crossings
    assert got == brute_force_crossings(shapes)
    assert got > 0


def test_rc2_crossings_equal_a_brute_force_on_the_attack():
    data = F.covered_crossings()
    assert region_complexity(data).boundary_crossings == brute_force_crossings(data['geometry']['shapes'])


def test_rc2_exact_contacts_do_not_count():
    """The contact shapes of the random documents alone: only the polygon's closing edge
    x = 4 crosses e0's bottom edge properly; every other meeting is a shared or collinear
    edge, a touch at an end point or a T-junction."""
    shapes = random_document(0)['geometry']['shapes']
    contacts = [s for s in shapes if s['name'] in {'e0', 'e1', 't0', 'k0', 't1', 'v0', 'd0', 'd1'}]
    assert region_complexity({'geometry': {'shapes': contacts}}).boundary_crossings == 1
    assert brute_force_crossings(contacts) == 1


def test_rc2_segments_are_the_rings_simcase_meshes():
    """A circle's segments are the 128-gon shape_polygon builds, to the bit; a rect's and a
    polygon's are their edges, the closing edge included."""
    shapes = [F.circle('c', 20.3, 10.1, 2.7), F.rect('r', 1.5, 2.5, 3.0, 4.0), F.polygon('p', [(0, 0), (3, 1), (1, 4)])]
    segments, owner, unmeasured = rc_module._boundary_segments(shapes)
    assert unmeasured == {}
    for k, shape in enumerate(shapes):
        ring = np.array(ring_of(shape), dtype=float)
        expected = np.stack([ring, np.roll(ring, -1, axis=0)], axis=1)
        assert np.array_equal(segments[owner == k], expected), shape['name']
    assert np.count_nonzero(owner == 0) == 128


# ---- exact arithmetic (not pre-registered) ----------------------------------------------------

def grid_document(seed):
    """Shapes on a half-unit grid: shared and collinear edges, vertices on edges, a repeated
    point (a zero-length segment) and circles whose 128-gon vertices land near grid lines."""
    rng = np.random.default_rng(seed)

    def g():
        return float(rng.integers(0, 9)) * 0.5
    shapes = [F.rect(f'r{k}', g(), g(), float(rng.integers(1, 6)) * 0.5, float(rng.integers(1, 6)) * 0.5)
              for k in range(int(rng.integers(3, 8)))]
    for k in range(int(rng.integers(2, 5))):
        points = [(g(), g()) for _ in range(int(rng.integers(3, 12)))]
        if k == 0:
            points.insert(1, points[0])
        shapes.append(F.polygon(f'p{k}', points))
    shapes += [F.circle(f'c{k}', 1 + g(), 1 + g(), float(rng.integers(1, 5)) * 0.5)
               for k in range(int(rng.integers(1, 3)))]
    return {'geometry': {'shapes': shapes}}


def sliver_document(seed):
    """Thin triangles nearly collinear with each other, offset by about one rounding error."""
    rng = np.random.default_rng(seed)
    shapes = []
    for k in range(10):
        base, angle, length = rng.uniform(0, 10, 2), rng.uniform(0, math.pi), rng.uniform(1, 10)
        d = np.array([math.cos(angle), math.sin(angle)])
        n, eps = np.array([-d[1], d[0]]), 10.0 ** rng.uniform(-15, -9)
        shapes.append(F.polygon(f'a{k}', [base, base + length * d, base + 0.5 * length * d + eps * n]))
        shapes.append(F.polygon(f'b{k}', [base + 0.3 * length * d + 1e-16 * n, base + 1.3 * length * d - 1e-16 * n,
                                          base + 0.8 * length * d - eps * n]))
    return {'geometry': {'shapes': shapes}}


def ulp_document():
    """Triangles with one vertex one ulp above, on and one ulp below a box's top edge, and
    two one ulp above and below a diagonal edge: only the two below cross, twice each."""
    up, down = float(np.nextafter(10.0, 20.0)), float(np.nextafter(10.0, 0.0))
    shapes = [F.rect('box', 0.0, 0.0, 10.0, 10.0), F.polygon('diagonal', [(0.5, 0.5), (9.5, 9.5), (9.5, 0.5)])]
    shapes += [F.polygon(name, [(x, y), (x + 0.5, 12.0), (x - 0.5, 12.0)])
               for name, x, y in (('above', 2.0, up), ('on', 5.0, 10.0), ('below', 8.0, down))]
    shapes += [F.polygon(name, [(x, y), (x - 1.0, y + 0.5), (x - 0.5, y + 1.0)])
               for name, x, y in (('diagonal above', 3.0, float(np.nextafter(3.0, 9.0))),
                                  ('diagonal below', 6.0, float(np.nextafter(6.0, 0.0))))]
    return {'geometry': {'shapes': shapes}}


def two_triangles():
    """A vertex of the second triangle lies 2**-52 below the first one's edge on y = x + 1,
    so two edges cross that edge by less than a rounding error; shapely's crosses (relate)
    reports one of the two as a touch."""
    return {'geometry': {'shapes': [
        F.polygon('a', [(1, 2), (3, 4), (3, 2)]),
        F.polygon('b', [(1.6464466094067263, 2.646446609406726), (1.6295244373225206, 2.664220522576491), (0, 4)])]}}


def moved(data, factor, offset=0.0):
    """The shapes with every coordinate multiplied by ``factor`` and shifted by ``offset``."""
    data = copy.deepcopy(data)
    for shape in data['geometry']['shapes']:
        for key in ('x', 'y', 'cx', 'cy'):
            if key in shape:
                shape[key] = shape[key] * factor + offset
        for key in ('w', 'h', 'r'):
            if key in shape:
                shape[key] *= factor
        if 'points' in shape:
            shape['points'] = [[x * factor + offset, y * factor + offset] for x, y in shape['points']]
    return data


NEAR_DEGENERATE = {
    'two triangles': two_triangles, 'ulp offsets': ulp_document,
    **{f'grid {seed}': (lambda seed=seed: grid_document(seed)) for seed in range(10)},
    **{f'slivers {seed}': (lambda seed=seed: sliver_document(seed)) for seed in range(3)},
    **{f'grid {seed} x {factor:.3g}': (lambda seed=seed, factor=factor: moved(grid_document(seed), factor))
       for seed in (0, 1) for factor in (1e-80, 1e80, 2.0 ** -290, 2.0 ** 290, 3.0 ** 100)},
    **{f'grid {seed} + 1e6': (lambda seed=seed: moved(grid_document(seed), 1.0, 1e6)) for seed in (0, 1)},
    **{f'grid {seed} x 1e-9 + 1': (lambda seed=seed: moved(grid_document(seed), 1e-9, 1.0)) for seed in (0, 1)},
}


@pytest.mark.parametrize('name', list(NEAR_DEGENERATE))
def test_crossings_equal_exact_arithmetic_on_near_degenerate_documents(name):
    """Contacts, near misses and crossings by less than a rounding error, at scales from
    1e-80 to 1e80: the count is the exact one, wherever shapely's crosses rounds."""
    data = NEAR_DEGENERATE[name]()
    assert rc_module._boundary_segments(data['geometry']['shapes'])[2] == {}      # all measured
    assert region_complexity(data).boundary_crossings == exact_crossings(data['geometry']['shapes'])


def test_the_exact_reference_is_not_vacuous():
    assert exact_crossings(two_triangles()['geometry']['shapes']) == 2
    assert exact_crossings(ulp_document()['geometry']['shapes']) == 4


@pytest.mark.parametrize('name', [*(f'random {seed}' for seed in SEEDS), 'covered crossings'])
def test_crossings_equal_exact_arithmetic_on_the_rc2_corpus(name):
    data = F.covered_crossings() if name == 'covered crossings' else random_document(int(name.split()[1]))
    assert region_complexity(data).boundary_crossings == exact_crossings(data['geometry']['shapes'])


# ---- RC-3 -----------------------------------------------------------------------------------

REALISTIC = {
    'steady example': F.steady_example,
    'transient example': F.transient_example,
    '8 x 8 grid of touching rects': F.rect_grid,
    '64 stacked layer strips': F.layer_strips,
    'steady example with 8 heaters straddling the plate edge': F.straddling_heaters,
    'the same heaters 0.3 mm higher': lambda: F.straddling_heaters(cy=11.3),
}


@pytest.mark.parametrize('name', list(REALISTIC))
def test_rc3_realistic_layouts_stay_within_a_quarter_of_the_cap(name):
    data = REALISTIC[name]()
    got = region_complexity(data, **STUDIO_MAXIMA)
    print(name, got)
    assert got.boundary_crossings is not None and got.boundary_crossings <= 256
    Document.from_dict(data)                                      # and they are valid documents


def test_rc3_heaters_across_the_plate_edge_cross_it_twice_each():
    """Not vacuous: 0.3 mm above the edge, each 128-gon crosses the plate's top edge in two
    points, and the heaters touch nothing else. Centred on the edge (the default), their
    128-gons meet it only at vertices, which count 0."""
    assert region_complexity(F.straddling_heaters(cy=11.3)).boundary_crossings == 16


# ---- RC-4 -----------------------------------------------------------------------------------
#
# RC-4 was fixed as wall-clock times (< 0.5 s for the attack, < 1 s for the costliest layout
# found within the caps) and FAILED: in one of 26 runs of this file one call on the chord
# stars took 1.015 s, and the diagonal and corner fans found later take over 1 s in some
# calls on the same machine (see the docs). By owner decision (2026-10-27) the time criterion
# stays recorded as failed, and these tests check a deterministic work bound that follows
# from the Studio caps instead; the times are still measured and printed (pytest -s), and no
# test fails on them.

#: Fixed on 2026-10-27 from the caps: the most boundary segments a document within 64 shapes,
#: 16 circles and 512 polygon points can give. A circle is a 128-gon, a rect 4 edges and a
#: polygon as many edges as its points; a polygon takes a shape a rect would fill with 4 edges,
#: so 16 circles, one polygon with all 512 points and 47 rects give the most (2748; reached by
#: F.circles_rects_polygon).
MAX_SEGMENTS = 16 * 128 + 4 * (64 - 16) + (512 - 4)
#: Every unordered pair of those segments (3,774,378): the most pairs a call can test once each.
#: These two numbers are what testing every pair would give, so they hold for any document
#: within the caps but a brute force would meet them too; what rules a brute force out is the
#: check in check_work_bound that only pairs whose boxes meet are tested.
MAX_PAIRS = MAX_SEGMENTS * (MAX_SEGMENTS - 1) // 2
#: The items the other shapely calls make or take (10,356): per segment its two end points and
#: its prepared line, per circle its centre, its disc, its ring and the ring's 129 coordinates.
MAX_LINEAR_ITEMS = 3 * MAX_SEGMENTS + 16 * (3 + 129)


class WorkCounter:
    """Stands in for shapely inside simcase.complexity and counts the work it is given: the
    segments built (``linestrings``), the pairs the STRtree query returns (ordered, each
    segment with itself included), the sizes of the pairwise ``intersects`` calls (the first
    on the pairs from different shapes whose boxes meet, the next four on the end points of
    the pairs that meet) and the items the calls in ``LINEAR`` make or take. Any other shapely
    name fails the test, so work this counter does not see cannot pass unnoticed."""

    #: The other calls region_complexity makes, each on one item per segment or per circle.
    LINEAR = frozenset({'points', 'buffer', 'get_exterior_ring', 'get_coordinates', 'prepare'})

    def __init__(self):
        self.segments, self.queries, self.tree_pairs, self.predicate_calls = 0, 0, 0, []
        self.linear_items = 0

    def __getattr__(self, name):
        if name not in self.LINEAR:
            raise AssertionError(f'shapely.{name} is not counted by the work bound')
        call = getattr(shapely, name)

        def counted(geometry, *args, **kwargs):
            result = call(geometry, *args, **kwargs)
            self.linear_items += (len(result) if name == 'get_coordinates' else
                                  int(np.size(geometry if name == 'prepare' else result)))
            return result
        return counted

    def linestrings(self, coords, **kwargs):
        self.segments += len(coords)
        return shapely.linestrings(coords, **kwargs)

    def STRtree(self, geoms, **kwargs):
        tree, counter = shapely.STRtree(geoms, **kwargs), self

        class CountedTree:
            def query(self, geometry):        # a predicate or distance would be uncounted work
                pairs = tree.query(geometry)
                counter.queries += 1
                counter.tree_pairs += pairs.shape[-1]
                return pairs
        return CountedTree()

    def intersects(self, a, b, **kwargs):
        result = shapely.intersects(a, b, **kwargs)
        self.predicate_calls.append(int(np.size(result)))
        return result

    def summary(self):
        tested, meeting = self.predicate_calls[0], self.predicate_calls[1]
        return {'segments': self.segments, 'tree pairs': self.tree_pairs, 'tested pairs': tested,
                'meeting pairs': meeting, 'predicates': sum(self.predicate_calls),
                'linear items': self.linear_items}


def box_pairs(shapes):
    """(ordered pairs of boundary segments whose bounding boxes meet, each segment with itself
    included; unordered such pairs from different shapes), counted here without shapely."""
    segments, owner = boundary_segments(shapes)
    low, high = segments.min(axis=1), segments.max(axis=1)
    meet = ((low[:, None, 0] <= high[None, :, 0]) & (low[None, :, 0] <= high[:, None, 0])
            & (low[:, None, 1] <= high[None, :, 1]) & (low[None, :, 1] <= high[:, None, 1]))
    return int(np.count_nonzero(meet)), int(np.count_nonzero(meet & (owner[:, None] != owner[None, :]))) // 2


def check_work_bound(data):
    """Count one call's work with the Studio maxima and check the bound, then time three calls
    without the counter; returns (result, work, seconds)."""
    counter = WorkCounter()
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(rc_module, 'shapely', counter)
        result = region_complexity(data, **STUDIO_MAXIMA)
    assert result.boundary_crossings is not None                 # within the caps: counted
    assert counter.queries == 1 and len(counter.predicate_calls) == 5     # the counter saw the work
    work = counter.summary()
    assert work['segments'] <= MAX_SEGMENTS
    assert work['tree pairs'] <= MAX_SEGMENTS ** 2
    assert work['tested pairs'] <= MAX_PAIRS
    assert work['predicates'] <= 5 * MAX_PAIRS        # a tested pair: 1, a meeting pair: 4 more
    assert work['linear items'] <= MAX_LINEAR_ITEMS
    # Not vacuous: the segments are the shapes' boundaries, the other calls make or take
    # exactly the items above, and only the pairs whose boxes meet are tested, so a test of
    # every pair would fail here.
    shapes = data['geometry']['shapes']
    ordered, different = box_pairs(shapes)
    assert work['segments'] == len(boundary_segments(shapes)[0])
    assert work['linear items'] == 3 * work['segments'] + (3 + 129) * direct_counts(data)[1]
    assert work['tree pairs'] <= ordered and work['tested pairs'] <= different
    assert result.boundary_crossings <= work['meeting pairs'] <= work['tested pairs']
    seconds = []
    for _ in range(3):
        start = time.perf_counter()
        assert region_complexity(data, **STUDIO_MAXIMA) == result
        seconds.append(round(time.perf_counter() - start, 3))
    return result, work, seconds


def test_rc4_the_segment_bound_is_the_most_the_caps_allow():
    """16 circles, 47 rects and a 512-gon reach MAX_SEGMENTS exactly."""
    data = F.circles_rects_polygon()
    assert direct_counts(data) == (64, 16, 512)
    _result, work, seconds = check_work_bound(data)
    print('16 circles, 47 rects and a 512-gon', work, seconds)
    assert work['segments'] == MAX_SEGMENTS == 2748


def test_rc4_the_covered_crossings_attack_stays_within_the_work_bound():
    data = F.covered_crossings()
    assert direct_counts(data) == (64, 0, 510)
    result, work, seconds = check_work_bound(data)
    print('covered crossings', result, work, seconds)
    assert result.boundary_crossings > 1024


#: The costliest layouts found within the caps: the chord stars (most crossings), the
#: diagonal fans (about twice the chord stars' segment pairs whose boxes meet) and the corner
#: fans, found by a review (a few more such pairs and, with 8 polygons, the most pairs that meet).
COSTLIEST = {**{f'chord stars {p} {r}': (lambda p=p, r=r: F.chord_stars(p, r))
                for p, r in [(16, 'thin'), (8, 'nested'), (4, 'plus'), (2, 'nested')]},
             **{f'diagonal fans {p} {r}': (lambda p=p, r=r: F.diagonal_fans(p, r))
                for p, r in [(1, 'squares'), (8, 'squares')]},
             **{f'corner fans {p} {r}': (lambda p=p, r=r: F.corner_fans(p, r))
                for p, r in [(1, 'corner'), (8, 'corner')]}}


@pytest.mark.parametrize('name', list(COSTLIEST))
def test_rc4_the_costliest_layouts_found_stay_within_the_work_bound(name):
    """Polygons whose edges cross nearly every other polygon edge (chord stars) or whose edge
    boxes hold every circle (diagonal fans; corner fans, whose edges also all meet at one
    corner), with 16 circles and rects filling 64 shapes."""
    data = COSTLIEST[name]()
    assert direct_counts(data) == (64, 16, 512)
    result, work, seconds = check_work_bound(data)
    print(name, result.boundary_crossings, work, seconds)
    if name.startswith('chord stars'):
        assert result.boundary_crossings > 100_000
    elif name.startswith('diagonal fans'):
        assert work['tree pairs'] > 2_000_000 and result.boundary_crossings > 60_000
    else:
        assert work['tree pairs'] > 2_000_000 and work['meeting pairs'] > 90_000


def random_document_within_the_caps(seed):
    """Rects and circles of any size and polygons with vertices anywhere in the domain, so
    long edges that cross many others, in random order: an even seed fills every cap (64
    shapes, 16 circles, 512 polygon points), an odd one stays at random within them."""
    rng = np.random.default_rng(1000 + seed)
    if seed % 2 == 0:
        circles, polygons = 16, int(rng.integers(1, 9))
        rects, points = 64 - 16 - polygons, 512
    else:
        circles, polygons = int(rng.integers(0, 17)), int(rng.integers(0, 9))
        rects = int(rng.integers(0, 64 - circles - polygons + 1))
        points = int(rng.integers(3 * polygons, 513)) if polygons else 0
    sizes = 3 + rng.multinomial(points - 3 * polygons, np.ones(polygons) / polygons) if polygons else []
    shapes = [F.rect(f'r{k}', float(rng.uniform(0, 38)), float(rng.uniform(0, 18)),
                     float(rng.uniform(0.01, 30)), float(rng.uniform(0.01, 15))) for k in range(rects)]
    shapes += [F.circle(f'c{k}', float(rng.uniform(0, 40)), float(rng.uniform(0, 20)), float(rng.uniform(0.05, 12)))
               for k in range(circles)]
    shapes += [F.polygon(f'p{k}', rng.uniform((0, 0), (40, 20), (int(n), 2))) for k, n in enumerate(sizes)]
    order = rng.permutation(len(shapes))
    return F.with_shapes([shapes[k] for k in order])


@pytest.mark.parametrize('seed', range(12))
def test_rc4_random_documents_within_the_caps_stay_within_the_work_bound(seed):
    data = random_document_within_the_caps(seed)
    shapes, circles, points = direct_counts(data)
    assert shapes <= 64 and circles <= 16 and points <= 512
    assert seed % 2 or (shapes, circles, points) == (64, 16, 512)
    result, work, seconds = check_work_bound(data)
    print('random', seed, result, work, seconds)


# ---- RC-5 -----------------------------------------------------------------------------------

def scaled(data, factor):
    """The document with every length multiplied by ``factor``."""
    data = copy.deepcopy(data)
    geometry = data['geometry']
    geometry['domain'] = {key: value * factor for key, value in geometry['domain'].items()}
    for shape in geometry['shapes']:
        for key in ('x', 'y', 'w', 'h', 'cx', 'cy', 'r'):
            if key in shape:
                shape[key] *= factor
        if 'points' in shape:
            shape['points'] = [[x * factor, y * factor] for x, y in shape['points']]
    return data


def shifted_chord_stars(polygons, rects):
    """The chord stars with every circle moved off the rects' sides (radius 0.0123 smaller,
    centre 0.0017 to the right), so no contact is left for rounding to decide."""
    data = F.chord_stars(polygons, rects)
    for shape in data['geometry']['shapes']:
        if shape['type'] == 'circle':
            shape['r'] -= 0.0123456789
            shape['cx'] += 0.0123456789 * math.sqrt(2) / 10
    return data


CHORD_STARS = [(16, 'thin'), (8, 'nested'), (4, 'plus'), (2, 'nested')]

#: Layouts whose contacts survive scaling. Excluded: layouts with contacts that rounding can
#: turn into a proper crossing, a vertex of one shape on an edge of another made by
#: arithmetic, such as the touching grid, whose corners lie on the neighbouring rects' edges
#: only because one rect's x + w equals the next one's x: scaled by a decimal factor, the
#: two sides of such an equality round separately, and the count depends on the rounding.
#: Contacts between collinear axis-aligned edges with shared ends, as in the layer strips,
#: cannot become a proper crossing and stay in.
#: The first run of this test also scaled the chord stars (8 polygons, nested rects) and
#: failed: 158,868 crossings became 158,874 at 1e-6 and 158,860 at 1e6, and every chord
#: star layout changes at 1e-6 (2 polygons: 121,634 became 121,640, and 121,624 at 1e6). They
#: have such contacts: in exact arithmetic, vertices of their circles' 128-gons lie on the
#: sides of their rects (in every layout the first circle's lowest vertex on the first
#: rect's bottom side; in the nested ones also circle q's lowest and highest vertices on the
#: sides of rect 6q, and its leftmost on rect 3.5q's). In floating point each such contact
#: is a touch, a crossing by about a rounding error or a near miss, and a decimal factor
#: rounds it again: at 1e-6 four touches and one near miss became crossings and two
#: crossings became misses (each contact is two segment pairs, the two segments at the
#: circle's vertex). region_complexity counts what exact arithmetic counts at every
#: scale (below), and scaled exactly (by powers of two) every layout keeps its counts; the
#: failure is recorded here and the chord stars stay out of this list. Added after the
#: failure, not pre-registered: the four layouts with their circles moved off those sides.
SCALED = {**{f'random {seed}': (lambda seed=seed: random_document(seed, contacts=False)) for seed in SEEDS},
          'covered crossings': F.covered_crossings, 'steady example': F.steady_example,
          'transient example': F.transient_example, '64 stacked layer strips': F.layer_strips,
          'heaters across the plate edge': lambda: F.straddling_heaters(cy=11.3),
          **{f'chord stars {p} {r}, circles moved': (lambda p=p, r=r: shifted_chord_stars(p, r))
             for p, r in CHORD_STARS}}


@pytest.mark.parametrize('name', list(SCALED))
def test_rc5_scaling_every_coordinate_keeps_the_counts(name):
    data = SCALED[name]()
    got = region_complexity(data)
    assert got.boundary_crossings > 0 or name in ('steady example', 'transient example', '64 stacked layer strips')
    for factor in (1e-6, 1e6):
        assert region_complexity(scaled(data, factor)) == got, factor


EXACTLY_SCALED = {**SCALED, '8 x 8 grid of touching rects': F.rect_grid,
                  'chord stars': lambda: F.chord_stars(8, 'nested'),
                  **{f'random {seed} with contacts': (lambda seed=seed: random_document(seed)) for seed in (0, 1)}}


@pytest.mark.parametrize('name', list(EXACTLY_SCALED))
def test_rc5_scaling_by_a_power_of_two_keeps_every_count(name):
    """Not a pre-registered criterion: multiplied by 2**-20 and 2**20 every coordinate scales
    without rounding, so even exact contacts survive, and the counts must not change at all."""
    data = EXACTLY_SCALED[name]()
    got = region_complexity(data)
    for factor in (2.0 ** -20, 2.0 ** 20):
        assert region_complexity(scaled(data, factor)) == got, factor


@pytest.mark.parametrize('polygons,rects', CHORD_STARS)
def test_rc5_the_chord_stars_scaled_by_decimal_factors_count_as_exact_arithmetic_does(polygons, rects):
    """The recorded RC-5 failure is in the input, not the count: at 1e-6 and 1e6 the chord
    stars' counts change, and the exact count changes with them."""
    data = F.chord_stars(polygons, rects)
    counts = []
    for factor in (1.0, 1e-6, 1e6):
        s = scaled(data, factor)
        counts.append(region_complexity(s).boundary_crossings)
        assert counts[-1] == exact_crossings(s['geometry']['shapes']), factor
    print('chord stars', polygons, rects, 'at 1, 1e-6, 1e6:', counts)


def test_rc5_the_moved_chord_stars_are_still_costly():
    for polygons, rects in CHORD_STARS:
        assert region_complexity(shifted_chord_stars(polygons, rects)).boundary_crossings > 100_000


# ---- RC-6 -----------------------------------------------------------------------------------

class NoShapely:
    def __getattr__(self, name):
        raise AssertionError(f'shapely.{name} was called although a maximum was exceeded')


@pytest.mark.parametrize('maximum', ['max_shapes', 'max_circles', 'max_polygon_points'])
def test_rc6_over_a_maximum_nothing_is_built(monkeypatch, maximum):
    data = F.circles_rects_polygon()
    counts = dict(zip(('max_shapes', 'max_circles', 'max_polygon_points'), direct_counts(data)))
    exact = region_complexity(data, **{maximum: counts[maximum]})
    assert exact.boundary_crossings is not None                 # at the maximum it is counted
    monkeypatch.setattr(rc_module, 'shapely', NoShapely())
    over = region_complexity(data, **{maximum: counts[maximum] - 1})
    assert over == (*direct_counts(data), None)
    assert region_complexity(F.covered_crossings(127, 58), **STUDIO_MAXIMA) == (64, 0, 514, None)


@pytest.mark.parametrize('value', [0, -1, True, 2.0, '64'])
def test_rc6_a_maximum_must_be_a_positive_int(value):
    for maximum in ('max_shapes', 'max_circles', 'max_polygon_points'):
        with pytest.raises(ValueError, match=f'{maximum}: expected a positive int'):
            region_complexity(F.steady_example(), **{maximum: value})


def test_the_names_are_exported():
    import simcase
    assert {'region_complexity', 'RegionComplexity'} <= set(simcase.__all__)
    assert examples.EXAMPLES['thermal_regions']['geometry']['shapes']          # the examples are dicts


# ---- port: the micrometre copy a run meshes --------------------------------------------------

#: Valid millimetre documents whose micrometre copies (runner.micrometre_document, as a run
#: makes them) are counted too.
MESHED_COPIES = {
    **{f'steady example, size {s}': (lambda s=s: F.steady_example(s)) for s in (2.0, 1.0, 0.5)},
    **{f'transient example, size {s}': (lambda s=s: F.transient_example(s)) for s in (2.0, 1.0, 0.5)},
    **{name: getattr(F, name) for name in (
        'spaced_rects', 'isolated_circles', 'clipped_circle', 'overlapped_circle', 'split_background', 'strip',
        'thin_film', 'circles_rects_polygon', 'tiny_global_size', 'straddling_heaters', 'rect_grid',
        'layer_strips')},
    'the same heaters 0.3 mm higher': lambda: F.straddling_heaters(cy=11.3),
    'crossing combs k=14': lambda: F.crossing_combs(14),
    'crossing combs k=63': lambda: F.crossing_combs(63),
    'covered crossings, 6 teeth, 4 front rects': lambda: F.covered_crossings(6, 4),
}


@pytest.mark.parametrize('name', list(MESHED_COPIES))
def test_port_the_micrometre_copy_a_run_meshes_counts_the_same(name):
    """Port, not pre-registered. Document.from_dict resolves the document's own numbers,
    which region_complexity counts; a run resolves the shapes again on its micrometre copy.
    A decimal unit factor can re-round exact contacts (RC-5), but on these documents the
    copy counts the same."""
    data = MESHED_COPIES[name]()
    meshed = micrometre_document(Document.from_dict(copy.deepcopy(data))).data
    assert (data['units']['length'], meshed['units']['length']) == ('mm', 'um')
    assert meshed['geometry'] != data['geometry']
    assert region_complexity(meshed) == region_complexity(data)
