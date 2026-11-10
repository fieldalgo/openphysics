// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0

const {before}=require('node:test');
let snapshot;
let OPTICAL_SETTINGS,opticalSettings,appendRun,mergeRuns,createSession,parseSession;
before(async()=>{
({snapshot}=await import('../../packages/simcase/src/simcase/studio/static/workspace-project.mjs'));
({OPTICAL_SETTINGS,opticalSettings,appendRun,mergeRuns,createSession,parseSession}=await import('../../packages/simcase/src/simcase/studio/static/workspace-notebook.mjs'));
});
const test=require('node:test');const assert=require('node:assert/strict');


const input=()=>snapshot({width:500,voltage:1,electric:false,heat:false,structure:false,optics:true},{materials:{Core:'Silicon',Oxide:'Silica',Heater:''},temperature:293.15,cooling:'',fixed:'',terminal:''});
// session format 6: run records under the section 5.3.4 names, node coordinates in metres
const run=(job='12345678')=>({job,completedAt:'2026-10-26T00:00:00.000Z',settings:opticalSettings(),input:input(),effective_index:[2.4,1.7],field:{node_coordinates:[[0,0],[1e-6,0],[0,1e-6]],triangles:[[0,1,2]],real:[[[1,0,0]],[[0,1,0]]],imag:[[[0,0,0]],[[0,0,0]]]},origin:'local'});
const stored=field=>({node_coordinates:field.node_coordinates,triangles:field.triangles,real:field.real,imag:field.imag});
test('session round trip preserves fields, comparison and immutable inputs; imports never become local calculations',()=>{const a=run(),b=run('abcdef12');b.input.model.shapes=[{...b.input.model.shapes[0],x:-350,w:700}];const d=createSession(input(),[a,b],b.job,[a.job,b.job]);const restored=parseSession(JSON.stringify(d));assert.equal(restored.runs[1].input.model.shapes[0].w,700);assert.equal(restored.runs[0].origin,'imported');assert.deepEqual(restored.comparison,[a.job,b.job]);assert.deepEqual(stored(restored.runs[0].field),a.field);assert.deepEqual(restored.runs[0].field.nodes,[[0,0],[1,0],[0,1]]);restored.runs[0].input.model.shapes[0].w=900;assert.equal(a.input.model.shapes[0].w,500);
 assert.equal(d.version,6);assert.deepEqual(d.runs[0].field,a.field);assert.equal('nodes' in d.runs[0].field,false);assert.deepEqual(d.runs[0].effective_index,[2.4,1.7]);});
test('bounded retention and replacing repeated job keeps unique latest six',()=>{let runs=[];for(let i=0;i<8;i++)runs=appendRun(runs,run(i.toString(16).padStart(8,'0')));assert.equal(runs.length,6);assert.equal(runs[0].job,'00000002');runs=appendRun(runs,run('00000004'));assert.equal(runs.length,6);assert.equal(runs.at(-1).job,'00000004');});
test('corrupted results, references, metadata and versions are rejected atomically',()=>{for(const change of [d=>d.version=7,d=>d.version=5,d=>d.runs[0].field.triangles[0][0]=99,d=>d.runs[0].effective_index[0]=null,d=>{d.runs[0].neff=d.runs[0].effective_index;delete d.runs[0].effective_index;},d=>d.runs[0].settings.height_nm=400,d=>d.runs[0].settings.vacuum_wavelength=1550,d=>d.runs[0].field.node_coordinates[0][0]='0 m',d=>d.selected='deadbeef',d=>d.runs[0].input.model.heat=true,d=>d.comparison=['bad',null]]){const d=JSON.parse(JSON.stringify(createSession(input(),[run()],'12345678',['12345678',null])));change(d);assert.throws(()=>parseSession(JSON.stringify(d)));}});
test('empty and oversized session handling',()=>{const d=createSession(input(),[],null,[null,null]);assert.equal(parseSession(JSON.stringify(d)).runs.length,0);assert.throws(()=>parseSession('x'.repeat(16*1024*1024+1)));});

test('saved field view persists and settings key order is immaterial',()=>{const r=run();r.settings=Object.fromEntries(Object.entries(opticalSettings()).reverse());const view={mode:1,component:'Ey',window:'Full window'};const d=createSession(input(),[r],r.job,[r.job,r.job],view);assert.deepEqual(parseSession(JSON.stringify(d)).view,view);d.view.mode=3;assert.throws(()=>parseSession(JSON.stringify(d)));});

test('package version survives sessions while old files remain version-unknown',()=>{const r=run();assert.equal(parseSession(JSON.stringify(createSession(input(),[r],r.job,[r.job,r.job]))).runs[0].serverVersion,null);r.serverVersion='0.1.0';const session=createSession(input(),[r],r.job,[r.job,r.job]);assert.equal(parseSession(JSON.stringify(session)).runs[0].serverVersion,'0.1.0');session.runs[0].serverVersion='<script>';assert.throws(()=>parseSession(JSON.stringify(session)));});


test('optional run names survive sessions; unsafe names are rejected and CSV quotes text safely',async()=>{
 const {validateRunLabel,runTableCsv}=await import('../../packages/simcase/src/simcase/studio/static/workspace-notebook.mjs');
 const r=run();r.label='Baseline, "wide"';const restored=parseSession(JSON.stringify(createSession(input(),[r],r.job,[r.job,r.job])));assert.equal(restored.runs[0].label,r.label);
 assert.ok(runTableCsv(restored.runs).includes('"Baseline, ""wide"""'));
 r.label='=1+1';assert.ok(runTableCsv([r]).includes('"\'=1+1"'));
 for(const value of ['x'.repeat(81),'bad\nname',null,123])assert.throws(()=>validateRunLabel(value));
 assert.equal(validateRunLabel('  reference  '),'reference');assert.equal(validateRunLabel(),'');
});


test('pinned references survive retention and a fully pinned notebook rejects a new result atomically',()=>{
 const original=Array.from({length:6},(_,i)=>run(i.toString(16).padStart(8,'0')));original[0].pinned=true;
 const next=appendRun(original,run('abcdef12'));assert.equal(next.length,6);assert.ok(next.some(r=>r.job==='00000000'));assert.ok(!next.some(r=>r.job==='00000001'));assert.equal(original.length,6);
 const pinned=original.map(r=>({...r,pinned:true}));assert.throws(()=>appendRun(pinned,run('abcdef12')),/pinned/);assert.equal(pinned.length,6);assert.equal(pinned[0].job,'00000000');
});
test('resuming an existing run preserves its name and pin, and session pin metadata is validated',()=>{
 const first={...run(),label:'Reference',pinned:true};const again=appendRun([first],run());assert.equal(again.length,1);assert.equal(again[0].label,'Reference');assert.equal(again[0].pinned,true);
 const doc=createSession(input(),[first],first.job,[first.job,first.job]);assert.equal(parseSession(JSON.stringify(doc)).runs[0].pinned,true);doc.runs[0].pinned='yes';assert.throws(()=>parseSession(JSON.stringify(doc)),/pin/);
 const old=createSession(input(),[run()],'12345678',['12345678',null]);delete old.runs[0].pinned;assert.equal(parseSession(JSON.stringify(old)).runs[0].pinned,false);
});


test('run import protects pinned and incoming runs while reporting evicted prior unpinned runs',()=>{
 const existing=Array.from({length:6},(_,i)=>run(i.toString(16).padStart(8,'0')));existing[0].pinned=true;
 const merged=mergeRuns(existing,[run('abcdef12'),run('abcdef13')]);assert.equal(merged.runs.length,6);assert.deepEqual(merged.evicted,['00000001','00000002']);assert.deepEqual(merged.added,['abcdef12','abcdef13']);assert.equal(merged.runs.at(-1).origin,'imported');assert.equal(existing.length,6);assert.equal(existing[1].job,'00000001');
});
test('matching imports retain local metadata and conflicting payloads reject atomically',()=>{
 const saved={...run(),label:'Reference',pinned:true};const existing=createSession(input(),[saved],saved.job,[saved.job,saved.job]).runs;
 const merged=mergeRuns(existing,[run()]);assert.deepEqual(merged.reused,[saved.job]);assert.equal(merged.runs[0],existing[0]);assert.equal(merged.runs[0].label,'Reference');assert.equal(merged.runs[0].origin,'local');
 const conflict=run();conflict.effective_index[0]=2.5;assert.throws(()=>mergeRuns(existing,[run('abcdef12'),conflict]),/Conflicting/);assert.equal(existing.length,1);assert.equal(existing[0].effective_index[0],2.4);
});
test('imports cannot silently drop an incoming run or a pinned reference when slots are exhausted',()=>{
 const existing=[{...run('deadbeef'),pinned:true}];const incoming=Array.from({length:6},(_,i)=>run(i.toString(16).padStart(8,'0')));
 assert.throws(()=>mergeRuns(existing,incoming),/exceed six/);assert.equal(existing[0].job,'deadbeef');assert.throws(()=>mergeRuns(existing,[]),/no completed/);assert.throws(()=>mergeRuns([], [run(),run()]),/Duplicate/);
});


test('probe and profile view settings round trip without mutating their input objects',()=>{
 const view={mode:1,component:'Ey',window:'Full window',probe:{x:.2,y:.4,active:true},profile:{axis:'y',coordinate:-.2,open:true}};
 const doc=createSession(input(),[run()],'12345678',['12345678',null],view);assert.deepEqual(parseSession(JSON.stringify(doc)).view,view);doc.view.probe.x='1 um';assert.equal(view.probe.x,.2);
 // session format 6 writes the coordinates as quantity strings
 assert.deepEqual(doc.view.profile,{axis:'y',coordinate:'-0.2 um',open:true});assert.equal(doc.view.probe.y,'0.4 um');
});
test('saved probe and profile coordinates carry their unit, are checked against the window in SI, and malformed view state rejects the whole session',()=>{
 const base=createSession(input(),[run()],'12345678',['12345678',null]);
 for(const field of [{probe:{x:'2 um',y:'0 um',active:true}},{probe:{x:'0 um',y:'0 um',active:'yes'}},{probe:{x:0,y:'0 um',active:true}},{probe:{x:'0.1',y:'0 um',active:true}},{probe:{x:'0.1 km',y:'0 um',active:true}},{profile:{axis:'x',coordinate:'1.3 um',open:true}},{profile:{axis:'x',coordinate:0.1,open:true}},{profile:{axis:'z',coordinate:'0 um',open:false}},{profile:null}]){const doc={...base,view:{...base.view,...field}};assert.throws(()=>parseSession(JSON.stringify(doc)),/saved/);}
 const edge={...base,view:{...base.view,probe:{x:'1.5 um',y:'-1.2 um',active:true},profile:{axis:'y',coordinate:'1.5e-6 m',open:false}}};
 const read=parseSession(JSON.stringify(edge)).view;assert.equal(read.profile.coordinate,1.5);assert.deepEqual([read.probe.x,read.probe.y],[1.5,-1.2]);
 const other={...base,view:{...base.view,probe:{x:'150 nm',y:'0 um',active:false}}};assert.equal(parseSession(JSON.stringify(other)).view.probe.x,.15);
});
