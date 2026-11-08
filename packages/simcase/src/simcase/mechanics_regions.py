# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Elasticity and thermoelastic documents on named material regions.

A ``mechanics.elasticity2d`` or ``mechanics.thermoelastic2d`` document whose geometry declares
regions (a 0.2 ``background``/``shapes`` block or a version 1 region component) takes E, nu and
alpha from the shared ``materials`` table (``young_modulus_pa``, ``poisson_ratio``,
``thermal_expansion_per_k``), and the thermoelastic heat stage takes ``conductivity_w_mk`` from
it as region heat does. Displacement, traction and pressure data name the boundaries region heat
names: the domain sides, ``boundary_tags`` names, ``outer`` on a void border and exterior
boundary selections. An interface selection is refused for them: galerkin fixes exterior nodes
only and a traction needs exterior edges. The mesh, region and heat helpers are those of
thermal_regions.py; the solve and the result packaging are those of mechanics.py. The rectangle
documents of mechanics.py are not changed. See docs/packages/simcase/mechanics2d.md.
"""
import copy
import time

import numpy as np

from .schema import DocumentError, check_format_units_and_tags
from .thermal import _number
from .thermal_regions import MATERIAL_KEYS as SHARED_MATERIAL_KEYS
from .thermal_regions import (SIDES, _sides, boundary_names, build_region_mesh, covered_shapes,
                              has_region_geometry, is_axisymmetric, region_geometry, region_inputs,
                              region_materials_table, region_mesh_settings, region_source)
from .mechanics import COMPONENTS, ELASTIC, PLANES, THERMOELASTIC, TYPES, solve_and_package

RESULT_FORMATS = {ELASTIC: ELASTIC+'-regions-result-v1', THERMOELASTIC: THERMOELASTIC+'-regions-result-v1'}
FIELD_LAYOUTS = {ELASTIC: 'mechanics2d-p1-regions-v1', THERMOELASTIC: 'thermoelastic2d-p1-regions-v1'}
#: the material keys each type reads from ``materials`` (thermal_regions.MATERIAL_KEYS holds the union)
MATERIAL_KEYS = {ELASTIC: ('young_modulus_pa', 'poisson_ratio'),
                 THERMOELASTIC: ('young_modulus_pa', 'poisson_ratio', 'thermal_expansion_per_k', 'conductivity_w_mk')}
#: physics keys of the rectangle contract that a region document takes from ``materials``
FROM_MATERIALS = {'young_modulus_pa': 'young_modulus_pa', 'poisson_ratio': 'poisson_ratio',
                  'thermal_expansion_per_k': 'thermal_expansion_per_k',
                  'thermal_conductivity_w_mk': 'conductivity_w_mk', 'conductivity_w_mk': 'conductivity_w_mk'}
HEAT_KEYS = {'reference_temperature_k', 'heat_source_w_m3', 'dirichlet_temperature_k', 'outward_flux_w_m2',
             'convection'}
TOP = {'openphysics', 'name', 'units', 'geometry', 'materials', 'physics', 'mesh', 'study', 'results'}


def is_region_mechanics(data):
    """A mechanics document that declares region geometry."""
    return any(has_region_geometry(data, kind) for kind in TYPES)


def _vector(value, path):
    if not isinstance(value, list) or len(value) != 2:
        raise DocumentError(path+': expected [x, y]')
    for i, v in enumerate(value):
        _number(v, f'{path}[{i}]')
    return [float(v) for v in value]


def _keys(value, keys, path):
    """An object whose keys are among ``keys``; an unknown key is refused by name."""
    if not isinstance(value, dict):
        raise DocumentError(f'{path}: expected an object')
    unknown = set(value) - set(keys)
    if unknown:
        raise DocumentError(f'{path}: unsupported mechanics keys {sorted(map(str, unknown))}')


def _boundary_names(value, allowed, interior, path):
    """``_keys`` over the boundaries a mechanics entry may name (an unknown name is not a domain
    side, an exterior tag or an exterior boundary selection); an interface selection is refused
    by name."""
    if isinstance(value, dict):
        for key in value:
            if key in interior:
                raise DocumentError(f'{path}.{key}: selection {key!r} lies on an interface between two regions; '
                                    'displacement, traction and pressure apply to exterior boundaries only')
    _keys(value, allowed, path)


def validate_region_mechanics(doc):
    d = doc.data
    _keys(d, TOP, 'document')
    if not isinstance(d['name'], str):
        raise DocumentError('name: expected a string')
    check_format_units_and_tags(doc)
    physics = d['physics']
    if not isinstance(physics, dict) or len(physics) != 1:
        raise DocumentError('physics: exactly one mechanics entry required')
    name, p = doc.sole_physics()
    if not isinstance(name, str) or not name.isidentifier() or not isinstance(p, dict):
        raise DocumentError('physics: expected identifier and settings object')
    kind = p.get('type')
    if kind not in TYPES:
        raise DocumentError('unsupported mechanics physics')
    thermal = kind == THERMOELASTIC
    path = 'physics.'+name
    if thermal:
        _keys(d.get('units'), {'length', 'temperature'}, 'units')
        if 'length' not in doc.scale.declared or d['units'].get('temperature') != 'K':
            raise DocumentError(f'{kind} requires explicit units.length and units.temperature="K"')
    else:
        _keys(d.get('units'), {'length'}, 'units')
        if 'length' not in doc.scale.declared:
            raise DocumentError(f'{kind} requires explicit units.length')
    if is_axisymmetric(doc):
        raise DocumentError(f'component {doc.component.name!r}: {kind} takes 2d components only; an axisymmetric '
                            'component is a body of revolution, which this plane mechanics does not describe '
                            '(steady and transient region heat take it)')
    for key, material_key in FROM_MATERIALS.items():
        if key in p:
            raise DocumentError(f'{path}.{key}: a region document takes {material_key} from materials')
    keys = {'type', 'plane', 'displacement_m', 'traction_pa', 'pressure_pa', 'body_force_n_m3'}
    required = {'type', 'plane', 'displacement_m'}
    if thermal:
        keys |= HEAT_KEYS
        required |= {'reference_temperature_k'}
    _keys(p, keys, path)
    missing = required - set(p)
    if missing:
        raise DocumentError(f'{path}: missing {sorted(missing)}')
    names = region_geometry(doc, 'mechanics')
    materials = d['materials']
    if isinstance(materials, dict):
        # the shared table's keys, refused here in mechanics words; the shared check follows
        for mname, spec in materials.items():
            if isinstance(spec, dict) and 'thermal_conductivity_w_mk' in spec:
                raise DocumentError(f'materials.{mname}.thermal_conductivity_w_mk: the materials table names thermal '
                                    'conductivity conductivity_w_mk (the rectangle thermoelastic physics key '
                                    'thermal_conductivity_w_mk is not a material key)')
            if isinstance(spec, dict):
                _keys(spec, SHARED_MATERIAL_KEYS, f'materials.{mname}')
    region_materials_table(doc, MATERIAL_KEYS[kind], kind)
    if p['plane'] not in PLANES:
        raise DocumentError(path+'.plane: expected "stress" or "strain"')
    _vector(p.get('body_force_n_m3', [0., 0.]), path+'.body_force_n_m3')
    tags, outside, inside = boundary_names(doc)
    allowed = set(SIDES) | tags | outside
    displacement = p['displacement_m']
    _boundary_names(displacement, allowed, inside, path+'.displacement_m')
    held = set()
    for tag, components in displacement.items():
        where = f'{path}.displacement_m.{tag}'
        _keys(components, COMPONENTS, where)
        if not components:
            raise DocumentError(where+': expected x and/or y')
        for component, value in components.items():
            _number(value, where+'.'+component)
            held.add(component)
    if held != set(COMPONENTS):
        raise DocumentError(f'{path}.displacement_m: constraints leave a rigid-body motion free; fix x and y '
                            'somewhere, and block rotation')
    traction = p.get('traction_pa', {})
    _boundary_names(traction, allowed, inside, path+'.traction_pa')
    for tag, vector in traction.items():
        t = _vector(vector, f'{path}.traction_pa.{tag}')
        for i, c in enumerate(COMPONENTS):
            if c in displacement.get(tag, {}) and t[i] != 0:
                raise DocumentError(f'{path}.traction_pa.{tag}: nonzero {c} traction on a boundary whose {c} '
                                    'displacement is prescribed')
    pressure = p.get('pressure_pa', {})
    _boundary_names(pressure, allowed, inside, path+'.pressure_pa')
    for tag, value in pressure.items():
        _number(value, f'{path}.pressure_pa.{tag}')
        if tag in traction:
            raise DocumentError(f'{path}.pressure_pa.{tag}: {tag!r} also has a traction; give that boundary one '
                                'entry')
    if thermal:
        _number(p['reference_temperature_k'], path+'.reference_temperature_k', nonnegative=True)
        region_source(p, names, path)
        _sides(p, name, SIDES, (tags, outside, inside))
    _keys(d['mesh'], {'size', 'min_angle', 'controls'}, 'mesh')
    region_mesh_settings(doc)
    if d['study'] != {'type': 'single'}:
        raise DocumentError(f'{kind} supports only study {{"type":"single"}}')
    _keys(d['results'], {'save_fields', 'plots'}, 'results')
    if not isinstance(d['results'].get('save_fields'), bool) or not isinstance(d['results'].get('plots'), bool):
        raise DocumentError('results.save_fields and results.plots must be booleans')
    if d['results']['plots']:
        raise DocumentError(f'results.plots: {kind} is headless; plots=true is not supported')
    doc.notes = []


def region_mechanics_summary(doc):
    name, p = doc.sole_physics()
    thermal = p['type'] == THERMOELASTIC
    lines = [f'{doc["name"]} (openphysics 0.2)',
             f'  physics {name}: {p["type"]}, headless single static solve, named material regions, plane '
             f'{p["plane"]}' + (', steady heat then prescribed-temperature mechanics' if thermal else ''),
             f'  domain {doc.domain} {doc.length_unit}; mesh size {doc["mesh"]["size"]} {doc.length_unit}',
             f'  background: {doc.background["material"]}']
    for s in doc.regions():
        lines.append(f'  shape {s["name"]}: {s["type"]}, {s["material"] if s["material"] is not None else "void (hole)"}')
    for mname, spec in doc['materials'].items():
        lines.append(f'  material {mname}: ' + ', '.join(f'{k}={spec[k]}' for k in MATERIAL_KEYS[p['type']] if k in spec))
    lines += [f'  displacement {p["displacement_m"]} m; traction {p.get("traction_pa", {})} Pa; '
              f'pressure {p.get("pressure_pa", {})} Pa; other exterior traction free',
              '  SI output: displacement m, strain 1, stress Pa; nodal loads and reactions N/m of depth; '
              'triangle regions' + ('; temperature K, heat W/m of depth' if thermal else '')]
    return '\n'.join(lines)


def _edge_set(mesh, tag):
    return {tuple(sorted(map(int, e))) for e in np.asarray(mesh.boundary_edges[tag]).reshape(-1, 2)}


def rigid_free_regions(mesh, fixed):
    """The region names of each connected part of the mesh that ``fixed`` ({(node, component): m})
    does not hold against all three planar rigid motions (the rank test galerkin applies)."""
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components
    p, t = np.asarray(mesh.nodes, dtype=float), np.asarray(mesh.triangles)
    rows, cols = t.ravel(), np.roll(t, -1, axis=1).ravel()
    count, labels = connected_components(coo_matrix((np.ones(len(rows)), (rows, cols)),
                                                     shape=(len(p), len(p))), directed=False)
    keys = np.array(list(fixed), dtype=int).reshape(-1, 2)
    free = []
    for c in range(count):
        nodes = np.flatnonzero(labels == c)
        local = keys[labels[keys[:, 0]] == c] if len(keys) else keys
        xy = (p[local[:, 0]] - p[nodes].mean(axis=0)) / np.ptp(p[nodes], axis=0).max()
        rigid = np.column_stack([local[:, 1] == 0, local[:, 1] == 1,
                                 np.where(local[:, 1] == 0, -xy[:, 1], xy[:, 0])])
        if len(local) < 3 or np.linalg.matrix_rank(rigid, tol=1e-10) < 3:
            ids = np.unique(np.asarray(mesh.regions)[labels[t[:, 0]] == c])
            free.append(sorted(mesh.region_names[int(i)] for i in ids))
    return free


def region_mechanics_inputs(doc, mesh, region_materials):
    """The solve_elasticity (or solve_thermoelasticity) keyword arguments of a meshed region document.

    E, nu (and alpha) are {region name: value} from ``materials``; Dirichlet DOFs are sorted by
    (node, component); each traction is a global [tx, ty] in Pa and each pressure p the callback
    ``-p * outward normal`` on its boundary edges.
    """
    name, p = doc.sole_physics()
    path = f'physics.{name}'
    materials = doc['materials']
    for label, table in (('displacement_m', mesh.boundary), ('traction_pa', mesh.boundary_edges),
                         ('pressure_pa', mesh.boundary_edges)):
        for tag in p.get(label, {}):
            if tag not in table:
                raise DocumentError(f'{path}.{label}.{tag}: no mesh edge lies on {tag!r} (a side or boundary that '
                                    'borders a void feature only, or a selection without mesh edges)')
    fixed, fixed_by = {}, {}
    for tag, components in p['displacement_m'].items():
        for component, value in components.items():
            for node in mesh.boundary[tag]:
                key = (int(node), COMPONENTS.index(component))
                if key in fixed and fixed[key] != float(value):
                    raise DocumentError(f'{path}.displacement_m: {fixed_by[key]!r} and {tag!r} share node {key[0]} '
                                        f'with different {component} displacements')
                fixed[key], fixed_by[key] = float(value), tag
    fixed = dict(sorted(fixed.items()))
    free = rigid_free_regions(mesh, fixed)
    if free:
        raise DocumentError(f'{path}.displacement_m: constraints leave a rigid-body motion free in the part of the '
                            f'body made of regions {free[0]}; each connected part needs x and y fixed and rotation '
                            'blocked')
    traction = {tag: [float(v) for v in vector] for tag, vector in p.get('traction_pa', {}).items()}
    pressure = {tag: float(v) for tag, v in p.get('pressure_pa', {}).items()}
    loaded = sorted(set(traction) | set(pressure))
    edges = {tag: _edge_set(mesh, tag) for tag in loaded}
    for i, a in enumerate(loaded):
        for b in loaded[i + 1:]:
            if edges[a] & edges[b]:
                raise DocumentError(f'{path}: {a!r} and {b!r} share mesh edges and both carry a traction or pressure; '
                                    'give that boundary one entry')
    nodes = np.asarray(mesh.nodes, dtype=float)
    for tag in loaded:
        for a, b in edges[tag]:
            d = nodes[b] - nodes[a]
            normal = np.abs([d[1], d[0]]) > 1e-12 * np.hypot(*d)
            for c in (0, 1):
                if (a, c) in fixed and (b, c) in fixed and (
                        (tag in traction and traction[tag][c] != 0) or (tag in pressure and pressure[tag] != 0
                                                                       and normal[c])):
                    raise DocumentError(f'{path}: {"traction_pa" if tag in traction else "pressure_pa"}.{tag} loads '
                                        f'the {COMPONENTS[c]} component of an edge whose {COMPONENTS[c]} displacement '
                                        f'{fixed_by[a, c]!r} prescribes')
    loads = dict(traction)
    for tag, value in pressure.items():
        loads[tag] = (lambda points, normals, value=value: -value * normals)
    inputs = dict(young_modulus={r: float(materials[m]['young_modulus_pa']) for r, m in region_materials.items()},
                  poisson_ratio={r: float(materials[m]['poisson_ratio']) for r, m in region_materials.items()},
                  plane=p['plane'], dirichlet=fixed,
                  body_force=tuple(float(v) for v in p.get('body_force_n_m3', [0., 0.])),
                  traction=dict(sorted(loads.items())) or None)
    if p['type'] == THERMOELASTIC:
        inputs.update(reference_temperature_k=float(p['reference_temperature_k']),
                      thermal_expansion_per_k={r: float(materials[m]['thermal_expansion_per_k'])
                                               for r, m in region_materials.items()})
    return inputs


def run_region_mechanics(doc, verbose=True, *, mesh_limits=None):
    doc.validate()
    given, doc = doc, doc.copy()
    doc.validate()
    name, p = doc.sole_physics()
    kind = p['type']
    start = time.perf_counter()
    mesh, region_materials, tri = build_region_mesh(doc, mesh_limits)
    # the hand-off's notes (slivers left out, raised circle counts) reach the caller's document
    given.notes.extend(n for n in doc.notes if n.startswith(('geometry.', 'mesh.controls:')) and n not in given.notes)
    inputs = region_mechanics_inputs(doc, mesh, region_materials)
    heat_args = region_inputs(doc, mesh, region_materials) if kind == THERMOELASTIC else None
    mesh_time = time.perf_counter() - start
    areas = mesh.areas()
    regions = np.asarray(mesh.regions)
    covered = covered_shapes(doc, mesh)
    region = dict(
        triangle_regions=regions.astype(np.int64), result_format=RESULT_FORMATS[kind], field_layout=FIELD_LAYOUTS[kind],
        metadata=dict(
            region_names=list(mesh.region_names),
            regions={r: {'material': region_materials[r], 'triangles': int(np.sum(regions == i)),
                         'area_m2': float(areas[regions == i].sum())} for i, r in enumerate(mesh.region_names)},
            materials=copy.deepcopy(doc['materials']),
            displacement_m=copy.deepcopy(p['displacement_m']), traction_pa=copy.deepcopy(p.get('traction_pa', {})),
            pressure_pa=copy.deepcopy(p.get('pressure_pa', {})),
            pressure_sign='traction = -pressure * outward normal; positive pressure pushes on the body',
            mesh={'nodes': int(mesh.num_nodes), 'triangles': int(mesh.num_triangles), 'size': doc['mesh']['size'],
                  'min_angle_deg': doc['mesh']['min_angle'], 'achieved_min_angle_deg': float(tri.min_angle()),
                  'size_unit': doc.length_unit}),
        summary=region_mechanics_summary(doc),
        log=[f'mesh: {mesh.num_nodes} nodes, {mesh.num_triangles} triangles, regions {mesh.region_names}',
             *([f'shapes fully covered by later shapes (no triangles): {covered}'] if covered else [])])
    if kind == THERMOELASTIC:
        region['metadata'].update(heat_source_w_m3=copy.deepcopy(p['heat_source_w_m3']),
                                  dirichlet_temperature_k=dict(p.get('dirichlet_temperature_k', {})),
                                  outward_flux_w_m2=copy.deepcopy(p.get('outward_flux_w_m2', {})),
                                  convection=copy.deepcopy(p.get('convection', {})))
    return solve_and_package(doc, mesh, inputs, heat_args, mesh_time, verbose, region)
