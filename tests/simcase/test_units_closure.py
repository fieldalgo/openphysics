# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Closure checks of the units and naming batch over everything that ships (units batch C11a).

- No document that ships or that a tool or benchmark writes is format 0.2: no
  ``"openphysics": "0.2"``, no ``units`` block and no ``_k``/``_m``-suffixed document key in the
  examples (JSON files and Python document literals), the built-in documents, the Studio
  starters, the format 0.3 fixtures, or any JSON file or document literal (a dict with an
  ``"openphysics"`` key) under ``tools/`` and ``benchmarks/``. The frozen
  ``tools/units_batch/fixtures/v02/`` documents are the P2-1 baseline's inputs and stay. Names a
  document chooses (materials, physics entries, components, parameters, selections) are not
  keys of the format and are not checked for suffixes.
- P2-11 over every shipped example: no key or array name of ``summary.json``, ``fields.npz``
  or the VTU exports ends in a unit token; no ``*_unit`` key; every ``field_units`` entry
  names a registry quantity and holds its canonical unit; every other array is on the closed
  structural list; axisymmetric and em results carry no ``_per_depth`` name; the supported
  layouts hold new identifiers only; every quantity a summary echoes as a value object has
  ``result`` in its registry places.

P2-12 over everything (examples, fixtures, built-ins, Studio starters and JS builder documents)
is in ``test_slots.py``; the geometry adapters' parts are checked here, with (a).
"""

from __future__ import annotations

import ast
import copy
import json
import re
from pathlib import Path

import numpy as np
import pytest
import simcase
from physmat import units

ROOT = Path(__file__).resolve().parents[2]
FROZEN_V02 = ROOT / "tools" / "units_batch" / "fixtures" / "v02"
#: the Studio files of the imported simcase package (the installed wheel in the installed-package run)
STATIC = Path(simcase.__file__).resolve().parent / "studio" / "static"
SUFFIXED = re.compile(r"_(k|m)$")
#: containers whose keys are names a document chooses, not keys of the format
NAMED = {"materials", "physics", "components", "parameters", "selections"}


def _documents_in(value):
    if isinstance(value, dict):
        if "openphysics" in value:
            yield value
        for item in value.values():
            yield from _documents_in(item)
    elif isinstance(value, list):
        for item in value:
            yield from _documents_in(item)


def _format_keys(value, named=False):
    """The keys of the format in a document (a chosen name is skipped, its value is not)."""
    if isinstance(value, dict):
        for key, item in value.items():
            if not named:
                yield key
            yield from _format_keys(item, named=key in NAMED and not named)
    elif isinstance(value, list):
        for item in value:
            yield from _format_keys(item)


def _problems(doc) -> list:
    out = []
    if str(doc.get("openphysics")) == "0.2" and not isinstance(doc.get("openphysics"), bool):
        out.append('"openphysics": "0.2"')
    if "units" in doc:
        out.append("a units block")
    suffixed = sorted({k for k in _format_keys(doc) if isinstance(k, str) and SUFFIXED.search(k)})
    if suffixed:
        out.append(f"suffixed keys {suffixed}")
    return out


def _python_literals(path: Path):
    """``(line, document)`` of every dict literal with an ``"openphysics"`` key in a Python file;
    a dict that is not wholly literal gives its literal keys and its format value."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Dict)
                and any(isinstance(k, ast.Constant) and k.value == "openphysics" for k in node.keys)):
            continue
        try:
            yield node.lineno, ast.literal_eval(node)
        except ValueError:
            partial = {}
            for key, value in zip(node.keys, node.values):
                if isinstance(key, ast.Constant) and isinstance(key.value, str):
                    try:
                        partial[key.value] = ast.literal_eval(value)
                    except ValueError:
                        partial[key.value] = None
            yield node.lineno, partial


def _studio_starters() -> dict:
    """The geometry lab's starters: the JSON literals of ``geometry-lab-starters.mjs``."""
    text = (STATIC / "geometry-lab-starters.mjs").read_text(encoding="utf-8")
    found = dict(re.findall(r"^\s*(\w+):(\{.*\}),?$", text, re.M))
    return {name: json.loads(literal) for name, literal in found.items()}


def test_no_shipped_or_tool_document_is_format_0_2():
    from simcase import examples
    checked, found = 0, []

    def check(label, doc):
        nonlocal checked
        checked += 1
        found.extend((label, p) for p in _problems(doc))
    for name, data in examples.EXAMPLES.items():
        check(f"built-in {name}", data)
    starters = _studio_starters()
    assert set(starters) == {"geometry_v1_soi_strip", "geometry_v1_imprint_rib"}
    for name, data in starters.items():
        check(f"Studio starter {name}", data)
    for root in (ROOT / "examples", ROOT / "tools", ROOT / "benchmarks"):
        for path in sorted(root.rglob("*.json")):
            if FROZEN_V02 in path.parents:
                continue
            data = json.loads(path.read_text(encoding="utf-8"))
            for doc in _documents_in(data):
                check(str(path.relative_to(ROOT)), doc)
        for path in sorted(root.rglob("*.py")):
            for line, doc in _python_literals(path):
                check(f"{path.relative_to(ROOT)}:{line}", doc)
    assert found == []
    # pre-registered floor: the 32 example JSON files, the 55 fixtures and the built-ins at least
    assert checked >= 100, checked


def test_the_geometry_adapters_write_format_0_3_parts():
    """sipi.geometry_v1 and meshine.geometry_v1 write format 0.3 parts: with the envelope a user
    adds, no units block and no suffixed key, and every path of the geometry and mesh parts
    matches exactly one slot (P2-12)."""
    pytest.importorskip("sipi")
    import meshine.geometry_v1 as meshine_v1
    import sipi.geometry_v1 as sipi_v1
    from meshine import shapes
    from sipi import templates
    from test_slots import _closed
    outs = {
        "sipi microstrip": sipi_v1.to_geometry_v1(templates.microstrip(width=0.3e-3, substrate_height=0.2e-3,
                                                                       eps_r=4.3, thickness=35e-6)),
        "sipi masked": sipi_v1.to_geometry_v1(templates.with_surface_mask(
            templates.microstrip(width=0.3e-3, substrate_height=0.2e-3, eps_r=4.3, thickness=35e-6),
            thickness=20e-6, eps_r=3.5)),
        "meshine rib": meshine_v1.to_geometry_v1(shapes.rib_waveguide(slab_thickness=0.3, size_core=0.1,
                                                                      size_far=0.6)[0], length_unit="um"),
        "meshine fiber": meshine_v1.to_geometry_v1(shapes.circular_fiber(core_radius=1.0, domain_radius=4.0,
                                                                         size_core=0.2), length_unit="um"),
    }
    for label, out in outs.items():
        assert "units" not in out, label
        parts = {"openphysics": "0.3", **{k: out[k] for k in ("geometry", "mesh", "materials") if k in out}}
        assert _problems(parts) == [], label
        closed = {"openphysics": "0.3", **{k: out[k] for k in ("geometry", "mesh") if k in out}}
        assert _closed(closed, label) > 10, label


def test_the_suffix_check_finds_a_0_2_key_and_skips_chosen_names():
    doc = {"openphysics": "0.3", "materials": {"low_k": {"thermal_conductivity": "1 W/(m K)"}},
           "physics": {"heat_m": {"type": "thermal.steady2d"}}}
    assert _problems(doc) == []
    doc["physics"]["heat_m"]["conductivity_w_mk"] = 1.0
    doc["physics"]["heat_m"]["temperature_k"] = 300.0
    assert _problems(doc) == ["suffixed keys ['temperature_k']"]
    assert _problems({"openphysics": "0.2", "units": {"length": "m"}})[:2] == ['"openphysics": "0.2"', "a units block"]


# ---- P2-11 over every shipped example -------------------------------------------------------------

UNIT_TOKEN = re.compile(r"_(k|m|s|w|j|jk|pa|deg|m2|um|nm|hz|v|a|w_m2|w_mk|w_m3|w_m2k|j_m3k|s_m|s_per_m|n_m3|"
                        r"per_m|db_cm|db_90deg)$")
#: arrays without a registry quantity: connectivity, ids, region and edge tables, text and JSON
#: blocks; the union of the per-family structural lists, closed
STRUCTURAL = {"triangles", "tetrahedra", "regions", "region_names", "triangle_regions", "edges", "tet_edges",
              "edge_orientation", "edge_signs", "pec_edge_ids", "wall_names", "prescribed_node_ids",
              "prescribed_components", "electric_prescribed_node_ids", "thermal_prescribed_node_ids", "field_layout",
              "result_format", "metadata_json", "field_representation", "mode_tracking_json", "open_boundary_json",
              "study_parameter", "frame_transform", "cluster_ids", "cluster_offsets", "cluster_completeness",
              "mode_count_policy", "normalization", "search", "electric_field_location"}
#: summary maps keyed by names the document chooses (materials, regions, terminals)
SUMMARY_NAMED = {"materials", "outward_current_per_depth", "outward_current"}
EXAMPLES = sorted((ROOT / "examples" / "simcase").glob("*.json"))


def _keys(tree, skip=("resolved_inputs", "regions", "defaults_applied", "diagnostics"), named=False):
    """The summary's own keys (a name the document chooses is skipped, its value is not)."""
    if isinstance(tree, dict):
        for key, value in tree.items():
            if not named:
                yield key
            if key not in skip:
                yield from _keys(value, skip, named=key in SUMMARY_NAMED and not named)
    elif isinstance(tree, list):
        for item in tree:
            yield from _keys(item, skip)


def _echoed_quantities(tree, skip=("resolved_inputs", "defaults_applied", "diagnostics", "field_units",
                                   "field_shapes", "regions")):
    """``(key, value object)`` of every summary entry written as ``{"value"|"values"|"re", "unit"}``."""
    if isinstance(tree, dict):
        for key, value in tree.items():
            if key in skip:
                continue
            if isinstance(value, dict) and "unit" in value and {"value", "values", "re"} & set(value):
                yield key, value
            else:
                yield from _echoed_quantities(value, skip)
    elif isinstance(tree, list):
        for item in tree:
            yield from _echoed_quantities(item, skip)


def _vtu_names(folder: Path) -> set:
    names = set()
    for vtu in folder.rglob("*.vtu"):
        names |= set(re.findall(r'<DataArray[^>]*\bName="([^"]+)"', vtu.read_text(encoding="utf-8", errors="replace")))
    return names


@pytest.fixture(scope="module")
def saved_examples(tmp_path_factory):
    from simcase import Document, export, run
    out = {}
    for path in EXAMPLES:
        data = json.loads(path.read_text(encoding="utf-8"))
        data["results"] = dict(data.get("results") or {}, plots=False)
        result = run(Document.from_dict(copy.deepcopy(data)), verbose=False)
        folder = result.save(tmp_path_factory.mktemp(path.stem) / "out")
        summary = json.loads((folder / "summary.json").read_text(encoding="utf-8"))
        arrays = []
        vtu = set()
        if (folder / "fields.npz").exists():
            with np.load(folder / "fields.npz", allow_pickle=False) as archive:
                arrays = list(archive.files)
            target = tmp_path_factory.mktemp(path.stem + "_vtu")
            for function, name in (("export_fields", "fields.vtu"), ("export_time_series", "series"),
                                   ("export_sweep", "sweep")):
                try:
                    getattr(export, function)(folder / "fields.npz", target / name)
                except Exception:                            # a layout this export does not take
                    continue
            vtu = _vtu_names(target)
        out[path.stem] = (data, summary, arrays, vtu)
    return out


def test_p2_11_covers_every_example(saved_examples):
    assert len(saved_examples) == len(EXAMPLES) >= 30


@pytest.mark.parametrize("name", [p.stem for p in EXAMPLES])
def test_p2_11_result_names_and_units_over_every_example(saved_examples, name):
    from simcase.export import RETIRED_LAYOUTS, SUPPORTED_LAYOUTS
    data, summary, arrays, vtu = saved_examples[name]
    names = list(_keys(summary)) + list(arrays)
    assert not [k for k in names if UNIT_TOKEN.search(k)], name
    assert not [k for k in names if k.endswith("_unit") and k != "length_unit"], name
    vtu_quantities = {n.split("_mode_")[0] for n in vtu}
    assert not [n for n in vtu if UNIT_TOKEN.search(n)], (name, sorted(vtu))
    for array, unit in summary.get("field_units", {}).items():
        quantity = units.quantity(array)
        assert unit == quantity.unit, (name, array, unit)
    assert set(arrays) - set(summary.get("field_units", {})) <= STRUCTURAL, (name, sorted(
        set(arrays) - set(summary.get("field_units", {})) - STRUCTURAL))
    types = {p.get("type") for p in data["physics"].values()}
    geometry = data["geometry"]
    axisymmetric = "version" in geometry and any(c.get("dimension") == "axisymmetric"
                                                for c in geometry["components"].values())
    if axisymmetric or types & {"em.modes2d", "em.cavity3d"}:
        assert not [k for k in names + sorted(vtu_quantities) if "_per_depth" in k], name
    if "field_layout" in summary:
        assert summary["field_layout"] not in RETIRED_LAYOUTS, name
    assert not set(RETIRED_LAYOUTS) & set(SUPPORTED_LAYOUTS)
    for key, value in _echoed_quantities(summary):
        try:
            quantity = units.quantity(key)
        except Exception:
            continue                                         # a structural or composite key, checked by its kind
        assert "result" in quantity.places, (name, key)
