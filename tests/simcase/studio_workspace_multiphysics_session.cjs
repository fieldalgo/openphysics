// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
// Session files of version 8 (a multiphysics model with its runs) and the optical files of
// versions 6 and 7 next to them: checks S1 and S3-S7 of the module (the browser checks are in
// tools/studio_browser/studio_multiphysics_session_browser.mjs). The optical references in
// studio_session_fixtures/ were written by the Studio before version 8 (commit 0606859).
const {before}=require('node:test');const test=require('node:test');const assert=require('node:assert/strict');
const {createHash}=require('node:crypto');const {readFileSync,readdirSync}=require('node:fs');const {join}=require('node:path');
const S='../../packages/simcase/src/simcase/studio/static/';
let M,N,P,MP;
before(async()=>{M=await import(S+'workspace-multiphysics-session.mjs');N=await import(S+'workspace-notebook.mjs');P=await import(S+'workspace-persistence.mjs');MP=await import(S+'workspace-multiphysics.mjs');});
const FIX=join(__dirname,'studio_session_fixtures');
const fixture=name=>readFileSync(join(FIX,name),'utf8');

// ---- a small multiphysics run as the server replies -------------------------------------------
const documentOf=(power='2e14 W/m^3')=>({openphysics:'0.3/multiphysics.1',name:'Heated silicon waveguide',
 geometry:{version:1,components:{xs:{dimension:'2d',length_unit:'um',depth:null,domain:{xmin:-3,xmax:3,ymin:-2,ymax:2.5},background:{material:'physmat:SiO2'},
  features:[{name:'core',type:'rect',x:-0.25,y:0,w:0.5,h:0.22,material:'physmat:Si'}]}}},
 materials:{},mesh:{element_size:'0.25 um'},
 physics:{heat1:{type:'thermal.steady2d',prescribed_temperature:{bottom:'300 K'},heat_source_density:{core:power}},modes1:{type:'em.modes2d',formulation:'scalar',vacuum_wavelength:'1550 nm',mode_count:1}},
 couplings:{heat1_to_modes1:{from:'heat1.temperature',to:'modes1.temperature',transfer:'same_mesh'}}});
const resultOf=(T=[300,301.5,302.25,-0],neff=2.4456501286415855)=>{
 const tri=[[0,1,2],[1,3,2]],mean=tri.map(t=>(T[t[0]]+T[t[1]]+T[t[2]])/3);
 return {result:'multiphysics-run-v1',name:'Heated silicon waveguide',solve_order:[['heat1'],['modes1']],
  couplings:{heat1_to_modes1:{from:'heat1.temperature',to:'modes1.temperature',quantity:'temperature',unit:'K',transfer:'same_mesh',location:'node',mesh_signature:'match',max_abs_difference:{value:0,unit:'K'},conservation_residual:null}},
  loops:[],timing:{heat1:0.1,modes1:0.2},diagnostics:[],
  mesh:{node_coordinates:[[0,0],[1e-6,0],[0,1e-6],[1e-6,1e-6]],field_units:{node_coordinates:'m'},triangles:tri,regions:[0,1],region_names:['background','core']},
  physics:{heat1:{type:'thermal.steady2d',temperature:{unit:'K',location:'node',values:T},range:{min:Math.min(...T),max:Math.max(...T),unit:'K'},summary:{}},
   modes1:{type:'em.modes2d',effective_index:{unit:'1',values:[[neff]]},vacuum_wavelength:{unit:'m',values:[1.55e-6]},summary:{},
    coupled:{temperature:{unit:'K',location:'element',values:mean},refractive_index:{location:'element',n:[3.4757,1.444],k:null},index_change:[1.8e-5,-0]}}}};
};
const runOf=(number,job,extra={})=>({job,number,label:'',pinned:false,completedAt:'2026-11-22T10:15:03.120Z',serverVersion:'0.0.2',doc:documentOf(),events:[{event:'physics_started',physics:'heat1'}],
 order:[['heat1'],['modes1']],result:resultOf(),maps:'kept',origin:'local',...extra});
const baselineOf=doc=>({job:'mp-77a01b2c3d4e',completedAt:'2026-11-22T10:15:04.300Z',document:MP.uncoupledDocument(doc,'modes1'),
 result:{type:'em.modes2d',effective_index:{unit:'1',values:[[2.443499265702046]]},vacuum_wavelength:{unit:'m',values:[1.55e-6]},summary:{}}});
const stateOf=(runs=[runOf(1,'mp-3f2a9c1d7e4b',{label:'Heater 10 mW',pinned:true})])=>({document:documentOf(),runs,baselines:{modes1:baselineOf(documentOf())},selected:runs.at(-1)?.job??null,
 view:{page:'Results',selection:'results:modes1',index_map:'change',baseline_option:true}});
// the server's validate reply for a document, as /api/multiphysics/validate gives it
const validReply=doc=>({ok:true,diagnostics:[],solve_order:Object.keys(doc.couplings||{}).length?[['heat1'],['modes1']]:Object.keys(doc.physics).map(n=>[n]),run_refusal:null});
const bits=x=>Buffer.from(new Float64Array([x]).buffer).toString('hex');
const flat=x=>Array.isArray(x)?x.flatMap(flat):[x];

test('SHA-256 equals node:crypto on the FIPS vectors and on 5 MB of mixed text',()=>{
 for(const text of ['','abc','abcdbcdecdefdefgefghfghighijhijkijkljklmklmnlmnomnopnopq','a'.repeat(55),'a'.repeat(56),'a'.repeat(64),'é ⇄ n₀ 😀'.repeat(1000),'x'.repeat(5e6)+'Δn_eff'])
  assert.equal(M.sha256Hex(text),createHash('sha256').update(text,'utf8').digest('hex'));
});
test('S1 module: -0.0, a subnormal, 1e308 and integers above 2^31 come back bit for bit; write, read, write is byte-identical',()=>{
 const special=[-0,5e-324,1e308,2**31+1,2**53-1,-1.5e-310,0.1+0.2,1e21,1e-7];
 const run=runOf(1,'mp-000000000001');run.result.timing={special};run.result.physics.modes1.summary={special};
 const state=stateOf([run]);const first=M.writeMultiphysicsSession(state);assert.equal(first.ok,true);
 assert.ok(first.text.includes('-0.0'),'negative zero written as -0.0');assert.ok(!first.text.includes('NaN'));
 const read=N.parseSession(first.text);
 assert.deepEqual(read.runs[0].result.timing.special.map(bits),special.map(bits));
 // every array of the reply, as Float64 bytes
 for(const path of [['mesh','node_coordinates'],['mesh','triangles'],['mesh','regions'],['physics','heat1','temperature','values'],['physics','modes1','coupled','temperature','values'],['physics','modes1','coupled','refractive_index','n'],['physics','modes1','coupled','index_change'],['physics','modes1','effective_index','values']]){
  const get=o=>path.reduce((x,k)=>x[k],o);assert.deepEqual(flat(get(read.runs[0].result)).map(bits),flat(get(run.result)).map(bits),path.join('.'));}
 assert.ok(Object.is(read.runs[0].result.physics.heat1.temperature.values[3],-0));
 const second=M.writeMultiphysicsSession({...state,document:read.document,runs:read.runs,baselines:read.baselines,selected:read.selected,view:read.view});
 assert.equal(second.text,first.text,'the second file is byte-identical');
 // NaN and the infinities are never written
 const bad=runOf(1,'mp-000000000001');bad.result.timing={x:NaN};assert.throws(()=>M.writeMultiphysicsSession(stateOf([bad])),/NaN or an infinite/);
});
test('the digest is SHA-256 of the sorted-key record without it; values-only runs drop the maps and keep the counts',()=>{
 const state=stateOf();const out=JSON.parse(M.writeMultiphysicsSession(state).text);const r=out.runs[0];
 assert.match(r.digest,/^sha256:[0-9a-f]{64}$/);const {digest,...rest}=r;
 assert.equal(digest,'sha256:'+createHash('sha256').update(M.digestJson(rest),'utf8').digest('hex'));
 assert.deepEqual(Object.keys(r),['job','number','label','pinned','completedAt','serverVersion','document','events','maps','result','digest']);
 assert.deepEqual(Object.keys(out),['format','version','application','document','runs','baselines','selected','view']);
 assert.equal(out.version,8);assert.equal(out.application,'multiphysics');assert.ok(out.baselines.modes1.digest);
 const reduced=M.sessionRun(state.runs[0],false);
 assert.equal(reduced.maps,'not kept');assert.deepEqual(reduced.counts,{nodes:4,triangles:2});assert.equal('mesh' in reduced.result,false);
 assert.equal('values' in reduced.result.physics.heat1.temperature,false);assert.deepEqual(reduced.result.physics.heat1.range,state.runs[0].result.physics.heat1.range);
 assert.deepEqual(reduced.result.physics.modes1.effective_index,state.runs[0].result.physics.modes1.effective_index);
 const back=N.parseSession(M.sessionJson({...out,runs:[reduced]}));assert.equal(back.runs[0].maps,'not kept');assert.deepEqual(back.runs[0].counts,{nodes:4,triangles:2});
 // a values-only run is written again as it was
 assert.deepEqual(M.sessionRun(back.runs[0]),reduced);
 // the Coupling check sentence from the counts and the heat range
 const rows=MP.couplingCheckRows(back.runs[0].result,back.runs[0].doc,back.runs[0].counts);
 assert.match(rows[0].sent,/^4 node temperatures, -?0\.0–302\.3 K$/);
});
test('S3: version 6 and 7 optical files open exactly as before; versions 1-5 keep their refusal',()=>{
 const {dump}=require('./studio_session_fixtures/dump.cjs');
 let files=0;
 for(const name of readdirSync(FIX).filter(f=>/^optical-v[67]-/.test(f))){
  const [,version,state]=/^optical-v(\d)-(\w+)\.json$/.exec(name),text=fixture(name),expected=JSON.parse(fixture(`expected-v${version}-${state}.json`));
  const parsed=N.parseSession(text),recovered=N.parseSession(text,{recovered:true});
  const texts={file:P.sessionLoadText(parsed),fileOverRuns:P.sessionLoadText(parsed,{runs:2,unsaved:true}),browser:P.sessionLoadText(recovered,{runs:1},'browser')};
  assert.deepEqual(JSON.parse(dump({parsed,recovered,texts})),expected,name);
  assert.equal('application' in parsed,false);files++;
 }
 assert.equal(files,6);
 const refusals=JSON.parse(fixture('refusals.json'));
 for(const version of [1,2,3,4,5])assert.throws(()=>N.parseSession(JSON.stringify({format:'openphysics-studio-session',version,input:{},runs:[]})),{message:refusals[version]});
 // a byte order mark still refuses an optical file, as before
 assert.throws(()=>N.parseSession('﻿'+fixture('optical-v7-one.json')),{message:'Session is not valid JSON.'});
});
test('S4: the same optical state is written byte for byte as the Studio before version 8 wrote it (version 7)',()=>{
 for(const state of ['empty','one','three']){
  const s=JSON.parse(fixture(`state-${state}.json`)),text=JSON.stringify(N.createSession(s.input,s.runs,s.selected,s.comparison,s.view));
  assert.equal(text,fixture(`optical-v7-${state}.json`),state);assert.equal(JSON.parse(text).version,7);
 }
});
test('S5 module: 16 MiB − 1 byte opens, 16 MiB + 1 byte is refused before parsing; a run alone over the limit is named',()=>{
 const text=M.writeMultiphysicsSession(stateOf()).text,limit=16*1024*1024;
 const pad=n=>text.slice(0,-1)+' '.repeat(n-Buffer.byteLength(text))+'}';
 const small=pad(limit-1);assert.equal(Buffer.byteLength(small),limit-1);assert.equal(N.parseSession(small).runs.length,1);
 const large=pad(limit+1);assert.equal(Buffer.byteLength(large),limit+1);
 const parse=JSON.parse;let calls=0;JSON.parse=(...a)=>{calls++;return parse(...a);};
 try{assert.throws(()=>N.parseSession(large),{message:'Session exceeds 16 MiB.'});}finally{JSON.parse=parse;}
 assert.equal(calls,0,'never parsed');
 // a run whose maps alone are about 17 MB
 const big=runOf(3,'mp-00000000000c',{pinned:true}),T=Array.from({length:340000},(_,i)=>300+i*1e-6);
 big.result.mesh.node_coordinates=T.map((_,i)=>[i*1.000000001e-9,i*1e-9]);big.result.mesh.triangles=[[0,1,2]];big.result.mesh.regions=[0];
 big.result.physics.heat1.temperature.values=T;big.result.physics.heat1.range={min:T[0],max:T.at(-1),unit:'K'};
 const out=M.writeMultiphysicsSession({...stateOf([runOf(1,'mp-00000000000a'),big]),selected:'mp-00000000000a'});
 assert.equal(out.ok,false);assert.equal(out.reduced,null);assert.match(out.refusal,/^Run 3 alone is 1[6-9] MB, over the 16 MiB session limit\. Unpin it or keep it in a smaller-mesh model\.$/);
 // over the limit with no pinned run: the dialog offers the selected run's maps only
 const unpinned={...big,pinned:false},second=runOf(4,'mp-00000000000d');
 const offer=M.writeMultiphysicsSession({...stateOf([unpinned,second]),selected:second.job});
 assert.equal(offer.ok,false);assert.deepEqual(offer.reduced.notKept,[3]);assert.match(M.overflowQuestion(offer.bytes),/^Session is 1\d MB; the limit is 16 MiB\. Keep the maps of the selected and pinned runs only\?/);
 const kept=M.writeMultiphysicsSession({...stateOf([unpinned,second]),selected:second.job},{keepSelected:true});
 assert.equal(kept.ok,true);assert.deepEqual(kept.notKept,[3]);const read=N.parseSession(kept.text);assert.deepEqual(read.runs.map(r=>r.maps),['not kept','kept']);
});
// one mutation per §3.4 check; the digest is recomputed (except for the digest case) so the
// named check is the one that refuses
const MUTATIONS=[
 ['an array value changed',d=>{d.runs[0].result.physics.modes1.coupled.refractive_index.n[0]=3.5;},/^Run 1 changed after it was saved \(its check value does not match\)\.$/,false],
 ['one array shortened',d=>{d.runs[0].result.physics.heat1.temperature.values.pop();},/^Run 1's stored maps are not well formed: Heat 1 node temperature has 3 values for 4 nodes\.$/],
 ['a triangle index out of range',d=>{d.runs[0].result.mesh.triangles[1][1]=4;},/^Run 1's stored maps are not well formed: triangle 1 names node 4, outside 0–3\.$/],
 ['a non-finite value',d=>{d.runs[0].result.physics.modes1.coupled.refractive_index.n[1]=7777.25;},/^Run 1's stored maps are not well formed: refractive_index\.n holds a value that is not a finite number\.$/],
 ['a coupling renamed',d=>{const r=d.runs[0].result;r.couplings.renamed=r.couplings.heat1_to_modes1;delete r.couplings.heat1_to_modes1;},/^Run 1's coupling records do not match its model's couplings\.$/],
 ['an unconverged loop',d=>{d.runs[0].document.study={type:'single',loops:[{physics:['heat1','modes1'],tolerance:{port:'heat1.temperature',value:'1e-6 K'},max_iterations:5}]};
  d.runs[0].result.loops=[{physics:['heat1','modes1'],method:'fixed_point',tolerance:{port:'heat1.temperature',value:'1e-6 K'},relaxation:1,iterations:3,converged:true,residuals:[{value:1e-3,unit:'K'},{value:2e-6,unit:'K'}]}];},
  /^Run 1's iteration step Heat 1 ⇄ Modes 1 did not converge: its last change 0\.000002 K is above the tolerance\.$/],
 ['a loop marked unconverged',d=>{d.runs[0].document.study={type:'single',loops:[{physics:['heat1','modes1'],tolerance:{port:'heat1.temperature',value:'1e-6 K'},max_iterations:5}]};
  d.runs[0].result.loops=[{physics:['heat1','modes1'],iterations:2,converged:false,residuals:[{value:1e-7,unit:'K'}]}];},/did not converge; a run that did not succeed cannot be in a session\.$/],
 ['a duplicate job',d=>{d.runs.push({...JSON.parse(JSON.stringify(d.runs[0])),number:2});},/^Two runs have the same job identifier mp-3f2a9c1d7e4b\.$/],
 ['a heat range that is not the stored minimum',d=>{d.runs[0].result.physics.heat1.range.max=303;},/^Run 1's heat range does not equal the minimum and maximum of its stored temperatures\.$/],
 ['a coupled temperature that is not the triangle mean',d=>{d.runs[0].result.physics.modes1.coupled.temperature.values[0]+=1e-9;},/^Run 1's coupled temperature is not the triangle mean of its node temperatures \(triangle 0\)\.$/],
 ['a baseline document changed',d=>{d.baselines.modes1.document.physics.modes1.vacuum_wavelength='1551 nm';},/^The without-heater result of Modes 1 belongs to no run in this file and not to its model\.$/],
 ['a baseline changed without its digest',d=>{d.baselines.modes1.result.effective_index.values[0][0]=2.5;},/^The without-heater result of Modes 1 changed after it was saved/,false],
 ['the selected run missing',d=>{d.selected='mp-ffffffffffff';},/^The selected run is not in the file\.$/],
 ['a view the view does not offer',d=>{d.view.index_map='other';},/^The saved view is not one this Studio offers\.$/],
 ['a selection outside the model',d=>{d.view.selection='physics:heat9';},/^The saved view is not one this Studio offers\.$/],
 ['seven runs',d=>{for(let i=2;i<=7;i++)d.runs.push({...JSON.parse(JSON.stringify(d.runs[0])),number:i,job:'mp-00000000000'+i});},/^Unsupported session format or run count\.$/],
 ['a job identifier of another form',d=>{d.runs[0].job='12345678';d.selected='12345678';},/^Run 1 has an invalid job identifier\.$/],
 ['a name with a control character',d=>{d.runs[0].label='a\u0007b';},/^Run 1: Run name must be at most 80 characters/],
 ['a coupling record of null',d=>{d.runs[0].result.couplings.heat1_to_modes1=null;},/^Run 1's coupling record heat1_to_modes1 does not match its model\.$/],
 ['a physics result of null',d=>{d.runs[0].result.physics.heat1=null;},/^Run 1's result does not hold the physics of its model\.$/],
 ['a selection of an inherited name',d=>{d.view.selection='physics:__proto__';},/^The saved view is not one this Studio offers\.$/],
 ['a loop tolerance that the result raised',d=>{d.runs[0].document.study={type:'single',loops:[{physics:['heat1','modes1'],tolerance:{port:'heat1.temperature',value:'1e-6 K'},max_iterations:5}]};
  d.runs[0].result.loops=[{physics:['heat1','modes1'],method:'fixed_point',tolerance:{port:'heat1.temperature',value:'1 K'},relaxation:1,iterations:3,converged:true,residuals:[{value:1e-3,unit:'K'},{value:2e-6,unit:'K'}]}];},
  /did not converge: its last change 0\.000002 K is above the tolerance\.$/],
 ['a document over 1 MiB',d=>{d.runs[0].document.description='x'.repeat(1<<20);},/^Run 1 is over 1 MiB, the size Studio reads a model file up to\.$/],
];
const redigest=d=>{for(const r of d.runs)r.digest=M.recordDigest(r);for(const b of Object.values(d.baselines))b.digest=M.recordDigest(b);return d;};
test('S6 module: each tampered file is refused by name before anything is returned',()=>{
 const text=M.writeMultiphysicsSession(stateOf()).text;N.parseSession(text);
 for(const [what,change,message,recompute=true] of MUTATIONS){const d=JSON.parse(text);change(d);if(recompute)redigest(d);
  assert.throws(()=>N.parseSession(M.sessionJson(d).replace('7777.25','1e999')),{message},what);}
});
test('S6/S7 module: the server checks refuse a run model that fails, is not run by Studio, or has another solve order; the current model only when unreadable',async()=>{
 const text=M.writeMultiphysicsSession(stateOf()).text,session=N.parseSession(text);
 assert.equal((await M.checkSessionModels(session,async doc=>validReply(doc))).runs.length,1);
 const reply=over=>async doc=>({...validReply(doc),...over(doc)});
 const failing=reply(doc=>doc.couplings?{ok:false,diagnostics:[{severity:'error',code:'E-CONTRACT',path:'couplings.heat1_to_modes1',message:'heat1 does not send x'}]}:{});
 // the current document is the first: it has couplings, but only an unreadable one refuses it
 await assert.rejects(M.checkSessionModels(N.parseSession(text),failing),{message:"Run 1's model does not pass today's check: couplings.heat1_to_modes1: heat1 does not send x"});
 await assert.rejects(M.checkSessionModels(N.parseSession(text),reply(doc=>doc.couplings?{solve_order:[['modes1'],['heat1']]}:{})),{message:'Run 1\'s solve order [["heat1"],["modes1"]] is not the order of its model ([["modes1"],["heat1"]]).'});
 await assert.rejects(M.checkSessionModels(N.parseSession(text),reply(()=>({run_refusal:'Sweeps of coupled models cannot run in this release.'}))),{message:"Run 1's model is not one Studio runs: Sweeps of coupled models cannot run in this release."});
 await assert.rejects(M.checkSessionModels(N.parseSession(text),reply(doc=>doc.physics.heat1?{}:{ok:false,diagnostics:[{severity:'error',code:'E-VALUE',path:'physics.modes1',message:'bad'}]})),{message:"The without-heater result of Modes 1's model does not pass today's check: physics.modes1: bad"});
 await assert.rejects(M.checkSessionModels(N.parseSession(text),async()=>{throw new Error('Failed to fetch');}),{message:"Studio's server must check the model before a session opens: Failed to fetch"});
 // the current model may have problems (they open into Messages), but not be unreadable
 const first={n:0},current=async doc=>first.n++===0?{ok:false,diagnostics:[{severity:'error',code:'E-REQUIRED',path:'x',message:'missing'}],solve_order:[],run_refusal:null}:validReply(doc);
 assert.equal((await M.checkSessionModels(N.parseSession(text),current)).runs.length,1);
 const version={n:0},unreadable=async doc=>version.n++===0?{ok:false,diagnostics:[{severity:'error',code:'E-FORMAT',path:'openphysics',message:'openphysics is "0.3/multiphysics.2"; this reader reads the format "0.3".'}],solve_order:[],run_refusal:null}:validReply(doc);
 await assert.rejects(M.checkSessionModels(N.parseSession(text),unreadable),{message:'The session model is not readable: openphysics: openphysics is "0.3/multiphysics.2"; this reader reads the format "0.3".'});
});
test('S7 module: newer versions, another application and another result are refused by name',()=>{
 const text=M.writeMultiphysicsSession(stateOf()).text;
 const change=f=>{const d=JSON.parse(text);f(d);return M.sessionJson(redigest(d));};
 // version 9 is now an optical session (application "optical"): a version 8 layout under it is refused, and the
 // newer-version refusal names version 10; a Studio before version 9 refused version 9 with the same template
 assert.throws(()=>N.parseSession(change(d=>{d.version=10;})),{message:'This session file is version 10, newer than this Studio reads (versions 6–9). Open it in a newer Studio.'});
 assert.equal(N.newerVersionText(9,8),'This session file is version 9, newer than this Studio reads (versions 6–8). Open it in a newer Studio.');
 assert.throws(()=>N.parseSession(change(d=>{d.version=9;})),{message:'Unknown key "document" in the session file.'});
 assert.throws(()=>N.parseSession(change(d=>{d.application='other';})),{message:'This session file holds a “other” model, which this Studio does not read.'});
 assert.throws(()=>N.parseSession(change(d=>{delete d.application;})),{message:'This session file holds a “unnamed” model, which this Studio does not read.'});
 assert.throws(()=>N.parseSession(change(d=>{d.runs[0].result.result='multiphysics-run-v2';})),{message:'Run 1 was saved as result “multiphysics-run-v2”, which this Studio does not read.'});
 // a version 7 layout under version 8 is not read as optical
 assert.throws(()=>N.parseSession(fixture('optical-v7-one.json').replace('"version":7','"version":8')),/does not read/);
 // a byte order mark is removed from a version 8 file
 assert.equal(N.parseSession('﻿'+text).runs.length,1);
});
test('the run list keeps six runs: pinned runs stay, a new run replaces the oldest unpinned one; the next number follows the highest',()=>{
 let runs=[];for(let i=1;i<=8;i++)runs=M.appendMultiphysicsRun(runs,runOf(i,'mp-'+String(i).padStart(12,'0'),{pinned:i===1}));
 assert.deepEqual(runs.map(r=>r.number),[1,4,5,6,7,8]);assert.equal(M.nextRunNumber(runs),9);
 const all=runs.map(r=>({...r,pinned:true}));assert.throws(()=>M.appendMultiphysicsRun(all,runOf(9,'mp-000000000009')),/All six runs are pinned/);
 assert.equal(M.multiphysicsRunName({number:2,label:'Heater 10 mW',pinned:true}),'Run 2 Heater 10 mW (pinned)');
 assert.equal(M.modelSlug('Heated silicon waveguide'),'heated-silicon-waveguide');assert.equal(M.modelSlug('2 µm ✓'),'m');assert.equal(M.modelSlug('…'),'multiphysics');
 assert.equal(P.sessionFileName(M.modelSlug('Heated silicon waveguide'),new Date(2026,10,22,10,15)),'heated-silicon-waveguide-session-2026-11-22-1015.json');
});
test('the open question and the save notice use the optical words',()=>{
 const session=N.parseSession(M.writeMultiphysicsSession(stateOf([runOf(1,'mp-000000000001',{label:'Heater 10 mW',pinned:true}),runOf(2,'mp-000000000002'),runOf(3,'mp-000000000003')])).text);
 const t=M.multiphysicsLoadText(session,{runs:1});
 assert.equal(t.title,'Open saved session?');assert.equal(t.runs,'Run 1 Heater 10 mW (pinned); Run 2; Run 3');
 assert.equal(t.description,'Brings back 3 runs with their names and pins. Replaces the current model and 1 run in this tab; input undo starts at the opened session.');
 assert.equal(M.savedNotice('heated-silicon-waveguide-session-2026-11-22-1015.json',{runs:3,baseline:true}),"Session file heated-silicon-waveguide-session-2026-11-22-1015.json sent to your browser's Downloads: the model, 3 runs and the without-heater result.");
 // File › Save through the browser's save dialog: the words say the file was written, and no more
 assert.equal(M.savedNotice('heater.json',{runs:3,baseline:true,via:'picker'}),'Saved to heater.json: the model, 3 runs and the without-heater result.');
 // round 10: the optical runs of the tab are not in a multiphysics session file, and the message says where they are kept
 const base=M.savedNotice('h.json',{runs:1});assert.equal(M.savedNotice('h.json',{runs:1,opticalRuns:0}),base);
 assert.equal(M.savedNotice('h.json',{runs:1,opticalRuns:2}),base+' The 2 Optical waveguide runs of this tab are not in this file; Library › Optical waveguide, then File › Save, keeps them in their own file.');
 assert.equal(M.savedNotice('h.json',{runs:1,opticalRuns:1}),base+' The Optical waveguide run of this tab is not in this file; Library › Optical waveguide, then File › Save, keeps it in its own file.');
 assert.ok(session.runs.every(r=>r.origin==='imported'));
});

// The committed version 8 fixture read by test_studio_multiphysics_session.py, which recomputes
// every digest with hashlib and its own writer: it is what this writer writes for a fixed state.
// OPENPHYSICS_WRITE_FIXTURES=1 writes it again.
test('the version 8 fixture is what the writer writes, with the numbers JSON cannot spell plainly',()=>{
 const run=runOf(1,'mp-3f2a9c1d7e4b',{label:'Heater 10 mW · Δn ✓',pinned:true});
 run.result.timing={heat1:-0,modes1:5e-324,total:1e21,small:1e-7,big:2**53-1,tiny:-1.5e-310,max:1.7976931348623157e308};
 const second=runOf(2,'mp-77a01b2c3d4f',{completedAt:'2026-11-22T10:16:00.000Z'});second.result.physics.heat1.temperature.values=[300,300.5,301,302];
 second.result.physics.heat1.range={min:300,max:302,unit:'K'};const T=second.result.physics.heat1.temperature.values;
 second.result.physics.modes1.coupled.temperature.values=[[0,1,2],[1,3,2]].map(t=>(T[t[0]]+T[t[1]]+T[t[2]])/3);
 const state={...stateOf([run]),runs:[run,M.sessionRun(second,false)].map((r,i)=>i?{...second,maps:'not kept',counts:r.counts,result:r.result}:r),selected:run.job};
 const text=M.writeMultiphysicsSession(state).text,path=join(FIX,'multiphysics-v8.json');
 if(process.env.OPENPHYSICS_WRITE_FIXTURES==='1')require('node:fs').writeFileSync(path,text);
 assert.equal(text,fixture('multiphysics-v8.json'));
 const read=N.parseSession(text);assert.deepEqual(read.runs.map(r=>r.maps),['kept','not kept']);
});

test('the file assembled from cached run texts is the session object written whole',()=>{
 const state=stateOf([runOf(1,'mp-000000000001',{pinned:true}),runOf(2,'mp-000000000002')]);
 const first=M.writeMultiphysicsSession(state).text;assert.equal(first,M.sessionJson(M.createMultiphysicsSession(state)));
 state.runs[1].label='renamed';const second=M.writeMultiphysicsSession(state).text;
 assert.equal(second,M.sessionJson(M.createMultiphysicsSession(state)));assert.notEqual(second,first);assert.equal(N.parseSession(second).runs[1].label,'renamed');
 // a baseline the file does not hold is not counted in the notice
 const lone={...state,runs:[],baselines:{modes1:{...baselineOf(documentOf()),document:{...MP.uncoupledDocument(documentOf('9e14 W/m^3'),'modes1'),name:'other'}}}};
 assert.equal(M.writeMultiphysicsSession(lone).baselines,0);assert.equal(M.writeMultiphysicsSession(state).baselines,1);
});
