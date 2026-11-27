// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
// Round 33 (agent proxy round 33 on main d3bc25e): M1, after an optical model is opened from a file
// or restored from this browser, the Messages line names its current inputs: the newest run whose
// inputs they equal (the comparison behind "has the results of the current inputs"), or, with no
// such run, the existing words "Current inputs (<summary>) have no run yet." Which inputs become
// current is unchanged. Plain text comparison only: no RegExp is built from a dynamic string.
const test=require('node:test');const assert=require('node:assert/strict');
const fs=require('node:fs');const path=require('node:path');
const STATIC='../../packages/simcase/src/simcase/studio/static/';
const read=name=>fs.readFileSync(path.join(__dirname,STATIC,name),'utf8');
const run=(number,signature,label,origin='imported')=>({number,signature,origin,...(label?{label}:{}),input:{model:{}}});

test('M1: open with the inputs of a named run names Run N · name',async()=>{
 const W=await import(STATIC+'workspace-workflow.mjs');
 const runs=[run(1,'a','Design A'),run(2,'b','Design B')];
 assert.equal(W.currentInputsText(runs,'b','700 × 300 nm'),"Current inputs are Run 2 · Design B's.");
 // several runs with these inputs: the newest is named
 assert.equal(W.currentInputsText([...runs,run(3,'a','Design A again')],'a','600 × 300 nm'),"Current inputs are Run 3 · Design A again's.");
});
test('M1: open with the inputs of an unnamed run names Run N',async()=>{
 const W=await import(STATIC+'workspace-workflow.mjs');
 assert.equal(W.currentInputsText([run(1,'a','Design A'),run(2,'b'),run(3,'c')],'c','650 × 300 nm'),"Current inputs are Run 3's.");
 // a run without a stored number takes its place in the list, as the footer's run does
 assert.equal(W.currentInputsText([{signature:'x',input:{model:{}}},{signature:'c',input:{model:{}}}],'c','650 × 300 nm'),"Current inputs are Run 2's.");
});
test('M1: open with inputs of no run reuses the save wording',async()=>{
 const W=await import(STATIC+'workspace-workflow.mjs');
 assert.equal(W.currentInputsText([run(1,'a','Design A'),run(2,'b','Design B')],'z','650 × 300 nm'),'Current inputs (650 × 300 nm) have no run yet.');
 // no runs: nothing is said, as the save message says nothing then
 assert.equal(W.currentInputsText([],'z','650 × 300 nm'),'');
});
test('M1: restore from this browser names the run the same way',async()=>{
 const W=await import(STATIC+'workspace-workflow.mjs');
 const runs=[run(1,'a','Design A','recovered'),run(2,'b','Design B','recovered')];
 assert.equal(W.currentInputsText(runs,'b','700 × 300 nm'),"Current inputs are Run 2 · Design B's.");
 assert.equal(W.currentInputsText(runs,'q','650 × 300 nm'),'Current inputs (650 × 300 nm) have no run yet.');
});
test('M1: the open, restore, project open and two-model restore messages carry the sentence',()=>{
 const app=read('workspace-app.mjs');
 // the optical model's own inputs, also while the multiphysics model is shown (its placeholder physics are not them)
 assert.ok(app.includes("const opticalInputsNow=()=>mpFlags&&workspacePhysics?snapshot({...state,...workspacePhysics},setup):current();"));
 assert.ok(app.includes("return currentInputsText(runs,studySignature(input,state.modeCount,state.groupIndex,pmlNow(),closedTargetNow()),geometryWords(input.model));"));
 // the optical open and restore line (one notice for both)
 assert.ok(app.includes("'File › Save keeps it in a file; input undo starts here.')));appendCurrentInputs();"));
 // the project open line, and the two-model restore line (after the second model's restore)
 assert.ok(app.includes("Results were read from the file, not recomputed; nothing was run.`);if(ws)appendCurrentInputs();"));
 assert.ok(app.includes("const options={then:()=>{done();appendCurrentInputs();}"));
 // the heated model's messages are not changed
 assert.ok(!read('workspace-multiphysics-view.mjs').includes('currentInputs'));
});
