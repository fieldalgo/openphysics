// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
// Round 20: usability fixes of the optical and heated models. Plain text comparison only: no
// RegExp is built from a dynamic string.
const test=require('node:test');const assert=require('node:assert/strict');
const fs=require('node:fs');const path=require('node:path');
const STATIC='../../packages/simcase/src/simcase/studio/static/';
const read=name=>fs.readFileSync(path.join(__dirname,STATIC,name),'utf8');

test('Z1: one state, one message: no request to run beside "No need to run"',async()=>{
 const W=await import(STATIC+'workspace-workflow.mjs'),I=await import(STATIC+'workspace-inputs.mjs'),M=await import(STATIC+'workspace-multiphysics.mjs');
 // the edit's own sentence stays, its request to run goes
 assert.equal(W.matchingRunMessage(I.editNoticeText('modeCount',3)),'Modes to find set to 3.');
 assert.equal(W.matchingRunMessage(I.editNoticeText('shapeW',600,{leftX:-300})),'Width set to 600 nm. Left x moved to −300 nm to keep the centre.');
 assert.equal(W.matchingRunMessage(I.editNoticeText('shapeH',300,{afterResult:true})),'Height set to 300 nm.');
 assert.equal(W.matchingRunMessage('Optical left edge closed (PEC). Run explicitly to compute new results.'),'Optical left edge closed (PEC).');
 assert.equal(W.matchingRunMessage('Inputs changed since the last result. Run again to compute the new inputs.'),'');
 // a message without a request is kept as it is (Undo, Redo, the group index option)
 assert.equal(W.matchingRunMessage('Group index off: the next run is one solve, without n_g.'),'Group index off: the next run is one solve, without n_g.');
 // without a matching run the edit notice keeps today's full sentence
 assert.equal(I.editNoticeText('modeCount',3),'Modes to find set to 3. Run explicitly to compute new results.');
 // the offer: the edit's sentence, then the "No need to run" sentence alone
 assert.equal(W.matchingRunMessage(I.editNoticeText('modeCount',3))+' '+M.matchesAgainText(6)+'.','Modes to find set to 3. No need to run: Run 6 already has these results. Run study adds a copy with the same values.');
 // status bar: a run read from file or recovered that has these results, without "press Run"
 const doc={model:{shapes:[{name:'Core',type:'rect',material:'Silicon',x:-250,y:0,w:500,h:220}],wavelength:1550,coreMesh:30},setup:{materials:{Oxide:'Silica'}}};
 const sig=JSON.stringify(doc);
 assert.equal(W.opticalReadyStatus(W.opticalFreshness(doc,[{signature:sig,origin:'recovered',number:6}])),'Run 6 · recovered from this browser, not recomputed · has the results of the current inputs');
 assert.equal(W.opticalReadyStatus(W.opticalFreshness(doc,[{signature:sig,origin:'imported'}])),'Run 1 · read from file, not recomputed · has the results of the current inputs');
 assert.equal(M.readyStatus('current',2,'recovered'),'Run 2 · recovered from this browser, not recomputed · has the results of the current model');
 assert.equal(M.readyStatus('current',2,'imported'),'Run 2 · read from file, not recomputed · has the results of the current model');
 // a run computed here keeps its words
 assert.equal(M.readyStatus('current',2,'local'),'Run 2 matches the model · press Run to solve again');
 // the drop line is about running; the dialog heading stays the question
 const run={number:3,settings:{mode_count:2},input:{model:doc.model}};
 assert.equal(W.dropWarningText(run),'If you run: drops Run 3 (500 × 220 nm · 2 modes) · pin it to keep it');
 assert.equal(W.opticalDropQuestion(run,[run,{...run,number:4}]).title,'Running drops Run 3 (500 × 220 nm · 2 modes).');
 for(const name of ['workspace-workflow.mjs','workspace-multiphysics.mjs'])assert.ok(!read(name).includes('press Run to compute it here'),name);
 assert.ok(read('workspace-app.mjs').includes('host.textContent=matchingRunMessage(host.textContent);'));
});

test('Z3: each return card names its model, so two never read alike',async()=>{
 const A=await import(STATIC+'workspace-applications.mjs');
 assert.equal(A.returnToModelText(2,'Optical waveguide'),'Return to Optical waveguide (2 runs)');
 assert.equal(A.returnToModelText(2,'Heated silicon waveguide'),'Return to Heated silicon waveguide (2 runs)');
 assert.equal(A.returnToModelText(1,'Heated silicon waveguide'),'Return to Heated silicon waveguide (1 run)');
 assert.equal(A.returnToModelText(0,'Optical waveguide'),'Return to Optical waveguide');
 const titles=[...A.APPLICATIONS,...A.COUPLED_TEMPLATES].map(a=>A.returnToModelText(2,a.title));
 assert.equal(new Set(titles).size,titles.length);
 assert.ok(read('workspace-applications.mjs').includes('returnToModelText(returnTo[app.id],app.title)'));
});

test('Z4: the box and the card name one time for one record',async()=>{
 const A=await import(STATIC+'workspace-applications.mjs');
 // a record relinked to the project file after a project save: savedAt 8:30, the file saved 8:31
 const relinked={runs:2,model:'Optical waveguide',names:['Run 1','Run 2'],savedAt:'8:30',file:'both-models.json',fileCurrent:true,fileSavedAt:'8:31'};
 const newest={runs:1,model:'Heated silicon waveguide',names:['Run 1'],savedAt:'8:32'};
 const t=x=>x;
 assert.equal(A.offerSavedAt(relinked),'8:31');
 const box=A.resumeChoices(newest,[{...relinked,index:0}],t)[1].label,card=A.cardResumeChoice(relinked,'Optical waveguide',t,{older:true}).label;
 assert.equal(box,'Restore from this browser: Optical waveguide · 2 runs · Run 1, Run 2 · same as file both-models.json · older · saved 8:31');
 assert.equal(card,'Restore from this browser · Optical waveguide · Run 1, Run 2 · older · same as file both-models.json, saved 8:31');
 // a record changed since its file, or with no file save time, names its own time in both
 for(const item of [{...relinked,fileCurrent:false},{...relinked,fileSavedAt:undefined},{...relinked,file:null}])assert.equal(A.offerSavedAt(item),'8:30');
 // the order still follows the records' own times
 assert.deepEqual(A.resumeChoices({...relinked,savedAt:'2026-11-24T08:30:00Z',fileSavedAt:'2026-11-24T08:31:00Z'},[{...newest,savedAt:'2026-11-24T08:30:30Z',index:0}],t).map(c=>c.kind),['earlier','latest']);
});
