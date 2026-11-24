// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
// Search near n_eff for closed-window runs, the page and the session (slice C2). Pre-registered:
// K9 (session version 11 only with a closed targeted run kept, reopened with the same targets and
// values; a version 10 reader refuses it by name; files without one keep their version, byte for
// byte against main 13f07f4: studio_session_fixtures/sessions-rewritten-13f07f4.json, made by
// closed_sessions.mjs from that commit's static folder), K10 (a changed or removed target makes a
// run needed; "No need to run" only for an equal target), K12 (the words) and K13 (A1: the template
// @2.46 with 4 modes lists 3, "Found 3 of 4 modes near n_eff 2.46, above n = 1.45", saved as
// version 11). The core-mode note on engine fields is in tests/simcase/test_studio_closed_target.py.
const test=require('node:test');const assert=require('node:assert/strict');
const fs=require('node:fs');const path=require('node:path');
const STATIC='../../packages/simcase/src/simcase/studio/static/';
const FIXTURES=path.join(__dirname,'studio_session_fixtures');
let N,P,C,W,M,X,J,G,S;
test.before(async()=>{
 N=await import(STATIC+'workspace-notebook.mjs');P=await import(STATIC+'workspace-project.mjs');C=await import(STATIC+'workspace-closed-target.mjs');
 W=await import(STATIC+'workspace-workflow.mjs');M=await import(STATIC+'workspace-modes.mjs');X=await import(STATIC+'workspace-compare.mjs');
 J=await import(STATIC+'workspace-job.mjs');S=await import(STATIC+'workspace-multiphysics-session.mjs');G=await import('./studio_session_fixtures/closed_sessions.mjs');
});
const setup=()=>({materials:{Core:'Silicon',Oxide:'Silica',Heater:''},temperature:293.15,cooling:'',fixed:'',terminal:''});
const SUBSTRATE={name:'Substrate',type:'rect',material:'Silicon',x:-1500,y:-1200,w:3000,h:700};
const input=(shapes)=>P.snapshot({width:500,voltage:1,electric:false,heat:false,structure:false,optics:true,wavelength:1550,coreMesh:30,...(shapes?{shapes}:{})},setup());
const field=k=>({node_coordinates:[[0,0],[1e-6,0],[0,1e-6],[1e-6,1e-6]],triangles:[[0,1,2],[1,3,2]],
 real:Array.from({length:k},(_,m)=>[[1,0.25*m,-0],[0.5,-0.125,1e-3*(m+1)]]),imag:Array.from({length:k},(_,m)=>[[0,1e-9*m,0],[-2e-3,0,0]])});
// the template @2.46 with 4 modes (K13, engine values measured on 13f07f4): the 4th is below the cladding
const TEMPLATE_4=[2.44257822,1.76989777,1.49297336,1.39191472];
const targetedRun=(job,re,asked,t,extra={})=>({job,completedAt:'2026-11-24T01:00:00.000Z',settings:N.closedTargetSettings(N.opticalSettings(1550,30,asked),t),input:input(),
 effective_index:re,field:field(re.length),origin:'local',serverVersion:'0.0.0',te_polarization_fraction:re.map(()=>0.9),effective_area:re.map(()=>1e-13),...extra});
const plainRun=(job,k=2)=>({job,completedAt:'2026-11-24T01:00:00.000Z',settings:N.opticalSettings(1550,30,k),input:input(),effective_index:[2.44257822,1.76989777].slice(0,k),field:field(k),origin:'local',serverVersion:'0.0.0'});
const view={mode:0,component:'magnitude',window:'Core region'};
const write=(inp,runs)=>N.sessionText(inp,runs,runs[0].job,[runs[0].job,runs.at(-1).job],view);

test('K13 (A1): a closed targeted result keeps the modes above 1.45, with their samples and values; the words',()=>{
 const result={vector_fields:[{real:TEMPLATE_4.map((_,m)=>[m]),imag:TEMPLATE_4.map((_,m)=>[-m])}],summary:{}};
 const kept=C.closedResultValues(result,TEMPLATE_4,2.46);
 assert.deepEqual(kept.keep,[0,1,2]);assert.deepEqual(kept.re,TEMPLATE_4.slice(0,3));
 assert.deepEqual(kept.data.vector_fields[0].real,[[0],[1],[2]]);assert.deepEqual(kept.data.vector_fields[0].imag,[[-0],[-1],[-2]]);
 assert.throws(()=>C.closedResultValues(result,[1.4,1.3],2.46),{message:'No mode above n = 1.45 was found near n_eff 2.46. Move Search near n_eff.'});
 assert.equal(C.closedFoundText(3,4,2.46),'Found 3 of 4 modes near n_eff 2.46, above n = 1.45');
 assert.equal(C.closedFoundText(2,2,2.46),'Found 2 of 2 modes near n_eff 2.46, above n = 1.45');
 assert.equal(C.leftOutText(3,4),'1 mode at or below n = 1.45 was left out.');assert.equal(C.leftOutText(2,4),'2 modes at or below n = 1.45 were left out.');assert.equal(C.leftOutText(4,4),'');
 // the run of these 3 modes is a valid run of 4 asked; the 1.39 mode is not accepted on one
 const run=N.validateRun(targetedRun('0000000a',kept.re,4,2.46));
 assert.deepEqual(run.effective_index,TEMPLATE_4.slice(0,3));assert.equal(N.runModeCount(run),4);assert.equal(N.runSearchTarget(run),2.46);
 assert.throws(()=>N.validateRun(targetedRun('0000000a',TEMPLATE_4,4,2.46)),{message:'This run: a closed-window search lists only modes above n = 1.45.'});
 // saved as version 11
 assert.equal(JSON.parse(write(input(),[run])).version,11);
});

test('K12: the words: the shortcut, the edge note (C0), the plan, the run tag and the help',()=>{
 assert.equal(C.shortcutText(2.46),'Search near 2.46 · 4 modes');assert.equal(C.SHORTCUT_MODE_COUNT,4);
 assert.equal(M.edgeNoteText(0,{shape:'Substrate',share:0.934}),'Mode 1 is mostly in Substrate (93 % of |E|²), which touches the window edge; its n_eff depends on the closed window. Use Open boundary to leave that edge open.');
 assert.equal(M.coreNoteText(1,{shape:'Core',share:0.644}),'Mode 2 is the core mode: 64 % of |E|² is in Core, which does not touch the window edge.');
 // no text promises that more modes reach the core mode (Q8)
 for(const name of ['workspace-app.mjs','workspace-modes.mjs','workspace-closed-target.mjs','workspace-workflow.mjs'])
  assert.ok(!fs.readFileSync(path.join(__dirname,STATIC,name),'utf8').includes('reach the core mode'),name);
 assert.equal(W.runPlanText({searchTarget:2.46}),'Closed window · near n_eff 2.46');
 assert.equal(W.runPlanText({searchTarget:2.46,groupIndex:true}),'Closed window · near n_eff 2.46 · group index on (3 solves)');
 assert.equal(W.runPlanText({}),'Closed window');assert.equal(W.runPlanText({open:true,searches:2,searchTarget:2.46}),'Open boundary · 2 searches');
 assert.equal(W.nextRunText(input(),4,false,null,2.46),'Next run uses '+W.opticalInputParts(input()).join(' · ')+' · Modes to find 4 · search near 2.46');
 const run=N.validateRun(targetedRun('0000000a',[2.48623178,2.43931663],2,2.46));
 assert.equal(X.boundaryTag(run),'closed near 2.46');assert.ok(X.runHeading(run,1).startsWith('Run 1 · closed near 2.46 · '),X.runHeading(run,1));
 assert.equal(X.boundaryTag(N.validateRun(plainRun('0000000b'))),'closed');
 assert.equal(C.CLOSED_SEARCH_HELP,'Off: the modes of highest n_eff above 1.45. On: the modes nearest this index, listed by n_eff, highest first; modes at or below 1.45 are left out. Closed and open values differ: refine the mesh before a close comparison.');
 assert.equal(C.closedSearchNotice(2.46),'Search near n_eff 2.460 in the closed window: the next run returns the modes nearest it.');
 assert.equal(C.closedSearchNotice(null),'Search near n_eff off: the next run returns the modes of highest n_eff.');
});

test('the core-mode note: a closed targeted run with an edge-touching shape names a mode mostly in a shape away from the edge',()=>{
 // two triangles, one in the core and one in the substrate; mode 1 in the substrate, mode 2 in the core
 const shapes=[{name:'Core',type:'rect',material:'Silicon',x:-250,y:0,w:500,h:220},SUBSTRATE];
 const f={node_coordinates:[[-2e-7,1e-8],[2e-7,1e-8],[0,2e-7],[-1.4e-6,-1.1e-6],[1.4e-6,-1.1e-6],[0,-6e-7]],triangles:[[0,1,2],[3,4,5]],
  real:[[[0,0,0],[1,0,0]],[[1,0,0],[0.1,0,0]]],imag:[[[0,0,0],[0,0,0]],[[0,0,0],[0,0,0]]]};
 const record=extra=>N.validateRun({...targetedRun('0000000c',[2.48623178,2.43931663],2,2.46),input:input(shapes),field:f,...extra});
 const run=record();
 assert.deepEqual(M.coreNotes(run).map(n=>n.mode),[1]);assert.ok(M.coreNotes(run)[0].text.startsWith('Mode 2 is the core mode: '),M.coreNotes(run)[0].text);
 // none for an untargeted run, nor without an edge-touching shape
 assert.deepEqual(M.coreNotes(N.validateRun({...plainRun('0000000d'),input:input(shapes),field:f,effective_index:[3.4,3.39]})),[]);
 assert.deepEqual(M.coreNotes(N.validateRun({...targetedRun('0000000e',[2.44,1.77],2,2.46)})),[]);
});

test('K9: version 11 only with a closed targeted run kept; it reopens with the same targets and values',()=>{
 const a=N.validateRun(targetedRun('0000000a',TEMPLATE_4.slice(0,3),4,2.46)),b=N.validateRun(targetedRun('0000000b',[2.84469192],1,2.85)),c=N.validateRun(plainRun('0000000c'));
 const text=write(input(),[a,b,c]),doc=JSON.parse(text);
 assert.equal(doc.version,11);assert.deepEqual(doc.runs.map(r=>r.settings.adapter),['optical-shapes-v10','optical-shapes-v10','optical-shapes-v8']);
 assert.deepEqual(Object.keys(doc.runs[0].settings),['adapter','domain','boundary','mode_count','search_target','solver_version','vacuum_wavelength','core_element_size']);
 const back=N.parseSession(text);
 assert.deepEqual(back.runs.map(N.runSearchTarget),[2.46,2.85,null]);
 assert.deepEqual(back.runs.map(r=>r.effective_index),[a.effective_index,b.effective_index,c.effective_index]);
 assert.deepEqual(back.runs.map(r=>r.signature),[a.signature,b.signature,c.signature]);
 // written again: the same bytes but the origin (a run read from a file is "imported"), and then stable
 const again=N.sessionText(back.input,back.runs,back.selected,back.comparison,back.view),twice=N.parseSession(again);
 assert.deepEqual(JSON.parse(again).runs.map(r=>r.origin),['imported','imported','imported']);
 assert.deepEqual(JSON.parse(again).runs.map(r=>r.settings),doc.runs.map(r=>r.settings));
 assert.equal(N.sessionText(twice.input,twice.runs,twice.selected,twice.comparison,twice.view),again);
 // without the targeted runs the session is not version 11
 assert.equal(JSON.parse(write(input(),[c])).version,7);
 // a version 11 file is refused by a version 10 reader: Studio 13f07f4 gives newerVersionText(11, 10)
 assert.equal(N.newerVersionText(11,10),'This session file is version 11, newer than this Studio reads (versions 6–10). Open it in a newer Studio.');
 // the reader: a version 10 file does not hold optical-shapes-v10; a version 11 run's target is checked
 const ten=JSON.parse(text);ten.version=10;for(const r of ten.runs){delete r.digest;r.digest=S.recordDigest(r);}
 assert.throws(()=>N.parseSession(S.sessionJson(ten)),{message:'Run 1: unsupported run settings (a version 10 file writes optical-shapes-v8 or optical-shapes-v9).'});
 // a run's search target is checked as the page's field is: 3 decimals, above 1.45, below n_max
 for(const [t,ok] of [[1.45,false],[3.4777,false],['2.46',false],[2.4605,false],[1.451,true]]){
  const record={...a,settings:{...a.settings,search_target:t}};
  if(ok)assert.equal(N.runSearchTarget(N.validateRun(record)),t);
  else assert.throws(()=>N.validateRun(record),/^Error: This run: invalid search target\. Search near n_eff must lie between 1\.45 and 3\.4777 \(3 decimals\)\.$/,String(t));
 }
});

test('K9 and K1: files without a closed targeted run keep their version, byte for byte against main 13f07f4',()=>{
 const golden=JSON.parse(fs.readFileSync(path.join(FIXTURES,'sessions-rewritten-13f07f4.json'),'utf8'));
 const now=G.rewrite(N,FIXTURES,P);
 assert.deepEqual(Object.keys(now),Object.keys(golden));
 for(const [name,text] of Object.entries(golden)){assert.equal(now[name],text,name);assert.notEqual(JSON.parse(text).version,11);}
 assert.deepEqual(Object.values(golden).map(t=>JSON.parse(t).version),[9,7,7,7,10,10]);
});

test('K10: a changed or removed target makes a run needed; "No need to run" only for an equal target',()=>{
 const inp=input([{name:'Core',type:'rect',material:'Silicon',x:-250,y:0,w:500,h:220},SUBSTRATE]);
 const run=N.validateRun({...targetedRun('0000000a',[2.52870542,2.48623178,2.43931663,2.4005893],4,2.46),input:inp});
 const runs=[run],fresh=t=>W.opticalFreshness(inp,runs,null,4,false,null,t);
 assert.equal(fresh(2.46).state,'current');
 for(const t of [2.47,2.459,null])assert.notEqual(fresh(t).state,'current',String(t));
 // the signature: the target written only when on, never with an open boundary
 assert.equal(N.studySignature(inp,4,false,null,null),N.studySignature(inp,4));
 assert.equal(N.studySignature(inp,4,false,null,2.46),N.studySignature(inp,4)+'\nnear 2.46');
 assert.equal(N.studySignature(inp,4,false,{open_edges:['left'],target:'2.460'},2.46),N.studySignature(inp,4,false,{open_edges:['left'],target:'2.460'}));
 assert.equal(run.signature,N.studySignature(inp,4,false,null,2.46));
 // the workflow step: Results is current only for the equal target
 const step=t=>W.opticalWorkflow({input:inp,runs,modeCount:4,searchTarget:t});
 assert.notDeepEqual(step(2.46),step(null));
});

test('a pending job keeps its closed target, never with an open boundary',()=>{
 const base={version:1,job:'0000000a',serverInstance:'a'.repeat(32),serverVersion:'0.0.0',startedAt:'2026-11-24T01:00:00.000Z',revision:0,input:input(),modeCount:4};
 assert.equal(J.validatePending({...base,searchTarget:2.46}).searchTarget,2.46);
 assert.equal(J.validatePending(base).searchTarget,undefined);
 for(const t of [1.45,'2.46',4])assert.throws(()=>J.validatePending({...base,searchTarget:t}),{message:'Invalid pending search target.'});
});

test('Use this run\'s inputs restores the box and the target of a closed targeted run (coordinator\'s answer (b))',()=>{
 const app=fs.readFileSync(path.join(__dirname,STATIC,'workspace-app.mjs'),'utf8');
 const body=app.slice(app.indexOf('function useRunInputs(run){'),app.indexOf('const runNumberTitle='));
 // the run's target (or off) after the inputs file is restored, named in the change list
 assert.ok(body.includes('const runTarget=runSearchTarget(run)'),body);
 assert.ok(body.includes('restoreEdit(doc,null);state.searchTarget=runTarget;'),body);
 assert.ok(body.includes("`Search near n_eff ${priorTarget==null?'off':shortTarget(priorTarget)} → ${runTarget==null?'off':shortTarget(runTarget)}`"),body);
 // the page's signature and document read the same target
 assert.ok(app.includes('const signature = () => studySignature(current(), state.modeCount, state.groupIndex, pmlNow(), closedTargetNow());'));
 assert.ok(app.includes('const opticalDocument=()=>buildOpticalDocument({...state,searchTarget:closedTargetNow()},setup);'));
 // the box and the target are not saved with the model inputs (this batch): inputsFile has no target
 assert.ok(app.includes("const inputsFile = () => {keepTargetInRange(); return withStudy(current(), {modeCount: state.modeCount, groupIndex: state.groupIndex, openBoundary: state.openBoundary});};"));
});
