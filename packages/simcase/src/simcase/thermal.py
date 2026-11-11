# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Headless, single homogeneous rectangle heat documents and numeric SI results."""
from dataclasses import dataclass
import math
import os
from pathlib import Path
import stat
import sys
import tempfile
import time

import numpy as np

from . import results_common, views
from .schema import DocumentError
from .registry import PhysicsKind, register

PHYSICS = 'thermal.steady2d'

# Format 0.3 rectangle results: the saved arrays under registry names (bytes unchanged), and
# the summary's balance values. Region results use the same names (thermal_regions.NAMES_03).
ARRAY_NAMES_03 = {
    'nodes_m': 'node_coordinates', 'triangles': 'triangles', 'temperature_k': 'temperature',
    'heat_flux_w_m2': 'heat_flux', 'load_w_per_m': 'generated_heat_rate_per_depth',
    'reaction_w_per_m': 'reaction_heat_rate_per_depth', 'residual_w_per_m': 'residual_heat_rate_per_depth',
    'dirichlet_node_ids': 'prescribed_node_ids', 'dirichlet_temperature_k': 'prescribed_temperature',
    'prescribed_outward_load_w_per_m': 'outward_prescribed_heat_rate_per_depth',
    'ambient_load_w_per_m': 'ambient_convective_heat_rate_per_depth',
    'convective_outward_w_per_m': 'outward_convective_heat_rate_per_depth',
    'system_rhs_w_per_m': 'applied_heat_rate_per_depth'}
#: array name -> (registry quantity or None for a structural array, location, components)
FIELDS_03 = {
    'node_coordinates': ('node_coordinates', 'nodes', ['x', 'y']),
    'triangles': (None, 'triangle_connectivity', None),
    'temperature': ('temperature', 'nodes', None),
    'heat_flux': ('heat_flux', 'triangle_centroids', ['x', 'y']),
    'generated_heat_rate_per_depth': ('generated_heat_rate_per_depth', 'nodes', None),
    'reaction_heat_rate_per_depth': ('reaction_heat_rate_per_depth', 'nodes', None),
    'residual_heat_rate_per_depth': ('residual_heat_rate_per_depth', 'nodes', None),
    'prescribed_node_ids': (None, 'prescribed_nodes', None),
    'prescribed_temperature': ('prescribed_temperature', 'prescribed_nodes', None),
    'outward_prescribed_heat_rate_per_depth': ('outward_prescribed_heat_rate_per_depth', 'nodes', None),
    'ambient_convective_heat_rate_per_depth': ('ambient_convective_heat_rate_per_depth', 'nodes', None),
    'outward_convective_heat_rate_per_depth': ('outward_convective_heat_rate_per_depth', 'nodes', None),
    'applied_heat_rate_per_depth': ('applied_heat_rate_per_depth', 'nodes', None)}
BALANCE_03 = {
    'source_heat_w_per_m': 'generated_heat_rate_per_depth', 'outward_heat_w_per_m': 'outward_heat_rate_per_depth',
    'heat_balance_defect_w_per_m': 'heat_rate_imbalance_per_depth',
    'normalized_heat_balance_defect': 'relative_conservation_residual', 'normalized_free_residual': 'relative_residual',
    'prescribed_outward_heat_w_per_m': 'outward_prescribed_heat_rate_per_depth',
    'convective_outward_heat_w_per_m': 'outward_convective_heat_rate_per_depth',
    'thermostat_outward_heat_w_per_m': 'outward_reaction_heat_rate_per_depth',
    'free_residual_max_w_per_m': 'maximum_residual_heat_rate_per_depth'}
from .steady_boundary_contract import LOAD_DEFINITION_03, OUTWARD_SIGN_03, REACTION_SIGN_03  # noqa: E402
_FORMAT_02 = ('format 0.2 rectangle heat documents are not read: units now travel with each value ("300 K", '
              '"12.5 W/(m K)") and the geometry declares its length_unit. Write "openphysics": "0.3" '
              '(docs/packages/simcase/thermal_steady2d.md)')


def refuse_format_02(doc, label):
    """A 0.2 rectangle heat document (flat, or a homogeneous version 1 one): refused by name."""
    raise DocumentError(_FORMAT_02.replace('thermal_steady2d', label), path='openphysics', code='E-FORMAT')


def strict_value(value, quantity_name):
    """A value object whose non-finite value is refused when the summary is written (heat
    summaries keep refusing non-finite numbers, as before the units batch)."""
    from physmat.units import quantity
    return {'value': float(value), 'unit': quantity(quantity_name).unit}


def strict_series(values, quantity_name):
    from physmat.units import quantity
    return {'unit': quantity(quantity_name).unit, 'values': [float(v) for v in values]}


def strict_timing(timings):
    """``timing.wall_time`` of a heat summary; a non-finite wall time is refused like any value."""
    return {'wall_time': {key: strict_value(timings[key], 'wall_time') for key in ('mesh', 'solve')}}


class _Renamed:
    """A result property name from before the units batch: refused, naming the registry name."""

    def __init__(self, new):
        self.new = new

    def __set_name__(self, owner, name):
        self.name = name

    def __get__(self, obj, owner=None):
        if obj is None:
            return self
        raise AttributeError(f'{self.name} is the format 0.2 name; read {self.new}')


def is_thermal(data):
    return isinstance(data, dict) and isinstance(data.get('physics'), dict) and any(
        isinstance(p, dict) and p.get('type') == PHYSICS for p in data['physics'].values())


def _number(value, path, positive=False, nonnegative=False, integer=False):
    try:
        valid = isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)
    except OverflowError:
        valid = False
    if not valid or (positive and value <= 0) or (nonnegative and value < 0) or (integer and not isinstance(value, int)):
        raise DocumentError(f'{path}: expected a finite ' + ('positive integer' if integer else
                            'positive number' if positive else 'nonnegative number' if nonnegative else 'number'))


def _authored(doc, path, unit=''):
    """The authored text of a value, for the summary line (a bare number gets ``unit``)."""
    value = doc.authored(path)
    if value is None:
        value = doc.authored(path + '.value')          # an annotated value
    if isinstance(value, dict) and 'value' in value:
        value = value['value']
    if isinstance(value, dict) and 'unit' in value:
        return f"[{', '.join(str(v) for v in value['values'])}] {value['unit']}"
    return value if isinstance(value, str) else f'{value} {unit}'.strip()


def rectangle_summary_03(doc, label, lines, versions=None):
    """The summary text of a format 0.3 rectangle heat document."""
    from .steady_boundary_contract import rect_geometry_03
    name, p = next(iter(doc.si['physics'].items()))
    where = f'physics.{name}'
    g = rect_geometry_03(doc)[1]
    dom = ', '.join(f'{k} {g["domain"][k]}' for k in ('xmin', 'xmax', 'ymin', 'ymax'))
    out = [f'{doc.si["name"]} (openphysics 0.3)', f'  physics {name}: {PHYSICS if not label else label}',
           f'  domain {dom} ({g["length_unit"]}); subdivision_count {doc.si["mesh"]["subdivision_count"]}',
           f'  thermal_conductivity {_authored(doc, where + ".thermal_conductivity")}'
           + (f', heat_source_density {_authored(doc, where + ".heat_source_density")}'
              if 'heat_source_density' in p else ', no heat_source_density')]
    temperatures = {tag: _authored(doc, f'{where}.prescribed_temperature.{tag}')
                    for tag in p['prescribed_temperature']}
    if 'inward_heat_flux' in p or 'convection' in p:
        flux = {tag: _authored(doc, f'{where}.inward_heat_flux.{tag}') for tag in p.get('inward_heat_flux', {})}
        convection = {tag: {k: _authored(doc, f'{where}.convection.{tag}.{k}') for k in c}
                      for tag, c in p.get('convection', {}).items()}
        out.append(f'  prescribed_temperature {temperatures}; inward_heat_flux {flux}; convection {convection}')
        out.append('  q.n = -inward_heat_flux + h (T - ambient_temperature); unselected natural sides insulated')
    else:
        out.append(f'  prescribed_temperature {temperatures}; remaining exterior insulated')
    out += lines
    if versions is not None:
        out.append(f'  result: {versions[0]}; layout: {versions[1]}')
    out.append('  output: SI (node_coordinates m, temperature K, heat_flux W/m^2, nodal heat rates W/m of depth)')
    return '\n'.join(out)


def thermal_summary(doc):
    from .thermal_regions import is_region_thermal, refuse_format_02 as refuse_regions_02, region_summary_03
    if doc.si is not None:
        if is_region_thermal(doc.data):
            from .thermal_regions import region_result_versions_03
            return region_summary_03(doc, f'{PHYSICS}, single steady heat, named material regions', [],
                                     region_result_versions_03(doc))
        from .steady_boundary_contract import steady_result_versions_03
        return rectangle_summary_03(doc, f'{PHYSICS}, single steady heat', [], steady_result_versions_03(doc))
    if is_region_thermal(doc.data):
        refuse_regions_02()
    refuse_format_02(doc, 'thermal_steady2d')


def require_fresh_output(path):
    if os.path.lexists(path):
        raise FileExistsError(f'thermal output already exists: {path}; choose a fresh output directory')


def _identity(path):
    s = path.lstat()
    return s.st_dev, s.st_ino


def _windows_handle(path, *, create=False):
    """Win32 sharing contract via stdlib only; callers own the returned handle.

    CREATE_NEW is exclusive; delete sharing requests rename/unlink compatibility.
    Open-file restrictions still apply; saved file identities use hard-link pins.
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


def _pin_file_link(path):
    """Keep a file identity alive without an open handle to its output path.

    Windows rename/replace can reject open destination files or directories
    containing open files even with delete sharing. A sibling hard link keeps
    the old file allocated while leaving the saved pathname free of handles.
    The filesystem must support same-volume hard links; failure is explicit.
    Only our link and its empty, exclusively created directory are removed.
    """
    directory = Path(tempfile.mkdtemp(prefix='.simcase-pin-', dir=path.parent.parent))
    directory_identity = _identity(directory)
    pin = directory/'file'
    try:
        os.link(path, pin)
    except OSError as exc:
        try:
            directory.rmdir()
        except OSError:
            pass  # never remove an unexpected file or mask link acquisition
        raise OSError('thermal output filesystem must support hard-link identity pins') from exc
    identity = _identity(pin)
    released = False

    def close():
        nonlocal released
        if released:
            return
        if directory.is_symlink() or _identity(directory) != directory_identity:
            raise OSError('thermal identity-pin directory was replaced; refusing cleanup')
        if os.path.lexists(pin):
            if pin.is_symlink() or _identity(pin) != identity:
                raise OSError('thermal identity pin was replaced; refusing cleanup')
            pin.unlink()
        directory.rmdir()  # preserve any unexpected file; never recurse
        released = True
    return close


def _pin_file(path, stream):
    if os.name == 'nt':
        return _pin_file_link(path)
    retained = [os.dup(stream.fileno())]

    def close():
        if retained:
            os.close(retained.pop())
    return close


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
            close_file = _pin_file(self.path/name, stream)
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
        # Releasing a detached old pin never deletes a replacement pathname.
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

    def __post_init__(self):
        # Bind ordinary public-result mutations to the calculation that ran.
        self.doc = self.doc.copy()
        self.doc.validate()  # the copy keeps the document's diagnostics; validate as the run did
        self._document_json = self._canonical_document()
        self._nodes_snapshot = np.array(self.mesh.nodes, copy=True)
        self._triangles_snapshot = np.array(self.mesh.triangles, copy=True)
        self._fixed_snapshot = np.array(self.dirichlet_node_ids, copy=True)
        self._temperature_snapshot = np.array(self.dirichlet_temperature_k, copy=True)
        from .steady_boundary_contract import steady_result_versions_03
        self._result_format, self._field_layout = steady_result_versions_03(self.doc)

    def _canonical_document(self):
        return self.doc.canonical_json(separators=(',', ':'))

    def _validated_document(self):
        # Compare BEFORE validation: restoring a removed default must not hide an edit.
        if self._canonical_document() != self._document_json:
            raise ValueError('thermal result document changed after the solve; run again')
        self.doc.validate()
        if self._canonical_document() != self._document_json:
            raise ValueError('thermal result document normalization changed after the solve')
        return self.doc

    def _validate_mesh_snapshot(self):
        for current, captured in (
                (self.mesh.nodes, self._nodes_snapshot),
                (self.mesh.triangles, self._triangles_snapshot),
                (self.dirichlet_node_ids, self._fixed_snapshot),
                (self.dirichlet_temperature_k, self._temperature_snapshot)):
            a = np.asarray(current)
            if a.dtype != captured.dtype or not np.array_equal(a, captured):
                raise ValueError('thermal result mesh or prescribed data changed after the solve')

    @property
    def result_format(self): return self._result_format

    @property
    def field_layout(self): return self._field_layout

    @property
    def boundary_enabled(self): return self._result_format.endswith(('-v2', '-v4'))

    # the format 0.2 names: a result refuses them, naming the registry name
    prescribed_outward_load_w_per_m = _Renamed('outward_prescribed_heat_rate_per_depth')
    ambient_load_w_per_m = _Renamed('ambient_convective_heat_rate_per_depth')
    convective_outward_w_per_m = _Renamed('outward_convective_heat_rate_per_depth')
    system_rhs_w_per_m = _Renamed('applied_heat_rate_per_depth')
    temperature_k = _Renamed('temperature')
    heat_flux_w_m2 = _Renamed('heat_flux')
    load_w_per_m = _Renamed('generated_heat_rate_per_depth')
    reaction_w_per_m = _Renamed('reaction_heat_rate_per_depth')
    residual_w_per_m = _Renamed('residual_heat_rate_per_depth')
    mesh_nodes_m = _Renamed('node_coordinates')

    @property
    def mesh_triangles(self): return self.mesh.triangles

    # registry names (format 0.3)
    @property
    def node_coordinates(self): return self.mesh.nodes

    @property
    def triangles(self): return self.mesh.triangles

    @property
    def temperature(self): return self.solution.temperature

    @property
    def heat_flux(self): return self.solution.heat_flux

    @property
    def generated_heat_rate_per_depth(self): return self.solution.load

    @property
    def reaction_heat_rate_per_depth(self): return self.solution.reaction

    @property
    def residual_heat_rate_per_depth(self): return self.solution.residual

    @property
    def outward_prescribed_heat_rate_per_depth(self): return self.solution.prescribed_outward_load

    @property
    def ambient_convective_heat_rate_per_depth(self): return self.solution.ambient_load

    @property
    def outward_convective_heat_rate_per_depth(self): return self.solution.convective_outward

    @property
    def applied_heat_rate_per_depth(self): return self.solution.system_rhs

    @property
    def prescribed_node_ids(self): return self.dirichlet_node_ids

    @property
    def prescribed_temperature(self): return self.dirichlet_temperature_k

    @property
    def balance(self):
        """The heat balance values of the summary, under the names this result saves them."""
        return dict(self.diagnostics)

    def _raw_arrays(self):
        return {ARRAY_NAMES_03[key]: a for key, a in self._checked_arrays().items()}

    def _checked_arrays(self):
        sol = self.solution
        arrays = dict(nodes_m=np.asarray(self.mesh.nodes), triangles=np.asarray(self.mesh.triangles),
                      temperature_k=np.asarray(sol.temperature), heat_flux_w_m2=np.asarray(sol.heat_flux),
                      load_w_per_m=np.asarray(sol.load), reaction_w_per_m=np.asarray(sol.reaction),
                      residual_w_per_m=np.asarray(sol.residual), dirichlet_node_ids=np.asarray(self.dirichlet_node_ids),
                      dirichlet_temperature_k=np.asarray(self.dirichlet_temperature_k))
        if self.boundary_enabled:
            arrays.update(prescribed_outward_load_w_per_m=np.asarray(sol.prescribed_outward_load),
                          ambient_load_w_per_m=np.asarray(sol.ambient_load),
                          convective_outward_w_per_m=np.asarray(sol.convective_outward),
                          system_rhs_w_per_m=np.asarray(sol.system_rhs))
        for key, a in arrays.items():
            if a.dtype.kind not in 'iuf' or not np.isfinite(a).all():
                raise ValueError(f'thermal raw array {key}: expected finite real numeric values')
        self._validated_document()
        self._validate_mesh_snapshot()
        nodes, tris, fixed = arrays['nodes_m'], arrays['triangles'], arrays['dirichlet_node_ids']
        if nodes.ndim != 2 or nodes.shape[1] != 2 or len(nodes) < 3:
            raise ValueError('thermal nodes_m: expected nonempty (N,2) coordinates')
        if tris.ndim != 2 or tris.shape[1] != 3 or not len(tris) or tris.dtype.kind not in 'iu':
            raise ValueError('thermal triangles: expected integer (M,3) connectivity')
        if fixed.ndim != 1 or (not self.boundary_enabled and not len(fixed)) or fixed.dtype.kind not in 'iu':
            raise ValueError('thermal dirichlet_node_ids: expected integer (D,) indices')
        if np.any(tris < 0) or np.any(tris >= len(nodes)) or np.any(fixed < 0) or np.any(fixed >= len(nodes)):
            raise ValueError('thermal raw connectivity/Dirichlet indices outside mesh')
        if np.any(np.diff(fixed.astype(np.int64)) <= 0):
            raise ValueError('thermal dirichlet_node_ids must be unique and sorted')
        shapes = {'temperature_k': (len(nodes),), 'heat_flux_w_m2': (len(tris), 2),
                  'load_w_per_m': (len(nodes),), 'reaction_w_per_m': (len(nodes),),
                  'residual_w_per_m': (len(nodes),), 'dirichlet_temperature_k': (len(fixed),)}
        if self.boundary_enabled:
            for key in ('prescribed_outward_load_w_per_m', 'ambient_load_w_per_m',
                        'convective_outward_w_per_m', 'system_rhs_w_per_m'):
                shapes[key] = (len(nodes),)
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

    def _summary_03(self):
        arrays = self._raw_arrays()
        doc = self.doc
        name, p = next(iter(doc.si['physics'].items()))
        vo = strict_value
        fields = {key: {'quantity': FIELDS_03[key][0], 'location': FIELDS_03[key][1], 'shape': list(a.shape),
                        'components': FIELDS_03[key][2]} for key, a in arrays.items()}
        maps = results_common.field_maps(fields)
        del maps['field_time_axes']                      # a steady result has no time axis
        result = {'name': doc.si['name'], 'physics_name': name, 'physics_type': PHYSICS,
                  **results_common.envelope(doc, result_format=self.result_format, field_layout=self.field_layout,
                                            timing_=strict_timing(self.timings)),
                  **maps, 'reaction_sign': REACTION_SIGN_03,
                  'mesh': {'nodes': len(self.mesh.nodes), 'triangles': len(self.mesh.triangles)},
                  'study': {'type': 'single'},
                  'thermal_conductivity': vo(p['thermal_conductivity'], 'thermal_conductivity')}
        if 'heat_source_density' in p:
            result['heat_source_density'] = vo(p['heat_source_density'], 'heat_source_density')
        result['prescribed_temperature'] = {tag: vo(v, 'prescribed_temperature')
                                            for tag, v in p['prescribed_temperature'].items()}
        result['prescribed_nodes'] = len(self.dirichlet_node_ids)
        result['minimum_temperature'] = vo(self.solution.temperature.min(), 'minimum_temperature')
        result['maximum_temperature'] = vo(self.solution.temperature.max(), 'maximum_temperature')
        for key, value in self.diagnostics.items():
            result[key] = vo(value, key)
        if self.boundary_enabled:
            result['inward_heat_flux'] = {tag: vo(v, 'inward_heat_flux') for tag, v in p.get('inward_heat_flux', {}).items()}
            result['convection'] = {tag: {'heat_transfer_coefficient': vo(c['heat_transfer_coefficient'],
                                                                           'heat_transfer_coefficient'),
                                          'ambient_temperature': vo(c['ambient_temperature'], 'ambient_temperature')}
                                    for tag, c in p.get('convection', {}).items()}
            result['outward_sign'] = OUTWARD_SIGN_03
            result['load_definition'] = LOAD_DEFINITION_03
        from .steady_boundary_contract import rect_geometry_03
        results_common.add_depth_totals(result, rect_geometry_03(doc)[2])
        results_common.dumps_summary(result)            # finite JSON only
        return result

    def summary(self):
        return self._summary_03()

    def save(self, outdir):
        owned = _OwnedOutput(outdir)
        try:
            owned.write('.incomplete', lambda f: f.write(b'incomplete thermal result\n'))
            summary = self.summary()
            encoded = results_common.dumps_summary(summary).encode('utf-8')
            model = model_bytes_03(self.doc)
            save_fields = self.doc.si['results']['save_fields']
            extra = dict(metadata_json=results_common.metadata_json(summary))
            owned.write('model.json', lambda f: f.write(model))
            owned.write('log.txt', lambda f: f.write(('\n'.join(self.log)+'\n').encode('utf-8')))
            if save_fields:
                arrays = dict(self._raw_arrays(), result_format=self.result_format, field_layout=self.field_layout,
                              **extra)
                if any(np.asarray(v).dtype.hasobject for v in arrays.values()):
                    raise ValueError('thermal raw arrays must not contain Python objects')
                for key, value in arrays.items():
                    a = np.asarray(value)
                    if a.dtype.kind in 'iuf' and not np.isfinite(a).all():
                        raise ValueError(f'thermal raw array {key} must be finite')
                owned.write('fields.npz', lambda f: np.savez_compressed(f, **arrays))
            owned.write('summary.json', lambda f: f.write(encoded))
            owned.finish()
        except Exception:
            owned.cleanup()
            raise
        finally:
            owned.close()
        return owned.path


def model_bytes_03(doc):
    """``model.json`` of a format 0.3 result: the authored bytes, else decimal-preserving JSON."""
    if doc.source_bytes is not None:
        return doc.source_bytes
    from .reader import dumps
    return (dumps(doc.data, indent=2, ensure_ascii=False)+'\n').encode('utf-8')


def log_lines_03(doc, lines):
    """``log.txt`` of a format 0.3 run: the extent lines, the summary, the run lines, every diagnostic."""
    from .diagnostics import render_text
    text = render_text(doc.diagnostics)
    return [*doc.extent_lines(), *lines, *([text] if text else [])]


def run_thermal(doc, verbose=True, *, mesh_limits=None):
    from .thermal_regions import is_region_thermal, run_region_thermal
    if is_region_thermal(doc.data):
        return run_region_thermal(doc, verbose=verbose, mesh_limits=mesh_limits)
    from galerkin import rectangle_mesh, assemble_stiffness
    try:
        from galerkin.thermal import solve_steady_heat
    except ImportError as exc:
        raise RuntimeError('thermal.steady2d requires a matching galerkin.thermal build') from exc
    doc.validate()
    doc = doc.copy()  # retain an independent validated document snapshot
    doc.validate()
    name, p = doc.sole_physics()
    grid = views.rectangle_mesh(doc, 'difference')
    t0 = time.perf_counter()
    mesh = rectangle_mesh(*grid.lengths, *grid.subdivisions)
    mesh.nodes += np.array(grid.origin)
    from .steady_boundary_contract import steady_boundary_inputs
    boundary_enabled = 'inward_heat_flux' in p or 'convection' in p
    if boundary_enabled:
        kwargs = steady_boundary_inputs(doc, mesh)
        prescribed = kwargs['dirichlet']
    else:
        # Preserve legacy side-to-node conversion and numerical call path.
        heat = views.rectangle_heat(doc)
        prescribed = {}
        for tag, value in heat.dirichlet.items():
            nodes = mesh.boundary.get(tag)
            if nodes is None or not len(nodes):
                raise DocumentError(f'physics.{name}.prescribed_temperature.{tag}: empty or unknown exterior tag')
            for node in nodes:
                if int(node) in prescribed and prescribed[int(node)] != value:
                    raise DocumentError(f'physics.{name}: conflicting corner temperature at node {node}')
                prescribed[int(node)] = value
        prescribed = dict(sorted(prescribed.items()))
        kwargs = dict(conductivity=heat.conductivity, dirichlet=prescribed, heat_source=heat.heat_source)
    fixed = np.array(sorted(prescribed), dtype=int)
    t_mesh = time.perf_counter()-t0
    # Capture the calculation before entering the producer, not after it returns.
    calculation_json = doc.canonical_json(separators=(',', ':'))
    calculation_nodes = np.array(mesh.nodes, copy=True)
    calculation_triangles = np.array(mesh.triangles, copy=True)
    calculation_prescribed = dict(prescribed)
    t0 = time.perf_counter()
    try:
        solution = solve_steady_heat(mesh, **kwargs)
    except (ValueError, RuntimeError) as exc:
        raise ValueError(f'physics.{name} ({PHYSICS}): {exc}') from exc
    t_solve = time.perf_counter()-t0
    if (doc.canonical_json(separators=(',', ':')) != calculation_json
            or not np.array_equal(mesh.nodes, calculation_nodes)
            or not np.array_equal(mesh.triangles, calculation_triangles)
            or prescribed != calculation_prescribed):
        raise ValueError('thermal calculation inputs changed during the solve')
    if boundary_enabled:
        for attr in ('prescribed_outward_load', 'ambient_load',
                     'convective_outward', 'system_rhs'):
            array = np.asarray(getattr(solution, attr, None))
            if (array.shape != (mesh.num_nodes,) or array.dtype.kind not in 'iuf'
                    or not np.isfinite(array).all()):
                raise ValueError(f'thermal boundary result {attr}: expected finite real (N,) data')
        # These are returned physical terms, not an absolute-temperature reassembly.
        G = solution.prescribed_outward_load
        C = solution.convective_outward
        source_heat = float(solution.load.sum())
        prescribed_outward = float(G.sum())
        convective_outward = float(C.sum())
        thermostat_outward = -float(solution.reaction.sum())
        outward = prescribed_outward+convective_outward+thermostat_outward
        balance_scale = max(float(sum(np.sum(abs(a)) for a in
                            (solution.load, solution.reaction, G, C))), np.finfo(float).tiny)
        free = np.setdiff1d(np.arange(mesh.num_nodes), fixed)
        diagnostics = {
            'source_heat_w_per_m': source_heat,
            'prescribed_outward_heat_w_per_m': prescribed_outward,
            'convective_outward_heat_w_per_m': convective_outward,
            'thermostat_outward_heat_w_per_m': thermostat_outward,
            'outward_heat_w_per_m': outward,
            'heat_balance_defect_w_per_m': outward-source_heat,
            'normalized_heat_balance_defect': abs(outward-source_heat)/balance_scale,
            # No K-only scale is presented as the Robin engine's normalized guard.
            'free_residual_max_w_per_m': float(np.max(abs(solution.residual[free]))) if len(free) else 0.}
    else:
        stiffness = assemble_stiffness(mesh, heat.conductivity)
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
    diagnostics = {BALANCE_03[key]: value for key, value in diagnostics.items()}
    printed = [doc.summary(), f'temperature: {solution.temperature.min():.12g} K to '
                              f'{solution.temperature.max():.12g} K',
               f'generated_heat_rate_per_depth {source_heat:.12g} W/m; '
               f'outward_heat_rate_per_depth {outward:.12g} W/m']
    log = log_lines_03(doc, printed)
    if verbose:
        print('\n'.join(printed))
    result = ThermalRunResult(doc, mesh, solution, fixed, np.array(list(prescribed.values())), diagnostics,
                              {'mesh': t_mesh, 'solve': t_solve}, log)
    result.summary()  # Validate complete output even without saving raw fields.
    return result



def _validate(doc):
    """Format 0.3 rectangles, regions and axisymmetric regions. A format 0.2 heat document is
    refused by name; a homogeneous version 1 rectangle compiles to the flat form (D-1)."""
    from .thermal_regions import is_region_thermal, refuse_format_02 as refuse_regions_02
    if doc.si is not None:
        if is_region_thermal(doc.data):
            from .thermal_regions import validate_region_thermal_03
            validate_region_thermal_03(doc)
            return
        from .steady_boundary_contract import validate_steady_rectangle_03
        validate_steady_rectangle_03(doc)
        return
    if is_region_thermal(doc.data):
        refuse_regions_02()
    refuse_format_02(doc, 'thermal_steady2d')


def _summary(doc):
    doc.validate()
    return thermal_summary(doc)


def _accepts_mesh_limits(data):
    """Region documents take mesh limits (simcase.mesh_limits); rectangle documents do not."""
    from .thermal_regions import is_region_thermal
    return is_region_thermal(data)


def _slots():
    from .steady_boundary_contract import heat_slots
    return heat_slots(PHYSICS)


def _forms():
    from .steady_boundary_contract import FORMS_03
    return FORMS_03


register(PhysicsKind(
    name=PHYSICS, types=frozenset({PHYSICS}), precedence=30,
    validate=_validate, run=run_thermal, summary=_summary,
    result_types=(ThermalRunResult,), fresh_output=True,
    stage_refusal='{stage} is an EM 2D stage; use run(document) for thermal.steady2d',
    accepts_mesh_limits=_accepts_mesh_limits, slots=_slots(), forms_03=_forms()))
