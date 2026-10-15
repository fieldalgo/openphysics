# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Headless, single homogeneous rectangle heat documents and numeric SI results."""
from dataclasses import dataclass
import copy
import json
import math
import os
from pathlib import Path
import stat
import sys
import time

import numpy as np

from .schema import DocumentError

PHYSICS = 'thermal.steady2d'
RESULT_FORMAT = 'thermal.steady2d-result-v1'
FIELD_LAYOUT = 'thermal2d-p1-node-cell-v1'


def is_thermal(data):
    return isinstance(data, dict) and isinstance(data.get('physics'), dict) and any(
        isinstance(p, dict) and p.get('type') == PHYSICS for p in data['physics'].values())


def defaults():
    return {'openphysics': '0.2', 'name': 'untitled', 'geometry': {'domain': None},
            'materials': {}, 'physics': {}, 'mesh': {}, 'study': {'type': 'single'},
            'results': {'save_fields': True, 'plots': False}}


def _object(value, keys, path):
    if not isinstance(value, dict):
        raise DocumentError(f'{path}: expected an object')
    unknown = set(value)-set(keys)
    if unknown:
        raise DocumentError(f'{path}: unsupported thermal keys {sorted(map(str, unknown))}')


def _number(value, path, positive=False, nonnegative=False, integer=False):
    try:
        valid = isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)
    except OverflowError:
        valid = False
    if not valid or (positive and value <= 0) or (nonnegative and value < 0) or (integer and not isinstance(value, int)):
        raise DocumentError(f'{path}: expected a finite ' + ('positive integer' if integer else
                            'positive number' if positive else 'nonnegative number' if nonnegative else 'number'))


def validate_thermal(doc):
    d = doc.data
    _object(d, {'openphysics', 'name', 'units', 'geometry', 'materials', 'physics', 'mesh', 'study', 'results'}, 'document')
    if not isinstance(d['name'], str):
        raise DocumentError('name: expected a string')
    name, p = doc.sole_physics()
    if not isinstance(name, str) or not name.isidentifier():
        raise DocumentError('physics name must be an identifier')
    _object(p, {'type', 'conductivity_w_mk', 'heat_source_w_m3', 'dirichlet_temperature_k'}, f'physics.{name}')
    _object(d.get('units'), {'length', 'temperature'}, 'units')
    if 'length' not in doc.scale.declared or d['units'].get('temperature') != 'K':
        raise DocumentError('thermal.steady2d requires explicit units.length and units.temperature="K"')
    _number(p.get('conductivity_w_mk'), f'physics.{name}.conductivity_w_mk', positive=True)
    p.setdefault('heat_source_w_m3', 0.0)
    _number(p['heat_source_w_m3'], f'physics.{name}.heat_source_w_m3')
    temperatures = p.get('dirichlet_temperature_k')
    _object(temperatures, {'left', 'right', 'bottom', 'top'}, f'physics.{name}.dirichlet_temperature_k')
    if not temperatures:
        raise DocumentError(f'physics.{name}.dirichlet_temperature_k: at least one exterior tag is required')
    for tag, value in temperatures.items():
        _number(value, f'physics.{name}.dirichlet_temperature_k.{tag}', nonnegative=True)
    # Opposite sides are disjoint; adjacent sides share an exterior corner.
    for horizontal in ('left', 'right'):
        for vertical in ('bottom', 'top'):
            if horizontal in temperatures and vertical in temperatures and temperatures[horizontal] != temperatures[vertical]:
                raise DocumentError(f'physics.{name}.dirichlet_temperature_k: conflicting corner temperatures on {horizontal}/{vertical}')
    _object(d['geometry'], {'domain'}, 'geometry')
    dom = d['geometry'].get('domain')
    _object(dom, {'xmin', 'xmax', 'ymin', 'ymax'}, 'geometry.domain')
    if set(dom) != {'xmin', 'xmax', 'ymin', 'ymax'}:
        raise DocumentError('geometry.domain needs xmin, xmax, ymin, ymax')
    for key, value in dom.items():
        _number(value, f'geometry.domain.{key}')
        _number(doc.scale.to_si(value, {'length': 1}), f'geometry.domain.{key} in metres')
    for axis in 'xy':
        _number(dom[axis+'max']-dom[axis+'min'], f'geometry.domain.{axis} extent', positive=True)
        _number(doc.scale.to_si(dom[axis+'max'], {'length': 1})-
                doc.scale.to_si(dom[axis+'min'], {'length': 1}), f'geometry.domain.{axis} SI extent', positive=True)
    if d['materials'] != {}:
        raise DocumentError('materials: thermal.steady2d requires an empty object; k is homogeneous')
    _object(d['mesh'], {'subdivisions'}, 'mesh')
    subdivisions = d['mesh'].get('subdivisions')
    if not isinstance(subdivisions, (list, tuple)) or len(subdivisions) != 2:
        raise DocumentError('mesh.subdivisions: expected [nx, ny]')
    for i, v in enumerate(subdivisions):
        _number(v, f'mesh.subdivisions[{i}]', positive=True, integer=True)
    if d['study'] != {'type': 'single'}:
        raise DocumentError('thermal.steady2d supports only study {"type":"single"}')
    _object(d['results'], {'save_fields', 'plots'}, 'results')
    if not isinstance(d['results'].get('save_fields'), bool) or not isinstance(d['results'].get('plots'), bool):
        raise DocumentError('results.save_fields and results.plots must be booleans')
    if d['results']['plots']:
        raise DocumentError('results.plots: thermal.steady2d is headless; plots=true is not supported')
    doc.notes = []


def thermal_summary(doc):
    name, p = doc.sole_physics()
    return (f'{doc["name"]} (openphysics 0.2)\n'
            f'  physics {name}: {PHYSICS}, single steady heat\n'
            f'  domain {doc.domain} {doc.length_unit}; mesh {doc["mesh"]["subdivisions"]}\n'
            f'  k={p["conductivity_w_mk"]} W/(m K), Q={p["heat_source_w_m3"]} W/m^3\n'
            f'  Dirichlet {p["dirichlet_temperature_k"]} K; remaining exterior insulated\n'
            '  output: coordinates m, temperature K, flux W/m^2, nodal heat W/m of depth')


def require_fresh_output(path):
    if os.path.lexists(path):
        raise FileExistsError(f'thermal output already exists: {path}; choose a fresh output directory')


def _identity(path):
    s = path.lstat()
    return s.st_dev, s.st_ino


def _windows_handle(path, *, create=False):
    """Win32 sharing contract via stdlib only; callers own the returned handle.

    CREATE_NEW is exclusive; FILE_SHARE_DELETE allows rename/unlink while pinned.
    Directory/query handles require BACKUP_SEMANTICS. OPEN_REPARSE_POINT avoids
    following a substituted junction/symlink. No third-party implementation used.
    """
    import ctypes
    from ctypes import wintypes
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    open_handle = kernel.CreateFileW
    open_handle.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                            wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    open_handle.restype = wintypes.HANDLE
    close_handle = kernel.CloseHandle
    close_handle.argtypes = [wintypes.HANDLE]
    close_handle.restype = wintypes.BOOL
    handle = open_handle(str(Path(path).absolute()), 0x40000000 if create else 0,
                         0x00000007, None, 1 if create else 3,
                         0x00000080 if create else 0x02200000, None)
    if handle == ctypes.c_void_p(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    def close():
        if not close_handle(handle):
            raise ctypes.WinError(ctypes.get_last_error())
    return handle, close


def _pin_directory(path):
    if os.name == 'nt':
        _, close = _windows_handle(path)
        return close
    fd = os.open(path, os.O_RDONLY | getattr(os, 'O_DIRECTORY', 0))
    return lambda: os.close(fd)


def _exclusive_stream(path):
    if os.name != 'nt':
        return Path(path).open('xb')
    import msvcrt
    handle, close = _windows_handle(path, create=True)
    try:
        fd = msvcrt.open_osfhandle(handle, os.O_WRONLY | os.O_BINARY)
    except BaseException:
        close()
        raise
    # open_osfhandle transfers native-handle ownership to the CRT descriptor.
    try:
        return os.fdopen(fd, 'wb')
    except BaseException:
        os.close(fd)
        raise


class _OwnedOutput:
    """Exclusive directory ownership; no recursive deletion or rename transaction."""
    def __init__(self, path):
        self.path = Path(path)
        require_fresh_output(self.path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.mkdir()  # the losing concurrent writer never enters cleanup
        self.identity = _identity(self.path)
        self.files = {}
        self.file_closers = {}
        self.handles = []
        # Pin the directory inode, including while its pathname is replaced.
        try:
            self.handles.append(_pin_directory(self.path))
            if not self.unchanged():
                raise OSError('thermal output target changed during ownership acquisition')
        except BaseException:
            # Constructor runs before save's try: clean only this same empty target.
            try:
                if self.unchanged():
                    self.path.rmdir()
            except OSError:
                pass
            self.close()
            raise

    def close(self):
        error = None
        for close in self.handles:
            try:
                close()
            except OSError as exc:
                error = error or exc
        self.handles.clear()
        if error is not None and sys.exc_info()[0] is None:
            raise error  # a close failure must not mask a primary save/pin failure

    def unchanged(self):
        try:
            return stat.S_ISDIR(self.path.lstat().st_mode) and _identity(self.path) == self.identity
        except OSError:
            return False

    def write(self, name, writer):
        if not self.unchanged():
            raise OSError('thermal output target was replaced; refusing to write')
        with _exclusive_stream(self.path/name) as stream:
            # Keep the inode alive: unlink/recreate must never acquire our identity.
            fd = os.dup(stream.fileno())
            retained = [fd]
            def close_file():
                if retained:
                    os.close(retained.pop())
            self.file_closers[name] = close_file
            self.handles.append(close_file)
            self.files[name] = (os.fstat(stream.fileno()).st_dev, os.fstat(stream.fileno()).st_ino)
            writer(stream)

    def owns(self, name):
        try:
            p = self.path/name
            return self.unchanged() and not p.is_symlink() and _identity(p) == self.files.get(name)
        except OSError:
            return False

    def finish(self):
        if (not self.unchanged() or any(not self.owns(name) for name in self.files)
                or any(not self.owns(p.name) for p in self.path.iterdir())):
            raise OSError('thermal output contains unexpected or replaced files; leaving it incomplete')
        if not self.owns('.incomplete'):
            raise OSError('thermal incomplete marker was replaced')
        (self.path/'.incomplete').unlink()
        self.file_closers['.incomplete']()

    def cleanup(self):
        try:
            self._cleanup()
        except OSError:
            pass  # keep the incomplete output; do not mask the original failure

    def _cleanup(self):
        if not self.unchanged():
            return  # never touch a replaced target, even if it has familiar names
        # Windows delete-pending files disappear only after their pins close.
        # Releasing our detached old file never deletes a replacement pathname.
        for name, close in self.file_closers.items():
            if not self.owns(name):
                close()
        safe = all(self.owns(p.name) for p in self.path.iterdir())
        for name in self.files:
            if name != '.incomplete' and self.owns(name):
                try:
                    (self.path/name).unlink()
                    self.file_closers[name]()
                except OSError:
                    safe = False
        if safe:
            try:
                if self.owns('.incomplete'):
                    (self.path/'.incomplete').unlink()
                    self.file_closers['.incomplete']()
                if self.unchanged():
                    self.path.rmdir()  # only succeeds when empty
                    return
            except OSError:
                pass
        if self.unchanged() and not (self.path/'.incomplete').exists():
            try:
                self.write('.incomplete', lambda f: f.write(b'incomplete thermal output; cleanup could not finish\n'))
            except OSError:
                pass


@dataclass
class ThermalRunResult:
    doc: object
    mesh: object
    solution: object
    dirichlet_node_ids: np.ndarray
    dirichlet_temperature_k: np.ndarray
    diagnostics: dict
    timings: dict
    log: list

    @property
    def mesh_nodes_m(self): return self.mesh.nodes

    @property
    def mesh_triangles(self): return self.mesh.triangles

    @property
    def temperature_k(self): return self.solution.temperature

    @property
    def heat_flux_w_m2(self): return self.solution.heat_flux

    @property
    def load_w_per_m(self): return self.solution.load

    @property
    def reaction_w_per_m(self): return self.solution.reaction

    @property
    def residual_w_per_m(self): return self.solution.residual

    def _raw_arrays(self):
        arrays = dict(nodes_m=np.asarray(self.mesh.nodes), triangles=np.asarray(self.mesh.triangles),
                      temperature_k=np.asarray(self.temperature_k), heat_flux_w_m2=np.asarray(self.heat_flux_w_m2),
                      load_w_per_m=np.asarray(self.load_w_per_m), reaction_w_per_m=np.asarray(self.reaction_w_per_m),
                      residual_w_per_m=np.asarray(self.residual_w_per_m), dirichlet_node_ids=np.asarray(self.dirichlet_node_ids),
                      dirichlet_temperature_k=np.asarray(self.dirichlet_temperature_k))
        for key, a in arrays.items():
            if a.dtype.kind not in 'iuf' or not np.isfinite(a).all():
                raise ValueError(f'thermal raw array {key}: expected finite real numeric values')
        nodes, tris, fixed = arrays['nodes_m'], arrays['triangles'], arrays['dirichlet_node_ids']
        if nodes.ndim != 2 or nodes.shape[1] != 2 or len(nodes) < 3:
            raise ValueError('thermal nodes_m: expected nonempty (N,2) coordinates')
        if tris.ndim != 2 or tris.shape[1] != 3 or not len(tris) or tris.dtype.kind not in 'iu':
            raise ValueError('thermal triangles: expected integer (M,3) connectivity')
        if fixed.ndim != 1 or not len(fixed) or fixed.dtype.kind not in 'iu':
            raise ValueError('thermal dirichlet_node_ids: expected integer (D,) indices')
        if np.any(tris < 0) or np.any(tris >= len(nodes)) or np.any(fixed < 0) or np.any(fixed >= len(nodes)):
            raise ValueError('thermal raw connectivity/Dirichlet indices outside mesh')
        if np.any(np.diff(fixed.astype(np.int64)) <= 0):
            raise ValueError('thermal dirichlet_node_ids must be unique and sorted')
        shapes = {'temperature_k': (len(nodes),), 'heat_flux_w_m2': (len(tris), 2),
                  'load_w_per_m': (len(nodes),), 'reaction_w_per_m': (len(nodes),),
                  'residual_w_per_m': (len(nodes),), 'dirichlet_temperature_k': (len(fixed),)}
        for key, shape in shapes.items():
            if arrays[key].shape != shape:
                raise ValueError(f'thermal raw array {key}: expected shape {shape}')
        v = nodes[tris][:, 1:]-nodes[tris][:, :1]
        det = v[:, 0, 0]*v[:, 1, 1]-v[:, 0, 1]*v[:, 1, 0]
        if not np.isfinite(det).all() or np.any(det <= 0):
            raise ValueError('thermal triangles must be finite, nondegenerate and CCW')
        if np.any(arrays['dirichlet_temperature_k'] < 0):
            raise ValueError('thermal prescribed temperature must be nonnegative kelvin')
        return arrays

    def summary(self):
        arrays = self._raw_arrays()
        name, p = self.doc.sole_physics()
        result = {'name': self.doc['name'], 'physics_name': name, 'physics_type': PHYSICS,
                'result_format': RESULT_FORMAT, 'field_layout': FIELD_LAYOUT,
                'units': copy.deepcopy(self.doc['units']), 'mesh_length_unit': 'm',
                'field_units': {'nodes_m': 'm', 'triangles': '1', 'dirichlet_node_ids': '1',
                                'dirichlet_temperature_k': 'K', 'temperature_k': 'K', 'heat_flux_w_m2': 'W/m^2',
                                'load_w_per_m': 'W/m', 'reaction_w_per_m': 'W/m', 'residual_w_per_m': 'W/m'},
                'field_locations': {'nodes_m': 'nodes', 'triangles': 'triangle_connectivity',
                                    'dirichlet_node_ids': 'dirichlet_nodes', 'dirichlet_temperature_k': 'dirichlet_nodes',
                                    'temperature_k': 'nodes', 'heat_flux_w_m2': 'triangle_centroids',
                                    'load_w_per_m': 'nodes', 'reaction_w_per_m': 'nodes', 'residual_w_per_m': 'nodes'},
                'field_shapes': {key: list(a.shape) for key, a in arrays.items()},
                'reaction_sign': 'inward; outward heat = -sum(reaction on unique Dirichlet nodes)',
                'mesh': {'nodes': len(self.mesh.nodes), 'triangles': len(self.mesh.triangles),
                         'subdivisions': list(self.doc['mesh']['subdivisions'])},
                'study': {'type': 'single'}, 'conductivity_w_mk': p['conductivity_w_mk'],
                'heat_source_w_m3': p['heat_source_w_m3'],
                'dirichlet_temperature_k': dict(p['dirichlet_temperature_k']),
                'dirichlet_nodes': len(self.dirichlet_node_ids),
                'temperature_min_k': float(self.temperature_k.min()),
                'temperature_max_k': float(self.temperature_k.max()),
                **self.diagnostics, 'timings_s': dict(self.timings)}
        json.dumps(result, allow_nan=False)
        return result

    def save(self, outdir):
        owned = _OwnedOutput(outdir)
        try:
            owned.write('.incomplete', lambda f: f.write(b'incomplete thermal result\n'))
            summary = self.summary()
            encoded = json.dumps(summary, indent=2, allow_nan=False).encode()
            owned.write('model.json', lambda f: f.write(json.dumps(self.doc.data, indent=2, allow_nan=False).encode()))
            owned.write('log.txt', lambda f: f.write(('\n'.join(self.log)+'\n').encode()))
            if self.doc['results']['save_fields']:
                arrays = dict(self._raw_arrays(), result_format=RESULT_FORMAT, field_layout=FIELD_LAYOUT,
                              mesh_length_unit='m', metadata_json=encoded.decode())
                if any(np.asarray(v).dtype.hasobject for v in arrays.values()):
                    raise ValueError('thermal raw arrays must not contain Python objects')
                for key, value in arrays.items():
                    a = np.asarray(value)
                    if a.dtype.kind in 'iuf' and not np.isfinite(a).all():
                        raise ValueError(f'thermal raw array {key} must be finite')
                owned.write('fields.npz', lambda f: np.savez_compressed(f, **arrays))
            owned.write('summary.json', lambda f: f.write(encoded))
            owned.finish()
        except (OSError, ValueError, RuntimeError):
            owned.cleanup()
            raise
        finally:
            owned.close()
        return owned.path


def run_thermal(doc, verbose=True):
    from galerkin import rectangle_mesh, assemble_stiffness
    try:
        from galerkin.thermal import solve_steady_heat
    except ImportError as exc:
        raise RuntimeError('thermal.steady2d requires a matching galerkin.thermal build') from exc
    doc.validate()
    doc = doc.copy()  # retain an independent validated document snapshot
    doc.validate()
    name, p = doc.sole_physics()
    dom = doc.domain
    origin = np.array([doc.scale.to_si(dom[a+'min'], {'length': 1}) for a in 'xy'])
    lengths = [doc.scale.to_si(dom[a+'max']-dom[a+'min'], {'length': 1}) for a in 'xy']
    t0 = time.perf_counter()
    mesh = rectangle_mesh(*lengths, *map(int, doc['mesh']['subdivisions']))
    mesh.nodes += origin
    prescribed = {}
    for tag, value in p['dirichlet_temperature_k'].items():
        nodes = mesh.boundary.get(tag)
        if nodes is None or not len(nodes):
            raise DocumentError(f'physics.{name}.dirichlet_temperature_k.{tag}: empty or unknown exterior tag')
        for node in nodes:
            if int(node) in prescribed and prescribed[int(node)] != value:
                raise DocumentError(f'physics.{name}: conflicting corner temperature at node {node}')
            prescribed[int(node)] = value
    fixed = np.array(sorted(prescribed), dtype=int)
    prescribed = {int(i): prescribed[int(i)] for i in fixed}
    t_mesh = time.perf_counter()-t0
    t0 = time.perf_counter()
    try:
        solution = solve_steady_heat(mesh, conductivity=p['conductivity_w_mk'], dirichlet=prescribed,
                                     heat_source=p['heat_source_w_m3'])
    except (ValueError, RuntimeError) as exc:
        raise ValueError(f'physics.{name} ({PHYSICS}): {exc}') from exc
    t_solve = time.perf_counter()-t0
    stiffness = assemble_stiffness(mesh, p['conductivity_w_mk'])
    increment = solution.temperature-prescribed[int(fixed[0])]
    scale = max(float(np.max(abs(stiffness)@abs(increment)+abs(solution.load))), np.finfo(float).tiny)
    free = np.setdiff1d(np.arange(mesh.num_nodes), fixed)
    source_heat = float(solution.load.sum())
    outward = -float(solution.reaction[fixed].sum())
    balance_scale = max(float(np.sum(abs(solution.load))+np.sum(abs(solution.reaction))), np.finfo(float).tiny)
    diagnostics = {'source_heat_w_per_m': source_heat, 'outward_heat_w_per_m': outward,
                   'heat_balance_defect_w_per_m': outward-source_heat,
                   'normalized_heat_balance_defect': abs(outward-source_heat)/balance_scale,
                   'normalized_free_residual': float(np.max(abs(solution.residual[free]))/scale) if len(free) else 0.}
    log = [doc.summary(), f'temperature K: {solution.temperature.min():.12g} to {solution.temperature.max():.12g}',
           f'source {source_heat:.12g} W/m; signed outward {outward:.12g} W/m of depth']
    if verbose:
        print('\n'.join(log))
    return ThermalRunResult(doc, mesh, solution, fixed, np.array(list(prescribed.values())), diagnostics,
                            {'mesh': t_mesh, 'solve': t_solve}, log)
