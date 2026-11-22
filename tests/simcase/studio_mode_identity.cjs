// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
// The modes table (workspace-modes.mjs): the TE fraction of the saved centroid field, Studio's
// polarization words, degenerate pairs, loss text, and the session files that carry them (V17).
const test=require('node:test');const assert=require('node:assert/strict');
const fs=require('node:fs');const path=require('node:path');
const STATIC='../../packages/simcase/src/simcase/studio/static/';
const FIXTURES=path.join(__dirname,'studio_session_fixtures');
const fixture=name=>fs.readFileSync(path.join(FIXTURES,name),'utf8');
let M,N,S,MP;
test.before(async()=>{
 M=await import(STATIC+'workspace-modes.mjs');N=await import(STATIC+'workspace-notebook.mjs');
 S=await import(STATIC+'workspace-multiphysics-session.mjs');MP=await import(STATIC+'workspace-multiphysics.mjs');
});

// two triangles of areas 1 and 1 (coordinates in metres); a mode per case
const square=(modes)=>({node_coordinates:[[0,0],[2e-6,0],[0,1e-6],[2e-6,1e-6]],triangles:[[0,1,2],[1,3,2]],
 real:modes.map(m=>m.map(v=>v.map(c=>typeof c==='number'?c:c[0]))),imag:modes.map(m=>m.map(v=>v.map(c=>typeof c==='number'?0:c[1])))});

test('f_TE = Σ A|Ex|² / Σ A(|Ex|² + |Ey|²): E_z left out, complex parts and areas weighted',()=>{
 const f=square([[[1,0,5],[[0,1],0,0]],[[0,1,0],[0,[1,-1],0]],[[1,1,0],[0,0,0]],[[0,0,1],[0,0,1]]]);
 assert.equal(M.teFraction(f,0),1);assert.equal(M.teFraction(f,1),0);assert.equal(M.teFraction(f,2),.5);
 assert.equal(M.teFraction(f,3),null,'no transverse field');
 const g=square([[[1,0,0],[0,1,0]]]);g.node_coordinates[1]=[6e-6,0];      // areas 3 and 1
 assert.ok(Math.abs(M.teFraction(g,0)-3/4)<1e-15);
});
test('words: TE-like at f_TE >= 0.9, TM-like at <= 0.1, otherwise hybrid; percentages to 0.1',()=>{
 assert.equal(M.polarizationWord(.9),'TE-like');assert.equal(M.polarizationWord(.8999),'hybrid');
 assert.equal(M.polarizationWord(.1),'TM-like');assert.equal(M.polarizationWord(.1001),'hybrid');
 assert.equal(M.tePercent(.98213),'98.2 % TE');
 const {rows}=M.modeTableRows([{re:2.44406001,im:0,fte:.98213,loss:null},{re:1.7,im:0,fte:.0123,loss:null}]);
 assert.deepEqual(rows.map(r=>[r.label,r.neff,r.polarization.text,r.loss]),[['Mode 1','2.44406001','TE-like · 98.2 % TE','lossless'],['Mode 2','1.70000000','TM-like · 1.2 % TE','lossless']]);
 assert.equal(rows[0].polarization.title,'TE = share of |E_x|² in |E_x|² + |E_y|², x horizontal');
});
test('degenerate pairs: Re n_eff within 1e-4 (inclusive) make one merged cell with the mean',()=>{
 assert.deepEqual(M.degenerateGroups([2.0,2.0001]),[[0,1]],'exactly 1e-4 is a pair');
 assert.deepEqual(M.degenerateGroups([2.0,2.00010001]),[]);
 assert.deepEqual(M.degenerateGroups([2.1,1.9,2.099985]),[],'only adjacent rows make a pair');
 assert.deepEqual(M.degenerateGroups([2,2.00009,2.00018]),[[0,1]],'no chaining: the whole group lies within 1e-4');
 // every row has its columns: a merged cell spans adjacent rows only
 const layout=M.modeTableRows([{re:2.00012,im:0,fte:.9,loss:null},{re:2.00005,im:0,fte:.2,loss:null},{re:1.9,im:0,fte:.95,loss:null}]).rows;
 let covered=0;for(const r of layout){if(r.polarization){assert.equal(covered,0);covered=r.polarization.rowspan-1;}else{assert.ok(covered>0,'a row without a cell is covered by the one above');covered--;}}
 // a pair without fractions keeps each row's reason, not a merged "—"
 const missing=M.modeTableRows([{re:2.5,im:0,fte:null,loss:null},{re:2.49999,im:0,fte:null,loss:null}],{missing:'PML result'});
 assert.deepEqual(missing.rows.map(r=>[r.polarization.text,r.polarization.title]),[['—','PML result'],['—','PML result']]);
 const {rows,groups}=M.modeTableRows([{re:2.5,im:0,fte:.73,loss:null},{re:2.499985,im:0,fte:.27,loss:null},{re:2.1,im:0,fte:.95,loss:null}]);
 assert.deepEqual(groups,[[0,1]]);
 assert.equal(rows[0].polarization.text,'pair (n_eff within 0.0001) · 50 % TE together');
 assert.equal(rows[0].polarization.rowspan,2);assert.equal(rows[1].polarization,null);
 assert.match(rows[0].polarization.title,/Each member's polarization is not defined/);
 assert.equal(rows[2].polarization.text,'TE-like · 95.0 % TE');
 const modes=[{re:2.5,fte:.73},{re:2.499985,fte:.27}];
 assert.equal(M.modeOptionLabel(0,modes),'Mode 1 · pair · n_eff 2.50000000');
 assert.equal(M.modeOptionLabel(0,[{re:2.44406001,fte:.982},{re:1.7,fte:.01}]),'Mode 1 · TE-like · n_eff 2.44406001');
});
test('loss: dB/cm = propagation_loss / 100 to 4 significant digits; "lossless" and its note when Im n_eff = 0',()=>{
 const im=1.0647158815313716e-4,db=M.propagationLoss(im,1.55e-6);
 assert.equal(M.lossText(im,db),'37.49 dB/cm');
 assert.ok(Math.abs(db-40*Math.PI/Math.log(10)*im/1.55e-6)<=1e-12*db);
 assert.equal(M.lossText(0,null),'lossless');
 const table=M.modeTableRows([{re:2.4,im:0,fte:1,loss:null}]);assert.equal(table.lossless,true);
 assert.equal(M.LOSSLESS_NOTE,'Lossless: all materials have k = 0 at this wavelength. Leakage and radiation are not computed in a closed window.');
 assert.equal(M.modeTableRows([{re:2.4,im:1e-4,fte:1,loss:3749}]).lossless,false);
 assert.equal(M.RANKING_TEXT,'Modes are ranked by effective index.');assert.equal(MP.RANKING_CAVEAT,M.RANKING_TEXT);
});
test('V17: optical v6 and v7 sessions open with two modes and the TE fraction computed by Studio',()=>{
 for(const name of ['optical-v6-one.json','optical-v7-one.json','optical-v6-three.json','optical-v7-three.json']){
  const session=N.parseSession(fixture(name));
  for(const run of session.runs){
   const modes=M.opticalModes(run);assert.equal(modes.length,2,name);
   for(let i=0;i<2;i++){const f=M.teFraction(run.field,i);assert.ok(f===null||(f>=0&&f<=1),name);assert.equal(modes[i].fte,f);}
   assert.equal(M.SOURCE_TEXT[run.te.source],'computed by Studio from the saved field');
  }
  // the fraction is derived, never written: a session written after reading it holds no new key
  assert.equal(JSON.stringify(N.createSession(session.input,session.runs,session.selected,session.comparison,session.view)).includes('te'+'_polarization'),false,name);
 }
});
test('the engine value of a fresh run is shown with its source and not written to the session',()=>{
 const s=JSON.parse(fixture('state-one.json')),run=s.runs[0];
 const engine=M.engineTeFraction({mode_postprocessing:{te_polarization_fraction:{unit:'1',values:[[.99,.01]]}}});
 assert.deepEqual(engine,[.99,.01]);
 Object.defineProperty(run,'te',{value:{values:engine,source:'engine'},enumerable:false});
 assert.equal(M.opticalModes(run)[0].fte,.99);
 assert.equal(JSON.stringify(N.createSession(s.input,s.runs,s.selected,s.comparison,s.view)),fixture('optical-v7-one.json'));
 assert.equal(M.engineTeFraction({}),null);
});
// a version 8 session with its modes result made complex ({re, im}) and given the engine's fraction
function complexV8(){
 // one JSON round trip first: the fixture holds -0, which JSON.stringify writes as 0
 const doc=JSON.parse(JSON.stringify(JSON.parse(fixture('multiphysics-v8.json'))));
 for(const run of doc.runs)for(const p of Object.values(run.result.physics))if(p.type==='em.modes2d'){
  const re=p.effective_index.values;p.effective_index={unit:'1',re,im:re.map(row=>row.map(()=>1.0647158815313716e-4)),time_convention:'exp(-i omega t)'};
  p.summary={...(p.summary||{}),formulation:'vector',propagation_loss:{unit:'dB/m',values:re.map(row=>row.map(()=>M.propagationLoss(1.0647158815313716e-4,1.55e-6)))},
   mode_postprocessing:{...(p.summary?.mode_postprocessing||{}),te_polarization_fraction:{unit:'1',values:re.map(row=>row.map(()=>.985))}}};
  const {digest,...record}=run;run.digest=S.recordDigest(record);
 }
 return doc;
}
test('V17: a version 8 run with a complex n_eff {re, im} reads, writes and reads back with the same digest',()=>{
 const doc=complexV8(),text=JSON.stringify(doc),read=N.parseSession(text);
 assert.equal(read.application,'multiphysics');
 const state={document:read.document,runs:read.runs,baselines:read.baselines,selected:read.selected,view:read.view};
 const again=N.parseSession(S.writeMultiphysicsSession(state).text);
 assert.deepEqual(again.runs.map(r=>r.result),read.runs.map(r=>r.result));
 const p=Object.values(read.runs[0].result.physics).find(x=>x.type==='em.modes2d');
 const identity=M.physicsModes(p),{rows}=M.modeTableRows(identity.modes,{missing:identity.missing});
 assert.equal(identity.source,'engine');assert.equal(rows[0].loss,'37.49 dB/cm');assert.equal(rows[0].polarization.text,'TE-like · 98.5 % TE');
 assert.deepEqual(MP.effectiveIndexRows(p).map(r=>r.value),p.effective_index.re.flat());
 // a complex series of mismatched shape or without its time convention is refused by name
 for(const change of [q=>q.effective_index.im[0].pop(),q=>delete q.effective_index.time_convention,q=>q.effective_index.values=q.effective_index.re]){
  const bad=complexV8();const run=bad.runs[0];change(Object.values(run.result.physics).find(x=>x.type==='em.modes2d'));const {digest,...record}=run;run.digest=S.recordDigest(record);
  assert.throws(()=>N.parseSession(JSON.stringify(bad)),/effective index is not well formed/);
 }
});
test('a vector run without saved fractions says Run again; fractions out of range or of another length are refused',()=>{
 const base={effective_index:{unit:'1',values:[[2.4,1.7]]},vacuum_wavelength:{unit:'m',values:[1.55e-6]},summary:{formulation:'vector'}};
 const old=M.physicsModes(base),rows=M.modeTableRows(old.modes,{missing:old.missing}).rows;
 assert.equal(rows[0].polarization.text,'—');assert.match(rows[0].polarization.title,/^Run again to compute/);
 const bad=v=>M.physicsModes({...base,summary:{formulation:'vector',mode_postprocessing:{te_polarization_fraction:{unit:'1',values:[v]}}}});
 assert.equal(bad([5,.1]).source,null);assert.equal(bad([.9]).source,null);assert.match(bad([.9]).missing,/do not match/);
 assert.equal(bad([.95,.02]).source,'engine');
});
test('V17: the version 8 fixture (scalar modes, saved before the TE fraction) opens and shows "—" with its reason',()=>{
 const read=N.parseSession(fixture('multiphysics-v8.json'));
 const p=Object.values(read.runs[0].result.physics).find(x=>x.type==='em.modes2d');
 const identity=M.physicsModes(p),{rows}=M.modeTableRows(identity.modes,{missing:identity.missing});
 assert.equal(rows[0].polarization.text,'—');
 if(p.summary?.formulation==='vector')assert.match(rows[0].polarization.title,/^Run again to compute/);
 else assert.match(rows[0].polarization.title,/^Scalar formulation/);
});
