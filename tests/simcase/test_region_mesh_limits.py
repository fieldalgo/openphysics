# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Mesh limits for heat region documents: the loop-vertex count and the domain it counts.

``geometry._domain_from_regions`` builds the meshine Domain exactly as ``build_domain``
did and also counts the loop vertices it queues: the sum of the lengths of the loops given
to ``Domain.add_region``, each ``Circle`` counted as its ``n``. ``build_domain`` keeps its
public three-tuple. The earlier ``build_domain`` is kept below, unchanged, as the
reference.

The pass criteria were fixed before the change. Nothing is stored: every comparison is
between two computations made here.
"""
import copy

import numpy as np
import pytest
from shapely.geometry import MultiPolygon, Point, Polygon

from meshine import Circle, Domain, box_sides
from simcase import Document, build_domain
from simcase import geometry
from simcase.geometry import _domain_from_regions, _min_area, _rings, resolve_regions

import region_studio_fixtures as F


def _build_domain_reference(doc):
    """geometry.build_domain before the loop-vertex count, kept as the reference."""
    mesh_cfg = doc["mesh"]
    d = Domain(size=mesh_cfg["size"])
    dom = doc.domain
    materials = {}
    circle_lookup = {}

    def circle_for(cx, cy, r):
        key = (round(cx, 12), round(cy, 12), round(r, 12))
        if key not in circle_lookup:
            circle_lookup[key] = Circle((cx, cy), r, n=max(16, int(2 * np.pi * r / (mesh_cfg["size"] / 2))))
        return circle_lookup[key]

    regions = resolve_regions(doc)
    min_area = _min_area(doc)
    exact_circles = {(rn): ex for rn, _m, _g, _s, ex in regions if ex}

    for name, material, geom, size, exact in regions:
        materials[name] = material
        if exact:
            d.add_region(name, circle_for(*exact["center"], exact["r"]), size=size)
            continue
        parts = list(geom.geoms) if isinstance(geom, MultiPolygon) else [geom]
        for part in parts:
            if part.area < min_area:
                continue
            outer, holes = _rings(part)
            hole_objs = []
            for h in holes:
                hp = Polygon(h)
                match = None
                for rn, ex in exact_circles.items():
                    c = Point(*ex["center"])
                    if abs(hp.area - np.pi * ex["r"] ** 2) < 0.05 * np.pi * ex["r"] ** 2 and hp.contains(c):
                        match = circle_for(*ex["center"], ex["r"])
                        break
                hole_objs.append(match if match is not None else h)
            d.add_region(name, outer, holes=hole_objs, size=size)
    return d, box_sides(dom["xmin"], dom["xmax"], dom["ymin"], dom["ymax"]), materials


#: Documents whose domains are compared. Each is valid; the covered crossings are kept small
#: here (their full size takes tens of seconds to validate).
CORPUS = {
    **{f'steady example, size {s}': (lambda s=s: F.steady_example(s)) for s in (2.0, 1.0, 0.5)},
    **{f'transient example, size {s}': (lambda s=s: F.transient_example(s)) for s in (2.0, 1.0, 0.5)},
    '64 spaced rects': F.spaced_rects,
    '16 isolated circles': F.isolated_circles,
    'crossing combs k=14': lambda: F.crossing_combs(14),
    'clipped circle': F.clipped_circle,
    'overlapped circle (128-gon)': F.overlapped_circle,
    'background split into parts': F.split_background,
    'strip': F.strip,
    'thin film': F.thin_film,
    '16 circles, 47 rects and a 512-gon': F.circles_rects_polygon,
    'tiny global size 0.0246': F.tiny_global_size,
    '8 heaters straddling the plate edge': F.straddling_heaters,
    '8 x 8 touching rects': F.rect_grid,
    '64 layer strips': F.layer_strips,
    'covered crossings, 6 teeth, 4 front rects': lambda: F.covered_crossings(6, 4),
}


def pending(domain):
    """What a Domain will build from: per queued region its name, size and loops, polygon
    loops as their exact coordinates and Circles as (first occurrence, centre, radius, n),
    so that a Circle shared by a region and a hole must be shared on both sides."""
    circles = []
    rows = []
    for name, loops, size in domain._pending:
        row = []
        for lp in loops:
            if isinstance(lp, Circle):
                index = next((k for k, c in enumerate(circles) if c is lp), None)
                if index is None:
                    circles.append(lp)
                    index = len(circles) - 1
                row.append(('circle', index, tuple(lp.center.tolist()), lp.radius, lp.n))
            else:
                row.append(('polygon', [tuple(map(float, p)) for p in lp]))
        rows.append((name, size, row))
    return rows


def loop_vertices(domain):
    """The sum of the queued loop lengths, a Circle counting as its n."""
    return sum(lp.n if isinstance(lp, Circle) else len(lp) for _name, loops, _size in domain._pending for lp in loops)


def boundary_samples(doc):
    """Points on and next to the domain sides, to compare two boundary namers by."""
    dom = doc.domain
    xs = np.linspace(dom['xmin'], dom['xmax'], 7)
    ys = np.linspace(dom['ymin'], dom['ymax'], 7)
    return [(x, y) for x in xs for y in (dom['ymin'], dom['ymax'])] + \
           [(x, y) for y in ys for x in (dom['xmin'], dom['xmax'])]


@pytest.mark.parametrize('case', list(CORPUS))
def test_c2_the_domain_is_the_one_build_domain_built(case):
    doc = Document.from_dict(CORPUS[case]())
    reference, ref_namer, ref_materials = _build_domain_reference(doc.copy())
    for new, namer, materials in (_domain_from_regions(doc.copy(), resolve_regions(doc.copy()))[:3],
                                  _domain_from_regions(doc.copy())[:3], build_domain(doc.copy())):
        assert new.default_size == reference.default_size
        assert pending(new) == pending(reference)
        assert materials == ref_materials
        assert [namer(p) for p in boundary_samples(doc)] == [ref_namer(p) for p in boundary_samples(doc)]


@pytest.mark.parametrize('case', list(CORPUS))
def test_c3_the_count_is_the_sum_of_the_queued_loops(case):
    doc = Document.from_dict(CORPUS[case]())
    domain, _namer, _materials, count = _domain_from_regions(doc)
    assert type(count) is int
    assert count == loop_vertices(domain) == loop_vertices(_build_domain_reference(doc.copy())[0])


def test_the_corpus_reaches_circles_holes_and_split_parts():
    """The comparison proves little unless the corpus has exact circles (as regions and as
    holes), 128-gon circles, regions in several parts and crossing polygons."""
    shared = parts = 0
    for build in CORPUS.values():
        doc = Document.from_dict(build())
        domain = _domain_from_regions(doc)[0]
        loops = [lp for _name, region_loops, _size in domain._pending for lp in region_loops]
        shared += sum(1 for lp in loops if isinstance(lp, Circle)) - len({id(lp) for lp in loops if isinstance(lp, Circle)})
        names = [name for name, _loops, _size in domain._pending]
        parts += len(names) - len(set(names))
    assert shared >= 16 and parts >= 2
    combs = _domain_from_regions(Document.from_dict(F.crossing_combs(14)))[0]
    assert len(combs._pending) > 100                                      # the combs cut each other


def test_build_domain_keeps_its_three_tuple():
    result = build_domain(Document.from_dict(F.steady_example()))
    assert isinstance(result, tuple) and len(result) == 3
    domain, namer, materials = result
    assert isinstance(domain, Domain) and callable(namer)
    assert materials == {'plate': 'steel', 'heater': 'copper', 'background': 'insulation'}


def test_build_domain_still_leaves_the_resolver_notes_on_the_document():
    """build_mesh copies the notes resolve_regions leaves on its micrometre document; an
    electromagnetic document with a shape outside the domain must keep its note."""
    from simcase import examples
    d = copy.deepcopy(examples.EXAMPLES['soi_strip'])
    d['geometry']['shapes'].append({'name': 'far', 'type': 'rect', 'x': 10.0, 'y': 10.0, 'w': 1.0, 'h': 1.0,
                                    'material': 'Si'})
    doc = Document.from_dict(d)
    doc.notes = []
    build_domain(doc)
    assert any("'far'" in note for note in doc.notes)
    assert geometry.build_domain is build_domain
