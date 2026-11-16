# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Compare-only high-precision direct tensor integrals; never writes fixtures.

Use the adjacent hash-pinned mpmath requirements in a separate environment.
Print differences and measured provenance; any changed binary64 value exits
nonzero. No product module or product centering algorithm is used.
"""
from pathlib import Path
from functools import lru_cache
from datetime import datetime, timezone
import hashlib
import json
import platform
import struct
import sys
import tempfile
import time
import mpmath as mp

@lru_cache(maxsize=64)
def rule(power,n,dps):
 with mp.workdps(dps):
  p=mp.mpf(float(power));x,w=mp.gauss_quadrature(n,'jacobi',alpha=0,beta=p-1)
  u=[(v+1)/2 for v in x];weights=[v*p/2**p for v in w]
  assert abs(mp.fsum(weights)-1)<mp.mpf('1e-'+str(dps-10))
  return u,weights

def reference(row,n,dps):
 with mp.workdps(dps):
  a,b,o=[mp.mpc(*(float(x) for x in row[k])) for k in ('first','second','offset')]
  p,q=mp.mpf(float(row['p'])),mp.mpf(float(row['q']))
  u,w=rule(row['p'],n,dps);v,z=rule(row['q'],n,dps)
  left=[w,[weight*mp.sqrt(p*(p+2))*((p+1)/p*x-1) for x,weight in zip(u,w)]]
  right=[z,[weight*mp.sqrt(q*(q+2))*((q+1)/q*x-1) for x,weight in zip(v,z)]]
  kernel=[[mp.log(abs(x*a-o-y*b)) for y in v] for x in u]
  return [[mp.fsum(left[i][r]*kernel[r][s]*right[j][s] for r in range(n) for s in range(n)) for j in range(2)] for i in range(2)]

def main():
    if mp.__version__ != "1.3.0":
        raise RuntimeError("requires the exact hash-pinned mpmath 1.3.0 wheel")
    path = Path(__file__).with_name("linear_separated_log.json")
    original = path.read_bytes()
    record = json.loads(original)
    started = datetime.now(timezone.utc).isoformat()
    start = time.perf_counter()
    rows = []
    for index, row in enumerate(record["inputs"]["cases"]):
        low = reference(row,48,60)
        medium = reference(row,64,60)
        high = reference(row,64,80)
        with mp.workdps(80):
            order_delta = max(abs(low[i][j]-medium[i][j]) for i in range(2) for j in range(2))
            precision_delta = max(abs(medium[i][j]-high[i][j]) for i in range(2) for j in range(2))
            assert order_delta < mp.mpf("1e-25")
            assert precision_delta < mp.mpf("1e-45")
        actual = [[float(x) for x in line] for line in high]
        name = f"case_{index:02d}"
        expected = next(v["data"] for v in record["values"] if v["name"] == name)
        def bits(matrix):
            return b"".join(struct.pack("<d", float(x)) for line in matrix for x in line)
        rows.append({"name": name, "binary64_equal": bits(actual) == bits(expected),
                     "maximum_absolute_difference": max(abs(actual[i][j]-expected[i][j]) for i in range(2) for j in range(2)),
                     "order_difference": mp.nstr(order_delta,14),
                     "precision_difference": mp.nstr(precision_delta,14), "data": actual})
    compute_s = time.perf_counter()-start
    with tempfile.TemporaryDirectory(prefix="linear-separated-reference-") as temp:
        output = Path(temp)/"values.json"
        output.write_text(json.dumps(rows,allow_nan=False),encoding="utf-8")
        numeric_sha = hashlib.sha256(output.read_bytes()).hexdigest()
    assert path.read_bytes() == original
    product_loaded = any(n.split(".")[0] in {"galerkin","sipi","meshine","simcase"} for n in sys.modules)
    assert not product_loaded
    report = {"generated_utc":started,"generator_sha256":hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              "mpmath":mp.__version__,"python":platform.python_version(),"os":platform.platform(),
              "machine":platform.machine(),"compute_s":compute_s,"wall_time_s":time.perf_counter()-start,
              "product_loaded":product_loaded,"differences":rows,"temporary_numeric_sha256":numeric_sha,
              "record_before_sha256":hashlib.sha256(original).hexdigest(),"temporary_output_removed":not Path(temp).exists()}
    print(json.dumps(report,indent=2,allow_nan=False))
    return 0 if all(x["binary64_equal"] for x in rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
