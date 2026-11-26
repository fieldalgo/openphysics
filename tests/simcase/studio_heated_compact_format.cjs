// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
// Compact heated maps (multiphysics session version 17, encoding "f32-offset-base64-v1"; design
// "Session versions 16 and 17", slice S2): the checks of the pre-registration that need no engine run.
// HQ1 (the encoding: every decoded sample is bitwise base + fround(x − base), coordinates, triangles
// and regions bitwise equal; the size follows from the counts), HQ7 (a version 17 round trip: the same
// bytes, the decoded maps bitwise the tab's, the run records equal; through a project file and browser
// recovery), HQ8 (every heated fixture of version 8 and 15 is written again byte for byte, none as
// version 17), HQ9 (refusals by name), HQ10 (the merge base c0dbc09, the last Studio before session
// version 16, refuses the file by name: studio_session_fixtures/refusals-v17-c0dbc09.json, written by
// compact_heated_sessions.mjs from that commit's static folder) and HQ11 (a run beyond single precision
// or of more than 256 region names stays text, at its text size). HQ1 to HQ4 on engine results are in
// tests/simcase/studio_heated_retention_engine.cjs.
const test=require('node:test');const assert=require('node:assert/strict');
const fs=require('node:fs');const path=require('node:path');
const S='../../packages/simcase/src/simcase/studio/static/';
const FIX=path.join(__dirname,'studio_session_fixtures');
const fixture=name=>fs.readFileSync(path.join(FIX,name),'utf8');
let M,N,PF,R,E,F,C;
test.before(async()=>{M=await import(S+'workspace-multiphysics-session.mjs');N=await import(S+'workspace-notebook.mjs');PF=await import(S+'workspace-project-file.mjs');
 R=await import(S+'workspace-notebook-recovery.mjs');E=await import(S+'workspace-map-encoding.mjs');F=await import(S+'workspace-field-encoding.mjs');C=await import('./studio_session_fixtures/compact_heated_sessions.mjs');});
const V17='multiphysics-v17-compact.json';
const stateOf=s=>({document:s.document,runs:s.runs,baselines:s.baselines,selected:s.selected,view:s.view});
const edit=(t,f,{keepDigest=false}={})=>{const d=JSON.parse(t);f(d);if(!keepDigest)for(const r of d.runs){delete r.digest;r.digest=M.recordDigest(r);}return M.sessionJson(d);};
const refused=(t,message)=>assert.throws(()=>N.parseSession(t),{message});
const message='This session file is version 17, newer than this Studio reads (versions 6–15). Open it in a newer Studio.';
const b64=(kind,values)=>{const size={f32:4,f64:8,u32:4,u8:1}[kind],v=new DataView(new ArrayBuffer(size*values.length));values.forEach((x,i)=>kind==='f32'?v.setFloat32(4*i,x,true):kind==='f64'?v.setFloat64(8*i,x,true):kind==='u32'?v.setUint32(4*i,x,true):v.setUint8(i,x));return Buffer.from(v.buffer).toString('base64');};
const same=(a,b,what)=>{assert.equal(a.length,b.length,what);a.forEach((x,i)=>assert.ok(Object.is(x,b[i]),`${what} ${i}: ${x} ${b[i]}`));};
const run=(number,result,extra={})=>({job:'mp-'+(0x17d000000000+number).toString(16),number,label:'',pinned:false,completedAt:`2026-11-26T11:${String(number).padStart(2,'0')}:00.000Z`,serverVersion:'0.0.2',
 doc:C.documentOf(),events:[],order:result.solve_order,result,maps:'kept',origin:'imported',...extra});

test('HQ1: each decoded sample is base + fround(x − base) bitwise; coordinates, triangles and regions are exact; the strings are little-endian base64 of the counts\' sizes',()=>{
 for(const [n,options] of [[2,{}],[6,{withK:true}],[40,{seed:7,names:['background','core','heater','unused']}],[301,{seed:3,withK:true}]]){
  const server=C.stripResult(n,options),record=E.encodeMaps(structuredClone(server),C.documentOf()),read=E.decodeMaps(record,C.documentOf(),'Run 1');
  const m=server.mesh,c=record.mesh,names=m.region_names.length;
  assert.deepEqual(Object.keys(c),['encoding','counts','node_coordinates','field_units','triangles','regions','region_names']);
  assert.deepEqual(c.counts,{nodes:m.node_coordinates.length,triangles:m.triangles.length});
  assert.equal(c.node_coordinates,b64('f64',m.node_coordinates.flat()));assert.equal(c.triangles,b64('u32',m.triangles.flat()));assert.equal(c.regions,b64('u8',m.regions));
  same(read.mesh.node_coordinates.flat(),m.node_coordinates.flat(),'coordinates');assert.deepEqual(read.mesh.triangles,m.triangles);assert.deepEqual(read.mesh.regions,m.regions);
  const T=server.physics.heat1.temperature.values,min=server.physics.heat1.range.min;
  assert.equal(record.physics.heat1.temperature.values,b64('f32',T.map(x=>x-min)));
  same(read.physics.heat1.temperature.values,T.map(x=>min+Math.fround(x-min)),'node T');
  const k=server.physics.modes1.coupled,kr=record.physics.modes1.coupled,kd=read.physics.modes1.coupled,regions=m.regions;
  for(const [what,a,text,base,back] of [['n',k.refractive_index.n,kr.refractive_index.n,kr.refractive_index.n_base,kd.refractive_index.n],['index_change',k.index_change,kr.index_change,kr.index_change_base,kd.index_change],
   ...(k.refractive_index.k?[['k',k.refractive_index.k,kr.refractive_index.k,kr.refractive_index.k_base,kd.refractive_index.k]]:[])]){
   assert.deepEqual(base,E.regionBases(a,regions,names),what);assert.equal(base.length,names);
   assert.equal(text,b64('f32',a.map((x,i)=>x-base[regions[i]])),what);
   same(back,a.map((x,i)=>base[regions[i]]+Math.fround(x-base[regions[i]])),what);
  }
  if(!k.refractive_index.k){assert.equal(kr.refractive_index.k,null);assert.ok(!('k_base' in kr.refractive_index));}
  // the coupled temperature is not stored; it reads as the mean of the decoded node temperatures
  assert.deepEqual(kr.temperature,{unit:'K',location:'element'});
  same(kd.temperature.values,m.triangles.map(t=>(read.physics.heat1.temperature.values[t[0]]+read.physics.heat1.temperature.values[t[1]]+read.physics.heat1.temperature.values[t[2]])/3),'coupled T');
  // the size: 4⌈16N/3⌉ + 4⌈12M/3⌉ + 4⌈M/3⌉ + 4⌈4N/3⌉ + (2 or 3)·4⌈4M/3⌉
  const N=c.counts.nodes,Mt=c.counts.triangles,q=x=>4*Math.ceil(x/3),maps=k.refractive_index.k?3:2;
  assert.equal(E.compactMapChars(c.counts,{heat:1,triangleMaps:maps}),q(16*N)+q(12*Mt)+q(Mt)+q(4*N)+maps*q(4*Mt));
  assert.equal(E.recordMapChars(record),E.compactMapChars(c.counts,{heat:1,triangleMaps:maps}));
  // the range stays the server's: its minimum decodes exactly, its maximum to min + fround(span)
  const D=read.physics.heat1.temperature.values;
  assert.equal(Math.min(...D),min);assert.equal(Math.max(...D),min+Math.fround(server.physics.heat1.range.max-min));
  assert.deepEqual(read.physics.heat1.range,server.physics.heat1.range);
  // everything else is the server's, unchanged
  assert.deepEqual({...read,mesh:null,physics:null},{...server,mesh:null,physics:null});
 }
});

test('HQ7: a version 17 session round-trips byte for byte; the decoded maps are the tab\'s; the run records are kept; also through a project file and browser recovery',()=>{
 const text=fixture(V17);
 assert.equal(C.compactHeatedSession(M),text);
 const d=JSON.parse(text);
 assert.equal(d.version,17);assert.deepEqual(d.runs.map(r=>[r.number,r.maps]),[[2,'compact'],[3,'not kept'],[5,'compact']]);
 const s=N.parseSession(text),tab=C.compactHeatedState(M);
 assert.equal(M.writeMultiphysicsSession(stateOfSession(s)).text,text);assert.equal(M.recoveryText(stateOfSession(s)).text,text);
 s.runs.forEach((r,i)=>{
  const t=tab.runs[i];
  for(const key of ['job','number','label','pinned','completedAt','serverVersion','events','maps'])assert.deepEqual(r[key],t[key],`Run ${r.number} ${key}`);
  if(r.maps==='compact'){
   assert.ok(M.isCompactResult(r.result));
   for(const get of [x=>x.mesh.node_coordinates.flat(),x=>x.mesh.triangles.flat(),x=>x.mesh.regions,x=>x.physics.heat1.temperature.values,x=>x.physics.modes1.coupled.temperature.values,
    x=>x.physics.modes1.coupled.refractive_index.n,x=>x.physics.modes1.coupled.index_change,x=>x.physics.modes1.coupled.refractive_index.k??[]])same(get(r.result),get(t.result),`Run ${r.number}`);
   // the values (n_eff, the range, the coupling check) are the server's
   assert.deepEqual(r.result.physics.modes1.effective_index,t.result.physics.modes1.effective_index);assert.deepEqual(r.result.physics.heat1.range,t.result.physics.heat1.range);
   assert.deepEqual(r.result.couplings,t.result.couplings);
  }
 });
 const project=PF.writeProject({name:'p',savedAt:'2026-11-26T10:00:00.000Z',studio:'0.0.0',active:'m1',entries:[PF.projectEntry({id:'m1',kind:'multiphysics',title:'Heated silicon waveguide',card:'heated-waveguide',text})]}).text;
 const entry=PF.readProject(project).models[0];assert.equal(entry.text,text);assert.deepEqual(entry.session.runs.map(r=>r.maps),['compact','not kept','compact']);
 const restored=R.readNotebookRecovery({version:1,savedAt:'2026-11-26T10:00:00.000Z',session:text}).session;
 assert.equal(M.recoveryText(stateOfSession(restored)).text,text);
 assert.deepEqual([...PF.KIND_VERSIONS.multiphysics],[8,15,17]);
 // a compact run let go and taken back is compact again, its record unchanged
 const back=N.parseSession(text).runs[0],record=M.sessionJson(M.sessionRun(back));M.letGoMaps(back);assert.equal(back.maps,'not kept');
 assert.equal(M.sessionJson(M.sessionRun(back)),M.sessionJson(M.sessionRun({...N.parseSession(text).runs[0]},false)));
 // 20 runs: version 17, again byte for byte
 const twenty=Array.from({length:20},(_,i)=>run(i+1,C.stripResult(4,{seed:i})));twenty.forEach(r=>assert.ok(M.compactRunMaps(r)));
 const t20=M.writeMultiphysicsSession({...tab,runs:twenty,selected:twenty[19].job}).text;
 assert.equal(JSON.parse(t20).version,17);assert.equal(M.writeMultiphysicsSession(stateOfSession(N.parseSession(t20))).text,t20);
 // one compact run among two: version 17 (any run count)
 assert.equal(JSON.parse(M.writeMultiphysicsSession({...tab,runs:[twenty[0]],selected:twenty[0].job}).text).version,17);
 assert.equal(record,M.sessionJson(M.sessionRun(N.parseSession(text).runs[0])));
});
const stateOfSession=stateOf;

test('HQ8: every heated fixture of version 8 and 15 is written again byte for byte, none as version 17',()=>{
 const texts={...JSON.parse(fixture('multiphysics-v8-ddb09a1.json')),'multiphysics-v8.json':fixture('multiphysics-v8.json'),'multiphysics-v15-thirteen-runs.json':fixture('multiphysics-v15-thirteen-runs.json')};
 for(const [name,text] of Object.entries(texts)){
  const s=N.parseSession(text),state=stateOf(s);
  assert.ok([8,15].includes(JSON.parse(text).version),name);
  assert.equal(M.writeMultiphysicsSession(state).text,text,name);assert.equal(M.recoveryText(state).text,text,name);
  assert.ok(s.runs.every(r=>r.maps!=='compact'),name);assert.ok(!text.includes(E.MAP_ENCODING),name);
 }
});

test('HQ9: damaged compact maps are refused by name',()=>{
 const text=fixture(V17),run2=d=>d.runs[0].result,where="Run 2's stored maps are not well formed";
 // a string whose length does not fit its counts; one that is not canonical base64
 refused(edit(text,d=>{run2(d).mesh.triangles+='AAAA';}),`${where}: triangles holds 123 bytes; its counts give 120.`);
 refused(edit(text,d=>{run2(d).physics.heat1.temperature.values=run2(d).physics.heat1.temperature.values.slice(0,-4);}),`${where}: heat1 node temperature holds 45 bytes; its counts give 48.`);
 refused(edit(text,d=>{const v=run2(d).mesh.regions;run2(d).mesh.regions=v.slice(0,-1)+'-';}),`${where}: regions is not canonical base64.`);
 refused(edit(text,d=>{run2(d).physics.modes1.coupled.refractive_index.n=run2(d).physics.modes1.coupled.refractive_index.n.replace(/=*$/,m=>m+' ').trimEnd()+'\n';}),`${where}: refractive_index.n is not canonical base64.`);
 // a decoded heat maximum that is not range.min + fround(range.max − range.min)
 refused(edit(text,d=>{run2(d).physics.heat1.range.max+=1e-6;}),"Run 2's heat range does not equal the minimum and maximum of its stored temperatures.");
 // a region index at or beyond the number of names
 refused(edit(text,d=>{const m=run2(d).mesh;m.regions=b64('u8',Array.from({length:m.counts.triangles},(_,i)=>i===3?2:0));}),`${where}: regions must hold 10 integers in 0–1.`);
 // maps "compact" in a version 15 file (seven runs, so the file is not read as version 8)
 const seven=M.writeMultiphysicsSession({...C.compactHeatedState(M),runs:Array.from({length:7},(_,i)=>run(i+1,C.stripResult(4,{seed:i})))}).text;
 assert.equal(JSON.parse(seven).version,15);
 refused(edit(seven,d=>{const r=JSON.parse(text).runs[0];d.runs[0]={...r,job:d.runs[0].job,number:1};}),"Run 1's stored maps are not well formed: compact maps are read from a version 17 session file only.");
 // another encoding, other mesh keys, a coupled temperature with values, missing bases
 refused(edit(text,d=>{run2(d).mesh.encoding='f16-base64-v1';}),`${where}: the maps are encoded as "f16-base64-v1", which this Studio does not read.`);
 refused(edit(text,d=>{run2(d).mesh.scale=1;}),`${where}: a compact mesh holds counts, encoding, field_units, node_coordinates, region_names, regions, triangles and nothing else.`);
 refused(edit(text,d=>{run2(d).mesh.counts.nodes=0;}),`${where}: its counts must be whole numbers of nodes and triangles, at least 1.`);
 refused(edit(text,d=>{run2(d).physics.modes1.coupled.temperature.values=[300];}),`${where}: a compact coupled temperature holds no values (it is the mean of the node temperatures).`);
 refused(edit(text,d=>{run2(d).physics.modes1.coupled.refractive_index.n_base=[1];}),`${where}: refractive_index.n_base must hold 2 finite numbers, one per region.`);
 refused(edit(text,d=>{delete run2(d).physics.modes1.coupled.index_change_base;}),`${where}: index_change_base must hold 2 finite numbers, one per region.`);
 refused(edit(text,d=>{run2(d).physics.heat1.temperature.values=b64('f32',[NaN,...Array(11).fill(0)]);}),`${where}: heat1 node temperature holds a value that is not a finite number.`);
 // an edit that keeps the old digest
 refused(edit(text,d=>{run2(d).physics.modes1.coupled.refractive_index.n_base[0]+=1e-9;},{keepDigest:true}),'Run 2 changed after it was saved (its check value does not match).');
 // 21 runs, and above 17 by name
 const twenty=M.writeMultiphysicsSession({...C.compactHeatedState(M),runs:Array.from({length:20},(_,i)=>{const r=run(i+1,C.stripResult(4,{seed:i}));M.compactRunMaps(r);return r;})}).text;
 refused(edit(twenty,d=>{const r=structuredClone(d.runs[0]);r.job='mp-0000000000ff';r.number=21;d.runs.push(r);}),'Unsupported session format or run count.');
 refused(edit(text,d=>{d.version=18;}),'This session file is version 18, newer than this Studio reads (versions 6–17). Open it in a newer Studio.');
});

test('HQ10: the merge base c0dbc09 refuses version 17 by name, alone, in a project and in a recovery record, and does not adopt the record',async()=>{
 const golden=JSON.parse(fixture('refusals-v17-c0dbc09.json'));
 assert.deepEqual(golden,{session:message,project:'Heated silicon waveguide: '+message,recovery:message,adopted:false});
 const now=await C.readWith(new URL(S,'file://'+__dirname+'/').href,FIX);
 assert.deepEqual(now,{session:null,project:null,recovery:null,adopted:true});
});

test('HQ11: a run beyond single precision, or of more than 256 region names, or without its source temperatures, stays text at its text size',()=>{
 const cases={
  'beyond float32':(()=>{const r=C.stripResult(4);r.physics.modes1.coupled.index_change[3]=1e39;return r;})(),
  // index_change is 0 in the background: a background value of 1e-40 is an offset below 2^-126
  'a nonzero offset below 2^-126':(()=>{const r=C.stripResult(4),i=r.mesh.regions.indexOf(0),j=r.mesh.regions.indexOf(0,i+1);r.physics.modes1.coupled.index_change[j]=1e-40;return r;})(),
  '257 region names':(()=>{const r=C.stripResult(4);r.mesh.region_names=Array.from({length:257},(_,i)=>i<2?['background','core'][i]:'r'+i);return r;})(),
 };
 for(const [what,result] of Object.entries(cases)){
  const r=run(1,result),bytes=M.mapBytes(r);
  assert.equal(M.compactRunMaps(r),false,what);assert.equal(r.maps,'kept',what);assert.equal(M.mapBytes(r),bytes,what);assert.equal(E.encodeMaps(result,C.documentOf()),null,what);
 }
 // the coupled maps' source temperatures are not in the result
 const doc=C.documentOf();delete doc.couplings;assert.equal(E.encodeMaps(C.stripResult(4),doc),null);
 // a text run among compact runs: the file is version 17 and holds both
 const text=run(1,cases['257 region names']),compact=run(2,C.stripResult(4));assert.ok(M.compactRunMaps(compact));
 const t=M.writeMultiphysicsSession({...C.compactHeatedState(M),runs:[text,compact],selected:compact.job}).text,s=N.parseSession(t);
 assert.equal(JSON.parse(t).version,17);assert.deepEqual(s.runs.map(r=>r.maps),['kept','compact']);
});
