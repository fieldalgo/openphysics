# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Compare-only direct integral reproduction; no fixture writes or product imports.

Use the adjacent hash-pinned mpmath1.3.0 requirements. Binary64 differences
are a nonzero exit. Temporary numeric output is removed before returning.
"""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,platform,struct,sys,tempfile,time
import mpmath as mp


def reference(case,digits):
    with mp.workdps(digits):
        p,h=mp.mpf(float(case['exponent'])),mp.mpf(float(case['length']))
        mean=p/(p+1);sd=mp.sqrt(p)/((p+1)*mp.sqrt(p+2))
        def mode(k,u):return mp.mpf(1) if k==0 else (u-mean)/sd
        gram=[];logs=[]
        for i,j in ((0,0),(0,1),(1,1)):
            gram.append(mp.quad(lambda x:p*p/((2*p-1)*h)*mode(i,x**(1/(2*p-1)))*mode(j,x**(1/(2*p-1))),[0,1]))
            def outer(x):
                radial=x**(1/(2*p))
                def inner(y):
                    t=y**(1/p);other=radial*t
                    return (mp.log(h)+mp.log(radial)+mp.log1p(-t))*(mode(i,radial)*mode(j,other)+mode(i,other)*mode(j,radial))/2
                return mp.quad(inner,[0,1])
            logs.append(mp.quad(outer,[0,1]))
        return {'gram':gram,'self_log':logs}


def main():
    if mp.__version__!='1.3.0':raise RuntimeError('requires exact hash-pinned mpmath1.3.0')
    path=Path(__file__).with_name('linear_self_gram.json');original=path.read_bytes();record=json.loads(original)
    start=time.perf_counter();started=datetime.now(timezone.utc).isoformat();arrays={};agreement=[]
    for index,case in enumerate(record['inputs']['cases']):
        low=reference(case,60);high=reference(case,80)
        with mp.workdps(80):
            difference=max(abs(a-b)/max(1,abs(b)) for key in ('gram','self_log') for a,b in zip(low[key],high[key]))
            assert difference<mp.mpf('1e-30');agreement.append(mp.nstr(difference,14))
        for key in ('gram','self_log'):arrays[f'{key}_{index:02d}']=[float(x) for x in high[key]]
    compute_s=time.perf_counter()-start;differences=[]
    for spec in record['values']:
        actual=arrays[spec['name']];expected=spec['data'];bits=lambda v:b''.join(struct.pack('<d',x) for x in v)
        differences.append(dict(name=spec['name'],binary64_equal=bits(actual)==bits(expected),maximum_absolute_difference=max(abs(a-b) for a,b in zip(actual,expected))))
    with tempfile.TemporaryDirectory(prefix='linear-self-reference-') as temp:
        output=Path(temp)/'values.json';output.write_text(json.dumps(arrays,allow_nan=False),encoding='utf-8');numeric_sha=hashlib.sha256(output.read_bytes()).hexdigest()
    assert path.read_bytes()==original
    product_loaded=any(n.split('.')[0] in {'galerkin','sipi','meshine','simcase'} for n in sys.modules);assert not product_loaded
    report=dict(generated_utc=started,generator_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),mpmath=mp.__version__,python=platform.python_version(),os=platform.platform(),machine=platform.machine(),compute_s=compute_s,wall_time_s=time.perf_counter()-start,product_loaded=product_loaded,differences=differences,precision_differences=agreement,temporary_numeric_sha256=numeric_sha,record_before_sha256=hashlib.sha256(original).hexdigest(),temporary_output_removed=not Path(temp).exists())
    print(json.dumps(report,indent=2,allow_nan=False))
    return 0 if all(x['binary64_equal'] for x in differences) else 1


if __name__=='__main__':raise SystemExit(main())
