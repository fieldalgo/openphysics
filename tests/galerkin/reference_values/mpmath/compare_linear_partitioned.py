# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Compare-only adaptive mixed integrals; no product imports or fixture writes.

Use hash-pinned mpmath1.3.0 in the adjacent requirements. The reference uses
the exact source identity and an independently flattened adaptive target
coordinate, not product dyadic cuts or cubic rules. Two inputs are admitted
product panel pairs. This is not an independent complete field solver.
"""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,platform,struct,sys,tempfile,time
import mpmath as mp

def source(z):
    def primitive(w):return w*(mp.log(w)-1) if w else mp.mpf(0)
    zero=mp.re(primitive(z+1)-primitive(z))
    if not z:one=mp.mpf('.5')
    elif z==-1:one=-mp.mpf('.5')
    else:one=mp.re(z+mp.mpf('.5')-z*(z+1)*(mp.log(z+1)-mp.log(z)))
    return zero,one

def reference(row,digits):
    with mp.workdps(digits):
        a,b,o=[mp.mpc(*(float(x) for x in row[k])) for k in ('a','b','offset')];p=mp.mpf(float(row['p']))
        cuts=[mp.mpf(0),mp.mpf(1)]
        for endpoint in (o,o+b):
            point=endpoint/a;center=min(mp.mpf(1),max(mp.mpf(0),point.real));distance=abs(point-center)
            cuts.append(center)
            for multiple in (1,8,64):
                for cut in (center-distance*multiple,center+distance*multiple):
                    if 0<cut<1:cuts.append(cut)
        breaks=sorted(set(x**p for x in cuts));cache={}
        def value(t,i,j):
            u=t**(1/p)
            if t not in cache:
                k0,k1=source((o-u*a)/b);cache[t]=(mp.log(abs(b))+k0,mp.sqrt(3)*k1)
            mode=mp.mpf(1) if i==0 else mp.sqrt(p*(p+2))*((p+1)/p*u-1)
            return mode*cache[t][j]
        return [[mp.quad(lambda t:value(t,i,j),breaks) for j in range(2)] for i in range(2)]


def main():
    if mp.__version__!='1.3.0': raise RuntimeError('requires hash-pinned mpmath1.3.0')
    path=Path(__file__).with_name('linear_partitioned_log.json');original=path.read_bytes();record=json.loads(original)
    start=time.perf_counter();started=datetime.now(timezone.utc).isoformat();arrays={};agreement=[]
    for index,row in enumerate(record['inputs']['cases']):
        low=reference(row,60);high=reference(row,80)
        with mp.workdps(80):
            difference=max(abs(low[i][j]-high[i][j]) for i in range(2) for j in range(2))
            assert difference<mp.mpf('1e-40');agreement.append(mp.nstr(difference,14))
        arrays[f'block_{index:02d}']=[[float(x) for x in line] for line in high]
    compute_s=time.perf_counter()-start;differences=[]
    for value in record['values']:
        actual=arrays[value['name']];expected=value['data'];bits=lambda a:b''.join(struct.pack('<d',v) for row in a for v in row)
        differences.append(dict(name=value['name'],binary64_equal=bits(actual)==bits(expected),maximum_absolute_difference=max(abs(a-b) for x,y in zip(actual,expected) for a,b in zip(x,y))))
    with tempfile.TemporaryDirectory(prefix='linear-partitioned-reference-') as temp:
        output=Path(temp)/'values.json';output.write_text(json.dumps(arrays,allow_nan=False),encoding='utf-8');numeric_sha=hashlib.sha256(output.read_bytes()).hexdigest()
    assert path.read_bytes()==original
    product_loaded=any(n.split('.')[0] in {'galerkin','sipi','meshine','simcase'} for n in sys.modules);assert not product_loaded
    report=dict(generated_utc=started,generator_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),mpmath=mp.__version__,python=platform.python_version(),os=platform.platform(),machine=platform.machine(),compute_s=compute_s,wall_time_s=time.perf_counter()-start,product_loaded=product_loaded,inputs_from_product=True,differences=differences,precision_differences=agreement,temporary_numeric_sha256=numeric_sha,record_before_sha256=hashlib.sha256(original).hexdigest(),temporary_output_removed=not Path(temp).exists())
    print(json.dumps(report,indent=2,allow_nan=False))
    return 0 if all(x['binary64_equal'] for x in differences) else 1


if __name__=='__main__':raise SystemExit(main())
