# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Measure the deflated vector mode search against the undeflated one (checks P2-P7, P14).

Not part of the test suite. Two ways in:

- as a pytest plugin, ``PYTHONPATH=tools python -m pytest -p static_deflation_check ...`` with
  ``STATIC_DEFLATION_LOG=<file.jsonl>``: every kernel vector solve (``_solve_modes_numpy``) runs
  deflated, as the product does, then with the fallback forced
  (``STATIC_DEFLATION_MIN_CUTOFF_DISTANCE = inf``), then forced again three times with
  ``v0 = ones + 1e-12 z |ones| / |z|``, z seeded standard normal (seeds 1, 2, 3). One JSON line per
  solve: counts, the static roots and margins of the deflated ARPACK result, and per root the
  difference d_i to the forced root and its spread s_i over the three perturbed runs;
- ``python tools/static_deflation_check.py records <out.jsonl> <case>...``: the same comparison on
  simcase records (candidates and selections), for a document path or ``c2`` (the bent slab with
  pml_search_mode_count 64);
- ``python tools/static_deflation_check.py summary <log.jsonl> [<tolerance>]``: the rule
  |d_i| <= max(tolerance, 10 s_i) per root, the branch that decided it, the count checks.

Roots are paired by order, then by nearest value. The tests stay what accepts the product;
this script only measures.
"""
from __future__ import annotations

import contextlib
import copy
import inspect
import json
import os
import sys
import time
import warnings
from pathlib import Path

import numpy as np

SEEDS = (1, 2, 3)
PERTURBATION = 1e-12
_state = {"seed": None}


def _pair(a, b):
    """Indices j(i) pairing each a[i] with b: by order when that is nearest, else the nearest unused."""
    used, pairs = set(), []
    for i, x in enumerate(a):
        if i < len(b) and i not in used and abs(x - b[i]) <= min(abs(x - y) for j, y in enumerate(b) if j not in used):
            j = i
        else:
            j = min((j for j in range(len(b)) if j not in used), key=lambda j: abs(x - b[j]))
        used.add(j); pairs.append(j)
    return pairs


def _relative(a, b):
    """Per root of b, |a - b| / |b| after pairing (None when the counts differ)."""
    a, b = np.asarray(a, complex), np.asarray(b, complex)
    if len(a) != len(b):
        return None
    out = np.zeros(len(b))
    for i, j in enumerate(_pair(b, a)):
        out[i] = abs(a[j] - b[i]) / max(abs(b[i]), 1e-300)
    return out


@contextlib.contextmanager
def _undeflated(seed=None):
    import galerkin._waveguide_kernels as K
    saved = K.STATIC_DEFLATION_MIN_CUTOFF_DISTANCE
    K.STATIC_DEFLATION_MIN_CUTOFF_DISTANCE = np.inf
    _state["seed"] = seed
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            yield
    finally:
        K.STATIC_DEFLATION_MIN_CUTOFF_DISTANCE = saved
        _state["seed"] = None


def install(log_path=None):
    """Wrap SciPy's eigs (perturbed v0 and the deflated result's statistics, for the mode search only)
    and, with ``log_path``, galerkin's vector solve (the per-solve comparison)."""
    import scipy.sparse.linalg as spla
    import galerkin._waveguide_kernels as K
    real_eigs, real_solve = spla.eigs, K._solve_modes_numpy
    last = {}

    def eigs(*args, **kwargs):
        caller = inspect.currentframe().f_back
        search = caller.f_code.co_name == "_solve_modes_numpy" and "sigma" in caller.f_locals
        if search and _state["seed"] is not None:
            v0 = np.asarray(kwargs["v0"])
            z = np.random.default_rng(_state["seed"]).standard_normal(v0.shape[0])
            kwargs["v0"] = v0 + PERTURBATION * z * (np.linalg.norm(v0) / np.linalg.norm(z))
        out = real_eigs(*args, **kwargs)
        if search:
            nu, sigma = np.asarray(out[0] if isinstance(out, tuple) else out), caller.f_locals["sigma"]
            scaled = np.abs(nu) * abs(sigma)
            last.update(deflated=caller.f_locals.get("project") is not None,
                        static=int(np.sum(np.abs(sigma + 1 / nu) <= K.STATIC_ROOT_TOL * abs(sigma))),
                        margin=float(np.min(np.abs(scaled - 1))),
                        kept=float(np.min(scaled[scaled > 1])) if np.any(scaled > 1) else None)
        return out
    spla.eigs = eigs
    if log_path is None:
        return
    log = open(log_path, "a", encoding="utf-8")

    def solve(*args, **kwargs):
        last.clear(); t = time.time()
        out = real_solve(*args, **kwargs)
        rec = dict(call=os.environ.get("PYTEST_CURRENT_TEST", "?").split(" ")[0], count=len(out[0]), **last)
        seconds = [round(time.time() - t, 2)]
        with _undeflated():
            last.clear(); t = time.time(); ref = real_solve(*args, **kwargs); ref_static = last.get("static")
        seconds.append(round(time.time() - t, 2))
        spread = []
        for seed in SEEDS:
            with _undeflated(seed):
                t = time.time(); spread.append(_relative(real_solve(*args, **kwargs)[0], ref[0]))
            seconds.append(round(time.time() - t, 2))
        rec["seconds"] = seconds   # deflated, forced, forced with seeds 1, 2, 3
        s = None if any(x is None for x in spread) else np.max(spread, axis=0)
        d = _relative(out[0], ref[0])
        rec.update(ref_count=len(ref[0]), ref_static=ref_static,
                   d=None if d is None else d.tolist(), s=None if s is None else s.tolist())
        log.write(json.dumps(rec) + "\n"); log.flush()
        return out
    K._solve_modes_numpy = solve


def pytest_configure(config):
    if os.environ.get("STATIC_DEFLATION_LOG"):
        install(os.environ["STATIC_DEFLATION_LOG"])


def _record(document, seed=None, forced=False):
    from simcase import Document, run
    d = copy.deepcopy(document)
    d.setdefault("results", {})["plots"] = False
    d["results"].pop("save_fields", None)
    with (_undeflated(seed) if forced else contextlib.nullcontext()):
        point = run(Document.from_dict(d), False).open_boundary[0]
    values = [complex(c["effective_index"]["re"], c["effective_index"]["im"]) for c in point["candidates"]]
    return point, values


def records(out_path, cases):
    """Candidates and selections of each case, deflated against the forced fallback (and its spread)."""
    install()
    with open(out_path, "a", encoding="utf-8") as log:
        for case in cases:
            if case == "c2":
                document = json.loads(Path("examples/simcase/pml_bent_slab.json").read_text(encoding="utf-8"))
                document["physics"]["em1"]["pml"]["pml_search_mode_count"] = 64
            else:
                document = json.loads(Path(case).read_text(encoding="utf-8"))
            point, values = _record(document)
            ref_point, ref = _record(document, forced=True)
            spread = [_relative(_record(document, seed, forced=True)[1], ref) for seed in SEEDS]
            s = None if any(x is None for x in spread) else np.max(spread, axis=0)
            d = _relative(values, ref)
            gain = sum(1 for c in point["candidates"] if c["effective_index"]["im"] < 0 and c["pml_l2_fraction"] >= 0.5)
            log.write(json.dumps(dict(call=case, count=len(values), ref_count=len(ref),
                                      selected=point["selected_candidates"], ref_selected=ref_point["selected_candidates"],
                                      gain_like=gain, max_residual=max(c["relative_residual"] for c in point["candidates"]),
                                      d=None if d is None else d.tolist(), s=None if s is None else s.tolist())) + "\n")
            log.flush()


def summary(path, tolerance=1e-9):
    rows = [json.loads(line) for line in open(path, encoding="utf-8")]
    failed = 0
    for r in rows:
        counts = r["count"] == r["ref_count"] and r.get("selected", 0) == r.get("ref_selected", 0)
        if not counts or r["d"] is None:
            failed += 1
            print("FAIL counts", r["call"], r["count"], r["ref_count"], r.get("selected"), r.get("ref_selected"))
            continue
        d, s = np.asarray(r["d"]), np.asarray(r["s"])
        bound = np.maximum(tolerance, 10 * s)
        ok = bool(np.all(d <= bound))
        branch = "1e-9" if np.all(d <= tolerance) else "spread"
        failed += not ok
        if branch != "1e-9" or not ok:
            print("PASS" if ok else "FAIL", branch, r["call"], "d", np.round(d, 12).tolist(), "s", np.round(s, 12).tolist())
    print(f"{len(rows)} calls; failing {failed}; decided by the spread branch: "
          f"{sum(1 for r in rows if r['d'] is not None and not np.all(np.asarray(r['d']) <= tolerance))}")
    return failed


if __name__ == "__main__":
    if sys.argv[1] == "records":
        records(sys.argv[2], sys.argv[3:])
    elif sys.argv[1] == "summary":
        sys.exit(1 if summary(sys.argv[2], float(sys.argv[3]) if len(sys.argv) > 3 else 1e-9) else 0)
