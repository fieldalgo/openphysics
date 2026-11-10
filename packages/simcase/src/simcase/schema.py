# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""The model document: everything a simulation needs, as plain data.

A document is a JSON object with these sections (lengths use its declared unit):

    units      the unit system the document's numbers are written in: one symbol
               per SI base dimension it needs, e.g. {"length": "um"}. There is no
               default. An absent dimension is SI, except where the physics
               requires it, and there absence is an error -- so a document in
               metres has to say so and cannot get metres by forgetting.
    openphysics     format version
    name       free text
    geometry   rectangular domain, a background material, and an ordered list
               of shapes (rect / circle / polygon). Later shapes cut earlier
               ones, the background fills whatever is left.
    materials  optional custom constants {"myglass": {"n": 1.5, "k": 0}}
               or Sellmeier models {"myglass": {"sellmeier": {"B": [...], "C": [...]}}};
               any other material name is looked up in physmat.
    physics    named physics, {"em1": {...}}. Each entry names its solver and
               its settings. Currently "em.modes2d": wavelength, formulation
               ("scalar" or "vector"), num_modes, boundary
               conditions per side ("pec" | "pmc"), and explicit n_cladding for
               vector modes. The names are how a study
               and (later) a coupling refer to one physics, so they are part of
               the document, not an implementation detail.
    mesh       global size, optional per-shape sizes (on the shape), optional
               radial grading {center, near, far, distance}, min_angle.
    study      {"type": "single"} or {"type": "sweep", "parameter": "physics.em1.wavelength", "values": [...]}
    results    {"save_fields": true, "plots": true}; optional "mode_overlap":
               {"gaussian": {"waist": w0, "center": [x, y]}} (document length unit)
               adds a Gaussian coupling efficiency to em.modes2d results

The same file drives a script, a command line run, and the optional studio: the GUI
is an editor for this document, nothing more.

Format 0.3 (``"openphysics": "0.3"``, docs/packages/simcase/document_format.md) is read
beside 0.2 by ``simcase.resolve``: values carry their units, keys are registry quantity names
and each geometry component declares its ``length_unit``. A document with that exact
envelope takes the 0.3 path; ``doc.data`` then holds the authored tree (exact ``Decimal``
numbers, never changed) and ``doc.si`` the resolved SI tree. No physics kind reads format
0.3 yet: each kind's document is refused with ``E-CONTRACT`` until its commit of the units
batch. Every other document takes the 0.2 path, unchanged.
"""

from __future__ import annotations

import copy
import json
import math
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from . import units
from .diagnostics import DiagnosticList, DocumentError
from .units import Scale, UnitError
from .mode_postprocessing import validate_mode_overlap
from .tracking import tracking_settings
from .registry import kind_of, physics_types

FORMAT = "0.2"
DEFAULT_PHYSICS = "em1"

#: base dimensions each physics needs a declared unit for
PHYSICS_REQUIRES = {"em.modes2d": {"length"}}

DEFAULTS: dict[str, Any] = {
    "openphysics": FORMAT,
    "name": "untitled",
    "geometry": {"domain": None, "background": {"material": "vacuum"}, "shapes": []},
    "materials": {},
    "physics": {DEFAULT_PHYSICS: {"type": "em.modes2d", "formulation": "scalar", "wavelength": 1.55,
                                  "num_modes": 1,
                                  "boundary": {"left": "pec", "right": "pec", "top": "pec",
                                               "bottom": "pec"}}},
    "mesh": {"size": 0.2, "min_angle": 28.0, "grading": None},
    "study": {"type": "single"},
    "results": {"save_fields": True, "plots": True},
}

SHAPE_TYPES = {"rect": {"x", "y", "w", "h"}, "circle": {"cx", "cy", "r"}, "polygon": {"points"}}
BOUNDARY_TYPES = {"pec", "pmc"}
FORMULATIONS = {"scalar", "vector"}


def steady_boundary_requested(data) -> bool:
    """New mappings opt into strict v2 by presence, including empty objects."""
    physics = data.get("physics") if isinstance(data, dict) else None
    return isinstance(physics, dict) and any(
        isinstance(p, dict) and p.get("type") == "thermal.steady2d"
        and ("outward_flux_w_m2" in p or "convection" in p)
        for p in physics.values())


def __getattr__(name: str):
    # Derived from the registry on access: the kinds register when their modules
    # import, and those modules import this one.
    if name == "PHYSICS_TYPES":
        return set(physics_types())
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def check_format_units_and_tags(doc: "Document") -> None:
    """The format version, the unit system and no tagged values: shared by most kinds."""
    d = doc.data
    if str(d.get("openphysics")) != FORMAT:
        raise DocumentError(f"unsupported openphysics format {d.get('openphysics')!r}; this reader handles {FORMAT}")
    try:
        doc.scale = units.resolve(d.get("units"))
    except UnitError as exc:
        raise DocumentError(str(exc)) from None
    geometry = d.get("geometry")
    if isinstance(geometry, dict) and "version" in geometry:
        # a version 1 block writes points as [x, y] with expressions; the reader checks it
        reject_tagged_values({k: v for k, v in d.items() if k != "geometry"})
    else:
        reject_tagged_values(d)


def reject_tagged_values(node, path: str = "") -> None:
    """``[value, "unit"]`` is reserved for a future tagged quantity, so refuse it now."""
    if isinstance(node, dict):
        for k, v in node.items():
            reject_tagged_values(v, f"{path}.{k}" if path else str(k))
    elif isinstance(node, list):
        if len(node) == 2 and isinstance(node[1], str) and isinstance(node[0], (int, float)):
            raise DocumentError(
                f"{path}: tagged quantities ([value, unit]) are reserved and not accepted in "
                f"openphysics {FORMAT}; write a bare number in the units the document declares")
        for i, v in enumerate(node):
            reject_tagged_values(v, f"{path}.{i}")


def _merge(defaults: dict, given: dict) -> dict:
    out = copy.deepcopy(defaults)
    for k, v in given.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = copy.deepcopy(v)
    return out


def _material_number(value, path: str) -> None:
    try:
        finite = isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)
    except OverflowError:
        finite = False
    if not finite:
        raise DocumentError(f"{path}: expected a finite number")


def _validate_material(spec, path: str) -> None:
    if not isinstance(spec, dict):
        raise DocumentError(f"{path}: custom material must be an object with n or sellmeier")
    if "source" in spec and not isinstance(spec["source"], str):
        raise DocumentError(f"{path}.source: expected a string")
    if "sellmeier" not in spec:
        if "n" not in spec:
            raise DocumentError(f"{path}: custom material needs n or sellmeier")
        for key in ("n", "k"):
            value = spec.get(key, 0.0)
            _material_number(value, f"{path}.{key}")
            if value < 0:
                raise DocumentError(f"{path}.{key}: must be non-negative")
        return
    if "n" in spec or "k" in spec:
        raise DocumentError(f"{path}: choose either n/k or sellmeier; mixing them would ignore n/k")
    path += ".sellmeier"
    model = spec["sellmeier"]
    if not isinstance(model, dict):
        raise DocumentError(f"{path}: expected an object with B and C arrays")
    if "range_um" in model:
        raise DocumentError(f"{path}.range_um: not supported; use range in the document's length unit")
    unknown = set(model) - {"B", "C", "A", "range"}
    if unknown:
        raise DocumentError(f"{path}: unknown keys {sorted(unknown)}")
    for key in ("B", "C"):
        values = model.get(key)
        if not isinstance(values, (list, tuple)) or not values:
            raise DocumentError(f"{path}.{key}: expected a non-empty array")
        for i, value in enumerate(values):
            _material_number(value, f"{path}.{key}[{i}]")
    if len(model["B"]) != len(model["C"]):
        raise DocumentError(f"{path}: B and C must have the same length")
    _material_number(model.get("A", 1.0), f"{path}.A")
    if "range" in model:
        bounds = model["range"]
        if not isinstance(bounds, (list, tuple)) or len(bounds) != 2:
            raise DocumentError(f"{path}.range: expected [minimum, maximum] in the document's length unit")
        for i, value in enumerate(bounds):
            _material_number(value, f"{path}.range[{i}]")
        if not 0 <= bounds[0] < bounds[1]:
            raise DocumentError(f"{path}.range: require 0 <= minimum < maximum")


@dataclass
class Document:
    data: dict[str, Any] = field(default_factory=lambda: copy.deepcopy(DEFAULTS))
    #: resolved by validate(); the document's numbers mean nothing without it
    scale: Scale = field(default=units.SI, init=False, repr=False)
    #: magnitude warnings from validate(); a scale error is not an invalid document
    notes: list[str] = field(default_factory=list, init=False, repr=False)
    #: the version 1 geometry block as written, when the document had one; ``data`` holds
    #: the same block for a 2D region component and its 0.2 compilation otherwise
    geometry_source: dict | None = field(default=None, init=False, repr=False)
    #: the length unit the version 1 block in ``data`` is written in when it differs from
    #: ``units.length``: set on the runner's micrometre copy, which then refuses to_dict()
    geometry_block_unit: str | None = field(default=None, init=False, repr=False)
    #: values the version 1 reader moved onto the 1 pm grid (simcase.geometry_document.Rounding)
    geometry_roundings: list = field(default_factory=list, init=False, repr=False)
    #: the parsed version 1 block (simcase.geometry_document.GeometryModel, integer pm); the
    #: mesh of such a document comes from the exact engine, not from the 0.2 compilation
    geometry_model: object = field(default=None, init=False, repr=False)
    #: the region complex the engine built when this document was meshed
    #: (simcase.geometry_engine.RegionComplex); set by geometry.build_domain
    geometry_complex: object = field(default=None, init=False, repr=False)
    #: format 0.3: the resolved SI tree (same keys as ``data``, without ``accept``); None for 0.2
    si: dict | None = field(default=None, init=False, repr=False, compare=False)
    #: every coded diagnostic, append-only (``simcase.diagnostics.DiagnosticList``)
    diagnostics: DiagnosticList = field(default_factory=DiagnosticList, init=False, repr=False, compare=False)
    #: format 0.3: ``[{"path", "value", "reason"}]`` of every default the reader applied
    defaults_applied: list = field(default_factory=list, init=False, repr=False, compare=False)
    #: the bytes the document was read from, when it came from a file or a text
    source_bytes: bytes | None = field(default=None, init=False, repr=False, compare=False)
    #: format 0.3: the flat form a homogeneous 2d or a box-only 3d version 1 component compiles to
    geometry_flat: dict | None = field(default=None, init=False, repr=False, compare=False)
    _resolution: object = field(default=None, init=False, repr=False, compare=False)

    # -- construction --------------------------------------------------------

    @classmethod
    def from_dict(cls, d: dict) -> "Document":
        if isinstance(d, dict) and _is_v03(d.get("openphysics")):
            from .resolve import resolve_tree
            return cls._accepted(resolve_tree(d))
        if not isinstance(d, dict):
            raise DocumentError('document: expected an object')
        source, roundings, model, complex_ = None, [], None, None
        geometry = d.get("geometry")
        if isinstance(geometry, dict) and "version" in geometry:
            # A version 1 geometry block (docs/packages/simcase/geometry_document.md) is read
            # exactly. A 2D region component stays in ``data`` as written: the validators
            # read it through the accessors (domain, background, regions) and the exact
            # engine meshes it (geometry.build_domain). A homogeneous rectangle or a box-only
            # 3D component is compiled to the 0.2 form its kind reads. The envelope stays 0.2.
            from .geometry_document import GeometryError, _pick, parse, to_v02
            try:
                model = parse(d)
                comp = _pick(model, None)
                homogeneous = not comp.features and "material" not in comp.background
                if comp.dimension == "3d" or homogeneous:
                    d = {**d, "geometry": to_v02(model, validation=True)}
                else:
                    d = {**d, "geometry": copy.deepcopy(geometry)}
            except GeometryError as exc:
                raise DocumentError(str(exc)) from None
            source, roundings = copy.deepcopy(geometry), model.roundings
        kind = kind_of(d)
        defaults = DEFAULTS if kind.defaults is None else kind.defaults()
        doc = cls(_merge(defaults, d))
        if model is not None and "version" in d["geometry"]:
            doc.data["geometry"] = d["geometry"]            # the kind's 0.2 geometry defaults do not apply
        doc.geometry_model = model
        doc.validate()
        doc.geometry_source, doc.geometry_roundings = source, list(roundings)
        doc.check_mesh_controls()
        if doc.is_version_1 and any(f.type == "segment" for f in doc.component.features):
            from .geometry_engine import check_handoff
            try:
                check_handoff(doc.complex())
            except GeometryError as exc:
                raise DocumentError(str(exc)) from None
        doc.notes.extend(f"{r.path}: {r.written} moved {float(r.displacement_pm):.3g} pm onto the 1 pm grid"
                         for r in roundings)
        return doc

    @classmethod
    def load(cls, path: str | Path) -> "Document":
        raw = Path(path).read_bytes()
        if declares_v03(raw):
            from .resolve import resolve_text
            return cls._accepted(resolve_text(raw))
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))

    @classmethod
    def loads(cls, text: str | bytes) -> "Document":
        """A document from its JSON text (str or bytes)."""
        if declares_v03(text):
            from .resolve import resolve_text
            return cls._accepted(resolve_text(text))
        return cls.from_dict(json.loads(text))

    @classmethod
    def _accepted(cls, result) -> "Document":
        doc = result.document()
        if doc is None:
            raise DocumentError("the document is refused", diagnostics=list(result.diagnostics))
        return doc

    @classmethod
    def _from_resolution(cls, result) -> "Document":
        """The format 0.3 document of a resolution (``simcase.resolve``), before its kind validates it."""
        doc = cls(result.tree)
        doc.si = result.si
        doc.diagnostics = result.diagnostics
        doc.defaults_applied = result.defaults_applied
        doc.source_bytes = result.source_bytes
        doc.geometry_model = result.geometry_model
        doc.geometry_flat = result.geometry_flat
        doc._resolution = result
        if result.geometry_model is not None:
            doc.geometry_source = copy.deepcopy(result.tree["geometry"])
        return doc

    # -- format 0.3 ----------------------------------------------------------

    @property
    def format(self) -> str:
        """``"0.3"`` for a document read by the format 0.3 reader, else ``"0.2"``."""
        return "0.2" if self.si is None else "0.3"

    def canonical_json(self, separators=(",", ":")) -> str:
        """The authored tree as sorted, decimal-preserving JSON (``reader.dumps``); for a 0.2 tree
        of floats the same bytes as ``json.dumps(data, sort_keys=True, ...)``."""
        from .reader import dumps
        return dumps(self.data, sort_keys=True, separators=separators, allow_nan=False)

    def _need_v03(self, what: str):
        if self._resolution is None:
            raise DocumentError(f"{what} is defined for format 0.3 documents only")
        return self._resolution

    def exact(self, path: str):
        """The exact SI value (a Fraction, or a list of them) of a tagged value or shape number, or None."""
        return self._need_v03("exact()").exact.get(path)

    def pm(self, path: str) -> int:
        """The picometre count of a shape number."""
        return self._need_v03("pm()").pm[path]

    def um(self, path: str):
        """The micrometre double of a length, from its exact value (hazard H2): never si / 1e-6."""
        from fractions import Fraction
        exact = self.exact(path)
        if exact is None:
            raise KeyError(path)
        if isinstance(exact, list):
            return [None if e is None else float(Fraction(e) * 10 ** 6) for e in exact]
        return float(Fraction(exact) * 10 ** 6)

    def degrees(self, path: str) -> float:
        """The angle number meshine takes (hazard H3): the authored number when written in deg,
        else math.degrees of the SI value."""
        from fractions import Fraction
        c = self._need_v03("degrees()").conversions[path]
        if c.unit_text == "deg":
            return float(Fraction(c.number_text))
        return math.degrees(c.value)

    def authored(self, path: str):
        """The authored token (a string or a number) of a value."""
        return self._need_v03("authored()").authored.get(path)

    def resolved_inputs(self) -> dict:
        """``{path: {"authored", "value", "unit"[, "length_unit"]}}`` of every authored input slot."""
        return copy.deepcopy(self._need_v03("resolved_inputs()").inputs)

    def extent_lines(self) -> list[str]:
        """One line per geometry component: what its numbers mean (``simcase.checks``)."""
        return list(self._need_v03("extent_lines()").extent)

    def spelling_fixes(self) -> list[dict]:
        """``[{"path", "written", "fix"}]``: value-preserving respellings (character aliases)."""
        return copy.deepcopy(self._need_v03("spelling_fixes()").spelling_fixes)

    def with_value(self, path: str, si, exact=None) -> "Document":
        """A copy with one resolved value replaced (a sweep point); the authored tree is unchanged."""
        from .reader import split_path
        from .resolve import _assign
        other = self.copy()
        _assign(other.si, split_path(path), si)
        if other._resolution is not None and exact is not None:
            other._resolution = copy.copy(other._resolution)
            other._resolution.exact = {**other._resolution.exact, path: exact}
        return other

    def to_dict(self) -> dict:
        """The document as written: a version 1 geometry block comes back unchanged.

        The micrometre copy a runner meshes (``runner.micrometre_document``) keeps a version
        1 block in the original unit while its ``units.length`` says micrometres, so it
        refuses; serialise the original document, as the results do."""
        unit = self.geometry_block_unit
        if unit is not None and unit != self.data.get("units", {}).get("length"):
            raise DocumentError(f"this is the runner's micrometre copy: its geometry block is written in {unit!r} "
                                "while units.length is micrometres; serialise the original document")
        data = copy.deepcopy(self.data)
        if self.geometry_source is not None:
            data["geometry"] = copy.deepcopy(self.geometry_source)
        return data

    def save(self, path: str | Path) -> None:
        if self.si is not None:
            from .reader import dumps
            data = self.source_bytes if self.source_bytes is not None else \
                (dumps(self.data, indent=2) + "\n").encode("utf-8")
            Path(path).write_bytes(data)
            return
        Path(path).write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")

    def copy(self) -> "Document":
        other = Document(copy.deepcopy(self.data))
        other.geometry_block_unit = self.geometry_block_unit
        other.geometry_source = copy.deepcopy(self.geometry_source)
        other.geometry_roundings = list(self.geometry_roundings)
        other.geometry_model = self.geometry_model
        other.geometry_complex = self.geometry_complex
        if self.si is not None:
            other.scale = self.scale
            other.si = copy.deepcopy(self.si)
            other.diagnostics = self.diagnostics.copy()
            other.defaults_applied = copy.deepcopy(self.defaults_applied)
            other.source_bytes = self.source_bytes
            other.geometry_flat = copy.deepcopy(self.geometry_flat)
            other._resolution = self._resolution
        return other

    # -- access --------------------------------------------------------------

    def __getitem__(self, key: str):
        return self.data[key]

    def get_path(self, dotted: str):
        node = self.data
        for part in dotted.split("."):
            node = node[part]
        return node

    def set_path(self, dotted: str, value) -> None:
        parts = dotted.split(".")
        node = self.data
        for part in parts[:-1]:
            node = node[part]
        node[parts[-1]] = value

    @property
    def is_version_1(self) -> bool:
        """``data['geometry']`` is a version 1 block (a 2D region component kept as written)."""
        if self.si is not None:
            return self.geometry_model is not None and self.geometry_flat is None
        return self.geometry_model is not None and "version" in self.data["geometry"]

    @property
    def component(self):
        """The one component of a version 1 geometry block (``geometry_document.Component``)."""
        from .geometry_document import _pick
        return _pick(self.geometry_model, None)

    def complex(self):
        """The region complex of a version 1 document, evaluated once and kept."""
        if self.geometry_complex is None:
            from .geometry_engine import evaluate
            self.geometry_complex = evaluate(self.geometry_model)
        return self.geometry_complex

    def _pm_per_unit(self):
        from .geometry_document import pm_per_unit
        return pm_per_unit(self.data.get("units"))

    def _length(self, k) -> float:
        """An integer pm count of the model in this document's length unit, rounded once."""
        from fractions import Fraction
        return float(Fraction(k) / self._pm_per_unit())

    @property
    def shapes(self) -> list[dict]:
        if self.is_version_1:
            raise DocumentError("a version 1 geometry block has features, not shapes; read regions()")
        return self.data["geometry"]["shapes"]

    @property
    def domain(self) -> dict:
        """The domain bounds in the document's length unit, whatever block form it holds."""
        if self.is_version_1:
            return {k: self._length(v) for k, v in self.component.domain.items()}
        return self.data["geometry"]["domain"]

    @property
    def background(self) -> dict:
        """``{"material": ..., "mesh_size": ...}`` of the background; keys only when given."""
        if self.is_version_1:
            bg = self.component.background
            out = {}
            if "material" in bg:
                out["material"] = bg["material"]
            if "mesh_size" in bg:
                out["mesh_size"] = self._length(bg["mesh_size"])
            return out
        return self.data["geometry"]["background"]

    def regions(self) -> list[dict]:
        """One entry per declared region, in order: ``{"name", "material", "mesh_size", "type"}``.

        A 0.2 block gives its shapes. A version 1 block gives its area features grouped by
        ``region`` (merged features share one entry with the smallest mesh_size); ``type``
        is the feature type, or ``"region"`` for a merge; ``material`` is None for void.
        """
        if not self.is_version_1:
            return [{"name": s["name"], "material": s["material"], "mesh_size": s.get("mesh_size"), "type": s["type"]}
                    for s in self.data["geometry"]["shapes"]]
        out: dict[str, dict] = {}
        for f in self.component.features:
            if f.type in ("segment", "layers"):
                continue
            size = None if f.mesh_size is None else self._length(f.mesh_size)
            entry = out.get(f.region)
            if entry is None:
                out[f.region] = {"name": f.region, "material": f.material, "mesh_size": size, "type": f.type}
            else:
                entry["type"] = "region"
                if size is not None and (entry["mesh_size"] is None or size < entry["mesh_size"]):
                    entry["mesh_size"] = size
        return list(out.values())

    @property
    def length_unit(self) -> str:
        """Display the declared unit without rescaling any document values."""
        declaration = self.data["units"]["length"]
        return declaration if isinstance(declaration, str) else f"{declaration['in_m']} m"

    def sole_physics(self) -> tuple[str, dict]:
        """The (name, settings) of the one physics, for the paths that assume one."""
        items = list(self.data["physics"].items())
        if len(items) != 1:
            raise DocumentError(
                f"this document declares {len(items)} physics ({', '.join(n for n, _ in items)}); "
                "solving more than one, and coupling them, is not implemented yet")
        return items[0]

    # -- validation ----------------------------------------------------------

    def validate(self) -> None:
        """The contract of the document's physics kind (``registry``).

        A format 0.3 document keeps its diagnostics: validating it again appends only what is
        new, so a runner that re-validates neither loses nor doubles an entry."""
        if self.si is None:
            kind_of(self.data).validate(self)
            return
        kept, self.diagnostics = self.diagnostics, DiagnosticList()
        try:
            kind_of(self.data).validate(self)
        finally:
            fresh, self.diagnostics = self.diagnostics, kept
            seen = {(d.code, d.path, d.message) for d in kept}
            kept.extend(d for d in fresh if (d.code, d.path, d.message) not in seen)

    def mesh_controls(self) -> list[dict]:
        """The contract's ``mesh.controls`` entries, as written (``[]`` when absent)."""
        controls = self.data.get("mesh", {}).get("controls")
        return [] if controls is None else controls

    def check_mesh_controls(self) -> None:
        """Refuse a malformed ``mesh.controls`` list, or one whose targets the component lacks.

        An entry is ``{"select": <name or selector>, <one control>}`` with the control
        ``circle_segments`` (an integer, at least 8: meshine's floor), ``size`` (a positive
        length in the document's unit, on a region selection) or the distance grading
        ``near``, ``far``, ``distance`` (three positive lengths: ``near`` on the selection,
        growing linearly to ``far`` at ``distance`` from it). The contract's ``z_divisions``
        is not implemented yet and is refused by name, as is any list on a 0.2 geometry
        block, which has no selections.
        """
        controls = self.mesh_controls()
        if not controls:
            return
        if not isinstance(controls, list):
            raise DocumentError("mesh.controls: expected a list of objects")
        if not self.is_version_1:
            raise DocumentError("mesh.controls needs a version 1 geometry block with a 2D region component; "
                                "a 0.2 geometry block has no selections to control")
        from .geometry_document import GeometryError
        for i, entry in enumerate(controls):
            where = f"mesh.controls[{i}]"
            if not isinstance(entry, dict) or "select" not in entry:
                raise DocumentError(f"{where}: expected an object with 'select' and one control")
            grading = {"near", "far", "distance"}
            keys = set(entry) - {"select"}
            if "z_divisions" in keys:
                raise DocumentError(f"{where}: z_divisions is not implemented yet; circle_segments, size and the "
                                    "distance grading (near, far, distance) are")
            if keys & grading:
                if keys != grading:
                    raise DocumentError(f"{where}: a distance grading needs near, far and distance together, "
                                        f"got {sorted(keys)}")
                for k in sorted(grading):
                    v = entry[k]
                    if type(v) not in (int, float) or not math.isfinite(v) or v <= 0:
                        raise DocumentError(f"{where}.{k}: expected a positive length in units.length")
            elif len(keys) != 1 or not keys <= {"circle_segments", "size"}:
                raise DocumentError(f"{where}: expected circle_segments, size, or near+far+distance, "
                                    f"got {sorted(keys)}")
            if "circle_segments" in entry:
                n = entry["circle_segments"]
                if type(n) is not int or n < 8:
                    raise DocumentError(f"{where}.circle_segments: expected an integer of at least 8")
            elif "size" in entry:
                h = entry["size"]
                if type(h) not in (int, float) or not math.isfinite(h) or h <= 0:
                    raise DocumentError(f"{where}.size: expected a positive length in units.length")
            try:
                kind, _chosen = self.complex().select(entry["select"])
            except GeometryError as exc:
                raise DocumentError(f"{where}: {exc}") from None
            if "size" in entry and kind != "region":
                raise DocumentError(f"{where}: select {entry['select']!r} is a boundary selection; a size on a "
                                    "boundary is not implemented yet (give the size to a region)")

    def controls_pm(self) -> list[dict]:
        """``mesh_controls()`` with each ``size`` as an integer pm count, for the engine hand-off.

        The entries are checked first (``check_mesh_controls``), so a document built without
        ``from_dict`` is refused by name here rather than failing inside the engine. A format
        0.3 document's controls are rounded to pm from their exact values, under the engine's
        names (``size``, ``near``, ``far``, ``distance``, ``circle_segments``)."""
        from fractions import Fraction
        if self.si is not None:
            names = {"element_size": "size", "near": "near", "far": "far", "refinement_distance": "distance"}
            out = []
            for i, entry in enumerate(self.si.get("mesh", {}).get("controls") or []):
                where = f"mesh.controls[{i}]"
                item = {"select": entry["select"]}
                for key, engine in names.items():
                    if key in entry:
                        item[engine] = int(round(Fraction(self.exact(f"{where}.{key}")) * 10 ** 12))
                if "circle_segment_count" in entry:
                    item["circle_segments"] = int(entry["circle_segment_count"])
                out.append(item)
            return out
        self.check_mesh_controls()
        unit_pm = self._pm_per_unit()
        out = []
        for entry in self.mesh_controls():
            entry = {**entry, **{k: int(round(Fraction(entry[k]) * unit_pm))
                                 for k in ("size", "near", "far", "distance") if k in entry}}
            out.append(entry)
        return out

    def validate_em_modes2d(self) -> None:
        """The ``em.modes2d`` contract; also reports a document no kind claims."""
        d = self.data
        check_format_units_and_tags(self)
        g = d["geometry"]
        if self.is_version_1 and self.component.dimension == "axisymmetric":
            raise DocumentError(f"component {self.component.name!r}: em.modes2d takes 2d components only; an "
                                "axisymmetric component is a body of revolution, which this waveguide physics "
                                "does not describe (steady region heat takes it)")
        dom = g.get("domain") if not self.is_version_1 else self.domain
        if not dom or any(k not in dom for k in ("xmin", "xmax", "ymin", "ymax")):
            raise DocumentError("geometry.domain needs xmin, xmax, ymin, ymax")
        if not (dom["xmin"] < dom["xmax"] and dom["ymin"] < dom["ymax"]):
            raise DocumentError("geometry.domain is empty")
        validate_mode_overlap(d["results"], dom, DocumentError)
        names = set()
        for i, s in enumerate([] if self.is_version_1 else g["shapes"]):
            t = s.get("type")
            if t not in SHAPE_TYPES:
                raise DocumentError(f"shape {i}: unknown type {t!r} (rect, circle, polygon)")
            missing = SHAPE_TYPES[t] - set(s)
            if missing:
                raise DocumentError(f"shape {i} ({t}): missing {sorted(missing)}")
            if "name" not in s or "material" not in s:
                raise DocumentError(f"shape {i}: needs 'name' and 'material'")
            if s["name"] in names or s["name"] == "background":
                raise DocumentError(f"shape name {s['name']!r} is duplicated or reserved")
            names.add(s["name"])
            if t == "rect" and (s["w"] <= 0 or s["h"] <= 0):
                raise DocumentError(f"shape {s['name']}: w and h must be positive")
            if t == "circle" and s["r"] <= 0:
                raise DocumentError(f"shape {s['name']}: r must be positive")
            if t == "polygon" and len(s["points"]) < 3:
                raise DocumentError(f"shape {s['name']}: polygon needs >= 3 points")
        if "material" not in self.background:
            raise DocumentError("geometry.background needs a material")
        if not isinstance(d["materials"], dict):
            raise DocumentError("materials must be an object mapping names to material definitions")
        for name, spec in d["materials"].items():
            _validate_material(spec, f"materials.{name}")
        if not isinstance(d["physics"], dict) or not d["physics"]:
            raise DocumentError("physics must be a non-empty map of name -> settings, e.g. {'em1': {...}}")
        for pname, p in d["physics"].items():
            if not (isinstance(pname, str) and pname.isidentifier()):
                raise DocumentError(f"physics name {pname!r} must be an identifier: a study or a coupling "
                                    "refers to a physics by this name")
            where = f"physics.{pname}"
            if not isinstance(p, dict):
                raise DocumentError(f"{where} must be a settings map; physics is keyed by name since 0.2, "
                                    "so a setting now lives at physics.<name>.<setting>")
            if p.get("type") not in physics_types():
                raise DocumentError(f"{where}.type {p.get('type')!r} not supported ({sorted(physics_types())})")
            if p["formulation"] not in FORMULATIONS:
                raise DocumentError(f"{where}.formulation must be one of {sorted(FORMULATIONS)}")
            if "n_target" in p:
                _material_number(p["n_target"], f"{where}.n_target")
                if p["n_target"] <= 0:
                    raise DocumentError(f"{where}.n_target must be positive")
            for side in ("left", "right", "top", "bottom"):
                if p["boundary"].get(side) not in BOUNDARY_TYPES:
                    raise DocumentError(f"{where}.boundary.{side} must be one of {sorted(BOUNDARY_TYPES)}")
            if not (isinstance(p["wavelength"], (int, float)) and p["wavelength"] > 0):
                raise DocumentError(f"{where}.wavelength must be a positive number (use study.sweep for several)")
            from .pml_contract import validate as validate_pml
            validate_pml(p, dom, where, DocumentError)
            if p["formulation"] == "vector":
                for key in ("wavelength", "n_cladding", "num_modes"):
                    value = p.get(key)
                    _material_number(value, f"{where}.{key}")
                    if value <= 0:
                        raise DocumentError(f"{where}.{key} must be positive")
                if p["num_modes"] != int(p["num_modes"]):
                    raise DocumentError(f"{where}.num_modes must be an integer")
            elif int(p["num_modes"]) < 1:
                raise DocumentError(f"{where}.num_modes must be >= 1")
        required = set()
        for p in d["physics"].values():
            required |= PHYSICS_REQUIRES.get(p["type"], set())
        missing = sorted(required - self.scale.declared)
        if missing:
            raise DocumentError(
                f"units is missing {missing}, which the physics in this document needs. "
                f"An absent dimension means SI, and that is not assumed where it matters: say "
                f"what the numbers are in, e.g. \"units\": {{\"length\": \"um\"}}.")
        self.notes = []
        for pname, p in d["physics"].items():
            note = units.implausible("wavelength", self.scale.to_si(p["wavelength"], {"length": 1}))
            if note:
                self.notes.append(f"physics.{pname}.wavelength: {note}")

        m = d["mesh"]
        if m["size"] <= 0:
            raise DocumentError("mesh.size must be positive")
        if m.get("grading"):
            gr = m["grading"]
            for k in ("center", "near", "far", "distance"):
                if k not in gr:
                    raise DocumentError(f"mesh.grading needs {k}")
        st = d["study"]
        if st["type"] not in ("single", "sweep"):
            raise DocumentError("study.type must be 'single' or 'sweep'")
        if st["type"] == "sweep":
            if (not isinstance(st.get("parameter"), str) or
                    not isinstance(st.get("values"), list) or not st["values"]):
                raise DocumentError("study.sweep needs 'parameter' (dotted path) and non-empty 'values'")
            try:
                self.get_path(st["parameter"])
            except (KeyError, TypeError):
                raise DocumentError(f"study.parameter {st['parameter']!r} does not exist in the document") from None
            if not st["parameter"].startswith("physics."):
                raise DocumentError(
                    f"study.parameter {st['parameter']!r} is not under 'physics.'. The mesh is built once for "
                    "the whole study, so sweeping geometry, mesh or materials would solve every point on the "
                    "first point's mesh. Only physics parameters may be swept.")
            open_names = [name for name, p in d["physics"].items() if "pml" in p]
            if open_names and (len(d["physics"]) != 1 or st["parameter"] != f"physics.{open_names[0]}.wavelength"):
                raise DocumentError("PML sweeps support only wavelength with fixed geometry and coordinates")
            vector_names = [name for name, p in d["physics"].items() if p["formulation"] == "vector"]
            if vector_names:
                if len(d["physics"]) != 1 or st["parameter"] != f"physics.{vector_names[0]}.wavelength":
                    raise DocumentError("vector sweeps support only the wavelength of one fixed physics entry")
                if len(st["values"]) < 3:
                    raise DocumentError("vector wavelength sweeps need at least 3 values for group index")
                for i, value in enumerate(st["values"]):
                    _material_number(value, f"study.values[{i}]")
                    if value <= 0:
                        raise DocumentError("vector sweep wavelengths must be positive")
                pairs = list(zip(st["values"], st["values"][1:]))
                if not (all(a < b for a, b in pairs) or all(a > b for a, b in pairs)):
                    raise DocumentError("vector sweep wavelengths must be strictly monotone (no duplicates)")
                try:
                    tracking_settings(int(d["physics"][vector_names[0]]["num_modes"]), st.get("tracking"))
                except (ValueError, OverflowError) as exc:
                    raise DocumentError(str(exc)) from None
                return
            if "tracking" in st:
                raise DocumentError("study.tracking is only supported for vector wavelength sweeps")
            for value in st["values"]:
                candidate = self.copy()
                candidate.set_path(st["parameter"], value)
                if any(isinstance(p, dict) and p.get("formulation") == "vector"
                       for p in candidate["physics"].values()):
                    raise DocumentError("a scalar sweep cannot switch to vector; use a vector wavelength sweep")

    def summary(self) -> str:
        return kind_of(self.data).summary(self)


    def em_modes2d_summary(self) -> str:
        p, m, st = self.data["physics"], self.data["mesh"], self.data["study"]
        dom, bg = self.domain, self.background
        length = self.length_unit
        lines = [f"{self.data['name']}  (openphysics {FORMAT})",
                 f"  domain x [{dom['xmin']}, {dom['xmax']}]  y [{dom['ymin']}, {dom['ymax']}] {length}",
                 f"  background: {bg.get('material')}"]
        for s in self.regions():
            lines.append(f"  shape {s['name']}: {s['type']} of {s['material']}" +
                         (f", mesh {s['mesh_size']} {length}" if s["mesh_size"] is not None else ""))
        for pname, ph in p.items():
            lines.append(f"  physics {pname}: {ph['type']} {ph['formulation']}, lambda {ph['wavelength']} {length}, "
                         f"{ph['num_modes']} mode(s), boundary {ph['boundary']}")
        lines.append(f"  mesh: size {m['size']} {length}" + (f", grading {m['grading']} ({length})" if m.get("grading") else ""))
        lines.append(f"  study: {st['type']}" + (f" over {st['parameter']} x{len(st['values'])}" if st["type"] == "sweep" else ""))
        return "\n".join(lines)


def _is_v03(value) -> bool:
    return isinstance(value, str) and value == "0.3"


_V03_TEXT = re.compile(r'"openphysics"\s*:\s*"0\.3"')


def declares_v03(raw) -> bool:
    """True for a document text whose envelope is the format 0.3 string, read exactly; for text
    that is not readable JSON, when the text holds that envelope (the 0.3 reader then reports
    why it cannot read it). Every other text takes the 0.2 path, unchanged."""
    from .reader import parse
    tree, _found = parse(raw)
    if isinstance(tree, dict):
        return _is_v03(tree.get("openphysics"))
    if tree is not None:
        return False
    if isinstance(raw, (bytes, bytearray, memoryview)):
        raw = bytes(raw).decode("utf-8", "replace")
    return isinstance(raw, str) and _V03_TEXT.search(raw) is not None
