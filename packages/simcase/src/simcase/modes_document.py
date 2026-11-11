# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""``em.modes2d`` documents in format 0.3: slots, validation, summary text and the kernel hand-off.

A format 0.3 waveguide document writes every length with its unit (``"vacuum_wavelength":
"1.55 um"``), names its keys by the registry (``mode_count``, ``target_effective_index``,
``effective_index_threshold``, ``pml.pml_thickness``, ``bend.bend_radius``, ...), gives its
materials as ``refractive_index`` records or exact ``physmat:<Name>`` references and reads
complex values under exp(-i omega t). The validator here checks the document on its SI values
(picometre counts for shape numbers, exact rationals for tagged lengths, hazard H14).

The mode kernel (``physics_em_modes2d``, ``physics_pml_modes``, the trackers and
``mode_postprocessing``) keeps its micrometre frame and exp(+i omega t) (phase-2 spec §1.2,
§3.8). ``kernel_document`` builds the hand-off it reads: the document's micrometre frame
(``views.micrometre_frame``: shape numbers ``float(Fraction(pm, 10**6))``, every tagged length
``float(exact metres * 10**6)``, hazard H2, and the mesher's angle as written, H3) with the
physics, study and results in the kernel's own keys, and the Sellmeier coefficients in square
micrometres from their exact values (H13). The document's own checks (``validate_03``) cover
what the kernel needs; of the retired kernel contract only its tracking check stays on the
hand-off (a vector sweep's settings, resolved by the tracker). Nobody writes it. The runner
(``simcase.runner``) converts the kernel's answers back once (``_to_public``).
"""

from __future__ import annotations

import math
from fractions import Fraction

import physmat
from physmat.units import Diagnostic

from . import views
from .schema import DocumentError

TYPE = "em.modes2d"
#: the kernel's boundary order (the format 0.2 default physics entry)
SIDES = ("left", "right", "top", "bottom")
FORMULATIONS = ("scalar", "vector")
#: the spectral keys; em.modes2d reads vacuum_wavelength only
SPECTRAL = ("vacuum_wavelength", "frequency", "photon_energy", "vacuum_wavenumber", "vacuum_angular_wavenumber")
TRACKING_METHODS = ("electric-l2-assignment-v1", "electric-l2-subspace-v1", "scalar-l2-assignment-v1")
#: format 0.3 key -> the kernel's key, per block
PHYSICS_KERNEL = {"vacuum_wavelength": "wavelength", "mode_count": "num_modes", "target_effective_index": "n_target",
                  "effective_index_threshold": "n_cladding", "formulation": "formulation", "type": "type",
                  "boundary": "boundary", "pml": "pml", "bend": "bend"}
PML_KERNEL = {"pml_thickness": "thickness", "pml_strength": "strength", "pml_order": "order",
              "pml_minimum_physical_fraction": "min_physical_fraction"}
#: the kernel's bend order (radius, axis, origin), as format 0.2 documents wrote it
BEND_KERNEL = (("bend_radius", "radius"), ("axis", "axis"), ("bend_origin", "origin"))
TRACKING_KERNEL = {"method": "method", "search_mode_count": "search_modes", "mode_tracking_threshold": "min_overlap",
                   "mode_tracking_margin_threshold": "min_margin", "degeneracy_tolerance": "degeneracy_tolerance",
                   "cluster_span_tolerance": "cluster_span_max", "cluster_gap_threshold": "external_gap_min"}
#: the kernel's tracking names -> format 0.3 names (results echo the settings under these)
TRACKING_PUBLIC = {kernel: public for public, kernel in TRACKING_KERNEL.items()}
SHAPE_KEYS = {"rect": {"x", "y", "w", "h"}, "circle": {"cx", "cy", "r"}, "polygon": {"points"}}

_FORMAT_02 = ('format 0.2 em.modes2d documents are not read: units now travel with each value ("1.55 um"), keys '
              'are registry names (vacuum_wavelength, mode_count, effective_index_threshold), library materials '
              'are "physmat:<Name>" and complex values read under exp(-i omega t). Write "openphysics": "0.3" '
              '(docs/packages/simcase/document_format.md)')


class ModesHandOff(views.MicrometreFrame):
    """The micrometre kernel hand-off of a format 0.3 ``em.modes2d`` document
    (``kernel_document``): its micrometre frame with the physics, study and results in the
    kernel's own keys and frame. It is never validated, written or read by a user."""


def _refuse(message, path=None, code="E-CONTRACT"):
    if code != "E-CONTRACT" and path and message.startswith(path + ": "):
        message = message[len(path) + 2:]
    raise DocumentError(message, path=path, code=code)


def is_modes(data) -> bool:
    physics = data.get("physics") if isinstance(data, dict) else None
    return isinstance(physics, dict) and any(isinstance(p, dict) and p.get("type") == TYPE
                                             for p in physics.values())


# -- slots ----------------------------------------------------------------------------------------

def modes_slots() -> tuple[dict, ...]:
    """The slots em.modes2d documents add to the shared ones (``simcase.slots``), data only."""
    p = "physics.*{" + TYPE + "}"

    def q(key, quantity, forms=("QS", "AV"), **extra):
        return {"pattern": f"{p}.{key}", "kind": "quantity", "quantity": quantity, "forms": list(forms), **extra}

    def obj(pattern, **extra):
        return {"pattern": pattern, "kind": "structural", "forms": ["OBJECT"], **extra}

    def enum(pattern, values, **extra):
        return {"pattern": pattern, "kind": "enum", "values": list(values), **extra}

    def refused(pattern, message, code="E-CONTRACT"):
        return {"pattern": pattern, "kind": "refused", "code": code, "message": message}

    out = [enum(f"{p}.type", [TYPE], required=True),
           enum(f"{p}.formulation", FORMULATIONS, default="scalar",
                default_reason="structural default: the scalar (semi-vectorial) formulation"),
           q("vacuum_wavelength", "vacuum_wavelength", required=True),
           q("mode_count", "mode_count", ("BC",), default=1, default_reason="count default: one mode"),
           q("target_effective_index", "target_effective_index", ("BD",)),
           q("effective_index_threshold", "effective_index_threshold", ("BD",)),
           obj(f"{p}.boundary", default={}, default_reason="structural default: every side is pec"),
           *[enum(f"{p}.boundary.{side}", ("pec", "pmc"), default="pec",
                  default_reason="structural default: a perfect electric conductor wall") for side in SIDES],
           obj(f"{p}.pml"), obj(f"{p}.pml.pml_thickness", required=True),
           *[q(f"pml.pml_thickness.{side}", "pml_thickness") for side in SIDES],
           q("pml.pml_strength", "pml_strength", ("BD",), default=3.0,
             default_reason="dimensionless default: the PML stretching strength"),
           q("pml.pml_order", "pml_order", ("BC",), default=2, default_reason="count default: a quadratic profile"),
           q("pml.pml_minimum_physical_fraction", "pml_minimum_physical_fraction", ("BD",), default=0.1,
             default_reason="dimensionless default: the candidate filter"),
           obj(f"{p}.bend"), q("bend.bend_radius", "bend_radius", required=True),
           q("bend.bend_origin", "bend_origin", required=True),
           enum(f"{p}.bend.axis", ("x", "y"), default="x",
                default_reason="structural default: the bend radius grows along +x"),
           *[refused(f"{p}.{key}", f"{key} is not read by em.modes2d in this release; give vacuum_wavelength "
                                   '(such as "1.55 um")') for key in SPECTRAL[1:]],
           refused(f"{p}.allow_gain", "allow_gain is not read: both mode solvers are passive only (k >= 0 and "
                                      "Im eps_r >= 0 under exp(-i omega t))"),
           obj("study.tracking"), enum("study.tracking.method", TRACKING_METHODS),
           {"pattern": "study.tracking.search_mode_count", "kind": "quantity", "quantity": "search_mode_count",
            "forms": ["BC"]},
           *[{"pattern": f"study.tracking.{key}", "kind": "quantity", "quantity": key, "forms": ["BD"]}
             for key in ("mode_tracking_threshold", "mode_tracking_margin_threshold", "degeneracy_tolerance",
                         "cluster_span_tolerance", "cluster_gap_threshold")],
           obj("results.mode_overlap"), obj("results.mode_overlap.gaussian", required=True),
           {"pattern": "results.mode_overlap.gaussian.beam_waist_radius", "kind": "quantity",
            "quantity": "beam_waist_radius", "forms": ["QS", "AV"], "required": True},
           {"pattern": "results.mode_overlap.gaussian.position", "kind": "quantity", "quantity": "position",
            "forms": ["SL", "TA"], "required": True}]
    results = {"save_fields": True, "plots": True}
    out += [{"pattern": "materials.*", "kind": "override", "library": "any", "reads": {TYPE: ["refractive_index"]}},
            {"pattern": "name", "kind": "override", "default": "untitled",
             "default_reason": "structural default: the document has no name"},
            {"pattern": "results", "kind": "override", "default": results,
             "default_reason": "structural default of em.modes2d documents"},
            {"pattern": "results.save_fields", "kind": "override", "default": True,
             "default_reason": "structural default of em.modes2d documents"},
            {"pattern": "results.plots", "kind": "override", "default": True,
             "default_reason": "structural default of em.modes2d documents"},
            {"pattern": "study", "kind": "override", "default": {"type": "single"},
             "default_reason": "structural default: one solve"}]
    return tuple(out)


def refuse_03(tree) -> tuple | None:
    """``E-SPECTRAL`` for an entry that gives more than one spectral key, before its slots are read."""
    physics = tree.get("physics") if isinstance(tree, dict) else None
    for name, entry in (physics.items() if isinstance(physics, dict) else ()):
        if isinstance(entry, dict) and entry.get("type") == TYPE:
            given = [key for key in SPECTRAL if key in entry]
            if len(given) > 1:
                where = f"physics.{name}.{given[1]}"
                return (where, f"{where}: give exactly one spectral key; em.modes2d reads vacuum_wavelength "
                               f"(found {', '.join(given)})", "E-SPECTRAL")
    return None


# -- the component ---------------------------------------------------------------------------------

def component(doc):
    """``(base path, authored block, SI block)`` of the one 2d component of a format 0.3 document."""
    g, si = doc.data["geometry"], doc.si["geometry"]
    if "version" not in g:
        return "geometry", g, si
    if len(g["components"]) != 1:
        _refuse("geometry.components: an em.modes2d document has exactly one component", "geometry.components")
    (name, block), = g["components"].items()
    base = f"geometry.components.{name}"
    dimension = block.get("dimension")
    if dimension == "axisymmetric":
        _refuse(f"{base}.dimension: em.modes2d takes 2d components only; an axisymmetric component is a body of "
                "revolution, which this waveguide physics does not describe (steady region heat takes it)",
                f"{base}.dimension")
    if dimension != "2d":
        _refuse(f"{base}.dimension: em.modes2d takes one 2d cross-section component", f"{base}.dimension")
    return base, block, si["components"][name]


def entry(doc):
    """``(name, SI entry, authored entry, path)`` of the one physics entry."""
    doc.sole_physics()
    name, p = next(iter(doc.si["physics"].items()))
    if not isinstance(name, str) or not name.isidentifier():
        _refuse("physics: name must be an identifier: a study or a coupling refers to a physics by this name",
                f"physics.{name}")
    return name, p, doc.data["physics"][name], f"physics.{name}"


def _exact(doc, path):
    """The exact SI value of a tagged value (an annotated value's ``value``)."""
    value = doc.exact(path)
    if value is None:
        value = doc.exact(path + ".value")
    if value is None:
        raise KeyError(path)
    return value


def um(doc, path):
    """A tagged length in micrometres from its exact value: ``float(exact * 10**6)`` (hazard H2)."""
    value = _exact(doc, path)
    if isinstance(value, list):
        return [None if v is None else float(Fraction(v) * 10 ** 6) for v in value]
    return float(Fraction(value) * 10 ** 6)


def _domain_m(doc, base):
    """The domain bounds as exact metres (from picometre counts)."""
    return {k: Fraction(doc.pm(f"{base}.domain.{k}"), 10 ** 12) for k in ("xmin", "xmax", "ymin", "ymax")}


# -- validation ------------------------------------------------------------------------------------

def validate(doc):
    """The ``em.modes2d`` contract on a format 0.3 document. A document that was not read as
    format 0.3 is refused by name (``E-FORMAT`` at ``openphysics``): a format 0.2 document of this
    type with its conversion hint, any other with the reader's (this kind is the registry's
    fallback, so a document no kind claims ends here)."""
    if doc.si is None:
        if is_modes(doc.data):
            raise DocumentError(_FORMAT_02, path="openphysics", code="E-FORMAT")
        from .resolve import format_refusal
        refusal = format_refusal(doc.data) if isinstance(doc.data, dict) else None
        if refusal is None:
            raise DocumentError("document: expected a format 0.3 document object, read by Document.from_dict",
                                path="openphysics", code="E-FORMAT")
        raise DocumentError(refusal.message, path=refusal.path, code=refusal.code)
    validate_03(doc)


def validate_03(doc):
    base, block, si_block = component(doc)
    name, p, a, path = entry(doc)
    dom = _domain_m(doc, base)
    for axis in "xy":
        if not dom[f"{axis}min"] < dom[f"{axis}max"]:
            _refuse(f"{base}.domain: expected a positive extent ({axis}min < {axis}max)", f"{base}.domain.{axis}max")
    _geometry(doc, base, block)
    _materials(doc)
    _mesh(doc)
    _physics(doc, name, p, a, path, dom)
    _study(doc, name, p, path)
    _gaussian(doc, dom)
    _default_boundaries(doc, name, a)
    if "version" in doc.data["geometry"]:
        # a version 1 block's region view is made (and its segments checked) at load; it is kept
        # on the document and meshed by build_mesh
        from .thermal_regions import handoff_03
        handoff_03(doc)


def _geometry(doc, base, block):
    background = block.get("background")
    if not isinstance(background, dict) or "material" not in background:
        _refuse(f"{base}.background.material: an em.modes2d window is filled; give the background material (for "
                'example "physmat:SiO2")', f"{base}.background.material", "E-KEY-MISSING")
    if background["material"] is None:
        _refuse(f"{base}.background.material: an em.modes2d window takes no void background; give a material",
                f"{base}.background.material")
    if "version" in doc.data["geometry"]:
        return
    names = set()
    for i, s in enumerate(block.get("shapes") or []):
        where = f"geometry.shapes[{i}]"
        t = s.get("type")
        if t not in SHAPE_KEYS:
            _refuse(f"{where}.type: em.modes2d takes rect, circle and polygon shapes", f"{where}.type")
        extra = sorted(set(s) - ({"type", "name", "material", "element_size"} | SHAPE_KEYS[t]))
        if extra:
            _refuse(f"a {t} shape does not take {extra[0]!r} (unsupported keys {extra})", f"{where}.{extra[0]}",
                    "E-KEY-UNKNOWN")
        missing = sorted(SHAPE_KEYS[t] - set(s))
        if missing:
            _refuse(f"a {t} shape needs {missing}", f"{where}.{missing[0]}", "E-KEY-MISSING")
        if s["name"] == "background" or s["name"] in names:
            _refuse(f'{where}.name: expected a unique name other than "background"', f"{where}.name", "E-ID-CLASH")
        names.add(s["name"])
        if t == "polygon":
            if len(s["points"]) < 3 or any(not isinstance(q, list) or len(q) != 2 for q in s["points"]):
                _refuse(f"{where}.points: expected at least three [x, y] points", f"{where}.points")
        for k in ("w", "h", "r"):
            if k in SHAPE_KEYS[t] and doc.pm(f"{where}.{k}") <= 0:
                _refuse(f"{where}.{k}: expected a positive length", f"{where}.{k}", "E-DOMAIN")


def _materials(doc):
    """Every local material a region uses gives refractive_index; library references are any
    physmat material (the reader resolved each reference exactly)."""
    local = doc.si.get("materials") or {}
    for where, target in doc._resolution.refs.items():
        if target[0] != "local":
            continue
        if "refractive_index" not in local[target[1]]:
            _refuse(f"materials.{target[1]}.refractive_index: required by em.modes2d (used at {where})",
                    f"materials.{target[1]}.refractive_index", "E-PROPERTY-MISSING")


def _mesh(doc):
    mesh = doc.si.get("mesh") or {}
    if "subdivision_count" in mesh:
        _refuse("mesh.subdivision_count: em.modes2d is meshed by element_size; subdivision_count belongs to "
                "rectangle documents", "mesh.subdivision_count", "E-KEY-UNKNOWN")
    if "element_size" not in mesh:
        _refuse('mesh.element_size: required by em.modes2d (for example "0.25 um"); the 0.2 default 0.2 in '
                "document units is gone", "mesh.element_size", "E-KEY-MISSING")
    if mesh.get("controls") and "version" not in doc.data["geometry"]:
        _refuse("mesh.controls needs a version 1 geometry block with a 2D region component; a flat geometry block "
                "has no selections to control", "mesh.controls")
    if mesh["minimum_angle"] > math.radians(33):
        _refuse("mesh.minimum_angle: at most 33 deg (refinement need not terminate above)", "mesh.minimum_angle",
                "E-DOMAIN")


def _physics(doc, name, p, a, path, dom):
    vector = p["formulation"] == "vector"
    if p["mode_count"] < 1:
        _refuse(f"{path}.mode_count: expected at least one mode", f"{path}.mode_count", "E-DOMAIN")
    if "target_effective_index" in p and not p["target_effective_index"] > 0:
        _refuse(f"{path}.target_effective_index: expected a positive index", f"{path}.target_effective_index",
                "E-DOMAIN")
    if vector and "effective_index_threshold" not in p:
        _refuse(f"{path}.effective_index_threshold: the vector formulation keeps the modes above this index (the "
                "cladding index, such as 1.444)", f"{path}.effective_index_threshold", "E-KEY-MISSING")
    if not vector and "effective_index_threshold" in p:
        _refuse(f"{path}.effective_index_threshold: read by the vector formulation only; the scalar formulation "
                "returns the mode_count largest indices", f"{path}.effective_index_threshold")
    if "bend" in p and "pml" not in p:
        _refuse(f"{path}.bend: a bend needs pml (the radiation of a bent guide leaves through it)", f"{path}.bend")
    if "pml" not in p:
        return
    if "target_effective_index" not in p:
        _refuse(f"{path}.pml: pml needs target_effective_index (the PML candidates are selected near it)",
                f"{path}.target_effective_index", "E-KEY-MISSING")
    pml = p["pml"]
    thickness = pml["pml_thickness"]
    if not thickness:
        _refuse(f"{path}.pml.pml_thickness: give at least one side with a positive thickness",
                f"{path}.pml.pml_thickness", "E-KEY-MISSING")
    for side in thickness:
        if p["boundary"][side] != "pec":
            _refuse(f"{path}.pml.pml_thickness.{side}: a PML side needs a pec outer wall (boundary.{side} is "
                    f"{p['boundary'][side]})", f"{path}.boundary.{side}")
    t = {side: Fraction(_exact(doc, f"{path}.pml.pml_thickness.{side}")) for side in thickness}
    if (t.get("left", 0) + t.get("right", 0) >= dom["xmax"] - dom["xmin"]
            or t.get("bottom", 0) + t.get("top", 0) >= dom["ymax"] - dom["ymin"]):
        _refuse(f"{path}.pml.pml_thickness: the PML strips leave no physical window", f"{path}.pml.pml_thickness")
    if pml["pml_order"] not in (2, 3, 4):
        _refuse(f"{path}.pml.pml_order: expected 2, 3 or 4", f"{path}.pml.pml_order", "E-DOMAIN")
    if "bend" in p:
        bend = p["bend"]
        radius = Fraction(_exact(doc, f"{path}.bend.bend_radius"))
        origin = Fraction(_exact(doc, f"{path}.bend.bend_origin"))
        if radius + dom[bend["axis"] + "min"] - origin <= 0:
            _refuse(f"{path}.bend: the whole window must lie at a positive radius (bend_radius + {bend['axis']}min - "
                    "bend_origin > 0)", f"{path}.bend.bend_radius")


def _study(doc, name, p, path):
    st = doc.si["study"]
    if st["type"] not in ("single", "sweep"):
        _refuse('study.type: em.modes2d takes "single" or "sweep"', "study.type")
    tracking = (doc.data.get("study") or {}).get("tracking")
    if st["type"] != "sweep":
        return                          # a single solve tracks nothing; its settings are not read, as before
    if "parameter" not in st or "values" not in st:
        _refuse("study: a sweep needs parameter (a dotted path under physics) and values", "study.parameter",
                "E-KEY-MISSING")
    parameter, values = st["parameter"], st["values"]
    wavelength = f"{path}.vacuum_wavelength"
    if "pml" in p and parameter != wavelength:
        _refuse("study.parameter: PML sweeps support only the vacuum wavelength, with fixed geometry and "
                "coordinates", "study.parameter")
    if p["formulation"] == "vector":
        if parameter != wavelength:
            _refuse("study.parameter: vector sweeps support only the vacuum_wavelength of the physics entry",
                    "study.parameter")
        if len(values) < 3:
            _refuse("study.values: vector wavelength sweeps need at least 3 values (the group index)",
                    "study.values")
        pairs = list(zip(values, values[1:]))
        if not (all(x < y for x, y in pairs) or all(x > y for x, y in pairs)):
            _refuse("study.values: vector sweep wavelengths must be strictly monotone (no duplicates)",
                    "study.values")
        _tracking(doc, int(p["mode_count"]), tracking)
        return
    if tracking is not None:
        _refuse("study.tracking: tracking settings are read for vector wavelength sweeps only", "study.tracking")
    if parameter == f"{path}.formulation" and "vector" in values:
        _refuse("study.values: a scalar sweep cannot switch to vector; use a vector wavelength sweep",
                "study.values")


def kernel_tracking(doc):
    """The study's tracking settings under the kernel's names, as written (None when absent)."""
    tracking = (doc.data.get("study") or {}).get("tracking")
    if tracking is None:
        return None
    si = doc.si["study"]["tracking"]
    return {TRACKING_KERNEL[key]: si[key] for key in tracking}


def _public_message(text: str) -> str:
    """A kernel settings message under the format 0.3 names."""
    for kernel, public in sorted(TRACKING_PUBLIC.items(), key=lambda kv: -len(kv[0])):
        if kernel != public:
            text = text.replace(f"study.tracking.{kernel}", f"study.tracking.{public}")
            text = text.replace(kernel, public)
    return text.replace("num_modes", "mode_count")


#: the kernel's solve messages under the format 0.3 names and convention (a closed list)
KERNEL_MESSAGES = (
    ("passive modes use Im eps <= 0 with exp(+i omega t - i beta z)",
     "passive modes need Im eps >= 0 under exp(-i omega t); a material with gain is refused"),
    ("check the cladding index,", "check effective_index_threshold,"),
    ("min_physical_fraction", "pml_minimum_physical_fraction"),
    ("n_target", "target_effective_index"),
    ("n_cladding", "effective_index_threshold"),
)


def public_kernel_message(text: str) -> str:
    """A message of the mode kernel's solve under the format 0.3 names."""
    for kernel, public in KERNEL_MESSAGES:
        text = text.replace(kernel, public)
    return text


def _tracking(doc, mode_count, tracking):
    """Check the tracking settings with the tracker's own resolver (as format 0.2 did) and echo
    the defaults it fills in ``defaults_applied``."""
    from .tracking import tracking_settings
    try:
        settings = tracking_settings(mode_count, kernel_tracking(doc))
    except (ValueError, OverflowError) as exc:
        message = _public_message(str(exc))
        named = [public for public in TRACKING_KERNEL if f"study.tracking.{public}" in message]
        where = f"study.tracking.{named[0]}" if named else "study.tracking"
        _refuse(message if message.startswith(where) else f"{where}: {message}", where)
    authored = set(tracking or ())
    seen = {entry["path"] for entry in doc.defaults_applied}
    for kernel, value in settings.items():
        public = TRACKING_PUBLIC[kernel]
        where = f"study.tracking.{public}"
        if public in authored or where in seen or kernel == "method":
            continue
        reason = ("count default: max(2 mode_count, mode_count + 4) candidates" if public == "search_mode_count"
                  else "dimensionless default of the mode tracker")
        doc.defaults_applied.append({"path": where, "value": value, "reason": reason})


def _gaussian(doc, dom):
    spec = (doc.si.get("results") or {}).get("mode_overlap")
    if spec is None:
        return
    where = "results.mode_overlap.gaussian.position"
    position = _exact(doc, where)
    if len(position) != 2:
        _refuse(f"{where}: expected [x, y]", where, "E-VALUE-FORM")
    x, y = (Fraction(v) for v in position)
    if not (dom["xmin"] <= x <= dom["xmax"] and dom["ymin"] <= y <= dom["ymax"]):
        _refuse(f"{where}: the Gaussian centre lies outside the geometry window", where)


def _default_boundaries(doc, name, a):
    """``I-DEFAULT-BOUNDARY`` for each side the entry does not name: it is pec."""
    given = a.get("boundary") or {}
    seen = {(d.code, d.path) for d in doc.diagnostics}
    for side in SIDES:
        where = f"physics.{name}.boundary.{side}"
        if side not in given and ("I-DEFAULT-BOUNDARY", where) not in seen:
            doc.diagnostics.append(Diagnostic("I-DEFAULT-BOUNDARY", where, f"side {side!r} has no boundary "
                                                                            "condition: it is pec (a perfect "
                                                                            "electric conductor wall)"))


# -- summary text ----------------------------------------------------------------------------------

def summary(doc) -> str:
    """The one-paragraph text of ``Document.summary`` and ``simcase validate``."""
    from .thermal import _authored
    if doc.si is None:
        validate(doc)                   # a document that was not read as format 0.3 is refused by name
    base, block, _ = component(doc)
    name, p, a, path = entry(doc)
    unit = block["length_unit"]
    lines = [f"{doc.si['name']}  (openphysics {doc.format})",
             f"  {base} (length_unit {unit}): background {block['background']['material']}"]
    if "version" not in doc.data["geometry"]:
        for i, s in enumerate(block.get("shapes") or []):
            size = (f", element_size {_authored(doc, f'geometry.shapes[{i}].element_size')}" if "element_size" in s
                    else "")
            lines.append(f"  shape {s['name']}: {s['type']} of {s['material']}{size}")
    else:
        for f in block.get("features") or []:
            if f.get("material") is not None:
                lines.append(f"  feature {f.get('name', f.get('id', '?'))}: {f.get('type')} of {f['material']}")
    boundary = ", ".join(f"{side} {p['boundary'][side]}" for side in SIDES)
    lines.append(f"  physics {name}: {TYPE} {p['formulation']}, vacuum_wavelength "
                 f"{_authored(doc, f'{path}.vacuum_wavelength')}, mode_count {p['mode_count']}; boundary {boundary}")
    if "pml" in p:
        sides = ", ".join(f"{side} {_authored(doc, f'{path}.pml.pml_thickness.{side}')}"
                          for side in p["pml"]["pml_thickness"])
        lines.append(f"  pml: {sides}; target_effective_index {p['target_effective_index']}"
                     + (f"; bend_radius {_authored(doc, f'{path}.bend.bend_radius')} along {p['bend']['axis']}"
                        if "bend" in p else ""))
    lines.append(f"  mesh: element_size {_authored(doc, 'mesh.element_size')}"
                 + (", graded" if (doc.si.get("mesh") or {}).get("grading") else ""))
    st = doc.si["study"]
    lines.append(f"  study: {st['type']}" + (f" over {st['parameter']} x{len(st['values'])}"
                                             if st["type"] == "sweep" else ""))
    return "\n".join(lines)


# -- materials ---------------------------------------------------------------------------------------

def optical_material(doc, ref) -> physmat.Material:
    """The physmat material of one reference: ``physmat:<Name>`` from the library, a local name
    from its ``refractive_index`` record (a constant index, n + i k, or the Sellmeier model with
    its coefficients in square micrometres from their exact values, hazard H13)."""
    if ref.startswith("physmat:"):
        return physmat.get(ref[len("physmat:"):])
    record = doc.si["materials"][ref]
    index = record["refractive_index"]
    source = record.get("source", "document")
    if isinstance(index, dict):
        return physmat.Material(ref, _sellmeier(doc, ref, index), source)
    z = complex(index)
    return physmat.Material(ref, physmat.Constant(float(z.real), float(z.imag), ref), source)


def _sellmeier(doc, ref, model):
    base = f"materials.{ref}.refractive_index"
    authored = doc.data["materials"][ref]["refractive_index"]
    strengths, squares = [], []
    for i, term in enumerate(model["terms"]):
        strengths.append(float(term["strength"]))
        where = f"{base}.terms[{i}]"
        if "resonance_wavelength_squared" in term:
            squares.append(float(Fraction(_exact(doc, f"{where}.resonance_wavelength_squared")) * 10 ** 12))
        else:
            squares.append(float((Fraction(_exact(doc, f"{where}.resonance_wavelength")) * 10 ** 6) ** 2))
    constant = float(model["constant"]) if "constant" in authored else 1.0
    valid = (model.get("valid") or {}).get("vacuum_wavelength")
    if valid is None:
        bounds = (0.0, float("inf"))
    else:
        lo, hi = um(doc, f"{base}.valid.vacuum_wavelength")
        bounds = (0.0 if lo is None else lo, hi)
    return physmat.Sellmeier(strengths, squares, constant, bounds, ref)


# -- the kernel hand-off -----------------------------------------------------------------------------

def kernel_path(path: str) -> str:
    """A study parameter path under the kernel's keys (``physics.em1.vacuum_wavelength`` ->
    ``physics.em1.wavelength``)."""
    parts = path.split(".")
    if len(parts) >= 3 and parts[0] == "physics":
        parts[2] = PHYSICS_KERNEL.get(parts[2], parts[2])
        if len(parts) >= 4 and parts[2] == "pml":
            parts[3] = PML_KERNEL.get(parts[3], parts[3])
        if len(parts) >= 4 and parts[2] == "bend":
            parts[3] = dict(BEND_KERNEL).get(parts[3], parts[3])
    return ".".join(parts)


def kernel_physics(doc, name) -> dict:
    """The physics entry in the kernel's keys and micrometres. The kernel's pml and bend blocks
    hold the keys the document writes (the kernel applies the same defaults); the boundary
    holds the four sides in the kernel's order."""
    p, a, path = doc.si["physics"][name], doc.data["physics"][name], f"physics.{name}"
    out = {"type": TYPE, "formulation": p["formulation"], "wavelength": um(doc, f"{path}.vacuum_wavelength"),
           "num_modes": int(p["mode_count"]), "boundary": {side: p["boundary"][side] for side in SIDES}}
    if "effective_index_threshold" in p:
        out["n_cladding"] = float(p["effective_index_threshold"])
    if "target_effective_index" in p:
        out["n_target"] = float(p["target_effective_index"])
    if "pml" in a:
        pml = {}
        for key in a["pml"]:
            if key == "pml_thickness":
                pml["thickness"] = {side: um(doc, f"{path}.pml.pml_thickness.{side}") for side in a["pml"][key]}
            elif key == "pml_order":
                pml["order"] = int(p["pml"][key])
            else:
                pml[PML_KERNEL[key]] = float(p["pml"][key])
        out["pml"] = pml
    if "bend" in a:
        bend = {}
        for key, kernel in BEND_KERNEL:
            if key in a["bend"]:
                bend[kernel] = p["bend"]["axis"] if key == "axis" else um(doc, f"{path}.bend.{key}")
        out["bend"] = bend
    return out


def kernel_study(doc) -> dict:
    st, out = doc.si["study"], {"type": doc.si["study"]["type"]}
    if st["type"] == "sweep":
        parameter = kernel_path(st["parameter"])
        out["parameter"] = parameter
        if st["parameter"].endswith(".vacuum_wavelength"):
            out["values"] = [um(doc, f"study.values[{i}]") for i in range(len(st["values"]))]
        else:
            out["values"] = list(st["values"])
    tracking = kernel_tracking(doc)
    if tracking is not None:
        out["tracking"] = tracking
    return out


def kernel_results(doc) -> dict:
    r = doc.si["results"]
    out = {"save_fields": r["save_fields"], "plots": r["plots"]}
    if r.get("mode_overlap") is not None:
        where = "results.mode_overlap.gaussian"
        out["mode_overlap"] = {"gaussian": {"waist": um(doc, f"{where}.beam_waist_radius"),
                                            "center": um(doc, f"{where}.position")}}
    return out


def kernel_document(doc) -> ModesHandOff:
    """The micrometre hand-off of a validated format 0.3 document: its micrometre frame
    (``views.micrometre_frame``, from the region view ``thermal_regions.handoff_03``) with the
    radial grading, the physics, the study and the results in the kernel's keys and
    micrometres; material references stay as written (the runner resolves them,
    ``optical_material``). A vector sweep's tracking settings are resolved once more here, as
    the kernel contract did."""
    from .thermal_regions import handoff_03
    k = views.micrometre_frame(doc, handoff_03(doc), ModesHandOff)
    d = k.data
    name = entry(doc)[0]
    d["physics"] = {name: kernel_physics(doc, name)}
    mesh = (doc.si.get("mesh") or {})
    grading = None
    if mesh.get("grading"):
        position = um(doc, "mesh.grading.position")
        grading = {"center": position, "near": um(doc, "mesh.grading.near"), "far": um(doc, "mesh.grading.far"),
                   "distance": um(doc, "mesh.grading.refinement_distance")}
    d["mesh"]["grading"] = grading
    d["study"] = kernel_study(doc)
    d["results"] = kernel_results(doc)
    st = d["study"]
    if st["type"] == "sweep" and d["physics"][name]["formulation"] == "vector":
        # the tracking check of the retired kernel contract, kept on purpose on this view: the
        # tracker's resolver on the hand-off's own settings, with the same arguments and at the
        # same point as before (redundant with the run-time call; the contract's check and the
        # recorded calls stay as they were)
        from .tracking import tracking_settings
        try:
            tracking_settings(int(d["physics"][name]["num_modes"]), st.get("tracking"))
        except (ValueError, OverflowError) as exc:
            raise DocumentError(str(exc)) from None
    return k


def stage_point(physics: dict) -> dict:
    """``solve_point``'s resolved SI physics entry in the kernel's keys and micrometres: each
    length is ``float(Fraction(repr(x)) * 10**6)`` (equal to ``float(exact * 10**6)`` for every
    value of at most 15 significant digits, spec §3.8)."""
    def mu(x):
        return float(Fraction(repr(float(x))) * 10 ** 6)
    out = {"type": physics.get("type", TYPE), "formulation": physics.get("formulation", "scalar"),
           "wavelength": mu(physics["vacuum_wavelength"]), "num_modes": int(physics.get("mode_count", 1)),
           "boundary": {side: (physics.get("boundary") or {}).get(side, "pec") for side in SIDES}}
    if physics.get("effective_index_threshold") is not None:
        out["n_cladding"] = float(physics["effective_index_threshold"])
    if physics.get("target_effective_index") is not None:
        out["n_target"] = float(physics["target_effective_index"])
    if physics.get("pml") is not None:
        pml = {}
        for key, value in physics["pml"].items():
            if key == "pml_thickness":
                pml["thickness"] = {side: mu(v) for side, v in value.items()}
            elif key == "pml_order":
                pml["order"] = int(value)
            else:
                pml[PML_KERNEL[key]] = float(value)
        out["pml"] = pml
    if physics.get("bend") is not None:
        bend = {}
        for key, kernel in BEND_KERNEL:
            if key in physics["bend"]:
                bend[kernel] = physics["bend"][key] if key == "axis" else mu(physics["bend"][key])
        out["bend"] = bend
    return out


def plausibility(doc, model, wavelength_um, say) -> None:
    """``W-MAGNITUDE`` for a region whose material index at the vacuum wavelength lies outside
    the registry band of refractive_index (0.01 to 100). Each material is asked once per region,
    as before; a material that cannot answer is skipped (a diagnostic must not fail the run)."""
    from physmat import units as registry
    refs = {}
    for where, target in doc._resolution.refs.items():
        key = target[1] if target[0] == "local" else "physmat:" + target[1]
        refs.setdefault(key, where)
    for region, material in model.materials.items():
        try:
            n = material.index(wavelength_um).real
        except Exception:
            continue
        ref = model.region_materials[region]
        where = refs.get(ref, f"materials.{ref}.refractive_index" if not ref.startswith("physmat:") else "materials")
        c = registry.convert(repr(float(n)), "refractive_index", path=where)
        found = [d for d in c.diagnostics if d.code == "W-MAGNITUDE"]
        seen = {(d.code, d.path) for d in doc.diagnostics}
        for d in found:
            message = f"region {region}: {material.name} has n = {float(n):.6g} at the vacuum wavelength; {d.message}"
            if (d.code, where) not in seen:
                doc.diagnostics.append(Diagnostic(d.code, where, message))
                say(f"  warning: {message}")
