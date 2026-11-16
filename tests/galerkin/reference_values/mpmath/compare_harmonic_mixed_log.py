# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Compare-only independent harmonic interaction integrals; never writes fixtures."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib, json, platform, struct, sys, tempfile, time
import mpmath as mp

def source(z):

    def primitive(w):
        return w * (mp.log(w) - 1) if w else mp.mpf(0)
    zero = mp.re(primitive(z + 1) - primitive(z))
    if not z:
        one = mp.mpf('.5')
    elif z == -1:
        one = -mp.mpf('.5')
    else:
        one = mp.re(z + mp.mpf('.5') - z * (z + 1) * (mp.log(z + 1) - mp.log(z)))
    return (zero, one)

def reference(row, digits):
    with mp.workdps(digits):
        a, b, o = [mp.mpc(*(float(x) for x in row[k])) for k in ('a', 'b', 'offset')]
        p = mp.mpf(float(row['p']))
        cuts = [mp.mpf(0), mp.mpf(1)]
        for endpoint in (o, o + b):
            point = endpoint / a
            center = min(mp.mpf(1), max(mp.mpf(0), point.real))
            distance = abs(point - center)
            cuts.append(center)
            for multiple in (1, 8, 64):
                for cut in (center - distance * multiple, center + distance * multiple):
                    if 0 < cut < 1:
                        cuts.append(cut)
        breaks = sorted(set((x ** p for x in cuts)))
        cache = {}

        def value(t, i, j):
            u = t ** (1 / p)
            if t not in cache:
                k0, k1 = source((o - u * a) / b)
                cache[t] = (mp.log(abs(b)) + k0, mp.sqrt(3) * k1)
            mode = mp.mpf(1) if i == 0 else mp.sqrt(3) * (2 * t - 1)
            return mode * cache[t][j]
        return [[mp.quad(lambda t: value(t, i, j), breaks) for j in range(2)] for i in range(2)]

from datetime import datetime,timezone
import platform,struct,tempfile,resource,sys

def generate(cases):
    if mp.__version__!='1.3.0':raise RuntimeError('requires hash-pinned mpmath1.3.0')
    arrays={};checks=[]
    for index,row in enumerate(cases):
        low=reference(row,60);high=reference(row,80);extra={}
        with mp.workdps(90):
            low=[[mp.mpf(x) for x in line] for line in low];high=[[mp.mpf(x) for x in line] for line in high]
            errors=[]
            for i in range(2):
                for j in range(2):
                    error=abs(low[i][j]-high[i][j])
                    errors.append(error)
            difference=max(errors);assert difference<mp.mpf('1e-40')
            checks.append(dict(index=index,precision_difference=mp.nstr(difference,30),**extra))
            arrays[f'block_{index:02d}']=[[float(x) for x in line] for line in high]
    return arrays,checks


def main():
    path=Path(__file__).with_name('harmonic_mixed_log.json');original=path.read_bytes();record=json.loads(original)
    start=time.perf_counter();started=datetime.now(timezone.utc).isoformat()
    arrays,checks=generate(record['inputs']['cases']);compute_s=time.perf_counter()-start;differences=[]
    for spec in record['values']:
        actual=arrays[spec['name']];expected=spec['data'];bits=lambda a:b''.join(struct.pack('<d',x) for line in a for x in line)
        differences.append(dict(name=spec['name'],binary64_equal=bits(actual)==bits(expected),maximum_absolute_difference=max(abs(a-b) for x,y in zip(actual,expected) for a,b in zip(x,y))))
    with tempfile.TemporaryDirectory(prefix='harmonic-interaction-reference-') as temp:
        output=Path(temp)/'values.json';output.write_text(json.dumps(arrays,allow_nan=False),encoding='utf-8');numeric_sha=hashlib.sha256(output.read_bytes()).hexdigest()
    assert path.read_bytes()==original
    product_loaded=any(n.split('.')[0] in {'galerkin','sipi','meshine','simcase'} for n in sys.modules);assert not product_loaded
    report=dict(generated_utc=started,generator_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),mpmath=mp.__version__,python=platform.python_version(),os=platform.platform(),machine=platform.machine(),compute_s=compute_s,wall_time_s=time.perf_counter()-start,linux_peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,product_loaded=product_loaded,differences=differences,self_checks=checks,temporary_numeric_sha256=numeric_sha,record_before_sha256=hashlib.sha256(original).hexdigest(),temporary_output_removed=not Path(temp).exists())
    print(json.dumps(report,indent=2,allow_nan=False))
    return 0 if all(x['binary64_equal'] for x in differences) else 1


if __name__=='__main__':raise SystemExit(main())
