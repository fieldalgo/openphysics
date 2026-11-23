# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""``pml.pml_additional_searches``: further open-boundary searches beside the primary one, merged
on one mesh and pencil, de-duplicated and selected by descending Re n_eff (slice T1).

The checks W1 to W8 were registered before the implementation; W1, W4 and W6 were measured
offline on the adopted draft, the rest are blind (docs/packages/simcase/pml_modes.md).
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

import numpy as np
import pytest

from open_boundary_fixtures import TOP_BOTTOM, build, db_per_cm, reference_modes, slab_reference
from simcase import Document, DocumentError, run
from simcase.physics_pml_modes import DUPLICATE_RULE, _merge

ROOT = Path(__file__).resolve().parents[2]
P = "physics.em1."
KEY = P + "pml.pml_additional_searches"
DEFAULT = [{"target_effective_index": 1.95, "pml_search_mode_count": 16}]
#: P1's union reference of the strip over a substrate (fixtures ``reference_modes``, 2.46/32 and 1.95/32),
#: as rounded in the record; the tests compare with the reference solves themselves
TE_LIKE, TM_LIKE, NEAR_CLADDING = 2.441263, 1.772790, 1.486427 + 7.92e-3j


def leaky(searches=DEFAULT, **physics):
    data = json.loads((ROOT / "examples" / "simcase" / "pml_leaky_slab.json").read_text(encoding="utf-8"))
    if searches is not None:
        data["physics"]["em1"]["pml"]["pml_additional_searches"] = searches
    data["physics"]["em1"].update(physics)
    data["results"] = {"plots": False}
    return data


def refused(data):
    with pytest.raises(DocumentError) as caught:
        Document.loads(data) if isinstance(data, str) else Document.from_dict(data)
    return caught.value


# -- the contract ------------------------------------------------------------------------------------

def test_the_key_is_echoed_and_handed_to_the_kernel():
    from simcase import modes_document
    doc = Document.from_dict(leaky([{"target_effective_index": 2.0, "pml_search_mode_count": 8},
                                    {"target_effective_index": 1.5, "pml_search_mode_count": 4}]))
    echo = doc.resolved_inputs()
    assert echo[KEY + "[0].target_effective_index"]["value"] == 2.0
    assert echo[KEY + "[1].pml_search_mode_count"]["value"] == 4
    pml = modes_document.kernel_document(doc).data["physics"]["em1"]["pml"]
    assert pml["additional_searches"] == [{"n_target": 2.0, "search_count": 8}, {"n_target": 1.5, "search_count": 4}]


@pytest.mark.parametrize("searches,where,code", [
    ([], KEY, "E-CONTRACT"),
    ([{"target_effective_index": 1.0 + i, "pml_search_mode_count": 4} for i in range(4)], KEY, "E-CONTRACT"),
    ([{"pml_search_mode_count": 4}], KEY + "[0].target_effective_index", "E-CONTRACT"),
    ([{"target_effective_index": 2.0}], KEY + "[0].pml_search_mode_count", "E-CONTRACT"),
    ([{"target_effective_index": 0, "pml_search_mode_count": 4}], KEY + "[0].target_effective_index", "E-DOMAIN"),
    ([{"target_effective_index": -1.5, "pml_search_mode_count": 4}], KEY + "[0].target_effective_index",
     "E-DOMAIN"),
    ([{"target_effective_index": 2.852, "pml_search_mode_count": 4}], KEY + "[0].target_effective_index",
     "E-CONTRACT"),
    ([{"target_effective_index": 2.0, "pml_search_mode_count": 4},
      {"target_effective_index": 2.0, "pml_search_mode_count": 8}], KEY + "[1].target_effective_index",
     "E-CONTRACT"),
    ([{"target_effective_index": 2.0, "pml_search_mode_count": 0}], KEY + "[0].pml_search_mode_count",
     "E-DOMAIN"),
    ([{"target_effective_index": 2.0, "pml_search_mode_count": 65}], KEY + "[0].pml_search_mode_count",
     "E-DOMAIN"),
    ([{"target_effective_index": 2.0, "pml_search_mode_count": 4, "pml_strength": 2}],
     KEY + "[0].pml_strength", "E-KEY-UNKNOWN"),
])
def test_refusals_name_the_key(searches, where, code):
    error = refused(leaky(searches))
    assert (error.path, error.code) == (where, code), (error.path, error.code, str(error))


def test_targets_compare_as_exact_decimals():
    text = json.dumps(leaky([{"target_effective_index": 2.0, "pml_search_mode_count": 4}]))
    error = refused(text.replace('"target_effective_index": 2.0,', '"target_effective_index": 2.8520,'))
    assert (error.path, error.code) == (KEY + "[0].target_effective_index", "E-CONTRACT")
    # a decimal that rounds to the same double is another target
    Document.loads(text.replace('"target_effective_index": 2.0,', '"target_effective_index": 2.85200000000000001,'))


def test_a_count_need_not_hold_mode_count():
    Document.from_dict(leaky([{"target_effective_index": 2.0, "pml_search_mode_count": 1}], mode_count=2))


def test_a_sweep_is_refused_and_a_bend_allowed():
    data = leaky()
    data["study"] = {"type": "sweep", "parameter": P + "vacuum_wavelength",
                     "values": {"unit": "um", "values": [1.54, 1.55, 1.56]}}
    error = refused(data)
    assert (error.path, error.code) == (KEY, "E-CONTRACT")
    assert "pml_additional_searches is not read with a study sweep in this release; give one target" in str(error)
    bent = json.loads((ROOT / "examples" / "simcase" / "pml_bent_slab.json").read_text(encoding="utf-8"))
    bent["physics"]["em1"]["pml"]["pml_additional_searches"] = [{"target_effective_index": 1.2,
                                                                 "pml_search_mode_count": 4}]
    Document.from_dict(bent)


def test_the_scalar_formulation_is_refused():
    data = leaky(formulation="scalar")
    del data["physics"]["em1"]["effective_index_threshold"]
    error = refused(data)
    assert (error.path, error.code) == (KEY, "E-CONTRACT")


# -- the merge, on synthetic candidates ----------------------------------------------------------------

def _gram(et):
    """<a, b> with the identity as the mass matrix."""
    return et.conj() @ et.T


def _records(n):
    return [dict(candidate=i + 1, reasons=[], selected=False) for i in range(len(n))]


def test_merge_marks_a_repeated_mode_and_keeps_a_near_distinct_one():
    rng = np.random.default_rng(1)
    a, b, c = rng.normal(size=(3, 40)) + 1j * rng.normal(size=(3, 40))
    n = np.array([2.0 + 1e-4j, 1.5, 2.0 + 1e-4j + 5e-10, 1.5 + 4.3e-7])
    et = np.stack([a, b, 0.3j * a + 1e-4 * c, c])                  # 3 repeats 1; 4 is near 2, another field
    records = _records(n)
    keep = _merge(records, [0, 1, 2, 3], n, _gram(et), np.array([1, 1, 2, 2]), 8)
    assert keep.tolist() == [0, 3, 1]                              # descending Re n_eff
    assert records[2]["reasons"] == ["duplicate_candidate"] and records[2]["duplicate_of"] == 1
    assert records[2]["duplicate_field_overlap"] >= DUPLICATE_RULE["field_overlap"]
    assert records[2]["duplicate_effective_index_distance"] <= 1e-9 * 2
    assert "duplicate_of" not in records[3] and records[3]["reasons"] == ["selected_descending_real_index"]
    assert [r["search"] for r in records] == [1, 1, 2, 2]


def test_merge_compares_ineligible_candidates_and_keeps_their_reasons():
    rng = np.random.default_rng(2)
    a = rng.normal(size=40) + 1j * rng.normal(size=40)
    n = np.array([2.0, 2.0])
    records = _records(n)
    records[0]["reasons"], records[1]["reasons"] = ["pencil_residual"], ["pencil_residual"]
    with_ineligible = _merge(records, [], n, _gram(np.stack([a, a])), np.array([1, 2]), 1)
    assert with_ineligible.tolist() == []
    assert records[1]["reasons"] == ["pencil_residual", "duplicate_candidate"]


def test_merge_degenerate_span():
    """Two earlier candidates within the index tolerance: b is a duplicate when its projection on their
    span holds >= 0.99 of its squared norm, although its overlap with each is below 0.99."""
    rng = np.random.default_rng(3)
    a1, a2, c = rng.normal(size=(3, 60)) + 1j * rng.normal(size=(3, 60))
    n = np.array([2.0, 2.0 + 1e-12, 2.0 + 2e-12, 2.0 + 3e-12])
    inside = (a1 + 0.8j * a2) / 2
    outside = a1 + a2 + 2 * c
    records = _records(n)
    et = np.stack([a1, a2, inside, outside])
    keep = _merge(records, [0, 1, 2, 3], n, _gram(et), np.array([1, 1, 2, 2]), 8)
    assert records[2]["duplicate_span"] == [1, 2] and records[2]["duplicate_field_overlap"] >= 0.99 ** 0.5
    assert max(abs(_gram(et)[i, 2]) / np.sqrt(_gram(et)[i, i].real * _gram(et)[2, 2].real) for i in (0, 1)) < 0.99
    assert "duplicate_of" not in records[3]
    assert sorted(keep.tolist()) == [0, 1, 3]


# -- the record ------------------------------------------------------------------------------------

def test_the_record_with_and_without_the_key():
    plain = run(Document.from_dict(leaky(None)), False).summary()
    assert plain["selection"] == "pml_heuristic_near_target"
    block = plain["open_boundary"][0]
    assert block["schema"] == "openphysics.pml-candidates/2"
    assert not {"searches", "selection", "duplicate_rule"} & set(block)
    assert all("search" not in c for c in block["candidates"])
    merged = run(Document.from_dict(leaky([{"target_effective_index": 2.0, "pml_search_mode_count": 8}])),
                 False).summary()
    assert merged["selection"] == "pml_heuristic_descending_real_index"
    assert merged["mode_result_schema"] == plain["mode_result_schema"] == "openphysics.modes2d/3"
    block = merged["open_boundary"][0]
    assert block["schema"] == "openphysics.pml-candidates/3"
    assert block["selection"] == "descending_real_index"
    assert block["duplicate_rule"] == {"effective_index_distance": 1e-9, "field_overlap": 0.99,
                                       "overlap_metric": "computational_transverse_electric_l2",
                                       "degenerate_span": 0.99}
    first, second = block["searches"]
    assert first == {"search": 1, "target_effective_index": 2.852, "search_mode_count": 6, "candidate_count": 6}
    assert second["search"] == 2 and second["target_effective_index"] == 2.0 and second["search_mode_count"] == 8
    assert len(block["candidates"]) == 6 + second["candidate_count"]
    assert [c["search"] for c in block["candidates"]] == [1] * 6 + [2] * second["candidate_count"]
    eligible = [c for c in block["candidates"] if c["reasons"] in (["selected_descending_real_index"],
                                                                     ["outside_requested_count"])]
    best = max(eligible, key=lambda c: c["effective_index"]["re"])
    assert block["selected_candidates"] == [best["candidate"]]
    assert merged["resolved_inputs"][KEY + "[0].target_effective_index"]["value"] == 2.0


# -- W1 to W8: Studio's documents (slow) -------------------------------------------------------------

def _run(d, searches=DEFAULT, **pml):
    d = copy.deepcopy(d)
    d["results"] = {"plots": False}
    if searches is not None:
        d["physics"]["em1"]["pml"]["pml_additional_searches"] = searches
    d["physics"]["em1"]["pml"].update(pml)
    r = run(Document.from_dict(d), False)
    return r.effective_index[0], r.propagation_loss()[0] / 100, r.open_boundary[0]


def _check_merge(block, n):
    """W3a and W3b on one result: no returned pair is a duplicate pair by index and every eligible
    candidate is returned, outside the count, or a duplicate of one of those."""
    candidates = {c["candidate"]: c for c in block["candidates"]}
    value = {k: complex(c["effective_index"]["re"], c["effective_index"]["im"]) for k, c in candidates.items()}
    returned = block["selected_candidates"]
    for i, a in enumerate(returned):
        for b in returned[i + 1:]:
            assert candidates[b]["search"] == candidates[a]["search"] or abs(value[b] - value[a]) > \
                DUPLICATE_RULE["effective_index_distance"] * max(1, abs(value[a])), (a, b)
    kept = {k for k, c in candidates.items()
            if c["reasons"] in (["selected_descending_real_index"], ["outside_requested_count"])}
    for k, c in candidates.items():
        if "duplicate_of" in c:
            a = c["duplicate_of"]
            assert candidates[a]["search"] < c["search"] and "duplicate_of" not in candidates[a]
            assert c["duplicate_effective_index_distance"] <= 1e-9 * max(1, abs(value[a]))
            assert abs(value[k] - value[a]) <= 1e-9 * max(1, abs(value[a]))
            assert c["duplicate_field_overlap"] >= 0.99 ** (0.5 if "duplicate_span" in c else 1)
            if c["reasons"] == ["duplicate_candidate"]:            # eligible: W3b, nothing lost
                assert a in kept, (k, a)
    assert sorted(value[k].real for k in returned)[::-1] == [value[k].real for k in returned]
    assert np.array_equal(n, [value[k] for k in returned])


def _union(text):
    union = []
    for target in (2.46, 1.95):
        for z in reference_modes(text, target):
            if not union or np.min(abs(np.asarray(union) - z)) > 1e-6:
                union.append(z)
    return sorted(union, key=lambda z: -z.real)


@pytest.mark.slow
def test_w1_strip_over_substrate_returns_the_mode_near_the_cladding():
    text = build("strip_substrate", 8)
    union = _union(text)
    assert len(union) == 3
    for z, rounded in zip(union, (TE_LIKE, TM_LIKE, NEAR_CLADDING)):
        assert abs(z.real - rounded.real) <= 5e-7 and abs(z.imag - rounded.imag) <= 5e-5, (z, rounded)
    n, _, block = _run(json.loads(text))
    _check_merge(block, n)
    for z in union:                                    # every mode, no known miss
        assert np.min(abs(n - z)) <= 1e-6, (z, n)
    two, _, block = _run(json.loads(build("strip_substrate", 2)))
    _check_merge(block, two)
    assert len(two) == 2 and abs(two[0] - union[0]) <= 1e-6 and abs(two[1] - union[1]) <= 1e-6, (two, union)


def _core(kind, w, h):
    d = json.loads(build(kind, 2))
    core = next(s for s in d["geometry"]["shapes"] if s["name"] == "Core")
    core.update(x=f"{-w / 2:g} nm", w=f"{w} nm", h=f"{h} nm")
    return d


@pytest.mark.slow
def test_w4_the_wide_core_is_ranked_by_descending_real_index():
    wide = _core("template", 700, 300)
    for count, expected in ((1, [2.8545]), (2, [2.8545, 2.4511])):
        wide["physics"]["em1"]["mode_count"] = count
        n, _, block = _run(wide)
        _check_merge(block, n)
        assert np.round(n.real, 4).tolist() == expected, n


@pytest.mark.slow
def test_w3b_the_square_core_returns_both_members_of_its_pair():
    """The pair is the two highest eligible candidates of the primary search alone (2.46/32)."""
    square = _core("template", 400, 400)
    single, _, alone = _run(square, searches=None)
    pair = sorted((complex(c["effective_index"]["re"], c["effective_index"]["im"]) for c in alone["candidates"]
                   if c["reasons"] in (["selected_near_target"], ["outside_requested_count"])),
                  key=lambda z: -z.real)[:2]
    n, _, block = _run(square)
    _check_merge(block, n)
    print(f"W3b square core: pair {pair}, returned {n}")
    assert len(n) == 2 and all(np.min(abs(n - z)) <= 1e-9 for z in pair), (n, pair)


@pytest.mark.slow
@pytest.mark.parametrize("pol,target", [("TE", 2.85), ("TM", 2.06)])
def test_w4_w6_w7_the_leaky_slab_returns_the_mode_nearest_the_pole(pol, target):
    pole = slab_reference(pol)
    d = json.loads(build("slab", 1, edges=TOP_BOTTOM))
    if pol == "TM":
        d["physics"]["em1"]["boundary"].update(left="pmc", right="pmc")
    n, loss, block = _run(d)
    _check_merge(block, n)
    candidates = [complex(c["effective_index"]["re"], c["effective_index"]["im"]) for c in block["candidates"]
                  if c["reasons"] in (["selected_descending_real_index"], ["outside_requested_count"])]
    assert abs(n[0] - pole) == min(abs(z - pole) for z in candidates), (n, pole)
    print(f"W{6 if pol == 'TE' else 7} {pol}: {n[0]}, loss {loss[0]:.4f} dB/cm vs {db_per_cm(pole):.4f}")
    assert abs(loss[0] / db_per_cm(pole) - 1) <= 0.035, (loss[0], db_per_cm(pole))


@pytest.mark.slow
def test_w8_strip_over_substrate_at_three_strengths():
    base = json.loads(build("strip_substrate", 8))
    for strength in (1.5, 3, 6):
        n, _, block = _run(base, pml_strength=strength)
        _check_merge(block, n)
        tolerance = 1e-6 if strength == 3 else 5e-4           # V4a's |dRe| gate when the PML changes
        for z in (TE_LIKE, TM_LIKE) + ((NEAR_CLADDING,) if strength != 6 else ()):
            assert np.min(abs(n.real - z.real)) <= tolerance, (strength, z, n)
        print(f"W8 strength {strength}: {n}")
