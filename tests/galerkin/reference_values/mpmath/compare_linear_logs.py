# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Compare pinned high-precision reproductions; never rewrite stored inputs/values.

Run from the repository root after installing the adjacent hash-pinned
requirements. Only mpmath and the standard library are imported. Temporary
numeric output is removed on exit; stdout contains measured provenance and
per-array differences. A differing binary64 value is a nonzero exit.
"""

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import struct
import sys
import tempfile
import time

import mpmath as mp


def far(row, dps):
    with mp.workdps(dps):
        a, b, o = [mp.mpc(*(float(x) for x in row[k]))
                   for k in ("first", "second", "offset")]
        p, q = mp.mpf(float(row["p"])), mp.mpf(float(row["q"]))

        def moment(power, mode, k):
            if mode == 0:
                return power / (power + k)
            return mp.sqrt(power * (power + 2)) * k / ((power + k) * (power + k + 1))

        values = []
        for i in range(2):
            values.append([])
            for j in range(2):
                terms = [mp.re(mp.fsum(
                    mp.binomial(k, r) * (a / o)**r * (-b / o)**(k - r)
                    * moment(p, i, r) * moment(q, j, k - r)
                    for r in range(k + 1))) / k for k in range(1, 101)]
                values[i].append((mp.log(abs(o)) if i == j == 0 else 0) - mp.fsum(terms))
        rho = (abs(a) + abs(b)) / abs(o)
        assert rho <= mp.mpf(".25")
        tail = 16 * rho**101 / (101 * (1 - rho))
        assert tail < mp.mpf("1e-40")
        return values


def vertex(row, dps):
    with mp.workdps(dps):
        a, b = [mp.mpc(*(float(x) for x in row[k])) for k in ("first", "second")]
        p, q = mp.mpf(float(row["p"])), mp.mpf(float(row["q"]))

        def average(power, exponent, fun):
            return mp.quad(lambda t: (t**(1 / power))**exponent * fun(t**(1 / power)),
                           [0, mp.mpf(".25"), mp.mpf(".75"), 1])

        x = [average(q, s, lambda v: mp.log(abs(a - v * b))) for s in range(2)]
        y = [average(p, r, lambda u: mp.log(abs(u * a - b))) for r in range(2)]
        moments = [[(p*x[s] + q*y[r] - p*q/((p+r)*(q+s))) / (p+q+r+s)
                    for s in range(2)] for r in range(2)]
        lp, lq = mp.sqrt(p*(p+2)), mp.sqrt(q*(q+2))
        left = [[1, 0], [-lp, lp*(p+1)/p]]
        right = [[1, 0], [-lq, lq*(q+1)/q]]
        return [[mp.fsum(left[i][r]*right[j][s]*moments[r][s]
                         for r in range(2) for s in range(2))
                 for j in range(2)] for i in range(2)]


def binary64(matrix):
    return b"".join(struct.pack("<d", float(x)) for row in matrix for x in row)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("kind", choices=("far", "vertex"))
    args = parser.parse_args()
    if mp.__version__ != "1.3.0":
        raise RuntimeError("requires the exact hash-pinned mpmath 1.3.0 wheel")
    path = Path(__file__).with_name(f"linear_{args.kind}_log.json")
    original = path.read_bytes()
    record = json.loads(original)
    started = datetime.now(timezone.utc).isoformat()
    start = time.perf_counter()
    values, differences = [], []
    for index, row in enumerate(record["inputs"]["cases"]):
        low = globals()[args.kind](row, 60)
        high = globals()[args.kind](row, 80)
        with mp.workdps(80):
            disagreement = max(abs(low[i][j]-high[i][j]) for i in range(2) for j in range(2))
            assert disagreement < mp.mpf("1e-40")
        actual = [[float(x) for x in line] for line in high]
        name = f"case_{index:02d}"
        expected = next(v["data"] for v in record["values"] if v["name"] == name)
        values.append({"name": name, "data": actual})
        differences.append({"name": name,
                            "binary64_equal": binary64(actual) == binary64(expected),
                            "maximum_absolute_difference": max(abs(actual[i][j]-expected[i][j])
                                                               for i in range(2) for j in range(2)),
                            "precision_difference": mp.nstr(disagreement, 12)})
    compute_s = time.perf_counter() - start
    with tempfile.TemporaryDirectory(prefix="linear-log-reference-") as temp:
        output = Path(temp) / "values.json"
        output.write_text(json.dumps(values, allow_nan=False), encoding="utf-8")
        numeric_sha = hashlib.sha256(output.read_bytes()).hexdigest()
    assert path.read_bytes() == original
    product_loaded = any(n.split(".")[0] in {"galerkin", "sipi", "meshine", "simcase"}
                         for n in sys.modules)
    assert not product_loaded
    report = {"kind": args.kind, "generated_utc": started,
              "generator_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              "record_before_sha256": hashlib.sha256(original).hexdigest(),
              "temporary_numeric_sha256": numeric_sha,
              "mpmath": mp.__version__, "python": platform.python_version(),
              "os": platform.platform(), "machine": platform.machine(),
              "compute_s": compute_s, "wall_time_s": time.perf_counter()-start,
              "product_loaded": product_loaded, "differences": differences,
              "temporary_output_removed": not Path(temp).exists()}
    print(json.dumps(report, indent=2, allow_nan=False))
    return 0 if all(x["binary64_equal"] for x in differences) else 1


if __name__ == "__main__":
    raise SystemExit(main())
