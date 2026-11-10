# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Strict headless adapters for the existing electric/Joule solvers: rectangle documents here,
region documents in :mod:`simcase.electric_regions` and :mod:`simcase.joule_regions`.

The three kinds read ``"openphysics": "0.3"`` (units batch C6; phase-2 spec sections 4.3 to 4.5):
values carry their units, keys are registry names, and a format 0.2 document is refused by
name. ``inward_current_density`` and ``inward_heat_flux`` are positive into the body; galerkin
still receives the outward values ``0.0 - value`` (hazard H1). Results save their arrays under
registry names with the summary of section 5.3.2: numeric balances under ``balance``, every
coded diagnostic under ``diagnostics``.
"""
import copy
import time
from dataclasses import asdict

import numpy as np

from .schema import DocumentError
from .steady_boundary_contract import SIDES, boundary_kwargs, natural_conditions_03, rect_geometry_03, rectangle_03
from .thermal import _OwnedOutput, _authored, model_bytes_03, log_lines_03
from . import results_common, views
from .registry import PhysicsKind, register
from .electric_regions import (FIELD_LAYOUT as REGION_FIELD_LAYOUT, is_region_electric, refuse_region_joule,
                               region_summary, run_region_electric, validate_region_electric)
from . import joule_regions

TYPES = {'electric.steady2d', 'joule.steady2d', 'joule.temperature2d'}
FIELD_LAYOUT = 'electric-joule2d-p1-v2'
MAX_TRIANGLES = 200_000
_FORMAT_02 = ('format 0.2 electric and Joule documents are not read: units now travel with each value ("1 V", '
              '"2 S/m", "300 K") and the geometry declares its length_unit. Write "openphysics": "0.3" '
              '(docs/packages/simcase/electric_joule.md)')

#: saved array -> (registry quantity, or None for a structural array; location; components)
FIELDS = {
    'node_coordinates': ('node_coordinates', 'nodes', ['x', 'y']),
    'triangles': (None, 'triangle_connectivity', None),
    'triangle_regions': (None, 'triangles', None),
    'electric_potential': ('electric_potential', 'nodes', None),
    'electric_field': ('electric_field', 'triangle_centroids', ['x', 'y']),
    'current_density': ('current_density', 'triangle_centroids', ['x', 'y']),
    'electrical_conductivity': ('electrical_conductivity', 'triangle_centroids', None),
    'joule_power_density': ('joule_power_density', 'triangle_centroids', None),
    'joule_power_per_depth': ('joule_power_per_depth', 'nodes', None),
    'reaction_current_per_depth': ('reaction_current_per_depth', 'nodes', None),
    'outward_prescribed_current_per_depth': ('outward_prescribed_current_per_depth', 'nodes', None),
    'residual_current_per_depth': ('residual_current_per_depth', 'nodes', None),
    'electric_prescribed_node_ids': (None, 'electric_prescribed_nodes', None),
    'prescribed_electric_potential': ('prescribed_electric_potential', 'electric_prescribed_nodes', None),
    'temperature': ('temperature', 'nodes', None),
    'heat_flux': ('heat_flux', 'triangle_centroids', ['x', 'y']),
    'generated_heat_rate_per_depth': ('generated_heat_rate_per_depth', 'nodes', None),
    'reaction_heat_rate_per_depth': ('reaction_heat_rate_per_depth', 'nodes', None),
    'residual_heat_rate_per_depth': ('residual_heat_rate_per_depth', 'nodes', None),
    'outward_prescribed_heat_rate_per_depth': ('outward_prescribed_heat_rate_per_depth', 'nodes', None),
    'ambient_convective_heat_rate_per_depth': ('ambient_convective_heat_rate_per_depth', 'nodes', None),
    'outward_convective_heat_rate_per_depth': ('outward_convective_heat_rate_per_depth', 'nodes', None),
    'applied_heat_rate_per_depth': ('applied_heat_rate_per_depth', 'nodes', None),
    'thermal_prescribed_node_ids': (None, 'thermal_prescribed_nodes', None),
    'prescribed_temperature': ('prescribed_temperature', 'thermal_prescribed_nodes', None),
    'evaluation_temperature': ('evaluation_temperature', 'nodes', None),
}
#: galerkin's electric result attribute of each electric array
ELECTRIC_ARRAYS = (('electric_potential', 'potential'), ('electric_field', 'electric_field'),
                   ('current_density', 'current_density'), ('electrical_conductivity', 'conductivity'),
                   ('joule_power_density', 'joule_heating'), ('joule_power_per_depth', 'joule_load'),
                   ('reaction_current_per_depth', 'reaction'),
                   ('outward_prescribed_current_per_depth', 'prescribed_outward_load'),
                   ('residual_current_per_depth', 'residual'))
#: galerkin's heat result attribute of each heat-stage array
HEAT_ARRAYS = (('temperature', 'temperature'), ('heat_flux', 'heat_flux'),
               ('generated_heat_rate_per_depth', 'load'), ('reaction_heat_rate_per_depth', 'reaction'),
               ('residual_heat_rate_per_depth', 'residual'),
               ('outward_prescribed_heat_rate_per_depth', 'prescribed_outward_load'),
               ('ambient_convective_heat_rate_per_depth', 'ambient_load'),
               ('outward_convective_heat_rate_per_depth', 'convective_outward'),
               ('applied_heat_rate_per_depth', 'system_rhs'))
#: ``JouleIteration`` field -> (column name, registry quantity, or None for a bare count)
ITERATION_COLUMNS = (
    ('iteration', 'iteration_count', None), ('temperature_defect', 'temperature_change', 'temperature_change'),
    ('conductivity_defect', 'relative_electrical_conductivity_change', 'relative_electrical_conductivity_change'),
    ('minimum_temperature', 'minimum_temperature', 'minimum_temperature'),
    ('maximum_temperature', 'maximum_temperature', 'maximum_temperature'),
    ('electric_free_residual', 'maximum_residual_current_per_depth', 'maximum_residual_current_per_depth'),
    ('thermal_free_residual', 'maximum_residual_heat_rate_per_depth', 'maximum_residual_heat_rate_per_depth'),
    ('nonlinear_heat_residual', 'relative_residual', 'relative_residual'),
    ('current_balance', 'current_imbalance_per_depth', 'current_imbalance_per_depth'),
    ('supplied_power_per_length', 'inward_electric_power_per_depth', 'inward_electric_power_per_depth'),
    ('joule_power_per_length', 'joule_power_per_depth', 'joule_power_per_depth'),
    ('outward_heat_per_length', 'outward_heat_rate_per_depth', 'outward_heat_rate_per_depth'),
    ('electric_power_defect', 'electric_power_imbalance_per_depth', 'electric_power_imbalance_per_depth'),
    ('heat_power_defect', 'heat_rate_imbalance_per_depth', 'heat_rate_imbalance_per_depth'))


def is_electric_joule(data):
    return isinstance(data, dict) and isinstance(data.get('physics'), dict) and any(
        isinstance(p, dict) and p.get('type') in TYPES for p in data['physics'].values())


def is_region_document(data):
    """An electric or steady Joule document on named material regions."""
    return is_region_electric(data) or joule_regions.is_region_joule(data)


def _refuse(message, path=None, code='E-CONTRACT'):
    """A coded refusal; a message of another code than E-CONTRACT does not repeat its path."""
    if code != 'E-CONTRACT' and path and message.startswith(path + ': '):
        message = message[len(path) + 2:]
    raise DocumentError(message, path=path, code=code)


# -- slots (format 0.3) ---------------------------------------------------------------------------

_MODEL_REFUSED = ('this kind takes one constant value such as "2 S/m"; a conductivity model needs an evaluation '
                  'temperature, which only joule.temperature2d has')


#: an outward flux as an input key: inputs are inward_ (the outward value negated)
_OUTWARD_INPUT = ('inputs are inward_: write {} (positive into the body, so an outward value is written negated, '
                  'such as "-2 {}")')


def electric_slots():
    """The physics slots of the three kinds (``simcase.slots``), data only."""
    out = []
    for kind in sorted(TYPES):
        p = 'physics.*{' + kind + '}'

        def q(key, quantity, forms=('QS', 'AV'), slot_kind='quantity', **extra):
            return {'pattern': f'{p}.{key}', 'kind': slot_kind, 'quantity': quantity, 'forms': list(forms), **extra}

        def obj(key, **extra):
            return {'pattern': f'{p}.{key}', 'kind': 'structural', 'forms': ['OBJECT'], **extra}

        def refused(key, message, code='E-CONTRACT'):
            return {'pattern': f'{p}.{key}', 'kind': 'refused', 'code': code, 'message': message}

        joule = kind != 'electric.steady2d'
        out += [{'pattern': f'{p}.type', 'kind': 'enum', 'values': [kind], 'required': True},
                obj('prescribed_electric_potential', required=True),
                q('prescribed_electric_potential.*', 'prescribed_electric_potential'),
                obj('inward_current_density'), q('inward_current_density.*', 'inward_current_density'),
                refused('inward_current', 'a terminal total is not supported; give inward_current_density'),
                refused('inward_current_per_depth', 'a terminal total is not supported; give inward_current_density'),
                refused('outward_current_density', _OUTWARD_INPUT.format('inward_current_density', 'A/m^2'),
                        'E-KEY-UNKNOWN')]
        if kind == 'joule.temperature2d':
            m = 'electrical_conductivity'
            out += [q(m, 'electrical_conductivity', ('MODEL',), 'material_property', required=True),
                    {'pattern': f'{p}.{m}.model', 'kind': 'enum', 'values': ['linear_resistivity'], 'required': True},
                    q(f'{m}.reference_conductivity', 'reference_conductivity', required=True),
                    q(f'{m}.reference_temperature', 'reference_temperature', required=True),
                    q(f'{m}.resistivity_temperature_coefficient', 'resistivity_temperature_coefficient',
                      required=True),
                    obj(f'{m}.valid', required=True),
                    q(f'{m}.valid.temperature', 'temperature', ('SL',), required=True, range=True),
                    refused(f'{m}.reference_resistivity', 'linear_resistivity takes reference_conductivity; '
                            'reference_resistivity is not read'),
                    refused(f'{m}.alpha', '"alpha" is not a key of linear_resistivity; write '
                            'resistivity_temperature_coefficient (the slope of the resistivity, 1/K)',
                            'E-KEY-UNKNOWN'),
                    refused(f'{m}.conductivity_temperature_coefficient', '"conductivity_temperature_coefficient" '
                            'is not a key of linear_resistivity, which takes resistivity_temperature_coefficient '
                            '(the slope of the resistivity)', 'E-KEY-UNKNOWN'),
                    q('initial_temperature', 'initial_temperature', required=True),
                    obj('iteration', required=True),
                    q('iteration.relaxation_factor', 'relaxation_factor', ('BD', 'AV'), default=0.5,
                      default_reason='dimensionless default: the Picard relaxation'),
                    q('iteration.temperature_tolerance', 'temperature_tolerance', required=True),
                    q('iteration.relative_tolerance', 'relative_tolerance', ('BD', 'AV'), default=1e-10,
                      default_reason='dimensionless default of the nonlinear solve'),
                    q('iteration.iteration_limit', 'iteration_limit', ('BC',), default=100,
                      default_reason='count default of the nonlinear solve')]
        else:
            out.append(q('electrical_conductivity', 'electrical_conductivity', slot_kind='material_property',
                         model_message=_MODEL_REFUSED))
        if joule:
            out += [refused('outward_heat_flux', _OUTWARD_INPUT.format('inward_heat_flux', 'W/m^2'), 'E-KEY-UNKNOWN'),
                    q('thermal_conductivity', 'thermal_conductivity', slot_kind='material_property'),
                    obj('prescribed_temperature'), q('prescribed_temperature.*', 'prescribed_temperature'),
                    obj('inward_heat_flux'), q('inward_heat_flux.*', 'inward_heat_flux'),
                    obj('convection'), obj('convection.*'),
                    q('convection.*.heat_transfer_coefficient', 'heat_transfer_coefficient', required=True),
                    q('convection.*.ambient_temperature', 'ambient_temperature', required=True),
                    refused('heat_source_density', 'a Joule document is heated by its current only; an '
                            'additional heat source is not supported')]
    reads = {'electric.steady2d': ['electrical_conductivity'],
             'joule.steady2d': ['electrical_conductivity', 'thermal_conductivity'], 'joule.temperature2d': []}
    results = {'save_fields': True, 'plots': False}
    out += [{'pattern': 'materials.*', 'kind': 'override', 'library': 'none', 'reads': reads},
            {'pattern': 'name', 'kind': 'override', 'default': 'untitled',
             'default_reason': 'structural default: the document has no name'},
            {'pattern': 'results', 'kind': 'override', 'default': results,
             'default_reason': 'structural default of electric and Joule documents'},
            {'pattern': 'results.save_fields', 'kind': 'override', 'default': True,
             'default_reason': 'structural default of electric and Joule documents'},
            {'pattern': 'results.plots', 'kind': 'override', 'default': False,
             'default_reason': 'structural default of electric and Joule documents (headless)'},
            {'pattern': 'study', 'kind': 'override', 'default': {'type': 'single'},
             'default_reason': 'structural default: one steady solve'}]
    return tuple(out)


# -- validation (format 0.3) ----------------------------------------------------------------------

def conductivity_model_03(spec):
    """galerkin's ``ConductivityModel`` of a validated ``linear_resistivity`` model (SI values):
    sigma(T) = reference_conductivity / (1 + coefficient (T - reference_temperature))."""
    from galerkin.temperature_joule_heating import ConductivityModel
    sigma, reference = spec['reference_conductivity'], spec['reference_temperature']
    alpha = spec['resistivity_temperature_coefficient']
    lo, hi = spec['valid']['temperature']
    return ConductivityModel(lambda t: sigma/(1.+alpha*(t-reference)), (lo, hi))


def _model_checks(spec, path):
    """The checks of today's conductivity model on SI values: a positive reference conductivity,
    the reference temperature inside the valid range and a positive conductivity at both ends."""
    where = f'{path}.electrical_conductivity'
    sigma, reference = spec['reference_conductivity'], spec['reference_temperature']
    alpha = spec['resistivity_temperature_coefficient']
    lo, hi = spec['valid']['temperature']
    if not sigma > 0:
        _refuse('reference_conductivity: expected a positive conductivity', f'{where}.reference_conductivity',
                'E-DOMAIN')
    if not lo <= reference <= hi:
        _refuse(f'{where}: the reference_temperature must lie inside valid.temperature', f'{where}.reference_temperature',
                'E-OUTSIDE-VALID')
    for t in (lo, hi):
        denominator = 1.+alpha*(t-reference)
        if not (denominator > 0 and sigma/denominator > 0 and np.isfinite(sigma/denominator)):
            _refuse(f'{where}: the conductivity at the valid.temperature bound {t!r} K is not positive and finite '
                    '(1 + resistivity_temperature_coefficient (T - reference_temperature) must stay positive)',
                    f'{where}.resistivity_temperature_coefficient')


def _entry_03(doc):
    """``(name, SI entry, path, kind)`` of the one physics entry."""
    doc.sole_physics()
    name, p = next(iter(doc.si['physics'].items()))
    if not isinstance(name, str) or not name.isidentifier():
        _refuse('physics: name must be an identifier', f'physics.{name}')
    return name, p, f'physics.{name}', p['type']


def _sides_of(table, path, key):
    extra = sorted(set(table) - set(SIDES))
    if extra:
        _refuse(f'{path}.{key}: unsupported keys {extra}; a rectangle takes {list(SIDES)}', f'{path}.{key}.{extra[0]}',
                'E-SELECTION-UNKNOWN')


def default_electric_boundaries_03(doc, name, p, sides):
    """``I-DEFAULT-BOUNDARY`` for each exterior side that no potential or current names: it is
    electrically insulating."""
    from physmat.units import Diagnostic
    named = set(p.get('prescribed_electric_potential', {})) | set(p.get('inward_current_density', {}))
    for side in sides:
        if side not in named:
            where = f'physics.{name}.inward_current_density.{side}'
            doc.diagnostics.append(Diagnostic('I-DEFAULT-BOUNDARY', where, f'side {side!r} has no condition: it is '
                                              'electrically insulating (inward_current_density 0 A/m^2)'))


def single_study_03(doc, kind):
    if doc.si['study'] != {'type': 'single'}:
        _refuse(f'study: {kind} supports only {{"type": "single"}}', 'study.type')
    if doc.si['results'].get('plots'):
        _refuse(f'results.plots: {kind} is headless; plots=true is not supported', 'results.plots')


def validate_rectangle_03(doc):
    """The three kinds on a rectangle (flat, or a homogeneous version 1 component, D-1): the checks
    of today's contract on SI values."""
    name, p, path, kind = _entry_03(doc)
    joule = kind != 'electric.steady2d'
    required = ['electrical_conductivity', 'prescribed_electric_potential']
    if joule:
        required += ['thermal_conductivity', 'prescribed_temperature']
    homogeneous = ('electrical_conductivity and thermal_conductivity are homogeneous' if joule
                   else 'electrical_conductivity is homogeneous')
    rectangle_03(doc, kind, tuple(required), noun='electric' if not joule else 'Joule', homogeneous=homogeneous)
    nx, ny = doc.si['mesh']['subdivision_count']
    if 2*nx*ny > MAX_TRIANGLES:
        _refuse(f'mesh.subdivision_count: at most {MAX_TRIANGLES} triangles supported', 'mesh.subdivision_count',
                'E-DOMAIN')
    single_study_03(doc, kind)
    potentials = p['prescribed_electric_potential']
    _sides_of(potentials, path, 'prescribed_electric_potential')
    if not potentials:
        _refuse(f'{path}.prescribed_electric_potential: at least one side potential is required; gauge-only inputs '
                'are unsupported', f'{path}.prescribed_electric_potential')
    for a in ('left', 'right'):
        for b in ('bottom', 'top'):
            if a in potentials and b in potentials and potentials[a] != potentials[b]:
                _refuse(f'{path}.prescribed_electric_potential: conflicting potential at the shared corner {a}/{b}',
                        f'{path}.prescribed_electric_potential.{b}')
    current = p.get('inward_current_density', {})
    _sides_of(current, path, 'inward_current_density')
    overlap = sorted(set(current) & set(potentials))
    if overlap:
        _refuse(f'{path}: a current condition overlaps a fixed potential side ({overlap[0]})',
                f'{path}.inward_current_density.{overlap[0]}')
    if kind != 'joule.temperature2d' and not p['electrical_conductivity'] > 0:
        _refuse('electrical_conductivity: expected a positive conductivity', f'{path}.electrical_conductivity',
                'E-DOMAIN')
    default_electric_boundaries_03(doc, name, p, SIDES)
    if not joule:
        return
    temperatures = p['prescribed_temperature']
    _sides_of(temperatures, path, 'prescribed_temperature')
    for a in ('left', 'right'):
        for b in ('bottom', 'top'):
            if a in temperatures and b in temperatures and temperatures[a] != temperatures[b]:
                _refuse(f'{path}.prescribed_temperature: conflicting corner temperatures on {a}/{b}',
                        f'{path}.prescribed_temperature.{b}')
    flux, convection = natural_conditions_03(p, path, temperatures)
    if not temperatures and not any(h > 0 for h, _ in convection.values()):
        _refuse(f'{path}: requires a prescribed-temperature or positive-convection anchor; pure Neumann is '
                'unsupported', f'{path}.prescribed_temperature', 'E-KEY-MISSING')
    from .thermal_regions import default_boundaries_03
    default_boundaries_03(doc, name, p, SIDES)
    if kind == 'joule.temperature2d':
        spec = p['electrical_conductivity']
        _model_checks(spec, path)
        lo, hi = spec['valid']['temperature']
        given = [('initial_temperature', p['initial_temperature']),
                 *((f'prescribed_temperature.{tag}', t) for tag, t in temperatures.items()),
                 *((f'convection.{tag}.ambient_temperature', c['ambient_temperature'])
                   for tag, c in p.get('convection', {}).items())]
        for where, t in given:
            if not lo <= t <= hi:
                _refuse(f'{where}: {t!r} K lies outside the conductivity model\'s valid.temperature [{lo!r}, {hi!r}] K',
                        f'{path}.{where}', 'E-OUTSIDE-VALID')
        iteration = p['iteration']
        if not iteration['relaxation_factor'] <= 1:
            _refuse('relaxation_factor: this kind takes 0 < relaxation_factor <= 1', f'{path}.iteration.relaxation_factor',
                    'E-DOMAIN')
        if not iteration['iteration_limit'] >= 1:
            _refuse('iteration_limit: expected at least one iteration', f'{path}.iteration.iteration_limit', 'E-DOMAIN')


def validate_electric_joule(doc):
    """Format 0.3 rectangles and regions. A format 0.2 document is refused by name."""
    if doc.si is None:
        raise DocumentError(_FORMAT_02, path='openphysics', code='E-FORMAT')
    refuse_region_joule(doc)
    if is_region_electric(doc.data):
        validate_region_electric(doc)
    elif joule_regions.is_region_joule(doc.data):
        joule_regions.validate_region_joule(doc)
    else:
        validate_rectangle_03(doc)


# -- summary text ---------------------------------------------------------------------------------

def rectangle_summary_03(doc):
    name, p, where, kind = _entry_03(doc)
    g = rect_geometry_03(doc)[1]
    dom = ', '.join(f'{k} {g["domain"][k]}' for k in ('xmin', 'xmax', 'ymin', 'ymax'))
    out = [f'{doc.si["name"]} (openphysics 0.3)', f'  physics {name}: {kind}, headless single steady rectangle',
           f'  domain {dom} ({g["length_unit"]}); subdivision_count {doc.si["mesh"]["subdivision_count"]}']
    if kind == 'joule.temperature2d':
        m = f'{where}.electrical_conductivity'
        out.append(f'  electrical_conductivity linear_resistivity: reference_conductivity '
                   f'{_authored(doc, m + ".reference_conductivity")}, reference_temperature '
                   f'{_authored(doc, m + ".reference_temperature")}, resistivity_temperature_coefficient '
                   f'{_authored(doc, m + ".resistivity_temperature_coefficient")}')
    else:
        out.append(f'  electrical_conductivity {_authored(doc, where + ".electrical_conductivity")}')
    potentials = {tag: _authored(doc, f'{where}.prescribed_electric_potential.{tag}')
                  for tag in p['prescribed_electric_potential']}
    current = {tag: _authored(doc, f'{where}.inward_current_density.{tag}') for tag in p.get('inward_current_density', {})}
    out.append(f'  prescribed_electric_potential {potentials}' + (f'; inward_current_density {current}' if current else '')
               + '; other sides electrically insulating')
    if kind != 'electric.steady2d':
        temperatures = {tag: _authored(doc, f'{where}.prescribed_temperature.{tag}') for tag in p['prescribed_temperature']}
        flux = {tag: _authored(doc, f'{where}.inward_heat_flux.{tag}') for tag in p.get('inward_heat_flux', {})}
        convection = {tag: {k: _authored(doc, f'{where}.convection.{tag}.{k}') for k in c}
                      for tag, c in p.get('convection', {}).items()}
        out.append(f'  thermal_conductivity {_authored(doc, where + ".thermal_conductivity")}; prescribed_temperature '
                   f'{temperatures}' + (f'; inward_heat_flux {flux}' if flux else '')
                   + (f'; convection {convection}' if convection else '') + '; other sides insulated')
    out.append(f'  result: {kind}-result-v2; layout: {FIELD_LAYOUT}')
    out.append('  output: SI (electric_potential V, current_density A/m^2, joule_power_density W/m^3, '
               'nodal currents A/m and powers W/m of depth)')
    return '\n'.join(out)


def document_summary(doc):
    doc.validate()
    if is_region_electric(doc.data):
        return region_summary(doc)
    if joule_regions.is_region_joule(doc.data):
        return joule_regions.region_summary(doc)
    return rectangle_summary_03(doc)


# -- results --------------------------------------------------------------------------------------

def _fixed(mesh, sides):
    return dict(sorted((int(node), float(value)) for side, value in sides.items()
                       for node in mesh.boundary[side]))


def _norm(a):
    return float(np.max(abs(np.asarray(a)), initial=0.))


def iteration_record(record):
    """One ``JouleIteration`` under the section 5.3.2 column names: values as value objects
    (a non-finite value is null), the iteration count bare."""
    values = asdict(record)
    return {column: (int(values[field]) if quantity is None else results_common.value_object(values[field], quantity))
            for field, column, quantity in ITERATION_COLUMNS}


def failure_evidence(exc):
    """JSON-safe failed-state evidence; never a successful result."""
    values = np.asarray(exc.last_temperature)
    return dict(status='failed', reason=exc.reason, iterations=[iteration_record(i) for i in exc.history],
                last_iterate={'temperature': results_common.tagged_array(values, 'temperature')},
                nonfinite_temperature_count=int(np.count_nonzero(~np.isfinite(values))))


def electric_balance(electric, fixed, mesh):
    """The electric values of ``balance`` (SI, per metre of depth)."""
    free = np.setdiff1d(np.arange(mesh.num_nodes), list(fixed))
    return {'current_imbalance_per_depth': float(np.sum(np.asarray(electric.reaction)
                                                        - np.asarray(electric.prescribed_outward_load))),
            'maximum_residual_current_per_depth': _norm(np.asarray(electric.residual)[free]),
            'inward_electric_power_per_depth': electric.supplied_power_per_length,
            'joule_power_per_depth': electric.joule_power_per_length,
            'electric_power_imbalance_per_depth': electric.supplied_power_per_length-electric.joule_power_per_length}


def heat_balance(coupled, fixed, mesh):
    """The heat-stage values of ``balance``."""
    heat = coupled.thermal
    free = np.setdiff1d(np.arange(mesh.num_nodes), list(fixed))
    return {'outward_heat_rate_per_depth': coupled.outward_heat_per_length,
            'heat_rate_imbalance_per_depth': coupled.outward_heat_per_length-coupled.source_power_per_length,
            'maximum_residual_heat_rate_per_depth': _norm(np.asarray(heat.residual)[free]),
            'minimum_temperature': float(np.min(heat.temperature)), 'maximum_temperature': float(np.max(heat.temperature))}


def result_arrays(mesh, electric, electric_fixed, *, regions=None, heat=None, heat_fixed=None, evaluated=None):
    """The saved arrays, in today's order under the registry names (bytes unchanged)."""
    arrays = {'node_coordinates': np.asarray(mesh.nodes), 'triangles': np.asarray(mesh.triangles)}
    if regions is not None:
        arrays['triangle_regions'] = np.asarray(regions)
    for key, attr in ELECTRIC_ARRAYS:
        arrays[key] = np.asarray(getattr(electric, attr))
    if regions is None:
        arrays['electric_prescribed_node_ids'] = np.asarray(list(electric_fixed))
    else:
        arrays['electric_prescribed_node_ids'] = np.array(list(electric_fixed), dtype=int)
    arrays['prescribed_electric_potential'] = np.asarray(list(electric_fixed.values()))
    if heat is not None:
        for key, attr in HEAT_ARRAYS:
            arrays[key] = np.asarray(getattr(heat, attr))
        arrays['thermal_prescribed_node_ids'] = np.array(list(heat_fixed), dtype=int)
        arrays['prescribed_temperature'] = np.asarray(list(heat_fixed.values()))
    if evaluated is not None:
        arrays['evaluation_temperature'] = np.asarray(evaluated)
    return arrays


def summary_03(doc, *, result_format, field_layout, arrays, balance, timings, mesh, depth, extra=None,
               history=(), minimum_angle=None):
    """The section 5.3.2 summary: the common envelope, the field maps, ``balance`` (value objects;
    with a depth, each per-depth value is followed by its total) and the iteration records."""
    import galerkin
    import scipy
    from . import __version__
    name, p, _, kind = _entry_03(doc)
    fields = {key: {'quantity': FIELDS[key][0], 'location': FIELDS[key][1], 'shape': list(a.shape),
                    'components': FIELDS[key][2]} for key, a in arrays.items()}
    maps = results_common.field_maps(fields)
    del maps['field_time_axes']                      # a steady result has no time axis
    vo = results_common.value_object
    values = {}
    for key, value in balance.items():
        if key == 'outward_current_per_depth':
            values[key] = {tag: vo(v, key) for tag, v in value.items()}
        else:
            values[key] = vo(value, key)
    if depth is not None:
        results_common.add_depth_totals(values, depth)
        if 'outward_current_per_depth' in values:
            terminal = {tag: vo(v, 'outward_current') for tag, v in
                        ((t, x['value'] * depth) for t, x in values['outward_current_per_depth'].items())}
            items = list(values.items())
            values.clear()
            for key, value in items:
                values[key] = value
                if key == 'outward_current_per_depth':
                    values['outward_current'] = terminal
    mesh_block = {'nodes': int(mesh.num_nodes), 'triangles': int(len(mesh.triangles))}
    if minimum_angle is not None:
        mesh_block['minimum_triangle_angle'] = vo(minimum_angle, 'minimum_triangle_angle')
    out = {'name': doc.si['name'], 'physics_name': name, 'physics_type': kind, 'status': 'converged',
           **results_common.envelope(doc, result_format=result_format, field_layout=field_layout,
                                     timing_=results_common.timing(timings['mesh'], timings['solve'])),
           **maps, 'mesh': mesh_block, 'study': {'type': 'single'}, **(extra or {}),
           'balance': values, 'iterations': [iteration_record(i) for i in history],
           'software_versions': dict(simcase=__version__, galerkin=galerkin.__version__, numpy=np.__version__,
                                     scipy=scipy.__version__)}
    results_common.dumps_summary(out)                # finite JSON only
    return out


class ElectricJouleRunResult:
    """Owned numeric evidence. Public field/summary access returns independent copies."""
    FIELD_LAYOUT = FIELD_LAYOUT

    def __init__(self, doc, arrays, metadata, log):
        self.doc = doc.copy()
        self.doc.validate()
        self._document_json = self.doc.canonical_json(separators=(', ', ': '))
        self._arrays = {k: np.array(v, copy=True) for k, v in arrays.items()}
        for key, array in self._arrays.items():
            if array.dtype.kind not in 'iuf' or not np.isfinite(array).all():
                raise ValueError(f'{key}: expected finite real numeric array')
            array.setflags(write=False)
        results_common.dumps_summary(metadata)           # finite JSON only
        self._metadata = copy.deepcopy(metadata)
        self._log = tuple(log)

    @property
    def fields(self):
        return {k: a.copy() for k, a in self._arrays.items()}

    @property
    def result_format(self):
        return self._metadata['result_format']

    @property
    def field_layout(self):
        return self._metadata['field_layout']

    def summary(self):
        if self.doc.canonical_json(separators=(', ', ': ')) != self._document_json:
            raise ValueError('electric/Joule result document changed after the solve; run again')
        return copy.deepcopy(self._metadata)

    def save(self, outdir):
        summary = self.summary()
        encoded = results_common.dumps_summary(summary).encode('utf-8')
        owned = _OwnedOutput(outdir)
        try:
            owned.write('.incomplete', lambda f: f.write(b'incomplete electric/Joule result\n'))
            owned.write('model.json', lambda f: f.write(model_bytes_03(self.doc)))
            owned.write('log.txt', lambda f: f.write(('\n'.join(self._log)+'\n').encode('utf-8')))
            if self.doc.si['results']['save_fields']:
                arrays = dict(self._arrays, result_format=summary['result_format'], field_layout=self.FIELD_LAYOUT,
                              metadata_json=results_common.metadata_json(summary))
                owned.write('fields.npz', lambda f: np.savez_compressed(f, **arrays))
            owned.write('summary.json', lambda f: f.write(encoded))
            owned.finish()
        except Exception:
            owned.cleanup()
            raise
        finally:
            owned.close()
        return owned.path


class RegionElectricRunResult(ElectricJouleRunResult):
    """Owned numeric evidence of a region electric run (``electric.steady2d-regions-result-v2``)."""
    FIELD_LAYOUT = REGION_FIELD_LAYOUT


class RegionJouleRunResult(ElectricJouleRunResult):
    """Owned numeric evidence of a region Joule run (``joule.steady2d-regions-result-v2``)."""
    FIELD_LAYOUT = joule_regions.FIELD_LAYOUT


def run_electric_joule(doc, verbose=True, *, mesh_limits=None):
    if is_region_electric(doc.data):
        return run_region_electric(doc, verbose, mesh_limits=mesh_limits)
    if joule_regions.is_region_joule(doc.data):
        return joule_regions.run_region_joule(doc, verbose, mesh_limits=mesh_limits)
    from galerkin import rectangle_mesh
    from galerkin.electric import solve_steady_electric
    from galerkin.joule_heating import solve_steady_joule_heat
    from galerkin.temperature_joule_heating import solve_temperature_joule_heat
    doc.validate()
    doc = doc.copy()
    doc.validate()
    name, p, _, kind = _entry_03(doc)
    start = time.perf_counter()
    # the mesh subtracts the converted corners (views.LENGTH_FORMULAS)
    grid = views.rectangle_mesh(doc, 'corners')
    mesh = rectangle_mesh(*grid.lengths, *grid.subdivisions)
    mesh.nodes += grid.origin
    inputs = views.rectangle_electric(doc)
    heat_args = None
    if kind != 'electric.steady2d':
        temperatures = {tag: float(v) for tag, v in p['prescribed_temperature'].items()}
        flux, convection = natural_conditions_03(p, f'physics.{name}', temperatures)
        heat = views.HeatInputs(conductivity=float(p['thermal_conductivity']), heat_source=0.0,
                                dirichlet=temperatures, outward_flux=flux, convection=convection)
        heat_args = boundary_kwargs(views.rectangle_mesh(doc, 'difference'), heat, mesh)
        heat_args.pop('heat_source')
    electric_fixed = _fixed(mesh, inputs.dirichlet)
    electric_args = dict(dirichlet=electric_fixed, outward_current=inputs.outward_current)
    mesh_time = time.perf_counter()-start
    start = time.perf_counter()
    coupled = nonlinear = None
    if kind == 'joule.temperature2d':
        nonlinear = solve_temperature_joule_heat(mesh,
            electrical_conductivity=inputs.conductivity_model,
            thermal_conductivity=heat_args['conductivity'], electric_dirichlet=electric_fixed,
            thermal_dirichlet=heat_args['dirichlet'], initial_temperature=inputs.initial_temperature,
            outward_current=electric_args['outward_current'], outward_flux=heat_args['outward_flux'],
            convection=heat_args['convection'], method='picard', **inputs.iteration)
        coupled = nonlinear.coupled
        electric = coupled.electrical
    else:
        electric = solve_steady_electric(mesh, conductivity=inputs.conductivity, **electric_args)
        if kind == 'joule.steady2d':
            coupled = solve_steady_joule_heat(mesh, electrical_result=electric, **heat_args)
    solve_time = time.perf_counter()-start
    arrays = result_arrays(mesh, electric, electric_fixed, heat=None if coupled is None else coupled.thermal,
                           heat_fixed=None if coupled is None else heat_args['dirichlet'],
                           evaluated=None if nonlinear is None else nonlinear.evaluated_temperature)
    balance = electric_balance(electric, electric_fixed, mesh)
    if coupled is not None:
        balance.update(heat_balance(coupled, heat_args['dirichlet'], mesh))
    metadata = summary_03(doc, result_format=kind+'-result-v2', field_layout=FIELD_LAYOUT, arrays=arrays,
                          balance=balance, timings={'mesh': mesh_time, 'solve': solve_time}, mesh=mesh,
                          depth=rect_geometry_03(doc)[2], history=() if nonlinear is None else nonlinear.history)
    printed = [doc.summary(), f'Solved {mesh.num_nodes} nodes, {mesh.num_triangles} triangles; '
               f'joule_power_per_depth {electric.joule_power_per_length:.12g} W/m']
    if verbose:
        print('\n'.join(printed))
    return ElectricJouleRunResult(doc, arrays, metadata, log_lines_03(doc, printed))


def _slots():
    return electric_slots()


def _refuse_03(tree):
    from .electric_regions import region_joule_refusal
    return region_joule_refusal(tree)


register(PhysicsKind(
    name='electric_joule', types=frozenset(TYPES), precedence=10,
    validate=validate_electric_joule, run=run_electric_joule, summary=document_summary,
    result_types=(ElectricJouleRunResult,), fresh_output=True,
    stage_refusal='{stage} is an EM stage; use run(document) for electric/Joule physics',
    accepts_mesh_limits=is_region_document, slots=_slots(), refuse_03=_refuse_03))
