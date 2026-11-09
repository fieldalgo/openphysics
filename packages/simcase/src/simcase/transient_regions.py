# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Transient heat documents with named material regions (EM-style geometry).

A thermal.transient2d document whose geometry has ``background``/``shapes``
takes conductivity and volumetric heat capacity from ``materials``. Initial
data (uniform or affine), sampled side Dirichlet data and the requested-time
contract are those of the rectangle documents. A version 1 ``axisymmetric``
component is a body of revolution: the mesh is (r, z), galerkin's axisymmetric
measure solves it and the result carries its own identifiers with full-revolution
rates in W (``_w``), heat content in J and quadratic functional in J K.
See docs/packages/simcase/thermal_regions2d.md.
"""
import copy
from dataclasses import dataclass, field
import json
import time

import numpy as np

from . import views
from .schema import DocumentError
from .thermal_regions import (_named_sides, build_region_mesh, covered_shapes, exterior_sides,
                              has_region_geometry, is_axisymmetric, region_geometry, region_materials_table,
                              region_mesh_settings, region_source)
from .transient_thermal import TransientThermalRunResult, _FIELD_SPEC
from .transient_thermal_contract import (PHYSICS, SIDES, _agree, _array, _initial_value, _number,
                                         _object, _samples)

RESULT_FORMAT = 'thermal.transient2d-regions-result-v1'
FIELD_LAYOUT = 'thermal2d-transient-p1-node-cell-regions-v1'
#: the result identifiers of an axisymmetric run: full-revolution rates in W, content in J,
#: never the Cartesian per-metre identifiers (docs/packages/galerkin/thermal_axisymmetric.md)
AXISYMMETRIC_RESULT_FORMAT = 'thermal.axisymmetric-transient-regions-result-v1'
AXISYMMETRIC_FIELD_LAYOUT = 'thermal-axisymmetric-transient-p1-node-cell-regions-v1'


def is_transient_region_thermal(data):
    """A transient heat document that declares region geometry."""
    return has_region_geometry(data, PHYSICS)


def validate_transient_region_thermal(doc):
    from . import units
    d = doc.data
    top = {'openphysics', 'name', 'units', 'geometry', 'materials', 'physics', 'mesh', 'study', 'results'}
    _object(d, top, 'document', top)
    if d['openphysics'] != '0.2':
        raise DocumentError('openphysics: expected format string "0.2"')
    if not isinstance(d['name'], str):
        raise DocumentError('name: expected a string')
    _object(d['units'], {'length', 'temperature', 'time'}, 'units', {'length', 'temperature', 'time'})
    if d['units']['temperature'] != 'K' or d['units']['time'] != 's':
        raise DocumentError('thermal.transient2d requires temperature="K" and time="s"')
    try:
        doc.scale = units.resolve(d['units'])
    except (units.UnitError, OverflowError, TypeError, ValueError) as exc:
        raise DocumentError(f'units: {exc}') from exc
    names = region_geometry(doc)
    region_materials_table(doc, ('conductivity_w_mk', 'volumetric_heat_capacity_j_m3k'), 'transient heat')
    region_mesh_settings(doc)
    _object(d['study'], {'type', 'time_s'}, 'study', {'type', 'time_s'})
    if d['study']['type'] != 'transient':
        raise DocumentError('study.type: expected "transient"')
    times = _array(d['study']['time_s'], 'study.time_s')
    if len(times) < 2 or times[0] < 0:
        raise DocumentError('study.time_s: need at least two nonnegative increasing seconds')
    for i, (a, b) in enumerate(zip(times, times[1:]), 1):
        _number(b-a, f'study.time_s step[{i}]', positive=True)
    if not isinstance(d['physics'], dict) or len(d['physics']) != 1:
        raise DocumentError('physics: exactly one transient heat entry is required')
    name, p = next(iter(d['physics'].items()))
    if not isinstance(name, str) or not name.isidentifier():
        raise DocumentError('physics name must be an identifier')
    where = f'physics.{name}'
    for key in ('conductivity_w_mk', 'volumetric_heat_capacity_j_m3k'):
        if key in p:
            raise DocumentError(f'{where}.{key}: a region document takes {key} from materials')
    keys = {'type', 'initial_temperature_k', 'dirichlet_temperature_k', 'heat_source_w_m3'}
    _object(p, keys, where, {'type', 'initial_temperature_k', 'dirichlet_temperature_k'})
    region_source(p, names, where)
    spec = p['initial_temperature_k']
    initial_path = where+'.initial_temperature_k'
    if isinstance(spec, dict):
        _object(spec, {'type', 'origin_temperature_k', 'gradient_k_per_m'}, initial_path,
                {'type', 'origin_temperature_k', 'gradient_k_per_m'})
        if spec['type'] != 'affine':
            raise DocumentError(f'{initial_path}.type: expected affine')
        _number(spec['origin_temperature_k'], initial_path+'.origin_temperature_k')
        _array(spec['gradient_k_per_m'], initial_path+'.gradient_k_per_m', 2)
    else:
        _number(spec, initial_path)
    dom = doc.domain
    # the corners come back from micrometres as the mesh nodes do (views.region_corner_m)
    x0, y0, x1, y1 = (views.region_corner_m(dom[k], doc.scale) for k in ('xmin', 'ymin', 'xmax', 'ymax'))
    corners = ((x0, y0), (x0, y1), (x1, y0), (x1, y1))
    initial = [_number(_initial_value(spec, x, y, (x0, y0)), initial_path+' at domain corner')
               for x, y in corners]
    side_corners = {'left': (0, 1), 'right': (2, 3), 'bottom': (0, 2), 'top': (1, 3)}
    boundary = p['dirichlet_temperature_k']
    from .thermal_regions import boundary_names
    tags, outside, inside = boundary_names(doc)
    # an axisymmetric domain at r = 0 has the axis in place of left: both refused by name
    _, sides = exterior_sides(doc)
    _named_sides(boundary, set(sides) | tags | outside | inside, where+'.dirichlet_temperature_k')
    sampled = {tag: _samples(value, times, where+'.dirichlet_temperature_k.'+tag)
               for tag, value in boundary.items()}
    for horizontal in ('left', 'right'):
        for vertical in ('bottom', 'top'):
            if horizontal in sampled and vertical in sampled and sampled[horizontal] != sampled[vertical]:
                raise DocumentError(f'{where}.dirichlet_temperature_k: conflicting corner '
                                    f'temperatures on {horizontal}/{vertical}')
    for tag, values in sampled.items():
        if tag in side_corners and any(not _agree(initial[i], values[0]) for i in side_corners[tag]):
            raise DocumentError(f'{where}.dirichlet_temperature_k.{tag}: initial t0 mismatch '
                                '(32 eps bound); no projection')
    _object(d['results'], {'save_fields', 'plots'}, 'results', {'save_fields', 'plots'})
    if any(not isinstance(d['results'][key], bool) for key in ('save_fields', 'plots')):
        raise DocumentError('results.save_fields and results.plots must be booleans')
    if d['results']['plots']:
        raise DocumentError('results.plots: transient heat is headless; plots=true unsupported')
    doc.notes = []


def transient_region_summary(doc):
    name, p = doc.sole_physics()
    lines = [f'{doc["name"]} (openphysics 0.2)',
             f'  physics {name}: {PHYSICS}, {len(doc["study"]["time_s"])} explicit times in s, '
             'named material regions',
             f'  domain {doc.domain} {doc.length_unit}; mesh size {doc["mesh"]["size"]} {doc.length_unit}',
             f'  background: {doc.background["material"]}']
    lines += [f'  shape {s["name"]}: {s["type"]}, {s["material"] if s["material"] is not None else "void (hole)"}'
              for s in doc.regions()]
    lines += [f'  material {m}: k={v.get("conductivity_w_mk")} W/(m K), '
              f'c={v.get("volumetric_heat_capacity_j_m3k")} J/(m^3 K)' for m, v in doc['materials'].items()]
    if is_axisymmetric(doc):
        lines.append('  axisymmetric (r, z): full-revolution rates in W, heat content in J')
    lines.append('  output: SI time/node/cell histories, triangle regions; rates at interval ends only')
    return '\n'.join(lines)


def transient_region_inputs(doc, mesh, region_materials):
    """solve_transient_heat keyword arguments for a meshed region document (from its internal SI
    view, ``simcase.views.transient_region_heat``)."""
    name, _ = doc.sole_physics()
    where = f'physics.{name}'
    heat = views.transient_region_heat(doc)
    times = heat.time
    nodes = np.asarray(mesh.nodes, dtype=float)
    origin = views.region_origin_m(doc)
    spec = heat.initial_temperature
    with np.errstate(over='ignore', invalid='ignore'):
        initial = (np.full(len(nodes), spec) if not isinstance(spec, views.AffineTemperature)
                   else spec.origin_temperature+(nodes-origin)@spec.gradient)
    if not np.isfinite(initial).all():
        raise DocumentError('initial_temperature_k: nonfinite field at mesh nodes')
    sampled_nodes = {}
    for tag, values in heat.dirichlet.items():
        if tag not in mesh.boundary:
            raise DocumentError(f'{where}.dirichlet_temperature_k.{tag}: no mesh edge lies on {tag!r} (a side that '
                                'borders a void feature only)')
        for node in mesh.boundary[tag]:
            node = int(node)
            if node in sampled_nodes and sampled_nodes[node] != values:
                raise DocumentError(f'{where}.dirichlet_temperature_k.{tag}: node {node} already carries another '
                                    'temperature history from an overlapping boundary')
            if not _agree(float(initial[node]), values[0]):
                raise DocumentError(f'mesh.boundary.{tag}: initial t0 mismatch; no projection')
            sampled_nodes[node] = values

    def lookup(values):
        table = dict(zip(map(float, times), values))
        def at_time(time_s):
            if not isinstance(time_s, (int, float)) or isinstance(time_s, bool):
                raise ValueError('boundary callback expects one requested scalar time')
            try:
                return table[float(time_s)]
            except KeyError as exc:
                raise ValueError('boundary time not in requested samples; no interpolation') from exc
        return at_time

    boundary = {node: (values[0] if all(v == values[0] for v in values) else lookup(values))
                for node, values in sorted(sampled_nodes.items())}
    source = heat.heat_source
    if isinstance(source, dict):
        dropped = set(source)-set(mesh.region_names)
        if dropped:
            raise DocumentError(f'{where}.heat_source_w_m3: regions {sorted(dropped)} are not in the meshed '
                                'geometry (fully covered by later shapes or smaller than the sliver limit)')
        source = {r: float(source.get(r, 0.)) for r in mesh.region_names}
    else:
        source = float(source)
    return {'conductivity': {r: float(heat.conductivity[m]) for r, m in region_materials.items()},
            'volumetric_heat_capacity': {r: float(heat.volumetric_heat_capacity[m])
                                         for r, m in region_materials.items()},
            'time_s': times, 'initial_temperature_k': initial.copy(), 'dirichlet': boundary,
            'heat_source': source}


@dataclass(frozen=True)
class TransientRegionRunResult(TransientThermalRunResult):
    """Transient histories plus triangle regions; materials checked by region."""
    region_ids: np.ndarray = field(default=None, repr=False, compare=False)
    region_names: tuple = ()
    region_materials: dict = field(default_factory=dict)
    result_format = RESULT_FORMAT
    field_layout = FIELD_LAYOUT

    def __post_init__(self):
        super().__post_init__()
        ids = np.array(self.region_ids, copy=True)
        object.__setattr__(self, 'region_ids', np.frombuffer(ids.astype('<i8').tobytes(), dtype='<i8'))
        object.__setattr__(self, 'region_names', tuple(self.region_names))
        object.__setattr__(self, 'region_materials', dict(self.region_materials))

    def _raw_arrays(self):
        arrays = super()._raw_arrays()
        regions = np.array(self.region_ids, copy=True)
        if (regions.shape != (len(arrays['triangles']),) or regions.dtype.kind not in 'iu'
                or np.any(regions < 0) or np.any(regions >= len(self.region_names))):
            raise ValueError('transient triangle_regions: expected one valid region id per triangle')
        arrays['triangle_regions'] = regions.astype(np.int64)
        return arrays

    def _summary(self, arrays):
        self._validate_document_snapshot()
        self.doc.validate()
        name, p = self.doc.sole_physics()
        times = arrays['time_s']
        if not np.array_equal(times, np.asarray(self.doc['study']['time_s'])):
            raise ValueError('transient result time_s does not match document')
        materials = self.doc['materials']
        expected_k = {r: float(materials[m]['conductivity_w_mk']) for r, m in self.region_materials.items()}
        expected_c = {r: float(materials[m]['volumetric_heat_capacity_j_m3k'])
                      for r, m in self.region_materials.items()}
        if (self.solution.conductivity_w_mk != expected_k
                or self.solution.volumetric_heat_capacity_j_m3k != expected_c):
            raise ValueError('transient result materials do not match document')
        source = arrays['source_load_w_per_m'].sum(axis=1)
        storage = arrays['storage_rate_w_per_m'].sum(axis=1)
        reaction = arrays['reaction_w_per_m'].sum(axis=1)
        nodes, tri = arrays['nodes_m'], arrays['triangles']
        v = nodes[tri][:, 1:]-nodes[tri][:, :1]
        area = .5*(v[:, 0, 0]*v[:, 1, 1]-v[:, 0, 1]*v[:, 1, 0])
        regions = arrays['triangle_regions']
        spec = dict(_FIELD_SPEC, triangle_regions=('1', 'triangles', 'static'))
        result = {
            'name': self.doc['name'], 'physics_name': name, 'physics_type': PHYSICS,
            'result_format': RESULT_FORMAT, 'field_layout': FIELD_LAYOUT,
            'units': copy.deepcopy(self.doc['units']), 'mesh_length_unit': 'm',
            'field_units': {key: s[0] for key, s in spec.items()},
            'field_locations': {key: s[1] for key, s in spec.items()},
            'field_time_axes': {key: s[2] for key, s in spec.items()},
            'field_shapes': {key: list(a.shape) for key, a in arrays.items()},
            'region_names': list(self.region_names),
            'regions': {r: {'material': self.region_materials[r], 'triangles': int(np.sum(regions == i)),
                            'area_m2': float(area[regions == i].sum())}
                        for i, r in enumerate(self.region_names)},
            'materials': copy.deepcopy(materials),
            'mesh': {'nodes': len(nodes), 'triangles': len(tri), 'size': self.doc['mesh']['size'],
                     'min_angle_deg': self.doc['mesh']['min_angle'], 'size_unit': self.doc.length_unit},
            'study': {'type': 'transient', 'time_s': times.tolist()},
            'heat_source_w_m3': copy.deepcopy(p['heat_source_w_m3']),
            'dirichlet_nodes': len(arrays['dirichlet_node_ids']),
            'temperature_min_k': arrays['temperature_k'].min(axis=1).tolist(),
            'temperature_max_k': arrays['temperature_k'].max(axis=1).tolist(),
            'source_heat_w_per_m': source.tolist(),
            'storage_heat_w_per_m': storage.tolist(),
            'outward_heat_w_per_m': (-reaction).tolist(),
            'heat_balance_defect_w_per_m': (storage-source[1:]-reaction).tolist(),
            'heat_content_j_per_m': arrays['heat_content_j_per_m'].tolist(),
            'quadratic_functional_jk_per_m': arrays['quadratic_functional_jk_per_m'].tolist(),
            'rate_time_s': times[1:].tolist(),
            'reaction_sign': 'inward; outward thermostat heat = -sum(reaction)',
            'balance_equation': 'sum(storage)=sum(source at step end)+sum(reaction)',
            'heat_content_definition': 'H=1^T M T with the per-region capacity; J/m, chosen zero at 0 K',
            'quadratic_functional_definition': 'V=0.5 T^T M T; J K/m; not stored heat',
            'save_fields': self.doc['results']['save_fields'],
            'timings_s': dict(self.timings),
        }
        json.dumps(result, allow_nan=False)
        return result


_PER_METRE = {'_w_per_m': '_w', '_j_per_m': '_j', '_jk_per_m': '_jk'}
_UNITS = {'W/m': 'W', 'J/m': 'J', 'J K/m': 'J K'}


def _axisymmetric_name(key):
    """The field name of a full-revolution quantity: ``storage_rate_w_per_m`` becomes
    ``storage_rate_w``, ``heat_content_j_per_m`` ``heat_content_j``."""
    for suffix, replacement in _PER_METRE.items():
        if key.endswith(suffix):
            return key[:-len(suffix)]+replacement
    return key


def _cartesian_name(key):
    """The inverse of ``_axisymmetric_name`` for the keys of a transient region result."""
    for suffix, replacement in _PER_METRE.items():
        if key.endswith(replacement) and not key.endswith(suffix):
            return key[:-len(replacement)]+suffix
    return key


@dataclass(frozen=True)
class AxisymmetricTransientRegionRunResult(TransientRegionRunResult):
    """The result of an axisymmetric run: the same histories with the nodal rates in W over the
    full revolution, the heat content in J and the quadratic functional in J K, under their own
    result identifiers and ``_w``/``_j``/``_jk`` field names. The inherited ``_per_m`` attributes
    return the same arrays (the public read path of TransientThermalRunResult); the saved fields
    and the summary carry the full-revolution names and units only."""
    result_format = AXISYMMETRIC_RESULT_FORMAT
    field_layout = AXISYMMETRIC_FIELD_LAYOUT

    @property
    def source_load_w(self): return self.solution.source_load_w_per_m

    @property
    def reaction_w(self): return self.solution.reaction_w_per_m

    @property
    def residual_w(self): return self.solution.residual_w_per_m

    @property
    def storage_rate_w(self): return self.solution.storage_rate_w_per_m

    @property
    def heat_content_j(self): return self.solution.heat_content_j_per_m

    @property
    def quadratic_functional_jk(self): return self.solution.quadratic_functional_jk_per_m

    def _raw_arrays(self):
        arrays = super()._raw_arrays()
        return {_axisymmetric_name(key): a for key, a in arrays.items()}

    def _summary(self, arrays):
        if getattr(self.solution, 'coordinate_system', 'cartesian') != 'axisymmetric':
            raise ValueError('axisymmetric transient result requires an axisymmetric solution')
        result = super()._summary({_cartesian_name(key): a for key, a in arrays.items()})
        result['result_format'], result['field_layout'] = AXISYMMETRIC_RESULT_FORMAT, AXISYMMETRIC_FIELD_LAYOUT
        for table in ('field_units', 'field_locations', 'field_time_axes', 'field_shapes'):
            result[table] = {_axisymmetric_name(key): (_UNITS.get(v, v) if table == 'field_units' else v)
                             for key, v in result[table].items()}
        for key in ('source_heat_w_per_m', 'storage_heat_w_per_m', 'outward_heat_w_per_m',
                    'heat_balance_defect_w_per_m', 'heat_content_j_per_m', 'quadratic_functional_jk_per_m'):
            result[_axisymmetric_name(key)] = result.pop(key)
        result['heat_content_definition'] = ('H=1^T M T with the per-region capacity and the measure 2*pi*r; '
                                             'J over the full revolution, chosen zero at 0 K')
        result['quadratic_functional_definition'] = 'V=0.5 T^T M T; J K over the full revolution; not stored heat'
        result['coordinate_system'] = 'axisymmetric'
        result['nodal_heat_rate_unit'] = 'W'
        result['coordinates'] = '(r, z) in metres; volume measure 2*pi*r dr dz, full revolution'
        json.dumps(result, allow_nan=False)
        return result


def run_transient_region_thermal(doc, verbose=True, *, mesh_limits=None):
    from galerkin.transient_heat import solve_transient_heat
    doc.validate()
    given, doc = doc, doc.copy()
    doc.validate()
    name, _ = doc.sole_physics()
    started = time.perf_counter()
    mesh, region_materials, tri = build_region_mesh(doc, mesh_limits)
    # the hand-off's notes (slivers left out, raised circle counts) reach the caller's document
    given.notes.extend(n for n in doc.notes if n.startswith(('geometry.', 'mesh.controls:')) and n not in given.notes)
    inputs = transient_region_inputs(doc, mesh, region_materials)
    mesh_seconds = time.perf_counter()-started
    started = time.perf_counter()
    axisymmetric = is_axisymmetric(doc)
    try:
        solution = solve_transient_heat(mesh, **inputs,
                                        coordinate_system='axisymmetric' if axisymmetric else 'cartesian')
    except (ValueError, RuntimeError) as exc:
        raise ValueError(f'physics.{name} ({PHYSICS}): {exc}') from exc
    solve_seconds = time.perf_counter()-started
    covered = covered_shapes(doc, mesh)
    log = (doc.summary(), f'mesh: {mesh.num_nodes} nodes, {len(mesh.triangles)} triangles, '
           f'regions {mesh.region_names}',
           *([f'shapes fully covered by later shapes (no triangles): {covered}'] if covered else []),
           f'transient heat: {len(solution.time_s)} requested times; full histories retained',
           ('SI: K, flux W/m^2, nodal rates W (full revolution; axisymmetric (r, z)); H J; quadratic V J K'
            if axisymmetric else 'SI: K, flux W/m^2, nodal rates W/m depth; H J/m; quadratic V J K/m'))
    cls = AxisymmetricTransientRegionRunResult if axisymmetric else TransientRegionRunResult
    result = cls(doc, solution, {'mesh': mesh_seconds, 'solve': solve_seconds}, log,
                 np.array(mesh.regions, copy=True), tuple(mesh.region_names), dict(region_materials))
    result.summary()
    if verbose:
        print('\n'.join(log))
    return result
