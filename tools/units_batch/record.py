# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Record what simcase hands its solvers and what it saves, for a list of documents.

Run it in its own interpreter against one source tree, with ``-I`` so that no
environment variable, user site or current directory decides what is imported:

    python -I tools/units_batch/record.py --root <checkout> --out <new dir> doc.json [id=doc.json ...]

The recorder puts ``<root>/packages/*/src`` first on ``sys.path`` and checks that
``simcase``, ``galerkin``, ``meshine`` and ``physmat`` were imported from there (an
editable install could otherwise serve another checkout). It imports every
submodule of the four packages (``simcase.studio`` excepted), then replaces each
module attribute that is one of the recorded callables with a recording wrapper,
so ``from x import f`` bindings are caught as well. Which callables are recorded is
the recorded tree's own declaration: ``<root>/tools/units_batch/targets.json``, or
``UNDECLARED_TARGETS`` for a tree that has none (every commit before that file).
For each document it runs ``simcase.run(Document.load(path))``, ``result.save()``
and the VTU export of exportable layouts, and writes ``<out>/<id>/record.json``
beside the saved files.

Every recorded call is stored in a canonical form: arrays as ``(dtype, shape,
sha256 of the bytes)``, floats as ``float.hex`` with their Python type noted,
mappings as ordered item lists, a meshine ``Domain`` as its pending regions and
loops, callables of position or time sampled at fixed points, and every call
the solver makes to a callback folded into a digest. Each call is stored twice
over: as written (positions and keywords) and bound to the callee's own parameter
names. ``compare.py`` compares two recordings. The harness is part of the
repository tools: no package imports it and nothing here ships.
"""

from __future__ import annotations

import argparse
import dataclasses
import functools
import hashlib
import importlib
import inspect
import json
import os
import pkgutil
import platform
import subprocess
import sys
import traceback
import types
from pathlib import Path

RECORD_FORMAT = "openphysics-units-batch-record-v1"
PACKAGES = ("physmat", "meshine", "galerkin", "simcase")
SKIPPED_MODULES = ("simcase.studio",)
MAX_DEPTH = 10
#: attributes that hold a lazily computed copy of other state, not state of their own
CACHE_ATTRIBUTES = frozenset({"_faces", "_cache"})
#: Mapping order is part of a canonical form (galerkin sums boundary entries in mapping order,
#: hazard H6), except in these lookup tables, which no solver iterates and whose order follows
#: set iteration under hash randomization (measured on thermoelastic_regions)
ORDER_FREE = frozenset({("galerkin.mesh.Mesh", "provenance_edges"), ("galerkin.mesh.Mesh", "selection_edges")})
GRID = 17                  # samples per axis of a callable's domain box
SIGMA_SAMPLES = 65         # samples across a conductivity model's valid range

TARGETS_FORMAT = "openphysics-units-batch-targets-v1"
#: where a source tree declares the callables it is recorded at (relative to its root)
TARGETS_FILE = "tools/units_batch/targets.json"
#: The recorded callables of a tree that declares none in TARGETS_FILE: every commit before
#: the phase-3 mode, f693ae3a and the phase-2 baseline 627eb28 included (README "Phase 3").
#: The same shape as TARGETS_FILE:
#:
#: - ``functions``: ``module:attribute``. Every module attribute in the four packages that is
#:   the same object is replaced, so the binding a caller looks up is the wrapper wherever it
#:   came from;
#: - ``function_modules``: every public function defined in these modules is recorded too;
#: - ``methods``: ``module:Class.method``, recorded on the class, so every instance is covered.
#:   physmat is recorded one level down, at the optical model's evaluation
#:   (``Dispersion.index`` and ``.eps``; every model class inherits them, and the install
#:   reports a subclass that overrides one), not at ``Material.eps``/``.index``;
#: - ``eigensolvers``: scipy eigensolvers, recorded where galerkin and simcase bind them;
#: - ``results``: calls whose result is recorded too: the meshers (their output is the next
#:   stage's input), the tracking settings and the material values physmat hands back. A
#:   solver's own result is compared through the saved arrays instead: the unselected
#:   candidates of an eigensolve (a near-null spurious mode and its neighbours) change in their
#:   last bits from run to run on the same inputs (measured on the em_gaussian_overlap_vector
#:   fixture: 6 runs, 6 different candidate arrays, identical saved arrays), so a recorded
#:   solver result would fail an identical rerun.
UNDECLARED_TARGETS = {
    "format": TARGETS_FORMAT,
    "functions": [
        "meshine.refine:generate",
        "galerkin.mesh:rectangle_mesh",
        "galerkin.thermal:solve_steady_heat",
        "galerkin.transient_heat:solve_transient_heat",
        "galerkin.electric:solve_steady_electric",
        "galerkin.joule_heating:solve_steady_joule_heat",
        "galerkin.temperature_joule_heating:solve_temperature_joule_heat",
        "galerkin.elasticity:solve_elasticity",
        "galerkin.thermoelasticity:freeze_temperature",
        "galerkin.thermoelasticity:solve_thermoelasticity",
        "simcase.physics_em_modes2d:solve",
        "galerkin.waveguide:solve_modes",
        "galerkin.waveguide:assemble_mode_system",
        "galerkin.mode_coordinates:mode_coordinates",
        "galerkin.mode_coordinates:solve_scalar_coordinates",
        "galerkin.mode_coordinates:scalar_coordinate_system",
        "galerkin.assembly:assemble_stiffness",
        "galerkin.assembly:assemble_mass",
        "galerkin.cavity:solve_cavity_box",
        "galerkin.material_cavity:solve_material_cavity_box",
        "simcase.tracking:tracking_settings",
        "simcase.subspace_tracking:subspace_settings",
    ],
    "function_modules": ["galerkin.mode_overlap"],
    "methods": [
        "physmat.dispersion:Dispersion.index",
        "physmat.dispersion:Dispersion.eps",
        "simcase.tracking:ModeTracker.__init__",
        "simcase.subspace_tracking:SubspaceTracker.__init__",
    ],
    "eigensolvers": ["eigs", "eigsh"],
    "results": [
        "meshine.refine.generate",
        "galerkin.mesh.rectangle_mesh",
        "simcase.tracking.tracking_settings",
        "simcase.subspace_tracking.subspace_settings",
        "physmat.dispersion.Dispersion.index",
        "physmat.dispersion.Dispersion.eps",
    ],
}
#: the recorded call names whose result is recorded too (set by ``install`` from the targets)
RESULTS_RECORDED = frozenset(UNDECLARED_TARGETS["results"])
#: the parameter a recorded call's times are read from, once bound: ``time_s`` on the code
#: before the galerkin step, ``time`` after it (the first one the call binds is read)
TIME_PARAMETERS = ("time_s", "time")


def check_targets(data, source: str) -> dict:
    """A target declaration, checked: the keys of UNDECLARED_TARGETS, each a list of names."""
    if not isinstance(data, dict) or data.get("format") != TARGETS_FORMAT:
        raise ValueError(f"{source}: format must be {TARGETS_FORMAT!r}")
    keys = set(UNDECLARED_TARGETS)
    if set(data) - {"description"} != keys:
        raise ValueError(f"{source}: keys must be {sorted(keys)} (and a description), not {sorted(data)}")
    for key in keys - {"format"}:
        names = data[key]
        if not isinstance(names, list) or not all(isinstance(n, str) and n for n in names) \
                or len(set(names)) != len(names):
            raise ValueError(f"{source}: {key} must be a list of distinct names")
    for name in data["functions"]:
        if name.count(":") != 1 or "." in name.split(":")[1]:
            raise ValueError(f"{source}: function {name!r} is not 'module:attribute'")
    for name in data["methods"]:
        if name.count(":") != 1 or name.split(":")[1].count(".") != 1:
            raise ValueError(f"{source}: method {name!r} is not 'module:Class.method'")
    return data


def load_targets(root: Path, path: Path | None = None) -> tuple[dict, str]:
    """The targets a tree is recorded at: ``path`` when given, else the tree's own
    TARGETS_FILE, else UNDECLARED_TARGETS. Returns the declaration and where it came from."""
    if path is None and (root / TARGETS_FILE).is_file():
        path, source = root / TARGETS_FILE, TARGETS_FILE
    elif path is not None:
        source = path.name
    else:
        return check_targets(UNDECLARED_TARGETS, "UNDECLARED_TARGETS"), "UNDECLARED_TARGETS"
    return check_targets(json.loads(path.read_text(encoding="utf-8")), source), source


# -- canonical forms ---------------------------------------------------------------------------

def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def dumps(obj) -> str:
    """Deterministic JSON text of a canonical form."""
    return json.dumps(obj, sort_keys=False, separators=(",", ":"), ensure_ascii=True, allow_nan=False)


def _qualname(obj) -> str:
    t = obj if isinstance(obj, type) else type(obj)
    return f"{t.__module__}.{t.__qualname__}"


#: The value transforms of phase-3 rule kinds 3, 5 and 6 (compare.py), per canonical array form
#: of the current document: ``{dumps(form): {"neg": form, "to_kernel": form}}``. An array is
#: stored by its digest, so the comparator cannot transform it; the recorder stores the forms of
#: ``0.0 - x`` and of ``to_kernel(x)`` (``out.real = x.real; out.imag = 0.0 - x.imag``, galerkin's
#: conventions rule) beside it. None while a callback stream folds its calls into a digest.
_TRANSFORMS: dict | None = None


def _array_form(obj) -> list:
    import numpy as np
    return ["array", obj.dtype.str, list(obj.shape), _sha(np.ascontiguousarray(obj).tobytes())]


def _note_transforms(obj, form: list) -> None:
    import numpy as np
    key = dumps(form)
    if _TRANSFORMS is None or key in _TRANSFORMS:
        return
    kernel = np.empty(obj.shape, dtype=complex)
    kernel.real = obj.real
    kernel.imag = 0.0 - obj.imag
    _TRANSFORMS[key] = {"neg": _array_form(0.0 - obj), "to_kernel": _array_form(kernel)}


def _is_material(obj) -> bool:
    """A physmat ``Material`` (``physmat._material`` since the galerkin step, ``physmat.material``
    before it; any physmat module, so that a moved class keeps its form)."""
    t = type(obj)
    return t.__name__ == "Material" and t.__module__.split(".")[0] == "physmat"


def _number(x, type_name: str):
    """A real scalar: float.hex of its double and its Python type (hazard H8)."""
    import numpy as np
    if isinstance(x, (int, np.integer)) and not isinstance(x, bool) and abs(int(x)) > 2 ** 53:
        return ["num", type_name, f"int:{int(x)}"]
    return ["num", type_name, float.hex(float(x))]


class Context:
    """What a callable found in a recorded call is sampled at: points, normals and times."""

    def __init__(self, points=None, times=()):
        import numpy as np
        self.points = points
        self.times = tuple(times)
        if points is not None:
            angles = np.arange(len(points)) * (2 * np.pi / 7.0)
            self.normals = np.column_stack([np.cos(angles), np.sin(angles)])
        else:
            self.normals = None


EMPTY = Context()


def _box_grid(lo, hi):
    import numpy as np
    xs = np.linspace(lo[0], hi[0], GRID)
    ys = np.linspace(lo[1], hi[1], GRID)
    gx, gy = np.meshgrid(xs, ys, indexing="xy")
    return gx.ravel(), gy.ravel()


def _sample_points(nodes):
    """The mesh nodes followed by a 17 x 17 grid of their bounding box."""
    import numpy as np
    nodes = np.asarray(nodes, dtype=float)
    if nodes.ndim != 2 or nodes.shape[1] != 2 or not len(nodes):
        return None
    gx, gy = _box_grid(nodes.min(axis=0), nodes.max(axis=0))
    return np.concatenate([nodes, np.column_stack([gx, gy])])


def _original(function):
    """The function a recording wrapper of this module stands for (samples never record)."""
    while getattr(function, "__units_batch_original__", None) is not None:
        function = function.__units_batch_original__
    return function


def _try(function, *args):
    try:
        return canon(_original(function)(*args))
    except Exception as exc:                   # the refusal is part of the behaviour
        return ["raises", _qualname(exc)]


def _required_positional(function):
    try:
        parameters = list(inspect.signature(function).parameters.values())
    except (TypeError, ValueError):
        return None
    if any(p.kind is p.VAR_POSITIONAL for p in parameters):
        return None
    return len([p for p in parameters if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)
                and p.default is p.empty])


def _callable(function, ctx: Context):
    """Samples of a callback by its number of required positional parameters (galerkin's rule):
    1 -> (points) and (time) at the call's times, 2 -> (points, normals), 3 -> (points, normals, t)."""
    function = _original(function)
    arity = _required_positional(function)
    samples = []
    if arity == 1:
        if ctx.points is not None:
            samples.append(["points", _try(function, ctx.points)])
        for t in ctx.times:
            samples.append(["time", float.hex(float(t)), _try(function, t)])
    elif arity == 2 and ctx.points is not None:
        samples.append(["points,normals", _try(function, ctx.points, ctx.normals)])
    elif arity == 3 and ctx.points is not None:
        for t in ctx.times or (0.0,):
            samples.append(["points,normals,time", float.hex(float(t)),
                            _try(function, ctx.points, ctx.normals, t)])
    return ["callable", arity, samples]


def _conductivity_model(obj, ctx, depth, stack):
    """sigma(T) models: the valid pair and the values at 65 temperatures across it."""
    import numpy as np
    lo, hi = (float(v) for v in obj.temperature_range)
    temperatures = np.linspace(lo, hi, SIGMA_SAMPLES)
    out = ["conductivity-model", _qualname(obj), [float.hex(lo), float.hex(hi)],
           _try(obj.evaluate, temperatures)]
    derivative = getattr(obj, "derivative", None)
    out.append(None if derivative is None else _try(derivative, temperatures))
    return out


def _domain(domain):
    """A meshine Domain before meshing: default size, tolerances and its pending regions in order."""
    regions = []
    for name, loops, size in domain._pending:
        rendered = []
        for loop in loops:
            if hasattr(loop, "center") and hasattr(loop, "radius") and hasattr(loop, "n"):
                rendered.append(["circle", [float.hex(float(c)) for c in loop.center],
                                 float.hex(float(loop.radius)), int(loop.n)])
            else:
                rendered.append(["loop", [[float.hex(float(c)) for c in vertex] for vertex in loop]])
        regions.append([name, None if size is None else float.hex(float(size)), rendered])
    return ["meshine.Domain", [float.hex(domain.default_size), float.hex(domain.merge_eps),
                               float.hex(domain.param_eps), float.hex(domain.snap_eps)], regions]


def _is_domain(obj) -> bool:
    return _qualname(obj) == "meshine.geometry.Domain"


def _is_conductivity_model(obj) -> bool:
    return (dataclasses.is_dataclass(obj) and not isinstance(obj, type)
            and callable(getattr(obj, "evaluate", None)) and hasattr(obj, "temperature_range"))


def _sparse(obj):
    import numpy as np
    fmt = obj.format
    if fmt in ("csr", "csc", "bsr"):
        parts = {"indptr": obj.indptr, "indices": obj.indices, "data": obj.data}
    elif fmt == "coo":
        parts = {"row": obj.row, "col": obj.col, "data": obj.data}
    else:
        obj = obj.tocoo()
        parts = {"row": obj.row, "col": obj.col, "data": obj.data}
    return ["sparse", fmt, str(obj.dtype), list(obj.shape),
            [[k, canon(np.asarray(v))] for k, v in parts.items()]]


def _linear_operator(obj):
    import numpy as np
    out = ["linear-operator", _qualname(obj), list(obj.shape), str(obj.dtype)]
    try:
        out.append(canon(obj.matvec(np.ones(obj.shape[1], dtype=obj.dtype))))
    except Exception as exc:
        out.append(["raises", _qualname(exc)])
    return out


def canon(obj, ctx: Context = EMPTY, depth: int = 0, stack: frozenset = frozenset()):
    """The canonical JSON form of a recorded value (see the module docstring)."""
    import numpy as np
    if obj is None or isinstance(obj, str):
        return obj
    if isinstance(obj, (bool, np.bool_)):
        return ["bool", bool(obj)]
    if isinstance(obj, (int, float, np.integer, np.floating)):
        return _number(obj, type(obj).__name__)
    if isinstance(obj, (complex, np.complexfloating)):
        return ["complex", type(obj).__name__, float.hex(float(obj.real)), float.hex(float(obj.imag))]
    if isinstance(obj, (bytes, bytearray)):
        return ["bytes", _sha(bytes(obj))]
    if isinstance(obj, np.ndarray):
        if obj.dtype.kind == "O":
            return ["object-array", list(obj.shape), [canon(v, ctx, depth + 1, stack) for v in obj.ravel()]]
        form = _array_form(obj)
        if obj.dtype.kind in "iufc":
            _note_transforms(obj, form)
        return form
    if depth > MAX_DEPTH:
        return ["deep", _qualname(obj)]
    if id(obj) in stack:
        return ["cycle", _qualname(obj)]
    inner = stack | {id(obj)}
    if isinstance(obj, dict):
        return ["dict", type(obj).__name__,
                [[canon(k, ctx, depth + 1, inner), canon(v, ctx, depth + 1, inner)] for k, v in obj.items()]]
    if isinstance(obj, (list, tuple)):
        return [type(obj).__name__, [canon(v, ctx, depth + 1, inner) for v in obj]]
    if isinstance(obj, (set, frozenset)):
        items = [canon(v, ctx, depth + 1, inner) for v in obj]
        return ["set", sorted(items, key=dumps)]
    if isinstance(obj, types.ModuleType):
        return ["module", obj.__name__]
    if isinstance(obj, type):
        return ["type", _qualname(obj)]
    try:
        import scipy.sparse as sp
        if sp.issparse(obj):
            return _sparse(obj)
        from scipy.sparse.linalg import LinearOperator
        if isinstance(obj, LinearOperator):
            return _linear_operator(obj)
    except ImportError:                        # pragma: no cover - scipy is a dependency
        pass
    if _is_domain(obj):
        return _domain(obj)
    if _qualname(obj) == "meshine.geometry.Circle":
        return ["circle", [float.hex(float(c)) for c in obj.center], float.hex(obj.radius), int(obj.n)]
    if _is_material(obj):
        # what the optical model receives; the record's metadata (source, datum) is not an input
        return ["physmat.Material", obj.name, canon(getattr(obj, "optical", None), ctx, depth + 1, inner)]
    if _is_conductivity_model(obj):
        return _conductivity_model(obj, ctx, depth, inner)
    if isinstance(obj, (types.FunctionType, types.MethodType, types.BuiltinFunctionType,
                        functools.partial, np.ufunc)):
        if isinstance(obj, np.ufunc):
            return ["ufunc", obj.__name__]
        return _callable(obj, ctx)
    if dataclasses.is_dataclass(obj):
        fields = [(f.name, getattr(obj, f.name, None)) for f in dataclasses.fields(obj)
                  if f.name not in CACHE_ATTRIBUTES]
        return ["object", _qualname(obj), [[k, canon(v, ctx, depth + 1, inner)] for k, v in fields]]
    state = getattr(obj, "__dict__", None)
    if isinstance(state, dict):
        name = _qualname(obj)
        items = sorted((k, v) for k, v in state.items()
                       if k not in CACHE_ATTRIBUTES and not k.startswith("__units_batch"))
        return ["object", name, [[k, _sorted_mapping(canon(v, ctx, depth + 1, inner))
                                  if (name, k) in ORDER_FREE else canon(v, ctx, depth + 1, inner)]
                                 for k, v in items]]
    return ["opaque", _qualname(obj)]


def _sorted_mapping(form):
    """A canonical mapping with its items sorted (only for the ORDER_FREE lookup tables)."""
    if isinstance(form, list) and len(form) == 3 and form[0] == "dict":
        return ["dict", form[1], sorted(form[2], key=dumps)]
    return form


# -- recording -------------------------------------------------------------------------------

class Stream:
    """Every call a solver makes to one callback, folded into a digest. ``path`` is where the
    callback was passed as written (``args[1]``, ``kwargs['flux']['top']``); ``bound`` is the
    same place by parameter name, ``(parameter, rest)``, or None when the call did not bind."""

    def __init__(self, path: str, bound=None):
        self.path, self.bound, self.calls, self._hash = path, bound, 0, hashlib.sha256()

    def wrap(self, function):
        @functools.wraps(function)             # keeps the signature galerkin inspects
        def recorded(*args, **kwargs):
            try:
                result = function(*args, **kwargs)
            except Exception as exc:
                self._fold(args, kwargs, ["raises", _qualname(exc)])
                raise
            self._fold(args, kwargs, None, result)
            return result
        recorded.__units_batch_original__ = function
        return recorded

    def _fold(self, args, kwargs, form, result=None):
        global _TRANSFORMS
        table, _TRANSFORMS = _TRANSFORMS, None          # a digest cannot be transformed
        try:
            if form is None:
                form = canon(result)
            self.calls += 1
            self._hash.update(dumps([canon(list(args)), canon(kwargs), form]).encode("ascii"))
            self._hash.update(b"\n")
        finally:
            _TRANSFORMS = table

    def record(self):
        return [self.path, self.calls, self._hash.hexdigest()]

    def bound_record(self):
        return [*self.bound, self.calls, self._hash.hexdigest()]


def _wrap_callbacks(obj, path: str, streams: list, depth: int = 0, bound=None):
    """``obj`` with every callback inside plain containers replaced by a stream recorder."""
    import numpy as np
    below = (lambda part: None if bound is None else (bound[0], bound[1] + part))   # noqa: E731
    if depth > 6:
        return obj
    if isinstance(obj, (types.FunctionType, types.MethodType, functools.partial)) and not isinstance(obj, np.ufunc):
        stream = Stream(path, bound)
        streams.append(stream)
        return stream.wrap(obj)
    if type(obj) is dict:
        new = {k: _wrap_callbacks(v, f"{path}[{k!r}]", streams, depth + 1, below(f"[{k!r}]")) for k, v in obj.items()}
        return new if any(new[k] is not obj[k] for k in obj) else obj
    if type(obj) in (list, tuple):
        new = [_wrap_callbacks(v, f"{path}[{i}]", streams, depth + 1, below(f"[{i}]")) for i, v in enumerate(obj)]
        return obj if all(a is b for a, b in zip(new, obj)) else type(obj)(new)
    if _is_conductivity_model(obj):
        changes = {}
        for name in ("evaluate", "derivative"):
            value = getattr(obj, name, None)
            if value is not None and callable(value):
                stream = Stream(f"{path}.{name}", below(f".{name}"))
                streams.append(stream)
                changes[name] = stream.wrap(value)
        return dataclasses.replace(obj, **changes)
    return obj


class Binding:
    """A call's arguments by parameter name, through the callee's own signature on its side
    (phase 3): moving an argument between a position and a keyword leaves it unchanged.

    ``places`` maps each place an argument was written at, ``("args", i)`` or
    ``("kwargs", key)``, to ``(parameter, rest)``: ``rest`` is ``""``, or ``[j]`` and ``['key']``
    inside ``*args`` and ``**kwargs``. Arguments not passed are not bound (no defaults are
    applied; a removed default is rule kind 8). ``reason`` says why a call did not bind."""

    def __init__(self, callee, args, kwargs, has_self=False):
        self.parameters, self.places, self.reason = [], {}, None
        try:
            signature = inspect.signature(callee)
        except (TypeError, ValueError) as exc:
            self.reason = f"no signature ({_qualname(exc)})"
            return
        marks = [("args", i) for i in range(len(args))]
        named = {key: ("kwargs", key) for key in kwargs}
        try:
            bound = signature.bind(*((None,) if has_self else ()), *marks, **named)
        except TypeError as exc:
            self.reason = f"does not bind: {exc}"
            return
        for i, (parameter, value) in enumerate(bound.arguments.items()):
            if has_self and i == 0:
                continue
            kind = signature.parameters[parameter].kind
            self.parameters.append((parameter, kind, value))
            if kind is inspect.Parameter.VAR_POSITIONAL:
                self.places.update({mark: (parameter, f"[{j}]") for j, mark in enumerate(value)})
            elif kind is inspect.Parameter.VAR_KEYWORD:
                self.places.update({mark: (parameter, f"[{key!r}]") for key, mark in value.items()})
            else:
                self.places[value] = (parameter, "")

    @property
    def ok(self) -> bool:
        return self.reason is None

    def _each(self, parameter_kind, value, at):
        if parameter_kind is inspect.Parameter.VAR_POSITIONAL:
            return "tuple", [at(mark) for mark in value]
        if parameter_kind is inspect.Parameter.VAR_KEYWORD:
            return "dict", {key: at(mark) for key, mark in value.items()}
        return None, at(value)

    def values(self, args, kwargs) -> dict:
        """{parameter: value} of the call (a tuple for ``*args``, a dict for ``**kwargs``)."""
        at = lambda mark: args[mark[1]] if mark[0] == "args" else kwargs[mark[1]]          # noqa: E731
        out = {}
        for parameter, kind, value in self.parameters:
            shape, item = self._each(kind, value, at)
            out[parameter] = tuple(item) if shape == "tuple" else item
        return out

    def forms(self, args_forms, kwargs_forms) -> dict:
        """{parameter: canonical form}, from the forms of the arguments as written."""
        at = lambda mark: args_forms[mark[1]] if mark[0] == "args" else kwargs_forms[mark[1]]  # noqa: E731
        out = {}
        for parameter, kind, value in self.parameters:
            shape, item = self._each(kind, value, at)
            out[parameter] = (["tuple", item] if shape == "tuple" else
                              ["dict", "dict", [[k, v] for k, v in item.items()]] if shape == "dict" else item)
        return out


class Recorder:
    def __init__(self):
        self.calls: list = []
        self.depth = 0
        self.mesher_outputs: list = []
        self.transforms: dict = {}

    def reset(self):
        global _TRANSFORMS
        self.calls, self.depth, self.mesher_outputs, self.transforms = [], 0, [], {}
        _TRANSFORMS = self.transforms

    def finish(self) -> dict:
        """The transform table of the calls; the exports and saved files that follow add none."""
        global _TRANSFORMS
        _TRANSFORMS = None
        return self.transforms

    # every recorded call goes through here
    def call(self, name, function, args, kwargs, *, bound_self=None, callee=None, has_self=False):
        """Record one call of ``function``. ``callee`` is the function whose signature the call is
        bound to (``function`` itself unless given); ``has_self`` drops its first parameter."""
        binding = Binding(function if callee is None else callee, args, kwargs, has_self or bound_self is not None)
        values = binding.values(args, kwargs) if binding.ok else None
        ctx = _context(name, args, kwargs, values)
        entry = {"seq": len(self.calls), "depth": self.depth, "function": name}
        if bound_self is not None:
            entry["self"] = canon(bound_self, ctx)
        # each argument at depth 1, as inside canon(list(args)) and canon(kwargs)
        args_forms = [canon(a, ctx, 1) for a in args]
        kwargs_forms = {k: canon(v, ctx, 1) for k, v in kwargs.items()}
        entry["args"] = ["list", args_forms]
        entry["kwargs"] = ["dict", "dict", [[k, v] for k, v in kwargs_forms.items()]]
        entry["bound"] = binding.forms(args_forms, kwargs_forms) if binding.ok else ["unbound", binding.reason]
        if name == "meshine.refine.generate":
            entry["samples"] = {}
        self.calls.append(entry)
        streams: list = []
        place = binding.places.get
        args = tuple(_wrap_callbacks(a, f"args[{i}]", streams, bound=place(("args", i))) for i, a in enumerate(args))
        kwargs = {k: _wrap_callbacks(v, f"kwargs[{k!r}]", streams, bound=place(("kwargs", k)))
                  for k, v in kwargs.items()}
        self.depth += 1
        try:
            result = function(*(() if bound_self is None else (bound_self,)), *args, **kwargs)
        except Exception as exc:
            entry["raised"] = [_qualname(exc), str(exc)]
            raise
        finally:
            self.depth -= 1
            entry["callbacks"] = [s.record() for s in streams]
            entry["bound_callbacks"] = (sorted(s.bound_record() for s in streams) if binding.ok else None)
        if name == "meshine.refine.generate":
            entry["samples"] = _mesher_samples(args, kwargs, result, values or {})
            self.mesher_outputs.append((entry["seq"], result))
        if name in RESULTS_RECORDED:
            entry["result"] = canon(result, ctx)
        return result


def _context(name, args, kwargs, values=None) -> Context:
    """Galerkin calls sample their callbacks on the mesh nodes, a grid of the mesh box and the
    call's times; other calls take no position samples. The times are the bound time parameter
    (TIME_PARAMETERS), whatever its name on the recorded side and however it was passed."""
    import numpy as np
    if not (name.startswith("galerkin.") or name.startswith("simcase.")):
        return EMPTY
    first = args[0] if args else kwargs.get("mesh", kwargs.get("space"))
    nodes = getattr(first, "nodes", None)
    if nodes is None:
        nodes = getattr(getattr(first, "mesh", None), "nodes", None)
    given = kwargs if values is None else values
    times = next((given[p] for p in TIME_PARAMETERS if p in given), None)
    times = () if times is None else [float(t) for t in np.asarray(times, dtype=float).ravel()]
    return Context(None if nodes is None else _sample_points(nodes), times)


def _mesher_samples(args, kwargs, result, values):
    """The namer at every input-loop segment midpoint and output boundary-edge midpoint; the size
    function on a 17 x 17 grid of the domain box and at the output nodes (originals, not wrappers)."""
    import numpy as np
    domain = values["domain"] if "domain" in values else (args[0] if args else kwargs["domain"])
    namer = values["boundary_names"] if "boundary_names" in values else \
        (args[1] if len(args) > 1 else kwargs.get("boundary_names", "outer"))
    size_fn = values.get("size_fn", kwargs.get("size_fn"))
    namer, size_fn = _original(namer), _original(size_fn)
    loops = []
    for _name, region_loops, _size in domain._pending:
        for loop in region_loops:
            vertices = loop.vertices() if hasattr(loop, "vertices") else np.asarray(loop, dtype=float)
            loops.append(np.asarray(vertices, dtype=float))
    out = {}
    if isinstance(namer, str):
        out["namer"] = ["string", namer]
    else:
        def name_at(point):
            try:
                return namer(tuple(point))
            except Exception as exc:           # a refusal is part of the namer's behaviour
                return ["raises", _qualname(exc)]
        mids = [0.5 * (v + np.roll(v, -1, axis=0)) for v in loops]
        names = [name_at(p) for m in mids for p in m]
        edge_mids = []
        for tag, edges in result.boundary_edges.items():
            edges = np.asarray(edges, dtype=int).reshape(-1, 2)
            points = 0.5 * (result.nodes[edges[:, 0]] + result.nodes[edges[:, 1]])
            edge_mids.append([tag, [name_at(p) for p in points]])
        out["namer"] = ["callable", names, edge_mids]
    if size_fn is not None and loops:
        allv = np.concatenate(loops)
        gx, gy = _box_grid(allv.min(axis=0), allv.max(axis=0))
        out["size_fn"] = [_try(size_fn, gx, gy),
                          _try(size_fn, result.nodes[:, 0].copy(), result.nodes[:, 1].copy())]
    return out


RECORDER = Recorder()


def _function_wrapper(name, original):
    @functools.wraps(original)
    def recorded(*args, **kwargs):
        return RECORDER.call(name, original, args, kwargs)
    recorded.__units_batch_original__ = original
    return recorded


def _method_wrapper(name, original):
    """A recorded method. A constructor records its arguments (the tracker settings, mesh and
    weights), not the object it builds; other methods record their object as ``self``."""
    if name.endswith(".__init__"):
        @functools.wraps(original)
        def recorded(self, *args, **kwargs):
            return RECORDER.call(name, lambda *a, **k: original(self, *a, **k), args, kwargs,
                                 callee=original, has_self=True)
    else:
        @functools.wraps(original)
        def recorded(self, *args, **kwargs):
            return RECORDER.call(name, original, args, kwargs, bound_self=self)
    recorded.__units_batch_original__ = original
    return recorded


class _ModuleProxy:
    """A module whose eigensolvers record their calls; every other attribute is the module's."""

    def __init__(self, module, overrides):
        self.__dict__["_module"] = module
        self.__dict__["_overrides"] = overrides

    def __getattr__(self, name):
        overrides = self.__dict__["_overrides"]
        return overrides[name] if name in overrides else getattr(self.__dict__["_module"], name)


def _package_modules():
    return sorted((name, module) for name, module in list(sys.modules.items())
                  if module is not None and name.split(".")[0] in PACKAGES)


def install(root: Path, targets: dict | None = None, source: str = "UNDECLARED_TARGETS") -> dict:
    """Import the four packages from ``root``, then install the recording wrappers of
    ``targets`` (a checked declaration; UNDECLARED_TARGETS when None)."""
    global RESULTS_RECORDED
    targets = check_targets(UNDECLARED_TARGETS if targets is None else targets, source)
    RESULTS_RECORDED = frozenset(targets["results"])
    sys.dont_write_bytecode = True             # -I ignores PYTHONDONTWRITEBYTECODE; leave the tree as it is
    for src in sorted((root / "packages").glob("*/src")):
        sys.path.insert(0, str(src))
    report = {"import_failures": [], "targets_missing": [], "targets_shadowed": [], "bindings": [],
              "targets_source": source, "targets": []}
    for top in PACKAGES:
        package = importlib.import_module(top)
        for info in pkgutil.walk_packages(package.__path__, top + "."):
            if info.name.startswith(SKIPPED_MODULES) or info.name.endswith(".__main__"):
                continue
            try:
                importlib.import_module(info.name)
            except Exception as exc:
                report["import_failures"].append([info.name, _qualname(exc)])
    import simcase
    simcase.Document                           # the lazy runner chain, as a first use loads it
    origins = {}
    for top in PACKAGES:
        file = Path(sys.modules[top].__file__).resolve()
        origins[top] = file.relative_to(root.resolve()).as_posix() if file.is_relative_to(root.resolve()) else str(file)
        if not file.is_relative_to((root / "packages").resolve()):
            raise SystemExit(f"{top} was imported from {file}, not from {root}/packages: an installed copy "
                             "or another checkout would be recorded instead of this tree")
    report["origins"] = origins

    replacements = {}                          # id(original) -> wrapper
    names = [tuple(name.split(":")) for name in targets["functions"]]
    for module_name in targets["function_modules"]:
        module = sys.modules.get(module_name)
        if module is None:
            report["targets_missing"].append(module_name)
            continue
        names += [(module_name, attr) for attr, value in sorted(vars(module).items())
                  if isinstance(value, types.FunctionType) and value.__module__ == module_name
                  and not attr.startswith("_")]
    for module_name, attr in names:
        module = sys.modules.get(module_name)
        original = getattr(module, attr, None) if module is not None else None
        if original is None:
            report["targets_missing"].append(f"{module_name}.{attr}")
            continue
        replacements[id(original)] = (original, _function_wrapper(f"{module_name}.{attr}", original))
        report["targets"].append(f"{module_name}.{attr}")
    import scipy.sparse.linalg as spla
    eig_wrappers = {name: _function_wrapper(f"scipy.sparse.linalg.{name}", getattr(spla, name))
                    for name in targets["eigensolvers"]}
    for name in targets["eigensolvers"]:
        replacements[id(getattr(spla, name))] = (getattr(spla, name), eig_wrappers[name])
        report["targets"].append(f"scipy.sparse.linalg.{name}")
    proxy = _ModuleProxy(spla, eig_wrappers)
    for module_name, module in _package_modules():
        for attr, value in list(vars(module).items()):
            hit = replacements.get(id(value))
            if hit is not None and hit[0] is value:
                setattr(module, attr, hit[1])
                report["bindings"].append(f"{module_name}.{attr}")
            elif value is spla:
                setattr(module, attr, proxy)
                report["bindings"].append(f"{module_name}.{attr} (scipy.sparse.linalg)")
    for target in targets["methods"]:
        module_name, rest = target.split(":")
        cls_name, method = rest.split(".")
        cls = getattr(sys.modules.get(module_name), cls_name, None)
        original = getattr(cls, method, None) if cls is not None else None
        if original is None:
            report["targets_missing"].append(f"{module_name}.{cls_name}.{method}")
            continue
        setattr(cls, method, _method_wrapper(f"{module_name}.{cls_name}.{method}", original))
        report["bindings"].append(f"{module_name}.{cls_name}.{method}")
        report["targets"].append(f"{module_name}.{cls_name}.{method}")
        # a subclass that defines the method itself would bypass the wrapper on the class
        report["targets_shadowed"] += [f"{_qualname(sub)}.{method}" for sub in _subclasses(cls)
                                       if method in sub.__dict__]
    report["bindings"].sort()
    report["targets"].sort()
    report["targets_shadowed"].sort()
    return report


def _subclasses(cls) -> list:
    out, todo = [], list(cls.__subclasses__())
    while todo:
        sub = todo.pop()
        if sub not in out:
            out.append(sub)
            todo += sub.__subclasses__()
    return out


def leaked_bindings() -> list:
    """Module attributes that still hold an original recorded function (a binding made after
    install that the wrappers missed); none is expected."""
    originals = set()
    for module_name, module in _package_modules():
        for value in vars(module).values():
            original = getattr(value, "__units_batch_original__", None)
            if original is not None:
                originals.add(id(original))
    import scipy.sparse.linalg as spla
    found = []
    for module_name, module in _package_modules():
        for attr, value in vars(module).items():
            if (id(value) in originals and getattr(value, "__units_batch_original__", None) is None) \
                    or value is spla:
                found.append(f"{module_name}.{attr}")
    return sorted(found)


# -- outputs ---------------------------------------------------------------------------------

def _file_table(folder: Path) -> list:
    return [[p.relative_to(folder).as_posix(), _sha(p.read_bytes()), p.stat().st_size]
            for p in sorted(folder.rglob("*")) if p.is_file()]


def _npz_table(path: Path) -> list:
    import numpy as np
    with np.load(path, allow_pickle=False) as data:
        return [[key, data[key].dtype.str, list(data[key].shape),
                 _sha(np.ascontiguousarray(data[key]).tobytes())] for key in data.files]


def _vtu(path: Path) -> dict:
    import meshio
    mesh = meshio.read(path)
    out = {"points": canon(mesh.points),
           "cells": [[block.type, canon(block.data)] for block in mesh.cells],
           "point_data": [[k, canon(v)] for k, v in mesh.point_data.items()],
           "cell_data": [[k, [canon(a) for a in v]] for k, v in mesh.cell_data.items()],
           "field_data": [[k, canon(v)] for k, v in mesh.field_data.items()]}
    return out


def _pvd(path: Path) -> list:
    import xml.etree.ElementTree as ET
    root = ET.parse(path).getroot()
    return [[d.get("timestep"), d.get("file")] for d in root.iter("DataSet")]


#: (name, function, target): every export of a saved result is attempted; a layout an export
#: does not take is recorded as its refusal (the exception type and message)
EXPORTS = (("fields", "export_fields", "fields.vtu"),
           ("time_series", "export_time_series", "time_series"),
           ("sweep", "export_sweep", "sweep"))


def _export(result_dir: Path, export_dir: Path, scrub) -> dict:
    """The VTU exports of the saved fields, each as a user would call it."""
    fields = result_dir / "fields.npz"
    if not fields.exists():
        return {}
    from simcase import export
    export_dir.mkdir(parents=True)
    out = {}
    for name, function, target in EXPORTS:
        try:
            getattr(export, function)(fields, export_dir / target)
        except Exception as exc:
            out[name] = {"status": "refused", "exception": [_qualname(exc), scrub(str(exc))]}
            continue
        files = {}
        base = export_dir / target
        for path in ([base] if base.is_file() else sorted(base.rglob("*"))):
            rel = path.relative_to(export_dir).as_posix()
            if path.suffix == ".vtu":
                files[rel] = _vtu(path)
            elif path.suffix == ".pvd":
                files[rel] = {"collection": _pvd(path)}
        out[name] = {"status": "ok", "files": files}
    return out


def _length_units(data) -> list:
    units = []
    if isinstance(data, dict):
        u = data.get("units")
        if isinstance(u, dict) and "length" in u:
            units.append(u["length"])
        g = data.get("geometry")
        if isinstance(g, dict):
            if "length_unit" in g:
                units.append(g["length_unit"])
            for component in (g.get("components") or {}).values():
                if isinstance(component, dict) and "length_unit" in component:
                    units.append(component["length_unit"])
    return [u if isinstance(u, str) else canon(u) for u in units]


def _scrub(text: str, *prefixes) -> str:
    for prefix in prefixes:
        text = text.replace(str(prefix), "<path>")
    return text


def _diagnostics(doc) -> dict:
    out = {"notes": [str(n) for n in getattr(doc, "notes", []) or []]}
    roundings = getattr(doc, "geometry_roundings", None) or []
    out["pm_roundings"] = [f"{getattr(r, 'path', '?')}: {getattr(r, 'written', '?')}" for r in roundings]
    diagnostics = getattr(doc, "diagnostics", None)
    if diagnostics is not None:
        out["diagnostics"] = [[getattr(d, "code", None), getattr(d, "path", None)] for d in diagnostics]
        out["pm_roundings"] += [f"{code} {path}" for code, path in out["diagnostics"]
                                if code in ("I-PM-ROUNDING", "W-PM-ROUNDING")]
    return out


def record_document(doc_id: str, path: Path, out: Path, root: Path) -> dict:
    from simcase import Document, run
    from simcase.registry import kind_of
    folder = out / doc_id
    folder.mkdir(parents=True)
    RECORDER.reset()
    entry = {"format": RECORD_FORMAT, "id": doc_id, "document": {"sha256": _sha(path.read_bytes())}}
    try:
        doc = Document.load(path)
    except Exception as exc:
        entry["load"] = {"status": "error", "exception": [_qualname(exc), _scrub(str(exc), path, root, out)]}
        entry["calls"] = RECORDER.calls
        return entry
    data = getattr(doc, "data", {})
    entry["load"] = {"status": "ok", "kind": kind_of(data).name, "length_units": _length_units(data),
                     "physics_types": sorted({p.get("type") for p in (data.get("physics") or {}).values()
                                              if isinstance(p, dict)}),
                     **_diagnostics(doc)}
    try:
        result = run(doc, verbose=False)
    except Exception as exc:
        entry["run"] = {"status": "error", "exception": [_qualname(exc), _scrub(str(exc), path, root, out)]}
        try:
            from simcase.electric_joule import failure_evidence
            from galerkin.temperature_joule_heating import JouleConvergenceError
            if isinstance(exc, JouleConvergenceError):
                entry["run"]["failure_evidence"] = json.loads(json.dumps(failure_evidence(exc)))
        except ImportError:
            pass
    else:
        entry["run"] = {"status": "ok", "result_type": _qualname(result), "after": _diagnostics(doc)}
    entry["calls"] = RECORDER.calls
    entry["leaked_bindings"] = leaked_bindings()
    entry["transforms"] = RECORDER.finish()
    if entry["run"]["status"] == "ok":
        result_dir = folder / "result"
        try:
            result.save(result_dir)
        except Exception as exc:
            entry["save"] = {"status": "error", "exception": [_qualname(exc), _scrub(str(exc), path, root, out)]}
        else:
            entry["save"] = {"status": "ok", "files": _file_table(result_dir)}
            if (result_dir / "fields.npz").exists():
                entry["save"]["npz"] = _npz_table(result_dir / "fields.npz")
            entry["export"] = _export(result_dir, folder / "export", lambda t: _scrub(t, path, root, out))
    if RECORDER.mesher_outputs:
        import numpy as np
        arrays = {}
        for seq, tri in RECORDER.mesher_outputs:
            arrays[f"nodes_{seq}"] = np.asarray(tri.nodes)
            arrays[f"triangles_{seq}"] = np.asarray(tri.triangles)
        np.savez(folder / "mesher_outputs.npz", **arrays)
    return entry


def _git(root: Path, *args) -> str | None:
    try:
        done = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True,
                              encoding="utf-8", check=False)
    except OSError:
        return None
    return done.stdout.strip() if done.returncode == 0 else None


def _documents(items) -> list:
    docs, seen = [], set()
    for item in items:
        doc_id, sep, path = item.partition("=")
        if not sep:
            path, doc_id = item, Path(item).stem
        if doc_id in seen or not doc_id or any(c in doc_id for c in '/\\:'):
            raise SystemExit(f"document id {doc_id!r} is empty, repeated or not a plain name")
        seen.add(doc_id)
        docs.append((doc_id, Path(path).resolve()))
    return docs


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--root", type=Path, required=True, help="checkout whose packages/*/src are recorded")
    parser.add_argument("--out", type=Path, required=True, help="new or empty output directory")
    parser.add_argument("--docs", type=Path, help="a text file with one document (path or id=path) per line")
    parser.add_argument("--targets", type=Path, help="the recorded callables (format "
                        f"{TARGETS_FORMAT}); default: the root's {TARGETS_FILE}, else UNDECLARED_TARGETS")
    parser.add_argument("documents", nargs="*", help="documents to record: path or id=path")
    args = parser.parse_args(argv)
    root, out = args.root.resolve(), args.out.resolve()
    targets, source = load_targets(root, args.targets)
    items = list(args.documents)
    if args.docs:
        items += [line.strip() for line in args.docs.read_text(encoding="utf-8").splitlines()
                  if line.strip() and not line.lstrip().startswith("#")]
    documents = _documents(items)
    if not documents:
        parser.error("no documents given")
    if out.exists() and (not out.is_dir() or any(out.iterdir())):
        parser.error(f"{out} must be a new or empty directory")
    if out.is_relative_to(root):
        parser.error("the output directory must be outside the recorded tree")
    out.mkdir(parents=True, exist_ok=True)
    report = install(root, targets, source)
    import numpy, scipy
    versions = {"python": sys.version, "implementation": platform.python_implementation(),
                "platform": platform.platform(), "machine": platform.machine(), "numpy": numpy.__version__,
                "scipy": scipy.__version__}
    for name in ("shapely", "meshio", "matplotlib"):
        try:
            versions[name] = importlib.import_module(name).__version__
        except ImportError:
            versions[name] = None
    manifest = {"format": RECORD_FORMAT, "root_commit": _git(root, "rev-parse", "HEAD"),
                "root_dirty": bool(_git(root, "status", "--porcelain", "--untracked-files=no")),
                "isolated": bool(sys.flags.isolated), "hash_randomization": bool(sys.flags.hash_randomization),
                "threads": {k: os.environ.get(k) for k in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS",
                                                           "MKL_NUM_THREADS", "MPLBACKEND")},
                "versions": versions, "install": report, "documents": []}
    failures = 0
    for doc_id, path in documents:
        try:
            entry = record_document(doc_id, path, out, root)
        except Exception:
            failures += 1
            entry = {"format": RECORD_FORMAT, "id": doc_id, "recorder_error": traceback.format_exc()}
        (out / doc_id).mkdir(exist_ok=True)
        (out / doc_id / "record.json").write_text(dumps(entry) + "\n", encoding="utf-8")
        status = entry.get("run", entry.get("load", {})).get("status", "recorder-error")
        manifest["documents"].append({"id": doc_id, "source": path.name, "status": status,
                                      "calls": len(entry.get("calls", []))})
        print(f"{doc_id}: {status}, {len(entry.get('calls', []))} calls", flush=True)
    (out / "manifest.json").write_text(json.dumps(manifest, indent=1) + "\n", encoding="utf-8")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
