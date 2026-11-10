# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Steady heat documents with named material regions (EM-style geometry).

A thermal.steady2d document whose geometry has ``background``/``shapes`` (or a version 1
component with features or a background material) takes its conductivity from a
``materials`` table: every shape and the background name a material, and every used
material gives ``thermal_conductivity``. The mesh follows the region boundaries (meshine,
``mesh.element_size``). Heat documents read format 0.3; the format 0.2 region helpers here
serve the electric, Joule and mechanics region kinds until their own commits. See
docs/packages/simcase/thermal_regions2d.md.
"""
import copy
from dataclasses import replace
import math
import time

import numpy as np

from . import views
from .schema import SHAPE_TYPES, Document, DocumentError
from .thermal import PHYSICS, ThermalRunResult, _number, _object

SIDES = ('left', 'right', 'bottom', 'top')
# One materials table serves every region physics of a document: each physics reads the keys it
# needs and requires them only for the materials its regions use (heat: conductivity and heat
# capacity; electric: electrical conductivity; mechanics: E, nu and alpha, see mechanics_regions.py).
MATERIAL_KEYS = {'conductivity_w_mk', 'volumetric_heat_capacity_j_m3k', 'electrical_conductivity_s_m', 'source',
                 'young_modulus_pa', 'poisson_ratio', 'thermal_expansion_per_k'}

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
    otherwise. Dirichlet data may name the tags and every selection (galerkin fixes interior
    nodes too, HQ decision 2026-11-08: a prescribed temperature on an interface); flux and
    convection the tags and the exterior selections only, an interior one being refused by
    name. A 0.2 document has none. An unnamed exterior boundary is insulated (HQ decision
    2026-11-08: a void border is insulated unless named)."""
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
    if doc.si is not None:                       # format 0.3: the engine works in pm
        return sum(c.area for c in rc.cells if c.void) / 1e24
    pm_per_m = float(doc._pm_per_unit()) / float(doc.scale.to_si(1.0, {'length': 1}))   # pm per unit / m per unit
    return sum(c.area for c in rc.cells if c.void) / pm_per_m ** 2


def _sides(p, name, allowed=SIDES, names=(set(), set(), set())):
    path = f'physics.{name}'
    tags, outside, inside = names
    dirichlet_ok = set(allowed) | tags | outside | inside
    flux_ok = set(allowed) | tags | outside
    bc = p.get('dirichlet_temperature_k', {})
    _named_sides(bc, dirichlet_ok, path+'.dirichlet_temperature_k')
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


def region_geometry(doc, label='heat'):
    """Validate geometry.domain/background/shapes; return the shape names. ``label`` names the
    physics in refusals (``heat``, ``electric``, ``mechanics``)."""
    d = doc.data
    g = d['geometry']
    if doc.is_version_1:
        return _version_1_region_geometry(doc, label)
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
    refuse_dropped_shapes(doc, label)
    return names


def _version_1_region_geometry(doc, label='heat'):
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
        raise DocumentError(f'geometry.background.material: expected a material name (region {label} takes no void '
                            'background)')
    names = {r['name'] for r in doc.regions() if r['material'] is not None}
    from .geometry import dropped_features
    dropped = dropped_features(doc)
    if dropped:
        raise DocumentError(' '.join(dropped) + f' A {label} region document refuses a feature that contributes no '
                            'material.')
    return names


def refuse_dropped_shapes(doc, label='heat'):
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
        raise DocumentError(' '.join(dropped)+f' A {label} region document refuses a shape that '
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
        if 'electrical_conductivity_s_m' in spec:
            _number(spec['electrical_conductivity_s_m'], where+'.electrical_conductivity_s_m', positive=True)
        if 'young_modulus_pa' in spec:
            _number(spec['young_modulus_pa'], where+'.young_modulus_pa', positive=True)
        if 'poisson_ratio' in spec:
            _number(spec['poisson_ratio'], where+'.poisson_ratio')
            if not -1 < spec['poisson_ratio'] < .5:
                raise DocumentError(where+'.poisson_ratio: expected -1 < nu < 0.5')
        if 'thermal_expansion_per_k' in spec:
            _number(spec['thermal_expansion_per_k'], where+'.thermal_expansion_per_k')
        if 'source' in spec and not isinstance(spec['source'], str):
            raise DocumentError(where+'.source: expected a string')
    for where, mname in [('geometry.background.material', doc.background['material'])] + [
            (f'geometry.shapes[{i}].material' if not doc.is_version_1 else f'region {s["name"]!r}', s['material'])
            for i, s in enumerate(doc.regions()) if s['material'] is not None]:
        if mname not in materials:
            raise DocumentError(f'{where}: material {mname!r} is not defined in materials '
                                '(thermal, electrical and mechanical properties are never taken from built-in '
                                'optical materials)')
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
                                    "flux and convection apply to exterior boundaries only (Dirichlet may fix it)")
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


# -- format 0.3 -----------------------------------------------------------------------------------
# Region and axisymmetric heat documents read "openphysics": "0.3" (units batch C5b; phase-2 spec
# §4.1, §4.2). The checks read the resolved SI tree (``doc.si``, pm counts for shape numbers) and
# name the format 0.3 keys. The mesh is made from a hand-off document (``handoff_03``): the
# geometry and mesh block in the component's length unit, which ``runner.micrometre_document``
# turns into the same micrometre model the mesher received for format 0.2 (hazards H2, H11;
# decision D-1 keeps the mesh routes). The 0.2 helpers above stay for the electric, Joule and
# mechanics region kinds until their own commits.

RESULT_FORMAT_03 = 'thermal.steady2d-regions-result-v2'
FIELD_LAYOUT_03 = 'thermal2d-p1-node-cell-regions-v2'
AXISYMMETRIC_RESULT_FORMAT_03 = 'thermal.axisymmetric-regions-result-v2'
AXISYMMETRIC_FIELD_LAYOUT_03 = 'thermal-axisymmetric-p1-node-cell-regions-v2'
#: the format 0.2 keys that the shared mesh-time checks name, under their format 0.3 names
NAMES_03 = {'dirichlet_temperature_k': 'prescribed_temperature', 'outward_flux_w_m2': 'inward_heat_flux',
            'convection': 'convection', 'heat_source_w_m3': 'heat_source_density',
            'initial_temperature_k': 'initial_temperature'}
_FORMAT_02 = ('format 0.2 region heat documents are not read: units now travel with each value ("300 K", '
              '"45 W/(m K)"), the geometry declares its length_unit and element sizes are element_size '
              'quantities. Write "openphysics": "0.3" (docs/packages/simcase/thermal_regions2d.md)')


def refuse_format_02():
    raise DocumentError(_FORMAT_02, path='openphysics', code='E-FORMAT')


def _refuse(message, path=None, code='E-CONTRACT'):
    """A coded refusal. An E-CONTRACT message names its own path; any other code is shown as
    ``<path>: <message> (<code>)``, so its message does not repeat the path."""
    if code != 'E-CONTRACT' and path and message.startswith(path + ': '):
        message = message[len(path) + 2:]
    raise DocumentError(message, path=path, code=code)


class RegionHandOff(Document):
    """The mesh hand-off of a format 0.3 region document (``handoff_03``): its geometry and mesh
    block in the component's length unit, in the form ``runner.micrometre_document`` turns into
    the micrometre model the mesher receives. It carries no physics and is never validated as a
    document of its own; no user writes it."""
    is_handoff = True


def _plain(value):
    """An authored tree with each decimal as the double its JSON text gives (integers stay)."""
    from decimal import Decimal
    if isinstance(value, dict):
        return {k: _plain(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_plain(v) for v in value]
    if isinstance(value, Decimal):
        return float(value)
    return copy.deepcopy(value)


def component_03(doc):
    """``(base path, authored block, SI block)`` of the region geometry of a format 0.3 document:
    the flat block, or the one component of a version 1 block."""
    g, si = doc.data['geometry'], doc.si['geometry']
    if 'version' not in g:
        return 'geometry', g, si
    if len(g['components']) != 1:
        _refuse('geometry.components: a region heat document has exactly one component', 'geometry.components')
    (name, block), = g['components'].items()
    return f'geometry.components.{name}', block, si['components'][name]


def depth_03(doc):
    """The planar depth in metres (None: per metre of depth); None for an axisymmetric component."""
    return component_03(doc)[2].get('depth')


def handoff_03(doc):
    """The ``RegionHandOff`` of a format 0.3 region document (kept on the document while its
    tree is unchanged). Shape numbers keep their authored values; element sizes, control lengths
    and length parameters are given in the component's length unit from their exact values;
    the angle is the authored degree number (H3)."""
    from fractions import Fraction
    from physmat.units import convert, is_quantity_text
    from . import units
    key = doc.canonical_json()
    cached = getattr(doc, '_region_handoff', None)
    if cached is not None and cached[0] == key:
        return cached[1]
    base, block, _ = component_03(doc)
    unit = block['length_unit']
    per_unit = convert(f'1 {unit}', 'length').exact

    def length(path):
        return float(Fraction(doc.exact(path)) / per_unit)

    def sized(item, path, keep):
        out = {k: _plain(v) for k, v in item.items() if k in keep}
        if 'element_size' in item:
            out['mesh_size'] = length(f'{path}.element_size')
        return out
    g = doc.data['geometry']
    skip = {'length_unit', 'depth', 'accept', 'element_size', 'background', 'shapes', 'features'}
    if 'version' in g:
        (cname, comp), = g['components'].items()
        new = {k: _plain(v) for k, v in comp.items() if k not in skip}
        if 'background' in comp:
            new['background'] = sized(comp['background'], f'{base}.background', {'material'})
        if 'features' in comp:
            new['features'] = [sized(f, f'{base}.features[{i}]', set(f) - {'element_size'})
                               for i, f in enumerate(comp['features'])]
        geometry = {'version': g['version'], 'components': {cname: new}}
        if 'parameters' in g:
            params = {}
            for name, spec in g['parameters'].items():
                where = f'geometry.parameters.{name}'
                item = _plain(spec)
                if spec.get('kind', 'length') == 'length':
                    if is_quantity_text(spec.get('value')):
                        item['value'] = length(f'{where}.value')
                    if 'range' in spec:
                        item['range'] = [float(Fraction(convert(v, 'length').exact) / per_unit)
                                         if is_quantity_text(v) else _plain(v) for v in spec['range']]
                params[name] = item
            geometry = {'version': g['version'], 'parameters': params, 'components': {cname: new}}
    else:
        geometry = {'domain': _plain(g['domain'])}
        if 'background' in g:
            geometry['background'] = sized(g['background'], 'geometry.background', {'material'})
        geometry['shapes'] = [sized(s, f'geometry.shapes[{i}]', set(s) - {'element_size'})
                              for i, s in enumerate(g.get('shapes') or [])]
    m = doc.data.get('mesh') or {}
    mesh = {'size': length('mesh.element_size'),
            'min_angle': doc.degrees('mesh.minimum_angle') if 'minimum_angle' in m else 28.0}
    if m.get('controls'):
        names = {'element_size': 'size', 'near': 'near', 'far': 'far', 'refinement_distance': 'distance'}
        controls = []
        for i, entry in enumerate(m['controls']):
            item = {'select': _plain(entry['select'])}
            for k, engine in names.items():
                if k in entry:
                    item[engine] = length(f'mesh.controls[{i}].{k}')
            if 'circle_segment_count' in entry:
                item['circle_segments'] = int(entry['circle_segment_count'])
            controls.append(item)
        mesh['controls'] = controls
    # a length_unit the 0.2 unit table lacks (in, mil, Angstrom) travels as the numeric unit
    # {"in_m": <metres>}: the double of its exact decimal, which the micrometre and picometre
    # ratios read back exactly (units.micrometres_per_length, geometry_document.pm_per_unit)
    spec = unit if unit in units.BASE_UNITS['length'] else {'in_m': float(per_unit)}
    tree = {'openphysics': '0.2', 'name': doc.si['name'], 'units': {'length': spec}, 'geometry': geometry,
            'materials': {}, 'physics': {}, 'mesh': mesh, 'study': {'type': 'single'},
            'results': {'save_fields': False, 'plots': False}}
    h = RegionHandOff(tree)
    h.scale = units.resolve(tree['units'])
    if 'version' in g:
        from .geometry_document import GeometryError, parse
        try:
            model = parse(tree)
        except GeometryError as exc:
            raise DocumentError(str(exc)) from None
        h.geometry_model, h.geometry_source = model, copy.deepcopy(geometry)
        h.geometry_roundings = list(model.roundings)
        if any(f.type == 'segment' for f in h.component.features):
            from .geometry_engine import check_handoff
            try:
                check_handoff(h.complex())
            except GeometryError as exc:
                raise DocumentError(str(exc)) from None
    doc._region_handoff = (key, h)
    return h


def _shape_03(doc, s, i, names):
    where = f'geometry.shapes[{i}]'
    t = s.get('type')
    if t not in SHAPE_TYPES:
        _refuse(f'{where}.type: a region heat document takes rect, circle or polygon shapes', f'{where}.type')
    extra = sorted(set(s) - ({'type', 'name', 'material', 'element_size'} | SHAPE_TYPES[t]))
    if extra:
        _refuse(f'a {t} shape does not take {extra[0]!r} (unsupported keys {extra})', f'{where}.{extra[0]}',
                'E-KEY-UNKNOWN')
    missing = sorted(SHAPE_TYPES[t] - set(s))
    if missing:
        _refuse(f'a {t} shape needs {missing}', f'{where}.{missing[0]}', 'E-KEY-MISSING')
    name = s['name']
    if name == 'background' or name in names:
        _refuse(f'{where}.name: expected a unique name other than "background"', f'{where}.name', 'E-ID-CLASH')
    names.add(name)
    if t == 'polygon':
        points = s['points']
        if len(points) < 3 or any(not isinstance(q, list) or len(q) != 2 for q in points):
            _refuse(f'{where}.points: expected at least three [x, y] points', f'{where}.points')
        from shapely.geometry import Polygon
        corners = [(doc.pm(f'{where}.points[{j}][0]'), doc.pm(f'{where}.points[{j}][1]')) for j in range(len(points))]
        if not Polygon(corners).is_valid:
            _refuse(f'{where}.points: polygon must not self-intersect', f'{where}.points')
    else:
        for k in ('w', 'h', 'r'):
            if k in SHAPE_TYPES[t] and doc.pm(f'{where}.{k}') <= 0:
                _refuse(f'{where}.{k}: expected a positive length', f'{where}.{k}', 'E-DOMAIN')


def region_geometry_03(doc, h, label='heat'):
    """The format 0.3 region geometry checks (``region_geometry`` of format 0.2): a positive
    domain extent on pm counts, a background material, the shapes, and no shape or feature that
    contributes no material (refused by name). Returns the names of the material regions."""
    base, block, _ = component_03(doc)
    if h.is_version_1:
        return _version_1_region_geometry(h, label)
    dom = block['domain']
    extra = sorted(set(dom) - {'xmin', 'xmax', 'ymin', 'ymax'})
    if extra:
        _refuse(f'unsupported keys {extra}; a region {label} document is 2D',
                f'geometry.domain.{extra[0]}', 'E-KEY-UNKNOWN')
    for axis in 'xy':
        if not doc.pm(f'geometry.domain.{axis}min') < doc.pm(f'geometry.domain.{axis}max'):
            _refuse(f'geometry.domain.{axis} extent: expected a positive extent ({axis}min < {axis}max)',
                    f'geometry.domain.{axis}max')
    if not isinstance(block.get('background'), dict) or 'material' not in block['background']:
        _refuse(f'geometry.background.material: a region {label} document needs a background material',
                'geometry.background.material', 'E-KEY-MISSING')
    names = set()
    for i, s in enumerate(block.get('shapes') or []):
        _shape_03(doc, s, i, names)
    refuse_dropped_shapes(h, label)
    return names


def region_materials_table_03(doc, h, required, label, properties='thermal properties'):
    """Every material a region uses is defined in ``materials`` and gives the ``required``
    properties (``E-PROPERTY-MISSING``); the reader has checked the values and flags the
    properties no physics of the run reads (``I-UNUSED-PROPERTY``). Returns the used material
    names, in use order (``properties`` names them in the refusal of an undefined material)."""
    base = component_03(doc)[0]
    materials = doc.si.get('materials') or {}
    used = [(f'{base}.background.material', h.background['material'])]
    used += [(f'geometry.shapes[{i}].material' if not h.is_version_1 else f'region {r["name"]!r}', r['material'])
             for i, r in enumerate(h.regions()) if r['material'] is not None]
    for where, mname in used:
        if mname not in materials:
            _refuse(f'{where}: material {mname!r} is not defined in materials ({properties} are never taken '
                    'from library materials)', where if where.startswith('geometry') else 'materials',
                    'E-MATERIAL-UNKNOWN')
        for key in required:
            if key not in materials[mname]:
                _refuse(f'materials.{mname}.{key}: required by {label}', f'materials.{mname}.{key}',
                        'E-PROPERTY-MISSING')
    return list(dict.fromkeys(mname for _where, mname in used))


def region_source_03(p, names, path):
    """``heat_source_density``: absent (no source), one value, or {region name: value} over the
    shape names and ``background``."""
    source = p.get('heat_source_density')
    if isinstance(source, dict):
        allowed = names | {'background'}
        for region in source:
            if region not in allowed:
                _refuse(f'{path}.heat_source_density.{region}: no shape or background of that name',
                        f'{path}.heat_source_density.{region}', 'E-SELECTION-UNKNOWN')


def _named_sides_03(value, allowed, path, interior=()):
    """The boundary names a document gives this data to; the axis, a left side at r = 0, an
    interior selection given flux or convection and an unknown name are refused by name."""
    for key in value:
        where = f'{path}.{key}'
        if key == 'axis' and key not in allowed:
            _refuse(f"{where}: 'axis' is the symmetry axis of an axisymmetric component; it carries natural "
                    "regularity and takes no prescribed temperature, flux or convection", where)
        if key == 'left' and key not in allowed:
            _refuse(f"{where}: an axisymmetric component whose domain starts at r = 0 has no left side; its r = 0 "
                    "side is the axis", where)
        if key in interior and key not in allowed:
            _refuse(f"{where}: selection {key!r} lies on an interface between two regions; flux and convection "
                    "apply to exterior boundaries only (a prescribed temperature may fix it)", where)
        if key not in allowed:
            _refuse(f'{where}: no side, boundary tag or selection of that name; expected one of {sorted(allowed)}',
                    where, 'E-SELECTION-UNKNOWN')


def sides_03(p, name, allowed=SIDES, names=(set(), set(), set()), transient=False):
    """The format 0.3 boundary checks (``_sides`` of format 0.2) on SI values: the names, the
    corner agreement of side temperatures, a prescribed-temperature or positive-convection
    anchor (steady), and no natural condition on a fully prescribed side."""
    path = f'physics.{name}'
    tags, outside, inside = names
    prescribed = p.get('prescribed_temperature', {})
    _named_sides_03(prescribed, set(allowed) | tags | outside | inside, f'{path}.prescribed_temperature')
    if transient:
        return
    for a in ('left', 'right'):
        for b in ('bottom', 'top'):
            if a in prescribed and b in prescribed and prescribed[a] != prescribed[b]:
                _refuse(f'{path}.prescribed_temperature: conflicting corner temperatures on {a}/{b}',
                        f'{path}.prescribed_temperature.{b}')
    flux, robin = p.get('inward_heat_flux', {}), p.get('convection', {})
    _named_sides_03(flux, set(allowed) | tags | outside, f'{path}.inward_heat_flux', inside)
    _named_sides_03(robin, set(allowed) | tags | outside, f'{path}.convection', inside)
    if not prescribed and not any(c['heat_transfer_coefficient'] > 0 for c in robin.values()):
        _refuse('a steady region document requires a prescribed-temperature or positive-convection anchor; pure '
                'Neumann is unsupported', f'{path}.prescribed_temperature', 'E-KEY-MISSING')
    overlap = sorted(set(prescribed) & (set(flux) | set(robin)))
    if overlap:
        _refuse(f'{path}: natural condition overlaps a fully prescribed-temperature side', f'{path}.{overlap[0]}')


def default_boundaries_03(doc, name, p, sides):
    """``I-DEFAULT-BOUNDARY`` for each exterior side that no condition names: it is insulated."""
    from physmat.units import Diagnostic
    named = set(p.get('prescribed_temperature', {})) | set(p.get('inward_heat_flux', {})) | set(p.get('convection', {}))
    for side in sides:
        if side not in named:
            where = f'physics.{name}.inward_heat_flux.{side}'
            doc.diagnostics.append(Diagnostic('I-DEFAULT-BOUNDARY', where, f'side {side!r} has no condition: it is '
                                                                           'insulated (inward_heat_flux 0 W/m^2)'))


def region_mesh_settings_03(doc, label='a region document'):
    """``mesh.element_size`` is required; ``minimum_angle`` is at most 33 degrees;
    ``subdivision_count`` belongs to rectangles."""
    import math
    mesh = doc.si.get('mesh') or {}
    if 'subdivision_count' in mesh:
        _refuse(f'mesh.subdivision_count: {label} is meshed by element_size; subdivision_count belongs to '
                'rectangle documents', 'mesh.subdivision_count', 'E-KEY-UNKNOWN')
    if 'element_size' not in mesh:
        _refuse(f'mesh.element_size: required by {label} (for example "2 mm")', 'mesh.element_size',
                'E-KEY-MISSING')
    if mesh.get('controls') and 'version' not in doc.data['geometry']:
        _refuse('mesh.controls needs a version 1 geometry block with a 2D region component; a flat geometry block '
                'has no selections to control', 'mesh.controls')
    if mesh['minimum_angle'] > math.radians(33):
        _refuse('mesh.minimum_angle: at most 33 deg (refinement need not terminate above)', 'mesh.minimum_angle',
                'E-DOMAIN')


def mesh_controls_03(doc, h):
    """Each ``mesh.controls`` entry selects something the component has; an element_size goes on
    a region (the reader has checked the entries' own values)."""
    from .geometry_document import GeometryError
    for i, entry in enumerate((doc.si.get('mesh') or {}).get('controls') or []):
        where = f'mesh.controls[{i}]'
        try:
            kind, _chosen = h.complex().select(entry['select'])
        except GeometryError as exc:
            _refuse(f'{where}: {exc}', f'{where}.select', 'E-SELECTION-UNKNOWN')
        if 'element_size' in entry and kind != 'region':
            _refuse(f"{where}: select {entry['select']!r} is a boundary selection; an element_size on a boundary is "
                    "not implemented yet (give it to a region)", f'{where}.select')


def _region_entry_03(doc, kind_label, allowed_keys):
    """``(name, SI entry, path)`` of the one physics entry of a region document; the material
    properties are refused on it by name."""
    doc.sole_physics()
    name, p = next(iter(doc.si['physics'].items()))
    if not isinstance(name, str) or not name.isidentifier():
        _refuse('physics: name must be an identifier', f'physics.{name}')
    path = f'physics.{name}'
    for key in ('thermal_conductivity', 'volumetric_heat_capacity'):
        if key in p:
            _refuse(f'{path}.{key}: a region document takes {key} from materials.<m>', f'{path}.{key}')
    extra = sorted(set(p) - allowed_keys)
    if extra:
        _refuse(f'{path}.{extra[0]}: {kind_label} on regions does not take {extra[0]} (a rectangle does)',
                f'{path}.{extra[0]}', 'E-KEY-UNKNOWN')
    return name, p, path


def validate_region_thermal_03(doc):
    """thermal.steady2d on regions and axisymmetric regions, format 0.3."""
    name, p, path = _region_entry_03(doc, 'steady heat', {'type', 'heat_source_density', 'prescribed_temperature',
                                                          'inward_heat_flux', 'convection'})
    region_mesh_settings_03(doc)
    h = handoff_03(doc)
    names = region_geometry_03(doc, h)
    mesh_controls_03(doc, h)
    region_materials_table_03(doc, h, ('thermal_conductivity',), 'steady heat')
    region_source_03(p, names, path)
    sides = exterior_sides(h)[1]
    sides_03(p, name, sides, boundary_names(h))
    default_boundaries_03(doc, name, p, sides)
    if doc.si['study'] != {'type': 'single'}:
        _refuse('study: thermal.steady2d supports only {"type": "single"}', 'study.type')
    if doc.si['results'].get('plots'):
        _refuse('results.plots: thermal.steady2d is headless; plots=true is not supported', 'results.plots')


def region_summary_03(doc, label, lines, versions):
    """The summary text of a format 0.3 region heat document."""
    from .thermal import _authored
    h = handoff_03(doc)
    name, p = next(iter(doc.si['physics'].items()))
    where = f'physics.{name}'
    base, block, _ = component_03(doc)
    dom = ', '.join(f'{k} {_plain(block["domain"][k])}' for k in ('xmin', 'xmax', 'ymin', 'ymax'))
    out = [f'{doc.si["name"]} (openphysics 0.3)', f'  physics {name}: {label}',
           f'  domain {dom} ({block["length_unit"]}); element_size {_authored(doc, "mesh.element_size")}',
           f'  background: {h.background["material"]}']
    out += [f'  region {r["name"]}: {r["type"]}, {r["material"] if r["material"] is not None else "void (hole)"}'
            for r in h.regions()]
    for mname, spec in doc.si['materials'].items():
        props = ', '.join(f'{k} {_authored(doc, f"materials.{mname}.{k}")}' for k in spec if k != 'source')
        out.append(f'  material {mname}: {props}')
    source = p.get('heat_source_density')
    if source is None:
        out.append('  no heat_source_density')
    elif isinstance(source, dict):
        out.append('  heat_source_density ' + str({r: _authored(doc, f'{where}.heat_source_density.{r}')
                                                   for r in source}))
    else:
        out.append(f'  heat_source_density {_authored(doc, where + ".heat_source_density")}')
    temperatures = {tag: _authored(doc, f'{where}.prescribed_temperature.{tag}')
                    for tag in p.get('prescribed_temperature', {})}
    flux = {tag: _authored(doc, f'{where}.inward_heat_flux.{tag}') for tag in p.get('inward_heat_flux', {})}
    convection = {tag: {k: _authored(doc, f'{where}.convection.{tag}.{k}') for k in c}
                  for tag, c in p.get('convection', {}).items()}
    out.append(f'  prescribed_temperature {temperatures}' + (f'; inward_heat_flux {flux}' if flux else '')
               + (f'; convection {convection}' if convection else '')
               + '; other exterior boundaries insulated')
    out += lines
    out.append(f'  result: {versions[0]}; layout: {versions[1]}')
    rate = 'W (full revolution; axisymmetric (r, z))' if is_axisymmetric(h) else 'W/m of depth'
    out.append(f'  output: SI (node_coordinates m, temperature K, heat_flux W/m^2, nodal heat rates {rate}, '
               'triangle_regions)')
    return '\n'.join(out)


def region_result_versions_03(doc):
    """The (result_format, field_layout) pair a format 0.3 steady region document saves."""
    if is_axisymmetric(handoff_03(doc)):
        return AXISYMMETRIC_RESULT_FORMAT_03, AXISYMMETRIC_FIELD_LAYOUT_03
    return RESULT_FORMAT_03, FIELD_LAYOUT_03


def build_region_mesh_03(doc, limits=None):
    """The 0.3 ``build_region_mesh``: the region mesh of the document's hand-off (``handoff_03``)
    in SI metres, its region materials and the diagnostic triangulation."""
    return build_region_mesh(handoff_03(doc), limits)


def build_region_mesh(doc, limits=None):
    """meshine mesh in SI metres with named regions and box-side tags.

    ``limits`` (simcase.mesh_limits._MeshLimits) bounds the loop vertices of the micrometre
    document that is meshed before meshine builds its domain, passes max_nodes to meshine
    as max_points, and compares the exact node and triangle counts after meshing; each
    check whose limit is None is skipped, and without limits the mesh is made exactly as
    before."""
    from galerkin.mesh import Mesh
    from meshine import generate
    from .geometry import build_domain
    from . import units
    grid = views.region_mesh(doc)
    canonical = grid.canonical
    if limits is None:
        domain, namer, region_materials = build_domain(canonical)
        tri = generate(domain, namer, min_angle=grid.minimum_angle_deg, **_grading(canonical))
    else:
        tri, region_materials = _limited_mesh(grid, limits, generate)
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
        on_axis = (np.asarray(tri.nodes, dtype=float)[:, 0] == 0.0) if 'axis' in exterior_sides(doc)[0] else None
        for name, edges in selections.items():
            edges = np.asarray(edges, dtype=int).reshape(-1, 2)
            nodes = np.unique(edges)
            if on_axis is not None:
                # the symmetry axis is not a physical boundary: a selection's nodes on it carry
                # no Dirichlet data (galerkin refuses axis-only Dirichlet nodes); the end faces
                # may still fix an axis end point through their own tag
                nodes = nodes[~on_axis[nodes]]
            if len(nodes) == 0:
                continue                                  # without a mesh node: no data (refused by name)
            if name in boundary or name in boundary_edges:
                raise DocumentError(f'selection {name!r} shares its name with a mesh tag')
            boundary[name] = nodes                                       # Dirichlet nodes, interior too
            if name in outside:
                boundary_edges[name] = edges                             # flux and convection
    mesh = Mesh(views.handback_m(tri.nodes), tri.triangles,
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


def _limited_mesh(grid, limits, generate):
    """(meshine mesh, region materials) of the region mesh view ``grid`` (views.RegionMesh) under
    ``limits``: the loop vertices of its micrometre document are counted before Domain.build,
    and max_points is passed only when max_nodes is set, so meshine otherwise keeps its own
    default cap."""
    from .geometry import _domain_from_regions
    from .mesh_limits import MeshLimitError
    doc = grid.canonical
    domain, namer, region_materials, _count = _domain_from_regions(
        doc, max_input_vertices=limits.max_input_vertices)
    grading = _grading(doc)
    if limits.max_nodes is None:
        return generate(domain, namer, min_angle=grid.minimum_angle_deg, **grading), region_materials
    from meshine import MeshSizeLimitError     # here: an older meshine fails only limited runs
    try:
        tri = generate(domain, namer, min_angle=grid.minimum_angle_deg, max_points=limits.max_nodes,
                       **grading)
    except MeshSizeLimitError as exc:
        raise MeshLimitError('nodes', limits.max_nodes) from exc
    return tri, region_materials


def region_inputs(doc, mesh, region_materials, heat=None, names=None):
    """solve_steady_heat keyword arguments for a meshed region document (from its internal SI
    view, ``simcase.views.region_heat``, or the given ``heat`` view). ``names`` maps the format
    0.2 keys the messages name to the document's own keys (``NAMES_03`` for format 0.3)."""
    name, _ = doc.sole_physics()
    path = f'physics.{name}'
    key = (lambda k: k) if names is None else (lambda k: names.get(k, k))      # noqa: E731
    heat = views.region_heat(doc) if heat is None else heat
    conductivity = {r: float(heat.conductivity[m]) for r, m in region_materials.items()}
    source = heat.heat_source   # a Joule document has none (simcase.joule_regions)
    if isinstance(source, dict):
        dropped = set(source)-set(mesh.region_names)
        if dropped:
            raise DocumentError(f'{path}.{key("heat_source_w_m3")}: regions {sorted(dropped)} are not in the meshed '
                                'geometry (fully covered by later shapes or smaller than the sliver limit)')
        source = {r: float(source.get(r, 0.0)) for r in mesh.region_names}
    else:
        source = float(source)
    prescribed, prescribed_by = {}, {}
    for label, table, given in (('dirichlet_temperature_k', mesh.boundary, heat.dirichlet),
                                ('outward_flux_w_m2', mesh.boundary_edges, heat.outward_flux),
                                ('convection', mesh.boundary_edges, heat.convection)):
        for tag in given:
            if tag not in table:
                raise DocumentError(f'{path}.{key(label)}.{tag}: no mesh edge lies on {tag!r} (a side or boundary '
                                    'that borders a void feature only, or a selection without mesh edges)')
    for tag, value in heat.dirichlet.items():
        for node in mesh.boundary[tag]:
            if int(node) in prescribed and prescribed[int(node)] != value:
                raise DocumentError(f'{path}.{key("dirichlet_temperature_k")}: {prescribed_by[int(node)]!r} and '
                                    f'{tag!r} share node {node} with different temperatures')
            prescribed[int(node)] = float(value)
            prescribed_by[int(node)] = tag
    flux = {tag: float(v) for tag, v in heat.outward_flux.items()}
    convection = {tag: (float(h), float(ambient)) for tag, (h, ambient) in heat.convection.items()}
    _refuse_doubled_edges(mesh, path, flux, convection, heat.dirichlet, key)
    return dict(conductivity=conductivity, dirichlet=dict(sorted(prescribed.items())),
                heat_source=source, outward_flux=flux, convection=convection)


def _refuse_doubled_edges(mesh, path, flux, convection, dirichlet, key=lambda k: k):
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
                    raise DocumentError(f'{path}.{key(label)}: {a!r} and {b!r} share mesh edges; give that '
                                        'boundary one entry')
    # a natural condition on a fully Dirichlet edge is refused by the solver; here by name,
    # for a side tag and a selection that carry the same edges (names alone are checked at
    # load). A selection without an edge tag (an interface selection that touches a side) is
    # read through its selection edges, so a side's flux under a fixed selection is named too.
    selected = getattr(mesh, 'selection_edges', None) or {}
    fixed = {}
    for tag in dirichlet:
        edges = mesh.boundary_edges.get(tag, selected.get(tag))
        if edges is not None:
            fixed[tag] = {tuple(sorted(map(int, e))) for e in np.asarray(edges).reshape(-1, 2)}
    for label, table in (('outward_flux_w_m2', flux), ('convection', convection)):
        for a, e in edge_sets(table).items():
            for b, f in fixed.items():
                if a != b and e & f:
                    fixed_word = 'Dirichlet' if key is None or key('dirichlet_temperature_k') == \
                        'dirichlet_temperature_k' else 'prescribed-temperature'
                    raise DocumentError(f'{path}.{key(label)}.{a}: {a!r} shares mesh edges with the {fixed_word} '
                                        f'boundary {b!r}; a natural condition does not apply on a {fixed_word} edge')


def per_depth_name(key):
    """The planar (``_per_depth``) name of a saved array or summary key of an axisymmetric
    result, which uses the plain name for its full-revolution value."""
    from .thermal import FIELDS_03
    return key + '_per_depth' if key + '_per_depth' in FIELDS_03 or key in _PLAIN_TOTALS else key


#: the plain names of the axisymmetric balance values (their planar names end in _per_depth)
_PLAIN_TOTALS = ('generated_heat_rate', 'outward_prescribed_heat_rate', 'outward_convective_heat_rate',
                 'outward_reaction_heat_rate', 'outward_heat_rate', 'heat_rate_imbalance', 'maximum_residual_heat_rate',
                 'heat_storage_rate', 'stored_heat', 'thermal_energy_functional')


def plain_name(key):
    """``generated_heat_rate_per_depth`` -> ``generated_heat_rate`` (full revolution)."""
    return key[:-len('_per_depth')] if key.endswith('_per_depth') else key


def mesh_diagnostics_03(doc, base, notes):
    """The mesher's findings on a format 0.3 document, as coded diagnostics at their paths: a
    piece of a region left out of the mesh (``W-PIECE-DROPPED``) and a raised circle segment
    count (``I-MESH-CONTROL-RAISED``). Each note names its own path before the colon."""
    from physmat.units import Diagnostic
    seen = {(d.code, d.path, d.message) for d in doc.diagnostics}
    for note in notes:
        where, _, _text = note.partition(':')
        code = 'I-MESH-CONTROL-RAISED' if where == 'mesh.controls' else \
            'W-PIECE-DROPPED' if where == 'geometry.features' else 'W-SHAPE-DROPPED'
        path = f'{base}.features' if where == 'geometry.features' else where
        if (code, path, note) not in seen:
            doc.diagnostics.append(Diagnostic(code, path, note))
            seen.add((code, path, note))


class RegionThermalRunResult(ThermalRunResult):
    """ThermalRunResult of a format 0.3 region document: the arrays under registry names with
    the triangle regions and the boundary rates, and the summary of section 5.3.1."""

    def __post_init__(self):
        super().__post_init__()
        self._regions_snapshot = np.array(self.mesh.regions, copy=True)
        self._names_snapshot = list(self.mesh.region_names)
        self._result_format, self._field_layout = region_result_versions_03(self.doc)

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

    _components = ['x', 'y']
    _area = 'area'

    def summary(self):
        from .thermal import FIELDS_03, strict_timing, strict_value as vo
        from .steady_boundary_contract import LOAD_DEFINITION_03, OUTWARD_SIGN_03, REACTION_SIGN_03
        from . import results_common
        arrays = self._raw_arrays()
        doc = self.doc
        name, p = next(iter(doc.si['physics'].items()))
        fields = {}
        for key, a in arrays.items():
            if key == 'triangle_regions':
                quantity, location, components = None, 'triangles', None
            else:
                quantity, location, components = FIELDS_03[per_depth_name(key)]
                if quantity is not None and key != per_depth_name(key):
                    quantity = plain_name(quantity)
                components = None if components is None else list(self._components)
            fields[key] = {'quantity': quantity, 'location': location, 'shape': list(a.shape),
                           'components': components}
        maps = results_common.field_maps(fields)
        del maps['field_time_axes']                      # a steady result has no time axis
        materials = doc.si['materials']
        k = self.mesh.by_region({r: materials[m]['thermal_conductivity'] for r, m in self.region_materials.items()})
        areas = self.mesh.areas()
        result = {'name': doc.si['name'], 'physics_name': name, 'physics_type': PHYSICS,
                  **results_common.envelope(doc, result_format=self.result_format, field_layout=self.field_layout,
                                            timing_=strict_timing(self.timings)),
                  **maps,
                  'region_names': self.region_names,
                  'regions': {r: {'material': self.region_materials[r],
                                  'triangles': int(np.sum(self.mesh.regions == i)),
                                  self._area: vo(float(areas[self.mesh.regions == i].sum()), self._area)}
                              for i, r in enumerate(self.region_names)},
                  'materials': {m: {key: vo(v, key) if isinstance(v, (int, float)) and not isinstance(v, bool)
                                    else copy.deepcopy(v) for key, v in spec.items()}
                                for m, spec in materials.items()},
                  'reaction_sign': self._text(REACTION_SIGN_03), 'outward_sign': self._text(OUTWARD_SIGN_03),
                  'load_definition': self._text(LOAD_DEFINITION_03),
                  'mesh': {'nodes': len(self.mesh.nodes), 'triangles': len(self.mesh.triangles)},
                  'study': {'type': 'single'}}
        source = p.get('heat_source_density')
        if isinstance(source, dict):
            result['heat_source_density'] = {r: vo(v, 'heat_source_density') for r, v in source.items()}
        elif source is not None:
            result['heat_source_density'] = vo(source, 'heat_source_density')
        result['prescribed_temperature'] = {tag: vo(v, 'prescribed_temperature')
                                            for tag, v in p.get('prescribed_temperature', {}).items()}
        result['inward_heat_flux'] = {tag: vo(v, 'inward_heat_flux') for tag, v in p.get('inward_heat_flux', {}).items()}
        result['convection'] = {tag: {'heat_transfer_coefficient': vo(c['heat_transfer_coefficient'],
                                                                      'heat_transfer_coefficient'),
                                      'ambient_temperature': vo(c['ambient_temperature'], 'ambient_temperature')}
                                for tag, c in p.get('convection', {}).items()}
        result['prescribed_nodes'] = len(self.dirichlet_node_ids)
        result['minimum_thermal_conductivity'] = vo(k.min(), 'minimum_thermal_conductivity')
        result['maximum_thermal_conductivity'] = vo(k.max(), 'maximum_thermal_conductivity')
        result['minimum_temperature'] = vo(self.solution.temperature.min(), 'minimum_temperature')
        result['maximum_temperature'] = vo(self.solution.temperature.max(), 'maximum_temperature')
        for key, value in self.diagnostics.items():
            result[key] = vo(value, key)
        self._axisymmetric_keys(result)
        results_common.dumps_summary(result)            # finite JSON only
        return result

    def _axisymmetric_keys(self, result):
        from . import results_common
        results_common.add_depth_totals(result, depth_03(self.doc))

    @staticmethod
    def _text(text):
        return text


class AxisymmetricRegionThermalRunResult(RegionThermalRunResult):
    """The result of an axisymmetric run: the same arrays with the nodal rates in W over the
    full revolution under their plain names (``generated_heat_rate``, never ``_per_depth``),
    (r, z) coordinates and the meridional area of each region."""
    _components = ['r', 'z']
    _area = 'meridional_area'

    def _raw_arrays(self):
        return {plain_name(key): a for key, a in super()._raw_arrays().items()}

    # the full-revolution rates under their plain names (the planar names are refused below)
    @property
    def generated_heat_rate(self): return self.solution.load

    @property
    def reaction_heat_rate(self): return self.solution.reaction

    @property
    def residual_heat_rate(self): return self.solution.residual

    @property
    def outward_prescribed_heat_rate(self): return self.solution.prescribed_outward_load

    @property
    def ambient_convective_heat_rate(self): return self.solution.ambient_load

    @property
    def outward_convective_heat_rate(self): return self.solution.convective_outward

    @property
    def applied_heat_rate(self): return self.solution.system_rhs

    @staticmethod
    def _text(text):
        return text.replace('_per_depth', '')      # full-revolution rates under their plain names

    def _axisymmetric_keys(self, result):
        result['coordinate_system'] = 'axisymmetric'
        result['coordinates'] = '(r, z) in metres; volume measure 2*pi*r dr dz, full revolution'


def _planar_name(name):
    def refused(self):
        raise AttributeError(f'{name} is a per-depth name; an axisymmetric result reads {plain_name(name)}')
    return property(refused)


for _name in ('generated_heat_rate_per_depth', 'reaction_heat_rate_per_depth', 'residual_heat_rate_per_depth',
              'outward_prescribed_heat_rate_per_depth', 'ambient_convective_heat_rate_per_depth',
              'outward_convective_heat_rate_per_depth', 'applied_heat_rate_per_depth'):
    setattr(AxisymmetricRegionThermalRunResult, _name, _planar_name(_name))


def run_region_thermal(doc, verbose=True, *, mesh_limits=None):
    from galerkin.thermal import solve_steady_heat
    from .thermal import log_lines_03
    doc.validate()
    given, doc = doc, doc.copy()
    doc.validate()
    name, _ = doc.sole_physics()
    t0 = time.perf_counter()
    h = handoff_03(doc)
    mesh, region_materials, tri = build_region_mesh(h, mesh_limits)
    # the mesher's findings reach the caller's document as coded diagnostics
    for target in (given, doc):
        mesh_diagnostics_03(target, component_03(doc)[0], h.notes)
    kwargs = region_inputs(doc, mesh, region_materials, views.region_heat_03(doc), NAMES_03)
    t_mesh = time.perf_counter()-t0
    calculation_json = doc.canonical_json(separators=(',', ':'))
    axisymmetric = is_axisymmetric(h)
    t0 = time.perf_counter()
    try:
        solution = solve_steady_heat(mesh, **kwargs, coordinate_system='axisymmetric' if axisymmetric else 'cartesian')
    except (ValueError, RuntimeError) as exc:
        raise ValueError(f'physics.{name} ({PHYSICS}): {exc}') from exc
    t_solve = time.perf_counter()-t0
    if doc.canonical_json(separators=(',', ':')) != calculation_json:
        raise ValueError('thermal calculation inputs changed during the solve')
    fixed = np.array(list(kwargs['dirichlet']), dtype=int)
    G, C = solution.prescribed_outward_load, solution.convective_outward
    source_heat = float(solution.load.sum())
    outward = float(G.sum())+float(C.sum())-float(solution.reaction.sum())
    scale = max(float(sum(np.sum(abs(a)) for a in (solution.load, solution.reaction, G, C))),
                np.finfo(float).tiny)
    free = np.setdiff1d(np.arange(mesh.num_nodes), fixed)
    rate = '' if axisymmetric else '_per_depth'
    diagnostics = {f'generated_heat_rate{rate}': source_heat,
                   f'outward_prescribed_heat_rate{rate}': float(G.sum()),
                   f'outward_convective_heat_rate{rate}': float(C.sum()),
                   f'outward_reaction_heat_rate{rate}': -float(solution.reaction.sum()),
                   f'outward_heat_rate{rate}': outward,
                   f'heat_rate_imbalance{rate}': outward-source_heat,
                   'relative_conservation_residual': abs(outward-source_heat)/scale,
                   f'maximum_residual_heat_rate{rate}': float(np.max(abs(solution.residual[free]))) if len(free) else 0.,
                   'minimum_triangle_angle': math.radians(float(tri.min_angle()))}
    covered = covered_shapes(h, mesh)
    unit = 'W' if axisymmetric else 'W/m'
    printed = [doc.summary(),
               f'mesh: {mesh.num_nodes} nodes, {len(mesh.triangles)} triangles, regions {mesh.region_names}',
               *([f'shapes fully covered by later shapes (no triangles): {covered}'] if covered else []),
               f'temperature: {solution.temperature.min():.12g} K to {solution.temperature.max():.12g} K',
               f'generated_heat_rate{rate} {source_heat:.12g} {unit}; outward_heat_rate{rate} {outward:.12g} {unit}'
               + (' (full revolution)' if axisymmetric else '')]
    if verbose:
        print('\n'.join(printed))
    cls = AxisymmetricRegionThermalRunResult if axisymmetric else RegionThermalRunResult
    result = cls(doc, mesh, solution, fixed, np.array([kwargs['dirichlet'][int(i)] for i in fixed], dtype=float),
                 diagnostics, {'mesh': t_mesh, 'solve': t_solve}, log_lines_03(doc, printed))
    result.region_materials = region_materials
    result.summary()
    return result
