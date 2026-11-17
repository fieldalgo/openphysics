# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Compare-only three-mode direct integrals; no product imports or zeta series."""
from pathlib import Path
from functools import lru_cache
import hashlib,json,platform,struct,sys,tempfile,time,resource
import mpmath as mp


@lru_cache(maxsize=32)
def unit_reference(exponent,digits):
    with mp.workdps(digits):
        p=mp.mpf(float(exponent));powers=(p,2*p,3*p)
        angular=[mp.quad(lambda t:mp.log1p(-t**(1/a)),
                        [0,mp.mpf('.5'),mp.mpf('.9'),1]) for a in powers]
        gram,log=mp.matrix(3),mp.matrix(3)
        for i,a in enumerate(powers):
            for j,b in enumerate(powers):
                gram[i,j]=a*b*mp.beta(a+b-1,1)
                log[i,j]=-1/(a+b)+(a*angular[j]+b*angular[i])/(a+b)
        transform=mp.matrix([[1,0,0],[-mp.sqrt(3),mp.sqrt(3),0],
                             [mp.sqrt(5),-3*mp.sqrt(5),2*mp.sqrt(5)]])
        return transform*gram*transform.T,transform*log*transform.T


def reference(case,digits):
    with mp.workdps(digits):
        gram,log=unit_reference(case['exponent'],digits)
        h=mp.mpf(float(case['length']));indices=((0,0),(0,1),(0,2),(1,1),(1,2),(2,2))
        return ([gram[i,j]/h for i,j in indices],
                [log[i,j]+(mp.log(h) if i==j==0 else 0) for i,j in indices])


def evaluate(cases):
    arrays={};agreement=[]
    for index,case in enumerate(cases):
        low,high=reference(case,70),reference(case,100)
        with mp.workdps(110):
            errors=[abs(a-b)/max(1,abs(b)) for old,new in zip(low,high) for a,b in zip(old,new)]
            assert max(errors)<mp.mpf('1e-50')
            agreement.append(mp.nstr(max(errors),30))
        for label,values in zip(('gram','self_log'),high):arrays[f'{label}_{index:02d}']=[float(x) for x in values]
    return arrays,agreement


def main():
    if mp.__version__!='1.3.0':raise RuntimeError('requires exact hash-pinned mpmath1.3.0')
    path=Path(__file__).with_name('quadratic_self.json');original=path.read_bytes();record=json.loads(original)
    start=time.perf_counter();arrays,agreement=evaluate(record['inputs']['cases']);differences=[]
    for spec in record['values']:
        actual=arrays[spec['name']];expected=spec['data'];bits=lambda v:b''.join(struct.pack('<d',x) for x in v)
        differences.append(dict(name=spec['name'],binary64_equal=bits(actual)==bits(expected),maximum_absolute_difference=max(abs(a-b) for a,b in zip(actual,expected))))
    with tempfile.TemporaryDirectory(prefix='quadratic-self-reference-') as temp:
        output=Path(temp)/'values.json';output.write_text(json.dumps(arrays,allow_nan=False));numeric_sha=hashlib.sha256(output.read_bytes()).hexdigest()
    assert path.read_bytes()==original
    product_loaded=any(n.split('.')[0] in {'galerkin','sipi','meshine','simcase'} for n in sys.modules);assert not product_loaded
    print(json.dumps(dict(generator_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),mpmath=mp.__version__,python=platform.python_version(),os=platform.platform(),machine=platform.machine(),compute_s=time.perf_counter()-start,linux_peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,product_loaded=product_loaded,differences=differences,precision_differences=agreement,temporary_numeric_sha256=numeric_sha,record_before_sha256=hashlib.sha256(original).hexdigest(),temporary_output_removed=not Path(temp).exists()),indent=2))
    return 0 if all(x['binary64_equal'] for x in differences) else 1


if __name__=='__main__':raise SystemExit(main())
