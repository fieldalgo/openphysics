# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Transient heat documents with named material regions (EM-style geometry), format 0.3.

A thermal.transient2d document whose geometry has ``background``/``shapes`` (or a version 1
component with regions) takes thermal_conductivity and volumetric_heat_capacity from
``materials``. Initial data (uniform or affine), sampled prescribed temperatures and the
requested-time contract are those of the rectangle documents. A version 1 ``axisymmetric``
component is a body of revolution: the mesh is (r, z), galerkin's axisymmetric measure
solves it and the result carries its own identifiers with the full-revolution values under
their plain names (``generated_heat_rate`` in W, ``stored_heat`` in J,
``thermal_energy_functional`` in J K). See docs/packages/simcase/thermal_regions2d.md.
"""
import copy
from dataclasses import dataclass, field
import time

import numpy as np

from . import views
from .schema import DocumentError
from .thermal_regions import (NAMES_03, _refuse, _region_entry_03, boundary_names, build_region_mesh,
                              component_03, covered_shapes, default_boundaries_03, depth_03, exterior_sides,
                              handoff_03, has_region_geometry, is_axisymmetric, mesh_controls_03,
                              mesh_diagnostics_03, plain_name,
                              region_geometry_03, region_materials_table_03,
                              region_mesh_settings_03, region_source_03, sides_03)
from .transient_thermal import (BALANCE_EQUATION_03, FIELDS_03, FUNCTIONAL_DEFINITION_03, STORED_HEAT_DEFINITION_03,
                                TransientThermalRunResult)
from .transient_thermal_contract import (PHYSICS, _agree, _initial_03, _initial_value_03, _number, _samples_03,
                                         study_times_03)

RESULT_FORMAT = 'thermal.transient2d-regions-result-v2'
FIELD_LAYOUT = 'thermal2d-transient-p1-node-cell-regions-v2'
#: the result identifiers of an axisymmetric run: full-revolution values under their plain names
#: (docs/packages/galerkin/thermal_axisymmetric.md)
AXISYMMETRIC_RESULT_FORMAT = 'thermal.axisymmetric-transient-regions-result-v2'
AXISYMMETRIC_FIELD_LAYOUT = 'thermal-axisymmetric-transient-p1-node-cell-regions-v2'


def is_transient_region_thermal(data):
    """A transient heat document that declares region geometry."""
    return has_region_geometry(data, PHYSICS)


def validate_transient_region_thermal_03(doc):
    """thermal.transient2d on regions and axisymmetric regions, format 0.3: today's contract on
    SI values. Flux and convection on regions are not supported yet (refused by name)."""
    from fractions import Fraction
    name, p, where = _region_entry_03(doc, 'transient heat', {'type', 'initial_temperature', 'prescribed_temperature',
                                                              'heat_source_density'})
    region_mesh_settings_03(doc)
    times = study_times_03(doc)
    h = handoff_03(doc)
    names = region_geometry_03(doc, h)
    mesh_controls_03(doc, h)
    region_materials_table_03(doc, h, ('thermal_conductivity', 'volumetric_heat_capacity'), 'transient heat')
    region_source_03(p, names, where)
    sides = exterior_sides(h)[1]
    # an axisymmetric domain at r = 0 has the axis in place of left: both refused by name
    sides_03(p, name, sides, boundary_names(h), transient=True)
    spec = _initial_03(p['initial_temperature'], where+'.initial_temperature')
    # the corners come back from micrometres as the mesh nodes do (H17 a)
    base = component_03(doc)[0]
    x0, y0, x1, y1 = (float(Fraction(doc.pm(f'{base}.domain.{k}'), 10 ** 6)) * 1e-6
                      for k in ('xmin', 'ymin', 'xmax', 'ymax'))
    corners = ((x0, y0), (x0, y1), (x1, y0), (x1, y1))
    initial = [_number(_initial_value_03(spec, x, y, (x0, y0)), where+'.initial_temperature at domain corner')
               for x, y in corners]
    side_corners = {'left': (0, 1), 'right': (2, 3), 'bottom': (0, 2), 'top': (1, 3)}
    sampled = {tag: _samples_03(value, times, f'{where}.prescribed_temperature.{tag}')
               for tag, value in p['prescribed_temperature'].items()}
    for horizontal in ('left', 'right'):
        for vertical in ('bottom', 'top'):
            if horizontal in sampled and vertical in sampled and sampled[horizontal] != sampled[vertical]:
                _refuse(f'{where}.prescribed_temperature: conflicting corner temperatures on {horizontal}/{vertical}',
                        f'{where}.prescribed_temperature.{vertical}')
    for tag, values in sampled.items():
        if tag in side_corners and any(not _agree(initial[i], values[0]) for i in side_corners[tag]):
            _refuse(f'{where}.prescribed_temperature.{tag}: initial t0 mismatch (32 eps bound); no projection',
                    f'{where}.prescribed_temperature.{tag}')
    default_boundaries_03(doc, name, p, sides)
    if doc.si['results'].get('plots'):
        _refuse('results.plots: transient heat is headless; plots=true is not supported', 'results.plots')


def transient_region_summary_03(doc):
    """The summary text of a format 0.3 transient region heat document."""
    from .thermal import _authored
    from .thermal_regions import region_summary_03
    name, p = next(iter(doc.si['physics'].items()))
    where = f'physics.{name}'
    initial = p['initial_temperature']
    initial_text = ('affine from ' + _authored(doc, where + '.initial_temperature.reference_temperature')
                    if isinstance(initial, dict) else _authored(doc, where + '.initial_temperature'))
    times = doc.si['study']['time']
    lines = [f'  initial_temperature {initial_text}; study.time {_authored(doc, "study.time")}',
             '  rates at interval ends only']
    return region_summary_03(doc, f'{PHYSICS}, {len(times)} explicit times, named material regions', lines,
                             transient_region_versions_03(doc))


def transient_region_versions_03(doc):
    if is_axisymmetric(handoff_03(doc)):
        return AXISYMMETRIC_RESULT_FORMAT, AXISYMMETRIC_FIELD_LAYOUT
    return RESULT_FORMAT, FIELD_LAYOUT


def transient_region_inputs(doc, mesh, region_materials, heat=None, origin=None, names=None):
    """solve_transient_heat keyword arguments for a meshed format 0.3 region document, from its
    ``heat`` view (``views.transient_region_heat_03``) and lower corner ``origin`` in metres
    (``views.region_origin_03``). ``names`` maps the keys the messages name to the document's
    own keys (``thermal_regions.NAMES_03``)."""
    name, _ = doc.sole_physics()
    where = f'physics.{name}'
    key = (lambda k: k) if names is None else (lambda k: names.get(k, k))      # noqa: E731
    if heat is None or origin is None:
        raise TypeError('transient_region_inputs takes the heat inputs and origin of a format 0.3 document '
                        '(views.transient_region_heat_03, views.region_origin_03)')
    times = heat.time
    nodes = np.asarray(mesh.nodes, dtype=float)
    spec = heat.initial_temperature
    with np.errstate(over='ignore', invalid='ignore'):
        initial = (np.full(len(nodes), spec) if not isinstance(spec, views.AffineTemperature)
                   else spec.origin_temperature+(nodes-origin)@spec.gradient)
    if not np.isfinite(initial).all():
        raise DocumentError(f'{key("initial_temperature_k")}: nonfinite field at mesh nodes')
    sampled_nodes = {}
    for tag, values in heat.dirichlet.items():
        if tag not in mesh.boundary:
            raise DocumentError(f'{where}.{key("dirichlet_temperature_k")}.{tag}: no mesh edge lies on {tag!r} (a side '
                                'that borders a void feature only)')
        for node in mesh.boundary[tag]:
            node = int(node)
            if node in sampled_nodes and sampled_nodes[node] != values:
                raise DocumentError(f'{where}.{key("dirichlet_temperature_k")}.{tag}: node {node} already carries '
                                    'another temperature history from an overlapping boundary')
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
            raise DocumentError(f'{where}.{key("heat_source_w_m3")}: regions {sorted(dropped)} are not in the meshed '
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
    """Transient histories plus triangle regions (format 0.3); materials checked by region."""
    region_ids: np.ndarray = field(default=None, repr=False, compare=False)
    region_names: tuple = ()
    region_materials: dict = field(default_factory=dict)
    result_format = RESULT_FORMAT
    field_layout = FIELD_LAYOUT
    _components = ('x', 'y')
    _area = 'area'

    def __post_init__(self):
        super().__post_init__()
        ids = np.array(self.region_ids, copy=True)
        object.__setattr__(self, 'region_ids', np.frombuffer(ids.astype('<i8').tobytes(), dtype='<i8'))
        object.__setattr__(self, 'region_names', tuple(self.region_names))
        object.__setattr__(self, 'region_materials', dict(self.region_materials))

    @property
    def triangle_regions(self):
        return self.region_ids

    def _raw_arrays(self):
        arrays = super()._raw_arrays()
        regions = np.array(self.region_ids, copy=True)
        if (regions.shape != (len(arrays['triangles']),) or regions.dtype.kind not in 'iu'
                or np.any(regions < 0) or np.any(regions >= len(self.region_names))):
            raise ValueError('transient triangle_regions: expected one valid region id per triangle')
        arrays['triangle_regions'] = regions.astype(np.int64)
        return arrays

    @staticmethod
    def _name(key):
        return key

    @staticmethod
    def _text(text):
        return text

    def _summary(self, arrays):
        from . import results_common
        from .thermal import strict_series as ta, strict_timing, strict_value as vo
        from .steady_boundary_contract import REACTION_SIGN_03
        self._validate_document_snapshot()
        doc = self.doc
        doc.validate()
        name, p = next(iter(doc.si['physics'].items()))
        n = self._name
        times = arrays['time']
        if not np.array_equal(times, np.asarray(doc.si['study']['time'])):
            raise ValueError('transient result time does not match the document')
        materials = doc.si['materials']
        expected_k = {r: float(materials[m]['thermal_conductivity']) for r, m in self.region_materials.items()}
        expected_c = {r: float(materials[m]['volumetric_heat_capacity']) for r, m in self.region_materials.items()}
        if (self.solution.conductivity_w_mk != expected_k
                or self.solution.volumetric_heat_capacity_j_m3k != expected_c):
            raise ValueError('transient result materials do not match the document')
        source = arrays[n('generated_heat_rate_per_depth')].sum(axis=1)
        storage = arrays[n('heat_storage_rate_per_depth')].sum(axis=1)
        reaction = arrays[n('reaction_heat_rate_per_depth')].sum(axis=1)
        nodes, tri = arrays['node_coordinates'], arrays['triangles']
        v = nodes[tri][:, 1:]-nodes[tri][:, :1]
        area = .5*(v[:, 0, 0]*v[:, 1, 1]-v[:, 0, 1]*v[:, 1, 0])
        regions = arrays['triangle_regions']
        fields = {}
        for key, a in arrays.items():
            if key == 'triangle_regions':
                quantity, location, axis, components = None, 'triangles', None, None
            else:
                planar = key + '_per_depth' if key + '_per_depth' in FIELDS_03 else key
                quantity, location, axis, components = FIELDS_03[planar]
                if quantity is not None and planar != key:
                    quantity = plain_name(quantity)
                components = None if components is None else list(self._components)
            fields[key] = {'quantity': quantity, 'location': location, 'shape': list(a.shape), 'time_axis': axis,
                           'components': components}
        result = {
            'name': doc.si['name'], 'physics_name': name, 'physics_type': PHYSICS,
            **results_common.envelope(doc, result_format=self.result_format, field_layout=self.field_layout,
                                      timing_=strict_timing(self.timings)),
            **results_common.field_maps(fields),
            'region_names': list(self.region_names),
            'regions': {r: {'material': self.region_materials[r], 'triangles': int(np.sum(regions == i)),
                            self._area: vo(float(area[regions == i].sum()), self._area)}
                        for i, r in enumerate(self.region_names)},
            'materials': {m: {key: vo(v, key) if isinstance(v, (int, float)) and not isinstance(v, bool)
                              else copy.deepcopy(v) for key, v in spec.items()} for m, spec in materials.items()},
            'mesh': {'nodes': len(nodes), 'triangles': len(tri)},
            'study': {'type': 'transient', 'time': ta(times.tolist(), 'time')}}
        heat_source = p.get('heat_source_density')
        if isinstance(heat_source, dict):
            result['heat_source_density'] = {r: vo(value, 'heat_source_density') for r, value in heat_source.items()}
        elif heat_source is not None:
            result['heat_source_density'] = vo(heat_source, 'heat_source_density')
        totals = {'generated_heat_rate_per_depth': source, 'heat_storage_rate_per_depth': storage,
                  'outward_heat_rate_per_depth': -reaction,
                  'heat_rate_imbalance_per_depth': storage-source[1:]-reaction,
                  'stored_heat_per_depth': arrays[n('stored_heat_per_depth')],
                  'thermal_energy_functional_per_depth': arrays[n('thermal_energy_functional_per_depth')]}
        result.update({
            'prescribed_nodes': len(arrays['prescribed_node_ids']),
            'minimum_temperature': ta(arrays['temperature'].min(axis=1).tolist(), 'minimum_temperature'),
            'maximum_temperature': ta(arrays['temperature'].max(axis=1).tolist(), 'maximum_temperature'),
            **{n(key): ta(values.tolist(), n(key)) for key, values in totals.items()},
            'reaction_sign': self._text(REACTION_SIGN_03), 'balance_equation': self._text(BALANCE_EQUATION_03),
            'heat_content_definition': self._text(STORED_HEAT_DEFINITION_03),
            'quadratic_functional_definition': self._text(FUNCTIONAL_DEFINITION_03),
            'save_fields': doc.si['results']['save_fields']})
        self._finish(result)
        results_common.dumps_summary(result)            # finite JSON only
        return result

    def _finish(self, result):
        from . import results_common
        results_common.add_depth_totals(result, depth_03(self.doc))


@dataclass(frozen=True)
class AxisymmetricTransientRegionRunResult(TransientRegionRunResult):
    """The result of an axisymmetric run: the same histories with the full-revolution values
    under their plain names (rates in W, ``stored_heat`` in J, ``thermal_energy_functional`` in
    J K), under their own result identifiers; the per-depth names are refused."""
    result_format = AXISYMMETRIC_RESULT_FORMAT
    field_layout = AXISYMMETRIC_FIELD_LAYOUT
    _components = ('r', 'z')
    _area = 'meridional_area'

    def __getattr__(self, name):
        if name.endswith('_per_depth') and not name.startswith('_'):
            raise AttributeError(f'{name} is a per-depth name; an axisymmetric result reads {plain_name(name)}')
        planar = name + '_per_depth'
        if not name.startswith('_') and planar in FIELDS_03:
            return super().__getattr__(planar)
        return super().__getattr__(name)

    def _raw_arrays(self):
        return {plain_name(key): a for key, a in super()._raw_arrays().items()}

    @staticmethod
    def _name(key):
        return plain_name(key)

    @staticmethod
    def _text(text):
        return (text.replace('_per_depth', '').replace('J/m,', 'J over the full revolution,')
                .replace('J K/m', 'J K over the full revolution'))

    def _summary(self, arrays):
        if getattr(self.solution, 'coordinate_system', 'cartesian') != 'axisymmetric':
            raise ValueError('axisymmetric transient result requires an axisymmetric solution')
        return super()._summary(arrays)

    def _finish(self, result):
        result['coordinate_system'] = 'axisymmetric'
        result['coordinates'] = '(r, z) in metres; volume measure 2*pi*r dr dz, full revolution'


def run_transient_region_thermal(doc, verbose=True, *, mesh_limits=None):
    from galerkin.transient_heat import solve_transient_heat
    from .thermal import log_lines_03
    doc.validate()
    given, doc = doc, doc.copy()
    doc.validate()
    name, _ = doc.sole_physics()
    started = time.perf_counter()
    h = handoff_03(doc)
    mesh, region_materials, tri = build_region_mesh(h, mesh_limits)
    base = component_03(doc)[0]
    # the mesher's findings reach the caller's document as coded diagnostics
    for target in (given, doc):
        mesh_diagnostics_03(target, base, h.notes)
    inputs = transient_region_inputs(doc, mesh, region_materials, views.transient_region_heat_03(doc),
                                     views.region_origin_03(doc, base), NAMES_03)
    mesh_seconds = time.perf_counter()-started
    started = time.perf_counter()
    axisymmetric = is_axisymmetric(h)
    try:
        solution = solve_transient_heat(mesh, **inputs,
                                        coordinate_system='axisymmetric' if axisymmetric else 'cartesian')
    except (ValueError, RuntimeError) as exc:
        raise ValueError(f'physics.{name} ({PHYSICS}): {exc}') from exc
    solve_seconds = time.perf_counter()-started
    covered = covered_shapes(h, mesh)
    printed = (doc.summary(), f'mesh: {mesh.num_nodes} nodes, {len(mesh.triangles)} triangles, '
               f'regions {mesh.region_names}',
               *([f'shapes fully covered by later shapes (no triangles): {covered}'] if covered else []),
               f'transient heat: {len(solution.time_s)} requested times; full histories retained')
    log = tuple(log_lines_03(doc, printed))
    cls = AxisymmetricTransientRegionRunResult if axisymmetric else TransientRegionRunResult
    result = cls(doc, solution, {'mesh': mesh_seconds, 'solve': solve_seconds}, log,
                 np.array(mesh.regions, copy=True), tuple(mesh.region_names), dict(region_materials))
    result.summary()
    if verbose:
        print('\n'.join(printed))
    return result
