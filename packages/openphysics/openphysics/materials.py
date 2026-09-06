# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0

"""Material names in the document -> physmat Material objects.

physmat is micrometre-native, so a document that supplies its own dispersion
coefficients has them converted here: a Sellmeier C carries length squared and a
validity range carries length, both in the document's units.
"""

from __future__ import annotations

import physmat

from . import units
from .schema import Document, DocumentError


def resolve_material(doc: Document, name: str) -> physmat.Material:
    custom = doc["materials"].get(name)
    if custom is not None:
        if "sellmeier" in custom:
            s = custom["sellmeier"]
            um = units.to_micrometres(1.0, doc.scale)          # one document length, in um
            rng = tuple(s.get("range", (0.0, float("inf"))))
            model = physmat.Sellmeier([float(b) for b in s["B"]],
                                      [float(c) * um ** 2 for c in s["C"]],
                                      s.get("A", 1.0),
                                      (rng[0] * um, rng[1] * um), name)
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
