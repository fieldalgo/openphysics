# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Mesh limits for heat region documents.

``geometry._domain_from_regions`` builds the meshine Domain exactly as ``build_domain``
did and also counts the loop vertices it queues: the sum of the lengths of the loops given
to ``Domain.add_region``, each ``Circle`` counted as its ``n``. ``build_domain`` keeps its
public three-tuple. The earlier ``build_domain`` is kept below, unchanged, as the
reference (C-2, C-3).

``run(doc, *, max_nodes, max_triangles, max_input_vertices)`` bounds a region run before
the solve, ``check_mesh_limits`` counts the loop vertices without building the domain, and
both raise ``MeshLimitError`` (C-1, C-4 to C-10). Node and triangle counts are never
written down: each test meshes uncapped first and takes N and M from that mesh.

A run meshes the document's micrometre copy (``runner.micrometre_document``), so the loop
vertices the limits count are those of that copy. The region documents here are written in
millimetres; the tests marked "port" were added when the limits moved onto that copy and
onto the physics registry, and were not pre-registered.

The pass criteria were fixed before the change. Nothing is stored: every comparison is
between two computations made here.
"""
import copy
import json
import math
import pickle

import numpy as np
import pytest
from shapely.geometry import MultiPolygon, Point, Polygon

import meshine
from meshine import Circle, Domain, box_sides
from simcase import Document, DocumentError, MeshLimitError, build_domain, check_mesh_limits, examples, run
from simcase import geometry, registry, units
from simcase.geometry import _domain_from_regions, _min_area, _rings, resolve_regions
from simcase.mesh_limits import _MeshLimits
from simcase.runner import micrometre_document

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


# ---- C-3: check_mesh_limits counts what the domain queues -----------------------------------

@pytest.mark.parametrize('case', list(CORPUS))
def test_c3_check_mesh_limits_returns_the_queued_loop_count(case):
    """The count is the reference domain's of the micrometre copy a run meshes. On this
    corpus, written in millimetres, it is also the count of the document itself (measured
    at the port; the next test shows a document where the two differ)."""
    doc = Document.from_dict(CORPUS[case]())
    before = json.dumps(doc.data, sort_keys=True)
    count = check_mesh_limits(doc, max_input_vertices=10 ** 6)
    assert type(count) is int
    assert count == loop_vertices(_build_domain_reference(micrometre_document(doc))[0])
    assert count == loop_vertices(_build_domain_reference(doc.copy())[0])
    assert json.dumps(doc.data, sort_keys=True) == before and doc.notes == []


# ---- helpers for the runs ---------------------------------------------------------------------

def saved(result, path):
    """Every public array a result saves and its summary without the timings."""
    out = result.save(path)
    with np.load(out / 'fields.npz', allow_pickle=False) as fields:
        arrays = {key: fields[key] for key in fields.files if key != 'metadata_json'}
    summary = json.loads((out / 'summary.json').read_text())
    summary.pop('timings_s')
    return arrays, summary


def assert_same_result(new, old, tmp_path):
    (a, sa), (b, sb) = saved(new, tmp_path / 'new'), saved(old, tmp_path / 'old')
    assert list(a) == list(b)
    for key in a:
        assert a[key].dtype == b[key].dtype and np.array_equal(a[key], b[key]), key
    assert sa == sb


def forbid(monkeypatch, target, name, message='a refused run must stop before this call'):
    def refused(*args, **kwargs):
        raise AssertionError(f'{target.__name__}.{name}: {message}')
    monkeypatch.setattr(target, name, refused)


def forbid_solvers(monkeypatch):
    import galerkin.thermal
    import galerkin.transient_heat
    # Modules that bind solve_steady_heat by name when first imported must be imported before
    # the stub goes in, or they keep it for the rest of the process: validating the Joule
    # documents of C-8 imports galerkin.joule_heating, and later tests then got the stub.
    import galerkin.joule_heating  # noqa: F401
    import galerkin.thermal_mechanical  # noqa: F401
    forbid(monkeypatch, galerkin.thermal, 'solve_steady_heat')
    forbid(monkeypatch, galerkin.transient_heat, 'solve_transient_heat')


def spy_generate(monkeypatch):
    """The keyword arguments of every meshine.generate call."""
    calls = []
    real = meshine.generate

    def spy(*args, **kwargs):
        calls.append(dict(kwargs))
        return real(*args, **kwargs)
    monkeypatch.setattr(meshine, 'generate', spy)
    return calls


RUNS = {**{f'steady example, size {s}': (lambda s=s: F.steady_example(s)) for s in (2.0, 1.0)},
        **{f'transient example, size {s}': (lambda s=s: F.transient_example(s)) for s in (2.0, 1.0, 0.7)}}


# ---- C-1: no limits, no change ---------------------------------------------------------------

@pytest.mark.parametrize('case', ['steady example, size 2.0', 'transient example, size 2.0'])
def test_c1_without_limits_meshine_gets_only_the_minimum_angle(monkeypatch, case):
    calls = spy_generate(monkeypatch)
    run(Document.from_dict(RUNS[case]()), verbose=False)
    run(Document.from_dict(RUNS[case]()), False, max_nodes=None, max_triangles=None, max_input_vertices=None)
    assert [set(kwargs) for kwargs in calls] == [{'min_angle'}, {'min_angle'}]


# ---- C-4, C-5: loop vertices -----------------------------------------------------------------

def test_c4_a_tiny_global_size_is_refused_by_its_loop_vertex_count(monkeypatch):
    """The heater is isolated, so its Circle gets max(16, int(4 pi r / mesh.size)) vertices
    and is queued twice (itself and the plate's hole); the plate's ring, the background box
    and the plate's ring again as the background's hole are 4 each. At mesh.size 0.0246 mm,
    24.6 um in the micrometre copy that is meshed, that is 2054 (computed below)."""
    doc = Document.from_dict(F.tiny_global_size(0.0246))
    r, size = (units.length_to_micrometres(v, doc.scale) for v in (2.0, 0.0246))
    expected = 2 * max(16, int(4 * math.pi * r / size)) + 3 * 4
    assert expected > 2048
    with pytest.raises(MeshLimitError) as refused:
        check_mesh_limits(doc, max_input_vertices=2048)
    assert (refused.value.quantity, refused.value.count, refused.value.limit) == ('input_vertices', expected, 2048)
    assert f'{expected} loop vertices' in str(refused.value) and '2048' in str(refused.value)
    assert 'global mesh.size' in str(refused.value)
    forbid(monkeypatch, meshine.Domain, 'build')
    forbid_solvers(monkeypatch)
    with pytest.raises(MeshLimitError) as in_run:
        run(Document.from_dict(F.tiny_global_size(0.0246)), verbose=False, max_input_vertices=2048)
    assert (in_run.value.quantity, in_run.value.count, in_run.value.limit) == ('input_vertices', expected, 2048)
    assert check_mesh_limits(doc, max_input_vertices=expected) == expected


@pytest.mark.parametrize('size', [5e-324, 1e-320, 1e-300])
def test_c5_a_global_size_near_zero_is_refused_before_any_circle_is_made(monkeypatch, size):
    class NoCircle(Circle):
        def __init__(self, *args, **kwargs):
            raise AssertionError('a Circle was made for an over-limit circle')
    doc = Document.from_dict(F.tiny_global_size(size))
    monkeypatch.setattr(geometry, 'Circle', NoCircle)
    with pytest.raises(MeshLimitError) as refused:
        check_mesh_limits(doc, max_input_vertices=2048)
    assert type(refused.value) is MeshLimitError
    assert (refused.value.quantity, refused.value.count, refused.value.limit) == ('input_vertices', None, 2048)
    r, size_um = (units.length_to_micrometres(v, doc.scale) for v in (2.0, size))   # what is meshed
    assert f'radius {r:g} um' in str(refused.value) and '2048' in str(refused.value)
    half = size_um / 2                                    # the circle's own estimate is named
    estimate = math.inf if half == 0 else 2 * math.pi * r / half
    assert f'= {estimate:.4g} loop vertices' in str(refused.value)
    forbid(monkeypatch, meshine.Domain, 'build')
    forbid_solvers(monkeypatch)
    with pytest.raises(MeshLimitError) as in_run:
        run(Document.from_dict(F.tiny_global_size(size)), verbose=False, max_input_vertices=2048)
    assert type(in_run.value) is MeshLimitError and in_run.value.count is None


# ---- C-6, C-6b, C-7: nodes and triangles -------------------------------------------------------

@pytest.mark.parametrize('case', list(RUNS))
def test_c6_limits_at_the_mesh_size_change_nothing_and_one_less_refuses(monkeypatch, tmp_path, case):
    """C-6 (steady and transient at sizes 2 and 1) and C-7 (transient at 0.7): max_nodes = N
    and max_triangles = M give every saved array and the summary of the unlimited run; N - 1
    and M - 1 are refused before the solve."""
    unlimited = run(Document.from_dict(RUNS[case]()), verbose=False)
    n, m = len(unlimited.mesh_nodes_m), len(unlimited.mesh_triangles)
    vertices = check_mesh_limits(Document.from_dict(RUNS[case]()), max_input_vertices=10 ** 6)
    both = run(Document.from_dict(RUNS[case]()), verbose=False, max_nodes=n, max_triangles=m,
               max_input_vertices=vertices)
    assert_same_result(both, unlimited, tmp_path / 'all')
    forbid_solvers(monkeypatch)
    with pytest.raises(MeshLimitError) as nodes:
        run(Document.from_dict(RUNS[case]()), verbose=False, max_nodes=n - 1)
    assert (nodes.value.quantity, nodes.value.limit) == ('nodes', n - 1)
    assert nodes.value.count is None          # meshine stopped at max_points = n - 1
    assert str(n - 1) in str(nodes.value)
    with pytest.raises(MeshLimitError) as triangles:
        run(Document.from_dict(RUNS[case]()), verbose=False, max_triangles=m - 1)
    assert (triangles.value.quantity, triangles.value.count, triangles.value.limit) == ('triangles', m, m - 1)
    assert f'{m} triangles' in str(triangles.value) and str(m - 1) in str(triangles.value)
    with pytest.raises(MeshLimitError) as loops:
        run(Document.from_dict(RUNS[case]()), verbose=False, max_input_vertices=vertices - 1)
    assert (loops.value.quantity, loops.value.count, loops.value.limit) == ('input_vertices', vertices, vertices - 1)


@pytest.mark.parametrize('limit', ['max_nodes', 'max_triangles', 'max_input_vertices'])
def test_c6b_each_limit_alone(monkeypatch, tmp_path, limit):
    """One limit given and the others None: the run passes at the exact value with the
    unlimited arrays, meshine gets max_points only from max_nodes, and one less refuses."""
    build = RUNS['steady example, size 1.0']
    unlimited = run(Document.from_dict(build()), verbose=False)
    exact = {'max_nodes': len(unlimited.mesh_nodes_m), 'max_triangles': len(unlimited.mesh_triangles),
             'max_input_vertices': check_mesh_limits(Document.from_dict(build()), max_input_vertices=10 ** 6)}[limit]
    calls = spy_generate(monkeypatch)
    alone = run(Document.from_dict(build()), verbose=False, **{limit: exact})
    assert_same_result(alone, unlimited, tmp_path)
    assert calls == [{'min_angle': 28.0, **({'max_points': exact} if limit == 'max_nodes' else {})}]
    forbid_solvers(monkeypatch)
    with pytest.raises(MeshLimitError) as refused:
        run(Document.from_dict(build()), verbose=False, **{limit: exact - 1})
    assert refused.value.quantity == limit.removeprefix('max_') and refused.value.limit == exact - 1


def test_c6b_a_triangle_or_vertex_limit_alone_leaves_meshine_its_own_cap(monkeypatch):
    """Without max_nodes no max_points is passed, so meshine keeps its default cap and its
    own error, a RuntimeError, as before."""
    real = meshine.generate

    def capped(*args, **kwargs):
        assert 'max_points' not in kwargs
        return real(*args, **kwargs, max_points=50)
    monkeypatch.setattr(meshine, 'generate', capped)
    with pytest.raises(meshine.MeshSizeLimitError) as refused:
        run(Document.from_dict(F.steady_example(2.0)), verbose=False, max_triangles=10 ** 6, max_input_vertices=10 ** 6)
    assert not isinstance(refused.value, MeshLimitError)


def test_only_max_nodes_needs_a_meshine_with_the_typed_cap(monkeypatch, tmp_path):
    """Documented, not a pre-registered criterion: with a meshine that lacks
    MeshSizeLimitError, a run that sets max_nodes raises ImportError, and other limits and
    unlimited runs are unchanged."""
    unlimited = run(Document.from_dict(F.steady_example()), verbose=False)
    monkeypatch.delattr(meshine, 'MeshSizeLimitError')
    with pytest.raises(ImportError):
        run(Document.from_dict(F.steady_example()), verbose=False, max_nodes=10 ** 6)
    others = run(Document.from_dict(F.steady_example()), verbose=False, max_triangles=10 ** 6,
                 max_input_vertices=10 ** 6)
    assert_same_result(others, unlimited, tmp_path)


# ---- C-8, C-9: where the limits apply ---------------------------------------------------------

@pytest.mark.parametrize('name', ['thermal_slab', 'transient_thermal_uniform', 'soi_strip',
                                  # port: the kinds and documents main gained since
                                  'thermal_boundary', 'electric_rectangle', 'joule_temperature', 'cavity_box'])
def test_c8_limits_refuse_documents_without_regions(monkeypatch, name):
    forbid(monkeypatch, meshine, 'generate')
    forbid_solvers(monkeypatch)
    for limit in ('max_nodes', 'max_triangles', 'max_input_vertices'):
        with pytest.raises(ValueError, match='mesh limits apply only to thermal region documents'):
            run(Document.from_dict(copy.deepcopy(examples.EXAMPLES[name])), verbose=False, **{limit: 10 ** 6})
    with pytest.raises(ValueError, match='expected a steady or transient heat region document'):
        check_mesh_limits(Document.from_dict(copy.deepcopy(examples.EXAMPLES[name])), max_input_vertices=10 ** 6)


@pytest.mark.parametrize('value', [0, -1, True, False, 2.0, '5', 10.0 ** 6])
def test_c8_a_limit_must_be_a_positive_int(monkeypatch, value):
    forbid(monkeypatch, meshine, 'generate')
    for limit in ('max_nodes', 'max_triangles', 'max_input_vertices'):
        with pytest.raises(ValueError, match=f'{limit}: expected a positive int'):
            run(Document.from_dict(F.steady_example()), verbose=False, **{limit: value})
    with pytest.raises(ValueError, match='max_input_vertices: expected a positive int'):
        check_mesh_limits(Document.from_dict(F.steady_example()), max_input_vertices=value)
    with pytest.raises(ValueError, match='max_input_vertices: expected a positive int'):
        check_mesh_limits(Document.from_dict(F.steady_example()), max_input_vertices=None)


def test_check_mesh_limits_takes_a_document():
    """Not a pre-registered criterion: a raw dict is a TypeError, not an AttributeError."""
    with pytest.raises(TypeError, match='expected a Document'):
        check_mesh_limits(F.steady_example(), max_input_vertices=2048)


def test_c8_a_numpy_integer_is_a_limit(tmp_path):
    result = run(Document.from_dict(F.steady_example()), verbose=False, max_nodes=np.int64(10 ** 6))
    assert_same_result(result, run(Document.from_dict(F.steady_example()), verbose=False), tmp_path)


def test_c9_the_error_type_and_the_exports():
    import simcase
    assert issubclass(MeshLimitError, ValueError) and not issubclass(MeshLimitError, DocumentError)
    assert {'MeshLimitError', 'check_mesh_limits'} <= set(simcase.__all__)
    for exc in (MeshLimitError('input_vertices', 2048, 2054), MeshLimitError('nodes', 10, None),
                MeshLimitError('triangles', 10, 11), MeshLimitError('input_vertices', 5, None, 'one circle')):
        copy_ = pickle.loads(pickle.dumps(exc))
        assert (type(copy_), str(copy_), copy_.quantity, copy_.limit, copy_.count) == \
               (MeshLimitError, str(exc), exc.quantity, exc.limit, exc.count)
    with pytest.raises(ValueError, match='unknown quantity'):
        MeshLimitError('points', 1, 2)


# ---- C-10: crossing combs ---------------------------------------------------------------------

def test_c10_crossing_combs_are_refused_without_building_the_domain(monkeypatch):
    """Combs k = 63: 510 polygon points, which their booleans cut into thousands of loops."""
    data = F.crossing_combs(63)
    assert sum(len(s['points']) for s in data['geometry']['shapes']) == 510
    doc = Document.from_dict(data)
    exact = loop_vertices(_build_domain_reference(doc.copy())[0])
    assert exact > 2048
    forbid(monkeypatch, meshine.Domain, 'build')
    forbid_solvers(monkeypatch)
    with pytest.raises(MeshLimitError) as refused:
        check_mesh_limits(doc, max_input_vertices=2048)
    assert (refused.value.quantity, refused.value.count, refused.value.limit) == ('input_vertices', exact, 2048)
    with pytest.raises(MeshLimitError) as in_run:
        run(Document.from_dict(data), verbose=False, max_input_vertices=2048)
    assert in_run.value.count == exact


# ---- port: the micrometre copy and the registry ---------------------------------------------

def spy_domains(monkeypatch):
    """The loop-vertex count of every Domain handed to meshine.generate, before it is built."""
    counts = []
    real = meshine.generate

    def spy(domain, *args, **kwargs):
        counts.append(loop_vertices(domain))
        return real(domain, *args, **kwargs)
    monkeypatch.setattr(meshine, 'generate', spy)
    return counts


def in_unit(data, unit, factor):
    """A region document rewritten in another length unit: every length times ``factor``."""
    d = copy.deepcopy(data)
    d['units']['length'] = unit
    g = d['geometry']
    g['domain'] = {k: v * factor for k, v in g['domain'].items()}
    if 'mesh_size' in g['background']:
        g['background']['mesh_size'] *= factor
    for shape in g['shapes']:
        for key in ('x', 'y', 'w', 'h', 'cx', 'cy', 'r', 'mesh_size'):
            if key in shape:
                shape[key] *= factor
        if 'points' in shape:
            shape['points'] = [[x * factor, y * factor] for x, y in shape['points']]
    d['mesh']['size'] *= factor
    return d


UNIT_RUNS = {**RUNS,
             'steady example in nm, size 2e6': lambda: in_unit(F.steady_example(2.0), 'nm', 1e6),
             'steady example in m, size 2e-3': lambda: in_unit(F.steady_example(2.0), 'm', 1e-3)}


@pytest.mark.parametrize('case', list(UNIT_RUNS))
def test_port_the_count_is_that_of_the_domain_a_run_meshes(monkeypatch, case):
    """Port, not pre-registered: check_mesh_limits equals the loop vertices of the Domain
    that a run hands to meshine, in millimetre, nanometre and metre documents."""
    counts = spy_domains(monkeypatch)
    run(Document.from_dict(UNIT_RUNS[case]()), verbose=False, max_input_vertices=10 ** 6)
    assert counts == [check_mesh_limits(Document.from_dict(UNIT_RUNS[case]()), max_input_vertices=10 ** 6)]


def test_port_the_micrometre_copy_is_counted_where_the_units_change_the_count(monkeypatch, tmp_path):
    """Port, not pre-registered. At mesh.size 4 pi 2 / 20 mm the heater's 4 pi r / mesh.size
    is 20 when computed in millimetres and rounds just below 20 in micrometres, so the
    document itself would queue two loop vertices more than the micrometre copy that is
    meshed (52 against 50 here). check_mesh_limits and the run's limit count the copy: the
    run passes at that count with the unlimited output and one less refuses it."""
    data = F.tiny_global_size(4 * math.pi * 2.0 / 20)
    doc = Document.from_dict(data)
    in_document = _domain_from_regions(doc.copy())[3]
    meshed = loop_vertices(_build_domain_reference(micrometre_document(doc))[0])
    assert in_document != meshed
    assert check_mesh_limits(doc, max_input_vertices=10 ** 6) == meshed
    counts = spy_domains(monkeypatch)
    limited = run(Document.from_dict(data), verbose=False, max_input_vertices=meshed)
    assert counts == [meshed]
    monkeypatch.undo()
    assert_same_result(limited, run(Document.from_dict(data), verbose=False), tmp_path)
    forbid(monkeypatch, meshine.Domain, 'build')
    with pytest.raises(MeshLimitError) as refused:
        run(Document.from_dict(data), verbose=False, max_input_vertices=meshed - 1)
    assert (refused.value.count, refused.value.limit) == (meshed, meshed - 1)


@pytest.mark.parametrize('k', [20, 23])
def test_port_an_unvalidated_document_is_counted_as_its_run_counts_it(monkeypatch, k):
    """Port, not pre-registered. Document.copy() and Document(data) have no resolved length
    unit until they are validated, and a run validates them first. At mesh.size 4 pi 2 / k mm
    (k = 20, 23) the document's own numbers and its micrometre copy give different counts;
    check_mesh_limits gives such a document the count of the validated one, which is the
    count of the Domain its run hands to meshine, and leaves it unvalidated."""
    data = F.tiny_global_size(4 * math.pi * 2.0 / k)
    validated = Document.from_dict(copy.deepcopy(data))
    expected = check_mesh_limits(validated, max_input_vertices=10 ** 6)
    assert expected != _domain_from_regions(validated.copy())[3]
    for doc in (validated.copy(), Document(copy.deepcopy(validated.data)), Document(copy.deepcopy(data))):
        before = (doc.scale, list(doc.notes), copy.deepcopy(doc.data))
        assert check_mesh_limits(doc, max_input_vertices=10 ** 6) == expected
        assert (doc.scale, doc.notes, doc.data) == before
        counts = spy_domains(monkeypatch)
        run(doc, verbose=False, max_input_vertices=expected)
        assert counts == [expected]
        monkeypatch.undo()


def test_port_only_an_unvalidated_document_is_validated_before_its_copy(monkeypatch):
    """Port, not pre-registered: a validated document costs one validation, that of its
    micrometre copy; an unvalidated one costs one more, of its own copy; one that its
    validation refuses raises DocumentError."""
    doc = Document.from_dict(F.steady_example())
    lengths = []
    real = Document.validate

    def validate(self):
        lengths.append(self.data['units']['length'])
        return real(self)
    monkeypatch.setattr(Document, 'validate', validate)
    check_mesh_limits(doc, max_input_vertices=10 ** 6)
    assert lengths == ['um']
    lengths.clear()
    check_mesh_limits(doc.copy(), max_input_vertices=10 ** 6)
    assert lengths == ['mm', 'um']
    bad = doc.copy()
    bad.data['units']['length'] = 'parsec'
    with pytest.raises(DocumentError, match='units.length'):
        check_mesh_limits(bad, max_input_vertices=10 ** 6)


def test_port_only_the_heat_kinds_take_mesh_limits():
    takes = {k.name for k in registry.kinds() if k.accepts_mesh_limits is not None}
    assert takes == {'thermal.steady2d', 'thermal.transient2d'}
    for name in ('thermal_regions', 'transient_thermal_regions'):
        data = examples.EXAMPLES[name]
        assert registry.kind_of(data).accepts_mesh_limits(data)
    for name in ('thermal_slab', 'thermal_boundary', 'transient_thermal_uniform'):
        data = examples.EXAMPLES[name]
        assert not registry.kind_of(data).accepts_mesh_limits(data)


class _Echo:
    def __init__(self, doc, kwargs):
        self.doc, self.kwargs = doc, kwargs


@pytest.mark.parametrize('accepts', [True, False])
def test_port_limits_reach_a_runner_only_through_its_kind(monkeypatch, accepts):
    """Port, not pre-registered: run hands the limits to the runner of the document's kind,
    as ``mesh_limits``, when the kind's ``accepts_mesh_limits`` claims the document, refuses
    them before that runner otherwise, and without limits calls ``run(doc, verbose=...)``."""
    monkeypatch.setattr(registry, '_KINDS', dict(registry._KINDS))

    def validate(doc):
        doc.notes = []
    registry.register(registry.PhysicsKind(
        name='test.limits', types=frozenset({'test.limits'}), precedence=50, validate=validate,
        run=lambda doc, **kwargs: _Echo(doc, kwargs), summary=lambda doc: 'test.limits',
        result_types=(_Echo,), defaults=lambda: {'study': {'type': 'single'}},
        accepts_mesh_limits=(lambda data: True) if accepts else None))
    doc = Document.from_dict({'physics': {'p': {'type': 'test.limits'}}})
    assert run(doc, verbose=False).kwargs == {'verbose': False}
    if accepts:
        assert run(doc, verbose=False, max_nodes=7, max_input_vertices=9).kwargs == {
            'verbose': False, 'mesh_limits': _MeshLimits(max_nodes=7, max_input_vertices=9)}
    else:
        with pytest.raises(ValueError, match='mesh limits apply only to thermal region documents'):
            run(doc, verbose=False, max_nodes=7)
