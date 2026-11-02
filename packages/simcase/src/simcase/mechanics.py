# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Strict headless rectangle adapter for the existing 2D elasticity solver.

One homogeneous isotropic rectangle, plane stress or plane strain, side-constant
displacement components and global Cartesian side tractions, an optional constant
body force. The document is projected into the steady heat contract for the shared
rectangle, unit, mesh, study and result checks, exactly as the electric/Joule
adapter does; the mechanics keys are validated here. ``run_mechanics`` builds the
mesh once in metres and calls ``galerkin.elasticity.solve_elasticity`` with no
new discretization.
"""
import copy
import json
import time

import numpy as np

from .schema import Document, DocumentError
from .steady_boundary_contract import SIDES, _number, _object, validate_steady_boundary, steady_boundary_inputs
from .thermal import _OwnedOutput
from . import units
from .registry import PhysicsKind, register

TYPES = {'mechanics.elasticity2d'}
PHYSICS = 'mechanics.elasticity2d'
RESULT_FORMAT = PHYSICS+'-result-v1'
FIELD_LAYOUT = 'mechanics2d-p1-v1'
MAX_TRIANGLES = 200_000
PLANES = ('stress', 'strain')
COMPONENTS = ('x', 'y')
STRAIN_COMPONENTS = ('exx', 'eyy', 'gxy')
STRESS_COMPONENTS = ('sxx', 'syy', 'sxy')


def is_mechanics(data):
    return isinstance(data, dict) and isinstance(data.get('physics'), dict) and any(
        isinstance(p, dict) and p.get('type') in TYPES for p in data['physics'].values())


def _thermal_document(doc):
    """Project the shared geometry, mesh, study and result sections into the heat contract."""
    d = copy.deepcopy(doc.data)
    d['units'] = {'length': d['units'].get('length'), 'temperature': 'K'}
    d['physics'] = {'heat': dict(type='thermal.steady2d', conductivity_w_mk=1.,
                                 dirichlet_temperature_k={'left': 0.})}
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
    d = doc.data
    top = {'openphysics', 'name', 'units', 'geometry', 'materials', 'physics', 'mesh', 'study', 'results'}
    _object(d, top, 'document', top)
    _object(d['units'], {'length'}, 'units', {'length'})
    physics = d['physics']
    if not isinstance(physics, dict) or len(physics) != 1:
        raise DocumentError('physics: exactly one mechanics entry required')
    name, p = next(iter(physics.items()))
    if not isinstance(name, str) or not name.isidentifier() or not isinstance(p, dict):
        raise DocumentError('physics: expected identifier and settings object')
    if p.get('type') not in TYPES:
        raise DocumentError('unsupported mechanics physics')
    path = 'physics.'+name
    required = {'type', 'plane', 'young_modulus_pa', 'poisson_ratio', 'displacement_m'}
    _object(p, required | {'body_force_n_m3', 'traction_pa'}, path, required)
    # Reuse the strict rectangle, length unit, mesh, study and result checks.
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
    doc.validate()
    name, p = doc.sole_physics()
    return (f'{doc["name"]} (openphysics 0.2)\n  physics {name}: {p["type"]}, headless single static rectangle, '
            f'plane {p["plane"]}\n  domain {doc.domain} {doc.length_unit}; mesh {doc["mesh"]["subdivisions"]}\n'
            '  SI output: displacement m, strain 1, stress Pa; nodal loads and reactions N/m of depth')


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
                arrays = dict(self._arrays, result_format=RESULT_FORMAT, field_layout=FIELD_LAYOUT,
                              mesh_length_unit='m', metadata_json=encoded.decode('utf-8'))
                owned.write('fields.npz', lambda f: np.savez_compressed(f, **arrays))
            owned.write('summary.json', lambda f: f.write(encoded))
            owned.finish()
        except Exception:
            owned.cleanup()
            raise
        finally:
            owned.close()
        return owned.path


def solver_inputs(doc, mesh):
    """The ``solve_elasticity`` keyword arguments of a validated document on ``mesh``.

    Dirichlet DOFs are sorted by (node, component); the body force is a (2,) tuple
    and each traction a global Cartesian [tx, ty] list in Pa. ``mesh`` must be the
    document's rectangle in metres (``build_rectangle``); the shared heat mesh checks
    run on it first.
    """
    name, p = doc.sole_physics()
    steady_boundary_inputs(_thermal_document(doc), mesh)
    traction = {side: [float(v) for v in vector] for side, vector in p.get('traction_pa', {}).items()}
    return dict(young_modulus=float(p['young_modulus_pa']), poisson_ratio=float(p['poisson_ratio']),
                plane=p['plane'], dirichlet=_fixed_dofs(mesh, p['displacement_m']),
                body_force=tuple(float(v) for v in p.get('body_force_n_m3', [0., 0.])),
                traction=traction or None)


def build_rectangle(doc):
    """The document's structured rectangle mesh in metres, nodes offset to the domain origin."""
    from galerkin import rectangle_mesh
    bounds = {k: doc.scale.to_si(v, {'length': 1}) for k, v in doc.domain.items()}
    mesh = rectangle_mesh(bounds['xmax']-bounds['xmin'], bounds['ymax']-bounds['ymin'],
                          *doc['mesh']['subdivisions'])
    mesh.nodes += [bounds['xmin'], bounds['ymin']]
    return mesh


def run_mechanics(doc, verbose=True):
    from galerkin.elasticity import solve_elasticity
    import galerkin
    import scipy
    from . import __version__
    doc.validate()
    doc = Document.from_dict(doc.data)
    name, p = doc.sole_physics()
    start = time.perf_counter()
    mesh = build_rectangle(doc)
    inputs = solver_inputs(doc, mesh)
    mesh_time = time.perf_counter()-start
    start = time.perf_counter()
    solved = solve_elasticity(mesh, **inputs)
    solve_time = time.perf_counter()-start
    arrays, field_units, locations = {}, {}, {}
    def add(key, value, unit, location):
        arrays[key] = np.asarray(value)
        field_units[key], locations[key] = unit, location
    add('nodes_m', mesh.nodes, 'm', 'nodes')
    add('triangles', mesh.triangles, '1', 'triangle_connectivity')
    add('displacement_m', solved.displacement, 'm', 'nodes')
    add('strain', solved.strain, '1', 'triangle_centroids')
    add('stress_pa', solved.stress, 'Pa', 'triangle_centroids')
    for key, attr in (('load_n_per_m', 'load'), ('reaction_n_per_m', 'reaction'), ('residual_n_per_m', 'residual')):
        add(key, getattr(solved, attr), 'N/m', 'nodes')
    fixed = inputs['dirichlet']
    add('dirichlet_node_ids', np.array([node for node, _ in fixed], dtype=int), '1', 'dirichlet_dofs')
    add('dirichlet_components', np.array([component for _, component in fixed], dtype=int), '1', 'dirichlet_dofs')
    add('dirichlet_displacement_m', list(fixed.values()), 'm', 'dirichlet_dofs')
    free = np.ones((mesh.num_nodes, 2), dtype=bool)
    free[arrays['dirichlet_node_ids'], arrays['dirichlet_components']] = False
    u, load, residual = arrays['displacement_m'], arrays['load_n_per_m'], arrays['residual_n_per_m']
    diagnostics = dict(
        free_residual_n_per_m=_norm(residual[free]),
        applied_load_n_per_m=[float(v) for v in load.sum(axis=0)],
        support_reaction_n_per_m=[float(v) for v in arrays['reaction_n_per_m'].sum(axis=0)],
        force_balance_n_per_m=[float(v) for v in (load+arrays['reaction_n_per_m']).sum(axis=0)],
        strain_energy_j_per_m=float(.5*np.sum(u*(load+residual))),
        max_displacement_m=float(np.max(np.hypot(u[:, 0], u[:, 1]), initial=0.)),
        max_abs_stress_pa=_norm(arrays['stress_pa']))
    metadata = dict(name=doc['name'], physics_name=name, physics_type=p['type'], status='solved',
        result_format=RESULT_FORMAT, field_layout=FIELD_LAYOUT, mesh_length_unit='m',
        input_units=copy.deepcopy(doc['units']), plane=p['plane'],
        young_modulus_pa=inputs['young_modulus'], poisson_ratio=inputs['poisson_ratio'],
        body_force_n_m3=list(inputs['body_force']),
        displacement_components=list(COMPONENTS), strain_components=list(STRAIN_COMPONENTS),
        stress_components=list(STRESS_COMPONENTS),
        field_units=field_units, field_locations=locations,
        field_shapes={k: list(v.shape) for k, v in arrays.items()}, diagnostics=diagnostics,
        diagnostic_units=dict(free_residual='N/m', applied_load='N/m', support_reaction='N/m',
                              force_balance='N/m', strain_energy='J/m', max_displacement='m',
                              max_abs_stress='Pa'),
        timings_s=dict(mesh=mesh_time, solve=solve_time),
        software_versions=dict(simcase=__version__, galerkin=galerkin.__version__, numpy=np.__version__,
                               scipy=scipy.__version__))
    log = [document_summary(doc), f'Solved {mesh.num_nodes} nodes, {mesh.num_triangles} triangles; '
           f'max displacement {diagnostics["max_displacement_m"]:.12g} m, '
           f'strain energy {diagnostics["strain_energy_j_per_m"]:.12g} J/m of depth']
    if verbose:
        print('\n'.join(log))
    return MechanicsRunResult(doc, arrays, metadata, log)


def _defaults():
    from .thermal import defaults
    return defaults()


register(PhysicsKind(
    name='mechanics', types=frozenset(TYPES), precedence=15,
    validate=validate_mechanics, run=run_mechanics, summary=document_summary,
    result_types=(MechanicsRunResult,), defaults=_defaults, fresh_output=True,
    stage_refusal='{stage} is an EM stage; use run(document) for mechanics physics'))
