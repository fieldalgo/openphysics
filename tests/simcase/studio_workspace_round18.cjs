// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
// Round 18: usability fixes of the optical and heated models. Plain text comparison only: no
// RegExp is built from a dynamic string.
const test=require('node:test');const assert=require('node:assert/strict');
const fs=require('node:fs');const path=require('node:path');
const STATIC='../../packages/simcase/src/simcase/studio/static/';
const read=name=>fs.readFileSync(path.join(__dirname,STATIC,name),'utf8');
let A;
test.before(async()=>{A=await import(STATIC+'workspace-applications.mjs');});

test('X10: a card of a model in the project reads "Return to model (N runs)"; others keep "Open model"',()=>{
 assert.equal(A.returnToModelText(2),'Return to model (2 runs)');assert.equal(A.returnToModelText(1),'Return to model (1 run)');
 assert.equal(A.returnToModelText(0),'Return to model');assert.equal(A.CARD_OPEN_TEXT,'Open model');
 const src=read('workspace-applications.mjs');
 assert.ok(src.includes("action.textContent=CARD_OPEN_TEXT;if(returnTo[app.id]!==undefined)action.textContent=returnToModelText(returnTo[app.id]);"));
 // every model of the project, shown or not
 const app=read('workspace-app.mjs');
 assert.ok(app.includes("if(workspaceInProject()&&workspaceCard())returnTo[workspaceCard()]=workspaceCard()==='optical'?runs.length:0;if(multiView.inProject())returnTo['heated-waveguide']=multiView.projectRuns();"));
});

test('X5: the project name dialog always says what the file holds; the after-save note says "a number such as (1)"',async()=>{
 const F=await import(STATIC+'workspace-files.mjs');
 assert.equal(F.fileHoldsText([{title:'Optical waveguide',runs:2},{title:'Heated silicon waveguide',runs:1}]),'The file will hold Optical waveguide (2 runs) and Heated silicon waveguide (1 run).');
 assert.equal(F.fileHoldsText([{title:'Steady heat conduction',runs:0}]),'The file will hold Steady heat conduction (no runs).');
 assert.equal(F.downloadAgainNote('x.json'),'A download cannot replace the earlier file, so your browser may add a number such as “ (1)” to its name.');
 const app=read('workspace-app.mjs');
 // set for the time of a project save, so both of its routes through the dialog show it
 assert.ok(app.includes("function deliverProject(makeText,{saveAs}){\n savingFile=true;nameDialogContents=projectHoldsText();"));
 assert.ok(app.includes("}).finally(()=>{savingFile=false;nameDialogContents=null;});"));
 assert.ok(app.includes('<h2 id="save-name-title">Save As</h2><p id="save-name-contents" hidden></p><p id="save-name-unavailable" hidden></p>'));
 assert.ok(app.includes("const contents=nameDialogContents;$('save-name-contents').hidden=!contents;$('save-name-contents').textContent=contents||'';"));
});

test('X4: browser recovery turning off posts one Messages line, once until it works again',async()=>{
 const P=await import(STATIC+'workspace-persistence.mjs');
 assert.equal(P.recoveryOffText('overLimit'),'Browser recovery is off: this session is over 16 MiB. File › Save keeps your work.');
 assert.equal(P.recoveryOffText('quota'),'Browser recovery is off: this browser’s storage is full. File › Save keeps your work.');
 assert.equal(P.recoveryOffText('unavailable'),null);assert.equal(P.recoveryOffText('kept'),null);
 const app=read('workspace-app.mjs');
 assert.ok(app.includes("const text=recoveryOffText(recoveryState);if(!text||recoveryOffPosted===recoveryState)return;recoveryOffPosted=recoveryState;"));
 assert.ok(app.includes("const host=$('file-status');if(resultNotice&&host.textContent){host.append(' '+text);}else notice(text);"));
 assert.ok(app.includes("if(state.phase==='current'){recoveryState='kept';recoveryOffPosted=null;}"));
 assert.ok(app.includes("if(state.phase==='saved'){recoveryState='kept';recoveryOffPosted=null;"));
 assert.ok(app.includes("Previous completed snapshot is retained if the database transaction failed.';postRecoveryOff();}"));
});
