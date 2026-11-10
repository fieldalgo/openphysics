# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""The model document: everything a simulation needs, as plain data.

A document is a JSON object in format 0.3 (``"openphysics": "0.3"``,
docs/packages/simcase/document_format.md): values carry their units (``"1.55 um"``), keys are
registry quantity names, and the geometry block (flat, or version 1 with its components)
declares its ``length_unit``. ``simcase.resolve`` reads it: ``doc.data`` holds the authored tree
(exact ``Decimal`` numbers, never changed) and ``doc.si`` the resolved SI tree, with the exact
value of every tagged length and the picometre count of every shape number. Each physics kind
checks its own document (``registry``). A document object of another format is refused by name
(``E-FORMAT`` at ``openphysics``, ``not_read``).

The same file drives a script, a command line run, and the optional studio: the GUI
is an editor for this document, nothing more.
"""

from __future__ import annotations

import copy
import json
import math
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .diagnostics import DiagnosticList, DocumentError
from .registry import kind_of, physics_types

#: the document format this release reads (``resolve.FORMAT``); another is refused by name
FORMAT = "0.3"


def steady_boundary_requested(data) -> bool:
    """New mappings opt into strict v2 by presence, including empty objects."""
    physics = data.get("physics") if isinstance(data, dict) else None
    return isinstance(physics, dict) and any(
        isinstance(p, dict) and p.get("type") == "thermal.steady2d"
        and ("outward_flux_w_m2" in p or "convection" in p)
        for p in physics.values())


def not_read(d: dict) -> DocumentError:
    """The refusal of a document object that is not format 0.3: ``E-FORMAT`` at ``openphysics``
    (the format 0.2 reader is retired, units batch C11a). A format 0.2 document (``"0.2"`` or the
    number) of a type a kind claims gets that kind's conversion hint, which names its renamed keys;
    any other envelope, or a 0.2 document no kind claims, gets the reader's
    (``resolve.format_refusal``). Nothing is merged with defaults: a kind's validator, given the
    document as written, refuses it by name before reading anything else."""
    from .resolve import format_refusal
    fmt = d.get("openphysics")
    if str(fmt) == "0.2" and not isinstance(fmt, bool):            # "0.2", or the number (float or Decimal)
        kind = kind_of(d)
        physics = d.get("physics") if isinstance(d.get("physics"), dict) else {}
        if any(isinstance(p, dict) and p.get("type") in kind.types for p in physics.values()):
            try:
                kind.validate(Document(copy.deepcopy(d)))    # each kind refuses a 0.2 document by name
            except DocumentError as exc:
                if exc.code == "E-FORMAT":
                    return exc
    refusal = format_refusal(d)
    return DocumentError(refusal.message, path=refusal.path, code=refusal.code)


def __getattr__(name: str):
    # Derived from the registry on access: the kinds register when their modules
    # import, and those modules import this one.
    if name == "PHYSICS_TYPES":
        return set(physics_types())
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


@dataclass
class Document:
    data: dict[str, Any] = field(default_factory=dict)
    #: the mesher's findings on a region view or a micrometre frame (``geometry.build_domain``),
    #: which the runners turn into coded diagnostics; a format 0.3 document reports its own in
    #: ``diagnostics``
    notes: list[str] = field(default_factory=list, init=False, repr=False)
    #: the version 1 geometry block as written, when the document had one
    geometry_source: dict | None = field(default=None, init=False, repr=False)
    #: values the version 1 reader moved onto the 1 pm grid (simcase.geometry_document.Rounding)
    geometry_roundings: list = field(default_factory=list, init=False, repr=False)
    #: the parsed version 1 block (simcase.geometry_document.GeometryModel, integer pm); the
    #: mesh of such a document comes from the exact engine, not from its flat compilation
    geometry_model: object = field(default=None, init=False, repr=False)
    #: the region complex the engine built when this document was meshed
    #: (simcase.geometry_engine.RegionComplex); set by geometry.build_domain
    geometry_complex: object = field(default=None, init=False, repr=False)
    #: format 0.3: the resolved SI tree (same keys as ``data``, without ``accept``); None when not read
    si: dict | None = field(default=None, init=False, repr=False, compare=False)
    #: format 0.3: every coded diagnostic, append-only (the ``diagnostics`` property)
    _diagnostics: DiagnosticList | None = field(default=None, init=False, repr=False, compare=False)
    #: format 0.3: ``[{"path", "value", "reason"}]`` of every default the reader applied
    defaults_applied: list = field(default_factory=list, init=False, repr=False, compare=False)
    #: the bytes the document was read from, when it came from a file or a text
    source_bytes: bytes | None = field(default=None, init=False, repr=False, compare=False)
    #: format 0.3: the flat form a homogeneous 2d or a box-only 3d version 1 component compiles to
    geometry_flat: dict | None = field(default=None, init=False, repr=False, compare=False)
    _resolution: object = field(default=None, init=False, repr=False, compare=False)
    #: format 0.3: the canonical JSON of ``data`` when it was read; a changed tree is read again
    _read_json: str | None = field(default=None, init=False, repr=False, compare=False)

    # -- construction --------------------------------------------------------

    @classmethod
    def from_dict(cls, d: dict) -> "Document":
        if isinstance(d, dict) and _is_v03(d.get("openphysics")):
            from .resolve import resolve_tree
            return cls._accepted(resolve_tree(d))
        if not isinstance(d, dict):
            raise DocumentError('document: expected an object')
        raise not_read(d)

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
        doc._read_json = doc.canonical_json()
        return doc

    def _read_again(self, refusal="the document was changed after it was read and is now refused") -> None:
        """A format 0.3 document whose authored tree was changed after it was read (by a caller;
        simcase never changes ``data``), or that was constructed without reading: read it (again),
        so that ``validate`` checks what it holds now. Refused with the reader's diagnostics;
        otherwise the SI tree follows the new values."""
        from .resolve import resolve_tree
        again = resolve_tree(copy.deepcopy(self.data))
        fresh = again.document()
        if fresh is None:
            raise DocumentError(refusal, diagnostics=list(again.diagnostics))
        seen = {(d.code, d.path, d.message) for d in self.diagnostics}
        self.diagnostics.extend(d for d in fresh.diagnostics if (d.code, d.path, d.message) not in seen)
        self.si, self.defaults_applied, self._resolution = fresh.si, fresh.defaults_applied, fresh._resolution
        self.geometry_model, self.geometry_flat, self.source_bytes = fresh.geometry_model, fresh.geometry_flat, None
        self._read_json = self.canonical_json()

    # -- format 0.3 ----------------------------------------------------------

    @property
    def diagnostics(self) -> DiagnosticList:
        """Every coded diagnostic of a format 0.3 document, append-only
        (``simcase.diagnostics.DiagnosticList``). A document object that was not read (a kernel
        hand-off, or ``Document(data)`` before ``validate()``) has none."""
        if self._diagnostics is None:
            raise AttributeError("a document that was not read has no coded diagnostics")
        return self._diagnostics

    @diagnostics.setter
    def diagnostics(self, value: DiagnosticList) -> None:
        self._diagnostics = value

    @property
    def format(self) -> str:
        """``"0.3"`` for a document read by the format 0.3 reader, else None (not read)."""
        return None if self.si is None else "0.3"

    def canonical_json(self, separators=(",", ":")) -> str:
        """The authored tree as sorted, decimal-preserving JSON (``reader.dumps``); for a tree of
        Python floats the same bytes as ``json.dumps(data, sort_keys=True, ...)``."""
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
        """The document as written: a version 1 geometry block comes back unchanged."""
        if getattr(self, "is_handoff", False):
            raise DocumentError("this is a kernel hand-off (a region view or a micrometre frame), which is never "
                                "written; serialise the original document")
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
        other.geometry_source = copy.deepcopy(self.geometry_source)
        other.geometry_roundings = list(self.geometry_roundings)
        other.geometry_model = self.geometry_model
        other.geometry_complex = self.geometry_complex
        if self.si is not None:
            other.si = copy.deepcopy(self.si)
            other.diagnostics = self.diagnostics.copy()
            other.defaults_applied = copy.deepcopy(self.defaults_applied)
            other.source_bytes = self.source_bytes
            other.geometry_flat = copy.deepcopy(self.geometry_flat)
            other._resolution = self._resolution
            other._read_json = self._read_json
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
        """Grid points per length unit of the version 1 component (its ``length_unit``), exactly."""
        return self.component.pm_per_unit

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

        A flat block gives its shapes. A version 1 block gives its area features grouped by
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
        """The geometry's ``length_unit``: the flat block's, or the version 1 component's."""
        if self.is_version_1:
            return self.component.length_unit
        return self.data["geometry"]["length_unit"]

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
        if self.si is None and isinstance(self.data, dict) and _is_v03(self.data.get("openphysics")):
            # ``Document(data)`` of a format 0.3 tree: read it now, as ``from_dict`` would
            self._diagnostics = DiagnosticList()
            self._read_again("the document is refused")
        if self.si is None:
            kind_of(self.data).validate(self)
            return
        if self._read_json is not None:
            try:
                changed = self.canonical_json() != self._read_json
            except (TypeError, ValueError):          # a value JSON cannot hold (NaN, an object)
                changed = True
            if changed:
                self._read_again()
        kept, self.diagnostics = self.diagnostics, DiagnosticList()
        try:
            kind_of(self.data).validate(self)
        finally:
            fresh, self.diagnostics = self.diagnostics, kept
            seen = {(d.code, d.path, d.message) for d in kept}
            kept.extend(d for d in fresh if (d.code, d.path, d.message) not in seen)

    def controls_pm(self) -> list[dict]:
        """The ``mesh.controls`` entries with each length as an integer pm count, rounded from its
        exact value, under the engine's names (``size``, ``near``, ``far``, ``distance``,
        ``circle_segments``), for the engine hand-off."""
        from fractions import Fraction
        self._need_v03("controls_pm()")
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

    def summary(self) -> str:
        return kind_of(self.data).summary(self)


def _is_v03(value) -> bool:
    return isinstance(value, str) and value == "0.3"


_V03_TEXT = re.compile(r'"openphysics"\s*:\s*"0\.3"')


def declares_v03(raw) -> bool:
    """True for a document text whose envelope is the format 0.3 string, read exactly; for text
    that is not readable JSON, when the text holds that envelope (the 0.3 reader then reports
    why it cannot read it). Every other text is parsed as plain JSON and refused by name (``not_read``)."""
    from .reader import parse
    tree, _found = parse(raw)
    if isinstance(tree, dict):
        return _is_v03(tree.get("openphysics"))
    if tree is not None:
        return False
    if isinstance(raw, (bytes, bytearray, memoryview)):
        raw = bytes(raw).decode("utf-8", "replace")
    return isinstance(raw, str) and _V03_TEXT.search(raw) is not None
