# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""The exact-circle check gives the answer it gave when it measured point by point.

geometry._isolated_circle decides whether a circle is meshed as an exact
meshine.Circle. It used to build one shapely Point per vertex of every other
shape's rings (about 43,000 in a document with 16 circles, on every resolve); it
now measures all rings and vertices in vectorised shapely calls. The earlier
implementation is kept below, unchanged, as the reference. The pass criteria were
fixed before the change: the same boolean for every circle of the corpus (C3a),
and the same resolve_regions output, geometries equal byte for byte (C3b). Both
limits are also met exactly, at every ring of the corpus, so the two implementations
must measure the same distances to the last bit, not only nearly the same.
"""
import copy
import math

import pytest
import shapely
from shapely.geometry import Point, Polygon, box

from simcase import Document, examples
from simcase import geometry
from simcase.geometry import CIRCLE_CLEARANCE, _polygonal, resolve_regions, shape_polygon


def _isolated_circle_reference(s, index, polys, clip):
    """geometry._isolated_circle before it was vectorised, kept as the reference."""
    centre, r = Point(s["cx"], s["cy"]), s["r"]
    lo, hi = r * (1 - CIRCLE_CLEARANCE), r * (1 + CIRCLE_CLEARANCE)
    if not clip.contains(centre) or clip.exterior.distance(centre) <= hi:
        return False
    for j, other in enumerate(polys):
        if j == index or other.is_empty:
            continue
        for part in shapely.get_parts(other):
            for line in (part.exterior, *part.interiors):
                far = max(centre.distance(Point(c)) for c in line.coords)
                if line.distance(centre) <= hi and far >= lo:
                    return False
    return True


R = 2.0
GAP = R * CIRCLE_CLEARANCE            # the clearance an exact circle needs, 2e-6 mm here
JUST_INSIDE, JUST_OUTSIDE = GAP * (1 - 1e-3), GAP * (1 + 1e-3)   # 2e-9 mm either side of it


def circle(name, cx, cy, r=R, material='copper'):
    return {'name': name, 'type': 'circle', 'cx': cx, 'cy': cy, 'r': r, 'material': material}


def rect(name, x, y, w, h, material='steel'):
    return {'name': name, 'type': 'rect', 'x': x, 'y': y, 'w': w, 'h': h, 'material': material}


def polygon(name, points, material='steel'):
    return {'name': name, 'type': 'polygon', 'points': [list(p) for p in points], 'material': material}


def heat_document(shapes):
    """The shipped steady region example (40 x 20 mm domain) with other shapes."""
    d = copy.deepcopy(examples.EXAMPLES['thermal_regions'])
    d['geometry']['shapes'] = shapes
    d['physics']['heat1']['heat_source_w_m3'] = 0.
    return d


def heater_at(**heater):
    d = copy.deepcopy(examples.EXAMPLES['thermal_regions'])
    d['geometry']['shapes'][1].update(heater)
    return d


def star(cx, cy, r1, r2, n):
    return [(cx + (r1 if i % 2 == 0 else r2) * math.cos(2 * math.pi * i / n),
             cy + (r1 if i % 2 == 0 else r2) * math.sin(2 * math.pi * i / n)) for i in range(n)]


def sixteen_circles():
    """16 isolated circles after 47 rects and a 512-point polygon (the measured workload)."""
    shapes = [polygon('star', star(7., 10., 5., 4.5, 512))]
    shapes += [rect(f'r{k}', 13.5 + 1.4 * (k % 6), 1.5 + 2.3 * (k // 6), .6, .6) for k in range(47)]
    shapes += [circle(f'c{k}', 25. + 4. * (k % 4), 2.5 + 5. * (k // 4), r=1.2) for k in range(16)]
    return heat_document(shapes)


# Concave bracket: it clips to a polygon plus a line piece (see test_thermal_regions).
BRACKET = [[38, 2], [44, 2], [44, 10], [40, 10], [40, 6], [42, 6], [42, 4], [38, 4]]
# Square ring with a slit on the right: a pocket [17, 23] x [7, 13] around (20, 10).
POCKET = [(14, 4), (26, 4), (26, 9.5), (23, 9.5), (23, 7), (17, 7), (17, 13), (23, 13), (23, 10.5),
          (26, 10.5), (26, 16), (14, 16)]
# Inverted U whose bridge lies below the domain: clipping leaves two legs, a MultiPolygon.
LEGS = [(10, 3), (11, 3), (11, -1), (13, -1), (13, 3), (14, 3), (14, -3), (10, -3)]


def _corner_square(name, rho):
    """A square centred on (20, 10) whose corners are rho from the centre."""
    a = rho / math.sqrt(2.)
    return rect(name, 20. - a, 10. - a, 2. * a, 2. * a)


# Radii whose limits land exactly on a distance shapely measures (checked below): an edge
# r * (1 + clearance) above the centre, and diamond corners r * (1 - clearance) from it.
TIE_EDGE_R, TIE_VERTEX_R = 3., 1.375
TIE_LO = TIE_VERTEX_R * (1 - CIRCLE_CLEARANCE)
DIAMOND = [(20. + TIE_LO, 10.), (20., 10. + TIE_LO), (20. - TIE_LO, 10.), (20., 10. - TIE_LO)]


# name -> (document, {circle name: the boolean the geometry implies}). The expected
# values are worked out from the geometry, so the corpus is known to reach both sides
# of every limit; C3a itself compares the two implementations on every circle.
CORPUS = {
    'shipped steady example': (examples.EXAMPLES['thermal_regions'], {'heater': True}),
    'shipped transient example': (examples.EXAMPLES['transient_thermal_regions'], {}),
    'shipped fiber example': (examples.EXAMPLES['fiber'], {'core': True}),
    'heater tangent to the bottom side': (heater_at(cy=2.), {'heater': False}),
    'heater tangent to the plate edge from outside': (heater_at(cy=13.), {'heater': False}),
    'heater across the plate edge': (heater_at(cy=11.), {'heater': False}),
    'heater clear of the plate': (heater_at(cy=13.5), {'heater': True}),
    # The edge runs from x = 5 to 35, so its vertices are 15 mm away: only the distance
    # to the edge itself, not to its vertices, puts it inside the clearance.
    'edge just inside the clearance': (heat_document(
        [rect('lid', 5., 12. + JUST_INSIDE, 30., 3.), circle('c', 20., 10.)]), {'c': False}),
    'edge just outside the clearance': (heat_document(
        [rect('lid', 5., 12. + JUST_OUTSIDE, 30., 3.), circle('c', 20., 10.)]), {'c': True}),
    # Both limits are inclusive: a boundary exactly at either one keeps the circle a polygon.
    'edge exactly at the clearance': (heat_document(
        [rect('lid', 12., 10. + TIE_EDGE_R * (1 + CIRCLE_CLEARANCE), 16., 3.),
         circle('c', 20., 10., r=TIE_EDGE_R)]), {'c': False}),
    'vertex exactly at the clearance inside': (heat_document(
        [circle('c', 20., 10., r=TIE_VERTEX_R), polygon('diamond', DIAMOND)]), {'c': False}),
    'edge after the circle just inside the clearance': (heat_document(
        [circle('c', 20., 10.), rect('lid', 5., 12. + JUST_INSIDE, 30., 3.)]), {'c': False}),
    'covered corner just inside the clearance': (heat_document(
        [_corner_square('core', R - JUST_INSIDE), circle('c', 20., 10.)]), {'c': False}),
    'covered corner just outside the clearance': (heat_document(
        [_corner_square('core', R - JUST_OUTSIDE), circle('c', 20., 10.)]), {'c': True}),
    'domain side just inside the clearance': (heat_document(
        [circle('c', 20., R + JUST_INSIDE)]), {'c': False}),
    'domain side just outside the clearance': (heat_document(
        [circle('c', 20., R + JUST_OUTSIDE)]), {'c': True}),
    'circle touching the domain side': (heat_document(
        [rect('plate', 5., 5., 30., 6.), circle('c', 40. - R, 15.)]), {'c': False}),
    'clipped circle and its neighbour': (heat_document(
        [circle('clipped', 39., 10.), circle('near', 34., 10.)]), {'clipped': False, 'near': True}),
    'circle overlapped by a later rect': (heat_document(
        [circle('c', 20., 10.), rect('bar', 19., 9., 6., 2.)]), {'c': False}),
    'later rect inside the circle': (heat_document(
        [circle('c', 20., 10.), rect('pin', 19.5, 9.5, 1., 1.)]), {'c': True}),
    'nested circles, inner one later': (heat_document(
        [circle('outer', 20., 10., r=6.), circle('inner', 20., 10., r=1.)]), {'outer': True, 'inner': True}),
    'nested circles, outer one later': (heat_document(
        [circle('inner', 20., 10., r=1.), circle('outer', 20., 10., r=6.)]), {'outer': True, 'inner': True}),
    'nested circles inside each other\'s clearance': (heat_document(
        [circle('outer', 20., 10., r=R + JUST_INSIDE), circle('inner', 20., 10.)]), {'outer': False, 'inner': False}),
    'nested circles 0.5 mm apart': (heat_document(
        [circle('outer', 20., 10., r=R + .5), circle('inner', 20., 10.)]), {'outer': True, 'inner': True}),
    '16 isolated circles, 47 rects and a 512-point polygon': (
        sixteen_circles(), {f'c{k}': True for k in range(16)}),
    'circle inside a polygon': (heat_document(
        [polygon('frame', star(20., 10., 6., 5.5, 64)), circle('c', 20., 10.)]), {'c': True}),
    'circle in a polygon pocket': (heat_document(
        [polygon('ring', POCKET), circle('c', 20., 10.)]), {'c': True}),
    'circle filling a polygon pocket to the clearance': (heat_document(
        [polygon('ring', POCKET), circle('c', 20., 10., r=3. / (1 + CIRCLE_CLEARANCE * (1 - 1e-3)))]),
        {'c': False}),
    'circle next to a shape clipped to a polygon and a line piece': (heat_document(
        [polygon('bracket', BRACKET), rect('plate', 5., 5., 30., 6.), circle('c', 20., 8.)]), {'c': True}),
    'circles at a shape clipped to two parts': (heat_document(
        [polygon('legs', LEGS), circle('above', 12., 5., r=1.), circle('between', 12., 1.5, r=1.)]),
        {'above': True, 'between': False}),
    # Each circle comes close to one leg only, so every part of the shape must be measured.
    'circles next to each leg of a two-part shape': (heat_document(
        [polygon('legs', LEGS), circle('left', 9., 1.5, r=1.), circle('right', 15., 1.5, r=1.),
         circle('clear', 18., 1.5, r=.5)]), {'left': False, 'right': False, 'clear': True}),
}


def _circles(doc):
    """[(index, shape, polys, clip)] for every circle, built as resolve_regions builds them."""
    dom = doc.domain
    clip = box(dom['xmin'], dom['ymin'], dom['xmax'], dom['ymax'])
    polys = [_polygonal(shape_polygon(s).intersection(clip)) for s in doc.shapes]
    return [(i, s, polys, clip) for i, s in enumerate(doc.shapes) if s['type'] == 'circle']


@pytest.mark.parametrize('case', list(CORPUS))
def test_c3a_every_circle_gets_the_reference_answer(case):
    data, expected = CORPUS[case]
    doc = Document.from_dict(copy.deepcopy(data))
    answers = {}
    for i, s, polys, clip in _circles(doc):
        new = geometry._isolated_circle(s, i, polys, clip)
        assert type(new) is bool, (s['name'], type(new))
        assert new == _isolated_circle_reference(s, i, polys, clip), s['name']
        answers[s['name']] = new
    assert answers == expected


@pytest.mark.parametrize('r,expected', [(R, True), (3. / (1 + CIRCLE_CLEARANCE * (1 - 1e-3)), False),
                                        (3. / (1 + CIRCLE_CLEARANCE * (1 + 1e-3)), True)])
def test_c3a_a_circle_inside_a_polygon_hole(r, expected):
    """A document shape clips to polygons without holes, so the interior rings are
    reached here with a frame built by hand: a square hole 3 mm from the centre."""
    clip = box(0., 0., 40., 20.)
    frame = box(10., 0., 30., 20.).difference(box(17., 7., 23., 13.))
    s = circle('c', 20., 10., r=r)
    polys = [frame, _polygonal(shape_polygon(s).intersection(clip))]
    assert len(frame.interiors) == 1
    new = geometry._isolated_circle(s, 1, polys, clip)
    assert type(new) is bool
    assert new == _isolated_circle_reference(s, 1, polys, clip) == expected


def test_the_corpus_reaches_both_answers_and_a_multipart_shape():
    """The comparison above proves little if every circle passed or every one failed."""
    answers = [v for _data, expected in CORPUS.values() for v in expected.values()]
    assert answers.count(True) >= 20 and answers.count(False) >= 12
    legs = Document.from_dict(copy.deepcopy(CORPUS['circles at a shape clipped to two parts'][0]))
    assert _circles(legs)[0][2][0].geom_type == 'MultiPolygon'
    many = Document.from_dict(sixteen_circles())
    assert len(shapely.get_coordinates(_circles(many)[0][2][0])) == 513     # 512 points, closed


def test_the_exact_cases_are_ties_as_the_reference_measures_them():
    """If a GEOS release rounds these distances differently, this fails instead of the two
    exact cases silently becoming near misses."""
    lid = Document.from_dict(copy.deepcopy(CORPUS['edge exactly at the clearance'][0]))
    (_i, s, polys, _clip), = _circles(lid)
    assert polys[0].exterior.distance(Point(s['cx'], s['cy'])) == s['r'] * (1 + CIRCLE_CLEARANCE)
    diamond = Document.from_dict(copy.deepcopy(CORPUS['vertex exactly at the clearance inside'][0]))
    (_i, s, polys, _clip), = _circles(diamond)
    centre = Point(s['cx'], s['cy'])
    assert max(centre.distance(Point(c)) for c in polys[1].exterior.coords) == s['r'] * (1 - CIRCLE_CLEARANCE)


def _radii(factor, limit):
    """[r] with r * factor == limit, the way _isolated_circle computes its limits from r.

    Where rounding leaves the limit out of reach (as where r crosses a power of two from
    it), the two adjacent radii whose limits straddle it.
    """
    r = limit / factor
    while r * factor < limit:
        r = math.nextafter(r, math.inf)
    while r * factor > limit:
        r = math.nextafter(r, -math.inf)
    return [r] if r * factor == limit else [r, math.nextafter(r, math.inf)]


def test_c3a_every_ring_of_the_corpus_at_both_limits():
    """Each ring of the corpus is measured from a circle's centre as the reference measures
    it, then set alone against each limit exactly at that distance and one float past it.
    The answer flips there, so the two implementations agree only if they measure every
    ring's nearest and farthest distance to the same double."""
    limits = exact = 0
    for case, (data, _expected) in CORPUS.items():
        doc = Document.from_dict(copy.deepcopy(data))
        for i, s, polys, _clip in _circles(doc):
            centre = Point(s['cx'], s['cy'])
            for part in shapely.get_parts([p for j, p in enumerate(polys) if j != i and not p.is_empty]):
                for line in (part.exterior, *part.interiors):
                    near = line.distance(centre)
                    far = max(centre.distance(Point(c)) for c in line.coords)
                    alone = [Polygon(line), polys[i]]
                    half = 2. * far + 1.
                    clip = box(s['cx'] - half, s['cy'] - half, s['cx'] + half, s['cy'] + half)
                    ties = [(1 - CIRCLE_CLEARANCE, far), (1 - CIRCLE_CLEARANCE, math.nextafter(far, math.inf))]
                    if near > 0.:      # no positive radius ties a ring through the centre
                        ties += [(1 + CIRCLE_CLEARANCE, near), (1 + CIRCLE_CLEARANCE, math.nextafter(near, -math.inf))]
                    for factor, limit in ties:
                        radii = _radii(factor, limit)
                        limits += 1
                        exact += len(radii) == 1
                        for r in radii:
                            probe = dict(s, r=r)
                            lo, hi = r * (1 - CIRCLE_CLEARANCE), r * (1 + CIRCLE_CLEARANCE)
                            old = _isolated_circle_reference(probe, 1, alone, clip)
                            assert old == (not (near <= hi and far >= lo)), (case, s['name'], r)
                            assert geometry._isolated_circle(probe, 1, alone, clip) == old, (case, s['name'], r)
    # A limit is out of reach mainly where r crosses a power of two from it: 1 of 4,222 here.
    assert limits > 4000 and exact >= .99 * limits, (exact, limits)


def _resolved(doc):
    return [(name, material, size, exact, shapely.to_wkb(geom))
            for name, material, geom, size, exact in resolve_regions(doc)]


@pytest.mark.parametrize('case', list(CORPUS))
def test_c3b_resolve_regions_is_unchanged(case, monkeypatch):
    data, expected = CORPUS[case]
    doc = Document.from_dict(copy.deepcopy(data))
    new_doc, old_doc = doc.copy(), doc.copy()
    new = _resolved(new_doc)
    with monkeypatch.context() as m:
        m.setattr(geometry, '_isolated_circle', _isolated_circle_reference)
        old = _resolved(old_doc)
    assert [row[:4] for row in new] == [row[:4] for row in old]
    assert [row[4] for row in new] == [row[4] for row in old]
    assert new_doc.notes == old_doc.notes
    exact = [name for name, _m, _s, ex, _g in new if ex]
    assert set(exact) <= {name for name, value in expected.items() if value}
