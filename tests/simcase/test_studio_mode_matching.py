# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""V15 and V15b: Studio's mode matching (workspace-match.mjs, in Node) on engine runs.

The samples are what Studio holds of a run: node_coordinates in metres, the triangles and the
complex centroid field per mode. The optical application fixes two modes, so the cases that need
more (rank changes) are engine runs fed straight into the matching function, as V13 does for the
TE fraction. The documents are the TE fraction checks' (tests/simcase/test_mode_polarization.py):
the optical template's window and PEC walls, a 220 nm tall silicon strip in silica, core
element 30 nm. Skipped without node; the .cjs suite runs the module's own checks (V14).

V15 (b) was first registered with "every accepted pair has the same polarization word on both
sides". It failed on the first run: at the 650 -> 700 nm step the second TE-like mode is matched
(eta 0.9286) from f_TE 0.8949 at 650 nm, 0.005 under the 0.9 TE-like line and so "hybrid", to
0.9308 at 700 nm, "TE-like": the same mode across a word threshold. That gate is recorded as
failed. Changed after the result was seen: every accepted pair now has |f_TE(A) - f_TE(B)| <= 0.1,
which keeps the intent (TE is never paired with TM: every TE/TM pair differs by more than 0.8).
"""
import importlib.util
import json
import shutil
import subprocess
from pathlib import Path

import numpy as np
import pytest

import simcase
from simcase import run

HERE = Path(__file__).resolve().parent
STATIC = Path(simcase.__file__).resolve().parent / "studio" / "static"
CORE = 0.03                            # core element size, um

_MATCH = r"""
import fs from 'node:fs';
const X = await import(process.argv[1]);
const M = await import(process.argv[2]);
const cases = JSON.parse(fs.readFileSync(process.argv[3], 'utf8'));
const out = cases.map(([a, b]) => {
  const m = X.matchModes(a, b);
  const fte = side => side.field.real.map((_, i) => M.teFraction(side.field, i));
  const word = side => fte(side).map(f => f === null ? null : M.polarizationWord(f));
  return {error: m.error ?? null, eta: m.eta, unitsA: m.unitsA, unitsB: m.unitsB, grid: m.grid && [m.grid.nx, m.grid.ny],
          pairs: m.pairs.map(p => ({a: p.unitA, b: p.unitB, eta: p.eta, accepted: p.accepted, rowNext: p.rowNext, columnNext: p.columnNext, delta: p.delta})),
          rows: X.compareMatchRows(m).map(r => ({kind: r.kind, text: r.text})), wordsA: word(a), wordsB: word(b), fteA: fte(a), fteB: fte(b)};
});
process.stdout.write(JSON.stringify(out));
"""


def node():
    found = shutil.which("node")
    if found is None:
        pytest.skip("node is not installed; studio_mode_matching.cjs runs in the cjs suite")
    return found


def polarization_module():
    spec = importlib.util.spec_from_file_location("mode_polarization", HERE / "test_mode_polarization.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


T = polarization_module()


def side(result, core=CORE):
    """A run as Studio's matching reads it."""
    e = result.vector_fields[0].electric.transpose(1, 0, 2)
    return {"field": {"node_coordinates": result.node_coordinates.tolist(), "triangles": result.triangles.tolist(),
                      "real": e.real.tolist(), "imag": e.imag.tolist()},
            "neff": np.real(result.effective_index[0]).tolist(), "coreSize": core * 1e-6}


def match(pairs, tmp_path):
    path = tmp_path / "pairs.json"
    path.write_text(json.dumps(pairs), encoding="utf-8")
    done = subprocess.run([node(), "--input-type=module", "-e", _MATCH, (STATIC / "workspace-match.mjs").as_uri(),
                           (STATIC / "workspace-modes.mjs").as_uri(), str(path)], capture_output=True, text=True,
                          encoding="utf-8")
    assert done.returncode == 0, done.stdout + done.stderr
    return json.loads(done.stdout)


def strip(width, mode_count):
    return run(T.strip(CORE, w=width, mode_count=mode_count), verbose=False)


def show(name, m):
    print(f"\n{name}: grid {m['grid']}")
    for p in m["pairs"]:
        print(f"  A {p['a']} <-> B {p['b']}: eta {p['eta']:.4f} (row next {p['rowNext']:.4f}, column next "
              f"{p['columnNext']:.4f}) {'accepted' if p['accepted'] else 'not accepted'}")
    for r in m["rows"]:
        print("  " + r["text"])


def check_rules(m):
    """Every accepted row has eta >= 0.8 and both margins >= 0.1; every other assigned row, and
    every unassigned mode, reads "no match" with no delta n_eff."""
    for p in m["pairs"]:
        rule = p["eta"] >= 0.8 and p["eta"] - p["rowNext"] >= 0.1 - 1e-12 and p["eta"] - p["columnNext"] >= 0.1 - 1e-12
        assert p["accepted"] == rule, p
    matched = sum(p["accepted"] for p in m["pairs"])
    assert sum(r["kind"] == "match" for r in m["rows"]) == matched
    for r in m["rows"]:
        if r["kind"] == "match":
            assert "Δn_eff" in r["text"]
        else:
            assert "no match in" in r["text"] and "Δn_eff" not in r["text"] and "best overlap" in r["text"]


@pytest.mark.slow
def test_v15_matching_on_strip_designs(tmp_path):
    # (a) 500 -> 450 nm, two modes
    a = [side(strip(0.5, 2)), side(strip(0.45, 2))]
    # (b) the scan 500 ... 1000 nm in 50 nm steps, four modes: the first step where rank 2 turns
    # from TM-like to TE-like
    widths = [round(0.5 + 0.05 * k, 2) for k in range(11)]
    scan = [side(strip(w, 4)) for w in widths]
    # (c) 300 -> 1500 nm, four modes (fewer exist at 300 nm)
    c = [side(strip(0.3, 4)), side(strip(1.5, 4))]
    steps = list(zip(scan, scan[1:]))
    results = match([a] + steps + [c], tmp_path)
    first, scanned, last = results[0], results[1:-1], results[-1]

    show("V15 (a) 500 -> 450 nm", first)
    check_rules(first)
    assert [(p["a"], p["b"]) for p in first["pairs"] if p["accepted"]] == [([0], [0]), ([1], [1])]
    assert all(p["eta"] >= 0.95 for p in first["pairs"])

    flips = [k for k, m in enumerate(scanned) if m["wordsA"][1] == "TM-like" and m["wordsB"][1] == "TE-like"]
    assert flips, "no step of the 50 nm scan turns rank 2 from TM-like to TE-like: " + str(
        [m["wordsA"] for m in scanned])
    k = flips[0]
    step = scanned[k]
    show(f"V15 (b) rank-change step {widths[k] * 1000:.0f} -> {widths[k + 1] * 1000:.0f} nm "
         f"(A {step['wordsA']}, B {step['wordsB']})", step)
    check_rules(step)
    accepted = [p for p in step["pairs"] if p["accepted"]]
    assert ([0], [0]) in [(p["a"], p["b"]) for p in accepted], "TE-like rank 1 matched to rank 1"
    assert step["wordsA"][0] == step["wordsB"][0] == "TE-like"
    assert all(not (p["a"] == [1] and p["b"] == [1]) for p in step["pairs"] if p["accepted"]), \
        "the two rank-2 modes are not paired"
    # changed after the result was seen (module docstring): the TE fractions agree within 0.1
    for p in accepted:
        for i, j in zip(p["a"], p["b"]):
            assert abs(step["fteA"][i] - step["fteB"][j]) <= 0.1, p
    tm = step["wordsA"].index("TM-like")
    assert any(p["a"] == [tm] and step["wordsB"][p["b"][0]] == "TM-like" for p in accepted), "TM-like matched to TM-like"
    for m in scanned:
        check_rules(m)

    show("V15 (c) 300 -> 1500 nm", last)
    check_rules(last)
    assert any(r["kind"] == "a" for r in last["rows"]), "at least one mode of A has no match"
    for p in last["pairs"]:
        if p["eta"] < 0.8:
            assert not p["accepted"]


@pytest.mark.slow
def test_v15b_square_pair_is_matched_as_one_unit(tmp_path):
    same = run(T.square(CORE, T.THICKNESS / 2), verbose=False)
    finer = run(T.square(0.02, T.THICKNESS / 2), verbose=False)
    moved = run(T.square(CORE, 0.2), verbose=False)
    base = side(same)
    results = match([[base, base], [base, side(finer, 0.02)], [base, side(moved)]], tmp_path)
    for name, m, floor in zip(("itself", "20 nm mesh", "grading at y = 0.2 um"), results, (1 - 1e-12, 0.95, 0.95)):
        show(f"V15b 400 x 400 nm square vs {name}", m)
        check_rules(m)
        assert m["unitsA"][0] == [0, 1] and m["unitsB"][0] == [0, 1], "the pair is formed on both sides"
        pair = next(p for p in m["pairs"] if p["a"] == [0, 1])
        assert pair["b"] == [0, 1] and pair["accepted"] and pair["eta"] >= floor, pair
    ra, rb = same.effective_index[0].real, finer.effective_index[0].real
    assert abs(results[1]["pairs"][0]["delta"] - ((rb[0] + rb[1]) / 2 - (ra[0] + ra[1]) / 2)) <= 1e-15
