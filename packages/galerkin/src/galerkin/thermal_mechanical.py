# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Explicit SI, isolated same-mesh steady heat then thermoelastic mechanics.

No persistence, unit conversion, source authentication, or thermodynamic coupling.
Import this submodule explicitly; existing component APIs remain unchanged.
"""
from collections.abc import Mapping
from dataclasses import dataclass, field
import json
import numpy as np

from .mesh import Mesh
from .core.checks import real_array, real_scalar, refuse_live
from .coupling import Field, OneWayChain, transfer
from ._thermal_mechanical_common import check_mesh_unchanged, dirichlet_supports, isolated_mesh, mesh_state
from .materials import is_per_region, region_property
from .thermal import solve_steady_heat
from .thermoelasticity import freeze_temperature, solve_thermoelasticity


class WorkflowStageError(ValueError):
    """Failure of input, heat, transfer, mechanics, or manifest; cause retained."""
    def __init__(self, stage, message):
        self.stage = stage
        super().__init__(f"steady thermoelasticity [{stage}]: {message}")


def _stage_error(stage, exc):
    return WorkflowStageError(stage, str(exc))


def _material(mesh, value, name, **bounds):
    """Validated scalar float, or a {region name: float} dict (sorted keys)."""
    if is_per_region(value):
        region_property(mesh, value, name, **bounds)
        return {str(k): float(value[k]) for k in sorted(value)}
    return real_scalar(value, name)


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
    over mesh.region_names (piecewise constant; docs/packages/galerkin/multimaterial.md).
    Heat uses Dirichlet + insulation. Mechanics uses component Dirichlet and
    zero total natural traction; body force N/m^3. See the complete EN/KO guide.
    """
    chain = OneWayChain(_stage_error)
    with chain.stage('input'):
        if not isinstance(units, Mapping) or dict(units) != {'length': 'm', 'temperature': 'K'}:
            raise ValueError("units must be exactly {'length':'m','temperature':'K'}; convert inputs explicitly")
        owned = isolated_mesh(mesh)
        state = mesh_state(owned)
        k = _material(owned, conductivity, 'conductivity', positive=True)
        e = _material(owned, young_modulus, 'young_modulus', positive=True)
        nu = _material(owned, poisson_ratio, 'poisson_ratio', lower=-1., upper=.5)
        alpha = _material(owned, thermal_expansion_per_k, 'thermal_expansion_per_k')
        tref = real_scalar(reference_temperature_k, 'reference_temperature_k')
        scalars = [v for v in (k, e) if not isinstance(v, dict)]
        if (any(v <= 0 for v in scalars) or (not isinstance(nu, dict) and not -1 < nu < .5)
                or tref < 0 or plane not in ('stress', 'strain')):
            raise ValueError('require k>0, E>0, -1<nu<.5, Tref>=0K and plane stress/strain')
        heat_bc = dirichlet_supports(thermal_dirichlet)
        mechanical_bc = dirichlet_supports(mechanical_dirichlet, vector=True)
        source = (heat_source if callable(heat_source)
                  else _material(owned, heat_source, 'heat_source'))
        body = body_force if callable(body_force) else real_array(body_force, 'body_force')
        if not callable(body) and body.shape != (2,):
            raise ValueError('constant body_force must have shape (2,)')
        # Capture configuration before external callbacks can mutate caller inputs.
        inputs = {'materials': {'conductivity_w_mk': k, 'young_modulus_pa': e,
                               'poisson_ratio': nu, 'thermal_expansion_per_k': alpha,
                               'reference_temperature_k': tref, 'plane': plane},
                  'thermal_dirichlet': [[i, v] for i, v in sorted(heat_bc.items())],
                  'mechanical_dirichlet': [[i, c, v] for (i, c), v in sorted(mechanical_bc.items())],
                  'heat_source_w_m3': _input_record(source), 'body_force_n_m3': _input_record(body)}
    with chain.stage('heat'):
        heat = solve_steady_heat(owned, conductivity=k, dirichlet=heat_bc, heat_source=source)
        # The mechanical stage computes with NumPy; a live heat input would lose its derivative.
        refuse_live(heat.temperature, "solve_steady_thermoelasticity heat inputs")
        check_mesh_unchanged(owned, state)
    with chain.stage('transfer'):
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
        check_mesh_unchanged(owned, state)
        # Same-mesh identity transfer of the nodal Kelvin field; the snapshot
        # below adds its immutable fingerprinted form for mechanics.
        nodal = transfer(Field(owned, temperature, location='node', unit='K',
                               name='heat temperature_k'), owned)
        snapshot = freeze_temperature(owned, nodal.values)
        if not np.array_equal(snapshot.temperature_k, temperature):
            raise ValueError('temperature transfer did not preserve exact nodal values')
    with chain.stage('mechanics'):
        mechanics = solve_thermoelasticity(owned, snapshot, reference_temperature_k=tref,
            thermal_expansion_per_k=alpha, young_modulus=e, poisson_ratio=nu, plane=plane,
            dirichlet=mechanical_bc, body_force=body)
        check_mesh_unchanged(owned, state)
    with chain.stage('manifest'):
        manifest = {'schema': 'galerkin-steady-thermoelasticity-v1',
            'units': {'length': 'm', 'temperature': 'K'}, 'inputs': inputs,
            'mesh': {'nodes': len(owned.nodes), 'triangles': len(owned.triangles),
                     'mesh_hash': snapshot.mesh_hash,
                     'boundary': {k: v.tolist() for k, v in state[2].items()},
                     'boundary_edges': {k: v.tolist() for k, v in state[3].items()},
                     'regions': None if state[4] is None else state[4].tolist(), 'region_names': state[5]},
            'transfer': {'policy': 'same_mesh_exact_nodal_P1_copy', 'schema_version': snapshot.schema_version,
                         'temperature_hash': snapshot.temperature_hash, 'snapshot_hash': snapshot.snapshot_hash},
            'stages': {stage: 'completed' for stage in chain.completed if stage != 'input'},
            'origin': 'workflow_owned_heat_call', 'authentication': 'not_certified',
            'callback_policy': 'caller_provided_unfingerprinted',
            'post_return_integrity': 'not_certified_mutable_component_results',
            'quantity_units': {'heat_load_reaction_residual': 'W/m', 'heat_flux': 'W/m^2',
                               'mechanical_load_reaction_residual': 'N/m', 'physical_elastic_energy': 'J/m'}}
        encoded = json.dumps(manifest, sort_keys=True, separators=(',', ':'), allow_nan=False)
    return SteadyThermoelasticResult(owned, heat, snapshot, mechanics, encoded)
