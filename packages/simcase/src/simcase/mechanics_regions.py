# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Elasticity and thermoelastic documents on named material regions.

A ``mechanics.elasticity2d`` or ``mechanics.thermoelastic2d`` document whose geometry declares
regions (flat ``background``/``shapes`` or a version 1 region component) takes
``youngs_modulus``, ``poisson_ratio`` and ``linear_expansion_coefficient`` from the shared
``materials`` table, and the thermoelastic heat stage takes ``thermal_conductivity`` from it as
region heat does. ``prescribed_displacement``, ``traction`` and ``gauge_pressure`` name the
boundaries region heat names: the domain sides, ``boundary_tags`` names, ``outer`` on a void
border and exterior boundary selections. An interface selection is refused for them: galerkin
fixes exterior nodes only and a traction needs exterior edges. The mesh, region and heat
helpers are those of thermal_regions.py (the format 0.3 hand-off, ``handoff_03``); the solve
and the result packaging are those of mechanics.py. See docs/packages/simcase/mechanics2d.md.

Format 0.3 (units batch C7): the gauge pressure is handed to galerkin as today's traction
callback ``-gauge_pressure * outward normal`` (no sign change: today's ``pressure_pa`` is the
registry's ``gauge_pressure``); the heat stage receives ``0.0 - inward_heat_flux`` (H1) and an
absent heat source as 0.0 (H8).
"""
import math
import time

import numpy as np

from . import views
from .schema import DocumentError
from .thermal_regions import (NAMES_03, SIDES, _refuse, boundary_names, build_region_mesh, component_03,
                              covered_shapes, default_boundaries_03, depth_03, exterior_sides, handoff_03,
                              has_region_geometry, mesh_controls_03, mesh_diagnostics_03, region_geometry_03,
                              region_inputs, region_materials_table_03, region_mesh_settings_03, region_source_03,
                              sides_03)
from .mechanics import (COMPONENTS, ELASTIC, THERMOELASTIC, TYPES, GAUGE_PRESSURE_SIGN, MechanicsRunResult,
                        balance_03, default_traction_free_03, displacement_components_03, entry_03, heat_text_03,
                        boundary_text_03, result_arrays, single_study_03, solve_03, solved_line, summary_03, vector_03)

RESULT_FORMATS = {ELASTIC: ELASTIC+'-regions-result-v2', THERMOELASTIC: THERMOELASTIC+'-regions-result-v2'}
FIELD_LAYOUTS = {ELASTIC: 'mechanics2d-p1-regions-v2', THERMOELASTIC: 'thermoelastic2d-p1-regions-v2'}
#: the material properties each type reads from ``materials``
MATERIAL_KEYS = {ELASTIC: ('youngs_modulus', 'poisson_ratio'),
                 THERMOELASTIC: ('youngs_modulus', 'poisson_ratio', 'linear_expansion_coefficient',
                                 'thermal_conductivity')}
#: the boundary data of a mechanics entry
LOAD_KEYS = ('prescribed_displacement', 'traction', 'gauge_pressure')


def is_region_mechanics(data):
    """A mechanics document that declares region geometry."""
    return any(has_region_geometry(data, kind) for kind in TYPES)


def _boundary_names(table, allowed, interior, where):
    """The boundary names of one mechanics key: an interface selection and an unknown name are
    refused by name."""
    for key in table:
        path = f'{where}.{key}'
        if key in interior:
            _refuse(f'{path}: selection {key!r} lies on an interface between two regions; displacement, traction '
                    'and gauge pressure apply to exterior boundaries only', path)
        if key not in allowed:
            _refuse(f'{path}: no side, boundary tag or exterior selection of that name; expected one of '
                    f'{sorted(allowed)}', path, 'E-SELECTION-UNKNOWN')


def validate_region_mechanics(doc):
    """mechanics.elasticity2d and mechanics.thermoelastic2d on regions, format 0.3."""
    name, p, path, kind = entry_03(doc)
    thermal = kind == THERMOELASTIC
    for key in MATERIAL_KEYS[THERMOELASTIC]:
        if key in p:
            _refuse(f'{path}.{key}: a region document takes {key} from materials.<m>', f'{path}.{key}')
    if component_03(doc)[1].get('dimension') == 'axisymmetric':
        _refuse(f'{kind} takes 2d components only; an axisymmetric component is a body of revolution, which this '
                'plane mechanics does not describe (steady and transient region heat take it)', 'geometry.components')
    region_mesh_settings_03(doc)
    h = handoff_03(doc)
    names = region_geometry_03(doc, h, 'mechanics')
    mesh_controls_03(doc, h)
    region_materials_table_03(doc, h, MATERIAL_KEYS[kind], kind, 'thermal, electrical and mechanical properties')
    materials = doc.si.get('materials') or {}
    for mname, spec in materials.items():
        if 'youngs_modulus' in spec and not spec['youngs_modulus'] > 0:
            _refuse('youngs_modulus: expected a positive modulus', f'materials.{mname}.youngs_modulus', 'E-DOMAIN')
    body = p.get('body_force_density')
    if body is not None:
        vector_03(body, f'{path}.body_force_density', 'body_force_density')
    tags, outside, inside = boundary_names(h)
    sides = exterior_sides(h)[1]
    allowed = set(SIDES) | tags | outside
    for key in LOAD_KEYS:
        _boundary_names(p.get(key, {}), allowed, inside, f'{path}.{key}')
    displacement = p['prescribed_displacement']
    displacement_components_03(p, path)
    held = {c for components in displacement.values() for c in components}
    if held != set(COMPONENTS):
        _refuse(f'{path}.prescribed_displacement: constraints leave a rigid-body motion free; fix x and y somewhere, '
                'and block rotation', f'{path}.prescribed_displacement')
    traction = p.get('traction', {})
    for tag, vector in traction.items():
        t = vector_03(vector, f'{path}.traction.{tag}', 'traction')
        for i, c in enumerate(COMPONENTS):
            if c in displacement.get(tag, {}) and t[i] != 0:
                _refuse(f'{path}.traction.{tag}: nonzero {c} traction on a boundary whose {c} displacement is '
                        'prescribed', f'{path}.traction.{tag}')
    for tag in p.get('gauge_pressure', {}):
        if tag in traction:
            _refuse(f'{path}.gauge_pressure.{tag}: {tag!r} also has a traction; give that boundary one entry',
                    f'{path}.gauge_pressure.{tag}')
    default_traction_free_03(doc, name, p, sides)
    if thermal:
        region_source_03(p, names, path)
        sides_03(p, name, sides, (tags, outside, inside))
        default_boundaries_03(doc, name, p, sides)
    single_study_03(doc, kind)


def region_mechanics_summary(doc):
    from .electric_regions import summary_lines_03
    name, p, where, kind = entry_03(doc)
    thermal = kind == THERMOELASTIC
    out = summary_lines_03(doc, f'{kind}, headless single static solve, named material regions, plane {p["plane"]}'
                           + (', steady heat then prescribed-temperature mechanics' if thermal else ''), ())
    body = p.get('body_force_density')
    from .thermal import _authored
    out.append(boundary_text_03(doc, where, p) + ('' if body is None else
                                                  f'; body_force_density {_authored(doc, where + ".body_force_density")}'))
    if thermal:
        out.append(heat_text_03(doc, where, p))
    out += [f'  result: {RESULT_FORMATS[kind]}; layout: {FIELD_LAYOUTS[kind]}',
            '  output: SI (displacement m, strain 1, stress Pa; nodal forces N/m of depth; triangle regions'
            + ('; temperature K, heat rates W/m of depth)' if thermal else ')')]
    return '\n'.join(out)


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
    """The solve_elasticity (or solve_thermoelasticity) keyword arguments of a meshed region document,
    from its internal SI view (``simcase.views.region_mechanics``), under galerkin's keywords.

    E, nu (and alpha) are {region name: value} from ``materials``; prescribed DOFs are sorted by
    (node, component); each traction is a global [tx, ty] in Pa and each gauge pressure p the
    callback ``-p * outward normal`` on its boundary edges; the loads are sorted by name (H6).
    """
    name, _ = doc.sole_physics()
    path = f'physics.{name}'
    m = views.region_mechanics(doc)
    for label, table, given in (('prescribed_displacement', mesh.boundary, m.displacement),
                                ('traction', mesh.boundary_edges, m.traction),
                                ('gauge_pressure', mesh.boundary_edges, m.pressure)):
        for tag in given:
            if tag not in table:
                raise DocumentError(f'{path}.{label}.{tag}: no mesh edge lies on {tag!r} (a side or boundary that '
                                    'borders a void feature only, or a selection without mesh edges)')
    fixed, fixed_by = {}, {}
    for tag, components in m.displacement.items():
        for component, value in components.items():
            for node in mesh.boundary[tag]:
                key = (int(node), COMPONENTS.index(component))
                if key in fixed and fixed[key] != float(value):
                    raise DocumentError(f'{path}.prescribed_displacement: {fixed_by[key]!r} and {tag!r} share node '
                                        f'{key[0]} with different {component} displacements')
                fixed[key], fixed_by[key] = float(value), tag
    fixed = dict(sorted(fixed.items()))
    free = rigid_free_regions(mesh, fixed)
    if free:
        raise DocumentError(f'{path}.prescribed_displacement: constraints leave a rigid-body motion free in the part '
                            f'of the body made of regions {free[0]}; each connected part needs x and y fixed and '
                            'rotation blocked')
    traction = {tag: [float(v) for v in vector] for tag, vector in m.traction.items()}
    pressure = {tag: float(v) for tag, v in m.pressure.items()}
    loaded = sorted(set(traction) | set(pressure))
    edges = {tag: _edge_set(mesh, tag) for tag in loaded}
    for i, a in enumerate(loaded):
        for b in loaded[i + 1:]:
            if edges[a] & edges[b]:
                raise DocumentError(f'{path}: {a!r} and {b!r} share mesh edges and both carry a traction or gauge '
                                    'pressure; give that boundary one entry')
    nodes = np.asarray(mesh.nodes, dtype=float)
    for tag in loaded:
        for a, b in edges[tag]:
            d = nodes[b] - nodes[a]
            normal = np.abs([d[1], d[0]]) > 1e-12 * np.hypot(*d)
            for c in (0, 1):
                if (a, c) in fixed and (b, c) in fixed and (
                        (tag in traction and traction[tag][c] != 0) or (tag in pressure and pressure[tag] != 0
                                                                       and normal[c])):
                    raise DocumentError(f'{path}: {"traction" if tag in traction else "gauge_pressure"}.{tag} loads '
                                        f'the {COMPONENTS[c]} component of an edge whose {COMPONENTS[c]} displacement '
                                        f'{fixed_by[a, c]!r} prescribes')
    loads = dict(traction)
    for tag, value in pressure.items():
        loads[tag] = (lambda points, normals, value=value: -value * normals)
    inputs = dict(young_modulus={r: float(m.young_modulus[k]) for r, k in region_materials.items()},
                  poisson_ratio={r: float(m.poisson_ratio[k]) for r, k in region_materials.items()},
                  plane=m.plane, dirichlet=fixed,
                  body_force=tuple(float(v) for v in m.body_force),
                  traction=dict(sorted(loads.items())) or None)
    if m.thermoelastic:
        inputs.update(reference_temperature_k=float(m.reference_temperature),
                      thermal_expansion_per_k={r: float(m.thermal_expansion[k]) for r, k in region_materials.items()})
    return inputs


def regions_block_03(doc, mesh, region_materials, p, kind):
    """The region-only summary keys of section 5.3.3: regions, the materials and the loads as SI value
    objects, the gauge pressure sign and, for thermoelastic documents, the heat-stage echoes."""
    from .results_common import tagged_array, value_object as vo
    areas = mesh.areas()
    regions = np.asarray(mesh.regions)
    materials = doc.si['materials']
    out = {'region_names': list(mesh.region_names),
           'regions': {r: {'material': region_materials[r], 'triangles': int(np.sum(regions == i)),
                           'area': vo(float(areas[regions == i].sum()), 'area')}
                       for i, r in enumerate(mesh.region_names)},
           'materials': {m: {key: vo(v, key) if isinstance(v, (int, float)) and not isinstance(v, bool) else v
                             for key, v in spec.items()} for m, spec in materials.items()},
           'prescribed_displacement': {tag: {c: vo(v, 'prescribed_displacement') for c, v in components.items()}
                                       for tag, components in p['prescribed_displacement'].items()},
           'traction': {tag: tagged_array(v, 'traction') for tag, v in p.get('traction', {}).items()},
           'gauge_pressure': {tag: vo(v, 'gauge_pressure') for tag, v in p.get('gauge_pressure', {}).items()},
           'gauge_pressure_sign': GAUGE_PRESSURE_SIGN}
    if kind == THERMOELASTIC:
        source = p.get('heat_source_density')
        if isinstance(source, dict):
            out['heat_source_density'] = {r: vo(v, 'heat_source_density') for r, v in source.items()}
        elif source is not None:
            out['heat_source_density'] = vo(source, 'heat_source_density')
        out['prescribed_temperature'] = {tag: vo(v, 'prescribed_temperature')
                                         for tag, v in p.get('prescribed_temperature', {}).items()}
        out['inward_heat_flux'] = {tag: vo(v, 'inward_heat_flux') for tag, v in p.get('inward_heat_flux', {}).items()}
        out['convection'] = {tag: {'heat_transfer_coefficient': vo(c['heat_transfer_coefficient'],
                                                                   'heat_transfer_coefficient'),
                                   'ambient_temperature': vo(c['ambient_temperature'], 'ambient_temperature')}
                             for tag, c in p.get('convection', {}).items()}
    return out


def run_region_mechanics(doc, verbose=True, *, mesh_limits=None):
    doc.validate()
    given, doc = doc, doc.copy()
    doc.validate()
    name, p, path, kind = entry_03(doc)
    thermal = kind == THERMOELASTIC
    start = time.perf_counter()
    h = handoff_03(doc)
    mesh, region_materials, tri = build_region_mesh(h, mesh_limits)
    # the mesher's findings reach the caller's document as coded diagnostics
    for target in (given, doc):
        mesh_diagnostics_03(target, component_03(doc)[0], h.notes)
    inputs = region_mechanics_inputs(doc, mesh, region_materials)
    heat_args = region_inputs(doc, mesh, region_materials, views.region_heat_03(doc), NAMES_03) if thermal else None
    mesh_time = time.perf_counter() - start
    start = time.perf_counter()
    solved, heat, snapshot = solve_03(mesh, inputs, heat_args, thermal, label=f'{path} ({kind})')
    solve_time = time.perf_counter() - start
    fixed = inputs['dirichlet']
    heat_fixed = None if heat_args is None else heat_args['dirichlet']
    arrays = result_arrays(mesh, solved, fixed, thermal=thermal, regions=np.asarray(mesh.regions).astype(np.int64),
                           heat=heat, heat_fixed=heat_fixed)
    balance = balance_03(arrays, solved, mesh, thermal=thermal, heat=heat, heat_fixed=heat_fixed)
    metadata = summary_03(doc, result_format=RESULT_FORMATS[kind], field_layout=FIELD_LAYOUTS[kind], arrays=arrays,
                          balance=balance, timings={'mesh': mesh_time, 'solve': solve_time}, mesh=mesh,
                          depth=depth_03(doc), snapshot=snapshot,
                          extra=regions_block_03(doc, mesh, region_materials, p, kind),
                          minimum_angle=math.radians(float(tri.min_angle())))
    covered = covered_shapes(h, mesh)
    printed = [doc.summary(), f'mesh: {mesh.num_nodes} nodes, {mesh.num_triangles} triangles, regions '
                              f'{mesh.region_names}',
               *([f'shapes fully covered by later shapes (no triangles): {covered}'] if covered else []),
               solved_line(mesh, balance, thermal)]
    if verbose:
        print('\n'.join(printed))
    from .thermal import log_lines_03
    result = MechanicsRunResult(doc, arrays, metadata, log_lines_03(doc, printed))
    result.region_materials = region_materials
    return result
