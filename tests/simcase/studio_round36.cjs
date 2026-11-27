// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
// Round 36 (agent proxy round 36 on main 907515a): C1, Compare names the core mode. In T18 the closed
// run of "Set search near 2.46 · 4 modes" has its core mode at mode 3 and the open run at mode 1;
// Compare listed "A mode 3 ↔ B mode 1 · overlap 0.99 · TE-like" with nothing saying it was the core
// mode. A mode that its run's notes call the core mode (Results' core-mode note: coreNotes for a
// closed run, the core notes of openRegionNotes for an open one) now reads "mode 3 (core)" in the
// Matched modes picker and in the matched-modes table; when the first modes are not matched with
// each other but the core modes are, one line above the table says "Core modes: A mode 3 ↔ B mode 1
// · overlap 0.99". The matching, the numbering and the default pick are unchanged. Plain text
// comparison only: no RegExp is built from a dynamic string.
const test=require('node:test');const assert=require('node:assert/strict');
const fs=require('node:fs');const path=require('node:path');
const STATIC='../../packages/simcase/src/simcase/studio/static/';
const read=name=>fs.readFileSync(path.join(__dirname,STATIC,name),'utf8');
let N,P,M,X;
test.before(async()=>{
 N=await import(STATIC+'workspace-notebook.mjs');P=await import(STATIC+'workspace-project.mjs');
 M=await import(STATIC+'workspace-modes.mjs');X=await import(STATIC+'workspace-match.mjs');
});
const setup=()=>({materials:{Core:'Silicon',Oxide:'Silica',Heater:''},temperature:293.15,cooling:'',fixed:'',terminal:''});
const CORE={name:'Core',type:'rect',material:'Silicon',x:-250,y:0,w:500,h:220};
const SUBSTRATE={name:'Substrate',type:'rect',material:'Silicon',x:-1500,y:-1200,w:3000,h:700};
const input=shapes=>P.snapshot({width:500,voltage:1,electric:false,heat:false,structure:false,optics:true,wavelength:1550,coreMesh:30,...(shapes?{shapes}:{})},setup());
// two triangles, one in the core and one in the substrate; inCore: per mode, whether its |E|² is in the core
const twoTriangles=inCore=>({node_coordinates:[[-2e-7,1e-8],[2e-7,1e-8],[0,2e-7],[-1.4e-6,-1.1e-6],[1.4e-6,-1.1e-6],[0,-6e-7]],triangles:[[0,1,2],[3,4,5]],
 real:inCore.map(c=>c?[[1,0,0],[0.1,0,0]]:[[0,0,0],[1,0,0]]),imag:inCore.map(()=>[[0,0,0],[0,0,0]])});
// T18 closed, "Set search near 2.46 · 4 modes": modes 1, 2 and 4 in the substrate, mode 3 the core mode
const T18_NEAR=[2.6,2.5,2.43931663,2.40];
const closedRun=(job,re,inCore,{target=2.46,shapes=[CORE,SUBSTRATE]}={})=>N.validateRun({job,completedAt:'2026-11-27T01:00:00.000Z',
 settings:target===null?N.opticalSettings(1550,30,re.length):N.closedTargetSettings(N.opticalSettings(1550,30,re.length),target),input:input(shapes),
 effective_index:re,field:twoTriangles(inCore),origin:'local',serverVersion:'0.0.0',te_polarization_fraction:re.map(()=>0.99),effective_area:re.map(()=>1e-13)});
// an open run (the round-25 P4 fixture): each mode's |E|² per region of the window and in the PML
function openRun(modes,{substrate=true}={}){
 const at={core:[0,110],cladding:[0,800],substrate:[0,-800],substrateEdge:[0,-1100],pml:[0,-1700]},X0=[],T=[],keys=Object.keys(at);
 for(const k of keys){const [x,y]=at[k],d=1,n=X0.length;X0.push([(x-d)*1e-9,(y-d)*1e-9],[(x+2*d)*1e-9,(y-d)*1e-9],[(x-d)*1e-9,(y+2*d)*1e-9]);T.push([n,n+1,n+2]);}
 const value=w=>[Math.sqrt(w),0,0];
 return {settings:{boundary:'PML',pml:{thickness:'1000 nm',open_edges:['left','right','bottom','top'],target:'2.46'}},
  input:{model:{shapes:[CORE,...(substrate?[{...SUBSTRATE,material:'Silica'}]:[])]}},
  effective_index:modes.map((_,i)=>2.44-0.1*i),te_polarization_fraction:modes.map(()=>0.99),
  field:{node_coordinates:X0,triangles:T,real:modes.map(m=>keys.map(k=>value(m[k]??0))),imag:modes.map(()=>keys.map(()=>[0,0,0]))}};
}
// mode 1 the core mode, mode 2 mostly in the substrate near its edge
const T18_OPEN=[{core:0.6,substrate:0.2,cladding:0.2,pml:10},{substrateEdge:0.7,core:0.1,cladding:0.2,pml:5}];
// a match of A's mode 3 with B's mode 1 (overlap 0.99); A's modes 1, 2 and 4 and B's mode 2 unmatched
const pair=(a,b,eta,accepted=true)=>({a,b,unitA:[a],unitB:[b],eta,accepted,rowNext:0,columnNext:0,delta:-0.005});
function matchOf(nA,nB,accepted){
 const pairs=accepted.map(([a,b,eta])=>pair(a,b,eta));
 const rows=Array.from({length:nA},(_,i)=>({unit:[i],match:pairs.find(p=>p.a===i)||null,best:{eta:0.001,unit:[0]}}));
 const unmatchedB=Array.from({length:nB},(_,j)=>j).filter(j=>!pairs.some(p=>p.b===j)).map(j=>({unit:[j],best:{eta:0.002,unit:[0]}}));
 return {unitsA:rows.map(r=>r.unit),unitsB:Array.from({length:nB},(_,j)=>[j]),pairs,rows,unmatchedB};
}

test('C1: the core modes are those Results gives a core-mode note, by the same rule',()=>{
 const a=closedRun('0000000a',T18_NEAR,[false,false,true,false]),b=openRun(T18_OPEN);
 assert.deepEqual([...M.coreModes(a)],[2]);assert.deepEqual([...M.coreModes(b)],[0]);
 // the same modes as the notes Results shows (the round-25 line of workspace-app.mjs, unchanged)
 const resultsCore=run=>[...new Map([...M.coreNotes(run),...M.openRegionNotes(run).filter(n=>n.kind==='core')].map(n=>[n.mode,n.text])).keys()];
 for(const run of [a,b])assert.deepEqual([...M.coreModes(run)],resultsCore(run));
 assert.equal(M.coreNotes(a)[0].text,'Mode 3 is the core mode: 84 % of |E|² is in Core, which does not touch the window edge.');
 assert.equal(M.openRegionNotes(b)[0].text,'Mode 1 is the core mode: 60 % of |E|² in the window (PML excluded) is in Core, which does not touch the window edge.');
 // no core mode: the closed "Run as set" (highest n_eff, no core-mode note), and the core-only Design A/B
 // geometry, closed or open (no shape touches the window edge, so Results shows no core-mode note)
 assert.deepEqual([...M.coreModes(closedRun('0000000b',[2.6,2.5],[false,false],{target:null}))],[]);
 assert.deepEqual(M.coreNotes(closedRun('0000000c',[2.44,1.77],[true,true],{target:null,shapes:[CORE]})),[]);
 assert.deepEqual([...M.coreModes(closedRun('0000000c',[2.44,1.77],[true,true],{target:null,shapes:[CORE]}))],[]);
 assert.deepEqual([...M.coreModes(closedRun('0000000d',[2.44,1.77],[true,true],{shapes:[CORE]}))],[]);
 assert.deepEqual([...M.coreModes(openRun([{core:0.9,cladding:0.1},{core:0.6,cladding:0.4}],{substrate:false}))],[]);
 // a run without fields has no core mode
 assert.deepEqual([...M.coreModes({...b,field:null})],[]);
});

test('C1: the Matched modes picker and the table rows mark the core mode "(core)"',()=>{
 const a=closedRun('0000000a',T18_NEAR,[false,false,true,false]),b=openRun(T18_OPEN),m=matchOf(4,2,[[2,0,0.993]]);
 assert.deepEqual(X.fieldChoices(m,{a,b}).map(c=>[c.a,c.b,c.label]),[[2,0,'A mode 3 (core) ↔ B mode 1 (core) · overlap 0.99 · TE-like']]);
 // without runs (no polarization words), no mark: as before
 assert.deepEqual(X.fieldChoices(m).map(c=>c.label),['A mode 3 ↔ B mode 1 · overlap 0.99']);
 const rows=X.compareMatchRows(m,X.compareCores({a,b}));
 assert.deepEqual(rows.map(r=>[r.kind,r.text]),[
  ['a','A mode 1: no match in B (best overlap 0.00, with B mode 1)'],
  ['a','A mode 2: no match in B (best overlap 0.00, with B mode 1)'],
  ['match','A mode 3 (core) ↔ B mode 1 (core) · overlap 0.99 · Δn_eff −0.00500000'],
  ['a','A mode 4: no match in B (best overlap 0.00, with B mode 1)'],
  ['b','B mode 2: no match in A (best overlap 0.00, with A mode 1)']]);
 // without cores, the row texts are the round-17 texts, unchanged
 assert.deepEqual(X.compareMatchRows(m).map(r=>r.text)[2],'A mode 3 ↔ B mode 1 · overlap 0.99 · Δn_eff −0.00500000');
 // an unmatched core mode carries its mark too
 const none=matchOf(4,2,[]);
 assert.equal(X.compareMatchRows(none,X.compareCores({a,b}))[2].text,'A mode 3 (core): no match in B (best overlap 0.00, with B mode 1)');
 assert.equal(X.compareMatchRows(none,X.compareCores({a,b}))[4].text,'B mode 1 (core): no match in A (best overlap 0.00, with A mode 1)');
 assert.equal(X.coreMark(new Set([2]),[2]),' (core)');assert.equal(X.coreMark(new Set([2]),[1]),'');assert.equal(X.coreMark(new Set(),[0]),'');assert.equal(X.coreMark(new Set([0]),null),'');
 // a run with no core mode gets no mark: the closed "Run as set" against the open run
 const plain=closedRun('0000000b',[2.6,2.5],[false,false],{target:null}),mp=matchOf(2,2,[[1,0,0.85]]);
 assert.deepEqual(X.fieldChoices(mp,{a:plain,b}).map(c=>c.label),['A mode 2 ↔ B mode 1 (core) · overlap 0.85 · TE-like']);
 // the plain Design A/B runs: no mark anywhere
 const da=closedRun('0000000e',[2.44,1.77],[true,true],{target:null,shapes:[CORE]}),db=closedRun('0000000f',[2.43,1.76],[true,true],{target:null,shapes:[CORE]}),md=matchOf(2,2,[[0,0,1],[1,1,0.99]]);
 assert.deepEqual(X.fieldChoices(md,{a:da,b:db}).map(c=>c.label),['A mode 1 ↔ B mode 1 · overlap 1.00 · TE-like','A mode 2 ↔ B mode 2 · overlap 0.99 · TE-like']);
 assert.ok(X.compareMatchRows(md,X.compareCores({a:da,b:db})).every(r=>!r.text.includes('(core)')));
});

test('C1: "Core modes: …" only when the first modes are not matched but the core modes are',()=>{
 const a=closedRun('0000000a',T18_NEAR,[false,false,true,false]),b=openRun(T18_OPEN);
 assert.equal(X.coreMatchText(matchOf(4,2,[[2,0,0.993]]),{a,b}),'Core modes: A mode 3 ↔ B mode 1 · overlap 0.99');
 // the first modes matched with each other: no line
 const firstA=closedRun('00000010',[2.44,2.40],[true,false]);
 assert.deepEqual([...M.coreModes(firstA)],[0]);
 assert.equal(X.coreMatchText(matchOf(2,2,[[0,0,0.99]]),{a:firstA,b}),'');
 // the core modes not matched: no line
 assert.equal(X.coreMatchText(matchOf(4,2,[]),{a,b}),'');
 assert.equal(X.coreMatchText(matchOf(4,2,[[3,1,0.9]]),{a,b}),'');
 // a run with no core mode: no line
 const plain=closedRun('0000000b',[2.6,2.5],[false,false],{target:null});
 assert.equal(X.coreMatchText(matchOf(2,2,[[1,0,0.85]]),{a:plain,b}),'');
 // matching off or failed: no line
 assert.equal(X.coreMatchText({...matchOf(4,2,[[2,0,0.993]]),disabled:'Not matched'},{a,b}),'');
 assert.equal(X.coreMatchText({error:'The two runs\' windows do not overlap.'},{a,b}),'');
});

test('C1: Compare uses the marks and the line; matching, numbering and the default pick unchanged',()=>{
 const app=read('workspace-app.mjs'),match=read('workspace-match.mjs');
 assert.ok(app.includes("const cores=compareCores({a,b}),pairShort=(ua,ub)=>{const ma=coreMark(cores.a,ua),mb=coreMark(cores.b,ub);return ma&&mb?`${short(ua)} ↔ ${short(ub)}${CORE_MARK}`:`${short(ua)}${ma} ↔ ${short(ub)}${mb}`;};"));
 assert.ok(app.includes("for(const r of compareMatchRows(match,cores)){"));
 assert.ok(app.includes("tr.append(cell('th',pairShort(r.unitA,r.unitB),{scope:'row',title:r.text,'aria-label':r.text}),"));
 assert.ok(app.includes("tr.append(cell('th',pairShort(r.unitA,r.unitB),{scope:'row',title:r.text,'aria-label':`A ${unitName(r.unitA)}${coreMark(cores.a,r.unitA)} ↔ B ${unitName(r.unitB)}${coreMark(cores.b,r.unitB)}`}),"));
 assert.ok(app.includes("const coreLine=coreMatchText(match,{a,b});"));
 assert.ok(app.includes("box.append(runs,...(coreLine?[cell('p',coreLine,{class:'table-note',id:'compare-core-line'})]:[]),more,frame,note);"));
 // the default pick and the picker's order are unchanged
 assert.ok(app.includes("const chosen=choices.find(c=>compareChoice&&c.a===compareChoice.a&&c.b===compareChoice.b)||choices.find(c=>compareChoice&&c.a===compareChoice.a)||choices[0]||null;"));
 assert.ok(match.includes(" return out.sort((x,y)=>x.a-y.a);\n}"));
 assert.deepEqual([X.MATCH_THRESHOLD,X.MATCH_MARGIN],[0.8,0.1]);
 // the Results line that names the core mode is the round-25 line, unchanged
 assert.ok(app.includes("core=new Map([...coreNotes(run),...regions.filter(n=>n.kind==='core')].map(n=>[n.mode,n.text]))"));
});
