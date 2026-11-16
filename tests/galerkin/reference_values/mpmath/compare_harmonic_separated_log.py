# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Compare-only independent harmonic interaction integrals; never writes fixtures."""
from pathlib import Path
from functools import lru_cache
import sys, json, time, hashlib
import mpmath as mp

@lru_cache(maxsize=64)
def rule(power, n, dps):
    with mp.workdps(dps):
        p = mp.mpf(float(power))
        nodes = []
        modes = [[], []]
        for branch, exponent in enumerate((p, 2 * p)):
            x, w = mp.gauss_quadrature(n, 'jacobi', alpha=0, beta=exponent - 1)
            u = [(v + 1) / 2 for v in x]
            weights = [v * exponent / 2 ** exponent for v in w]
            assert abs(mp.fsum(weights) - 1) < mp.mpf('1e-' + str(dps - 10))
            nodes += u
            modes[0] += [v if branch == 0 else mp.mpf(0) for v in weights]
            modes[1] += [(-1 if branch == 0 else 1) * mp.sqrt(3) * v for v in weights]
        return (nodes, modes)

def reference(row, n, dps):
    with mp.workdps(dps):
        a, b, o = [mp.mpc(*(float(x) for x in row[k])) for k in ('first', 'second', 'offset')]
        u, left = rule(row['p'], n, dps)
        v, right = rule(row['q'], n, dps)
        kernel = [[mp.log(abs(x * a - o - y * b)) for y in v] for x in u]
        return [[mp.fsum((left[i][r] * kernel[r][s] * right[j][s] for r in range(2 * n) for s in range(2 * n))) for j in range(2)] for i in range(2)]

from datetime import datetime,timezone
import platform,struct,tempfile,resource,sys

def generate(cases):
    if mp.__version__!='1.3.0':raise RuntimeError('requires hash-pinned mpmath1.3.0')
    arrays={};checks=[]
    for index,row in enumerate(cases):
        low=reference(row,48,60);medium=reference(row,64,60);high=reference(row,64,80)
        with mp.workdps(90):
            delta=max(abs(low[i][j]-medium[i][j]) for i in range(2) for j in range(2));assert delta<mp.mpf('1e-25');extra=dict(order_difference=mp.nstr(delta,30))
        low=medium
        with mp.workdps(90):
            low=[[mp.mpf(x) for x in line] for line in low];high=[[mp.mpf(x) for x in line] for line in high]
            errors=[]
            for i in range(2):
                for j in range(2):
                    error=abs(low[i][j]-high[i][j])
                    errors.append(error)
            difference=max(errors);assert difference<mp.mpf('1e-45')
            checks.append(dict(index=index,precision_difference=mp.nstr(difference,30),**extra))
            arrays[f'block_{index:02d}']=[[float(x) for x in line] for line in high]
    return arrays,checks


def main():
    path=Path(__file__).with_name('harmonic_separated_log.json');original=path.read_bytes();record=json.loads(original)
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
