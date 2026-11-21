# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Steady heat reads a library material's constant thermal_conductivity (physmat's 300 K
handbook value) in single- and multi-physics documents; transient heat does not."""
import copy
import json
from pathlib import Path

import numpy as np
import pytest

from simcase import Document, DocumentError, multiphysics, resolve, run

from multiphysics_fixtures import heated_slab, uncoupled_modes

EXAMPLES = Path(__file__).resolve().parents[2] / "examples" / "simcase"


def _example(name):
    return json.loads((EXAMPLES / name).read_text(encoding="utf-8"))


def _regions(local=True):
    """thermal_regions.json with its materials replaced by Si (plate), SiO2 (background) and a
    local copper heater; as library references, or as local records of the library values."""
    tree = _example("thermal_regions.json")
    tree["materials"] = {"copper": {"thermal_conductivity": "400 W/(m K)"}}
    if local:
        tree["materials"].update(si={"thermal_conductivity": "148 W/(m K)"},
                                 silica={"thermal_conductivity": "1.38 W/(m K)"})
        names = {"plate": "si", "background": "silica"}
    else:
        names = {"plate": "physmat:Si", "background": "physmat:SiO2"}
    tree["geometry"]["background"]["material"] = names["background"]
    for shape in tree["geometry"]["shapes"]:
        if shape["name"] == "plate":
            shape["material"] = names["plate"]
    return tree


def test_library_conductivity_gives_the_local_record_result_bit_for_bit():
    local = run(Document.from_dict(_regions(True)), verbose=False)
    library = run(Document.from_dict(_regions(False)), verbose=False)
    assert np.array_equal(np.asarray(local.mesh.nodes), np.asarray(library.mesh.nodes))
    assert np.array_equal(np.asarray(local.temperature), np.asarray(library.temperature))
    assert np.array_equal(np.asarray(local.solution.heat_flux), np.asarray(library.solution.heat_flux))


def test_the_library_record_is_resolved_under_its_reference():
    doc = Document.from_dict(_regions(False))
    assert doc.si["materials"]["physmat:Si"] == {"thermal_conductivity": 148.0}
    assert doc.si["materials"]["physmat:SiO2"] == {"thermal_conductivity": 1.38}
    summary = doc.summary()
    assert "material physmat:Si: thermal_conductivity 148 W/(m K) (physmat, constant 300 K handbook value)" in summary


@pytest.mark.parametrize("name, words", [
    ("Cu", "gives thermal_conductivity as a temperature model"),
    ("Al", "gives thermal_conductivity as a temperature model"),
    ("vacuum", "gives no thermal_conductivity in the library"),
    ("standard_air", "gives no thermal_conductivity in the library"),
])
def test_a_library_material_without_a_constant_conductivity_is_refused_by_name(name, words):
    tree = _regions(False)
    tree["geometry"]["background"]["material"] = f"physmat:{name}"
    with pytest.raises(DocumentError) as caught:
        Document.from_dict(tree)
    assert caught.value.code == "E-PROPERTY-MISSING"
    assert f'"physmat:{name}" {words}' in str(caught.value)
    assert "describe the material as a local record" in str(caught.value)


def test_a_library_material_without_a_stated_temperature_is_reported():
    tree = _regions(False)
    tree["geometry"]["background"]["material"] = "physmat:Si3N4"
    found = [d.code for d in resolve.resolve_tree(tree).diagnostics]
    assert "I-DATUM-ASSUMED" in found
    assert Document.from_dict(tree).si["materials"]["physmat:Si3N4"] == {"thermal_conductivity": 20.0}


def test_transient_heat_still_refuses_library_materials():
    tree = _example("transient_thermal_regions.json")
    tree["geometry"]["background"]["material"] = "physmat:SiO2"
    found = [(d.code, d.message) for d in resolve.resolve_tree(tree).diagnostics.errors]
    assert any(c == "E-CONTRACT" and "library properties for this physics are not supported" in m for c, m in found)


def _library_slab(**kw):
    tree = heated_slab(0.04, **kw)
    xs = tree["geometry"]["components"]["xs"]
    xs["background"]["material"], xs["features"][0]["material"] = "physmat:SiO2", "physmat:Si"
    del tree["materials"]
    return tree


def test_a_heat_to_modes_document_reads_physmat_si_and_sio2():
    """The heat field equals the local-record document's bit for bit; with 300 K everywhere and
    no source the modes equal the uncoupled single-physics document of physmat:Si and SiO2."""
    library = multiphysics.run(Document.from_dict(_library_slab(bottom="300 K", top="400 K")), verbose=False)
    local = multiphysics.run(Document.from_dict(heated_slab(0.04, bottom="300 K", top="400 K")), verbose=False)
    assert np.array_equal(np.asarray(library.results["heat1"].temperature),
                          np.asarray(local.results["heat1"].temperature))
    flat = multiphysics.run(Document.from_dict(_library_slab(bottom="300 K", top="300 K", sides="300 K")),
                            verbose=False).results["modes1"]
    tree = uncoupled_modes(0.04)
    xs = tree["geometry"]["components"]["xs"]
    xs["background"]["material"], xs["features"][0]["material"] = "physmat:SiO2", "physmat:Si"
    del tree["materials"]
    uncoupled = run(Document.from_dict(tree), verbose=False)
    assert np.array_equal(flat.effective_index, uncoupled.effective_index)
    assert np.array_equal(flat.mode_fields[0], uncoupled.mode_fields[0])
