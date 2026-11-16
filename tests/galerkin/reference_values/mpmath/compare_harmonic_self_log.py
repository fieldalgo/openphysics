# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Compare-only independent direct self-integral reproduction, no product imports."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,platform,struct,sys,tempfile,time,resource
import mpmath as mp


def reference(case,digits):
    with mp.workdps(digits):
        p,h=mp.mpf(float(case['exponent'])),mp.mpf(float(case['length']))
        exponents=(p,2*p)
        # Duffy triangles with analytic radial integration. Angular integrals
        # are evaluated numerically after flattening each normalized density.
        # No product series, digamma or zeta function is evaluated here.
        angular=[mp.quad(lambda t:mp.log1p(-t**(1/a)),
                         [0,mp.mpf('.5'),mp.mpf('.9'),1]) for a in exponents]
        raw=mp.matrix(2)
        for i,a in enumerate(exponents):
            for j,b in enumerate(exponents):
                raw[i,j]=mp.log(h)-1/(a+b)+(a*angular[j]+b*angular[i])/(a+b)
        transform=mp.matrix([[1,-mp.sqrt(3)],[0,mp.sqrt(3)]])
        value=transform.T*raw*transform
        return [value[0,0],value[0,1],value[1,1]]


def evaluate(cases):
    arrays={};agreement=[]
    for index,case in enumerate(cases):
        low,high=reference(case,60),reference(case,80)
        with mp.workdps(90):
            errors=[]
            for k,(a,b) in enumerate(zip(low,high)):
                if case['exponent']==1 and k==1:
                    assert max(abs(a),abs(b))<mp.mpf('1e-40')
                else:
                    error=abs(a-b)/abs(b)
                    assert error<mp.mpf('1e-40')
                    errors.append(error)
            agreement.append(mp.nstr(max(errors),30))
        arrays[f'self_log_{index:02d}']=[float(x) for x in high]
    return arrays,agreement


def main():
    if mp.__version__!='1.3.0':raise RuntimeError('requires exact hash-pinned mpmath1.3.0')
    path=Path(__file__).with_name('harmonic_self_log.json');original=path.read_bytes();record=json.loads(original)
    start=time.perf_counter();started=datetime.now(timezone.utc).isoformat()
    arrays,agreement=evaluate(record['inputs']['cases'])
    compute_s=time.perf_counter()-start;differences=[]
    for spec in record['values']:
        actual=arrays[spec['name']];expected=spec['data'];bits=lambda v:b''.join(struct.pack('<d',x) for x in v)
        differences.append(dict(name=spec['name'],binary64_equal=bits(actual)==bits(expected),maximum_absolute_difference=max(abs(a-b) for a,b in zip(actual,expected))))
    with tempfile.TemporaryDirectory(prefix='harmonic-self-reference-') as temp:
        output=Path(temp)/'values.json';output.write_text(json.dumps(arrays,allow_nan=False),encoding='utf-8');numeric_sha=hashlib.sha256(output.read_bytes()).hexdigest()
    assert path.read_bytes()==original
    product_loaded=any(n.split('.')[0] in {'galerkin','sipi','meshine','simcase'} for n in sys.modules);assert not product_loaded
    report=dict(generated_utc=started,generator_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),mpmath=mp.__version__,python=platform.python_version(),os=platform.platform(),machine=platform.machine(),compute_s=compute_s,wall_time_s=time.perf_counter()-start,linux_peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,product_loaded=product_loaded,differences=differences,precision_differences=agreement,temporary_numeric_sha256=numeric_sha,record_before_sha256=hashlib.sha256(original).hexdigest(),temporary_output_removed=not Path(temp).exists())
    print(json.dumps(report,indent=2,allow_nan=False))
    return 0 if all(x['binary64_equal'] for x in differences) else 1


if __name__=='__main__':raise SystemExit(main())
