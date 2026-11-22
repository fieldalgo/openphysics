// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
// Matching the modes of two runs by field overlap (workspace-match.mjs): V14 against the exact
// overlap of shifted Gaussians on two different meshes with the grid spacing study, the
// assignment and acceptance rules, degenerate pairs as units, the words, and V17 on the
// optical session files.
const test=require('node:test');const assert=require('node:assert/strict');
const fs=require('node:fs');const path=require('node:path');
const STATIC='../../packages/simcase/src/simcase/studio/static/';
const FIXTURES=path.join(__dirname,'studio_session_fixtures');
let X,N;
test.before(async()=>{X=await import(STATIC+'workspace-match.mjs');N=await import(STATIC+'workspace-notebook.mjs');});

// a structured mesh of the window [x0, x1] × [y0, y1] (metres): squares of side h split on one
// diagonal ('/' or '\'), interior nodes moved by up to ±jitter·h (seeded, reproducible)
function mesh({x0=-1.5e-6,x1=1.5e-6,y0=-1.2e-6,y1=1.2e-6,h,diagonal='/',jitter=0,seed=1}){
 const nx=Math.round((x1-x0)/h),ny=Math.round((y1-y0)/h),hx=(x1-x0)/nx,hy=(y1-y0)/ny;
 let s=seed;const random=()=>{s=(s*1103515245+12345)%2147483648;return s/2147483648;};
 const nodes=[];
 for(let j=0;j<=ny;j++)for(let i=0;i<=nx;i++){
  const inside=i>0&&i<nx&&j>0&&j<ny;
  nodes.push([x0+i*hx+(inside?(2*random()-1)*jitter*hx:0),y0+j*hy+(inside?(2*random()-1)*jitter*hy:0)]);
 }
 const id=(i,j)=>j*(nx+1)+i,triangles=[];
 for(let j=0;j<ny;j++)for(let i=0;i<nx;i++){
  const a=id(i,j),b=id(i+1,j),c=id(i+1,j+1),d=id(i,j+1);
  if(diagonal==='/')triangles.push([a,b,c],[a,c,d]);else triangles.push([a,b,d],[b,c,d]);
 }
 return {node_coordinates:nodes,triangles};
}
// the centroid samples of modes given as functions (x, y) -> [[Ex re, Ex im], [Ey re, Ey im]]
function field(m,modes){
 const real=[],imag=[];
 for(const f of modes){
  const re=[],im=[];
  for(const t of m.triangles){
   const [p,q,r]=t.map(k=>m.node_coordinates[k]),x=(p[0]+q[0]+r[0])/3,y=(p[1]+q[1]+r[1])/3,[ex,ey]=f(x,y);
   re.push([ex[0],ey[0],0]);im.push([ex[1],ey[1],0]);
  }
  real.push(re);imag.push(im);
 }
 return {...m,real,imag};
}
const W0=0.4e-6;
const gaussian=(d,scale=[1,0])=>(x,y)=>{const g=Math.exp(-((x-d)**2+y*y)/(W0*W0));return [[g*scale[0],g*scale[1]],[0,0]];};
// erf to 1.2e-7 (Abramowitz and Stegun 7.1.26); only ratios near 1 use it here
function erf(x){const t=1/(1+0.3275911*Math.abs(x)),y=1-(((((1.061405429*t-1.453152027)*t)+1.421413741)*t-0.284496736)*t+0.254829592)*t*Math.exp(-x*x);return x>=0?y:-y;}
// the exact overlap on the window [X0, X1] (the y factors cancel): exp(-d²/w0²) E(d/2)² / (E(0) E(d))
function exact(d,X0=-1.5e-6,X1=1.5e-6){
 const E=c=>erf(Math.SQRT2*(X1-c)/W0)-erf(Math.SQRT2*(X0-c)/W0);
 return Math.exp(-d*d/(W0*W0))*E(d/2)**2/(E(0)*E(d));
}
const A_MESH=()=>mesh({h:30e-9,diagonal:'/'}),B_MESH=()=>mesh({h:25e-9,diagonal:'\\',jitter:0.2,seed:7});

test('V14: the overlap of a Gaussian and its shift on two meshes is the exact value to 1e-3, and halving the grid changes it by at most 1e-3',()=>{
 const a=A_MESH(),b=B_MESH(),scale=[3.7*Math.cos(0.9),3.7*Math.sin(0.9)];
 const report=[];
 for(const d of [0,0.1e-6,0.3e-6,0.6e-6]){
  const A={field:field(a,[gaussian(0)]),neff:[2],coreSize:30e-9},B={field:field(b,[gaussian(d,scale)]),neff:[2],coreSize:25e-9};
  const at=s=>X.matchModes(A,B,s?{spacing:s,cap:Infinity}:{}).eta[0][0];
  const base=X.matchModes(A,B);assert.equal(base.spacing,12.5e-9);assert.deepEqual([base.grid.nx,base.grid.ny],[240,192]);
  const e=[at(null),at(6.25e-9),at(3.125e-9)],ref=exact(d);
  report.push(`d ${(d*1e6).toFixed(1)} um: exact ${ref.toFixed(6)}, s ${e.map(v=>(v-ref).toExponential(2)).join(', s/2 ')} (s/4)`);
  assert.ok(Math.abs(e[0]-ref)<=1e-3,`d ${d}: |η - exact| = ${Math.abs(e[0]-ref)}`);
  assert.ok(Math.abs(e[0]-e[1])<=1e-3,`d ${d}: halving the grid changes η by ${Math.abs(e[0]-e[1])}`);
  // the phase and scale of a mode, and the order of the runs, do not change η
  const plain=X.matchModes(A,{...B,field:field(b,[gaussian(d)])}).eta[0][0];
  assert.ok(Math.abs(plain-e[0])<=1e-12,'phase and scale');
  assert.ok(Math.abs(X.matchModes(B,A).eta[0][0]-e[0])<=1e-12,'symmetric');
 }
 console.log('V14 errors η - exact at s = 12.5 nm, s/2, s/4:\n '+report.join('\n '));
});
test('the grid: cell centres over the intersection of the windows, spacing ½ min(core size), at most 400 per axis',()=>{
 const a=mesh({h:100e-9}),b=mesh({x0:-1e-6,x1:2e-6,y0:-1.2e-6,y1:0.8e-6,h:100e-9});
 const g=X.commonGrid(a,b,10e-9);
 assert.deepEqual([g.x0,g.x1,g.y0,g.y1],[-1e-6,1.5e-6,-1.2e-6,0.8e-6]);assert.deepEqual([g.nx,g.ny],[250,200]);
 const capped=X.commonGrid(a,a,1e-9);assert.deepEqual([capped.nx,capped.ny],[400,400]);
 assert.equal(X.commonGrid(a,mesh({x0:2e-6,x1:3e-6,h:100e-9}),10e-9),null);
 assert.match(X.matchModes({field:field(a,[gaussian(0)]),neff:[2],coreSize:30e-9},{field:field(mesh({x0:2e-6,x1:3e-6,h:100e-9}),[gaussian(0)]),neff:[2],coreSize:30e-9}).error,/do not overlap/);
 // a point outside one run's mesh (a hole) is left out of every sum
 const holed=mesh({h:100e-9});holed.triangles=holed.triangles.filter(t=>t.every(k=>holed.node_coordinates[k][0]<=0));
 const g2=X.commonGrid(a,holed,50e-9),loc=X.locate(holed,g2);
 assert.ok(loc.some(t=>t===-1)&&loc.some(t=>t>=0));
 const left=(x,y)=>[[x<0?1:0,0],[0,0]],right=(x,y)=>[[x>0?1:0,0],[0,0]];
 const m=X.matchModes({field:field(a,[left,right]),neff:[2,1.5],coreSize:100e-9},{field:field(holed,[left,right]),neff:[2,1.5],coreSize:100e-9});
 assert.ok(Math.abs(m.eta[0][0]-1)<1e-12);assert.equal(m.eta[1][1],0,'B has no field where its mesh is');
});
// two Hermite-Gaussian-like modes: TE-like x-even, and an x-odd TE-like one, and a y-polarized
const even=(x,y)=>{const g=Math.exp(-(x*x+y*y)/(W0*W0));return [[g,0],[0,0]];};
const odd=(x,y)=>{const g=Math.exp(-(x*x+y*y)/(W0*W0));return [[g*x/W0,0],[0,0]];};
const ypol=(x,y)=>{const g=Math.exp(-(x*x+y*y)/(W0*W0));return [[0,0],[g,0]];};
test('assignment: the largest total overlap, one to one, whatever the ranks; Δn_eff is B − A of the matched modes',()=>{
 const a=A_MESH(),b=B_MESH();
 const A={field:field(a,[even,ypol]),neff:[2.4,1.8],coreSize:30e-9},B={field:field(b,[even,odd,ypol]),neff:[2.5,1.9,1.85],coreSize:25e-9};
 const m=X.matchModes(A,B);
 assert.deepEqual(m.rows.map(r=>r.match&&[r.match.unitA,r.match.unitB]),[[[0],[0]],[[1],[2]]],'the y-polarized rank 2 of A is rank 3 of B');
 assert.ok(Math.abs(m.rows[1].match.delta-(1.85-1.8))<1e-15);
 assert.deepEqual(m.unmatchedB.map(u=>u.unit),[[1]]);
 assert.equal(X.matchText(m.rows[0].match),'A mode 1 ↔ B mode 1 · overlap 1.00 · Δn_eff +0.10000000');
 assert.equal(X.matchText(m.rows[1].match),'A mode 2 ↔ B mode 3 · overlap 1.00 · Δn_eff +0.05000000');
 const rows=X.compareMatchRows(m);
 assert.deepEqual(rows.map(r=>r.kind),['match','match','b']);
 assert.match(rows[2].text,/^B mode 2: no match in A \(best overlap 0\.00, with A mode \d\)$/);
 assert.deepEqual(X.fieldChoices(m).map(c=>[c.a,c.b,c.label]),[[0,0,'A mode 1 ↔ B mode 1 · overlap 1.00'],[1,2,'A mode 2 ↔ B mode 3 · overlap 1.00']]);
 assert.deepEqual(X.bestAssignment([[0.9,0.85],[0.86,0.1]]),[[0,1],[1,0]],'the total, not the row maximum, decides');
});
test('acceptance: η ≥ 0.8 and 0.1 above the next best in its row and in its column; otherwise "no match" with the best overlap',()=>{
 const a=A_MESH(),b=B_MESH();
 // B mode 1 = cos θ even + sin θ odd: η = cos² θ with A's even mode
 const mix=c=>(x,y)=>{const e=even(x,y)[0][0],o=odd(x,y)[0][0],n=Math.hypot(c,Math.sqrt(1-c*c)*2);return [[(c*e+Math.sqrt(1-c*c)*o*2)/n,0],[0,0]];};
 const run=(fa,fb)=>X.matchModes({field:field(a,fa),neff:fa.map((_,i)=>2.4-0.3*i),coreSize:30e-9},{field:field(b,fb),neff:fb.map((_,i)=>2.4-0.3*i),coreSize:25e-9});
 const low=run([even],[mix(Math.sqrt(0.43))]);
 assert.ok(Math.abs(low.eta[0][0]-0.43)<0.01,String(low.eta[0][0]));
 assert.equal(low.rows[0].match,null);
 assert.equal(X.compareMatchRows(low)[0].text,'A mode 1: no match in B (best overlap 0.43, with B mode 1)');
 assert.equal(X.compareMatchRows(low)[1].text,'B mode 1: no match in A (best overlap 0.43, with A mode 1)');
 assert.ok(run([even],[mix(Math.sqrt(0.83))]).rows[0].match,'0.83 alone is accepted');
 // a column competitor within 0.1: A modes 1 and 2 both overlap B mode 1
 const amb=X.matchModes({field:field(a,[even,mix(Math.sqrt(0.9))]),neff:[2.4,2.1],coreSize:30e-9},{field:field(b,[even]),neff:[2.4],coreSize:25e-9});
 assert.ok(amb.eta[0][0]>0.99&&amb.eta[1][0]>0.89);assert.equal(amb.rows[0].match,null,'margin in the column');
 assert.equal(X.formatOverlap(0.7996),'0.799');assert.equal(X.formatOverlap(0.8),'0.80');assert.equal(X.formatOverlap(0.43),'0.43');
 assert.equal(X.formatDelta(-0.00214),'−0.00214000');
 assert.equal(X.MATCH_THRESHOLD,0.8);assert.equal(X.MATCH_MARGIN,0.1);
});
test('degenerate pairs are one unit, matched by the mean squared cosine of the principal angles; a rotation inside the pair is free',()=>{
 // one mesh for both runs: the overlap of the same span is then 1 to round-off
 const a=A_MESH(),b=a,th=0.7,c=Math.cos(th),s=Math.sin(th);
 const rotated=k=>(x,y)=>{const e=even(x,y)[0][0];return k?[[-s*e,0],[c*e,0]]:[[c*e,0],[s*e,0]];};
 const A={field:field(a,[even,ypol,odd]),neff:[2.2,2.1995,1.9],coreSize:30e-9},B={field:field(b,[rotated(0),rotated(1),odd]),neff:[2.21,2.2108,1.91],coreSize:30e-9};
 const m=X.matchModes(A,B);
 assert.deepEqual(m.unitsA,[[0,1],[2]]);assert.deepEqual(m.unitsB,[[0,1],[2]]);
 const pair=m.rows[0].match;assert.ok(pair&&pair.eta>1-1e-9,String(pair?.eta));
 assert.ok(Math.abs(pair.delta-((2.21+2.2108)/2-(2.2+2.1995)/2))<1e-15,'the difference of the pair means');
 assert.equal(X.unitName([0,1]),'modes 1–2 (pair)');
 assert.match(X.matchText(pair),/^A modes 1–2 \(pair\) ↔ B modes 1–2 \(pair\) · overlap 1\.00 · Δn_eff \+0\.01065000$/);
 // the single modes inside the pair overlap only in part: the pair as a unit is what matches
 assert.deepEqual(X.fieldChoices(m).map(x=>x.label),['A mode 1 ↔ B mode 1 (pair, any rotation) · overlap 1.00','A mode 2 ↔ B mode 2 (pair, any rotation) · overlap 1.00','A mode 3 ↔ B mode 3 · overlap 1.00']);
 // a pair against two separate modes is at most 1/2 and never accepted
 const split=X.matchModes(A,{...B,neff:[2.21,2.205,1.91]});
 assert.deepEqual(split.unitsB,[[0],[1],[2]]);assert.ok(split.eta[0].slice(0,2).every(v=>v<=0.5+1e-12));assert.equal(split.rows[0].match,null);
});
test('V17: every optical v6 and v7 session opens and Compare matches the modes of its runs from the stored samples',()=>{
 for(const name of ['optical-v6-one.json','optical-v7-one.json','optical-v6-three.json','optical-v7-three.json']){
  const session=N.parseSession(fs.readFileSync(path.join(FIXTURES,name),'utf8'));
  const [a,b]=[session.runs[0],session.runs.at(-1)];
  const m=X.opticalMatch(a,b);assert.equal(m.error,undefined,name);
  assert.ok(m.rows.every(r=>r.match),name+': each mode matched');
  assert.equal(X.opticalMatch(a,b),m,'kept per pair of runs');
  for(const row of X.compareMatchRows(m))assert.match(row.text,/^A mode \d ↔ B mode \d · overlap \d\.\d\d · Δn_eff [+−]\d\.\d{8}$/);
  assert.match(X.unitPolarization(a,[0]),/^(TE-like|TM-like|hybrid) · \d+\.\d % TE$/);
 }
});
test('V17: matching leaves the runs as stored: version 7 is written byte for byte as before (S4 with Compare matching)',()=>{
 for(const state of ['one','three']){
  // S4's state: the same bytes as the Studio before version 8 wrote them, after every run pair is matched
  const st=JSON.parse(fs.readFileSync(path.join(FIXTURES,`state-${state}.json`),'utf8'));
  for(const a of st.runs)for(const b of st.runs)assert.equal(X.opticalMatch(a,b).error,undefined);
  assert.equal(JSON.stringify(N.createSession(st.input,st.runs,st.selected,st.comparison,st.view)),fs.readFileSync(path.join(FIXTURES,`optical-v7-${state}.json`),'utf8'),state);
  // and a session read from the file is written the same with and without matching its runs
  const session=N.parseSession(fs.readFileSync(path.join(FIXTURES,`optical-v7-${state}.json`),'utf8'));
  const write=()=>JSON.stringify(N.createSession(session.input,session.runs,session.selected,session.comparison,session.view));
  const before=write();for(const a of session.runs)for(const b of session.runs)X.opticalMatch(a,b);
  assert.equal(write(),before,state);
 }
});
