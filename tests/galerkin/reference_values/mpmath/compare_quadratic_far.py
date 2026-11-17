# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Independent multiprecision complex series; imports no product modules."""
from functools import lru_cache
import json, math, sys, hashlib, platform, struct, tempfile, time, resource
from pathlib import Path
import mpmath as mp


def evaluate(row, digits):
    with mp.workdps(digits):
        a, b, o = [mp.mpc(*[mp.mpf(x) for x in row[key]])
                   for key in ('first', 'second', 'offset')]
        p, q = mp.mpf(row['p']), mp.mpf(row['q'])
        rho = (abs(a)+abs(b))/abs(o)
        assert rho <= mp.mpf(1)/4
        @lru_cache(None)
        def moment(exponent, mode, power):
            if power == 0:
                return mp.mpf(mode == 0)
            r = exponent
            values = [k*r/(k*r+power) for k in (1, 2, 3)]
            return [values[0], mp.sqrt(3)*(values[1]-values[0]),
                    mp.sqrt(5)*(2*values[2]-3*values[1]+values[0])][mode]
        result = mp.matrix(3, 3);result[0, 0] = mp.log(abs(o))
        for power in range(1, 101):
            for first_power in range(power+1):
                second_power = power-first_power
                coefficient = ((-1)**(power+1)*mp.mpf(math.comb(power, first_power))/power
                               *(-a/o)**first_power*(b/o)**second_power).real
                for i in range(3):
                    for j in range(3):
                        result[i, j] += coefficient*moment(p, i, first_power)*moment(q, j, second_power)
        tail = 5*rho**101/(101*(1-rho))
        return dict(values=[[mp.nstr(result[i, j], digits) for j in range(3)] for i in range(3)],
                    rho=mp.nstr(rho, digits), tail_bound=mp.nstr(tail, digits))


def evaluate_cases(cases):
    arrays={};agreement=[];bounds=[]
    for index,case in enumerate(cases):
        low,high=evaluate(case,70),evaluate(case,100)
        with mp.workdps(110):
            difference=max(abs(mp.mpf(low['values'][i][j])-mp.mpf(high['values'][i][j])) for i in range(3) for j in range(3))
            assert difference<mp.mpf('1e-60')
            agreement.append(mp.nstr(difference,30));bounds.append(high['tail_bound'])
        arrays[f'far_{index:02d}']=[float(value) for row in high['values'] for value in row]
    return arrays,agreement,bounds


def main():
    if mp.__version__!='1.3.0':raise RuntimeError('requires exact hash-pinned mpmath1.3.0')
    path=Path(__file__).with_name('quadratic_far.json');original=path.read_bytes();record=json.loads(original)
    start=time.perf_counter();arrays,agreement,bounds=evaluate_cases(record['inputs']['cases']);differences=[]
    for spec in record['values']:
        actual=arrays[spec['name']];expected=spec['data'];bits=lambda v:b''.join(struct.pack('<d',x) for x in v)
        differences.append(dict(name=spec['name'],binary64_equal=bits(actual)==bits(expected),maximum_absolute_difference=max(abs(a-b) for a,b in zip(actual,expected))))
    with tempfile.TemporaryDirectory(prefix='quadratic-far-reference-') as temp:
        output=Path(temp)/'values.json';output.write_text(json.dumps(arrays,allow_nan=False));numeric_sha=hashlib.sha256(output.read_bytes()).hexdigest()
    assert path.read_bytes()==original
    product_loaded=any(n.split('.')[0] in {'galerkin','sipi','meshine','simcase'} for n in sys.modules);assert not product_loaded
    print(json.dumps(dict(generator_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),mpmath=mp.__version__,python=platform.python_version(),os=platform.platform(),machine=platform.machine(),compute_s=time.perf_counter()-start,linux_peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,product_loaded=product_loaded,differences=differences,precision_differences=agreement,tail_bounds=bounds,temporary_numeric_sha256=numeric_sha,record_before_sha256=hashlib.sha256(original).hexdigest(),temporary_output_removed=not Path(temp).exists()),indent=2))
    return 0 if all(x['binary64_equal'] for x in differences) else 1


if __name__=='__main__':raise SystemExit(main())
