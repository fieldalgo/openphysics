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
 assert.deepEqual(rows.map(r=>[r.label,r.neff,r.polarization.text,r.loss]),[['Mode 1','2.44406001','TE-like · 98.2 % TE','0 dB/cm'],['Mode 2','1.70000000','TM-like · 98.8 % TM (1.2 % TE)','0 dB/cm']]);
 // a TM-like cell names its dominant TM share first; the two shares add to 100.0 as shown
 assert.equal(M.polarizationShare(.0315),'96.9 % TM (3.1 % TE)');assert.equal(M.polarizationShare(.1),'90.0 % TM (10.0 % TE)');assert.equal(M.polarizationShare(0),'100.0 % TM (0.0 % TE)');
 for(let k=0;k<=1000;k++){const f=k/10000,m=/^(\d+\.\d) % TM \((\d+\.\d) % TE\)$/.exec(M.polarizationShare(f));assert.ok(m);assert.equal((Number(m[1])*10+Number(m[2])*10).toFixed(0),'1000');}
 // TE-like and hybrid cells are unchanged
 assert.equal(M.polarizationShare(.98213),'98.2 % TE');assert.equal(M.polarizationShare(.5),'50.0 % TE');
 assert.equal(rows[0].polarization.title,'TE = share of |E_x|² in |E_x|² + |E_y|², x horizontal');
});
test('degenerate pairs: Re n_eff within 1e-3 (inclusive) make one merged cell with the mean',()=>{
 assert.equal(M.PAIR_TOLERANCE,1e-3);
 assert.deepEqual(M.degenerateGroups([2.0,2.001]),[[0,1]],'exactly 1e-3 is a pair');
 assert.deepEqual(M.degenerateGroups([2.0,2.0010001]),[]);
 assert.deepEqual(M.degenerateGroups([2.0,1.99974]),[[0,1]],'a mesh split of 2.6e-4 (the square core at 10 nm) is a pair');
 assert.deepEqual(M.degenerateGroups([2.1,1.9,2.09985]),[],'only adjacent rows make a pair');
 assert.deepEqual(M.degenerateGroups([2,2.0009,2.0018]),[[0,1]],'no chaining: the whole group lies within 1e-3');
 // every row has its columns: a merged cell spans adjacent rows only
 const layout=M.modeTableRows([{re:2.0012,im:0,fte:.9,loss:null},{re:2.0005,im:0,fte:.2,loss:null},{re:1.9,im:0,fte:.95,loss:null}]).rows;
 let covered=0;for(const r of layout){if(r.polarization){assert.equal(covered,0);covered=r.polarization.rowspan-1;}else{assert.ok(covered>0,'a row without a cell is covered by the one above');covered--;}}
 // a pair without fractions keeps each row's reason, not a merged "—"
 const missing=M.modeTableRows([{re:2.5,im:0,fte:null,loss:null},{re:2.49999,im:0,fte:null,loss:null}],{missing:'PML result'});
 assert.deepEqual(missing.rows.map(r=>[r.polarization.text,r.polarization.title]),[['—','PML result'],['—','PML result']]);
 const {rows,groups}=M.modeTableRows([{re:2.5,im:0,fte:.73,loss:null},{re:2.499985,im:0,fte:.27,loss:null},{re:2.1,im:0,fte:.95,loss:null}]);
 assert.deepEqual(groups,[[0,1]]);
 assert.equal(rows[0].polarization.text,'pair (n_eff within 1e-3) · 50 % TE together');
 assert.equal(rows[0].polarization.rowspan,2);assert.equal(rows[1].polarization,null);
 assert.match(rows[0].polarization.title,/Each member's polarization is not defined/);
 assert.equal(rows[2].polarization.text,'TE-like · 95.0 % TE');
 const modes=[{re:2.5,fte:.73},{re:2.499985,fte:.27}];
 assert.equal(M.modeOptionLabel(0,modes),'Mode 1 · pair · n_eff 2.50000000');
 assert.equal(M.modeOptionLabel(0,[{re:2.44406001,fte:.982},{re:1.7,fte:.01}]),'Mode 1 · TE-like · n_eff 2.44406001');
});
test('loss: dB/cm = propagation_loss / 100 to 4 significant digits; "0 dB/cm" and its absorption-only note when Im n_eff = 0',()=>{
 const im=1.0647158815313716e-4,db=M.propagationLoss(im,1.55e-6);
 assert.equal(M.lossText(im,db),'37.49 dB/cm');
 assert.ok(Math.abs(db-40*Math.PI/Math.log(10)*im/1.55e-6)<=1e-12*db);
 // the documented formula: dB/cm = 20 log10(e) k0 Im(n_eff) / 100, k0 = 2 pi / lambda0 in 1/m
 const k0=2*Math.PI/1.55e-6;assert.ok(Math.abs(db/100-20*Math.log10(Math.E)*k0*im/100)<=1e-12*db/100);
 // an independent literal: Im n_eff = 1e-4 at lambda0 = 1550 nm,
 // 20 log10(e) x (2 pi / 1.55e-6 m) x 1e-4 / 100 = 8.685889638 x 4.053667940e6 x 1e-4 / 100 = 35.21 dB/cm
 assert.equal(M.lossText(1e-4,M.propagationLoss(1e-4,1.55e-6)),'35.21 dB/cm');
 assert.equal(M.lossText(0,null),'0 dB/cm');
 // pre-registered: no threshold; a tiny nonzero Im n_eff is shown as it is, to 4 significant digits
 const tiny=1e-15;assert.equal(M.lossText(tiny,M.propagationLoss(tiny,1.55e-6)),(M.propagationLoss(tiny,1.55e-6)/100).toPrecision(4)+' dB/cm');
 assert.equal(M.lossText(tiny,M.propagationLoss(tiny,1.55e-6)),'3.521e-10 dB/cm');
 const table=M.modeTableRows([{re:2.4,im:0,fte:1,loss:null}]);assert.equal(table.lossless,true);assert.equal(table.rows[0].lossless,true);
 assert.equal(M.LOSSLESS_NOTE,'Absorption loss counts material absorption (k) only: all materials have k = 0 at this wavelength, so it is 0 dB/cm. Leakage and radiation are not computed in a closed window.');
 assert.equal(M.modeTableRows([{re:2.4,im:tiny,fte:1,loss:M.propagationLoss(tiny,1.55e-6)}]).rows[0].lossless,false);
 // an optical run's n_eff is real: every mode reads 0 dB/cm
 assert.deepEqual(M.opticalModes({effective_index:[2.4,1.7],te:{values:[.98,.01],source:'studio'}}).map(m=>M.lossText(m.im,m.loss)),['0 dB/cm','0 dB/cm']);
 assert.equal(M.modeTableRows([{re:2.4,im:1e-4,fte:1,loss:3749}]).lossless,false);
 assert.equal(M.RANKING_TEXT,'Modes are ranked by effective index.');assert.equal(MP.RANKING_CAVEAT,M.RANKING_TEXT);
});
test('round 10: the loss column of a closed window is "Absorption loss (dB/cm)", every cell with the absorption-only help; an open boundary (PML) reads "Loss (dB/cm)"',()=>{
 const tiny=1e-15,lossy=M.propagationLoss(1e-4,1.55e-6);
 // closed, lossless: the header, the help on every cell and the note with the lossless words
 const closed=M.modeTableRows([{re:2.4,im:0,fte:1,loss:null},{re:1.7,im:0,fte:.01,loss:null}]);
 assert.equal(closed.loss.header,'Absorption loss (dB/cm)');
 assert.equal(closed.loss.help,'Absorption (material k) only; leakage and radiation are not computed in a closed window');
 assert.ok(closed.rows.every(r=>r.lossTitle===closed.loss.help&&r.loss==='0 dB/cm'));
 assert.equal(closed.loss.note,M.LOSSLESS_NOTE);
 // closed, lossy: the same header and help, digits unchanged, the note without "k = 0"
 const absorbing=M.modeTableRows([{re:2.4,im:1e-4,fte:1,loss:lossy},{re:1.7,im:tiny,fte:.01,loss:M.propagationLoss(tiny,1.55e-6)}]);
 assert.deepEqual(absorbing.rows.map(r=>r.loss),['35.21 dB/cm','3.521e-10 dB/cm']);
 assert.equal(absorbing.loss.header,'Absorption loss (dB/cm)');assert.ok(absorbing.rows.every(r=>r.lossTitle===M.ABSORPTION_HELP));
 assert.equal(absorbing.loss.note,'Absorption loss counts material absorption (k) only. Leakage and radiation are not computed in a closed window.');
 assert.doesNotMatch(absorbing.loss.note,/k = 0/);
 // an open boundary: Im n_eff includes leakage into the PML, so the column does not say absorption only
 const pml=M.physicsModes({effective_index:{unit:'1',re:[[2.4]],im:[[1e-4]]},vacuum_wavelength:{unit:'m',values:[1.55e-6]},summary:{formulation:'vector',open_boundary:true}});
 assert.equal(pml.open,true);
 const open=M.modeTableRows(pml.modes,{open:pml.open});
 assert.equal(open.loss.header,'Loss (dB/cm)');
 assert.equal(open.loss.help,'Material absorption (k) and leakage into the PML of the open boundary');
 assert.equal(open.rows[0].lossTitle,open.loss.help);assert.equal(open.rows[0].loss,'35.21 dB/cm');
 assert.equal(open.loss.note,'Loss includes material absorption (k) and leakage into the PML of the open boundary. Leakage depends on what lies outside the window: shapes touching an open edge continue through the PML.');
 assert.doesNotMatch(open.loss.header+open.loss.help+open.loss.note,/Absorption loss|only/);
 // a closed multiphysics result keeps the absorption header
 assert.equal(M.physicsModes({effective_index:{unit:'1',values:[[2.4]]},summary:{formulation:'vector'}}).open,false);
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

// ---- Effective area (M3) -----------------------------------------------------------------------
test('A_eff = (Σ A|E|²)² / Σ A|E|⁴ with all three components, complex parts and areas weighted',()=>{
 // areas 1e-12 and 1e-12 m²; |E|² = 1 + 4 + 9 = 14 in the first triangle, 2 (complex E_z) in the second
 const f=square([[[1,2,3],[0,1,[0,1]]],[[1,0,0],[1,0,0]],[[0,0,0],[0,0,0]]]);
 const a=1e-12,expected=(a*14+a*2)**2/(a*14*14+a*2*2);
 assert.ok(Math.abs(M.effectiveArea(f,0)-expected)<=1e-15*expected);
 // a uniform field over the whole window: A_eff is the window's area
 assert.ok(Math.abs(M.effectiveArea(f,1)-2e-12)<=1e-27);
 assert.equal(M.effectiveArea(f,2),null,'no field');
 // scale free: a mode times any complex number has the same area
 const g=square([[[[3,-4],0,[0,2]],[0,[1,1],0]]]),h=square([[[[6,-8],0,[0,4]],[0,[2,2],0]]]);
 assert.ok(Math.abs(M.effectiveArea(g,0)/M.effectiveArea(h,0)-1)<=1e-15);
 assert.equal(M.areaText(1.9094544e-13),'0.1909');assert.equal(M.areaText(null),'—');
 assert.equal(M.areaText(12345.6e-12),'12346','no exponent for large windows');assert.equal(M.areaText(999.94e-12),'999.9');
 assert.equal(M.AREA_HELP,'Effective area (∫|E|²)²/∫|E|⁴ over the window, all three field components');
});
test('the modes table gives each mode its A_eff; a pair member keeps its own value with a note',()=>{
 const {rows}=M.modeTableRows([{re:2.5,im:0,fte:.73,loss:null,area:3e-13},{re:2.499985,im:0,fte:.27,loss:null,area:5e-13},{re:2.1,im:0,fte:.95,loss:null,area:4e-13}]);
 assert.deepEqual(rows.map(r=>r.area.text),['0.3000','0.5000','0.4000']);
 assert.match(rows[0].area.title,/degenerate pair/);assert.match(rows[1].area.title,/degenerate pair/);
 assert.equal(rows[2].area.title,M.AREA_HELP);
 const none=M.modeTableRows([{re:2.4,im:0,fte:1,loss:null,area:null}],{areaMissing:'Run again to compute: x'}).rows[0].area;
 assert.deepEqual([none.text,none.title],['—','Run again to compute: x']);
 assert.equal(M.modeTableRows([{re:2.4,im:0,fte:1,loss:null,area:null}]).rows[0].area.title,'No field: no effective area');
 // a scalar result names |φ|², not three field components
 const scalar=M.physicsModes({effective_index:{unit:'1',values:[[2.4]]},summary:{formulation:'scalar',mode_postprocessing:{effective_area:{unit:'m^2',values:[[2e-13]]}}}});
 const cell=M.modeTableRows(scalar.modes,{areaHelp:scalar.areaHelp}).rows[0].area;
 assert.equal(cell.text,'0.2000');assert.equal(cell.title,M.SCALAR_AREA_HELP);assert.match(cell.title,/φ/);
});
test('Compare: a matched pair shows the mean A_eff of its members with a note, a single mode its own',async()=>{
 const X=await import(STATIC+'workspace-match.mjs');
 const s=JSON.parse(fixture('state-one.json')),run=s.runs[0];
 const own=M.opticalModes(run);
 const one=X.unitArea(run,[0]);assert.equal(one.value,own[0].area);assert.equal(one.text,M.areaText(own[0].area));
 const pair=X.unitArea(run,[0,1]);assert.equal(pair.value,(own[0].area+own[1].area)/2);
 assert.match(pair.text,/^mean \d\.\d{4}$/);assert.match(pair.title,/Mean of the pair members/);
});
test('round 10, Compare: the absorption loss of a unit from the saved indices, a pair the mean of its members',async()=>{
 const X=await import(STATIC+'workspace-match.mjs');
 const s=JSON.parse(fixture('state-one.json')),run=s.runs[0];
 // an optical run of the template is lossless: every unit reads 0 dB/cm, with the absorption help
 for(const unit of [[0],[1],[0,1]]){const v=X.unitLoss(run,unit);assert.deepEqual([v.text,v.value,v.title],['0 dB/cm',0,M.ABSORPTION_HELP]);}
 assert.deepEqual(X.unitLoss(run,null),{text:'—',value:null,title:M.ABSORPTION_HELP});
 // complex indices saved with a run (no field is needed): the mode's own text, a pair the mean in dB/cm
 const lossy={effective_index:[2.4,2.3999],effective_index_im:[1e-4,0],input:{model:{wavelength:1550}},te_polarization_fraction:[.5,.5],effective_area:[1e-13,1e-13]};
 const one=X.unitLoss(lossy,[0]);assert.equal(one.text,'35.21 dB/cm');assert.ok(Math.abs(one.value-M.propagationLoss(1e-4,1.55e-6)/100)<=1e-12*one.value);
 assert.equal(X.unitLoss(lossy,[1]).text,'0 dB/cm');
 const pair=X.unitLoss(lossy,[0,1]);assert.equal(pair.text,'mean '+(M.propagationLoss(1e-4,1.55e-6)/200).toPrecision(4)+' dB/cm');// 35.2097 dB/cm / 2 = 17.6049 dB/cm
 assert.equal(pair.text,'mean 17.60 dB/cm');
});
test('V17-M3: optical v6 and v7 sessions open with A_eff computed by Studio; v7 is written byte for byte',()=>{
 for(const name of ['optical-v6-one.json','optical-v7-one.json','optical-v6-three.json','optical-v7-three.json']){
  const session=N.parseSession(fixture(name));
  for(const run of session.runs){
   const modes=M.opticalModes(run);
   // each mode against the formula written out here, independently of the module
   const X=run.field.node_coordinates;
   for(let i=0;i<2;i++){
    let num=0,den=0;run.field.triangles.forEach((t,k)=>{const [a,b,c]=t.map(j=>X[j]),A=Math.abs((b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0]))/2;
     let d=0;for(let q=0;q<3;q++)d+=run.field.real[i][k][q]**2+run.field.imag[i][k][q]**2;num+=A*d;den+=A*d*d;});
    assert.ok(Math.abs(modes[i].area/(num*num/den)-1)<=1e-12,name);
   }
   assert.equal(M.SOURCE_TEXT[run.area.source],'computed by Studio from the saved field');
   assert.ok(M.modeTableRows(modes).rows.every(r=>r.area.text===M.areaText(r.area.value)&&/^\d+(\.\d+)?$/.test(r.area.text)),name);
  }
  const written=JSON.stringify(N.createSession(session.input,session.runs,session.selected,session.comparison,session.view));
  assert.equal(written.includes('effective'+'_area'),false,name);
 }
 // v7 written byte for byte from the same state after Studio computed every A_eff
 for(const state of ['one','three']){
  const st=JSON.parse(fixture(`state-${state}.json`));for(const run of st.runs)M.opticalModes(run);
  assert.equal(JSON.stringify(N.createSession(st.input,st.runs,st.selected,st.comparison,st.view)),fixture(`optical-v7-${state}.json`),state);
 }
 // the engine's value of a fresh run is shown with its source and not written
 const s=JSON.parse(fixture('state-one.json')),run=s.runs[0];
 const engine=M.engineEffectiveArea({mode_postprocessing:{effective_area:{unit:'m^2',values:[[1.9e-13,3.4e-13]]}}});
 assert.deepEqual(engine,[1.9e-13,3.4e-13]);
 Object.defineProperty(run,'area',{value:{values:engine,source:'engine'},enumerable:false});
 assert.equal(M.opticalModes(run)[1].area,3.4e-13);
 assert.equal(JSON.stringify(N.createSession(s.input,s.runs,s.selected,s.comparison,s.view)),fixture('optical-v7-one.json'));
 // refused: another unit, a non-positive area
 assert.equal(M.engineEffectiveArea({mode_postprocessing:{effective_area:{unit:'um^2',values:[[.19]]}}}),null);
 assert.equal(M.engineEffectiveArea({mode_postprocessing:{effective_area:{unit:'m^2',values:[[0]]}}}),null);
 assert.equal(M.engineEffectiveArea({}),null);
});
test('V17-M3: a version 8 run with and without effective_area round-trips with its digest; without it A_eff is "—"',()=>{
 for(const withArea of [false,true]){
  const doc=complexV8();
  for(const run of doc.runs)for(const p of Object.values(run.result.physics))if(p.type==='em.modes2d'){
   const re=p.effective_index.re;
   if(withArea)p.summary.mode_postprocessing.effective_area={unit:'m^2',values:re.map(row=>row.map((_,i)=>(1.9+i)*1e-13))};
   const {digest,...record}=run;run.digest=S.recordDigest(record);
  }
  const text=JSON.stringify(doc),read=N.parseSession(text);
  const state={document:read.document,runs:read.runs,baselines:read.baselines,selected:read.selected,view:read.view};
  const written=S.writeMultiphysicsSession(state).text,again=N.parseSession(written);
  assert.deepEqual(again.runs.map(r=>r.result),read.runs.map(r=>r.result));
  assert.deepEqual(JSON.parse(written).runs.map(r=>r.digest),doc.runs.map(r=>r.digest));
  const p=Object.values(read.runs[0].result.physics).find(x=>x.type==='em.modes2d');
  const identity=M.physicsModes(p),{rows}=M.modeTableRows(identity.modes,{missing:identity.missing,areaMissing:identity.areaMissing});
  if(withArea){assert.equal(identity.areaSource,'engine');assert.deepEqual(rows.map(r=>r.area.text),rows.map((_,i)=>M.areaText((1.9+i)*1e-13)));assert.equal(rows[0].area.text,'0.1900');}
  else{assert.equal(identity.areaSource,null);assert.equal(rows[0].area.text,'—');assert.match(rows[0].area.title,/^Run again to compute: this run was saved before Studio kept the effective area/);}
 }
 // the unmodified version 8 fixture shows "—" too
 const read=N.parseSession(fixture('multiphysics-v8.json'));
 const p=Object.values(read.runs[0].result.physics).find(x=>x.type==='em.modes2d');
 const identity=M.physicsModes(p);
 assert.equal(M.modeTableRows(identity.modes,{areaMissing:identity.areaMissing}).rows[0].area.text,'—');
});
