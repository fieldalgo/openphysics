# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Headless transient heat adapter and versioned, numeric history output.

Output directories require caller-exclusive access through save and cleanup.
Observed replacements are preserved; this is not atomic protection against
external writers replacing a pathname between an ownership check and use.
"""
from dataclasses import dataclass
import copy
import json
import time

import numpy as np

from .schema import DocumentError
from .thermal import _OwnedOutput, require_fresh_output
from .transient_thermal_contract import (
    PHYSICS, RESULT_FORMAT, FIELD_LAYOUT, transient_solver_inputs,
)


_FIELD_SPEC = {
    'nodes_m': ('m', 'nodes', 'static'),
    'triangles': ('1', 'triangle_connectivity', 'static'),
    'time_s': ('s', 'requested_times', 'time_s'),
    'temperature_k': ('K', 'nodes', 'time_s'),
    'heat_flux_w_m2': ('W/m^2', 'triangle_centroids', 'time_s'),
    'source_load_w_per_m': ('W/m', 'nodes', 'time_s'),
    'reaction_w_per_m': ('W/m', 'nodes', 'time_s[1:]'),
    'residual_w_per_m': ('W/m', 'nodes', 'time_s[1:]'),
    'storage_rate_w_per_m': ('W/m', 'nodes', 'time_s[1:]'),
    'heat_content_j_per_m': ('J/m', 'domain', 'time_s'),
    'quadratic_functional_jk_per_m': ('J K/m', 'domain', 'time_s'),
    'dirichlet_node_ids': ('1', 'dirichlet_nodes', 'static'),
    'dirichlet_temperatures_k': ('K', 'dirichlet_nodes', 'time_s'),
}


@dataclass(frozen=True)
class TransientThermalRunResult:
    """Existing solver's owned read-only histories, plus a document snapshot.

    No interpolation, clamping, normalization or initial projection is applied.
    Full history memory remains O(Nt*(N+M)); save makes validation copies.
    Public metadata is mutable, so all arrays/JSON are revalidated before save.
    """
    doc: object
    solution: object
    timings: dict
    log: tuple

    def __getattr__(self, name):
        if name in _FIELD_SPEC:
            return getattr(self.solution, name)
        raise AttributeError(name)

    @property
    def mesh_nodes_m(self):
        return self.solution.nodes_m

    @property
    def mesh_triangles(self):
        return self.solution.triangles

    def _raw_arrays(self):
        # Freeze the values used by this save before writing any artifact.
        arrays = {key: np.array(getattr(self.solution, key), copy=True)
                  for key in _FIELD_SPEC}
        for key, a in arrays.items():
            if a.dtype.kind not in 'iuf' or not np.isfinite(a).all():
                raise ValueError(f'transient raw array {key}: expected finite real numeric values')
        nodes, tri, times, fixed = (arrays[k] for k in
                                   ('nodes_m', 'triangles', 'time_s', 'dirichlet_node_ids'))
        if nodes.ndim != 2 or nodes.shape[1] != 2 or len(nodes) < 3:
            raise ValueError('transient nodes_m: expected (N,2) SI coordinates')
        if tri.ndim != 2 or tri.shape[1] != 3 or not len(tri) or tri.dtype.kind not in 'iu':
            raise ValueError('transient triangles: expected integer (M,3)')
        if np.any(tri < 0) or np.any(tri >= len(nodes)):
            raise ValueError('transient triangle indices outside mesh')
        if fixed.ndim != 1 or fixed.dtype.kind not in 'iu':
            raise ValueError('transient dirichlet_node_ids: expected integer (D,)')
        if (np.any(fixed < 0) or np.any(fixed >= len(nodes))
                or (len(fixed) > 1 and np.any(fixed[1:] <= fixed[:-1]))):
            raise ValueError('transient Dirichlet indices must be valid, unique and sorted')
        with np.errstate(over='ignore', invalid='ignore'):
            steps = np.diff(times) if times.ndim == 1 else np.array([])
        if (times.ndim != 1 or len(times) < 2 or np.any(times < 0)
                or not np.isfinite(steps).all() or np.any(steps <= 0)):
            raise ValueError('transient time_s: require nonnegative strictly increasing finite times/dt')
        n, m, nt, d = len(nodes), len(tri), len(times), len(fixed)
        shapes = {'temperature_k': (nt, n), 'heat_flux_w_m2': (nt, m, 2),
                  'source_load_w_per_m': (nt, n), 'reaction_w_per_m': (nt-1, n),
                  'residual_w_per_m': (nt-1, n), 'storage_rate_w_per_m': (nt-1, n),
                  'heat_content_j_per_m': (nt,), 'quadratic_functional_jk_per_m': (nt,),
                  'dirichlet_temperatures_k': (nt, d)}
        for key, shape in shapes.items():
            if arrays[key].shape != shape:
                raise ValueError(f'transient raw array {key}: expected shape {shape}')
        with np.errstate(over='ignore', invalid='ignore'):
            v = nodes[tri][:, 1:]-nodes[tri][:, :1]
            det = v[:, 0, 0]*v[:, 1, 1]-v[:, 0, 1]*v[:, 1, 0]
        if not np.isfinite(det).all() or np.any(det <= 0):
            raise ValueError('transient triangles must be finite, nondegenerate and CCW')
        # No extra nonnegative-K rule: the linear engine explicitly allows it.
        return arrays

    def _summary(self, arrays):
        self.doc.validate()
        name, p = self.doc.sole_physics()
        if p['type'] != PHYSICS:
            raise ValueError('transient result requires a transient document')
        times = arrays['time_s']
        if not np.array_equal(times, np.asarray(self.doc['study']['time_s'])):
            raise ValueError('transient result time_s does not match document')
        for value, expected, label in (
                (self.solution.conductivity_w_mk, p['conductivity_w_mk'], 'conductivity'),
                (self.solution.volumetric_heat_capacity_j_m3k,
                 p['volumetric_heat_capacity_j_m3k'], 'volumetric_heat_capacity')):
            if not np.isfinite(value) or value <= 0 or value != expected:
                raise ValueError(f'transient result {label} does not match document')
        source = arrays['source_load_w_per_m'].sum(axis=1)
        storage = arrays['storage_rate_w_per_m'].sum(axis=1)
        reaction = arrays['reaction_w_per_m'].sum(axis=1)
        result = {
            'name': self.doc['name'], 'physics_name': name, 'physics_type': PHYSICS,
            'result_format': RESULT_FORMAT, 'field_layout': FIELD_LAYOUT,
            'units': copy.deepcopy(self.doc['units']), 'mesh_length_unit': 'm',
            'field_units': {key: spec[0] for key, spec in _FIELD_SPEC.items()},
            'field_locations': {key: spec[1] for key, spec in _FIELD_SPEC.items()},
            'field_time_axes': {key: spec[2] for key, spec in _FIELD_SPEC.items()},
            'field_shapes': {key: list(a.shape) for key, a in arrays.items()},
            'mesh': {'nodes': len(arrays['nodes_m']), 'triangles': len(arrays['triangles']),
                     'subdivisions': list(self.doc['mesh']['subdivisions'])},
            'study': {'type': 'transient', 'time_s': times.tolist()},
            'conductivity_w_mk': p['conductivity_w_mk'],
            'volumetric_heat_capacity_j_m3k': p['volumetric_heat_capacity_j_m3k'],
            'heat_source_w_m3': p['heat_source_w_m3'],
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
            'heat_content_definition': 'H=1^T M T; J/m, chosen zero at 0 K',
            'quadratic_functional_definition': 'V=0.5 T^T M T; J K/m; not stored heat',
            'raw_fields_saved': self.doc['results']['save_fields'],
            'timings_s': dict(self.timings),
        }
        json.dumps(result, allow_nan=False)
        return result

    def summary(self):
        return self._summary(self._raw_arrays())

    def save(self, outdir):
        """Fresh output only; summary last, known-owned cleanup, no crash rollback.

        Caller must exclude external writers until save/cleanup returns. Reuses
        the shared Windows/POSIX ownership implementation, including required
        file identity checks and native-handle lifetime handling.
        """
        owned = _OwnedOutput(outdir)
        try:
            owned.write('.incomplete', lambda f: f.write(b'incomplete transient heat result\n'))
            arrays = self._raw_arrays()
            summary = self._summary(arrays)
            encoded = json.dumps(summary, indent=2, allow_nan=False).encode('utf-8')
            model = json.dumps(self.doc.data, indent=2, allow_nan=False).encode('utf-8')
            log = ('\n'.join(self.log)+'\n').encode('utf-8')
            owned.write('model.json', lambda f: f.write(model))
            owned.write('log.txt', lambda f: f.write(log))
            if self.doc['results']['save_fields']:
                arrays.update(result_format=np.asarray(RESULT_FORMAT), field_layout=np.asarray(FIELD_LAYOUT),
                              mesh_length_unit=np.asarray('m'), metadata_json=np.asarray(encoded.decode('utf-8')))
                if any(a.dtype.hasobject for a in arrays.values()):
                    raise ValueError('transient raw arrays must not contain Python objects')
                owned.write('fields.npz', lambda f: np.savez_compressed(f, **arrays))
            owned.write('summary.json', lambda f: f.write(encoded))
            owned.finish()
        except BaseException:
            owned.cleanup()
            raise
        finally:
            owned.close()
        return owned.path


def run_transient_thermal(doc, verbose=True):
    """Validate a document snapshot and call the existing transient engine once."""
    from galerkin import rectangle_mesh
    from galerkin.transient_heat import solve_transient_heat
    doc.validate()
    doc = doc.copy()
    doc.validate()
    name, p = doc.sole_physics()
    if p['type'] != PHYSICS:
        raise DocumentError(f'expected {PHYSICS}')
    started = time.perf_counter()
    dom = doc.domain
    origin = np.array([doc.scale.to_si(dom[a+'min'], {'length': 1}) for a in 'xy'])
    upper = np.array([doc.scale.to_si(dom[a+'max'], {'length': 1}) for a in 'xy'])
    mesh = rectangle_mesh(*(upper-origin), *doc['mesh']['subdivisions'])
    mesh.nodes += origin
    inputs = transient_solver_inputs(doc, mesh)
    mesh_seconds = time.perf_counter()-started
    started = time.perf_counter()
    try:
        solution = solve_transient_heat(mesh, **inputs)
    except (ValueError, RuntimeError) as exc:
        raise ValueError(f'physics.{name} ({PHYSICS}): {exc}') from exc
    solve_seconds = time.perf_counter()-started
    log = (doc.summary(), f'transient heat: {len(solution.time_s)} requested times; full histories retained',
           'SI: K, flux W/m^2, nodal rates W/m depth; H J/m; quadratic V J K/m')
    result = TransientThermalRunResult(doc, solution, {'mesh': mesh_seconds, 'solve': solve_seconds}, log)
    result.summary()  # reject malformed/nonfinite results even when no save is requested
    if verbose:
        print('\n'.join(log))
    return result
