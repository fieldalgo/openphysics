// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
// Round 34 (agent proxy round 34 on main 3a4f3e5): M2, in a Messages line that names more than one
// model (the project open line, the two-model restore line) the current-inputs sentence starts with
// the optical model's title as that line names it: "Optical waveguide: current inputs are Run 2 ·
// Design B's." A line that names one model keeps "Current inputs are Run 2 · Design B's." Which
// inputs become current is unchanged. Plain text comparison only: no RegExp is built from a dynamic string.
const test=require('node:test');const assert=require('node:assert/strict');
const fs=require('node:fs');const path=require('node:path');
const STATIC='../../packages/simcase/src/simcase/studio/static/';
const read=name=>fs.readFileSync(path.join(__dirname,STATIC,name),'utf8');
const run=(number,signature,label,origin='imported')=>({number,signature,origin,...(label?{label}:{}),input:{model:{}}});

test('M2: a two-model line names the optical model before a named run',async()=>{
 const W=await import(STATIC+'workspace-workflow.mjs');
 const runs=[run(1,'a','Design A'),run(2,'b','Design B')];
 assert.equal(W.currentInputsText(runs,'b','700 × 300 nm','Optical waveguide'),"Optical waveguide: current inputs are Run 2 · Design B's.");
 // the title is the one the line uses, not a fixed name
 assert.equal(W.currentInputsText(runs,'b','700 × 300 nm','Ring bus'),"Ring bus: current inputs are Run 2 · Design B's.");
});
test('M2: a two-model line names the optical model before an unnamed run',async()=>{
 const W=await import(STATIC+'workspace-workflow.mjs');
 assert.equal(W.currentInputsText([run(1,'a','Design A'),run(2,'b'),run(3,'c')],'c','650 × 300 nm','Optical waveguide'),"Optical waveguide: current inputs are Run 3's.");
});
test('M2: a two-model line names the optical model when no run has the current inputs',async()=>{
 const W=await import(STATIC+'workspace-workflow.mjs');
 assert.equal(W.currentInputsText([run(1,'a','Design A')],'z','650 × 300 nm','Optical waveguide'),'Optical waveguide: current inputs (650 × 300 nm) have no run yet.');
 // no runs: nothing is said, as before
 assert.equal(W.currentInputsText([],'z','650 × 300 nm','Optical waveguide'),'');
});
test('M2: a one-model line keeps the round-33 sentence',async()=>{
 const W=await import(STATIC+'workspace-workflow.mjs');
 const runs=[run(1,'a','Design A'),run(2,'b','Design B')];
 assert.equal(W.currentInputsText(runs,'b','700 × 300 nm'),"Current inputs are Run 2 · Design B's.");
 assert.equal(W.currentInputsText(runs,'b','700 × 300 nm',''),"Current inputs are Run 2 · Design B's.");
 assert.equal(W.currentInputsText(runs,'z','650 × 300 nm'),'Current inputs (650 × 300 nm) have no run yet.');
});
test('M2: the project open and two-model restore lines pass the optical title; the one-model line does not',()=>{
 const app=read('workspace-app.mjs');
 // one-model open and restore line: no title
 assert.ok(app.includes("'File › Save keeps it in a file; input undo starts here.')));appendCurrentInputs();"));
 // project open: the optical model's title as modelsText prints it, only when the project also holds the heated model
 assert.ok(app.includes("Results were read from the file, not recomputed; nothing was run.`);if(ws)appendCurrentInputs(mp?ws.title:'');"));
 // two-model restore: the optical model's title as pairLine prints it
 assert.ok(app.includes("const opticalTitle=card==='heated-waveguide'?other.model:entry.model||'Optical waveguide';"));
 assert.ok(app.includes("const options={then:()=>{done();appendCurrentInputs(opticalTitle);}"));
 assert.ok(read('workspace-applications.mjs').includes("export const pairLine=(item,pair)=>`${item.model||'Optical waveguide'} (${runCount(item.runs)}) and ${pair.model} (${runCount(pair.runs)})`;"));
 // the heated model's messages are not changed
 assert.ok(!read('workspace-multiphysics-view.mjs').includes('currentInputs'));
});
