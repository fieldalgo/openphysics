# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Steady heat documents with named material regions (EM-style geometry).

A thermal.steady2d document whose geometry has ``background``/``shapes`` takes
its conductivity from a ``materials`` table: every shape and the background
name a material, and every used material gives ``conductivity_w_mk``. The
mesh follows the region boundaries (meshine, ``mesh.size``). The rectangle
documents of thermal.py are not changed. See docs/packages/simcase/thermal_regions2d.md.
"""
import copy
from dataclasses import replace
import json
import math
import time

import numpy as np

from .schema import SHAPE_TYPES, DocumentError
from .thermal import PHYSICS, ThermalRunResult, _number, _object

RESULT_FORMAT = 'thermal.steady2d-regions-result-v1'
FIELD_LAYOUT = 'thermal2d-p1-node-cell-regions-v1'
SIDES = ('left', 'right', 'bottom', 'top')
#: the result identifiers of an axisymmetric run: full-revolution rates in W, never the
#: Cartesian per-metre identifiers (galerkin docs/packages/galerkin/thermal_axisymmetric.md)
AXISYMMETRIC_RESULT_FORMAT = 'thermal.axisymmetric-regions-result-v1'
AXISYMMETRIC_FIELD_LAYOUT = 'thermal-axisymmetric-p1-node-cell-regions-v1'
MATERIAL_KEYS = {'conductivity_w_mk', 'volumetric_heat_capacity_j_m3k', 'source'}
BOUNDARY_FIELDS = ('prescribed_outward_load_w_per_m', 'ambient_load_w_per_m',
                   'convective_outward_w_per_m', 'system_rhs_w_per_m')


def has_region_geometry(data, physics_type):
    """A document of physics_type that declares region geometry (exported by ``simcase``; Studio
    decides the region path with it)."""
    if not isinstance(data, dict) or not isinstance(data.get('physics'), dict):
        return False
    typed = any(isinstance(p, dict) and p.get('type') == physics_type for p in data['physics'].values())
    geometry = data.get('geometry')
    if not typed or not isinstance(geometry, dict):
        return False
    if 'version' in geometry:
        return _version_1_has_regions(geometry)
    return 'shapes' in geometry or 'background' in geometry


def _version_1_has_regions(geometry):
    """A raw version 1 block that Document.from_dict keeps as a 2D region component: its one
    component has features or a background material. A homogeneous rectangle (neither) is
    compiled to the 0.2 rectangle form at load and takes the rectangle path, as does a 3D
    component (cavity form). A block of another shape is left to the reader to refuse and
    counted as a region block, so the refusal names it."""
    components = geometry.get('components')
    if not isinstance(components, dict) or len(components) != 1:
        return True
    (component,) = components.values()
    if not isinstance(component, dict):
        return True
    if component.get('dimension') == '3d':
        return False
    background = component.get('background')
    features = component.get('features')
    return (isinstance(features, list) and bool(features)) or (isinstance(background, dict) and 'material' in background)


def is_region_thermal(data):
    """A steady heat document that declares region geometry."""
    return has_region_geometry(data, PHYSICS)


def _shape(s, i, names):
    where = f'geometry.shapes[{i}]'
    if not isinstance(s, dict) or s.get('type') not in SHAPE_TYPES:
        raise DocumentError(f'{where}: expected a rect, circle or polygon object')
    t = s['type']
    _object(s, {'type', 'name', 'material', 'mesh_size'} | SHAPE_TYPES[t], where)
    missing = ({'name', 'material'} | SHAPE_TYPES[t])-set(s)
    if missing:
        raise DocumentError(f'{where} ({t}): missing {sorted(missing)}')
    name = s['name']
    if not isinstance(name, str) or not name or name == 'background' or name in names:
        raise DocumentError(f'{where}.name: expected a unique nonempty string other than "background"')
    names.add(name)
    if not isinstance(s['material'], str) or not s['material']:
        raise DocumentError(f'{where}.material: expected a material name')
    if 'mesh_size' in s:
        _number(s['mesh_size'], f'{where}.mesh_size', positive=True)
    if t == 'polygon':
        points = s['points']
        if not isinstance(points, list) or len(points) < 3:
            raise DocumentError(f'{where}.points: expected at least three [x, y] points')
        for j, point in enumerate(points):
            if not isinstance(point, list) or len(point) != 2:
                raise DocumentError(f'{where}.points[{j}]: expected [x, y]')
            for value in point:
                _number(value, f'{where}.points[{j}]')
        from shapely.geometry import Polygon
        if not Polygon([tuple(p) for p in points]).is_valid:
            raise DocumentError(f'{where}.points: polygon must not self-intersect')
    else:
        for key in SHAPE_TYPES[t]:
            _number(s[key], f'{where}.{key}', positive=key in ('w', 'h', 'r'))


def is_axisymmetric(doc):
    """A version 1 document whose component is axisymmetric: its mesh is (r, z)."""
    return bool(getattr(doc, 'is_version_1', False)) and doc.component.dimension == 'axisymmetric'


def exterior_sides(doc):
    """The mesh tags of the domain sides of this document, and those that may carry data.

    A 2D document has the four sides. An axisymmetric document whose domain starts at
    r = 0 has ``axis`` in place of ``left``; the axis is the symmetry axis, which carries
    natural regularity and no Dirichlet, flux or convection data (galerkin rejects them),
    so it is a side of the mesh but not a side a document may name. An annulus (xmin > 0)
    keeps ``left`` as a physical side."""
    if is_axisymmetric(doc) and doc.domain['xmin'] == 0:
        return ('axis', 'right', 'bottom', 'top'), ('right', 'bottom', 'top')
    return SIDES, SIDES


def boundary_names(doc):
    """The boundary names a region heat document may give data to, beyond its domain sides.

    A version 1 document adds the exterior mesh tags its complex declares (a ``boundary_tags``
    name, ``outer`` on the border of a void feature or a sliver gap) and its boundary
    selections. Returns ``(tags, exterior_selections, interior_selections)``; a selection is
    exterior when every curve it holds borders the exterior (the domain or a void), interior
    otherwise. Data may name the tags and the exterior selections; an interior selection is
    refused by name (galerkin fixes and loads exterior nodes only). A 0.2 document has none. An
    unnamed exterior boundary is insulated (HQ decision 2026-11-08: a void border is insulated
    unless named)."""
    if not getattr(doc, 'is_version_1', False):
        return set(), set(), set()
    rc = doc.complex()
    exterior = set(rc.exterior_curves())
    # "outer" is always declared: a sliver gap, left out of the mesh at the hand-off, gets it
    # too; a name without mesh edges is refused by name at mesh time
    tags = ({rc.curves[i].tag for i in exterior} | {'outer'}) - set(SIDES) - {'axis'}
    outside, inside = set(), set()
    for name, (kind, chosen) in rc.selections.items():
        if kind != 'boundary':
            continue
        (outside if set(chosen) <= exterior else inside).add(name)
    return tags, outside, inside


def void_area_m2(doc):
    """The area of a version 1 document's void cells in square metres (holes in the mesh)."""
    if not getattr(doc, 'is_version_1', False):
        return 0.0
    rc = doc.complex()
    pm_per_m = float(doc._pm_per_unit()) / float(doc.scale.to_si(1.0, {'length': 1}))   # pm per unit / m per unit
    return sum(c.area for c in rc.cells if c.void) / pm_per_m ** 2


def _sides(p, name, allowed=SIDES, names=(set(), set(), set())):
    path = f'physics.{name}'
    tags, outside, inside = names
    dirichlet_ok = flux_ok = set(allowed) | tags | outside
    bc = p.get('dirichlet_temperature_k', {})
    _named_sides(bc, dirichlet_ok, path+'.dirichlet_temperature_k', inside)
    for tag, value in bc.items():
        _number(value, f'{path}.dirichlet_temperature_k.{tag}', nonnegative=True)
    for a in ('left', 'right'):
        for b in ('bottom', 'top'):
            if a in bc and b in bc and bc[a] != bc[b]:
                raise DocumentError(f'{path}.dirichlet_temperature_k: conflicting corner temperatures on {a}/{b}')
    flux = p.get('outward_flux_w_m2', {})
    _named_sides(flux, flux_ok, path+'.outward_flux_w_m2', inside)
    for tag, value in flux.items():
        _number(value, f'{path}.outward_flux_w_m2.{tag}')
    robin = p.get('convection', {})
    _named_sides(robin, flux_ok, path+'.convection', inside)
    anchored = False
    for tag, value in robin.items():
        where = f'{path}.convection.{tag}'
        _object(value, {'h_w_m2k', 'ambient_temperature_k'}, where)
        if set(value) != {'h_w_m2k', 'ambient_temperature_k'}:
            raise DocumentError(f'{where}: needs h_w_m2k and ambient_temperature_k')
        _number(value['h_w_m2k'], where+'.h_w_m2k', nonnegative=True)
        _number(value['ambient_temperature_k'], where+'.ambient_temperature_k', nonnegative=True)
        anchored |= value['h_w_m2k'] > 0
    if not bc and not anchored:
        raise DocumentError(f'{path}: requires Dirichlet or positive Robin anchor; pure Neumann unsupported')
    if set(bc) & (set(flux) | set(robin)):
        raise DocumentError(f'{path}: natural condition overlaps a fully Dirichlet side')


def region_geometry(doc):
    """Validate geometry.domain/background/shapes; return the shape names."""
    d = doc.data
    g = d['geometry']
    if doc.is_version_1:
        return _version_1_region_geometry(doc)
    _object(g, {'domain', 'background', 'shapes'}, 'geometry')
    dom = g.get('domain')
    _object(dom, {'xmin', 'xmax', 'ymin', 'ymax'}, 'geometry.domain')
    if set(dom) != {'xmin', 'xmax', 'ymin', 'ymax'}:
        raise DocumentError('geometry.domain needs xmin, xmax, ymin, ymax')
    for key, value in dom.items():
        _number(value, f'geometry.domain.{key}')
        _number(doc.scale.to_si(value, {'length': 1}), f'geometry.domain.{key} in metres')
    for axis in 'xy':
        _number(dom[axis+'max']-dom[axis+'min'], f'geometry.domain.{axis} extent', positive=True)
    background = g.get('background')
    _object(background, {'material', 'mesh_size'}, 'geometry.background')
    if not isinstance(background.get('material'), str) or not background['material']:
        raise DocumentError('geometry.background.material: expected a material name')
    if 'mesh_size' in background:
        _number(background['mesh_size'], 'geometry.background.mesh_size', positive=True)
    shapes = g.setdefault('shapes', [])
    if not isinstance(shapes, list):
        raise DocumentError('geometry.shapes: expected a list')
    names = set()
    for i, s in enumerate(shapes):
        _shape(s, i, names)
    refuse_dropped_shapes(doc)
    return names


def _version_1_region_geometry(doc):
    """The region checks of a version 1 block: the reader has checked the geometry itself;
    here the domain must be finite in metres, the background needs a material, a void feature
    (``material: null``) is a hole whose border is an exterior boundary (insulated unless named,
    HQ decision 2026-11-08), and a feature that the domain cuts away or that is a sliver is
    refused by name, as a dropped 0.2 shape is. A feature that later features cover is not.
    Returns the names of the material regions."""
    dom = doc.domain
    for key, value in dom.items():
        _number(doc.scale.to_si(value, {'length': 1}), f'geometry.domain.{key} in metres')
    if not isinstance(doc.background.get('material'), str) or not doc.background['material']:
        raise DocumentError('geometry.background.material: expected a material name (region heat takes no void '
                            'background)')
    names = {r['name'] for r in doc.regions() if r['material'] is not None}
    from .geometry import dropped_features
    dropped = dropped_features(doc)
    if dropped:
        raise DocumentError(' '.join(dropped) + ' A heat region document refuses a feature that contributes no '
                            'material.')
    return names


def refuse_dropped_shapes(doc):
    """Refuse a named shape that lies outside the domain or below the sliver limit.

    geometry.resolve_regions drops such a shape and leaves a note in doc.notes, which
    no run log prints (electromagnetic documents drop it the same way). A heat region
    document would then run without that material and say nothing, so the note
    becomes an error here. A shape that
    later shapes cover completely is not refused ("later wins"); the run log names it.
    """
    from .geometry import resolve_regions
    saved, doc.notes = doc.notes, []
    try:
        resolve_regions(doc)
        dropped = list(doc.notes)
    finally:
        doc.notes = saved
    if dropped:
        raise DocumentError(' '.join(dropped)+' A heat region document refuses a shape that '
                            'contributes no material.')


def covered_shapes(doc, mesh):
    """Shapes with no triangles in the mesh: fully covered by later shapes (a void region is
    never meshed and is not listed)."""
    return [s['name'] for s in doc.regions() if s['material'] is not None and s['name'] not in mesh.region_names]


def region_materials_table(doc, required, label):
    """Validate the materials table; every used material needs the `required` keys."""
    d = doc.data
    materials = d['materials']
    if not isinstance(materials, dict):
        raise DocumentError('materials: expected an object mapping names to thermal properties')
    for mname, spec in materials.items():
        where = f'materials.{mname}'
        _object(spec, MATERIAL_KEYS, where)
        if 'conductivity_w_mk' in spec:
            _number(spec['conductivity_w_mk'], where+'.conductivity_w_mk', positive=True)
        if 'volumetric_heat_capacity_j_m3k' in spec:
            _number(spec['volumetric_heat_capacity_j_m3k'], where+'.volumetric_heat_capacity_j_m3k', positive=True)
        if 'source' in spec and not isinstance(spec['source'], str):
            raise DocumentError(where+'.source: expected a string')
    for where, mname in [('geometry.background.material', doc.background['material'])] + [
            (f'geometry.shapes[{i}].material' if not doc.is_version_1 else f'region {s["name"]!r}', s['material'])
            for i, s in enumerate(doc.regions()) if s['material'] is not None]:
        if mname not in materials:
            raise DocumentError(f'{where}: material {mname!r} is not defined in materials '
                                '(thermal properties are never taken from built-in optical materials)')
        for key in required:
            if key not in materials[mname]:
                raise DocumentError(f'materials.{mname}.{key}: required by {label}')


def region_source(p, names, path):
    """Validate heat_source_w_m3: a number or {region name: number}; default zero."""
    source = p.setdefault('heat_source_w_m3', 0.0)
    if isinstance(source, dict):
        allowed = names | {'background'}
        for region, value in source.items():
            if region not in allowed:
                raise DocumentError(f'{path}.heat_source_w_m3.{region}: no shape or background of that name')
            _number(value, f'{path}.heat_source_w_m3.{region}')
    else:
        _number(source, f'{path}.heat_source_w_m3')


def _named_sides(value, allowed, path, interior=()):
    """``_object`` over the boundary names a document may give this data to; the axis, a left
    side at r = 0 and an interior selection given flux or convection are refused by name."""
    if isinstance(value, dict) and 'axis' in value and 'axis' not in allowed:
        raise DocumentError(f"{path}.axis: 'axis' is the symmetry axis of an axisymmetric component; it carries "
                            "natural regularity and takes no Dirichlet, flux or convection data")
    if isinstance(value, dict) and 'left' in value and 'left' not in allowed:
        raise DocumentError(f"{path}.left: an axisymmetric component whose domain starts at r = 0 has no left "
                            "side; its r = 0 side is the axis")
    if isinstance(value, dict):
        for key in value:
            if key in interior and key not in allowed:
                raise DocumentError(f"{path}.{key}: selection {key!r} lies on an interface between two regions; "
                                    "boundary data applies to exterior boundaries only (galerkin fixes and loads "
                                    "exterior nodes)")
    _object(value, allowed, path)


def region_mesh_settings(doc):
    mesh = doc.data['mesh']
    _object(mesh, {'size', 'min_angle', 'controls'}, 'mesh')   # controls: Document.check_mesh_controls
    if 'size' not in mesh:
        raise DocumentError('mesh.size: required by a region document (document length units)')
    _number(mesh['size'], 'mesh.size', positive=True)
    angle = mesh.setdefault('min_angle', 28.0)
    _number(angle, 'mesh.min_angle', positive=True)
    if angle > 33.0:
        raise DocumentError('mesh.min_angle: at most 33 degrees (refinement need not terminate above)')


def validate_region_thermal(doc):
    d = doc.data
    _object(d, {'openphysics', 'name', 'units', 'geometry', 'materials', 'physics', 'mesh', 'study', 'results'},
            'document')
    if not isinstance(d['name'], str):
        raise DocumentError('name: expected a string')
    name, p = doc.sole_physics()
    if not isinstance(name, str) or not name.isidentifier():
        raise DocumentError('physics name must be an identifier')
    path = f'physics.{name}'
    if 'conductivity_w_mk' in p:
        raise DocumentError(f'{path}.conductivity_w_mk: a region document takes conductivity from materials')
    _object(p, {'type', 'heat_source_w_m3', 'dirichlet_temperature_k', 'outward_flux_w_m2', 'convection'}, path)
    _object(d.get('units'), {'length', 'temperature'}, 'units')
    if 'length' not in doc.scale.declared or d['units'].get('temperature') != 'K':
        raise DocumentError('thermal.steady2d requires explicit units.length and units.temperature="K"')
    names = region_geometry(doc)
    region_materials_table(doc, ('conductivity_w_mk',), 'steady heat')
    region_source(p, names, path)
    _sides(p, name, exterior_sides(doc)[1], boundary_names(doc))
    region_mesh_settings(doc)
    if d['study'] != {'type': 'single'}:
        raise DocumentError('thermal.steady2d supports only study {"type":"single"}')
    _object(d['results'], {'save_fields', 'plots'}, 'results')
    if not isinstance(d['results'].get('save_fields'), bool) or not isinstance(d['results'].get('plots'), bool):
        raise DocumentError('results.save_fields and results.plots must be booleans')
    if d['results']['plots']:
        raise DocumentError('results.plots: thermal.steady2d is headless; plots=true is not supported')
    doc.notes = []


def region_summary(doc):
    name, p = doc.sole_physics()
    lines = [f'{doc["name"]} (openphysics 0.2)',
             f'  physics {name}: {PHYSICS}, single steady heat, named material regions',
             f'  domain {doc.domain} {doc.length_unit}; mesh size {doc["mesh"]["size"]} {doc.length_unit}',
             f'  background: {doc.background["material"]}']
    for s in doc.regions():
        lines.append(f'  shape {s["name"]}: {s["type"]}, {s["material"] if s["material"] is not None else "void (hole)"}')
    for mname, spec in doc['materials'].items():
        lines.append(f'  material {mname}: k={spec.get("conductivity_w_mk")} W/(m K)')
    rate = 'W (full revolution; axisymmetric (r, z))' if is_axisymmetric(doc) else 'W/m of depth'
    lines += [f'  Q={p["heat_source_w_m3"]} W/m^3',
              f'  Dirichlet {p.get("dirichlet_temperature_k", {})} K; other exterior insulated unless flux/convection given',
              f'  output: coordinates m, temperature K, flux W/m^2, nodal heat {rate}, triangle regions']
    return '\n'.join(lines)


def build_region_mesh(doc, limits=None):
    """meshine mesh in SI metres with named regions and box-side tags.

    ``limits`` (simcase.mesh_limits._MeshLimits) bounds the loop vertices of the micrometre
    document that is meshed before meshine builds its domain, passes max_nodes to meshine
    as max_points, and compares the exact node and triangle counts after meshing; each
    check whose limit is None is skipped, and without limits the mesh is made exactly as
    before."""
    from galerkin.mesh import Mesh
    from meshine import generate
    from .geometry import build_domain, size_function
    from .runner import micrometre_document
    from . import units
    canonical = micrometre_document(doc)
    if limits is None:
        domain, namer, region_materials = build_domain(canonical)
        tri = generate(domain, namer, min_angle=float(doc['mesh']['min_angle']), **_grading(canonical))
    else:
        tri, region_materials = _limited_mesh(canonical, limits, generate)
    doc.notes.extend(note for note in canonical.notes
                     if note.startswith(('geometry.', 'mesh.controls:')) and note not in doc.notes)
    if tri.num_triangles == 0:
        raise DocumentError('meshing produced no triangles; check mesh.size against the domain')
    sides = set(exterior_sides(doc)[0])
    declared = sides | boundary_names(doc)[0]
    tags = set(tri.boundary_edges)
    # a side that borders a void feature only has no mesh edge and is absent; a tag the
    # geometry does not declare is a defect of the hand-off
    if not tags <= declared or (not doc.is_version_1 and tags != sides):
        raise DocumentError(f'mesh: exterior edges must lie on the domain sides {sorted(sides)} and the boundaries '
                            f'the geometry declares {sorted(declared - sides)}; found tags {sorted(tags)}')
    if limits is not None:
        from .mesh_limits import MeshLimitError
        if limits.max_nodes is not None and tri.num_nodes > limits.max_nodes:
            raise MeshLimitError('nodes', limits.max_nodes, int(tri.num_nodes))
        if limits.max_triangles is not None and tri.num_triangles > limits.max_triangles:
            raise MeshLimitError('triangles', limits.max_triangles, int(tri.num_triangles))
    # Convert the canonical mesh directly to SI, never through document units.
    from .geometry import provenance_edges_of, selection_edges_of
    boundary = {k: np.asarray(v) for k, v in tri.boundary_nodes.items()}
    boundary_edges = {k: np.asarray(v) for k, v in tri.boundary_edges.items()}
    selections = selection_edges_of(canonical, tri)
    if selections:
        # a boundary selection names its nodes for Dirichlet data; an exterior one also tags its
        # edges for flux and convection, beside the side or outer tag the same edges carry
        _tags, outside, _inside = boundary_names(doc)
        for name, edges in selections.items():
            if name not in outside or len(edges) == 0:
                continue                                  # interior, or without a mesh edge: no data
            if name in boundary or name in boundary_edges:
                raise DocumentError(f'selection {name!r} shares its name with a mesh tag')
            boundary[name] = np.unique(np.asarray(edges, dtype=int))
            boundary_edges[name] = np.asarray(edges, dtype=int).reshape(-1, 2)
    mesh = Mesh(np.asarray(tri.nodes, dtype=float)*units.UM_IN_SI, tri.triangles,
                boundary=boundary, boundary_edges=boundary_edges,
                regions=np.asarray(tri.regions), region_names=list(tri.region_names),
                provenance_edges=provenance_edges_of(canonical, tri), selection_edges=selections)
    region_materials = {r: region_materials[r] for r in mesh.region_names}
    # Keep the diagnostic triangulation in document units, as before.
    tri = replace(tri, nodes=units.lengths_from_micrometres(tri.nodes, doc.scale))
    return mesh, region_materials, tri


def _grading(canonical):
    """meshine's ``size_fn`` keyword for a version 1 document's distance gradings, after its
    domain is built; empty otherwise, so a 0.2 document's call is exactly as before."""
    from .geometry import size_function
    size_fn = size_function(canonical)
    return {} if size_fn is None else {'size_fn': size_fn}


def _limited_mesh(doc, limits, generate):
    """(meshine mesh, region materials) of the micrometre document ``doc`` under ``limits``:
    the loop vertices are counted before Domain.build, and max_points is passed only when
    max_nodes is set, so meshine otherwise keeps its own default cap."""
    from .geometry import _domain_from_regions, size_function
    from .mesh_limits import MeshLimitError
    domain, namer, region_materials, _count = _domain_from_regions(
        doc, max_input_vertices=limits.max_input_vertices)
    grading = _grading(doc)
    if limits.max_nodes is None:
        return generate(domain, namer, min_angle=float(doc['mesh']['min_angle']), **grading), region_materials
    from meshine import MeshSizeLimitError     # here: an older meshine fails only limited runs
    try:
        tri = generate(domain, namer, min_angle=float(doc['mesh']['min_angle']), max_points=limits.max_nodes,
                       **grading)
    except MeshSizeLimitError as exc:
        raise MeshLimitError('nodes', limits.max_nodes) from exc
    return tri, region_materials


def region_inputs(doc, mesh, region_materials):
    """solve_steady_heat keyword arguments for a meshed region document."""
    name, p = doc.sole_physics()
    path = f'physics.{name}'
    materials = doc['materials']
    conductivity = {r: float(materials[m]['conductivity_w_mk']) for r, m in region_materials.items()}
    source = p['heat_source_w_m3']
    if isinstance(source, dict):
        dropped = set(source)-set(mesh.region_names)
        if dropped:
            raise DocumentError(f'{path}.heat_source_w_m3: regions {sorted(dropped)} are not in the meshed '
                                'geometry (fully covered by later shapes or smaller than the sliver limit)')
        source = {r: float(source.get(r, 0.0)) for r in mesh.region_names}
    else:
        source = float(source)
    prescribed = {}
    for label in ('dirichlet_temperature_k', 'outward_flux_w_m2', 'convection'):
        for tag in p.get(label, {}):
            if tag not in mesh.boundary_edges:
                raise DocumentError(f'{path}.{label}.{tag}: no mesh edge lies on {tag!r} (a side or boundary that '
                                    'borders a void feature only, or a selection whose curves are inside the mesh)')
    for tag, value in p.get('dirichlet_temperature_k', {}).items():
        for node in mesh.boundary[tag]:
            if int(node) in prescribed and prescribed[int(node)] != value:
                raise DocumentError(f'{path}: conflicting corner temperature at node {node}')
            prescribed[int(node)] = float(value)
    flux = {tag: float(v) for tag, v in p.get('outward_flux_w_m2', {}).items()}
    convection = {tag: (float(v['h_w_m2k']), float(v['ambient_temperature_k']))
                  for tag, v in p.get('convection', {}).items()}
    _refuse_doubled_edges(mesh, path, flux, convection, p.get('dirichlet_temperature_k', {}))
    return dict(conductivity=conductivity, dirichlet=dict(sorted(prescribed.items())),
                heat_source=source, outward_flux=flux, convection=convection)


RATE_FIELDS = ('load_w_per_m', 'reaction_w_per_m', 'residual_w_per_m') + BOUNDARY_FIELDS


def _axisymmetric_name(key):
    """The field name of a full-revolution rate: ``load_w_per_m`` becomes ``load_w``."""
    return key[:-len('_per_m')] if key.endswith('_w_per_m') else key


def _refuse_doubled_edges(mesh, path, flux, convection, dirichlet):
    """A mesh edge may carry one flux and one convection entry: a side tag and an exterior
    selection on the same edges, both given data, would apply it twice."""
    def edge_sets(tags):
        return {tag: {tuple(sorted(map(int, e))) for e in np.asarray(mesh.boundary_edges[tag]).reshape(-1, 2)}
                for tag in tags}
    for label, table in (('outward_flux_w_m2', flux), ('convection', convection)):
        edges = edge_sets(table)
        names = sorted(edges)
        for i, a in enumerate(names):
            for b in names[i + 1:]:
                if edges[a] & edges[b]:
                    raise DocumentError(f'{path}.{label}: {a!r} and {b!r} share mesh edges; give that boundary '
                                        'one entry')
    # a natural condition on a fully Dirichlet edge is refused by the solver; here by name,
    # for a side tag and a selection that carry the same edges (names alone are checked at load)
    fixed = edge_sets(dirichlet)
    for label, table in (('outward_flux_w_m2', flux), ('convection', convection)):
        for a, e in edge_sets(table).items():
            for b, f in fixed.items():
                if a != b and e & f:
                    raise DocumentError(f'{path}.{label}.{a}: {a!r} shares mesh edges with the Dirichlet boundary '
                                        f'{b!r}; a natural condition does not apply on a Dirichlet edge')


class RegionThermalRunResult(ThermalRunResult):
    """ThermalRunResult with triangle regions and the boundary load fields."""

    def __post_init__(self):
        self.doc = self.doc.copy()
        self.doc.validate()
        self._document_json = self._canonical_document()
        self._nodes_snapshot = np.array(self.mesh.nodes, copy=True)
        self._triangles_snapshot = np.array(self.mesh.triangles, copy=True)
        self._fixed_snapshot = np.array(self.dirichlet_node_ids, copy=True)
        self._temperature_snapshot = np.array(self.dirichlet_temperature_k, copy=True)
        self._regions_snapshot = np.array(self.mesh.regions, copy=True)
        self._names_snapshot = list(self.mesh.region_names)
        self._result_format, self._field_layout = RESULT_FORMAT, FIELD_LAYOUT

    @property
    def boundary_enabled(self):
        return True

    @property
    def triangle_regions(self):
        return self.mesh.regions

    @property
    def region_names(self):
        return list(self.mesh.region_names)

    def _raw_arrays(self):
        if (not np.array_equal(self.mesh.regions, self._regions_snapshot)
                or list(self.mesh.region_names) != self._names_snapshot):
            raise ValueError('thermal result regions changed after the solve')
        arrays = super()._raw_arrays()
        regions = np.asarray(self.mesh.regions)
        if (regions.shape != (len(arrays['triangles']),) or regions.dtype.kind not in 'iu'
                or np.any(regions < 0) or np.any(regions >= len(self._names_snapshot))):
            raise ValueError('thermal triangle_regions: expected one valid region id per triangle')
        arrays['triangle_regions'] = regions.astype(np.int64)
        return arrays

    def summary(self):
        arrays = self._raw_arrays()
        name, p = self.doc.sole_physics()
        units = {'nodes_m': 'm', 'triangles': '1', 'triangle_regions': '1', 'dirichlet_node_ids': '1',
                 'dirichlet_temperature_k': 'K', 'temperature_k': 'K', 'heat_flux_w_m2': 'W/m^2',
                 'load_w_per_m': 'W/m', 'reaction_w_per_m': 'W/m', 'residual_w_per_m': 'W/m'}
        units.update({key: 'W/m' for key in BOUNDARY_FIELDS})
        locations = {key: 'nodes' for key in units}
        locations.update(triangles='triangle_connectivity', triangle_regions='triangles',
                         dirichlet_node_ids='dirichlet_nodes', dirichlet_temperature_k='dirichlet_nodes',
                         heat_flux_w_m2='triangle_centroids')
        k = self.mesh.by_region({r: self.doc['materials'][m]['conductivity_w_mk']
                                 for r, m in self.region_materials.items()})
        areas = self.mesh.areas()
        result = {'name': self.doc['name'], 'physics_name': name, 'physics_type': PHYSICS,
                  'result_format': self.result_format, 'field_layout': self.field_layout,
                  'units': copy.deepcopy(self.doc['units']), 'mesh_length_unit': 'm',
                  'field_units': units, 'field_locations': locations,
                  'field_shapes': {key: list(a.shape) for key, a in arrays.items()},
                  'region_names': self.region_names,
                  'regions': {r: {'material': self.region_materials[r],
                                  'triangles': int(np.sum(self.mesh.regions == i)),
                                  'area_m2': float(areas[self.mesh.regions == i].sum())}
                              for i, r in enumerate(self.region_names)},
                  'materials': copy.deepcopy(self.doc['materials']),
                  'reaction_sign': 'inward thermostat contribution; thermostat outward = -sum(reaction)',
                  'outward_sign': 'total outward = sum(prescribed_outward_load + convective_outward - reaction)',
                  'load_definition': 'source only; system_rhs = load + ambient_load - prescribed_outward_load',
                  'mesh': {'nodes': len(self.mesh.nodes), 'triangles': len(self.mesh.triangles),
                           'size': self.doc['mesh']['size'], 'min_angle_deg': self.doc['mesh']['min_angle'],
                           'size_unit': self.doc.length_unit},
                  'study': {'type': 'single'},
                  'heat_source_w_m3': copy.deepcopy(p['heat_source_w_m3']),
                  'dirichlet_temperature_k': dict(p.get('dirichlet_temperature_k', {})),
                  'outward_flux_w_m2': copy.deepcopy(p.get('outward_flux_w_m2', {})),
                  'convection': copy.deepcopy(p.get('convection', {})),
                  'dirichlet_nodes': len(self.dirichlet_node_ids),
                  'conductivity_range_w_mk': [float(k.min()), float(k.max())],
                  'temperature_min_k': float(self.temperature_k.min()),
                  'temperature_max_k': float(self.temperature_k.max()),
                  **self.diagnostics, 'timings_s': dict(self.timings)}
        json.dumps(result, allow_nan=False)
        return result


class AxisymmetricRegionThermalRunResult(RegionThermalRunResult):
    """The result of an axisymmetric run: the same arrays with the nodal rates in W over the
    full revolution, under their own result identifiers and ``_w`` field names. The inherited
    ``_w_per_m`` properties return the same arrays (the public read path of ThermalRunResult);
    the saved fields and the summary carry the ``_w`` names and the unit W only."""

    def __post_init__(self):
        super().__post_init__()
        self._result_format, self._field_layout = AXISYMMETRIC_RESULT_FORMAT, AXISYMMETRIC_FIELD_LAYOUT

    @property
    def load_w(self): return self.solution.load

    @property
    def reaction_w(self): return self.solution.reaction

    @property
    def residual_w(self): return self.solution.residual

    @property
    def prescribed_outward_load_w(self): return self.solution.prescribed_outward_load

    @property
    def ambient_load_w(self): return self.solution.ambient_load

    @property
    def convective_outward_w(self): return self.solution.convective_outward

    @property
    def system_rhs_w(self): return self.solution.system_rhs

    def _raw_arrays(self):
        arrays = super()._raw_arrays()
        return {_axisymmetric_name(key): a for key, a in arrays.items()}

    def summary(self):
        result = super().summary()
        for table in ('field_units', 'field_locations'):
            result[table] = {_axisymmetric_name(key): ('W' if key in RATE_FIELDS and table == 'field_units' else v)
                             for key, v in result[table].items()}
        result['coordinate_system'] = 'axisymmetric'
        result['nodal_heat_rate_unit'] = 'W'
        result['coordinates'] = '(r, z) in metres; volume measure 2*pi*r dr dz, full revolution'
        json.dumps(result, allow_nan=False)
        return result


def run_region_thermal(doc, verbose=True, *, mesh_limits=None):
    from galerkin.thermal import solve_steady_heat
    doc.validate()
    given, doc = doc, doc.copy()
    doc.validate()
    name, _ = doc.sole_physics()
    t0 = time.perf_counter()
    mesh, region_materials, tri = build_region_mesh(doc, mesh_limits)
    # the hand-off's notes (slivers left out, raised circle counts) reach the caller's document
    given.notes.extend(n for n in doc.notes if n.startswith(('geometry.', 'mesh.controls:')) and n not in given.notes)
    kwargs = region_inputs(doc, mesh, region_materials)
    t_mesh = time.perf_counter()-t0
    calculation_json = json.dumps(doc.data, sort_keys=True, separators=(',', ':'), allow_nan=False)
    axisymmetric = is_axisymmetric(doc)
    t0 = time.perf_counter()
    try:
        solution = solve_steady_heat(mesh, **kwargs, coordinate_system='axisymmetric' if axisymmetric else 'cartesian')
    except (ValueError, RuntimeError) as exc:
        raise ValueError(f'physics.{name} ({PHYSICS}): {exc}') from exc
    t_solve = time.perf_counter()-t0
    if json.dumps(doc.data, sort_keys=True, separators=(',', ':'), allow_nan=False) != calculation_json:
        raise ValueError('thermal calculation inputs changed during the solve')
    fixed = np.array(list(kwargs['dirichlet']), dtype=int)
    G, C = solution.prescribed_outward_load, solution.convective_outward
    source_heat = float(solution.load.sum())
    outward = float(G.sum())+float(C.sum())-float(solution.reaction.sum())
    scale = max(float(sum(np.sum(abs(a)) for a in (solution.load, solution.reaction, G, C))),
                np.finfo(float).tiny)
    free = np.setdiff1d(np.arange(mesh.num_nodes), fixed)
    rate = 'w' if axisymmetric else 'w_per_m'
    diagnostics = {f'source_heat_{rate}': source_heat,
                   f'prescribed_outward_heat_{rate}': float(G.sum()),
                   f'convective_outward_heat_{rate}': float(C.sum()),
                   f'thermostat_outward_heat_{rate}': -float(solution.reaction.sum()),
                   f'outward_heat_{rate}': outward,
                   f'heat_balance_defect_{rate}': outward-source_heat,
                   'normalized_heat_balance_defect': abs(outward-source_heat)/scale,
                   f'free_residual_max_{rate}': float(np.max(abs(solution.residual[free]))) if len(free) else 0.,
                   'mesh_min_angle_deg': float(tri.min_angle())}
    log = [region_summary(doc),
           f'mesh: {mesh.num_nodes} nodes, {len(mesh.triangles)} triangles, regions {mesh.region_names}',
           *([f'shapes fully covered by later shapes (no triangles): {covered_shapes(doc, mesh)}']
             if covered_shapes(doc, mesh) else []),
           f'temperature K: {solution.temperature.min():.12g} to {solution.temperature.max():.12g}',
           (f'source {source_heat:.12g} W; signed outward {outward:.12g} W (full revolution)' if axisymmetric
            else f'source {source_heat:.12g} W/m; signed outward {outward:.12g} W/m of depth')]
    if verbose:
        print('\n'.join(log))
    cls = AxisymmetricRegionThermalRunResult if axisymmetric else RegionThermalRunResult
    result = cls(doc, mesh, solution, fixed, np.array([kwargs['dirichlet'][int(i)] for i in fixed], dtype=float),
                 diagnostics, {'mesh': t_mesh, 'solve': t_solve}, log)
    result.region_materials = region_materials
    result.summary()
    return result
