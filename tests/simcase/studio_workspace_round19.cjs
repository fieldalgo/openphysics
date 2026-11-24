// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
// Round 19: usability fixes of the optical and heated models. Plain text comparison only: no
// RegExp is built from a dynamic string.
const test=require('node:test');const assert=require('node:assert/strict');
const fs=require('node:fs');const path=require('node:path');
const STATIC='../../packages/simcase/src/simcase/studio/static/';
const read=name=>fs.readFileSync(path.join(__dirname,STATIC,name),'utf8');

test('Y5: with no run timed in this tab, the Run study box says "no timed run in this tab yet"',async()=>{
 const W=await import(STATIC+'workspace-workflow.mjs');
 assert.equal(W.runPlanText({modeCount:2}),'Closed window · no timed run in this tab yet');
 assert.equal(W.runPlanText({open:true,searches:2,groupIndex:true,modeCount:2}),'Open boundary · 2 searches · group index on (3 solves) · no timed run in this tab yet');
 // a run timed in this tab still gives its time
 assert.equal(W.runPlanText({modeCount:2,last:12400}),'Closed window · last such run 0:12');
 assert.ok(!read('workspace-workflow.mjs').includes(":'no earlier run'"));
});

test('Y6: the heater-off label is associated with its box by for=, as well as by wrapping it',()=>{
 const html=read('workspace.html');
 assert.ok(html.includes('<label id="run-baseline-option" for="run-baseline" class="run-option" hidden><input type="checkbox" id="run-baseline">'));
});

test('Y7: a shape\'s Name and Material fields each have their own label (for=), not a wrapping one',()=>{
 const app=read('workspace-app.mjs');
 assert.ok(app.includes('<div><label for="shape-name">Name</label><input id="shape-name" type="text" maxlength="40" value="${escapeHtml(shape.name)}"></div>'));
 assert.ok(app.includes('<div><label for="shape-material">Material</label><select id="shape-material">${options(SHAPE_MATERIAL_CHOICES,shape.material)}</select></div>'));
 assert.ok(!app.includes('<label>Material<select id="shape-material">'));
});

test('Y2: the optical open and recovery messages say the runs are numbered from 1 in this tab',async()=>{
 const W=await import(STATIC+'workspace-workflow.mjs');
 assert.equal(W.RENUMBERED_TEXT,'Runs are numbered from 1 in this tab; names and pins are kept.');
 assert.equal(W.renumberedText('Optical waveguide'),'Optical waveguide runs are numbered from 1 in this tab; names and pins are kept.');
 const app=read('workspace-app.mjs');
 // a session file opened, or a session restored from this browser: when it has runs
 assert.ok(app.includes("'File › Save keeps it in a file; input undo starts here.'))+(runs.length?' '+RENUMBERED_TEXT:''));"));
 // a project file: when its optical model has runs
 assert.ok(app.includes("nothing was run.`+(ws?.session.runs.length?' '+renumberedText(ws.title):''));"));
 // the heated model keeps its stored numbers: its messages do not say this
 assert.ok(!read('workspace-multiphysics-view.mjs').includes('numbered from 1'));
});
