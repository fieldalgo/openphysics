# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Heat region documents that bound what a region run costs, shared by several tests.

Each generator returns a new raw document (a dict, as JSON would give it, before
``Document.from_dict``), built on one of the two shipped region examples
(``simcase.examples.EXAMPLES``), so every one is a valid document unless its docstring
says otherwise. The tests derive every count they check (loop vertices, nodes, boundary
crossings) in-process from these documents; nothing here stores an expected value, and
the sizes quoted in docstrings are descriptions, not criteria.

The steady example's domain is 40 x 20 mm; the transient example's is 30 x 5 mm.
"""
import copy
import math
import random

from simcase import examples


def steady_example(size=None):
    """The shipped steady region example: a steel plate with a copper heater in insulation."""
    doc = copy.deepcopy(examples.EXAMPLES['thermal_regions'])
    if size is not None:
        doc['mesh']['size'] = size
    return doc


def transient_example(size=None, times=None):
    """The shipped transient region example (steel plate beside insulation), optionally at
    another mesh size or with ``times`` requested times 5 s apart."""
    doc = copy.deepcopy(examples.EXAMPLES['transient_thermal_regions'])
    if size is not None:
        doc['mesh']['size'] = size
    if times is not None:
        doc['study']['time_s'] = [5.0 * i for i in range(times)]
    return doc


def rect(name, x, y, w, h, material='steel', **extra):
    return {'name': name, 'type': 'rect', 'x': x, 'y': y, 'w': w, 'h': h, 'material': material, **extra}


def circle(name, cx, cy, r, material='copper', **extra):
    return {'name': name, 'type': 'circle', 'cx': cx, 'cy': cy, 'r': r, 'material': material, **extra}


def polygon(name, points, material='steel', **extra):
    return {'name': name, 'type': 'polygon', 'points': [[float(x), float(y)] for x, y in points],
            'material': material, **extra}


def regular_polygon(cx, cy, r, n, r2=None):
    """n points on a circle of radius r, every second one on r2 when given (a gear)."""
    return [(cx + (r if r2 is None or i % 2 == 0 else r2) * math.cos(2 * math.pi * i / n),
             cy + (r if r2 is None or i % 2 == 0 else r2) * math.sin(2 * math.pi * i / n)) for i in range(n)]


def with_shapes(shapes, heat=None, base=None):
    """The steady example (or ``base``) with these shapes and a heat source on the named
    regions (``heat``: {name: W/m^3}), or no source."""
    doc = steady_example() if base is None else base
    doc['geometry']['shapes'] = shapes
    name = next(iter(doc['physics']))
    doc['physics'][name]['heat_source_w_m3'] = heat if heat else 0.0
    return doc


# ---- one thin feature in a coarse background ------------------------------------------------

def strip(width=0.2, size=0.06):
    """One copper strip from x = 1 to 39 mm, ``width`` high, centred in the steady domain,
    meshed at ``size`` inside a background of mesh size 1000: the background's sides stay
    single long segments next to a fine mesh. 12 loop vertices."""
    doc = with_shapes([rect('heater', 1.0, 10.0 - width / 2, 38.0, width, 'copper', mesh_size=size)],
                      heat={'heater': 5e6})
    doc['geometry']['background']['mesh_size'] = 1000.0
    return doc


def thin_film(thickness=1e-7):
    """The steady example with a steel film 30 mm long and ``thickness`` thick added at
    y = 15 mm: 27 input points, far below every count limit, and far finer than any
    reasonable mesh."""
    doc = steady_example()
    doc['geometry']['shapes'].append(rect('film', 2.0, 15.0, 30.0, thickness))
    return doc


# ---- many shapes, circles or polygon points --------------------------------------------------

def spaced_rects(count=64):
    """``count`` 1 x 1 mm squares on a grid, none touching another or the domain sides."""
    cols = math.ceil(math.sqrt(2 * count))
    rows = math.ceil(count / cols)
    return with_shapes([rect(f'r{k}', (k % cols + 0.25) * 40.0 / cols, (k // cols + 0.25) * 20.0 / rows, 1.0, 1.0)
                        for k in range(count)])


def isolated_circles(count=16, r=0.6):
    """``count`` circles of radius ``r`` on a grid, clear of each other and of the sides,
    so each is meshed as an exact meshine Circle."""
    cols = 8
    rows = math.ceil(count / cols)
    return with_shapes([circle(f'c{k}', 2.5 + (k % cols) * 5.0, 1.5 + (k // cols) * 18.0 / rows, r)
                        for k in range(count)])


def circles_rects_polygon():
    """16 isolated circles, then 47 rects, then a regular 512-gon: exactly 64 shapes,
    16 circles and 512 polygon points."""
    shapes = [circle(f'c{k}', 2.5 + (k % 8) * 5.0, 2.0 + (k // 8) * 4.0, 0.6) for k in range(16)]
    shapes += [rect(f'r{k}', 1.0 + (k % 11) * 3.5, 10.0 + (k // 11) * 2.2, 2.0, 1.0) for k in range(47)]
    shapes.append(polygon('p0', regular_polygon(5.0, 7.5, 1.2, 512)))
    return with_shapes(shapes)


def tiny_global_size(size=0.0246):
    """The steady example with the background and the plate sized 2 mm and a tiny global
    ``mesh.size``. The heater is an isolated circle, and an isolated circle takes its vertex
    count from the global size, max(16, int(4 pi r / mesh.size)), even with its own
    ``mesh_size``; it is counted twice, as itself and as the plate's hole."""
    doc = steady_example(size)
    doc['geometry']['background']['mesh_size'] = 2.0
    doc['geometry']['shapes'][0]['mesh_size'] = 2.0
    return doc


def straddling_heaters(count=8, cy=11.0, r=0.8):
    """The steady example's plate with ``count`` heaters of radius ``r`` spread along
    x = 6.5 to 33.5 mm at height ``cy``. At the default cy they straddle the plate's top
    edge (y = 11 mm), so none is isolated: each is a 128-gon, counted as itself and as a
    hole in the plate or the background."""
    doc = steady_example()
    plate = doc['geometry']['shapes'][0]
    heaters = [circle(f'h{j}', 6.5 + j * 27.0 / max(count - 1, 1), cy, r) for j in range(count)]
    return with_shapes([plate, *heaters], heat={h['name']: 5e6 for h in heaters}, base=doc)


def rect_grid(nx=8, ny=8):
    """nx x ny rects that tile the steady domain exactly, edge to edge: every shared edge is
    a collinear overlap and every inner corner a touch, none a proper crossing."""
    w, h = 40.0 / nx, 20.0 / ny
    return with_shapes([rect(f'g{i}_{j}', i * w, j * h, w, h, 'steel' if (i + j) % 2 else 'copper')
                        for j in range(ny) for i in range(nx)])


def layer_strips(count=64, x0=2.0, x1=38.0, y0=2.0, y1=18.0):
    """``count`` strips stacked edge to edge from y0 to y1, each from x0 to x1.

    A valid document, but not one that runs: at the default 64 strips ``run`` fails
    galerkin's normalized component heat-balance check (it did before the mesh limits
    too; 16 and 32 strips run). Use it for counts and meshing, not as a run that succeeds."""
    h = (y1 - y0) / count
    return with_shapes([rect(f'layer{k}', x0, y0 + k * h, x1 - x0, h, 'steel' if k % 2 else 'copper')
                        for k in range(count)])


# ---- crossing boundaries ---------------------------------------------------------------------

def crossing_combs(k):
    """Two interlocking combs, each a polygon of 4k + 3 points: k horizontal teeth (steel)
    and k vertical teeth (copper). Every horizontal tooth crosses every vertical one, so the
    later comb cuts the earlier into about k^2 pieces and the loop vertices grow as k^2."""
    h = 18.0 / (2 * k)
    hcomb = [(1.0, 1.0)]
    for i in range(k):
        ya = 1.0 + 2 * i * h
        hcomb += [(2.0, ya), (39.0, ya), (39.0, ya + h), (2.0, ya + h)]
    hcomb += [(2.0, 19.0), (1.0, 19.0)]
    w = 36.0 / (2 * k)
    vcomb = [(38.5, 0.2), (38.5, 0.8)]
    for i in range(k - 1, -1, -1):
        xa = 2.5 + 2 * i * w
        vcomb += [(xa + w, 0.8), (xa + w, 19.5), (xa, 19.5), (xa, 0.8)]
    vcomb += [(2.5, 0.2)]
    return with_shapes([polygon('h', hcomb), polygon('v', vcomb, 'copper')])


def covered_crossings(teeth=126, front=58, box=(8.0, 32.0, 1.0, 19.0)):
    """Crossings hidden under covering shapes. ``front`` tiny rects near the origin come
    first; then two sawtooth polygons of 2 * teeth + 3 points each, one with its teeth
    across the box height and one across its width, so nearly every tooth edge of one
    crosses every tooth edge of the other; then 4 rects that cover the box, so none of the
    crossings is visible in the resolved geometry. At the defaults: 64 shapes, no circle,
    510 polygon points, and tens of thousands of crossings."""
    x0, x1, y0, y1 = box
    wa = (x1 - x0) / teeth
    across_height = [(x0, y0), (x1, y0)]
    for i in range(teeth, 0, -1):
        across_height += [(x0 + i * wa, y0 + 0.01), (x0 + (i - 0.5) * wa, y1)]
    across_height.append((x0, y0 + 0.01))
    hb = (y1 - y0) / teeth
    across_width = [(x0, y1), (x0, y0)]
    for i in range(teeth):
        across_width += [(x0 + 0.01, y0 + i * hb), (x1, y0 + (i + 0.5) * hb)]
    across_width.append((x0 + 0.01, y1))
    shapes = [rect(f'fr{j}', 0.1 + (j % 24) * 0.05, 0.1 + (j // 24) * 0.05, 0.02, 0.02) for j in range(front)]
    shapes += [polygon('gA', across_height), polygon('gB', across_width, 'copper')]
    xm, ym = 0.5 * (x0 + x1), 10.0
    shapes += [rect(f'cq{a}{b}', x0 - 0.5 if a == 0 else xm, 0.0 if b == 0 else ym,
                    xm - x0 + 0.5 if a == 0 else x1 - xm + 0.5, ym if b == 0 else 20.0 - ym)
               for a in (0, 1) for b in (0, 1)]
    return with_shapes(shapes)


def covered_crossings_with_circles(teeth=15, circles=16, r=1.2):
    """``covered_crossings`` with ``circles`` fewer front rects and, after the covering
    rects, ``circles`` identical circles of radius ``r`` at (1.5, 15) mm. Identical circles
    share every edge, which is a collinear overlap, not a crossing, so they add no
    boundary crossings but make each shape's boolean with the later ones costlier. At the
    defaults: 64 shapes, 16 circles, 66 polygon points, about a thousand crossings."""
    doc = covered_crossings(teeth=teeth, front=58 - circles)
    doc['geometry']['shapes'] += [circle(f'ic{k}', 1.5, 15.0, r) for k in range(circles)]
    return doc


def collinear_overlaps(rects=47, circles=16, points=512, y0=8.0, y1=12.0):
    """Boundaries that overlap without crossing: one polygon of ``points`` points whose
    bottom and top edges are split into collinear points on y = y0 and y1, ``rects``
    rects on the same two lines with staggered x, and ``circles`` identical circles. At
    the defaults: 64 shapes, 16 circles, 512 polygon points and no boundary crossing."""
    n = points // 2
    xs = [2.0 + 36.0 * i / (n - 1) for i in range(n)]
    shapes = [polygon('pa', [(x, y0) for x in xs] + [(x, y1) for x in reversed(xs)], 'copper')]
    shapes += [rect(f'r{k}', 3.0 + 0.3 * k, y0, 20.0, y1 - y0, 'steel' if k % 2 else 'copper')
               for k in range(rects)]
    shapes += [circle(f'c{k}', 20.0, 10.0, 2.0) for k in range(circles)]
    return with_shapes(shapes)


def concentric_rings(count=7, r0=1.0, dr=0.3, size=0.15, min_angle=33.0):
    """``count`` concentric circles in the steady domain, radii r0 + k dr, larger ones
    first, so that each later circle cuts an annulus out of the one before (every circle
    is a 128-gon), each with ``mesh_size`` ``size``, and ``min_angle``. At the defaults
    meshine's refinement does not finish within its 80 rounds before the node cap."""
    shapes = [circle(f'c{k}', 20.0, 10.0, r0 + (count - 1 - k) * dr, 'copper' if k % 2 else 'steel',
                     mesh_size=size) for k in range(count)]
    doc = with_shapes(shapes)
    doc['mesh']['min_angle'] = min_angle
    return doc


def chord_stars(polygons=8, rects='nested'):
    """``polygons`` polygons of ``512 // polygons`` points each, each a star whose every edge
    is a chord through the centre of the steady domain, so that nearly every pair of their
    edges crosses; 16 nested circles across them; rects filling the document to 64 shapes,
    ``'nested'`` (concentric frames), ``'plus'`` (alternately wide and tall bars, crossing
    pairwise) or ``'thin'`` (long thin bars across the domain). With ``polygons`` dividing
    512, exactly 64 shapes, 16 circles and 512 polygon points: the costliest layouts for
    counting boundary crossings that a search within those numbers found."""
    n = 512 // polygons

    def star(radius, phase):
        step = math.pi + math.pi / n                # each vertex nearly opposite the last
        return [(20.0 + radius * math.cos(phase + i * step), 10.0 + radius * math.sin(phase + i * step))
                for i in range(n)]
    shapes = [polygon(f'p{j}', star(9.5 - 0.01 * j, 0.003 * j)) for j in range(polygons)]
    shapes += [circle(f'c{q}', 20.0 + 0.05 * q, 10.0, 9.0 - 0.3 * q) for q in range(16)]
    count = 64 - 16 - polygons
    if rects == 'nested':
        shapes += [rect(f'r{q}', 11.0 + 0.1 * q, 1.0 + 0.05 * q, 18.0 - 0.2 * q, 18.0 - 0.1 * q) for q in range(count)]
    elif rects == 'plus':
        shapes += [rect(f'r{q}', 11.0 + 0.37 * q, 9.5 - 0.01 * q, 1.0 + 0.2 * q, 1.0 + 0.02 * q) if q % 2 else
                   rect(f'r{q}', 19.5 - 0.01 * q, 1.0 + 0.37 * q, 1.0 + 0.02 * q, 1.0 + 0.2 * q) for q in range(count)]
    elif rects == 'thin':
        shapes += [rect(f'r{q}', 1.0 + 0.01 * q, 1.0 + 0.37 * q, 38.0 - 0.02 * q, 0.01) for q in range(count)]
    else:
        raise ValueError(rects)
    return with_shapes(shapes)


def diagonal_fans(polygons=1, rects='thin'):
    """``polygons`` polygons of ``512 // polygons`` points each, each a zigzag between two
    opposite corners of the square [10, 30] x [0, 20], so that every edge's bounding box holds
    every circle; the 16 nested circles of ``chord_stars``; rects filling the document to 64
    shapes, ``'thin'`` (bars 0.01 high across the square) or ``'squares'`` (concentric
    squares). With ``polygons`` dividing 512, exactly 64 shapes, 16 circles and 512 polygon
    points: about twice as many segment pairs whose boxes meet as the chord stars, found when
    the work bound replaced the time bound in the region_complexity tests. Not a valid
    document (the zigzags intersect themselves)."""
    n = 512 // polygons

    def zigzag(j):
        points = []
        for i in range(n):
            a = (i * 0.6180339887498949 + j * 0.7548776662466927) % 1.0 * 0.5
            b = (i * 0.7548776662466927 + j * 0.5698402909980532) % 1.0 * 0.5
            points.append((10.0 + a, b + 0.001 * i) if i % 2 == 0 else (30.0 - a, 20.0 - b - 0.001 * i))
        return points
    shapes = [polygon(f'p{j}', zigzag(j)) for j in range(polygons)]
    shapes += [circle(f'c{q}', 20.0 + 0.05 * q, 10.0, 9.0 - 0.3 * q) for q in range(16)]
    count = 64 - 16 - polygons
    if rects == 'thin':
        shapes += [rect(f'r{q}', 10.0, 0.2 + 0.4 * q, 20.0, 0.01) for q in range(count)]
    elif rects == 'squares':
        shapes += [rect(f'r{q}', 11.0 + 0.18 * q, 1.0 + 0.18 * q, 18.0 - 0.36 * q, 18.0 - 0.36 * q) for q in range(count)]
    else:
        raise ValueError(rects)
    return with_shapes(shapes)


def corner_fans(polygons=8, rects='corner'):
    """``polygons`` polygons of ``512 // polygons`` points each, every other point the corner
    (10, 0) of the square [10, 30] x [0, 20] and the others near the opposite corner, so that
    every edge's bounding box holds every circle and every polygon edge meets every other at
    (10, 0); the 16 nested circles of ``chord_stars``; rects filling the document to 64
    shapes, ``'corner'`` (each with its lower-left corner at (10, 0)) or ``'squares'`` (those
    of ``diagonal_fans``). With ``polygons`` dividing 512, exactly 64 shapes, 16 circles and
    512 polygon points: a few more segment pairs whose boxes meet than the diagonal fans, and
    more pairs that meet, found by a review of the work bound in the region_complexity tests.
    Not a valid document (each polygon returns to the corner at every other point)."""
    n = 512 // polygons

    def fan(j):
        points = []
        for i in range(n):
            a = (i * 0.6180339887498949 + j * 0.7548776662466927) % 1.0
            b = (i * 0.7548776662466927 + j * 0.5698402909980532) % 1.0
            if i % 2 == 0:
                points.append((10.0, 0.0))
            elif a < 0.5:
                points.append((30.0 - 0.5 * a, 20.0 - 0.5 * b))
            else:
                points.append((30.0 - 0.5 * a + 0.25, 20.0 - 0.3 * a))
        return points
    shapes = [polygon(f'p{j}', fan(j)) for j in range(polygons)]
    shapes += [circle(f'c{q}', 20.0 + 0.05 * q, 10.0, 9.0 - 0.3 * q) for q in range(16)]
    count = 64 - 16 - polygons
    if rects == 'corner':
        shapes += [rect(f'r{q}', 10.0, 0.0, 20.0 - 0.3 * q, 20.0 - 0.25 * q) for q in range(count)]
    elif rects == 'squares':
        shapes += [rect(f'r{q}', 11.0 + 0.18 * q, 1.0 + 0.18 * q, 18.0 - 0.36 * q, 18.0 - 0.36 * q) for q in range(count)]
    else:
        raise ValueError(rects)
    return with_shapes(shapes)


def sawtooth(teeth=254, tip_angle_deg=None, jitter=0.0, seed=1, crossing_rects=0, rect_width=0.03,
             min_angle=None):
    """One sawtooth polygon of 2 * teeth + 3 points across the steady domain: a straight
    base at y = 4 mm and teeth from x = 2 to 38 mm whose tips reach y = 16 mm. At the
    default the valleys are at y = 8 mm, so each tip is about 1 degree; with
    ``tip_angle_deg`` the valleys rise until the tips have that angle. ``jitter`` moves
    every tooth point up or down by up to that fraction of the tooth height (seeded),
    ``crossing_rects`` thin vertical rects of ``rect_width`` cross the tooth band, and
    ``min_angle`` sets mesh.min_angle. Such inputs need very fine meshes near their tips."""
    x0, x1, ybase, yhi = 2.0, 38.0, 4.0, 16.0
    w = (x1 - x0) / teeth
    ylo = 8.0 if tip_angle_deg is None else yhi - (w / 2) / math.tan(math.radians(tip_angle_deg) / 2)
    points = [[x0, ybase], [x1, ybase]]
    for i in range(teeth, 0, -1):
        points += [[x0 + i * w, ylo], [x0 + (i - 0.5) * w, yhi]]
    points.append([x0, ylo])
    if jitter:
        rng = random.Random(seed)
        amplitude = jitter * (yhi - ylo)
        for point in points[3:-1]:
            point[1] += rng.uniform(-amplitude, amplitude)
    shapes = [polygon('saw', points)]
    for j in range(crossing_rects):
        shapes.append(rect(f'xr{j}', x0 + 0.37 + j * (36.0 - 0.8) / crossing_rects, ylo - 0.3, rect_width,
                           yhi - ylo + 0.6, 'copper'))
    doc = with_shapes(shapes)
    if min_angle is not None:
        doc['mesh']['min_angle'] = min_angle
    return doc


def crossing_stars(count=16, points=32, inner=6.0):
    """16 isolated circles first, then ``count`` stars of ``points`` points (radii 9 and
    ``inner`` mm) all centred in the steady domain and slightly rotated against each
    other, so that their edges cross pairwise: 32 shapes and 512 polygon points at the
    default."""
    slots = [(x, y) for x in (1.6, 4.8, 8.0, 32.0, 35.2, 38.4) for y in (2.5, 7.5, 12.5, 17.5)]
    shapes = [circle(f'pc{j}', x, y, 1.2) for j, (x, y) in enumerate(slots[:16])]
    for j in range(count):
        phase = j * 2 * math.pi / (points * count)
        star = [(20.0 + (9.0 if i % 2 == 0 else inner) * math.cos(phase + 2 * math.pi * i / points),
                 10.0 + (9.0 if i % 2 == 0 else inner) * math.sin(phase + 2 * math.pi * i / points))
                for i in range(points)]
        shapes.append(polygon(f'x{j}', star, 'steel' if j % 2 else 'copper'))
    return with_shapes(shapes)


# ---- small layouts that exercise the domain builder ------------------------------------------

def clipped_circle():
    """A circle cut by the right side of the domain (a polygon after clipping) beside an
    isolated one."""
    return with_shapes([circle('clipped', 39.0, 10.0, 2.0), circle('near', 33.0, 10.0, 2.0)])


def overlapped_circle():
    """A circle that a later rect overlaps: meshed as a 128-gon, not as a Circle."""
    return with_shapes([circle('c', 20.0, 10.0, 2.0), rect('bar', 19.0, 9.0, 6.0, 2.0)])


def split_background():
    """A rect across the full height splits the background into two parts."""
    return with_shapes([rect('wall', 18.0, 0.0, 4.0, 20.0), circle('c', 8.0, 10.0, 2.0)])
