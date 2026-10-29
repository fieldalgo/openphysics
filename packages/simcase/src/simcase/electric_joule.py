# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Strict headless rectangle adapters for the existing electric/Joule solvers."""
import copy
from dataclasses import asdict
import json
import time

import numpy as np

from .schema import Document, DocumentError
from .steady_boundary_contract import SIDES, _number, _object, validate_steady_boundary, steady_boundary_inputs
from .thermal import _OwnedOutput
from . import units
from .registry import PhysicsKind, register

TYPES = {'electric.steady2d', 'joule.steady2d', 'joule.temperature2d'}
FIELD_LAYOUT = 'electric-joule2d-p1-v1'
MAX_TRIANGLES = 200_000


def is_electric_joule(data):
    return isinstance(data, dict) and isinstance(data.get('physics'), dict) and any(
        isinstance(p, dict) and p.get('type') in TYPES for p in data['physics'].values())


def _thermal_document(doc):
    """Project shared geometry and thermal boundary data into the existing contract."""
    d = copy.deepcopy(doc.data)
    p = next(iter(d['physics'].values()))
    thermal = p['type'] != 'electric.steady2d'
    d['units']['temperature'] = 'K'
    d['physics'] = {'heat': dict(type='thermal.steady2d',
        conductivity_w_mk=p['thermal_conductivity_w_mk'] if thermal else 1.,
        dirichlet_temperature_k=p['dirichlet_temperature_k'] if thermal else {'left': 0.},
        outward_flux_w_m2=p.get('outward_flux_w_m2', {}), convection=p.get('convection', {}))}
    return Document(d)


def _sides(value, path):
    _object(value, SIDES, path)
    for side, v in value.items():
        _number(v, path+'.'+side)


def _model(spec, path):
    keys = {'type', 'reference_conductivity_s_m', 'reference_temperature_k',
            'alpha_per_k', 'temperature_range_k'}
    _object(spec, keys, path, keys)
    if spec['type'] != 'linear_resistivity':
        raise DocumentError(path+'.type: expected linear_resistivity')
    sigma = _number(spec['reference_conductivity_s_m'], path+'.reference_conductivity_s_m', positive=True)
    reference = _number(spec['reference_temperature_k'], path+'.reference_temperature_k', nonnegative=True)
    alpha = _number(spec['alpha_per_k'], path+'.alpha_per_k')
    bounds = spec['temperature_range_k']
    if not isinstance(bounds, list) or len(bounds) != 2:
        raise DocumentError(path+'.temperature_range_k: expected [lo, hi]')
    lo, hi = [_number(v, path+'.temperature_range_k', nonnegative=True) for v in bounds]
    if not lo < hi or not lo <= reference <= hi:
        raise DocumentError(path+': require lo < hi and reference temperature inside range')
    for t in (lo, hi):
        denominator = _number(1.+alpha*(t-reference), path+' denominator at endpoint', positive=True)
        _number(sigma/denominator, path+' conductivity at endpoint', positive=True)
    from galerkin.temperature_joule_heating import ConductivityModel
    return ConductivityModel(lambda t: sigma/(1.+alpha*(t-reference)), (lo, hi))


def validate_electric_joule(doc):
    d = doc.data
    top = {'openphysics', 'name', 'units', 'geometry', 'materials', 'physics', 'mesh', 'study', 'results'}
    _object(d, top, 'document', top)
    _object(d['units'], {'length', 'temperature'}, 'units', {'length'})
    physics = d['physics']
    if not isinstance(physics, dict) or len(physics) != 1:
        raise DocumentError('physics: exactly one electric/Joule entry required')
    name, p = next(iter(physics.items()))
    if not isinstance(name, str) or not name.isidentifier() or not isinstance(p, dict):
        raise DocumentError('physics: expected identifier and settings object')
    kind = p.get('type')
    if kind not in TYPES:
        raise DocumentError('unsupported electric/Joule physics')
    path = 'physics.'+name
    required = {'type', 'dirichlet_potential_v'}
    optional = {'outward_current_a_m2'}
    if kind == 'joule.temperature2d':
        required |= {'conductivity_model', 'initial_temperature_k'}
        optional |= {'iteration'}
    else:
        required |= {'conductivity_s_m'}
    if kind != 'electric.steady2d':
        required |= {'thermal_conductivity_w_mk', 'dirichlet_temperature_k'}
        optional |= {'outward_flux_w_m2', 'convection'}
        if d['units'].get('temperature') != 'K':
            raise DocumentError('units.temperature: Joule documents require K')
    elif 'temperature' in d['units'] and d['units']['temperature'] != 'K':
        raise DocumentError('units.temperature: expected K')
    _object(p, required | optional, path, required)
    # Reuse strict rectangle, units, heat boundary, study and result checks.
    validate_steady_boundary(_thermal_document(doc))
    counts = d['mesh']['subdivisions']
    if 2*counts[0]*counts[1] > MAX_TRIANGLES:
        raise DocumentError(f'mesh: at most {MAX_TRIANGLES} triangles supported')
    bc = p['dirichlet_potential_v']
    _sides(bc, path+'.dirichlet_potential_v')
    if not bc:
        raise DocumentError(path+': at least one voltage side is required; gauge-only inputs unsupported')
    for a in ('left', 'right'):
        for b in ('bottom', 'top'):
            if a in bc and b in bc and bc[a] != bc[b]:
                raise DocumentError(path+': conflicting potential at shared corner')
    current = p.get('outward_current_a_m2', {})
    _sides(current, path+'.outward_current_a_m2')
    if set(current) & set(bc):
        raise DocumentError(path+': current condition overlaps a fixed voltage side')
    if kind == 'joule.temperature2d':
        model = _model(p['conductivity_model'], path+'.conductivity_model')
        lo, hi = model.temperature_range
        initial = _number(p['initial_temperature_k'], path+'.initial_temperature_k', nonnegative=True)
        temperatures = [initial, *p['dirichlet_temperature_k'].values(),
                        *(v['ambient_temperature_k'] for v in p.get('convection', {}).values())]
        if any(not lo <= t <= hi for t in temperatures):
            raise DocumentError(path+': initial/boundary temperature outside conductivity model range')
        iteration = p.get('iteration', {})
        _object(iteration, {'relaxation', 'temperature_atol_k', 'relative_tolerance', 'max_iterations'}, path+'.iteration')
        for key, value in iteration.items():
            _number(value, path+'.iteration.'+key, positive=True, integer=key == 'max_iterations')
        if iteration.get('relaxation', .5) > 1:
            raise DocumentError(path+'.iteration.relaxation: must be <= 1')
    else:
        _number(p['conductivity_s_m'], path+'.conductivity_s_m', positive=True)
    doc.scale = units.resolve(d['units'])
    doc.notes = []


def document_summary(doc):
    doc.validate()
    name, p = doc.sole_physics()
    return (f'{doc["name"]} (openphysics 0.2)\n  physics {name}: {p["type"]}, headless single steady rectangle\n'
            f'  domain {doc.domain} {doc.length_unit}; mesh {doc["mesh"]["subdivisions"]}\n'
            '  SI output: V, A/m^2, W/m^3; integrated current A/m and power W/m of depth')


def _fixed(mesh, sides):
    return dict(sorted((int(node), float(value)) for side, value in sides.items()
                       for node in mesh.boundary[side]))


def _norm(a):
    return float(np.max(abs(np.asarray(a)), initial=0.))


def failure_evidence(exc):
    """JSON-safe failed-state evidence; never a successful result."""
    values = np.asarray(exc.last_temperature)
    return dict(status='failed', reason=exc.reason, iterations=[asdict(i) for i in exc.history],
                last_temperature_k=[float(v) if np.isfinite(v) else None for v in values],
                nonfinite_temperature_count=int(np.count_nonzero(~np.isfinite(values))))


class ElectricJouleRunResult:
    """Owned numeric evidence. Public field/summary access returns independent copies."""
    def __init__(self, doc, arrays, metadata, log):
        self.doc = doc.copy()
        self.doc.validate()
        self._document_json = json.dumps(self.doc.data, sort_keys=True, allow_nan=False)
        self._arrays = {k: np.array(v, copy=True) for k, v in arrays.items()}
        for key, array in self._arrays.items():
            if array.dtype.kind not in 'iuf' or not np.isfinite(array).all():
                raise ValueError(f'{key}: expected finite real numeric array')
            array.setflags(write=False)
        self._metadata_json = json.dumps(metadata, allow_nan=False)
        self._log = tuple(log)

    @property
    def fields(self):
        return {k: a.copy() for k, a in self._arrays.items()}

    def summary(self):
        if json.dumps(self.doc.data, sort_keys=True, allow_nan=False) != self._document_json:
            raise ValueError('electric/Joule result document changed after the solve; run again')
        return json.loads(self._metadata_json)

    def save(self, outdir):
        summary = self.summary()
        encoded = json.dumps(summary, indent=2, allow_nan=False).encode('utf-8')
        owned = _OwnedOutput(outdir)
        try:
            owned.write('.incomplete', lambda f: f.write(b'incomplete electric/Joule result\n'))
            owned.write('model.json', lambda f: f.write(self._document_json.encode('utf-8')))
            owned.write('log.txt', lambda f: f.write(('\n'.join(self._log)+'\n').encode('utf-8')))
            if self.doc['results']['save_fields']:
                arrays = dict(self._arrays, result_format=summary['result_format'],
                              field_layout=FIELD_LAYOUT, mesh_length_unit='m', metadata_json=encoded.decode('utf-8'))
                owned.write('fields.npz', lambda f: np.savez_compressed(f, **arrays))
            owned.write('summary.json', lambda f: f.write(encoded))
            owned.finish()
        except Exception:
            owned.cleanup()
            raise
        finally:
            owned.close()
        return owned.path


def run_electric_joule(doc, verbose=True):
    from galerkin import rectangle_mesh
    from galerkin.electric import solve_steady_electric
    from galerkin.joule_heating import solve_steady_joule_heat
    from galerkin.temperature_joule_heating import solve_temperature_joule_heat
    import galerkin
    import scipy
    from . import __version__
    doc.validate()
    doc = Document.from_dict(doc.data)
    name, p = doc.sole_physics()
    kind = p['type']
    start = time.perf_counter()
    bounds = {k: doc.scale.to_si(v, {'length': 1}) for k, v in doc.domain.items()}
    mesh = rectangle_mesh(bounds['xmax']-bounds['xmin'], bounds['ymax']-bounds['ymin'],
                          *doc['mesh']['subdivisions'])
    mesh.nodes += [bounds['xmin'], bounds['ymin']]
    heat_args = steady_boundary_inputs(_thermal_document(doc), mesh)
    heat_args.pop('heat_source')
    electric_fixed = _fixed(mesh, p['dirichlet_potential_v'])
    electric_args = dict(dirichlet=electric_fixed, outward_current=p.get('outward_current_a_m2', {}))
    mesh_time = time.perf_counter()-start
    start = time.perf_counter()
    coupled = nonlinear = None
    if kind == 'joule.temperature2d':
        options = dict(p.get('iteration', {}))
        if 'temperature_atol_k' in options:
            options['temperature_atol'] = options.pop('temperature_atol_k')
        nonlinear = solve_temperature_joule_heat(mesh,
            electrical_conductivity=_model(p['conductivity_model'], 'conductivity_model'),
            thermal_conductivity=heat_args['conductivity'], electric_dirichlet=electric_fixed,
            thermal_dirichlet=heat_args['dirichlet'], initial_temperature=p['initial_temperature_k'],
            outward_current=electric_args['outward_current'], outward_flux=heat_args['outward_flux'],
            convection=heat_args['convection'], method='picard', **options)
        coupled = nonlinear.coupled
        electric = coupled.electrical
    else:
        electric = solve_steady_electric(mesh, conductivity=p['conductivity_s_m'], **electric_args)
        if kind == 'joule.steady2d':
            coupled = solve_steady_joule_heat(mesh, electrical_result=electric, **heat_args)
    solve_time = time.perf_counter()-start
    arrays, field_units, locations = {}, {}, {}
    def add(key, value, unit, location):
        arrays[key] = np.asarray(value)
        field_units[key], locations[key] = unit, location
    add('nodes_m', mesh.nodes, 'm', 'nodes')
    add('triangles', mesh.triangles, '1', 'triangle_connectivity')
    for key, attr, unit, location in (
        ('potential_v', 'potential', 'V', 'nodes'),
        ('electric_field_v_m', 'electric_field', 'V/m', 'triangle_centroids'),
        ('current_density_a_m2', 'current_density', 'A/m^2', 'triangle_centroids'),
        ('conductivity_s_m', 'conductivity', 'S/m', 'triangle_centroids'),
        ('joule_heating_w_m3', 'joule_heating', 'W/m^3', 'triangle_centroids'),
        ('joule_load_w_per_m', 'joule_load', 'W/m', 'nodes'),
        ('electric_reaction_a_per_m', 'reaction', 'A/m', 'nodes'),
        ('prescribed_outward_current_a_per_m', 'prescribed_outward_load', 'A/m', 'nodes'),
        ('electric_residual_a_per_m', 'residual', 'A/m', 'nodes')):
        add(key, getattr(electric, attr), unit, location)
    add('electric_dirichlet_node_ids', list(electric_fixed), '1', 'electric_dirichlet_nodes')
    add('dirichlet_potential_v', list(electric_fixed.values()), 'V', 'electric_dirichlet_nodes')
    free_e = np.setdiff1d(np.arange(mesh.num_nodes), list(electric_fixed))
    diagnostics = dict(current_balance_a_per_m=float(np.sum(electric.reaction-electric.prescribed_outward_load)),
        electric_free_residual_a_per_m=_norm(electric.residual[free_e]),
        supplied_power_w_per_m=electric.supplied_power_per_length,
        joule_power_w_per_m=electric.joule_power_per_length,
        electric_power_defect_w_per_m=electric.supplied_power_per_length-electric.joule_power_per_length)
    if coupled is not None:
        heat = coupled.thermal
        for key, attr, unit, location in (
            ('temperature_k', 'temperature', 'K', 'nodes'), ('heat_flux_w_m2', 'heat_flux', 'W/m^2', 'triangle_centroids'),
            *((key+'_w_per_m', attr, 'W/m', 'nodes') for key, attr in (
                ('thermal_load', 'load'), ('thermal_reaction', 'reaction'), ('thermal_residual', 'residual'),
                ('prescribed_outward_heat', 'prescribed_outward_load'), ('ambient_load', 'ambient_load'),
                ('convective_outward_heat', 'convective_outward'), ('thermal_system_rhs', 'system_rhs')))):
            add(key, getattr(heat, attr), unit, location)
        fixed = heat_args['dirichlet']
        add('thermal_dirichlet_node_ids', np.array(list(fixed), dtype=int), '1', 'thermal_dirichlet_nodes')
        add('dirichlet_temperature_k', list(fixed.values()), 'K', 'thermal_dirichlet_nodes')
        free_t = np.setdiff1d(np.arange(mesh.num_nodes), list(fixed))
        diagnostics.update(outward_heat_w_per_m=coupled.outward_heat_per_length,
            heat_power_defect_w_per_m=coupled.outward_heat_per_length-coupled.source_power_per_length,
            thermal_free_residual_w_per_m=_norm(heat.residual[free_t]),
            temperature_min_k=float(heat.temperature.min()), temperature_max_k=float(heat.temperature.max()))
    if nonlinear is not None:
        add('evaluated_temperature_k', nonlinear.evaluated_temperature, 'K', 'nodes')
    history = [] if nonlinear is None else [asdict(i) for i in nonlinear.history]
    metadata = dict(name=doc['name'], physics_name=name, physics_type=kind, status='converged',
        result_format=kind+'-result-v1', field_layout=FIELD_LAYOUT, mesh_length_unit='m',
        input_units=copy.deepcopy(doc['units']), field_units=field_units, field_locations=locations,
        field_shapes={k: list(v.shape) for k, v in arrays.items()}, diagnostics=diagnostics,
        iterations=history, iteration_units=dict(iteration='1', temperature_defect='K', conductivity_defect='1',
            minimum_temperature='K', maximum_temperature='K', electric_free_residual='A/m',
            thermal_free_residual='W/m', nonlinear_heat_residual='1', current_balance='A/m',
            **{key: 'W/m' for key in ('supplied_power_per_length', 'joule_power_per_length',
                                       'outward_heat_per_length', 'electric_power_defect', 'heat_power_defect')}),
        timings_s=dict(mesh=mesh_time, solve=solve_time),
        software_versions=dict(simcase=__version__, galerkin=galerkin.__version__, numpy=np.__version__, scipy=scipy.__version__))
    log = [document_summary(doc), f'Solved {mesh.num_nodes} nodes, {mesh.num_triangles} triangles; '
           f'Joule power {electric.joule_power_per_length:.12g} W/m of depth']
    if verbose:
        print('\n'.join(log))
    return ElectricJouleRunResult(doc, arrays, metadata, log)


def _defaults():
    from .thermal import defaults
    return defaults()


register(PhysicsKind(
    name='electric_joule', types=frozenset(TYPES), precedence=10,
    validate=validate_electric_joule, run=run_electric_joule, summary=document_summary,
    result_types=(ElectricJouleRunResult,), defaults=_defaults, fresh_output=True,
    stage_refusal='{stage} is an EM stage; use run(document) for electric/Joule physics'))
