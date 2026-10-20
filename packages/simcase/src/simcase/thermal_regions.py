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
import json
import math
import time

import numpy as np

from .schema import SHAPE_TYPES, DocumentError
from .thermal import PHYSICS, ThermalRunResult, _number, _object

RESULT_FORMAT = 'thermal.steady2d-regions-result-v1'
FIELD_LAYOUT = 'thermal2d-p1-node-cell-regions-v1'
SIDES = ('left', 'right', 'bottom', 'top')
MATERIAL_KEYS = {'conductivity_w_mk', 'volumetric_heat_capacity_j_m3k', 'source'}
BOUNDARY_FIELDS = ('prescribed_outward_load_w_per_m', 'ambient_load_w_per_m',
                   'convective_outward_w_per_m', 'system_rhs_w_per_m')


def has_region_geometry(data, physics_type):
    """A document of physics_type that declares region geometry."""
    if not isinstance(data, dict) or not isinstance(data.get('physics'), dict):
        return False
    typed = any(isinstance(p, dict) and p.get('type') == physics_type for p in data['physics'].values())
    geometry = data.get('geometry')
    return typed and isinstance(geometry, dict) and ('shapes' in geometry or 'background' in geometry)


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


def _sides(p, name):
    path = f'physics.{name}'
    bc = p.get('dirichlet_temperature_k', {})
    _object(bc, set(SIDES), path+'.dirichlet_temperature_k')
    for tag, value in bc.items():
        _number(value, f'{path}.dirichlet_temperature_k.{tag}', nonnegative=True)
    for a in ('left', 'right'):
        for b in ('bottom', 'top'):
            if a in bc and b in bc and bc[a] != bc[b]:
                raise DocumentError(f'{path}.dirichlet_temperature_k: conflicting corner temperatures on {a}/{b}')
    flux = p.get('outward_flux_w_m2', {})
    _object(flux, set(SIDES), path+'.outward_flux_w_m2')
    for tag, value in flux.items():
        _number(value, f'{path}.outward_flux_w_m2.{tag}')
    robin = p.get('convection', {})
    _object(robin, set(SIDES), path+'.convection')
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
    """Shapes with no triangles in the mesh: fully covered by later shapes."""
    return [s['name'] for s in doc['geometry']['shapes'] if s['name'] not in mesh.region_names]


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
    g = d['geometry']
    for where, mname in [('geometry.background.material', g['background']['material'])] + [
            (f'geometry.shapes[{i}].material', s['material']) for i, s in enumerate(g['shapes'])]:
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


def region_mesh_settings(doc):
    mesh = doc.data['mesh']
    _object(mesh, {'size', 'min_angle'}, 'mesh')
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
    _sides(p, name)
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
    g = doc['geometry']
    lines = [f'{doc["name"]} (openphysics 0.2)',
             f'  physics {name}: {PHYSICS}, single steady heat, named material regions',
             f'  domain {doc.domain} {doc.length_unit}; mesh size {doc["mesh"]["size"]} {doc.length_unit}',
             f'  background: {g["background"]["material"]}']
    for s in g['shapes']:
        lines.append(f'  shape {s["name"]}: {s["type"]}, {s["material"]}')
    for mname, spec in doc['materials'].items():
        lines.append(f'  material {mname}: k={spec.get("conductivity_w_mk")} W/(m K)')
    lines += [f'  Q={p["heat_source_w_m3"]} W/m^3',
              f'  Dirichlet {p.get("dirichlet_temperature_k", {})} K; other exterior insulated unless flux/convection given',
              '  output: coordinates m, temperature K, flux W/m^2, nodal heat W/m of depth, triangle regions']
    return '\n'.join(lines)


def build_region_mesh(doc):
    """meshine mesh in SI metres with named regions and box-side tags."""
    from galerkin.mesh import Mesh
    from meshine import generate
    from .geometry import build_domain
    domain, namer, region_materials = build_domain(doc)
    tri = generate(domain, namer, min_angle=float(doc['mesh']['min_angle']))
    if tri.num_triangles == 0:
        raise DocumentError('meshing produced no triangles; check mesh.size against the domain')
    unknown = set(tri.boundary_edges)-set(SIDES)
    if unknown or set(tri.boundary_edges) != set(SIDES):
        raise DocumentError(f'mesh: exterior edges must all lie on the four domain sides; found tags '
                            f'{sorted(tri.boundary_edges)}')
    factor = doc.scale.to_si(1.0, {'length': 1})
    mesh = Mesh(np.asarray(tri.nodes, dtype=float)*factor, tri.triangles,
                boundary={k: np.asarray(v) for k, v in tri.boundary_nodes.items()},
                boundary_edges={k: np.asarray(v) for k, v in tri.boundary_edges.items()},
                regions=np.asarray(tri.regions), region_names=list(tri.region_names))
    region_materials = {r: region_materials[r] for r in mesh.region_names}
    return mesh, region_materials, tri


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
    for tag, value in p.get('dirichlet_temperature_k', {}).items():
        for node in mesh.boundary[tag]:
            if int(node) in prescribed and prescribed[int(node)] != value:
                raise DocumentError(f'{path}: conflicting corner temperature at node {node}')
            prescribed[int(node)] = float(value)
    flux = {tag: float(v) for tag, v in p.get('outward_flux_w_m2', {}).items()}
    convection = {tag: (float(v['h_w_m2k']), float(v['ambient_temperature_k']))
                  for tag, v in p.get('convection', {}).items()}
    return dict(conductivity=conductivity, dirichlet=dict(sorted(prescribed.items())),
                heat_source=source, outward_flux=flux, convection=convection)


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


def run_region_thermal(doc, verbose=True):
    from galerkin.thermal import solve_steady_heat
    doc.validate()
    doc = doc.copy()
    doc.validate()
    name, _ = doc.sole_physics()
    t0 = time.perf_counter()
    mesh, region_materials, tri = build_region_mesh(doc)
    kwargs = region_inputs(doc, mesh, region_materials)
    t_mesh = time.perf_counter()-t0
    calculation_json = json.dumps(doc.data, sort_keys=True, separators=(',', ':'), allow_nan=False)
    t0 = time.perf_counter()
    try:
        solution = solve_steady_heat(mesh, **kwargs)
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
    diagnostics = {'source_heat_w_per_m': source_heat,
                   'prescribed_outward_heat_w_per_m': float(G.sum()),
                   'convective_outward_heat_w_per_m': float(C.sum()),
                   'thermostat_outward_heat_w_per_m': -float(solution.reaction.sum()),
                   'outward_heat_w_per_m': outward,
                   'heat_balance_defect_w_per_m': outward-source_heat,
                   'normalized_heat_balance_defect': abs(outward-source_heat)/scale,
                   'free_residual_max_w_per_m': float(np.max(abs(solution.residual[free]))) if len(free) else 0.,
                   'mesh_min_angle_deg': float(tri.min_angle())}
    log = [region_summary(doc),
           f'mesh: {mesh.num_nodes} nodes, {len(mesh.triangles)} triangles, regions {mesh.region_names}',
           *([f'shapes fully covered by later shapes (no triangles): {covered_shapes(doc, mesh)}']
             if covered_shapes(doc, mesh) else []),
           f'temperature K: {solution.temperature.min():.12g} to {solution.temperature.max():.12g}',
           f'source {source_heat:.12g} W/m; signed outward {outward:.12g} W/m of depth']
    if verbose:
        print('\n'.join(log))
    result = RegionThermalRunResult(doc, mesh, solution, fixed,
                                    np.array([kwargs['dirichlet'][int(i)] for i in fixed], dtype=float),
                                    diagnostics, {'mesh': t_mesh, 'solve': t_solve}, log)
    result.region_materials = region_materials
    result.summary()
    return result
