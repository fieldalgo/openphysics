// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
// Compact heated maps in the tab (design "Session versions 16 and 17", slice S3, section 3.1): the
// checks that need no engine run. While every map fits as text nothing changes (version 8 or 15, byte
// for byte); at the first arrival where the maps would not all fit as text every map of the tab is made
// compact, and from then on every map that arrives (an opened or restored file only when its maps would
// not all fit); a run whose maps cannot be compact stays text; Keep Run N's maps brings compact maps
// back compact; the estimate before a run counts compact sizes; the two notes and no Messages sentence;
// a seeded sequence of 600 steps where the tab equals the file and the order of 3.2 holds with compact
// sizes. HQ5 and HQ6 on engine results: tests/simcase/studio_heated_retention_engine.cjs.
const test=require('node:test');const assert=require('node:assert/strict');
const fs=require('node:fs');const path=require('node:path');
const S='../../packages/simcase/src/simcase/studio/static/';
const read=name=>fs.readFileSync(path.join(__dirname,S,name),'utf8');
let M,N,B,W,C;
test.before(async()=>{M=await import(S+'workspace-multiphysics-session.mjs');N=await import(S+'workspace-notebook.mjs');B=await import(S+'workspace-budget.mjs');
 W=await import(S+'workspace-multiphysics-retention.mjs');C=await import('./studio_session_fixtures/compact_heated_sessions.mjs');});
const VIEW={page:'Results',selection:'results:modes1',index_map:'change',baseline_option:false};
const bytesOf=t=>Buffer.byteLength(t,'utf8');
const run=(number,n=40,extra={})=>({job:'mp-'+(0x17e000000000+number).toString(16),number,label:'',pinned:false,completedAt:new Date(Date.UTC(2026,10,26,0,0,number)).toISOString(),serverVersion:'0.0.2',
 doc:C.documentOf(`${number}e14 W/m^3`),events:[],order:[['heat1'],['modes1']],result:C.stripResult(n,{seed:number}),maps:'kept',origin:'local',...extra});
const stateOf=(runs,selected=runs.at(-1)?.job??null)=>({document:C.documentOf(),runs,baselines:{},selected,view:VIEW});
const textBytes=r=>M.mapBytes({...r,result:r.result,maps:'kept'});

test('the tab: no conversion while every map fits as text; at the first arrival that would not fit, every map is compact; then every arrival is',()=>{
 const runs=[run(1),run(2),run(3)],state=stateOf(runs),fits=M.sessionText(state).length;
 // within the budget: nothing changes, version 8 byte for byte
 assert.deepEqual(M.compactMaps(state,{budget:fits+10}),{converted:[],started:false});
 assert.ok(runs.every(r=>r.maps==='kept'));assert.equal(JSON.parse(M.sessionText(state)).version,8);
 // over it: every map compact, the first conversion
 const out=M.chooseMapsAtArrival(state,{budget:fits-10});
 assert.deepEqual(out.converted.map(r=>r.number),[1,2,3]);assert.equal(out.started,true);assert.deepEqual(out.letGo,[]);
 assert.ok(runs.every(r=>r.maps==='compact'));assert.equal(JSON.parse(M.sessionText(state)).version,17);
 // the next map arrives compact even when it would fit as text
 const next=run(4);state.runs.push(next);state.selected=next.job;
 const again=M.compactMaps(state,{budget:1e9});
 assert.deepEqual(again.converted.map(r=>r.number),[4]);assert.equal(again.started,false);
 // an opened or restored session converts only when its maps would not all fit
 const opened=stateOf([run(5),run(6)]);opened.runs[0].maps='kept';
 assert.deepEqual(M.compactMaps(opened,{budget:1e9,loaded:true}).converted,[]);
 // the tab holds what a file holds: the file read again is the tab's text
 const text=M.sessionText(state);assert.equal(M.sessionText(stateOf(N.parseSession(text).runs,state.selected)),text);
 // compact bytes are smaller than text bytes (the engine's meshes: HQ6)
 for(const r of runs){const t=textBytes({...r,result:C.stripResult(40,{seed:r.number})});assert.ok(M.mapBytes(r)<t,`Run ${r.number}: ${M.mapBytes(r)} of ${t}`);}
});

test('a run whose maps cannot be compact stays text in a compact tab; Keep Run N\'s maps brings compact maps back compact',()=>{
 const odd=run(2);odd.result.mesh.region_names=Array.from({length:257},(_,i)=>i<2?['background','core'][i]:'r'+i);
 const runs=[run(1),odd,run(3)],state=stateOf(runs),bytes=M.mapBytes(odd);
 M.compactMaps(state,{budget:1000});
 assert.deepEqual(runs.map(r=>r.maps),['compact','kept','compact']);assert.equal(M.mapBytes(odd),bytes);
 // let go, then taken back: the compact record is the same
 const record=M.sessionJson(M.sessionRun(runs[0]));M.letGoMaps(runs[0]);assert.equal(runs[0].maps,'not kept');
 assert.equal(M.takeBackMaps(runs[0]),true);assert.equal(runs[0].maps,'compact');assert.equal(M.sessionJson(M.sessionRun(runs[0])),record);
 // a recompute's maps attached in a compact tab are compacted at its arrival
 const r3=runs[2];M.letGoMaps(r3);M.forgetHeldMaps(runs);M.attachMaps(r3,C.stripResult(40,{seed:3}));assert.equal(r3.maps,'kept');
 assert.deepEqual(M.compactMaps(state,{first:[r3.job]}).converted,[r3]);assert.equal(r3.maps,'compact');
 assert.equal(M.compactMapBytesOf(odd),null);assert.equal(M.compactMapBytesOf(r3),M.mapBytes(r3));
});

test('before the run: "If you run" counts the compact sizes the arrival will use',()=>{
 // text: three runs fill the budget; the next one would let Run 1 go as text, but not once compact
 const runs=[run(1,200),run(2,200),run(3,200)],state=stateOf(runs),text=M.sessionText(state).length,budget=text+Math.round(textBytes(runs[0])/2);
 const out=M.chooseMaps({...state,runs:[...runs,{...runs[2],job:'mp-ffffffffffff',number:4}]},{budget});assert.equal(out.fits,false);
 // the prediction with the page's budget: compact sizes when the arrival converts
 const big=Array.from({length:20},(_,i)=>run(i+1,1500)),s20=stateOf(big.slice(0,19));
 const before=W.predictedMapsLetGo(s20,big[0].doc);
 M.compactMaps(s20);const after=M.chooseMaps({...s20,runs:M.appendMultiphysicsRun(s20.runs,{...big[18],job:'mp-fffffffffffe',number:20})});
 assert.deepEqual(before.map(r=>r.number),after.letGo.filter(r=>r.job!=='mp-fffffffffffe').map(r=>r.number));
});

test('the words: the notes under the maps and the run list; no Messages sentence at the conversion',()=>{
 assert.equal(W.MP_COMPACT_RESULTS_TEXT,"Maps at single precision (float32). The values above are the engine's.");
 assert.equal(W.MP_COMPACT_NOTE,'When maps would not all fit, they are kept at single precision.');
 const runs=[run(1)];assert.equal(W.mpRunsKeptNote(runs),W.MP_RUNS_KEPT_TEXT);M.compactRunMaps(runs[0]);
 assert.equal(W.mpRunsKeptNote(runs),W.MP_RUNS_KEPT_TEXT+' When maps would not all fit, they are kept at single precision.');
 const view=read('workspace-multiphysics-view.mjs');
 assert.ok(view.includes('<p data-mp-runs-kept>${esc(mpRunsKeptNote(runs))}</p>'));
 assert.ok(view.includes("const compactNote=`<p class=\"input-hint\" data-mp-map-precision>${esc(MP_COMPACT_RESULTS_TEXT)}</p>`;"));
 assert.equal(view.split("${lastRun.maps==='compact'?compactNote:''}").length,3);
 // the arrival converts first, then lets go in the order; its words are the let-go words only
 assert.ok(view.includes("const state=sessionState();let out;try{compactMaps(state,{first,loaded});out=chooseMaps(state,{first});}catch{return '';}"));
 assert.ok(view.includes("const mapWords=applyMapBudget([],{loaded:true});"));
 assert.doesNotMatch(view,/single precision/);
});

function rng(seed){let s=seed>>>0;return ()=>{s=(s*1664525+1013904223)>>>0;return s/2**32;};}
test('600 seeded steps with compact maps: the tab equals the file and recovery, the order of 3.2 with compact sizes, no number reused',()=>{
 const random=rng(20261126),pick=list=>list[Math.floor(random()*list.length)],budget=60000;
 let runs=[],selected=null,top=0,converted=0;
 for(let step=0;step<600;step++){
  const op=pick(runs.length?['result','result','pin','unpin','select','reopen']:['result']);
  if(op==='result'){const r=run(++top,pick([3,10,40,120]));try{runs=M.appendMultiphysicsRun(runs,r);selected=r.job;}catch{top--;continue;}}
  else if(op==='pin')pick(runs).pinned=true;else if(op==='unpin')pick(runs).pinned=false;else if(op==='select'){selected=pick(runs).job;continue;}
  else if(op==='reopen'){const s=N.parseSession(M.sessionText(stateOf(runs,selected)));runs=s.runs;}
  if(op==='pin'||op==='unpin')continue;
  const state=stateOf(runs,selected);
  const out=M.compactMaps(state,{budget,loaded:op==='reopen'});converted+=out.converted.length;
  // the reference: the order, each map tried with the session text written in full
  const order=B.budgetOrder(runs.filter(r=>r.maps!=='not kept'),selected),keep=new Set();
  if(bytesOf(M.sessionText(state))>budget)order.forEach((r,i)=>{const trial=new Set([...keep,r.job]);if(bytesOf(M.sessionText(state,trial))<=budget||(i===0&&r.job===selected))keep.add(r.job);});
  else for(const r of order)keep.add(r.job);
  const chosen=M.keepMapsAtArrival(state,{budget}),text=M.sessionText(state);
  assert.deepEqual(runs.filter(r=>r.maps!=='not kept').map(r=>r.number),runs.filter(r=>keep.has(r.job)).map(r=>r.number),`step ${step}`);
  if(chosen.total!==null)assert.equal(chosen.total,bytesOf(text),`step ${step}: the cached sum`);
  assert.equal(M.recoveryText(state).text,text,`step ${step}: recovery`);
  assert.equal(M.sessionText(stateOf(N.parseSession(text).runs,selected)),text,`step ${step}: the file read again`);
  assert.equal(new Set(runs.map(r=>r.number)).size,runs.length);
  if(runs.some(r=>r.maps==='compact'))assert.equal(JSON.parse(text).version,17);
 }
 assert.ok(converted>0);
});
