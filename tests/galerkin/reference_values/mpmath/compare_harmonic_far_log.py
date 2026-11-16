# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Compare-only independent harmonic interaction integrals; never writes fixtures."""
from pathlib import Path
import json, time, hashlib, math, resource
import mpmath as mp

def evaluate(row, digits):
    with mp.workdps(digits):
        a, b, o = [mp.mpc(*[mp.mpf(float(x)) for x in row[k]]) for k in ('first', 'second', 'offset')]
        p, q = [mp.mpf(float(row[k])) for k in ('first_exponent', 'second_exponent')]
        radius = (abs(a) + abs(b)) / abs(o)
        tail = 4 * radius ** 81 / (81 * (1 - radius))
        assert radius <= mp.mpf('.25') and tail < mp.mpf('1e-45')

        def moments(power):
            return [[power / (power + k) for k in range(81)], [mp.sqrt(3) * power * k / ((power + k) * (2 * power + k)) for k in range(81)]]
        am, bm = (moments(p), moments(q))
        ap = [(-a / o) ** k for k in range(81)]
        bp = [(b / o) ** k for k in range(81)]
        matrix = mp.matrix(2)
        matrix[0, 0] = mp.log(abs(o))
        for k in range(1, 81):
            weights = [math.comb(k, j) * ap[k - j] * bp[j] for j in range(k + 1)]
            for i in range(2):
                for j in range(2):
                    matrix[i, j] += mp.re((-1) ** (k + 1) / mp.mpf(k) * mp.fsum((weights[l] * am[i][k - l] * bm[j][l] for l in range(k + 1))))
        return dict(values=[[mp.nstr(matrix[i, j], digits) for j in range(2)] for i in range(2)], tail=mp.nstr(tail, 30))

from datetime import datetime,timezone
import platform,struct,tempfile,resource,sys

def generate(cases):
    if mp.__version__!='1.3.0':raise RuntimeError('requires hash-pinned mpmath1.3.0')
    arrays={};checks=[]
    for index,row in enumerate(cases):
        low=evaluate(row,60);high=evaluate(row,80);low=low['values'];high=high['values'];extra=dict(tail_bound=evaluate(row,80)['tail'])
        with mp.workdps(90):
            low=[[mp.mpf(x) for x in line] for line in low];high=[[mp.mpf(x) for x in line] for line in high]
            errors=[]
            for i in range(2):
                for j in range(2):
                    error=abs(low[i][j]-high[i][j])
                    assert high[i][j]!=0;error/=abs(high[i][j])
                    errors.append(error)
            difference=max(errors);assert difference<mp.mpf('1e-40')
            checks.append(dict(index=index,precision_difference=mp.nstr(difference,30),**extra))
            arrays[f'block_{index:02d}']=[[float(x) for x in line] for line in high]
    return arrays,checks


def main():
    path=Path(__file__).with_name('harmonic_far_log.json');original=path.read_bytes();record=json.loads(original)
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
