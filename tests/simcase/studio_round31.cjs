// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
// Round 31 (agent proxy round 31 on main 6b1455b): K1, the Library restore box names one way back;
// K2, the question before an open-boundary run whose group index was carried over; K3, the Compare
// pickers' visible labels Run A and Run B.
// Plain text comparison only: no RegExp is built from a dynamic string.
const test=require('node:test');const assert=require('node:assert/strict');
const fs=require('node:fs');const path=require('node:path');
const STATIC='../../packages/simcase/src/simcase/studio/static/';
const read=name=>fs.readFileSync(path.join(__dirname,STATIC,name),'utf8');
const when=t=>t;

test('K1: the box note and the newest detail name no second way back',async()=>{
 const A=await import(STATIC+'workspace-applications.mjs');
 assert.equal(A.RESUME_NOTE,'Restore brings back completed runs kept in this browser, without recomputing.');
 const base={runs:1,model:'Optical waveguide',names:['Run 1'],savedAt:'T',file:'heater-study.json'};
 assert.equal(A.resumeDetail({...base,fileCurrent:true,fileSavedAt:'F'},when),'Kept in this browser T · same as heater-study.json, saved F');
 assert.equal(A.resumeDetail({...base,fileCurrent:true},when),'Kept in this browser T · same as heater-study.json as opened');
 // no string of the newest offer (1–6), single or pair, names Open file…
 const pair=c=>({model:'Heated silicon waveguide',runs:1,savedAt:'T',fileCurrent:c});
 for(const file of [null,'heater-study.json'])for(const fileCurrent of [true,false,null])for(const fileSavedAt of ['F',undefined])for(const p of [undefined,pair(true),pair(false)]){
  const d=A.resumeDetail({...base,file,fileCurrent,fileSavedAt,pair:p},when);assert.ok(!d.includes('Open file'),d);
  const c=A.resumeChoices({...base,file,fileCurrent,fileSavedAt,pair:p},[],when);assert.ok(!c.newest.detail.includes('Open file'),c.newest.detail);
 }
 // the box keeps its structure: the earlier-copies and #resume-other details are unchanged
 const lib=read('workspace-applications.mjs');
 assert.ok(!lib.includes('Open file… at the top opens a project file instead.'));
 const older={runs:2,model:'Optical waveguide',names:['Run 1','Run 2'],savedAt:'8:30',file:'both-models.json',fileCurrent:true,fileSavedAt:'8:31'};
 const box=A.resumeChoices({runs:1,model:'Heated silicon waveguide',names:['Run 1'],savedAt:'8:32'},[{...older,index:0}],when);
 assert.equal(box.other.detail,'Older · kept in this browser 8:30 · same as both-models.json, saved 8:31 · Open file… gives the same runs');
});

test('K2: the question\'s title, words and buttons, with the estimate of the plan line',async()=>{
 const W=await import(STATIC+'workspace-workflow.mjs');
 assert.equal(W.GROUP_CARRY_TITLE,'Group index is still on');
 assert.deepEqual(W.GROUP_CARRY_BUTTONS,['Run with group index','Turn off group index and run','Cancel']);
 // the estimate is groupIndexEstimate's, in aboutText's words (the plan line's "about N min")
 const kinds={isOpen:r=>!!r.open,hasGroup:r=>!!r.group};
 const open68={open:true,duration:68000},est=W.groupIndexEstimate([open68],{open:true},kinds);
 assert.equal(est,204000);
 assert.equal(W.groupCarryText(est),`This open-boundary run with group index takes about ${W.aboutText(est)} (3 solves).`);
 assert.equal(W.groupCarryText(est),'This open-boundary run with group index takes about 3 min (3 solves).');
 assert.equal(W.groupCarryText(20000),'This open-boundary run with group index takes about 20 s (3 solves).');
 assert.ok(W.runPlanText({open:true,groupIndex:true,estimate:est}).endsWith(' · about 3 min'));
 // no estimate (no timed open run in this tab)
 for(const none of [null,undefined,NaN])assert.equal(W.groupCarryText(none),'This open-boundary run with group index takes about three times as long (3 solves).');
});

test('K2: asked only when group index was on before the last completed run, for an open run',async()=>{
 const W=await import(STATIC+'workspace-workflow.mjs');
 const open={open:true,groupIndex:true,multiphysics:false};
 // no completed run in this tab: not carried over
 {const m=W.groupCarryMemory();m.seen(true);assert.equal(m.due(open),false);}
 // on, a run started and completed with it on: carried over
 const carried=()=>{const m=W.groupCarryMemory();m.seen(true);m.started(true);m.seen(true);m.completed();m.seen(true);return m;};
 assert.equal(carried().due(open),true);
 // asked again after another run completed with it on (it was still on before that run)
 {const m=carried();m.started(true);m.completed();assert.equal(m.due(open),true);}
 // not for a closed window, the multiphysics model, or group index off
 assert.equal(carried().due({...open,open:false}),false);
 assert.equal(carried().due({...open,multiphysics:true}),false);
 assert.equal(carried().due({...open,groupIndex:false}),false);
 // turned on since the last completed run: off then on again
 {const m=carried();m.seen(false);m.seen(true);assert.equal(m.due(open),false);}
 // the last completed run was without group index, then it was turned on
 {const m=W.groupCarryMemory();m.seen(false);m.started(false);m.completed();m.seen(true);assert.equal(m.due(open),false);}
 // turned off and on again while the run was computing: on since, not before
 {const m=W.groupCarryMemory();m.seen(true);m.started(true);m.seen(false);m.seen(true);m.completed();assert.equal(m.due(open),false);}
 // a run that did not complete (failed, or Cancel of the question) changes nothing
 {const m=carried();m.started(true);assert.equal(m.due(open),true);}
 {const m=W.groupCarryMemory();m.seen(true);m.started(true);assert.equal(m.due(open),false);}
 // a run turned off then completed: not carried
 {const m=carried();m.seen(false);m.started(false);m.completed();m.seen(true);assert.equal(m.due(open),false);}
});

test('K2: the dialog follows the slab question: modal, named, described, focus on its first button',()=>{
 const app=read('workspace-app.mjs');
 assert.ok(app.includes("carryDialog.id='group-carry-question';carryDialog.setAttribute('aria-labelledby','group-carry-title');carryDialog.setAttribute('aria-describedby','group-carry-text');"));
 assert.ok(app.includes('<h2 id="group-carry-title">\'+GROUP_CARRY_TITLE+\'</h2><p id="group-carry-text"></p><div class="leave-actions"><button type="button" id="group-carry-run" class="primary"></button> <button type="button" id="group-carry-off"></button> <button type="button" id="group-carry-cancel"></button></div>'));
 assert.ok(app.includes("carryDialog.showModal();$('group-carry-run').focus();"));
 assert.ok(app.includes("carryDialog.oncancel=event=>{event.preventDefault();carryAnswer?.(null);};"));
 assert.ok(app.includes("restoreDialogFocus(opener);resolve(value);"));
 // Run study waits while either question is open
 assert.ok(app.includes("if(solverBusy||pendingJob||opticalBlock()||retentionBlock()||slabDialog.open||carryDialog.open)return;"));
 // the memory: seen on every render, started with each new optical run, completed with its result
 assert.ok(app.includes('function render(){groupCarry.seen(state.groupIndex);'));
 assert.equal(app.split('groupCarry.started(state.groupIndex);').length-1,1);
 assert.ok(app.includes('runs=next;solverRun=runs.find(run=>run.job===completed.job);groupCarry.completed();'));
});

test('K2: never with the slab question; Turn off and run is the checkbox\'s own change, then Run',async()=>{
 const app=read('workspace-app.mjs'),O=await import(STATIC+'workspace-open-run.mjs');
 // the slab question needs a closed window (no open boundary), the group question settings.pml (an
 // open boundary with an open edge): the second is asked only when the first is not
 assert.ok(app.includes("const edgeWarning=()=>isOptical()&&applicationChosen()&&!state.openBoundary&&"));
 assert.equal(O.signaturePml(null,[]),null);
 // the group question first (an open run), then the slab question (a closed window): at most one
 const ask="$('run-optical').onclick=async()=>{\n if(solverBusy||pendingJob||opticalBlock()||retentionBlock()||slabDialog.open||carryDialog.open)return;\n try{rejectInvalidInput();}catch(e){notice(e.message);return;}\n // round 31 (K2): an open run only (pmlNow), so never with the slab question below (a closed window)\n if(groupCarry.due({open:!!pmlNow(),groupIndex:state.groupIndex,multiphysics:multiView.active()})){\n  const answer=await askGroupCarry();\n  if(!answer)return;\n  if(answer==='off')turnOffGroupIndex();\n  if(solverBusy||pendingJob||opticalBlock()||retentionBlock())return;\n }\n const risk=edgeWarning(),key=slabKeyNow();\n if(slabQuestion.due(risk,key)){";
 assert.equal(app.split(ask).length-1,1);
 // after Turn off and run, the run is Run study's own: the same code from here on
 const at=app.indexOf(ask);assert.ok(app.indexOf('doc=opticalDocument();groupCarry.started(state.groupIndex);solverBusy=true;',at)>at);
 // the open boundary of the run is pmlNow's: null without an open boundary, as the slab question needs
 assert.ok(app.includes('const pmlNow = () => {if (!isOptical()) return null; keepTargetInRange(); return signaturePml(state.openBoundary, state.shapes);};'));
 // unticking the box and Turn off group index make the same change
 assert.ok(app.includes("box.onchange=e=>{state.groupIndex=e.target.checked;render();notice(groupIndexNotice(state.groupIndex));};"));
 assert.ok(app.includes("function turnOffGroupIndex(){if(state.groupIndex!==true)return;state.groupIndex=false;render();notice(groupIndexNotice(false));}"));
 // the question's text from the plan line's own estimate (an open run)
 assert.ok(app.includes("groupCarryText(groupIndexEstimate(runs,{open:true},{isOpen:isOpenRun,hasGroup:hasGroupIndex}))"));
});
