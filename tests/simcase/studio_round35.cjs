// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
// Round 35 (agent proxy round 35 on main 2a74bba): L4, the reason Open boundary set Modes to find back
// (round 29, L1) stays under the Modes to find field: "Back to 2 with Open boundary: 4 was for the
// closed window's search near 2.46." The Messages sentence is unchanged, and both say the same reason.
// The note is kept until the next run starts or Modes to find or the outer boundary changes again.
// The memory of the shortcut's count is not lost across a closed run (the dialog's "Set search near
// 2.46 · 4 modes and run"): the browser check covers that path end to end. Plain text comparison
// only: no RegExp is built from a dynamic string.
const test=require('node:test');const assert=require('node:assert/strict');
const fs=require('node:fs');const path=require('node:path');
const STATIC='../../packages/simcase/src/simcase/studio/static/';
const read=name=>fs.readFileSync(path.join(__dirname,STATIC,name),'utf8');
const between=(text,start,end)=>{const i=text.indexOf(start);assert.notEqual(i,-1,start);const j=text.indexOf(end,i+start.length);assert.notEqual(j,-1,end);return text.slice(i,j);};

test('L4: the field note says the Messages sentence\'s reason',async()=>{
 const C=await import(STATIC+'workspace-closed-target.mjs');
 assert.equal(C.shortcutModesNoteText(2,4,2.46),"Back to 2 with Open boundary: 4 was for the closed window's search near 2.46.");
 assert.equal(C.shortcutModesNoteText(3,4,2.455),"Back to 3 with Open boundary: 4 was for the closed window's search near 2.455.");
 // the same reason as the round-29 sentence, which is unchanged
 assert.equal(C.shortcutModesBackText(2,4,2.46),"Modes to find back to 2: 4 was for the closed window's search near 2.46.");
 const reason="4 was for the closed window's search near 2.46.";
 assert.ok(C.shortcutModesNoteText(2,4,2.46).endsWith(': '+reason));assert.ok(C.shortcutModesBackText(2,4,2.46).endsWith(': '+reason));
});
test('L4: the memory keeps the note after Open boundary until it is cleared',async()=>{
 const C=await import(STATIC+'workspace-closed-target.mjs');
 const m=C.shortcutModesMemory();
 assert.equal(m.note(),'');
 m.set(2,4,2.46);assert.equal(m.note(),'');
 // the round-29 answer is unchanged
 assert.deepEqual(m.onOpen(4),{modeCount:2,text:"Modes to find back to 2: 4 was for the closed window's search near 2.46."});
 assert.equal(m.note(),"Back to 2 with Open boundary: 4 was for the closed window's search near 2.46.");
 // read again: still there (another notice does not touch it)
 assert.equal(m.note(),"Back to 2 with Open boundary: 4 was for the closed window's search near 2.46.");
 m.clearNote();assert.equal(m.note(),'');
 m.set(2,4,2.46);m.onOpen(4);m.clear();assert.equal(m.note(),'');
 m.set(2,4,2.46);m.onOpen(4);m.set(3,4,2.46);assert.equal(m.note(),'');
 // no note when the count was not set back
 m.set(2,4,2.46);assert.equal(m.onOpen(3),null);assert.equal(m.note(),'');
 m.set(4,4,2.46);assert.equal(m.onOpen(4),null);assert.equal(m.note(),'');
 assert.equal(m.onOpen(4),null);assert.equal(m.note(),'');
});
test('L4: a closed run keeps the shortcut memory; it clears only the note',()=>{
 const app=read('workspace-app.mjs');
 const runHandler=between(app,"$('run-optical').onclick=async()=>{",'function recomputeButton(');
 assert.ok(runHandler.includes('shortcutModes.clearNote();'),'the run start clears the note');
 assert.ok(!runHandler.includes('shortcutModes.clear()'),'the run does not forget the shortcut count');
 assert.ok(runHandler.includes("if(answer==='search')useClosedSearch(near);"),'the dialog answer sets the shortcut');
});
test('L4: Open boundary, the field and the other changes',()=>{
 const app=read('workspace-app.mjs');
 const outer=between(app,'function setOuterBoundary(open){','// Search near n_eff in a closed window');
 // the note goes with any boundary change, then Open boundary may set it again
 const cleared=outer.indexOf('shortcutModes.clearNote();'),onOpen=outer.indexOf('shortcutModes.onOpen(state.modeCount)');
 assert.ok(cleared!==-1&&onOpen!==-1&&cleared<onOpen,outer);
 // the Messages sentence stays
 assert.ok(outer.includes("if(back)$('file-status').append(' '+back.text);"));
 const field=between(app,'const modeCountField=()=>','\n');
 assert.ok(field.includes('shortcutModes.note()'),field);assert.ok(field.includes('id="mode-count-back-note"'),field);
 assert.ok(field.includes('aria-describedby="mode-count-back-note"'),field);
 // typed, Undo, Redo, Use this run's inputs, a new model or file: shortcutModes.clear(), which clears the note
 assert.ok(app.includes("if(key==='modeCount')shortcutModes.clear();"));
 assert.ok(between(app,'function restoreEdit(doc,label){','\n}').includes('shortcutModes.clear();'));
 assert.ok(between(app,'function applyProject(doc,','\n}').includes('shortcutModes.clear();'));
});
