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
