// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
// Round 28 (agent-proxy pilot, build 7008bee3): G2, the Compute label beside Run study names Modes to
// find; G3, the slab question shows the run that already has the shortcut's results instead of
// running a copy; G4, the Library card's sentence agrees with browser recovery.
// Plain text comparison only: no RegExp is built from a dynamic string.
const test=require('node:test');const assert=require('node:assert/strict');
const fs=require('node:fs');const path=require('node:path');
const STATIC='../../packages/simcase/src/simcase/studio/static/';
const read=name=>fs.readFileSync(path.join(__dirname,STATIC,name),'utf8');

test('G2: the Compute label names the mode count, as the job label does',async()=>{
 const W=await import(STATIC+'workspace-workflow.mjs');
 assert.equal(W.runPlanText({open:true,searches:2,groupIndex:true,modeCount:4,estimate:300000}),'Open boundary · 4 modes · 2 searches · group index on (3 solves) · about 5 min');
 assert.equal(W.runPlanText({modeCount:2}),'Closed window · 2 modes');
 assert.equal(W.runPlanText({searchTarget:2.46,modeCount:4}),'Closed window · near n_eff 2.46 · 4 modes');
 // one mode reads singular; the default is Modes to find 2
 assert.equal(W.runPlanText({modeCount:1}),'Closed window · 1 mode');
 assert.equal(W.runPlanText({}),'Closed window · 2 modes');
 // the time parts stay last
 assert.equal(W.runPlanText({modeCount:4,last:12400}),'Closed window · 4 modes · last such run 0:12');
 assert.equal(W.runPlanText({open:true,modeCount:2,pmlCheck:true,last:220000}),'Open boundary · 2 modes · 1 search · PML check on (3 solves) · last such run 3:40');
 // the page passes Modes to find in the plan
 const app=read('workspace-app.mjs');
 assert.ok(app.includes('pmlCheck:ui.pmlCheck===true&&hasOpenEdge(state.openBoundary),modeCount:state.modeCount,searchTarget:open?null:closedTargetNow()};'));
});

// the T18 strip on a substrate, as studio_round27.cjs builds it
const input=model=>({model,setup:{materials:{Oxide:'Silica'}}});
test('G3: the run that already has the shortcut\'s results, by the panel\'s No need to run rule',async()=>{
 const W=await import(STATIC+'workspace-workflow.mjs'),N=await import(STATIC+'workspace-notebook.mjs');
 const now=input({wavelength:1550,coreMesh:30,shapes:[{type:'rect',name:'Core'}]}),other=input({wavelength:1310,coreMesh:30,shapes:[{type:'rect',name:'Core'}]});
 const run=(number,inp,modes,group,t)=>({number,signature:N.studySignature(inp,modes,group,null,t)});
 const highest=run(5,now,2,false,null),near=run(6,now,4,false,2.46),nearOther=run(7,other,4,false,2.46),nearTwo=run(8,now,2,false,2.46),nearGroup=run(9,now,4,true,2.46);
 // a run of the current inputs with Nearest to n_eff 2.46 and Modes to find 4: the newest such run
 assert.equal(W.shortcutRun([highest,near,nearOther,nearTwo],now,false,2.46),near);
 assert.equal(W.shortcutRun([near,run(10,now,4,false,2.46)],now,false,2.46).number,10);
 // other inputs, another mode count, another target or another group-index state: none
 assert.equal(W.shortcutRun([highest,nearOther,nearTwo],now,false,2.46),null);
 assert.equal(W.shortcutRun([near],now,false,2.5),null);
 assert.equal(W.shortcutRun([near],now,true,2.46),null);assert.equal(W.shortcutRun([nearGroup],now,true,2.46),nearGroup);
 assert.equal(W.shortcutRun([],now,false,2.46),null);
});

test('G3: the question\'s first button reads "… · show Run N" only with such a run',async()=>{
 const C=await import(STATIC+'workspace-closed-target.mjs');
 assert.deepEqual(C.slabQuestionButtons(2.46,6),['Set search near 2.46 · 4 modes · show Run 6','Run as set','Cancel']);
 assert.deepEqual(C.slabQuestionButtons(2.46,6)[0],C.shortcutText(2.46)+' · show Run 6');
 // without one: exactly as in round 27
 assert.deepEqual(C.slabQuestionButtons(2.46),['Set search near 2.46 · 4 modes and run','Run as set','Cancel']);
 assert.deepEqual(C.slabQuestionButtons(2.46,null),C.slabQuestionButtons(2.46));
});

test('G3: the page shows that run without running; Run as set, Cancel and the dialog are unchanged',()=>{
 const app=read('workspace-app.mjs');
 // the question looks for the run with the shortcut's inputs and names it on the first button
 assert.ok(app.includes('const opener=document.activeElement,shown=shortcutRun(runs,current(),state.groupIndex,t),[search,run,cancel]=slabQuestionButtons(t,shown?runNumber(shown):null);'));
 // with it, the first button sets the shortcut (useClosedSearch), shows the run and resolves null,
 // so the Run study handler returns before anything of the run
 assert.ok(app.includes("slabAnswer=value=>{slabAnswer=null;if(slabDialog.open)slabDialog.close();restoreDialogFocus(opener);if(value==='search'&&shown){showShortcutRun(t,shown);resolve(null);return;}resolve(value);};"));
 assert.ok(app.includes('function showShortcutRun(t,run){useClosedSearch(t);if(!runs.includes(run))return;solverRun=run;ui.page=\'Results\';render();}'));
 // the dialog, its focus and Escape, and the Run study handler are those of round 27
 assert.ok(app.includes("slabDialog.showModal();$('slab-question-search').focus();"));
 assert.ok(app.includes("slabDialog.oncancel=event=>{event.preventDefault();slabAnswer?.(null);};"));
 assert.ok(app.includes("$('slab-question-run').onclick=()=>slabAnswer?.('run');"));
 assert.ok(app.includes("$('slab-question-cancel').onclick=()=>slabAnswer?.(null);"));
});
