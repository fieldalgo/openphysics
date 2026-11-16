# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""Compare-only selected Green blocks with product-free mpmath 1.3.0.

Stored panel directions and topology are product-derived inputs. Self/source/
Duffy identities share mathematics with the implementation. This is a primitive
comparison, not an independent field solve. No fixture is rewritten.
"""
from pathlib import Path
from functools import lru_cache
from datetime import datetime,timezone
import hashlib,json,platform,struct,sys,tempfile,time
import mpmath as mp

@lru_cache(maxsize=64)
def rule(power,n,dps):
 with mp.workdps(dps):
  p=mp.mpf(float(power));x,w=mp.gauss_quadrature(n,'jacobi',alpha=0,beta=p-1)
  u=[(v+1)/2 for v in x];weights=[v*p/2**p for v in w]
  assert abs(mp.fsum(weights)-1)<mp.mpf('1e-'+str(dps-10))
  return u,weights

def direct_tensor(row,n,dps):
 with mp.workdps(dps):
  a,b,o=[mp.mpc(*(float(x) for x in row[k])) for k in ('first','second','offset')]
  p,q=mp.mpf(float(row['p'])),mp.mpf(float(row['q']))
  u,w=rule(row['p'],n,dps);v,z=rule(row['q'],n,dps)
  left=[w,[weight*mp.sqrt(p*(p+2))*((p+1)/p*x-1) for x,weight in zip(u,w)]]
  right=[z,[weight*mp.sqrt(q*(q+2))*((q+1)/q*x-1) for x,weight in zip(v,z)]]
  kernel=[[mp.log(abs(x*a-o-y*b)) for y in v] for x in u]
  return [[mp.fsum(left[i][r]*kernel[r][s]*right[j][s] for r in range(n) for s in range(n)) for j in range(2)] for i in range(2)]
def source(z):
 def A(w):return w*(mp.log(w)-1) if w else 0
 zero=mp.re(A(z+1)-A(z))
 if not z:one=mp.mpf('.5')
 elif z==-1:one=-mp.mpf('.5')
 else:one=mp.re(z+mp.mpf('.5')-z*(z+1)*(mp.log(z+1)-mp.log(z)))
 return zero,one

def direct_mixed(row,dps):
 with mp.workdps(dps):
  a,b,o=[mp.mpc(*(float(x) for x in row[k])) for k in ('first','second','offset')];p=mp.mpf(float(row['p']));cache={}
  def evaluate(t,i,j):
   u=t**(1/p)
   if t not in cache:
    zero,one=source((o-u*a)/b);cache[t]=[mp.log(abs(b))+zero,mp.sqrt(3)*one]
   factor=1 if i==0 else mp.sqrt(p*(p+2))*((p+1)/p*u-1)
   return factor*cache[t][j]
  return [[mp.quad(lambda t:evaluate(t,i,j),[0,mp.mpf('.25'),mp.mpf('.75'),1]) for j in range(2)] for i in range(2)]
def direct_vertex(a,b,p,q,dps):
 with mp.workdps(dps):
  a,b=[mp.mpc(float(x),float(y)) for x,y in (a,b)];p,q=mp.mpf(float(p)),mp.mpf(float(q))
  def average(power,exponent,fun):
   return mp.quad(lambda t:(t**(1/power))**exponent*fun(t**(1/power)),[0,mp.mpf('.25'),mp.mpf('.75'),1])
  x=[average(q,s,lambda v:mp.log(abs(a-v*b))) for s in range(2)]
  y=[average(p,r,lambda u:mp.log(abs(u*a-b))) for r in range(2)]
  J=[[ (p*x[s]+q*y[r]-p*q/((p+r)*(q+s)))/(p+q+r+s) for s in range(2)] for r in range(2)]
  lp,lq=mp.sqrt(p*(p+2)),mp.sqrt(q*(q+2));left=[[1,0],[-lp,lp*(p+1)/p]];right=[[1,0],[-lq,lq*(q+1)/q]]
  return [[mp.fsum(left[i][r]*right[j][s]*J[r][s] for r in range(2) for s in range(2)) for j in range(2)] for i in range(2)]

def exact_self(row,dps):
 with mp.workdps(dps):
  p=mp.mpf(float(row['p']));a=mp.mpc(*(float(x) for x in row['first']));h=abs(a);lp=mp.sqrt(p*(p+2))
  cross=lp*(1-p)/(2*p*(p+1))
  return [[mp.log(h)-1/(2*p)-mp.digamma(p+1)-mp.euler,cross],[cross,-(p+2)/(2*(p+1))]]

def entry(row,n,dps):
 with mp.workdps(dps):
  if row['kind']=='self':real=exact_self(row,dps)
  elif row['kind']=='vertex':real=direct_vertex(row['first'],row['second'],row['p'],row['q'],dps)
  elif row['q']==1:real=direct_mixed(row,dps)
  else:real=direct_tensor(row,n,dps)
  image=dict(row,second=[row['second'][0],-row['second'][1]],offset=row['image_offset'])
  if row['q']==1:imag=direct_mixed(image,dps)
  else:imag=direct_tensor(image,n,dps)
  return [[imag[i][j]-real[i][j] for j in range(2)] for i in range(2)]

def main():
    if mp.__version__ != '1.3.0': raise RuntimeError('requires hash-pinned mpmath 1.3.0')
    path=Path(__file__).with_name('linear_half_space.json');original=path.read_bytes();record=json.loads(original)
    started=datetime.now(timezone.utc).isoformat();start=time.perf_counter();arrays={};agreement=[]
    for index,row in enumerate(record['inputs']['entries']):
        low=entry(row,48,60);medium=entry(row,64,60);high=entry(row,64,80)
        with mp.workdps(80):
            order=max(abs(low[i][j]-medium[i][j]) for i in range(2) for j in range(2))
            precision=max(abs(medium[i][j]-high[i][j]) for i in range(2) for j in range(2))
            assert order<mp.mpf('1e-25') and precision<mp.mpf('1e-40')
            agreement.append(dict(order=mp.nstr(order,14),precision=mp.nstr(precision,14)))
        arrays[f'block_{index:02d}']=[[float(x) for x in line] for line in high]
    compute_s=time.perf_counter()-start;differences=[]
    for value in record['values']:
        actual=arrays[value['name']];expected=value['data']
        bits=lambda a:b''.join(struct.pack('<d',v) for row in a for v in row)
        differences.append(dict(name=value['name'],binary64_equal=bits(actual)==bits(expected),maximum_absolute_difference=max(abs(a-b) for x,y in zip(actual,expected) for a,b in zip(x,y))))
    with tempfile.TemporaryDirectory(prefix='linear-half-space-reference-') as temp:
        output=Path(temp)/'values.json';output.write_text(json.dumps(arrays,allow_nan=False),encoding='utf-8');numeric_sha=hashlib.sha256(output.read_bytes()).hexdigest()
    assert path.read_bytes()==original
    product_loaded=any(n.split('.')[0] in {'galerkin','sipi','meshine','simcase'} for n in sys.modules);assert not product_loaded
    report=dict(generated_utc=started,generator_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),mpmath=mp.__version__,python=platform.python_version(),os=platform.platform(),machine=platform.machine(),compute_s=compute_s,wall_time_s=time.perf_counter()-start,product_loaded=product_loaded,inputs_from_product=True,differences=differences,precision_differences=agreement,temporary_numeric_sha256=numeric_sha,record_before_sha256=hashlib.sha256(original).hexdigest(),temporary_output_removed=not Path(temp).exists())
    print(json.dumps(report,indent=2,allow_nan=False))
    return 0 if all(x['binary64_equal'] for x in differences) else 1


if __name__=='__main__': raise SystemExit(main())
