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
 // the drop line is about running (round 21: the dialog is gone)
 const run={number:3,settings:{mode_count:2},input:{model:doc.model}};
 assert.equal(W.dropWarningText(run),'If you run: drops Run 3 (closed · 500 × 220 nm) · pin it to keep it');
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
 // after rounds 26–30 the box's entry names both times, each for what it is
 const box=A.resumeChoices(newest,[{...relinked,index:0}],t).other,card=A.cardResumeChoice(relinked,'Optical waveguide',t,{older:true}).label;
 assert.equal(box.label,'Restore from this browser: Optical waveguide · 2 runs · Run 1, Run 2');
 assert.equal(box.detail,'Older · kept in this browser 8:30 · same as both-models.json, saved 8:31 · Open file… gives the same runs');
 assert.equal(card,'Restore from this browser · Optical waveguide · Run 1, Run 2 · older · same as file both-models.json, saved 8:31');
 // a record changed since its file, or with no file save time, names its own time in both
 for(const item of [{...relinked,fileCurrent:false},{...relinked,fileSavedAt:undefined},{...relinked,file:null}])assert.equal(A.offerSavedAt(item),'8:30');
 // the order still follows the records' own times
 const order=A.resumeChoices({...relinked,savedAt:'2026-11-24T08:30:00Z',fileSavedAt:'2026-11-24T08:31:00Z'},[{...newest,savedAt:'2026-11-24T08:30:30Z',index:0}],t);
 assert.deepEqual([order.newest.kind,order.other.kind],['earlier','latest']);
});

test('Z5: without a comparable timed run the Run study box has no timing part',async()=>{
 const W=await import(STATIC+'workspace-workflow.mjs');
 assert.equal(W.runPlanText({modeCount:2}),'Closed window · 2 modes');
 assert.equal(W.runPlanText({groupIndex:true,modeCount:2}),'Closed window · 2 modes · group index on (3 solves)');
 assert.equal(W.runPlanText({open:true,searches:2,groupIndex:true,pmlCheck:true,modeCount:2}),'Open boundary · 2 modes · 2 searches · group index on · PML check on (5 solves)');
 assert.equal(W.runPlanText({open:true,modeCount:2,last:220000}),'Open boundary · 2 modes · 1 search · last such run 3:40');
 const src=read('workspace-workflow.mjs');assert.ok(!src.includes("'no timed run in this tab yet'"));assert.ok(!src.includes("'no earlier run'"));
});

test('Z6: the optical scope note names the closed window and the open boundary, whichever is chosen',()=>{
 const src=read('workspace-app.mjs');
 assert.ok(src.includes("const OPTICAL_SCOPE_BOUNDARY='3 × 2.4 µm window, closed (PEC edges) or with an open boundary (PML 1 µm outside the open edges, PEC on the closed ones)';"));
 assert.ok(src.includes("'+OPTICAL_SCOPE_BOUNDARY+'; 1 to 8 modes"));
 assert.ok(!src.includes("'PEC outer edges'"));
});

test('Z7 (round 21 W2): the drop question and its waiting words are gone',async()=>{
 const W=await import(STATIC+'workspace-workflow.mjs');
 assert.equal(W.RUN_QUESTION_PLAN,undefined);assert.equal(W.RUN_QUESTION_STATUS,undefined);
 const app=read('workspace-app.mjs'),view=read('workspace-multiphysics-view.mjs');
 for(const text of ['runQuestion','RUN_QUESTION','run-drop-confirm'])assert.ok(!app.includes(text),text);
 for(const text of ['runQuestionOpen','runQuestionWords','confirmDrop'])assert.ok(!view.includes(text)&&!app.includes(text),text);
 // the hidden job panel still keeps no message
 assert.ok(app.includes("if($('job-panel').hidden){$('job-message').textContent='';$('job-message').title='';}"));
});

test('Z2: the newest offer of a project with both models restores both',async()=>{
 const A=await import(STATIC+'workspace-applications.mjs');
 const t=x=>x;
 const optical={runs:6,model:'Optical waveguide',names:['Run 1'],savedAt:'2026-11-24T08:44:00Z',file:'both-models.json',fileCurrent:false,pair:{model:'Heated silicon waveguide',runs:2,savedAt:'2026-11-24T08:30:00Z'}};
 const heated={runs:2,model:'Heated silicon waveguide',names:['Run 1','Run 2'],savedAt:'2026-11-24T08:30:00Z',file:'both-models.json',fileCurrent:false,index:0};
 const choices=A.resumeChoices(optical,[heated],t);
 // after rounds 26–30 the file words and the time are in the detail line (string 5: an opened file)
 assert.deepEqual(choices.newest,{kind:'latest',newest:true,pair:true,label:'Restore newest from this browser: Optical waveguide (6 runs) and Heated silicon waveguide (2 runs)',detail:'Kept in this browser 2026-11-24T08:44:00Z · newer than both-models.json as opened'});
 // round 21 (W4): the other model's own entry is not listed again
 assert.equal(choices.other,null);assert.deepEqual(choices.earlier,[]);
 // a pair on an entry that is not the newest is not offered; one run reads "1 run"
 assert.equal(A.resumeChoices({...heated,kind:'latest',pair:{model:'Optical waveguide',runs:1}},[{...optical,pair:null,index:0}],t).other.pair,undefined);
 assert.equal(A.pairLine({model:'Heated silicon waveguide',runs:1},{model:'Optical waveguide',runs:1}),'Heated silicon waveguide (1 run) and Optical waveguide (1 run)');
 // the caller: a pair only while the tab holds runs of neither model, and not "(already in this tab)"
 const app=read('workspace-app.mjs');
 assert.ok(app.includes("const pairable=!runs.length&&!multiView.projectRuns();"));
 assert.ok(app.includes("return o&&!o.inTab&&o.record?{...entry,pair:{model:o.model,runs:o.runs,savedAt:o.record.savedAt,fileCurrent:o.record.fileCurrent}}:entry;"));
 // the second record is found again by its model, time and file; a failure names that model
 assert.ok(app.includes("e.recovered.session.application===record.application&&e.recovered.savedAt===record.savedAt&&entryFile(e)===record.file"));
 assert.ok(app.includes("notice(`${other.model} was not restored: its browser record is no longer stored.`)"));
 assert.ok(app.includes("failed:message=>notice(`${other.model} was not restored: ${message}`)"));
 // the newest record's model is shown at the end, with one message for both
 assert.ok(app.includes("const done=()=>{chooseTemplate(card);notice(`Restored ${pairLine(entry,{model:other.model,runs:record.runs})} from this browser, not recomputed.`);};"));
 // with both records the same as the file, the project reads as saved
 assert.ok(app.includes("projectMatched:firstFile?.current===true&&firstFile.name===record.file"));
 // no format change: the recovery record and session writers are untouched by Z2
 assert.ok(!read('workspace-notebook-recovery.mjs').includes('pair'));
});

test('Z2 follow-up: both restores write this tab\'s pending recovery save before they read the stored record',()=>{
 const app=read('workspace-app.mjs');
 assert.ok(app.includes("const loaded=await workspaceLoads.read(async()=>{await notebookAutosave.settle();const latest=await notebookStore.load();const list=await notebookStore.loadEarlier();"));
 assert.ok(app.includes("const loaded=await workspaceLoads.read(async()=>{await notebookAutosave.settle();const record=await notebookStore.load();"));
 // the store's conflict rule is unchanged
 assert.ok(read('workspace-notebook-recovery.mjs').includes("if(recoveryRevision(request.result)!==baseline){"));
});
