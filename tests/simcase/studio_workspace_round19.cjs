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

test('Y4: before the six-run limit drops a run, Run study asks: Pin Run N and run, Run, Cancel',async()=>{
 const W=await import(STATIC+'workspace-workflow.mjs');
 const shape={type:'rect',name:'Core',material:'Silicon',x:-350,y:0,w:700,h:300};
 const run=n=>({number:n,label:'',pinned:false,input:{model:{shapes:[shape]}},settings:{mode_count:4}});
 const runs=[1,2,3,4,5,6].map(run);
 assert.deepEqual(W.opticalDropQuestion(runs[2],runs),{title:'Running drops Run 3 (700 × 300 nm · 4 modes).',note:'Up to six runs are kept; a pinned run is never dropped.',pin:'Pin Run 3 and run',run:'Run',cancel:'Cancel'});
 // the last unpinned run cannot be pinned: the new run would have no slot
 const pinned=runs.map((r,i)=>({...r,pinned:i!==5}));
 assert.equal(W.opticalDropQuestion(pinned[5],pinned).pin,null);
 // a named run, and the heated model's words
 assert.equal(W.opticalDropQuestion({...runs[0],label:'Design A'},runs).title,'Running drops Run 1 · Design A (700 × 300 nm · 4 modes).');
 assert.deepEqual(W.dropQuestion('Run 3 (run at 05:31 AM)',3),{title:'Running drops Run 3 (run at 05:31 AM).',note:'Up to six runs are kept; a pinned run is never dropped.',pin:'Pin Run 3 and run',run:'Run',cancel:'Cancel'});
 const app=read('workspace-app.mjs');
 // the dialog: modal, labelled, Escape cancels, the first answer focused, focus back to the opener
 assert.ok(app.includes("dropDialog.id='run-drop-confirm';dropDialog.setAttribute('aria-labelledby','run-drop-confirm-title');dropDialog.setAttribute('aria-describedby','run-drop-confirm-description');"));
 assert.ok(app.includes("dropDialog.oncancel=event=>{event.preventDefault();dropAnswer?.(null);};"));
 assert.ok(app.includes("dropAnswer=answer=>{dropAnswer=null;dropDialog.close();restoreDialogFocus(opener);resolve(answer);};"));
 assert.ok(app.includes("if(!dropDialog.open)dropDialog.showModal();(question.pin?pin:$('run-drop-confirm-run')).focus();"));
 // the optical Run study asks first, and checks the state again after the answer
 assert.ok(app.includes(" if(!await confirmOpticalDrops())return;\n // the question waited for an answer: the state is checked again\n"));
 // Pin Run N and run pins it and asks again for the run that would then be dropped
 assert.ok(app.includes("for(let run=nextDropped(runs,RUN_LIMIT);run;run=nextDropped(runs,RUN_LIMIT)){"));
 // the heated model asks with the same dialog
 const view=read('workspace-multiphysics-view.mjs');
 assert.ok(view.includes("run:()=>askedRun(),"));
 assert.ok(view.includes("dropQuestion(`${runTitle(r)} (run at ${runTime(r)})`,r.number,{canPin:runs.filter(x=>!x.pinned).length>1})"));
 // the limit and the line beside Run study stay
 assert.ok(app.includes("const host=$('run-drop'),run=nextDropped(runs,RUN_LIMIT);"));
});
