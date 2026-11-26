// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
// Compact field encoding (optical session version 14), the format. Pre-registered:
// F1 (module path: every earlier optical fixture, the multiphysics session and the project file are
// written again byte for byte, and none is written as version 14), F3 (a version 14 round trip, 20
// compact runs, every refusal of a compact field by its sentence, a 21-run file, and version 13's
// refusals of unknown and missing run keys), F4 (main 499a0d3, the last Studio before version 14,
// refuses the file by name alone, in a project and in a recovery record, and does not adopt that
// record: studio_session_fixtures/refusals-v14-499a0d3.json, written by compact_sessions.mjs from that
// commit's static folder) and F10 (a compact field's bytes follow from its counts, and the cached sum
// is the written length). F5 (the same strings as NumPy) is in test_studio_field_encoding.py.
const test=require('node:test');const assert=require('node:assert/strict');
const fs=require('node:fs');const path=require('node:path');
const STATIC='../../packages/simcase/src/simcase/studio/static/';
const FIX=path.join(__dirname,'studio_session_fixtures');
const fixture=name=>fs.readFileSync(path.join(FIX,name),'utf8');
let N,P,S,PF,R,E,K,G,C,Q,V;
test.before(async()=>{
 N=await import(STATIC+'workspace-notebook.mjs');P=await import(STATIC+'workspace-project.mjs');S=await import(STATIC+'workspace-multiphysics-session.mjs');
 PF=await import(STATIC+'workspace-project-file.mjs');R=await import(STATIC+'workspace-notebook-recovery.mjs');E=await import(STATIC+'workspace-field-encoding.mjs');
 K=await import('./studio_session_fixtures/compact_sessions.mjs');G=await import('./studio_session_fixtures/retained_sessions.mjs');
 C=await import('./studio_session_fixtures/closed_sessions.mjs');Q=await import('./studio_session_fixtures/numbered_sessions.mjs');
 V=await import('./studio_session_fixtures/values_only_sessions.mjs');
});
const VIEW={mode:0,component:'magnitude',window:'Core region'};
const utf8=t=>Buffer.byteLength(t,'utf8');
const rewrite=text=>{const s=N.parseSession(text);return N.sessionText(s.input,s.runs,s.selected,s.comparison,s.view);};
// a session text edited, with each run's digest computed again unless keepDigest
const edit=(text,f,{keepDigest=false}={})=>{const d=JSON.parse(text);f(d);if(!keepDigest)for(const r of d.runs){delete r.digest;r.digest=S.recordDigest(r);}return S.sessionJson(d);};
const V14='optical-v14-compact.json';
const message='This session file is version 14, newer than this Studio reads (versions 6–13). Open it in a newer Studio.';
const refused=(t,m)=>assert.throws(()=>N.parseSession(t),{message:m});
// little-endian bytes of float32 or float64 values, or uint32 indices, in standard base64
const b64=(kind,values)=>{const size={f32:4,f64:8,u32:4}[kind],v=new DataView(new ArrayBuffer(size*values.length));values.forEach((x,i)=>kind==='f32'?v.setFloat32(4*i,x,true):kind==='f64'?v.setFloat64(8*i,x,true):v.setUint32(4*i,x,true));return Buffer.from(v.buffer).toString('base64');};

test('F1 (module path): every earlier optical fixture, the multiphysics session and the project file are written again byte for byte; none as version 14',()=>{
 const versions=[];
 const same=(text,name,expected=text)=>{const once=rewrite(text);assert.equal(once,expected,name);const v=JSON.parse(once).version;versions.push(v);assert.notEqual(v,14,name);assert.ok(!/"encoding"/.test(once),name);};
 for(const state of ['empty','one','three']){
  const seven=fixture(`optical-v7-${state}.json`),once=rewrite(seven);
  same(once,`optical-v7-${state}.json written once`);same(fixture(`optical-v6-${state}.json`),`optical-v6-${state}.json`,once);
 }
 const golden=JSON.parse(fixture('sessions-rewritten-13f07f4.json'));
 for(const [name,text] of Object.entries(golden)){if(name==='synthetic version 9'){same(rewrite(text),name+' written once');continue;}same(text,name);same(fixture(name),name+' from its file',text);}
 assert.equal(C.synthetic(N,P),golden['synthetic version 9']);
 const v9=N.parseSession(C.synthetic(N,P)),target=N.validateRun({...v9.runs[0],job:'0000000c',settings:N.closedTargetSettings(v9.runs[0].settings,2.46)});
 const eleven=N.sessionText(v9.input,[...v9.runs,target],v9.selected,v9.comparison,v9.view);assert.equal(JSON.parse(eleven).version,11);same(eleven,'version 11');
 const twelve=fixture('optical-v12-numbers.json');assert.equal(Q.numberedSession(N,P,FIX),twelve);same(twelve,'optical-v12-numbers.json');
 const thirteen=fixture('optical-v13-nine-runs.json');assert.equal(G.retainedSession(N,P,FIX),thirteen);same(thirteen,'optical-v13-nine-runs.json');
 const values=fixture('optical-values-only-14.json');assert.equal(V.valuesOnlySession(N,P),values);same(values,'optical-values-only-14.json');
 assert.deepEqual([...new Set(versions)].sort((a,b)=>a-b),[7,9,10,11,12,13]);
 const mp=N.parseSession(fixture('multiphysics-v8.json'));
 assert.equal(S.writeMultiphysicsSession({document:mp.document,runs:mp.runs,baselines:mp.baselines,selected:mp.selected,view:mp.view}).text,fixture('multiphysics-v8.json'));
 const project=fixture('project-v1.json'),read=PF.readProject(project),doc=JSON.parse(project);
 const again=PF.writeProject({name:doc.name,savedAt:doc.savedAt,studio:doc.studio,active:doc.active,entries:doc.models.map((m,i)=>PF.projectEntry({id:m.id,kind:m.kind,title:m.title,card:m.card,text:read.models[i].text}))});
 assert.equal(again.text,project);
});

test('encoding: little-endian float32, float64 and uint32 in padded standard base64; rounding to nearest (ties to even), -0 kept',()=>{
 const field={node_coordinates:[[1,-2.5e-7],[0.1,0],[3e-6,-0]],triangles:[[0,1,2]],real:[[[1,0.1,-0]]],imag:[[[1+2**-24,1+3*2**-24,-1e-9]]]};
 const r=E.encodeField(field);
 assert.deepEqual(Object.keys(r),['encoding','counts','node_coordinates','triangles','real','imag']);
 assert.deepEqual(r.counts,{modes:1,nodes:3,triangles:1});
 assert.equal(r.encoding,'f32-base64-v1');
 // 1 → 00 00 80 3f; 0.1 → cd cc cc 3d; -0 → 00 00 00 80; 1 + 2^-24 is the midpoint 1 | 1 + 2^-23 (to even: 1)
 assert.equal(r.real,Buffer.from([0,0,0x80,0x3f,0xcd,0xcc,0xcc,0x3d,0,0,0,0x80]).toString('base64'));
 assert.equal(r.imag,b64('f32',[1,1+2**-22,Math.fround(-1e-9)]));
 assert.equal(r.node_coordinates,b64('f64',[1,-2.5e-7,0.1,0,3e-6,-0]));
 assert.equal(r.triangles,b64('u32',[0,1,2]));
 const back=E.decodeField(r,1);
 assert.deepEqual(back.node_coordinates,field.node_coordinates);assert.ok(Object.is(back.node_coordinates[2][1],-0));
 assert.deepEqual(back.triangles,[[0,1,2]]);
 assert.deepEqual(back.real,[[[1,Math.fround(0.1),-0]]]);assert.ok(Object.is(back.real[0][0][2],-0));
 assert.deepEqual(back.imag,[[[1,1+2**-22,Math.fround(-1e-9)]]]);
 // the size follows from the counts: 32·k·T + 4⌈16N/3⌉ + 4⌈12T/3⌉
 for(const counts of [{modes:1,nodes:3,triangles:1},{modes:8,nodes:250000,triangles:500000},{modes:3,nodes:6301,triangles:12253},{modes:2,nodes:6302,triangles:12253}]){
  assert.equal(E.compactFieldChars(counts),32*counts.modes*counts.triangles+4*Math.ceil(16*counts.nodes/3)+4*Math.ceil(12*counts.triangles/3));
 }
 assert.equal(E.compactFieldChars(r.counts),r.node_coordinates.length+r.triangles.length+r.real.length+r.imag.length);
 // a float32 that is not finite is refused (no field is written beyond single precision)
 assert.throws(()=>E.encodeField({...field,real:[[[1e39,0,0]]]}),{message:'A field sample is beyond single precision.'});
});

test('base64 over chunk boundaries and the reader\'s largest field (500,000 triangles)',()=>{
 for(const n of [0,1,2,3,0x7fff,0x8000,0x8001,3*0x8000+2]){
  const bytes=Uint8Array.from({length:n},(_,i)=>(i*131+7)&255),text=E.bytesToBase64(bytes);
  assert.equal(text,Buffer.from(bytes).toString('base64'),String(n));assert.deepEqual(E.base64ToBytes(text),bytes,String(n));
 }
 // not canonical: another alphabet, white space, missing padding, unused bits set
 for(const t of ['AAB-','AAB_','AA B','AAA','AAF=','AB==','A===','AAAA\n'])assert.equal(E.base64ToBytes(t),null,t);
 const T=500000,nodes=250000,field={node_coordinates:Array.from({length:nodes},(_,i)=>[i*1e-9,(i%7)*1e-9]),triangles:Array.from({length:T},(_,i)=>[i%nodes,(i+1)%nodes,(i+2)%nodes]),
  real:[Array.from({length:T},(_,i)=>[Math.sin(i),Math.cos(i),i*1e-7])],imag:[Array.from({length:T},(_,i)=>[0,-Math.sin(i),1/(i+1)])]};
 const r=E.encodeField(field);
 assert.equal(r.real.length+r.imag.length+r.node_coordinates.length+r.triangles.length,E.compactFieldChars({modes:1,nodes,triangles:T}));
 const back=E.decodeField(r,1);
 assert.deepEqual(back.triangles[T-1],field.triangles[T-1]);assert.deepEqual(back.node_coordinates[nodes-1],field.node_coordinates[nodes-1]);
 for(const i of [0,1,T>>1,T-1])assert.deepEqual(back.real[0][i],field.real[0][i].map(Math.fround));
});

test('F3: a version 14 session of two compact runs and one text run is read and written again byte for byte',()=>{
 const text=fixture(V14);
 // the fixture is what this Studio writes from its runs
 assert.equal(K.compactSession(N,P,FIX),text);
 const d=JSON.parse(text);
 assert.equal(d.version,14);assert.deepEqual(d.runs.map(r=>r.number),[3,5,8]);
 assert.deepEqual(d.runs.map(r=>r.field.encoding??'text'),['f32-base64-v1','f32-base64-v1','text']);
 for(const r of d.runs)assert.ok(r.te_polarization_fraction&&r.effective_area,`Run ${r.number} stores its TE fractions and areas`);
 assert.equal(rewrite(text),text);assert.equal(rewrite(rewrite(text)),text);
 const s=N.parseSession(text);
 assert.deepEqual(s.runs.map(r=>E.isCompactField(r.field)),[true,true,false]);
 // the decoded samples are the float32 roundings of the field it was made from; coordinates and triangles are exact
 const source=JSON.parse(fixture('optical-v10-open-full-083e151.json')).runs.find(r=>r.job==='a0000004').field;
 const open=s.runs[0].field;
 assert.deepEqual(open.node_coordinates,source.node_coordinates);assert.deepEqual(open.triangles,source.triangles);
 for(const part of ['real','imag'])open[part].forEach((m,i)=>m.forEach((v,t)=>v.forEach((x,c)=>{const y=source[part][i][t][c];assert.ok(Object.is(x,Math.fround(y)),`${part} ${i} ${t} ${c}`);assert.ok(Math.abs(x-y)<=2**-24*Math.abs(y));})));
 // the stored values are those the run showed from its float64 field
 assert.deepEqual(d.runs[0].te_polarization_fraction,JSON.parse(fixture('optical-v10-open-full-083e151.json')).runs.find(r=>r.job==='a0000004').te_polarization_fraction);
 // a project and a browser recovery record hold the same text
 const project=PF.writeProject({name:'compact',savedAt:'2026-11-25T10:00:00.000Z',studio:'0.0.0',active:'m1',entries:[PF.projectEntry({id:'m1',kind:'workspace',title:'Optical waveguide',card:'optical',text})]}).text;
 assert.equal(PF.readProject(project).models[0].text,text);
 const recovered=R.readNotebookRecovery({version:1,savedAt:'2026-11-25T10:00:00.000Z',session:text}).session;
 assert.deepEqual(recovered.runs.map(r=>E.isCompactField(r.field)),[true,true,false]);
 assert.deepEqual(recovered.runs.map(r=>E.compactRecord(r.field)),s.runs.map(r=>E.compactRecord(r.field)));
 assert.ok(PF.KIND_VERSIONS.workspace.includes(14));
});

test('F3: 20 runs with compact fields round-trip; 21 are refused',()=>{
 const s=N.parseSession(fixture(V14));
 const runs=Array.from({length:20},(_,i)=>{const r=s.runs[i%2];return Object.assign(N.validateRun({...r,job:(0x10+i).toString(16).padStart(8,'0'),completedAt:`2026-11-25T${String(i).padStart(2,'0')}:00:00.000Z`}),{number:i+1});});
 assert.ok(runs.every(r=>E.isCompactField(r.field)));
 const text=N.sessionText(s.input,runs,runs[19].job,[null,null],VIEW);
 assert.equal(JSON.parse(text).version,14);assert.equal(rewrite(text),text);
 refused(edit(text,d=>{d.runs.push({...d.runs[0],job:'000000ff',number:21});}),'Unsupported session format or run count.');
});

test('F3: each refusal of a compact field, by its sentence and the run\'s number',()=>{
 const text=fixture(V14),run3=d=>d.runs[0].field,run5=d=>d.runs[1].field;
 // an unknown encoding; other keys, or these keys in another order
 refused(edit(text,d=>{run5(d).encoding='f16-base64-v1';}),'Run 5\'s field is encoded as "f16-base64-v1", which this Studio does not read.');
 refused(edit(text,d=>{run5(d).scale=1;}),'Run 5\'s compact field must hold encoding, counts, node_coordinates, triangles, real, imag in this order, and nothing else.');
 refused(edit(text,d=>{const f=run5(d),{real,imag}=f;delete f.real;delete f.imag;f.imag=imag;f.real=real;}),'Run 5\'s compact field must hold encoding, counts, node_coordinates, triangles, real, imag in this order, and nothing else.');
 refused(edit(text,d=>{delete run5(d).imag;}),'Run 5\'s compact field must hold encoding, counts, node_coordinates, triangles, real, imag in this order, and nothing else.');
 // counts that are not whole numbers within readOpticalField's limits, or another number of modes
 const counts='Run 5\'s compact field counts must be whole numbers: modes 1 to 8, nodes 3 to 250000, triangles 1 to 500000.';
 for(const [key,value] of [['modes',0],['modes',9],['modes',2.5],['nodes',2],['nodes',250001],['nodes','5'],['triangles',0],['triangles',500001],['triangles',null]])
  refused(edit(text,d=>{run5(d).counts[key]=value;}),counts);
 refused(edit(text,d=>{run5(d).counts={nodes:5,modes:2,triangles:3};}),counts);
 refused(edit(text,d=>{run5(d).counts.extra=1;}),counts);
 refused(edit(text,d=>{run5(d).counts.modes=1;}),'Run 5\'s compact field holds 1 modes; the run has 2.');
 // a text that is not canonical base64, or whose decoded length is not that of the counts
 refused(edit(text,d=>{const f=run5(d);f.real=f.real.replace(/A/,'-');}),'Run 5\'s compact field real is not canonical base64.');
 refused(edit(text,d=>{const f=run5(d);f.node_coordinates=f.node_coordinates.slice(0,-2)+'V=';}),'Run 5\'s compact field node_coordinates is not canonical base64.');
 refused(edit(text,d=>{const f=run5(d);f.imag=f.imag.slice(0,40)+'\n'+f.imag.slice(40);}),'Run 5\'s compact field imag is not canonical base64.');
 refused(edit(text,d=>{run5(d).counts.nodes=4;}),'Run 5\'s compact field node_coordinates holds 80 bytes; its counts give 64.');
 refused(edit(text,d=>{run5(d).counts.triangles=2;}),'Run 5\'s compact field triangles holds 36 bytes; its counts give 24.');
 refused(edit(text,d=>{const f=run5(d);f.real=b64('f32',Array(15).fill(0.5));}),'Run 5\'s compact field real holds 60 bytes; its counts give 72.');
 // a sample or a coordinate that is not finite
 refused(edit(text,d=>{const f=run5(d);f.imag=b64('f32',[...Array(17).fill(0),NaN]);}),'Run 5\'s compact field imag holds a value that is not a finite number.');
 refused(edit(text,d=>{const f=run5(d);f.real=b64('f32',[Infinity,...Array(17).fill(0)]);}),'Run 5\'s compact field real holds a value that is not a finite number.');
 refused(edit(text,d=>{const f=run5(d);f.node_coordinates=b64('f64',[0,0,1e-6,0,0,1e-6,1e-6,1e-6,0,-Infinity]);}),'Run 5\'s compact field node_coordinates holds a value that is not a finite number.');
 // a triangle index at or beyond the node count, or repeated within a triangle
 refused(edit(text,d=>{run5(d).triangles=b64('u32',[0,1,2,1,3,2,2,3,5]);}),'Run 5\'s compact field triangle 2 names node 5, outside 0–4.');
 refused(edit(text,d=>{run5(d).triangles=b64('u32',[0,1,2,1,3,3,2,3,4]);}),'Run 5\'s compact field triangle 1 repeats a node.');
 // a compact run stores its TE fractions and effective areas
 refused(edit(text,d=>{delete d.runs[1].te_polarization_fraction;}),'Run 5 has a compact field and no saved TE fractions and effective areas.');
 refused(edit(text,d=>{delete d.runs[0].effective_area;}),'Run 3 has a compact field and no saved TE fractions and effective areas.');
 // a compact field is read from a version 14 file only
 refused(edit(text,d=>{d.version=13;}),'Run 3: a compact field is read from a version 14 session file only.');
 // version 13's refusals of unknown and missing run keys hold for version 14
 refused(edit(text,d=>{d.runs[0].duration=12;}),'Run 1: unknown key "duration".');
 refused(edit(text,d=>{delete d.runs[2].settings;}),'Run 3: missing settings.');
 refused(edit(text,d=>{delete d.runs[1].number;}),'Run 2: missing number.');
 refused(edit(text,d=>{run5(d).real=run5(d).imag;},{keepDigest:true}),'Run 2 changed after it was saved (its check value does not match).');
 // a version newer than 14 is refused by name
 refused(edit(text,d=>{d.version=18;}),'This session file is version 18, newer than this Studio reads (versions 6–17). Open it in a newer Studio.');
 // a version 14 file with no compact field (edited by hand) is read; this Studio writes it as version 13 or earlier
 const plain=N.parseSession(fixture('optical-v13-nine-runs.json'));
 const hand=edit(fixture('optical-v13-nine-runs.json'),d=>{d.version=14;});
 const read=N.parseSession(hand);assert.equal(read.runs.length,9);
 assert.equal(N.sessionText(read.input,read.runs,read.selected,read.comparison,read.view),N.sessionText(plain.input,plain.runs,plain.selected,plain.comparison,plain.view));
});

test('F3: version 14 is written exactly when a run is kept with a compact field',()=>{
 const s=N.parseSession(fixture(V14));
 assert.equal(N.sessionVersion(s.runs,VIEW),14);
 // without the compact fields' runs, or with their fields left out, the file is version 13 or earlier
 assert.notEqual(N.sessionVersion([s.runs[2]],VIEW),14);
 const keep=new Set([s.runs[2].job]);
 const reduced=N.sessionText(s.input,s.runs,s.selected,s.comparison,s.view,{keep});
 assert.equal(JSON.parse(reduced).version,12);assert.ok(!/"encoding"/.test(reduced));
 // the runs written without fields keep the TE fractions and areas they stored
 const back=N.parseSession(reduced);assert.deepEqual(back.runs[0].te_polarization_fraction,s.runs[0].te_polarization_fraction);
 // a run made compact keeps every stored value of its record
 const t=N.parseSession(fixture('optical-v13-nine-runs.json')),before=N.sessionText(t.input,t.runs,t.selected,t.comparison,t.view,{keep:new Set()});
 t.runs.forEach(N.compactRunField);
 assert.equal(N.sessionText(t.input,t.runs,t.selected,t.comparison,t.view,{keep:new Set()}),before);
 assert.equal(JSON.parse(N.sessionText(t.input,t.runs,t.selected,t.comparison,t.view)).version,14);
 // compactRunField is idempotent: a compact field keeps its record
 const record=E.compactRecord(t.runs[0].field);N.compactRunField(t.runs[0]);assert.equal(E.compactRecord(t.runs[0].field),record);
});

test('F4: main 499a0d3 refuses version 14 by name, alone, in a project and in a recovery record, and does not adopt the record',()=>{
 const golden=JSON.parse(fixture('refusals-v14-499a0d3.json'));
 assert.deepEqual(golden,{session:message,project:'Optical waveguide: '+message,recovery:message,adopted:false});
});

test('F10: a compact field\'s bytes are its counts\' characters and its keys; the cached sum is the written length',()=>{
 const s=N.parseSession(fixture(V14)),text=fixture(V14);
 for(const run of s.runs.filter(r=>E.isCompactField(r.field))){
  const r=E.compactRecord(run.field),c=r.counts;
  const keys=`,"field":{"encoding":"f32-base64-v1","counts":{"modes":${c.modes},"nodes":${c.nodes},"triangles":${c.triangles}},"node_coordinates":"","triangles":"","real":"","imag":""}`;
  assert.equal(N.runFieldBytes(run),E.compactFieldChars(c)+utf8(keys),`Run ${run.number}`);
 }
 const sum=N.sessionBytesWithoutFields(s.input,s.runs,s.selected,s.comparison,s.view)+s.runs.reduce((a,r)=>a+N.runFieldBytes(r),0);
 assert.equal(sum,utf8(text));
});
