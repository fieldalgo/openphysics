# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Strict headless adapters for the existing 2D elasticity and thermoelastic solvers.

A document whose geometry declares material regions (a 0.2 ``background``/``shapes`` block or a
version 1 region component) takes the region path of mechanics_regions.py; the rest of this
module is the rectangle contract below, unchanged.

One homogeneous isotropic rectangle, plane stress or plane strain, side-constant
displacement components and global Cartesian side tractions, an optional constant
body force. ``mechanics.elasticity2d`` is the isothermal solve;
``mechanics.thermoelastic2d`` first solves steady heat with side-constant boundary
data on the same mesh, freezes the nodal temperature and solves the prescribed-
temperature mechanical stage with TOTAL physical side tractions. The document is
projected into the steady heat contract for the shared rectangle, unit, mesh,
study, result and heat boundary checks, exactly as the electric/Joule adapter does;
the mechanics keys are validated here. The runners build the mesh once in metres
and call ``galerkin`` with no new discretization.
"""
import copy
import json
import time

import numpy as np

from .schema import Document, DocumentError
from .steady_boundary_contract import SIDES, _number, _object, validate_steady_boundary, steady_boundary_inputs
from .thermal import _OwnedOutput
from . import units, views
from .registry import PhysicsKind, register

ELASTIC = 'mechanics.elasticity2d'
THERMOELASTIC = 'mechanics.thermoelastic2d'
TYPES = {ELASTIC, THERMOELASTIC}
FIELD_LAYOUTS = {ELASTIC: 'mechanics2d-p1-v1', THERMOELASTIC: 'thermoelastic2d-p1-v1'}
FIELD_LAYOUT = FIELD_LAYOUTS[ELASTIC]
RESULT_FORMAT = ELASTIC+'-result-v1'
MAX_TRIANGLES = 200_000
PLANES = ('stress', 'strain')
COMPONENTS = ('x', 'y')
STRAIN_COMPONENTS = ('exx', 'eyy', 'gxy')
STRESS_COMPONENTS = ('sxx', 'syy', 'sxy')
HEAT_KEYS = {'thermal_conductivity_w_mk', 'dirichlet_temperature_k'}
HEAT_OPTIONAL = {'heat_source_w_m3', 'outward_flux_w_m2', 'convection'}


def is_mechanics(data):
    return isinstance(data, dict) and isinstance(data.get('physics'), dict) and any(
        isinstance(p, dict) and p.get('type') in TYPES for p in data['physics'].values())


def _thermal_document(doc):
    """Project the shared sections, and a thermoelastic document's heat data, into the heat contract."""
    d = copy.deepcopy(doc.data)
    p = next(iter(d['physics'].values()))
    thermal = p.get('type') == THERMOELASTIC
    d['units'] = {'length': d['units'].get('length'), 'temperature': 'K'}
    heat = dict(type='thermal.steady2d',
                conductivity_w_mk=p.get('thermal_conductivity_w_mk') if thermal else 1.,
                dirichlet_temperature_k=p.get('dirichlet_temperature_k') if thermal else {'left': 0.})
    if thermal:
        for key, target in (('heat_source_w_m3', 'heat_source_w_m3'), ('outward_flux_w_m2', 'outward_flux_w_m2'),
                            ('convection', 'convection')):
            if key in p:
                heat[target] = p[key]
    d['physics'] = {'heat': heat}
    return Document(d)


def _vector(value, path):
    if not isinstance(value, list) or len(value) != 2:
        raise DocumentError(path+': expected [x, y]')
    return [_number(v, f'{path}[{i}]') for i, v in enumerate(value)]


def _displacement(value, path):
    """{side: {x?: m, y?: m}} -> {(side, component): metres}; refuses conflicting corners."""
    _object(value, SIDES, path)
    fixed = {}
    for side, components in value.items():
        where = path+'.'+side
        _object(components, COMPONENTS, where)
        if not components:
            raise DocumentError(where+': expected x and/or y')
        for component, v in components.items():
            fixed[side, component] = _number(v, where+'.'+component)
    for a in ('left', 'right'):
        for b in ('bottom', 'top'):
            for c in COMPONENTS:
                if (a, c) in fixed and (b, c) in fixed and fixed[a, c] != fixed[b, c]:
                    raise DocumentError(f'{path}: conflicting {c} displacement at the {a}/{b} corner')
    return fixed


def rigid_modes_fixed(fixed):
    """Whether side-constant constraints hold all three planar rigid-body motions.

    ``fixed`` holds (side, component) keys. A rigid motion is u = (a - t*y, b + t*x).
    Fixing x on left or right (y varies along the side) or y on bottom or top
    kills the rotation t; so does fixing x on both bottom and top, or y on both
    left and right. Fixing only x on one horizontal side and y on one vertical
    side leaves a hinge about their corner, and is refused.
    """
    x_sides = {side for side, c in fixed if c == 'x'}
    y_sides = {side for side, c in fixed if c == 'y'}
    if not x_sides or not y_sides:
        return False
    return bool(x_sides & {'left', 'right'} or y_sides & {'bottom', 'top'}
                or {'bottom', 'top'} <= x_sides or {'left', 'right'} <= y_sides)


def validate_mechanics(doc):
    from .mechanics_regions import is_region_mechanics, validate_region_mechanics
    if is_region_mechanics(doc.data):
        validate_region_mechanics(doc)
        return
    d = doc.data
    top = {'openphysics', 'name', 'units', 'geometry', 'materials', 'physics', 'mesh', 'study', 'results'}
    _object(d, top, 'document', top)
    physics = d['physics']
    if not isinstance(physics, dict) or len(physics) != 1:
        raise DocumentError('physics: exactly one mechanics entry required')
    name, p = next(iter(physics.items()))
    if not isinstance(name, str) or not name.isidentifier() or not isinstance(p, dict):
        raise DocumentError('physics: expected identifier and settings object')
    kind = p.get('type')
    if kind not in TYPES:
        raise DocumentError('unsupported mechanics physics')
    path = 'physics.'+name
    required = {'type', 'plane', 'young_modulus_pa', 'poisson_ratio', 'displacement_m'}
    optional = {'body_force_n_m3', 'traction_pa'}
    if kind == THERMOELASTIC:
        _object(d['units'], {'length', 'temperature'}, 'units', {'length', 'temperature'})
        if d['units']['temperature'] != 'K':
            raise DocumentError('units.temperature: thermoelastic documents require K')
        required |= HEAT_KEYS | {'thermal_expansion_per_k', 'reference_temperature_k'}
        optional |= HEAT_OPTIONAL
    else:
        _object(d['units'], {'length'}, 'units', {'length'})
    _object(p, required | optional, path, required)
    # Reuse the strict rectangle, length unit, mesh, study, result and heat boundary checks.
    validate_steady_boundary(_thermal_document(doc))
    counts = d['mesh']['subdivisions']
    if 2*counts[0]*counts[1] > MAX_TRIANGLES:
        raise DocumentError(f'mesh: at most {MAX_TRIANGLES} triangles supported')
    if p['plane'] not in PLANES:
        raise DocumentError(path+'.plane: expected "stress" or "strain"')
    _number(p['young_modulus_pa'], path+'.young_modulus_pa', positive=True)
    nu = _number(p['poisson_ratio'], path+'.poisson_ratio')
    if not -1 < nu < .5:
        raise DocumentError(path+'.poisson_ratio: expected -1 < nu < 0.5')
    if kind == THERMOELASTIC:
        _number(p['thermal_expansion_per_k'], path+'.thermal_expansion_per_k')
        _number(p['reference_temperature_k'], path+'.reference_temperature_k', nonnegative=True)
    _vector(p.get('body_force_n_m3', [0., 0.]), path+'.body_force_n_m3')
    fixed = _displacement(p['displacement_m'], path+'.displacement_m')
    if not rigid_modes_fixed(fixed):
        raise DocumentError(path+'.displacement_m: constraints leave a rigid-body motion free; '
                            'fix x and y, and block rotation (x on left/right, y on bottom/top, '
                            'x on both bottom and top, or y on both left and right)')
    traction = p.get('traction_pa', {})
    _object(traction, SIDES, path+'.traction_pa')
    for side, vector in traction.items():
        t = _vector(vector, path+'.traction_pa.'+side)
        for i, c in enumerate(COMPONENTS):
            if (side, c) in fixed and t[i] != 0:
                raise DocumentError(f'{path}.traction_pa.{side}: nonzero {c} traction on a side whose '
                                    f'{c} displacement is prescribed')
    doc.scale = units.resolve(d['units'])
    doc.notes = []


def document_summary(doc):
    from .mechanics_regions import is_region_mechanics, region_mechanics_summary
    if is_region_mechanics(doc.data):
        doc.validate()
        return region_mechanics_summary(doc)
    doc.validate()
    name, p = doc.sole_physics()
    thermal = p['type'] == THERMOELASTIC
    return (f'{doc["name"]} (openphysics 0.2)\n  physics {name}: {p["type"]}, headless single static rectangle, '
            f'plane {p["plane"]}' + (', steady heat then prescribed-temperature mechanics' if thermal else '')
            + f'\n  domain {doc.domain} {doc.length_unit}; mesh {doc["mesh"]["subdivisions"]}\n'
            '  SI output: displacement m, strain 1, stress Pa; nodal loads and reactions N/m of depth'
            + ('; temperature K, heat W/m of depth' if thermal else ''))


def _fixed_dofs(mesh, displacement):
    """{(node, component): m} sorted by (node, component); corners agree by validation."""
    fixed = {}
    for side, components in displacement.items():
        for component, value in components.items():
            for node in mesh.boundary[side]:
                fixed[int(node), COMPONENTS.index(component)] = float(value)
    return dict(sorted(fixed.items()))


def _norm(a):
    return float(np.max(abs(np.asarray(a)), initial=0.))


class MechanicsRunResult:
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
            raise ValueError('mechanics result document changed after the solve; run again')
        return json.loads(self._metadata_json)

    def save(self, outdir):
        summary = self.summary()
        encoded = json.dumps(summary, indent=2, allow_nan=False).encode('utf-8')
        owned = _OwnedOutput(outdir)
        try:
            owned.write('.incomplete', lambda f: f.write(b'incomplete mechanics result\n'))
            owned.write('model.json', lambda f: f.write(self._document_json.encode('utf-8')))
            owned.write('log.txt', lambda f: f.write(('\n'.join(self._log)+'\n').encode('utf-8')))
            if self.doc['results']['save_fields']:
                arrays = dict(self._arrays, result_format=summary['result_format'],
                              field_layout=summary['field_layout'], mesh_length_unit='m',
                              metadata_json=encoded.decode('utf-8'))
                owned.write('fields.npz', lambda f: np.savez_compressed(f, **arrays))
            owned.write('summary.json', lambda f: f.write(encoded))
            owned.finish()
        except Exception:
            owned.cleanup()
            raise
        finally:
            owned.close()
        return owned.path


def heat_inputs(doc, mesh):
    """The ``solve_steady_heat`` keyword arguments of a thermoelastic document on ``mesh``."""
    return steady_boundary_inputs(_thermal_document(doc), mesh)


def solver_inputs(doc, mesh):
    """The mechanical keyword arguments of a validated document on ``mesh``.

    For ``mechanics.elasticity2d`` these are the ``solve_elasticity`` arguments; a
    thermoelastic document adds ``reference_temperature_k`` and ``thermal_expansion_per_k``
    for ``solve_thermoelasticity``, whose temperature snapshot comes from the heat
    solve. Dirichlet DOFs are sorted by (node, component); the body force is a (2,)
    tuple and each traction a global Cartesian [tx, ty] list in Pa. ``mesh`` must be
    the document's rectangle in metres (``build_rectangle``); the shared heat mesh
    checks run on it first. The values come from the document's internal SI view
    (``simcase.views.rectangle_mechanics``).
    """
    doc.sole_physics()      # one physics entry, refused by name before any mesh check
    steady_boundary_inputs(_thermal_document(doc), mesh)
    m = views.rectangle_mechanics(doc)
    traction = {side: [float(v) for v in vector] for side, vector in m.traction.items()}
    inputs = dict(young_modulus=float(m.young_modulus), poisson_ratio=float(m.poisson_ratio),
                  plane=m.plane, dirichlet=_fixed_dofs(mesh, m.displacement),
                  body_force=tuple(float(v) for v in m.body_force),
                  traction=traction or None)
    if m.thermoelastic:
        inputs.update(reference_temperature_k=float(m.reference_temperature),
                      thermal_expansion_per_k=float(m.thermal_expansion))
    return inputs


def build_rectangle(doc):
    """The document's structured rectangle mesh in metres, nodes offset to the domain origin; the
    side lengths subtract the converted corners (views.LENGTH_FORMULAS)."""
    from galerkin import rectangle_mesh
    grid = views.rectangle_mesh(doc, 'corners')
    mesh = rectangle_mesh(*grid.lengths, *grid.subdivisions)
    mesh.nodes += grid.origin
    return mesh


def run_mechanics(doc, verbose=True, *, mesh_limits=None):
    from .mechanics_regions import is_region_mechanics, run_region_mechanics
    if is_region_mechanics(doc.data):
        return run_region_mechanics(doc, verbose=verbose, mesh_limits=mesh_limits)
    doc.validate()
    doc = Document.from_dict(doc.data)
    thermal = doc.sole_physics()[1]['type'] == THERMOELASTIC
    start = time.perf_counter()
    mesh = build_rectangle(doc)
    inputs = solver_inputs(doc, mesh)
    heat_args = heat_inputs(doc, mesh) if thermal else None
    return solve_and_package(doc, mesh, inputs, heat_args, time.perf_counter()-start, verbose)


def solve_and_package(doc, mesh, inputs, heat_args, mesh_time, verbose, region=None):
    """Solve a validated document's mechanics on ``mesh`` and return its MechanicsRunResult.

    ``inputs`` are the mechanical solver arguments, ``heat_args`` the steady heat arguments of a
    thermoelastic document (None otherwise). ``region`` is None for a rectangle document; a
    region document (mechanics_regions.py) passes ``triangle_regions``, ``result_format``,
    ``field_layout``, ``metadata`` (replacing the scalar material entries), ``summary`` (the log
    header) and ``log`` (extra log lines).
    """
    from galerkin.elasticity import solve_elasticity
    from galerkin.thermal import solve_steady_heat
    from galerkin.thermoelasticity import freeze_temperature, solve_thermoelasticity
    import galerkin
    import scipy
    from . import __version__
    name, p = doc.sole_physics()
    kind = p['type']
    thermal = kind == THERMOELASTIC
    start = time.perf_counter()
    heat = snapshot = None
    try:
        if thermal:
            heat = solve_steady_heat(mesh, **heat_args)
            snapshot = freeze_temperature(mesh, heat.temperature)
            solved = solve_thermoelasticity(mesh, snapshot, **inputs)
        else:
            solved = solve_elasticity(mesh, **inputs)
    except (ValueError, RuntimeError) as exc:
        if region is None:
            raise
        raise ValueError(f'physics.{name} ({kind}): {exc}') from exc
    solve_time = time.perf_counter()-start
    arrays, field_units, locations = {}, {}, {}
    def add(key, value, unit, location):
        arrays[key] = np.asarray(value)
        field_units[key], locations[key] = unit, location
    add('nodes_m', mesh.nodes, 'm', 'nodes')
    add('triangles', mesh.triangles, '1', 'triangle_connectivity')
    if region is not None:
        add('triangle_regions', region['triangle_regions'], '1', 'triangles')
    diagnostics = {}
    if thermal:
        add('temperature_k', heat.temperature, 'K', 'nodes')
        add('heat_flux_w_m2', heat.heat_flux, 'W/m^2', 'triangle_centroids')
        for key, attr in (('thermal_load', 'load'), ('thermal_reaction', 'reaction'), ('thermal_residual', 'residual'),
                          ('prescribed_outward_heat', 'prescribed_outward_load'), ('ambient_load', 'ambient_load'),
                          ('convective_outward_heat', 'convective_outward'), ('thermal_system_rhs', 'system_rhs')):
            add(key+'_w_per_m', getattr(heat, attr), 'W/m', 'nodes')
        fixed_t = heat_args['dirichlet']
        add('thermal_dirichlet_node_ids', np.array(list(fixed_t), dtype=int), '1', 'thermal_dirichlet_nodes')
        add('dirichlet_temperature_k', list(fixed_t.values()), 'K', 'thermal_dirichlet_nodes')
        free_t = np.setdiff1d(np.arange(mesh.num_nodes), list(fixed_t))
        outward = float(np.sum(-heat.reaction+heat.prescribed_outward_load+heat.convective_outward))
        diagnostics.update(source_heat_w_per_m=float(heat.load.sum()), outward_heat_w_per_m=outward,
            heat_power_defect_w_per_m=outward-float(heat.load.sum()),
            thermal_free_residual_w_per_m=_norm(heat.residual[free_t]),
            temperature_min_k=float(heat.temperature.min()), temperature_max_k=float(heat.temperature.max()))
        add('displacement_m', solved.displacement, 'm', 'nodes')
        add('total_strain', solved.total_strain, '1', 'triangle_centroids')
        add('thermal_strain', solved.thermal_strain, '1', 'triangle_centroids')
        add('elastic_strain', solved.elastic_strain, '1', 'triangle_centroids')
        add('stress_pa', solved.stress, 'Pa', 'triangle_centroids')
        add('sigma_zz_pa', solved.sigma_zz, 'Pa', 'triangle_centroids')
        add('epsilon_zz', solved.epsilon_zz, '1', 'triangle_centroids')
        for key, attr in (('load_external_n_per_m', 'load_external'), ('load_thermal_n_per_m', 'load_thermal'),
                          ('load_body_n_per_m', 'load_body'), ('load_traction_n_per_m', 'load_traction'),
                          ('reaction_n_per_m', 'reaction'), ('residual_n_per_m', 'residual')):
            add(key, getattr(solved, attr), 'N/m', 'nodes')
        load = arrays['load_external_n_per_m']+arrays['load_thermal_n_per_m']
    else:
        add('displacement_m', solved.displacement, 'm', 'nodes')
        add('strain', solved.strain, '1', 'triangle_centroids')
        add('stress_pa', solved.stress, 'Pa', 'triangle_centroids')
        for key, attr in (('load_n_per_m', 'load'), ('reaction_n_per_m', 'reaction'), ('residual_n_per_m', 'residual')):
            add(key, getattr(solved, attr), 'N/m', 'nodes')
        load = arrays['load_n_per_m']
    fixed = inputs['dirichlet']
    add('dirichlet_node_ids', np.array([node for node, _ in fixed], dtype=int), '1', 'dirichlet_dofs')
    add('dirichlet_components', np.array([component for _, component in fixed], dtype=int), '1', 'dirichlet_dofs')
    add('dirichlet_displacement_m', list(fixed.values()), 'm', 'dirichlet_dofs')
    free = np.ones((mesh.num_nodes, 2), dtype=bool)
    free[arrays['dirichlet_node_ids'], arrays['dirichlet_components']] = False
    u, reaction, residual = arrays['displacement_m'], arrays['reaction_n_per_m'], arrays['residual_n_per_m']
    diagnostics.update(
        free_residual_n_per_m=_norm(residual[free]),
        applied_load_n_per_m=[float(v) for v in load.sum(axis=0)],
        support_reaction_n_per_m=[float(v) for v in reaction.sum(axis=0)],
        force_balance_n_per_m=[float(v) for v in (load+reaction).sum(axis=0)],
        strain_energy_j_per_m=float(.5*np.sum(u*(load+residual))),
        max_displacement_m=float(np.max(np.hypot(u[:, 0], u[:, 1]), initial=0.)),
        max_abs_stress_pa=_norm(arrays['stress_pa']))
    if thermal:
        diagnostics.update(external_load_n_per_m=[float(v) for v in arrays['load_external_n_per_m'].sum(axis=0)],
                           thermal_load_n_per_m=[float(v) for v in arrays['load_thermal_n_per_m'].sum(axis=0)],
                           physical_elastic_energy_j_per_m=float(solved.physical_elastic_energy))
    diagnostic_units = dict(free_residual='N/m', applied_load='N/m', support_reaction='N/m', force_balance='N/m',
                            strain_energy='J/m', max_displacement='m', max_abs_stress='Pa')
    if region is None:
        metadata = dict(name=doc['name'], physics_name=name, physics_type=kind, status='solved',
            result_format=kind+'-result-v1', field_layout=FIELD_LAYOUTS[kind], mesh_length_unit='m',
            input_units=copy.deepcopy(doc['units']), plane=p['plane'],
            young_modulus_pa=inputs['young_modulus'], poisson_ratio=inputs['poisson_ratio'])
    else:
        metadata = dict(name=doc['name'], physics_name=name, physics_type=kind, status='solved',
            result_format=region['result_format'], field_layout=region['field_layout'], mesh_length_unit='m',
            input_units=copy.deepcopy(doc['units']), plane=p['plane'], **region['metadata'])
    metadata.update(body_force_n_m3=list(inputs['body_force']),
        displacement_components=list(COMPONENTS), strain_components=list(STRAIN_COMPONENTS),
        stress_components=list(STRESS_COMPONENTS))
    if thermal:
        if region is None:
            metadata.update(thermal_expansion_per_k=inputs['thermal_expansion_per_k'])
        metadata.update(reference_temperature_k=inputs['reference_temperature_k'])
        if region is None:
            metadata.update(thermal_conductivity_w_mk=heat_args['conductivity'])
        metadata.update(temperature_snapshot=dict(mesh_hash=snapshot.mesh_hash,
                                                  temperature_hash=snapshot.temperature_hash,
                                                  snapshot_hash=snapshot.snapshot_hash))
        diagnostic_units.update(source_heat='W/m', outward_heat='W/m', heat_power_defect='W/m',
                                thermal_free_residual='W/m', temperature_min='K', temperature_max='K',
                                external_load='N/m', thermal_load='N/m', physical_elastic_energy='J/m')
    metadata.update(field_units=field_units, field_locations=locations,
        field_shapes={k: list(v.shape) for k, v in arrays.items()}, diagnostics=diagnostics,
        diagnostic_units=diagnostic_units, timings_s=dict(mesh=mesh_time, solve=solve_time),
        software_versions=dict(simcase=__version__, galerkin=galerkin.__version__, numpy=np.__version__,
                               scipy=scipy.__version__))
    log = [document_summary(doc) if region is None else region['summary'], *([] if region is None else region['log']),
           f'Solved {mesh.num_nodes} nodes, {mesh.num_triangles} triangles; '
           f'max displacement {diagnostics["max_displacement_m"]:.12g} m, '
           f'strain energy {diagnostics["strain_energy_j_per_m"]:.12g} J/m of depth']
    if thermal:
        log.append(f'Temperature {diagnostics["temperature_min_k"]:.12g} to {diagnostics["temperature_max_k"]:.12g} K; '
                   f'outward heat {diagnostics["outward_heat_w_per_m"]:.12g} W/m of depth')
    if verbose:
        print('\n'.join(log))
    return MechanicsRunResult(doc, arrays, metadata, log)


def _defaults():
    from .thermal import defaults
    return defaults()


def _accepts_mesh_limits(data):
    """Region documents take mesh limits (simcase.mesh_limits); rectangle documents do not."""
    from .mechanics_regions import is_region_mechanics
    return is_region_mechanics(data)


register(PhysicsKind(
    name='mechanics', types=frozenset(TYPES), precedence=15,
    validate=validate_mechanics, run=run_mechanics, summary=document_summary,
    result_types=(MechanicsRunResult,), defaults=_defaults, fresh_output=True,
    stage_refusal='{stage} is an EM stage; use run(document) for mechanics physics',
    accepts_mesh_limits=_accepts_mesh_limits))
