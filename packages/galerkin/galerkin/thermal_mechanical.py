# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Explicit SI, isolated same-mesh steady heat then thermoelastic mechanics.

No persistence, unit conversion, source authentication, or thermodynamic coupling.
Import this submodule explicitly; existing component APIs remain unchanged.
"""
from collections.abc import Mapping
from contextlib import contextmanager
from dataclasses import dataclass, field
import copy
import json
import numpy as np

from .mesh import Mesh
from .materials import is_per_region, region_property
from .thermal import solve_steady_heat
from .thermoelasticity import freeze_temperature, solve_thermoelasticity


class WorkflowStageError(ValueError):
    """Failure of input, heat, transfer, mechanics, or manifest; cause retained."""
    def __init__(self, stage, message):
        self.stage = stage
        super().__init__(f"steady thermoelasticity [{stage}]: {message}")


@contextmanager
def _stage(name):
    try:
        yield
    except Exception as exc:
        raise WorkflowStageError(name, str(exc)) from exc


def _real(value, name):
    a = np.asarray(value)
    if a.dtype.kind not in 'iuf' or not np.all(np.isfinite(a)):
        raise ValueError(f'{name} must contain finite real numbers')
    with np.errstate(over='ignore', invalid='ignore'):
        result = np.array(a, dtype=float, copy=True)
    if not np.all(np.isfinite(result)):
        raise ValueError(f'{name} exceeds finite numeric range')
    return result


def _scalar(value, name):
    a = _real(value, name)
    if a.shape != ():
        raise ValueError(f'{name} must be scalar')
    return float(a)


def _integer(value, name):
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, (int, np.integer)):
        raise ValueError(f'{name} must be an integer')
    return int(value)


def _supports(mapping, vector=False):
    if not isinstance(mapping, Mapping):
        raise ValueError('Dirichlet data must be a mapping')
    result = {}
    for key, value in mapping.items():
        if vector:
            if not isinstance(key, tuple) or len(key) != 2:
                raise ValueError('mechanical Dirichlet keys must be (node, component)')
            key = tuple(_integer(k, 'mechanical Dirichlet index') for k in key)
            if key[1] not in (0, 1):
                raise ValueError('mechanical component must be 0 or 1')
        else:
            key = _integer(key, 'thermal Dirichlet node')
        result[key] = _scalar(value, 'Dirichlet value')
    return result


def _isolated_mesh(mesh):
    if not isinstance(mesh, Mesh):
        raise ValueError('mesh must be a galerkin.mesh.Mesh with SI coordinates')
    p = _real(mesh.nodes, 'mesh.nodes')
    t = np.array(mesh.triangles, copy=True)
    if p.ndim != 2 or p.shape[1] != 2 or len(p) < 3:
        raise ValueError('mesh.nodes must have shape (N,2), N>=3')
    if (t.ndim != 2 or t.shape[1] != 3 or not len(t) or t.dtype.kind not in 'iu'
            or np.any(t < 0) or np.any(t >= len(p))):
        raise ValueError('mesh.triangles must be integer (M,3) valid indices before construction')
    q = p[t]
    with np.errstate(over='ignore', invalid='ignore'):
        j = q[:, 1:] - q[:, :1]
        det = j[:, 0, 0]*j[:, 1, 1]-j[:, 0, 1]*j[:, 1, 0]
    if np.any(~np.isfinite(det)) or np.any(det <= 0):
        raise ValueError('raw mesh triangles must be finite, CCW and nondegenerate; no orientation repair')
    def tags(mapping, width):
        if not isinstance(mapping, Mapping):
            raise ValueError('mesh boundary data must be mappings')
        out = {}
        for name, ids in mapping.items():
            a = np.array(ids, copy=True)
            if (not isinstance(name, str) or a.dtype.kind not in 'iu'
                    or a.ndim != (1 if width == 1 else 2)
                    or (width == 2 and a.shape[1] != 2)
                    or np.any(a < 0) or np.any(a >= len(p))):
                raise ValueError('invalid raw boundary tag/index data')
            out[name] = a.astype(np.int64, copy=True)
        return out
    boundary = tags(mesh.boundary, 1)
    edges = tags(mesh.boundary_edges, 2)
    # Geometry/connectivity were checked BEFORE Mesh can cast or flip triangles.
    regions = None if mesh.regions is None else np.array(mesh.regions, copy=True)
    if regions is not None and (regions.shape != (len(t),) or regions.dtype.kind not in 'iu'):
        raise ValueError('mesh.regions must be integer (M,) data when supplied')
    if regions is not None and np.any(regions > np.iinfo(np.int64).max):
        raise ValueError('mesh.regions exceeds integer representation')
    names = copy.deepcopy(mesh.region_names)
    if names is not None and (not isinstance(names, list) or any(not isinstance(v, str) for v in names)):
        raise ValueError('mesh.region_names must be a list of strings when supplied')
    owned = Mesh(p, t.astype(np.int64, copy=True), boundary, edges, regions, names)
    return owned


def _mesh_state(mesh):
    return (mesh.nodes.copy(), mesh.triangles.copy(),
            {k: v.copy() for k, v in mesh.boundary.items()},
            {k: v.copy() for k, v in mesh.boundary_edges.items()},
            None if mesh.regions is None else mesh.regions.copy(), copy.deepcopy(mesh.region_names))


def _check_mesh(mesh, state):
    if not (np.array_equal(mesh.nodes, state[0]) and np.array_equal(mesh.triangles, state[1])):
        raise ValueError('isolated reference mesh changed during workflow')
    if not np.array_equal(mesh.regions, state[4]) or mesh.region_names != state[5]:
        raise ValueError('isolated reference region metadata changed during workflow')
    for actual, expected in ((mesh.boundary, state[2]), (mesh.boundary_edges, state[3])):
        if set(actual) != set(expected) or any(not np.array_equal(actual[k], expected[k]) for k in expected):
            raise ValueError('isolated reference boundary data changed during workflow')


def _material(mesh, value, name, **bounds):
    """Validated scalar float, or a {region name: float} dict (sorted keys)."""
    if is_per_region(value):
        region_property(mesh, value, name, **bounds)
        return {str(k): float(value[k]) for k in sorted(value)}
    return _scalar(value, name)


def _input_record(value):
    if callable(value):
        return {'kind': 'callable', 'origin': 'caller_provided', 'fingerprinted': False}
    if isinstance(value, dict):
        return {'kind': 'per_region', 'value': dict(value)}
    return {'kind': 'constant', 'value': np.asarray(value).tolist()}


@dataclass(frozen=True)
class SteadyThermoelasticResult:
    """Aggregate at return time; component arrays/owned mesh remain mutable.

    temperature_snapshot and canonical manifest JSON are immutable copies.
    There is no post-return certification of mutable component results.
    """
    reference_mesh: Mesh
    heat: object
    temperature_snapshot: object
    mechanics: object
    manifest_json: str = field(repr=False)

    @property
    def manifest(self):
        """Return a fresh dictionary; editing it cannot change canonical JSON."""
        return json.loads(self.manifest_json)


def solve_steady_thermoelasticity(mesh, *, units, conductivity, thermal_dirichlet,
                                 heat_source=0.0, young_modulus, poisson_ratio,
                                 plane, thermal_expansion_per_k, reference_temperature_k,
                                 mechanical_dirichlet, body_force=(0., 0.)):
    """Run existing heat/freeze/mechanics APIs on one isolated SI reference mesh.

    units must equal {'length':'m','temperature':'K'}; no conversion/inference.
    Constant k W/(m K), E Pa, nu, signed alpha 1/K, nonnegative Tref K.
    k, E, nu, alpha and a constant heat_source may each be {region name: value}
    over mesh.region_names (piecewise constant; docs/multimaterial.md).
    Heat uses Dirichlet + insulation. Mechanics uses component Dirichlet and
    zero total natural traction; body force N/m^3. See the complete EN/KO guide.
    """
    with _stage('input'):
        if not isinstance(units, Mapping) or dict(units) != {'length': 'm', 'temperature': 'K'}:
            raise ValueError("units must be exactly {'length':'m','temperature':'K'}; convert inputs explicitly")
        owned = _isolated_mesh(mesh)
        state = _mesh_state(owned)
        k = _material(owned, conductivity, 'conductivity', positive=True)
        e = _material(owned, young_modulus, 'young_modulus', positive=True)
        nu = _material(owned, poisson_ratio, 'poisson_ratio', lower=-1., upper=.5)
        alpha = _material(owned, thermal_expansion_per_k, 'thermal_expansion_per_k')
        tref = _scalar(reference_temperature_k, 'reference_temperature_k')
        scalars = [v for v in (k, e) if not isinstance(v, dict)]
        if (any(v <= 0 for v in scalars) or (not isinstance(nu, dict) and not -1 < nu < .5)
                or tref < 0 or plane not in ('stress', 'strain')):
            raise ValueError('require k>0, E>0, -1<nu<.5, Tref>=0K and plane stress/strain')
        heat_bc = _supports(thermal_dirichlet)
        mechanical_bc = _supports(mechanical_dirichlet, vector=True)
        source = (heat_source if callable(heat_source)
                  else _material(owned, heat_source, 'heat_source'))
        body = body_force if callable(body_force) else _real(body_force, 'body_force')
        if not callable(body) and body.shape != (2,):
            raise ValueError('constant body_force must have shape (2,)')
        # Capture configuration before external callbacks can mutate caller inputs.
        inputs = {'materials': {'conductivity_w_mk': k, 'young_modulus_pa': e,
                               'poisson_ratio': nu, 'thermal_expansion_per_k': alpha,
                               'reference_temperature_k': tref, 'plane': plane},
                  'thermal_dirichlet': [[i, v] for i, v in sorted(heat_bc.items())],
                  'mechanical_dirichlet': [[i, c, v] for (i, c), v in sorted(mechanical_bc.items())],
                  'heat_source_w_m3': _input_record(source), 'body_force_n_m3': _input_record(body)}
    with _stage('heat'):
        heat = solve_steady_heat(owned, conductivity=k, dirichlet=heat_bc, heat_source=source)
        _check_mesh(owned, state)
    with _stage('transfer'):
        raw = np.asarray(heat.temperature)
        if raw.shape != (len(owned.nodes),):
            raise ValueError(f'heat temperature_k must have shape ({len(owned.nodes)},), got {raw.shape}')
        if raw.dtype.kind not in 'iuf':
            raise ValueError('heat temperature_k must be a real numeric nodal array')
        invalid = np.flatnonzero(~np.isfinite(raw))
        if len(invalid):
            node = int(invalid[0])
            raise ValueError(f'nonfinite temperature transfer at node {node}: {raw[node]} K')
        with np.errstate(over='ignore', invalid='ignore'):
            temperature = np.array(raw, dtype=float, copy=True)
        invalid = np.flatnonzero(~np.isfinite(temperature))
        if len(invalid):
            raise ValueError(f'temperature transfer exceeds finite numeric range at node {int(invalid[0])}')
        minimum_node = int(np.argmin(temperature))
        if temperature[minimum_node] < 0:
            raise ValueError(f'temperature transfer requires nonnegative Kelvin; minimum {temperature[minimum_node]} K at node {minimum_node}')
        _check_mesh(owned, state)
        snapshot = freeze_temperature(owned, temperature)
        if not np.array_equal(snapshot.temperature_k, temperature):
            raise ValueError('temperature transfer did not preserve exact nodal values')
    with _stage('mechanics'):
        mechanics = solve_thermoelasticity(owned, snapshot, reference_temperature_k=tref,
            thermal_expansion_per_k=alpha, young_modulus=e, poisson_ratio=nu, plane=plane,
            dirichlet=mechanical_bc, body_force=body)
        _check_mesh(owned, state)
    with _stage('manifest'):
        manifest = {'schema': 'galerkin-steady-thermoelasticity-v1',
            'units': {'length': 'm', 'temperature': 'K'}, 'inputs': inputs,
            'mesh': {'nodes': len(owned.nodes), 'triangles': len(owned.triangles),
                     'mesh_hash': snapshot.mesh_hash,
                     'boundary': {k: v.tolist() for k, v in state[2].items()},
                     'boundary_edges': {k: v.tolist() for k, v in state[3].items()},
                     'regions': None if state[4] is None else state[4].tolist(), 'region_names': state[5]},
            'transfer': {'policy': 'same_mesh_exact_nodal_P1_copy', 'schema_version': snapshot.schema_version,
                         'temperature_hash': snapshot.temperature_hash, 'snapshot_hash': snapshot.snapshot_hash},
            'stages': {'heat': 'completed', 'transfer': 'completed', 'mechanics': 'completed'},
            'origin': 'workflow_owned_heat_call', 'authentication': 'not_certified',
            'callback_policy': 'caller_provided_unfingerprinted',
            'post_return_integrity': 'not_certified_mutable_component_results',
            'quantity_units': {'heat_load_reaction_residual': 'W/m', 'heat_flux': 'W/m^2',
                               'mechanical_load_reaction_residual': 'N/m', 'physical_elastic_energy': 'J/m'}}
        encoded = json.dumps(manifest, sort_keys=True, separators=(',', ':'), allow_nan=False)
    return SteadyThermoelasticResult(owned, heat, snapshot, mechanics, encoded)
