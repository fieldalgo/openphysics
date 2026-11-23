// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
// Group index (M5-s): Also compute group index in Study (off by default), the optical-shapes-v8
// document with and without results.group_index, the run values in the version 9 slots
// (group_index, group_index_method), the n_g cells of the modes table and of Compare.
const test=require('node:test');const assert=require('node:assert/strict');
const fs=require('node:fs');const path=require('node:path');
const STATIC='../../packages/simcase/src/simcase/studio/static/';
const fixture=name=>fs.readFileSync(path.join(__dirname,'studio_session_fixtures',name),'utf8');
let N,O,P,M,H,S;
test.before(async()=>{
 N=await import(STATIC+'workspace-notebook.mjs');O=await import(STATIC+'workspace-optical.mjs');P=await import(STATIC+'workspace-project.mjs');
 M=await import(STATIC+'workspace-modes.mjs');H=await import(STATIC+'workspace-match.mjs');S=await import(STATIC+'workspace-multiphysics-session.mjs');
});
const setup=()=>({materials:{Core:'Silicon',Oxide:'Silica',Heater:''},temperature:293.15,cooling:'',fixed:'',terminal:''});
const state=(extra={})=>({height:220,width:500,wavelength:1550,coreMesh:30,electric:false,heat:false,structure:false,optics:true,
 shapes:[{name:'Core',type:'rect',material:'Silicon',x:-250,y:0,w:500,h:220}],...extra});
const input=()=>P.snapshot({width:500,voltage:1,electric:false,heat:false,structure:false,optics:true,wavelength:1550,coreMesh:30},setup());
const field=k=>({node_coordinates:[[0,0],[1e-6,0],[0,1e-6],[1e-6,1e-6]],triangles:[[0,1,2],[1,3,2]],
 real:Array.from({length:k},(_,m)=>[[1,0.25*m,0],[0.5,-0.125,1e-3*(m+1)]]),imag:Array.from({length:k},()=>[[0,0,0],[-2e-3,0,0]])});
const METHOD='central_difference 1 nm electric-l2-assignment-v1';
const run=(job,k=3,extra={})=>({job,completedAt:'2026-11-22T01:00:00.000Z',settings:N.opticalSettings(1550,30,k),input:input(),
 effective_index:Array.from({length:k},(_,m)=>2.9-0.17*m),field:field(k),origin:'local',serverVersion:'0.0.0',...extra});
const view={mode:0,component:'magnitude',window:'Core region'};
const write=runs=>N.sessionText(input(),runs,runs[0].job,[runs[0].job,runs.at(-1).job],view);
// the summary blocks of an engine run with results.group_index
const summary=(values,reasons)=>({group_index:{unit:'1',values:[values]},
 group_index_method:{method:'central_difference',wavelength_step:{value:1e-9,unit:'m'},tracking:'electric-l2-assignment-v1',reasons}});

test('S-a: Also compute group index off gives the optical-shapes-v8 document, byte for byte',()=>{
 const v8=fixture('optical-document-template-v7.json');          // v8 with 2 modes is the v7 document (M4-a)
 for(const s of [state(),state({groupIndex:false}),state({groupIndex:undefined})])assert.equal(JSON.stringify(O.opticalDocument(s,setup())),v8);
 // a session of runs without n_g keeps the M4 rules: version 7 where version 7 holds it
 assert.equal(JSON.parse(write([run('00000001',2)])).version,7);
});
test('S-b: on, the document is the v8 document with results.group_index only, and the adapter and settings are unchanged',()=>{
 const off=O.opticalDocument(state(),setup()),on=O.opticalDocument(state({groupIndex:true}),setup());
 assert.deepEqual(on,{...off,results:{save_fields:true,plots:false,group_index:{wavelength_step:'1 nm'}}});
 assert.deepEqual(Object.keys(on.results),['save_fields','plots','group_index']);
 assert.equal(O.GROUP_INDEX_STEP,'1 nm');
 assert.deepEqual(N.opticalSettings(1550,30,2),N.opticalSettings(1550,30,2));
 assert.equal(N.OPTICAL_ADAPTER,'optical-shapes-v8');
});
test('S-b rule: a run\'s document is rebuilt from its settings and group_index_method',()=>{
 const r=N.validateRun(run('00000002',3,N.engineGroupIndex(summary([4.2,null,3.9]),3)));
 assert.equal(r.group_index_method,METHOD);
 const s=r.settings,fromSettings=state({wavelength:parseFloat(s.vacuum_wavelength),coreMesh:parseFloat(s.core_element_size),modeCount:s.mode_count});
 const rebuilt=O.withGroupIndex(O.opticalDocument(fromSettings,setup()),O.groupIndexStep(r.group_index_method));
 assert.equal(JSON.stringify(rebuilt),JSON.stringify(O.opticalDocument(state({modeCount:3,groupIndex:true}),setup())));
 assert.equal(O.groupIndexStep('central_difference 1 nm'),null);assert.equal(O.groupIndexStep(undefined),null);
});
test('engine values: group_index (k numbers or null) and its method string from the summary; anything else is not taken',()=>{
 assert.deepEqual(N.engineGroupIndex(summary([4.2,null,3.9],[null,'r',null]),3),{group_index:[4.2,null,3.9],group_index_method:METHOD});
 assert.deepEqual(N.engineGroupIndexReasons(summary([4.2,null,3.9],[null,'r',null]),3),[null,'r',null]);
 assert.deepEqual(N.engineGroupIndex({},3),{});
 assert.deepEqual(N.engineGroupIndex({group_index:{unit:'1',values:[[4,4,4]]}},3),{},'a sweep-style group_index without the method');
 assert.deepEqual(N.engineGroupIndex(summary([4.2,3.9],[]),3),{},'k entries');
 const bad=summary([4.2,4.1,3.9]);bad.group_index_method.tracking='x y';assert.deepEqual(N.engineGroupIndex(bad,3),{});
 const step=summary([4.2,4.1,3.9]);step.group_index_method.wavelength_step={value:2e-9,unit:'m'};
 assert.equal(N.engineGroupIndex(step,3).group_index_method,'central_difference 2 nm electric-l2-assignment-v1');
 assert.equal(N.engineGroupIndexReasons(summary([1],['a','b']),1),null);
});
test('S-c: a version 9 session with n_g (one null) round-trips bit for bit and keeps both slots',()=>{
 const runs=[N.validateRun(run('00000003',3,N.engineGroupIndex(summary([4.2,null,3.9]),3))),N.validateRun(run('00000004',2))];
 const text=write(runs),doc=JSON.parse(text);
 assert.equal(doc.version,9);
 assert.deepEqual(doc.runs[0].group_index,[4.2,null,3.9]);assert.equal(doc.runs[0].group_index_method,METHOD);
 assert.equal(doc.runs[1].group_index,undefined);assert.equal(doc.runs[1].group_index_method,undefined);
 const read=N.parseSession(text);
 assert.deepEqual(read.runs[0].group_index,[4.2,null,3.9]);assert.equal(read.runs[0].group_index_method,METHOD);
 // reading marks the runs imported (as for every file); from then on save → load → save is identical
 const again=N.sessionText(read.input,read.runs,read.selected,read.comparison,read.view),read2=N.parseSession(again);
 assert.equal(JSON.stringify(JSON.parse(again).runs.map(({origin,digest,...r})=>r)),JSON.stringify(doc.runs.map(({origin,digest,...r})=>r)));
 assert.equal(N.sessionText(read2.input,read2.runs,read2.selected,read2.comparison,read2.view),again);
 // the reasons are not written: a file of a run with them is the same file
 const withReasons={...runs[0],groupIndexReasons:[null,'vacuum_wavelength 1.549 um: weak overlap',null]};
 assert.equal(write([withReasons,runs[1]]),text);
});
test('S-d: "—" with its help when the run did not compute n_g, live with the engine reason, and after a reload',()=>{
 const off=N.validateRun(run('00000005',2));
 assert.deepEqual(M.groupIndexCell(off,0),{text:'—',value:null,title:'Turn on Also compute group index in Study or Optical modes'});
 const on=N.validateRun(run('00000006',3,N.engineGroupIndex(summary([4.21234,null,3.9]),3)));
 assert.deepEqual(M.groupIndexCell(on,0),{text:'4.2123',value:4.21234,title:M.groupIndexHelp('1 nm')});
 assert.match(M.groupIndexCell(on,0).title,/central difference over λ0 ± 1 nm \(3 solves\)/);
 // after a reload (a run read from a file): the reason is not kept
 assert.deepEqual(M.groupIndexCell(on,1),{text:'—',value:null,title:'Not matched at λ0 ± 1 nm; the reason is not kept in session files'});
 // live: the engine's reason
 const live={...on,groupIndexReasons:[null,'vacuum_wavelength 1.55 um: near-degenerate with another requested mode within n_eff tolerance 1e-05',null]};
 assert.equal(M.groupIndexCell(live,1).title,'Not matched: vacuum_wavelength 1.55 um: near-degenerate with another requested mode within n_eff tolerance 1e-05');
});
test('S-e: Compare n_g of a unit: the mode\'s, the mean of a pair, "—" when a member has none',()=>{
 const on=N.validateRun(run('00000007',3,N.engineGroupIndex(summary([4.2,4.4,null]),3)));
 assert.deepEqual(H.unitGroupIndex(on,[0]),M.groupIndexCell(on,0));
 const pair=H.unitGroupIndex(on,[0,1]);assert.equal(pair.text,'mean 4.3000');assert.ok(Math.abs(pair.value-4.3)<1e-12);
 assert.equal(H.unitGroupIndex(on,[1,2]).text,'—');assert.equal(H.unitGroupIndex(on,null).text,'—');
 assert.equal(H.unitGroupIndex(N.validateRun(run('00000008',2)),[0]).title,'Turn on Also compute group index in Study or Optical modes');
});
test('S-f: the multiphysics modes table has no n_g column',()=>{
 const src=fs.readFileSync(path.join(__dirname,STATIC,'workspace-multiphysics-view.mjs'),'utf8');
 assert.ok(!/n_g|group_?index/i.test(src));
});
test('review: the box is part of the study signature; a run with n_g is of the inputs only with the box on',async()=>{
 const W=await import(STATIC+'workspace-workflow.mjs');
 const plain=N.validateRun(run('00000009',2)),withNg=N.validateRun(run('00000010',2,N.engineGroupIndex(summary([4.2,4.1]),2)));
 assert.equal(N.studySignature(input(),2),JSON.stringify(input()),'off: the signature of earlier Studios');
 assert.equal(N.studySignature(input(),2,true),JSON.stringify(input())+'\ngroup index');
 assert.equal(plain.signature,N.studySignature(input(),2));assert.equal(withNg.signature,N.studySignature(input(),2,true));
 const own=(runs,g)=>W.opticalFreshness(input(),runs,runs.at(-1),2,g);
 assert.deepEqual([own([plain],false).state,own([plain],true).state].map(x=>x===own([plain],false).state),[true,false],'ticking the box makes a run without n_g another study');
 assert.equal(own([withNg],true).state,own([plain],false).state);
 assert.equal(O.groupIndexStep,M.groupIndexStep,'one parser');
});
