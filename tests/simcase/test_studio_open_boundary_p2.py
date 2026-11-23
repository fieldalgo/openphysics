# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Open boundary in Studio (slice P2): the documents the page sends.

- The leakage case the browser check builds through the UI (a silicon substrate x -1500, y -1200,
  3000 x 700 nm under the template core: BOX 500 nm, all edges open) is P1's strip over a
  substrate; the browser compares its solver document with the fixture checked here.
- The PML check solves the run's document again with pml_strength 6 only: the same mesh (node
  coordinates and triangles identical), so each mode can be paired with the check's candidates.
"""
from __future__ import annotations

import copy
import json

import numpy as np

from open_boundary_fixtures import ALL, FIXTURES, build
from simcase import Document, run


def test_the_leakage_case_fixture_is_p1s_strip_over_a_substrate():
    expected = (FIXTURES / "optical-document-strip-substrate-open.json").read_text(encoding="utf-8")
    assert build("strip_substrate", 2, edges=ALL, single=True) == expected
    # slice T2: the page's document is P1's with the second search near 1.95, and nothing else
    searches = (FIXTURES / "optical-document-strip-substrate-open-searches.json").read_text(encoding="utf-8")
    assert build("strip_substrate", 2, edges=ALL) == searches
    two, one = json.loads(searches), json.loads(expected)
    assert two["physics"]["em1"]["pml"].pop("pml_additional_searches") == [
        {"target_effective_index": 1.95, "pml_search_mode_count": 16}]
    assert two == one and json.dumps(two) == json.dumps(one)       # the key order too


def test_the_pml_check_solves_the_same_mesh_with_strength_6():
    doc = json.loads(build("template", 2, edges=ALL))
    check = copy.deepcopy(doc)
    # slice T2: the check searches once (checkDocuments drops the run's second search)
    searches = check["physics"]["em1"]["pml"].pop("pml_additional_searches")
    check["physics"]["em1"]["pml"]["pml_strength"] = 6
    # nothing else differs
    assert {**check, "physics": {"em1": {**check["physics"]["em1"], "pml": {**check["physics"]["em1"]["pml"], "pml_strength": 3,
                                                                          "pml_additional_searches": searches}}}} == doc
    first, second = (run(Document.from_dict({**d, "results": {"plots": False}}), False) for d in (doc, check))
    assert first.triangles.shape == second.triangles.shape and first.node_coordinates.shape == second.node_coordinates.shape
    assert np.array_equal(first.triangles, second.triangles)
    assert np.array_equal(first.node_coordinates, second.node_coordinates)
    print("PML check mesh:", first.node_coordinates.shape[0], "nodes,", first.triangles.shape[0], "triangles")
