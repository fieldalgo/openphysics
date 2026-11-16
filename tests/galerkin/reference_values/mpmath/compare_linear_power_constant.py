# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Compare-only adaptive references for power/constant linear log moments.

Run in a separate environment with adjacent hash-pinned mpmath requirements.
No product imports or writes to tests. Unknown process costs are not invented.
"""
from pathlib import Path
from datetime import datetime,timezone
import json,time,hashlib,sys,platform,struct,tempfile
import mpmath as mp

def source(z):
 def A(w):return w*(mp.log(w)-1) if w else 0
 zero=mp.re(A(z+1)-A(z))
 if not z:one=mp.mpf('.5')
 elif z==-1:one=-mp.mpf('.5')
 else:one=mp.re(z+mp.mpf('.5')-z*(z+1)*(mp.log(z+1)-mp.log(z)))
 return zero,one

def reference(row,dps):
 with mp.workdps(dps):
  a,b,o=[mp.mpc(*(float(x) for x in row[k])) for k in ('first','second','offset')];p=mp.mpf(float(row['p']));cache={}
  def evaluate(t,i,j):
   u=t**(1/p)
   if t not in cache:
    zero,one=source((o-u*a)/b);cache[t]=[mp.log(abs(b))+zero,mp.sqrt(3)*one]
   factor=1 if i==0 else mp.sqrt(p*(p+2))*((p+1)/p*u-1)
   return factor*cache[t][j]
  return [[mp.quad(lambda t:evaluate(t,i,j),[0,mp.mpf('.25'),mp.mpf('.75'),1]) for j in range(2)] for i in range(2)]

def main():
    if mp.__version__ != "1.3.0":
        raise RuntimeError("requires exact hash-pinned mpmath1.3.0")
    path=Path(__file__).with_name("linear_power_constant_log.json")
    original=path.read_bytes();record=json.loads(original)
    start=time.perf_counter();started=datetime.now(timezone.utc).isoformat()
    source_values=[];self_checks=[]
    for x,y in record["inputs"]["source_points"]:
        with mp.workdps(80):
            z=mp.mpc(float(x),float(y));center=-mp.mpf(float(x));radius=abs(mp.mpf(float(y)))
            breaks=[0,1]
            if 0<center<=1:
                breaks=sorted(set([mp.mpf(0),mp.mpf(1)]+[v for v in (center-radius,center,center+radius) if 0<v<1]))
            direct=mp.quad(lambda t:(2*t-1)*mp.log(abs(z+t)),breaks)
            difference=abs(direct-source(z)[1]);assert difference<mp.mpf("1e-50")
            source_values.append(float(direct));self_checks.append(mp.nstr(difference,14))
    arrays={"source_first_moment":source_values};precision=[]
    for index,row in enumerate(record["inputs"]["cases"]):
        low=reference(row,60);high=reference(row,80)
        with mp.workdps(80):
            difference=max(abs(low[i][j]-high[i][j]) for i in range(2) for j in range(2))
            assert difference<mp.mpf("1e-40")
            precision.append(mp.nstr(difference,14))
        arrays[f"block_{index:02d}"]=[[float(x) for x in line] for line in high]
    compute_s=time.perf_counter()-start
    def flatten(value):
        for x in value:
            if isinstance(x,list):yield from flatten(x)
            else:yield float(x)
    differences=[]
    for spec in record["values"]:
        actual=list(flatten(arrays[spec["name"]]));expected=list(flatten(spec["data"]))
        bits=lambda row:b"".join(struct.pack("<d",x) for x in row)
        differences.append(dict(name=spec["name"],binary64_equal=bits(actual)==bits(expected),
                                maximum_absolute_difference=max(abs(a-b) for a,b in zip(actual,expected))))
    with tempfile.TemporaryDirectory(prefix="linear-power-constant-") as temp:
        output=Path(temp)/"values.json";output.write_text(json.dumps(arrays,allow_nan=False),encoding="utf-8")
        numeric_sha=hashlib.sha256(output.read_bytes()).hexdigest()
    assert path.read_bytes()==original
    product_loaded=any(n.split(".")[0] in {"galerkin","sipi","meshine","simcase"} for n in sys.modules)
    assert not product_loaded
    report=dict(generated_utc=started,generator_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                mpmath=mp.__version__,python=platform.python_version(),os=platform.platform(),machine=platform.machine(),
                compute_s=compute_s,wall_time_s=time.perf_counter()-start,product_loaded=product_loaded,
                differences=differences,source_identity_differences=self_checks,block_precision_differences=precision,
                record_before_sha256=hashlib.sha256(original).hexdigest(),temporary_numeric_sha256=numeric_sha,
                temporary_output_removed=not Path(temp).exists())
    print(json.dumps(report,indent=2,allow_nan=False))
    return 0 if all(x["binary64_equal"] for x in differences) else 1


if __name__=="__main__":
    raise SystemExit(main())
