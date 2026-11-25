// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
// Number of modes (M4): Modes to find (1 to 8), the optical-shapes-v8 document, and the optical
// session of version 9 (runs of 1 to 8 modes, complex indices, the engine's values, runs without
// fields, a digest per run). A session that version 7 holds stays version 7, byte for byte.
const test=require('node:test');const assert=require('node:assert/strict');
const fs=require('node:fs');const path=require('node:path');
const STATIC='../../packages/simcase/src/simcase/studio/static/';
const FIXTURES=path.join(__dirname,'studio_session_fixtures');
const fixture=name=>fs.readFileSync(path.join(FIXTURES,name),'utf8');
let N,O,I,P,M,S,F;
test.before(async()=>{
 N=await import(STATIC+'workspace-notebook.mjs');O=await import(STATIC+'workspace-optical.mjs');I=await import(STATIC+'workspace-inputs.mjs');
 P=await import(STATIC+'workspace-project.mjs');M=await import(STATIC+'workspace-modes.mjs');S=await import(STATIC+'workspace-multiphysics-session.mjs');
 F=await import(STATIC+'workspace-field.mjs');
});
const setup=()=>({materials:{Core:'Silicon',Oxide:'Silica',Heater:''},temperature:293.15,cooling:'',fixed:'',terminal:''});
const state=(extra={})=>({height:220,width:500,wavelength:1550,coreMesh:30,electric:false,heat:false,structure:false,optics:true,
 shapes:[{name:'Core',type:'rect',material:'Silicon',x:-250,y:0,w:500,h:220}],...extra});
const input=(width=500)=>P.snapshot({width,voltage:1,electric:false,heat:false,structure:false,optics:true,wavelength:1550,coreMesh:30},setup());
// k modes on four nodes and two triangles, values of every sign (and a negative zero)
const field=k=>({node_coordinates:[[0,0],[1e-6,0],[0,1e-6],[1e-6,1e-6]],triangles:[[0,1,2],[1,3,2]],
 real:Array.from({length:k},(_,m)=>[[1,0.25*m,-0],[0.5,-0.125,1e-3*(m+1)]]),imag:Array.from({length:k},(_,m)=>[[0,1e-9*m,0],[-2e-3,0,0]])});
const neff=k=>Array.from({length:k},(_,m)=>2.9-0.17*m);
const run=(job,k=8,asked=8,extra={})=>({job,completedAt:'2026-11-22T01:00:00.000Z',settings:N.opticalSettings(1550,30,asked),input:input(),
 effective_index:neff(k),field:field(k),origin:'local',serverVersion:'0.0.0',...extra});
const view={mode:0,component:'magnitude',window:'Core region'};
const write=(runs,v=view,options)=>N.sessionText(input(),runs,runs[0]?.job??null,[runs[0]?.job??null,runs.at(-1)?.job??null],v,options);
// a file changed and its digests computed again: what a damaged file with valid check values reads as
const redigest=doc=>{for(const r of doc.runs){delete r.digest;r.digest=S.recordDigest(r);}return doc;};
const edit=(text,f,digest=true)=>{const d=JSON.parse(text);f(d);return S.sessionJson(digest?redigest(d):d);};

test('M4-d client: Modes to find takes a whole number from 1 to 8; 0, 9 and 2.5 are refused with one message',()=>{
 const text='Modes to find must be a whole number from 1 to 8.';
 for(const raw of ['0','9','2.5','','-1','2e0','x'])assert.deepEqual(I.parseNumeric('modeCount',raw),{ok:false,message:text},raw);
 for(const [raw,value] of [['1',1],['8',8],[' 3 ',3]])assert.deepEqual(I.parseNumeric('modeCount',raw),{ok:true,value});
 assert.equal(I.INPUT_FIELDS.modeCount.label,'Modes to find');assert.equal(I.INPUT_FIELDS.modeCount.node,'Optical modes');
 assert.equal(I.editNoticeText('modeCount',3),'Modes to find set to 3. Run explicitly to compute new results.');
 for(const n of [0,9,2.5,'2',NaN,null,true])assert.throws(()=>N.opticalSettings(1550,30,n),{message:text},String(n));
 // the page's state: an absent count is the default
 for(const n of [0,9,2.5,'2',NaN,true])assert.throws(()=>O.opticalDocument(state({modeCount:n}),setup()),{message:text},String(n));
 assert.equal(O.opticalDocument(state({modeCount:undefined}),setup()).physics.em1.mode_count,2);
 for(const n of [1,8]){assert.equal(N.opticalSettings(1550,30,n).mode_count,n);assert.equal(O.opticalDocument(state({modeCount:n}),setup()).physics.em1.mode_count,n);}
 assert.deepEqual([...N.MODE_COUNT_RANGE],[1,8]);assert.equal(N.DEFAULT_MODE_COUNT,2);
});
test('M4-a: with 2 modes the optical-shapes-v8 document is the optical-shapes-v7 document of the template, byte for byte',()=>{
 // the fixture is the document of the Studio before mode counts (commit 78b9a60) for the template
 const v7=fixture('optical-document-template-v7.json');
 assert.equal(JSON.stringify(O.opticalDocument(state(),setup())),v7);
 assert.equal(JSON.stringify(O.opticalDocument(state({modeCount:2}),setup())),v7);
 assert.equal(JSON.stringify(O.opticalDocument(state({modeCount:5}),setup())),v7.replace('"mode_count":2','"mode_count":5'));
 // a run's settings: the v8 adapter with its count; a version 7 file writes them as optical-shapes-v7
 assert.deepEqual(Object.keys(N.opticalSettings()),['adapter','domain','boundary','mode_count','solver_version','vacuum_wavelength','core_element_size']);
 assert.deepEqual(N.v7Settings(N.opticalSettings()),{...N.opticalSettings(),adapter:'optical-shapes-v7'});
});
test('M4-c: "Found k of N modes above n = 1.45" only when fewer modes than asked were found',()=>{
 assert.equal(N.foundText(3,8),'Found 3 of 8 modes above n = 1.45');assert.equal(N.foundText(8,8),'');assert.equal(N.foundText(2,2),'');
 assert.equal(N.foundText(1,2),'Found 1 of 2 modes above n = 1.45');
 const r=N.validateRun(run('00000003',3,8));assert.equal(r.effective_index.length,3);assert.equal(N.runModeCount(r),8);
 assert.equal(M.modeTableRows(M.opticalModes(r)).rows.length,3);
 // more modes than asked are refused
 assert.throws(()=>N.validateRun(run('00000009',3,2)),/Invalid effective indices/);
});
test('V17: a session of two-mode real runs with fields is version 7, byte for byte; a run of another count makes it version 9',()=>{
 for(const name of ['empty','one','three']){
  const st=JSON.parse(fixture(`state-${name}.json`));
  assert.equal(N.sessionText(st.input,st.runs,st.selected,st.comparison,st.view),fixture(`optical-v7-${name}.json`),name);
 }
 const two=run('0000000a',2,2);assert.equal(JSON.parse(write([two])).version,7);
 // engine values of a two-mode run are not written to version 7 (they are recomputed from the field on open)
 const withEngine=run('0000000a',2,2,{te_polarization_fraction:[0.9,0.1],effective_area:[2e-13,3e-13]});
 assert.equal(write([withEngine]),write([two]));
 for(const [what,r,v] of [['8 modes',run('0000000b'),view],['3 of 8',run('0000000c',3,8),view],['1 of 2',run('0000000d',1,2),view],
  ['complex',run('0000000e',2,2,{effective_index:{re:[2.4,1.7],im:[1e-4,0]}}),view],['group index',run('0000000f',2,2,{group_index:[4.2,null]}),view],
  ['view mode 3',run('00000010'),{...view,mode:3}]]){
  const text=write([r,two],v),doc=JSON.parse(text);
  assert.equal(doc.version,9,what);assert.equal(doc.application,'optical',what);
  assert.deepEqual(Object.keys(doc),['format','version','application','input','runs','selected','comparison','view'],what);
 }
});
test('V17: opening a version 6 or 7 file reads two modes with Studio\'s TE fraction and A_eff; writing it again is version 7',()=>{
 for(const name of ['optical-v6-one.json','optical-v7-one.json','optical-v6-three.json','optical-v7-three.json']){
  const s=N.parseSession(fixture(name));
  for(const r of s.runs){
   assert.equal(r.effective_index.length,2,name);assert.equal(N.runModeCount(r),2,name);assert.equal(r.settings.adapter,'optical-shapes-v7',name);
   const modes=M.opticalModes(r);assert.equal(r.te.source,'studio');assert.equal(r.area.source,'studio');
   assert.deepEqual(modes.map(m=>m.fte),[0,1].map(i=>M.teFraction(r.field,i)));assert.deepEqual(modes.map(m=>m.area),[0,1].map(i=>M.effectiveArea(r.field,i)));
  }
  // not rewritten: the session read writes version 7 again (the text differs only where the runs became imported)
  const again=JSON.parse(N.sessionText(s.input,s.runs,s.selected,s.comparison,s.view));assert.equal(again.version,7,name);
  const original=JSON.parse(fixture(name).replace(/"version":6/g,'"version":7'));
  assert.deepEqual(again.runs.map(r=>({...r,origin:null})),original.runs.map(r=>({...r,origin:null,input:again.runs.find(x=>x.job===r.job).input})),name);
 }
 // a version 7 file carries no version 9 key: one is not read (as before), and the run reads two modes
 const extra=JSON.parse(fixture('optical-v7-one.json'));extra.runs[0].te_polarization_fraction=[0.5,0.5];extra.runs[0].group_index=[1,2];
 const r=N.parseSession(JSON.stringify(extra)).runs[0];assert.equal(r.te_polarization_fraction,undefined);assert.equal(r.group_index,undefined);
 // a version 7 file keeps exactly two real modes
 for(const change of [d=>{d.runs[0].effective_index=[2.4,1.7,1.5];},d=>{d.runs[0].effective_index={re:[2.4,1.7],im:[0,0]};},d=>{d.runs[0].settings.mode_count=8;},d=>{d.runs[0].settings.adapter='optical-shapes-v8';},d=>{delete d.runs[0].field;}]){
  const d=JSON.parse(fixture('optical-v7-one.json'));change(d);assert.throws(()=>N.parseSession(JSON.stringify(d)));
 }
});
test('V17: version 9 round-trips bit for bit: complex indices, engine values, group index slots and negative zero',()=>{
 const runs=[run('00000001',8,8,{te_polarization_fraction:Array.from({length:8},(_,i)=>i/8),effective_area:Array.from({length:8},(_,i)=>(i+1)*1e-13)}),
  run('00000002',3,8,{effective_index:{re:[2.9,2.4,1.6],im:[1e-4,-0,2.5e-7]},group_index:[4.1,null,3.9],group_index_method:'finite difference in wavelength'}),
  run('00000003',2,2,{pinned:true,label:'Reference'})];
 const text=write(runs,{...view,mode:7}),doc=JSON.parse(text);
 assert.equal(doc.version,9);assert.match(text,/"im":\[0\.0001,-0\.0,2\.5e-7\]/);
 assert.deepEqual(Object.keys(doc.runs[1]),['job','completedAt','label','pinned','origin','serverVersion','settings','input','effective_index','field','group_index','group_index_method','digest']);
 assert.deepEqual(Object.keys(doc.runs[0]),['job','completedAt','label','pinned','origin','serverVersion','settings','input','effective_index','field','te_polarization_fraction','effective_area','digest']);
 assert.equal(doc.runs[2].settings.adapter,'optical-shapes-v8');
 for(const r of doc.runs)assert.equal(r.digest,S.recordDigest(r));
 const read=N.parseSession(text);
 assert.equal(Object.is(read.runs[1].effective_index_im[1],-0),true);assert.equal(Object.is(read.runs[1].field.real[0][0][2],-0),true);
 assert.deepEqual(read.runs[1].group_index,[4.1,null,3.9]);assert.equal(read.runs[1].group_index_method,'finite difference in wavelength');
 assert.equal(read.view.mode,7);
 // the runs Studio read are written with origin "imported"; a file of imported runs round-trips exactly
 const imported=write(read.runs,read.view);
 assert.equal(write(N.parseSession(imported).runs,read.view),imported);
 const back=JSON.parse(imported);assert.deepEqual(back.runs.map(r=>r.origin),['imported','imported','imported']);
 assert.deepEqual(back.runs.map(({origin,digest,...r})=>r),doc.runs.map(({origin,digest,...r})=>r));
 // the engine's values come back as the engine's
 M.opticalModes(read.runs[0]);assert.equal(read.runs[0].te.source,'engine');assert.equal(read.runs[0].area.source,'engine');
 assert.deepEqual(M.opticalModes(read.runs[1]).map(m=>m.im),[1e-4,-0,2.5e-7]);
 // a version 9 reader accepts runs without the group index slots
 assert.equal(read.runs[0].group_index,undefined);
});
test('V17: the digest covers every key of a version 9 run; unknown keys and mode counts over 8 are refused with messages',()=>{
 const runs=[run('00000001',8,8,{te_polarization_fraction:Array(8).fill(0.5),effective_area:Array(8).fill(1e-13),group_index:Array(8).fill(4),group_index_method:'m'}),
  run('00000002',2,2,{effective_index:{re:[2.4,1.7],im:[1e-4,0]}})];
 const text=write(runs);assert.equal(N.parseSession(text).runs.length,2);
 const changed=/^Run [12] changed after it was saved \(its check value does not match\)\.$/;
 for(const [what,f] of [['n_eff',d=>{d.runs[0].effective_index[0]+=1e-12;}],['im',d=>{d.runs[1].effective_index.im[0]=2e-4;}],
  ['te',d=>{d.runs[0].te_polarization_fraction[3]=0.25;}],['area',d=>{d.runs[0].effective_area[0]=2e-13;}],['group index',d=>{d.runs[0].group_index[7]=4.5;}],
  ['method',d=>{d.runs[0].group_index_method='n';}],['mode count',d=>{d.runs[0].settings.mode_count=7;}],['field',d=>{d.runs[0].field.real[0][0][0]=0.75;}],
  ['label',d=>{d.runs[1].label='other';}],['pin',d=>{d.runs[1].pinned=true;}],['origin',d=>{d.runs[1].origin='recovered';}],['input',d=>{d.runs[1].input.model.wavelength=1551;}],
  ['removed key',d=>{delete d.runs[0].group_index_method;}],['removed field',d=>{delete d.runs[1].field;}]])
  assert.throws(()=>N.parseSession(edit(text,f,false)),{message:changed},what);
 assert.throws(()=>N.parseSession(edit(text,d=>{d.extra=1;})),{message:'Unknown key "extra" in the session file.'});
 assert.throws(()=>N.parseSession(edit(text,d=>{d.runs[1].note='x';})),{message:'Run 2: unknown key "note".'});
 assert.throws(()=>N.parseSession(edit(text,d=>{d.runs[0].settings.mode_count=9;})),{message:'Run 1 asks for 9 modes; this Studio reads 1 to 8.'});
 assert.throws(()=>N.parseSession(edit(text,d=>{d.runs[0].settings.mode_count=2.5;})),{message:'Run 1 asks for 2.5 modes; this Studio reads 1 to 8.'});
 assert.throws(()=>N.parseSession(edit(text,d=>{d.application='multiphysics';})),{message:'A version 9 session file holds an optical model (application "optical").'});
 assert.throws(()=>N.parseSession(edit(text,d=>{d.runs[0].settings.adapter='optical-shapes-v7';})),{message:'Run 1: unsupported run settings (a version 9 file writes optical-shapes-v8).'});
 assert.throws(()=>N.parseSession(edit(text,d=>{delete d.runs[0].digest;},false)),{message:'Run 1: missing digest.'});
 assert.throws(()=>N.parseSession(edit(text,d=>{d.runs[0].effective_index.reverse();d.runs[0].field.real.reverse();d.runs[0].field.imag.reverse();})),{message:'Run 1: its effective indices are not ranked by Re n_eff.'});
 assert.throws(()=>N.parseSession(edit(text,d=>{d.runs[1].effective_index.re[1]=1.45;})),{message:'Run 2: an effective index is not above n = 1.45.'});
 assert.throws(()=>N.parseSession(edit(text,d=>{d.runs[0].te_polarization_fraction[0]=1.5;})),{message:'Run 1: invalid saved TE fractions.'});
 assert.throws(()=>N.parseSession(edit(text,d=>{d.runs[0].effective_area.pop();})),{message:'Run 1: invalid saved effective areas.'});
 assert.throws(()=>N.parseSession(edit(text,d=>{delete d.runs[0].group_index;})),{message:'Run 1: invalid group index method.'});
 assert.throws(()=>N.parseSession(edit(text,d=>{d.runs[0].field.real.pop();d.runs[0].field.imag.pop();})),{message:'Invalid complex field samples.'});
 assert.throws(()=>N.parseSession(edit(text,d=>{d.view.mode=2;d.selected=d.runs[1].job;})),{message:'Unsupported saved field view.'});
 // a newer file is refused by name; a Studio before version 9 refused this one with the same template
 // (version 10, the open boundary, is read since slice P2, and version 11, the closed-window search,
 // since slice C2, and version 12, the run numbers, since then: version 13 is the newer one; the refusal Studio 4b58fb7 gave a version 10 file is
 // newerVersionText(10, 9), and the one Studio 13f07f4 gives a version 11 file newerVersionText(11, 10))
 assert.throws(()=>N.parseSession(edit(text,d=>{d.version=13;})),{message:'This session file is version 13, newer than this Studio reads (versions 6–12). Open it in a newer Studio.'});
 assert.equal(N.newerVersionText(11,10),'This session file is version 11, newer than this Studio reads (versions 6–10). Open it in a newer Studio.');
 assert.equal(N.newerVersionText(10,9),'This session file is version 10, newer than this Studio reads (versions 6–9). Open it in a newer Studio.');
 assert.equal(N.newerVersionText(9,8),'This session file is version 9, newer than this Studio reads (versions 6–8). Open it in a newer Studio.');
});
test('M4-e: over 16 MiB a session keeps the fields of the selected and pinned runs only, when asked; the others keep n_eff, TE and A_eff',()=>{
 const runs=[run('00000001'),run('00000002',8,8,{pinned:true}),run('00000003'),run('00000004')];
 const full=N.writeOpticalSession(input(),runs,'00000003',['00000001','00000004'],view);assert.equal(full.ok,true);
 // a limit below the file: a question, nothing written
 const limit=full.bytes-1,asked=N.writeOpticalSession(input(),runs,'00000003',['00000001','00000004'],view,{limit});
 assert.equal(asked.ok,false);assert.equal(asked.refusal,null);assert.deepEqual(asked.reduced.notKept,[1,4]);assert.ok(asked.reduced.bytes<limit);
 assert.match(N.opticalOverflowQuestion(23182303),/^Session is 23 MB; the limit is 16 MiB\. Keep the fields of the selected and pinned runs only\? The other runs keep n_eff, the TE fractions and the effective areas, but not their fields\.$/);
 const kept=N.writeOpticalSession(input(),runs,'00000003',['00000001','00000004'],view,{limit,keepSelected:true});
 assert.equal(kept.ok,true);assert.deepEqual(kept.notKept,[1,4]);
 const doc=JSON.parse(kept.text);assert.equal(doc.version,9);assert.deepEqual(doc.runs.map(r=>'field' in r),[false,true,true,false]);
 const shown=M.opticalModes(runs[0]);assert.deepEqual(doc.runs[0].te_polarization_fraction,shown.map(m=>m.fte));assert.deepEqual(doc.runs[0].effective_area,shown.map(m=>m.area));
 const read=N.parseSession(kept.text);assert.equal(read.runs[0].field,null);
 const modes=M.opticalModes(read.runs[0]);assert.equal(read.runs[0].te.source,'file');assert.deepEqual(modes.map(m=>m.fte),shown.map(m=>m.fte));
 assert.match(M.SOURCE_TEXT.file,/fields were not kept/);
 // written again, the run without fields stays without fields and keeps its values
 assert.equal(N.sessionText(read.input,read.runs,read.selected,read.comparison,read.view),write(read.runs.map(r=>r),view).replace(/"selected":"[0-9a-f]+","comparison":\[[^\]]*\]/,`"selected":"00000003","comparison":["00000001","00000004"]`));
 // V17: a field-less run round-trips bit for bit (a file of the runs Studio read, whose origin is imported)
 const once=N.sessionText(read.input,read.runs,read.selected,read.comparison,read.view),reread=N.parseSession(once);
 assert.equal(N.sessionText(reread.input,reread.runs,reread.selected,reread.comparison,reread.view),once);
 assert.equal('field' in JSON.parse(once).runs[0],false);assert.equal(Object.is(reread.runs[0].effective_index[0],read.runs[0].effective_index[0]),true);
 // a field-less run must carry its values: without TE fractions or without effective areas it is refused
 for(const key of ['te_polarization_fraction','effective_area'])
  assert.throws(()=>N.parseSession(edit(kept.text,d=>{delete d.runs[0][key];})),{message:'Run 1 has no fields and no saved TE fractions and effective areas.'},key);
 // even the selected and pinned runs over the limit: refused, naming them
 const tight=N.writeOpticalSession(input(),runs,'00000003',['00000001','00000004'],view,{limit:1000,keepSelected:true});
 assert.equal(tight.ok,false);assert.match(tight.refusal,/^The selected run \(Run 3\) and the pinned run \(Run 2\) are [\d.]+ MB with their fields, over the 16\.8 MB session limit\. Unpin it\.$/);
 // browser recovery takes the reduced file without asking
 const capture=N.captureSession(input(),runs,'00000003',['00000001','00000004'],view);assert.equal(JSON.parse(capture()).version,9);
});
test('the study signature: a two-mode run keeps the signature of its inputs; another count adds it',()=>{
 const i=input();assert.equal(N.studySignature(i),JSON.stringify(i));assert.equal(N.studySignature(i,2),JSON.stringify(i));
 assert.equal(N.studySignature(i,8),JSON.stringify(i)+'\n8 modes');
 assert.equal(N.validateRun(run('00000001',8,8)).signature,JSON.stringify(N.validateRun(run('00000001')).input)+'\n8 modes');
 assert.equal(N.validateRun(run('00000001',2,2)).signature,JSON.stringify(input()));
});
test('the field module reads 1 to 8 modes and shows any of them',()=>{
 const f=field(8),data={node_coordinates:f.node_coordinates,field_units:{node_coordinates:'m'},triangles:f.triangles,vector_fields:[{...F.FIELD_METADATA,real:f.real,imag:f.imag}]};
 const read=F.readOpticalField(data,8);assert.equal(read.real.length,8);assert.equal(F.fieldScalars(read,7).values.length,2);
 assert.throws(()=>F.fieldScalars(read,8),/Invalid field selection/);assert.throws(()=>F.readOpticalField(data),/Invalid complex field samples/);
 assert.throws(()=>F.readOpticalField(data,9),/Invalid complex field samples/);
});
test('engine values of a new result: the first study point, k entries, within range',()=>{
 const summary={mode_postprocessing:{te_polarization_fraction:{unit:'1',values:[[0.98,0.05,null]]},effective_area:{unit:'m^2',values:[[1.9e-13,3.4e-13,5e-13]]}}};
 assert.deepEqual(N.engineRunValues(summary,3),{te_polarization_fraction:[0.98,0.05,null],effective_area:[1.9e-13,3.4e-13,5e-13]});
 assert.deepEqual(N.engineRunValues(summary,2),{});
 assert.deepEqual(N.engineRunValues({mode_postprocessing:{te_polarization_fraction:{unit:'1',values:[[1.2,0,0]]}}},3),{});
});
test('review: the writer refuses what a version 9 reader would refuse; a v9 file needs every top-level key',()=>{
 // a version 7 run whose indices are not ranked above 1.45 opens as before, but cannot go into version 9
 for(const bad of [[2.0,2.5],[2.0,1.44]]){
  const d=JSON.parse(fixture('optical-v7-one.json'));d.runs[0].effective_index=bad;const s=N.parseSession(JSON.stringify(d));
  assert.equal(JSON.parse(N.sessionText(s.input,s.runs,s.selected,s.comparison,s.view)).version,7,'still written as version 7');
  assert.throws(()=>write([...s.runs,run('00000077')]),{message:'Run 1: its effective indices are not ranked by Re n_eff above n = 1.45, so a version 9 session cannot hold it. Remove the run or save it in a session of its own.'});
 }
 // a view of a mode the selected run does not have is not written
 assert.throws(()=>N.sessionText(input(),[run('00000001',3,8),run('00000002')],'00000001',['00000001',null],{...view,mode:3}),{message:'Unsupported saved field view.'});
 const text=write([run('00000001')]);
 assert.throws(()=>N.parseSession(edit(text,d=>{delete d.view;})),{message:'The session file has no "view".'});
});
test('review: importing a run that a file kept without its fields is the same run, not a conflict',()=>{
 const runs=[run('00000001'),run('00000002')],full=N.parseSession(write(runs));
 const reduced=N.parseSession(N.writeOpticalSession(input(),runs,'00000002',['00000001','00000002'],view,{limit:1,keepSelected:true}).ok?'':N.sessionText(input(),runs,'00000002',['00000001','00000002'],view,{keep:new Set(['00000002'])}));
 assert.equal(reduced.runs[0].field,null);
 for(const [have,add] of [[full.runs,reduced.runs],[reduced.runs,full.runs]]){const out=N.mergeRuns(have,add);assert.deepEqual(out.reused,['00000001','00000002']);assert.deepEqual(out.added,[]);}
 // a different field is still a conflict
 const other=N.parseSession(write([run('00000001',8,8,{field:{...field(8),real:field(8).real.map(m=>m.map(v=>v.map(x=>x+1)))}})]));
 assert.throws(()=>N.mergeRuns(full.runs,other.runs),/Conflicting result for job 00000001/);
});
test('V17: a key inside field other than the four arrays is not refused, as in version 7; the digest covers it and it is not written again',()=>{
 const v7=JSON.parse(fixture('optical-v7-one.json'));v7.runs[0].field.note='x';assert.equal(N.parseSession(JSON.stringify(v7)).runs.length,1);
 const text=write([run('00000001')]),added=edit(text,d=>{d.runs[0].field.note='x';});
 const read=N.parseSession(added);assert.equal('note' in read.runs[0].field,false);
 assert.doesNotMatch(N.sessionText(read.input,read.runs,read.selected,read.comparison,read.view),/"note"/);
 assert.throws(()=>N.parseSession(edit(text,d=>{d.runs[0].field.note='x';},false)),{message:/^Run 1 changed after it was saved/});
});
