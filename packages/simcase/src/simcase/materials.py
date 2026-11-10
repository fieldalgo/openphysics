# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Material names in the document -> physmat Material objects, and the format 0.3 rules.

physmat is micrometre-native, so a 0.2 document that supplies its own dispersion
coefficients has them converted here: a Sellmeier C carries length squared and a
validity range carries length, both in the document's units.

Format 0.3 (rule 2.6): a material reference is a local name, which resolves only to its
record in ``materials``, or ``physmat:<Name>``, matched exactly against ``physmat.names()``
(no case folding, no aliases). Which library references a document may use is its kind's
policy: ``any``, ``vacuum`` (only ``physmat:vacuum``) or ``none``. A local name is any
non-empty string without ``:``. ``check_record_model`` checks the Sellmeier model form of
``refractive_index`` beyond what each of its values checks on its own.
"""

from __future__ import annotations

import difflib

import physmat
from physmat.units import Diagnostic, Suggestion

from . import units
from .schema import Document, DocumentError

LIBRARY_PREFIX = "physmat:"
LIBRARY_POLICIES = ("any", "vacuum", "none")


def resolve_material(doc: Document, name: str) -> physmat.Material:
    custom = doc["materials"].get(name)
    if custom is not None:
        if "sellmeier" in custom:
            s = custom["sellmeier"]
            rng = tuple(s.get("range", (0.0, float("inf"))))
            # Each coefficient is converted exactly, so the same glass written in nm,
            # um or m reaches physmat as the same doubles.
            model = physmat.Sellmeier([float(b) for b in s["B"]],
                                      [units.length_to_micrometres(c, doc.scale, power=2) for c in s["C"]],
                                      s.get("A", 1.0),
                                      tuple(units.length_to_micrometres(r, doc.scale) for r in rng), name)
            return physmat.Material(name, model, custom.get("source", "document"))
        return physmat.Material(name, physmat.Constant(float(custom["n"]), float(custom.get("k", 0.0)), name),
                                custom.get("source", "document"))
    try:
        return physmat.get(name)
    except KeyError:
        raise DocumentError(f"material {name!r} is neither defined in the document nor built into physmat "
                            f"(built-ins: {physmat.names()})") from None


def material_table(doc: Document, region_materials: dict[str, str]) -> dict[str, physmat.Material]:
    return {region: resolve_material(doc, mat) for region, mat in region_materials.items()}


# -- format 0.3 -----------------------------------------------------------------------------------

def check_local_name(name, path: str) -> Diagnostic | None:
    """``E-ID-CLASH`` for a local material name that is empty or holds ``:`` (rule 2.6)."""
    if not isinstance(name, str) or not name:
        return Diagnostic("E-ID-CLASH", path, "a local material name is a non-empty string")
    if ":" in name:
        return Diagnostic("E-ID-CLASH", path, f'local material name "{name}" holds ":", which is reserved for '
                                              'library references such as "physmat:SiO2"; rename it')
    return None


def _library_hints(name: str) -> list[str]:
    hints = []
    try:
        hints.append(physmat.get(name).name)          # case and the library's own aliases
    except KeyError:
        pass
    if name.lower() == "air":
        hints += ["vacuum", "standard_air"]
    hints += difflib.get_close_matches(name, physmat.names(), n=2, cutoff=0.6)
    return list(dict.fromkeys(hints))


def _ref_suggestions(names) -> tuple[Suggestion, ...]:
    return tuple(Suggestion(f"{LIBRARY_PREFIX}{n}", None, None, "1") for n in names)


def resolve_reference(ref, local: dict, path: str, policy: str) -> tuple[tuple | None, list[Diagnostic]]:
    """``(("local", name) or ("library", name) or None, diagnostics)`` of one reference."""
    if policy not in LIBRARY_POLICIES:
        raise ValueError(f"library policy: expected one of {LIBRARY_POLICIES}, got {policy!r}")
    if not isinstance(ref, str) or not ref:
        return None, [Diagnostic("E-VALUE-FORM", path, "a material reference is a local name or \"physmat:<Name>\"")]
    if ref.startswith(LIBRARY_PREFIX):
        name = ref[len(LIBRARY_PREFIX):]
        if name not in physmat.names():
            hints = _library_hints(name)
            msg = f'"{ref}" is not a physmat library material; names are matched exactly, without aliases.'
            if hints:
                msg += " Did you mean " + " or ".join(f'"{LIBRARY_PREFIX}{h}"' for h in hints) + "?"
            msg += f" Library names: {' '.join(physmat.names())}."
            return None, [Diagnostic("E-LIBRARY-UNKNOWN", path, msg, suggestions=_ref_suggestions(hints))]
        if policy == "none":
            return None, [Diagnostic("E-CONTRACT", path,
                                     f'{path}: "{ref}": library properties for this physics are not supported in '
                                     "this release; write a local record in materials")]
        if policy == "vacuum" and name != "vacuum":
            return None, [Diagnostic("E-CONTRACT", path, f'{path}: "{ref}": this physics takes constant '
                                                         'relative_permittivity only; of the library it reads '
                                                         '"physmat:vacuum"')]
        return ("library", name), []
    if ref in local:
        return ("local", ref), []
    msg = f'material "{ref}" has no record in materials; a bare name is local only.'
    hints = [] if policy == "none" else _library_hints(ref)
    if ref in physmat.names() and ref not in hints:
        hints.insert(0, ref)
    if hints and policy != "none":
        msg += " For the library material write " + " or ".join(f'"{LIBRARY_PREFIX}{h}"' for h in hints) + "."
    return None, [Diagnostic("E-MATERIAL-UNKNOWN", path, msg, suggestions=_ref_suggestions(hints))]


def datum_diagnostic(name: str, path: str) -> Diagnostic | None:
    """``I-DATUM-ASSUMED`` for a library record whose source states no reference temperature."""
    material = physmat.get(name)
    if getattr(material, "datum_assumed", False):
        return Diagnostic("I-DATUM-ASSUMED", path,
                          f'"{LIBRARY_PREFIX}{name}": its source states no temperature for its data, so the '
                          "data are assumed to hold at room temperature (an error under --strict)")
    return None


def check_record_model(model: dict, path: str) -> list[Diagnostic]:
    """Checks of a ``refractive_index`` model object that span its values.

    Each value was converted on its own already (the reader also checks that a
    ``valid.vacuum_wavelength`` range has ``lo < hi``, or ``null`` for an open lower bound);
    here: one wavelength form per Sellmeier term."""
    found = []
    if model.get("model") == "rii_formula":
        return found
    for i, term in enumerate(model.get("terms") or []):
        if not isinstance(term, dict):
            continue
        given = [k for k in ("resonance_wavelength_squared", "resonance_wavelength") if k in term]
        where = f"{path}.terms[{i}]"
        if len(given) == 2:
            found.append(Diagnostic("E-OVERDETERMINED", where, "a Sellmeier term takes one of "
                                    "resonance_wavelength_squared and resonance_wavelength, not both"))
        elif not given:
            found.append(Diagnostic("E-KEY-MISSING", f"{where}.resonance_wavelength_squared",
                                    "a Sellmeier term needs resonance_wavelength_squared (or "
                                    "resonance_wavelength)"))
    return found
