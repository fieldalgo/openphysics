// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
// Round 19: usability fixes of the optical and heated models. Plain text comparison only: no
// RegExp is built from a dynamic string.
const test=require('node:test');const assert=require('node:assert/strict');
const fs=require('node:fs');const path=require('node:path');
const STATIC='../../packages/simcase/src/simcase/studio/static/';
const read=name=>fs.readFileSync(path.join(__dirname,STATIC,name),'utf8');

test('Y5 (round 20, Z5: the timing part is left out): with no run timed in this tab, the Run study box gives no time',async()=>{
 const W=await import(STATIC+'workspace-workflow.mjs');
 assert.equal(W.runPlanText({modeCount:2}),'Closed window · 2 modes');
 assert.equal(W.runPlanText({open:true,searches:2,groupIndex:true,modeCount:2}),'Open boundary · 2 modes · 2 searches · group index on (3 solves)');
 // a run timed in this tab still gives its time
 assert.equal(W.runPlanText({modeCount:2,last:12400}),'Closed window · 2 modes · last such run 0:12');
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
 // since session version 12 (stable run numbers) no message speaks about numbering: a file stores the
 // numbers, or Studio wrote it only while they were its places (HQ decision
 // 2026-11-24-openphysics-studio-session-v12-k10-amended)
 assert.equal(W.RENUMBERED_TEXT,undefined);assert.equal(W.renumberedText,undefined);
 const app=read('workspace-app.mjs');
 // a session file opened, or a session restored from this browser
 assert.ok(app.includes("'File › Save keeps it in a file; input undo starts here.')));"));
 // a project file
 assert.ok(app.includes("Results were read from the file, not recomputed; nothing was run.`);"));
 assert.ok(!app.includes('numbered from 1'));
 // the heated model keeps its stored numbers: its messages do not say this
 assert.ok(!read('workspace-multiphysics-view.mjs').includes('numbered from 1'));
});

test('Y4 (round 21 W2): Run study no longer asks; the line beside it stays',async()=>{
 const W=await import(STATIC+'workspace-workflow.mjs');
 assert.equal(W.dropQuestion,undefined);assert.equal(W.opticalDropQuestion,undefined);assert.equal(W.DROP_QUESTION_NOTE,undefined);
 const app=read('workspace-app.mjs'),view=read('workspace-multiphysics-view.mjs');
 for(const text of ['dropDialog','askRunDrop','confirmOpticalDrops','await confirm'])assert.ok(!app.includes(text),text);
 assert.ok(!view.includes('askedRun'));assert.ok(view.includes("run:()=>run(),"));
 // the limit and the line beside Run study stay
 assert.ok(app.includes("const host=$('run-drop'),run=matched?null:list[0]||null;"));
});

test('Y3: a restore brings back the project name and file it was saved to, or names the file it was a copy of',async()=>{
 const P=await import(STATIC+'workspace-persistence.mjs');const when=()=>'06:15 AM';
 assert.equal(P.projectTitle({models:1,recovery:'kept',copyOf:'both-models.json'},when),'Untitled project · recovered from a copy of both-models.json · not saved to a file · kept for recovery in this browser');
 assert.equal(P.projectTitle({models:1,recovery:'kept'},when),'Untitled project · not saved to a file · kept for recovery in this browser');
 // a file of the project wins over the copy
 assert.equal(P.projectTitle({name:'y3-saved',models:1,file:{name:'y3-saved.json',how:'recovered',savedAt:'T'},current:false,recovery:'kept',copyOf:'both-models.json'},when),'y3-saved · y3-saved.json · changed since saved 06:15 AM · kept for recovery in this browser');
 const app=read('workspace-app.mjs');
 // a saved project file: the name and file, also when the record changed since (saved only when current)
 assert.ok(app.includes(" if(!file?.projectName){if(!file&&opened&&!project.file&&!project.name)project.copyOf=opened;return;}"));
 assert.ok(app.includes("project.stamp=file.current===true&&(projectModels().length===1||matched)?projectStamp():null;"));
 assert.ok(!app.includes("if(file?.current!==true||!file.projectName)return;"));
 // both models' restores pass the opened file; a file replacing the project clears the copy
 assert.ok(app.includes("restoreProjectFile(file,pending.openedFile,{matched:pending.projectMatched===true});"));assert.ok(app.includes("restoreProjectFile(savedFile,openedFile,{matched:projectMatched===true});"));
 assert.ok(app.includes("stamp:null,scope:project.scope+1,copyOf:null,recovered:null});"));
 assert.ok(app.includes("recovery:opticalRecoveryShown(),copyOf:project.copyOf,recovered});"));
});

test('Y1: the newest stored session with runs is the first restore offer; every other says it is older',async()=>{
 const A=await import(STATIC+'workspace-applications.mjs');
 const when=t=>({T546:'5:46 AM',T538:'5:38 AM',T530:'5:30 AM'})[t]??t;
 // ISO times so the order is by time; the newest with runs leads whatever its kind
 const at=s=>'2026-11-24T05:'+s+':00Z',w=t=>when({[at('46')]:'T546',[at('38')]:'T538',[at('30')]:'T530'}[t]);
 const latest={runs:5,savedAt:at('38'),model:'Optical waveguide',names:[],file:'both-models.json',fileCurrent:false};
 const earlier=[{runs:6,savedAt:at('46'),model:'Optical waveguide',names:[],index:0,file:'both-models.json',fileCurrent:false},{runs:1,savedAt:at('30'),model:'Heated silicon waveguide',names:['Run 1'],index:1}];
 // after rounds 26–30: one button per piece of work; the times and file words are in the detail lines,
 // the other model's newest record is the second button, the rest are earlier copies
 const c=A.resumeChoices(latest,earlier,w);
 assert.deepEqual(c.newest,{kind:'earlier',index:0,newest:true,label:'Restore newest from this browser: Optical waveguide · 6 runs',detail:'Kept in this browser 5:46 AM · newer than both-models.json as opened'});
 assert.deepEqual(c.other,{kind:'earlier',index:1,label:'Restore from this browser: Heated silicon waveguide · 1 run · Run 1',detail:'Older · kept in this browser 5:30 AM · not saved to a file'});
 assert.deepEqual(c.earlier,[{kind:'latest',label:'Restore Optical waveguide · 5 runs',detail:'Older copy · kept in this browser 5:38 AM · last linked to both-models.json'}]);
 // a session without runs saved after the newest is not called older
 assert.deepEqual(A.resumeChoices({runs:0,savedAt:at('50')},[{runs:2,savedAt:at('46'),index:0}],t=>t).earlier.map(e=>[e.label,e.detail]),[['Restore 0 runs','Copy without runs · kept in this browser '+at('50')+' · not saved to a file']]);
 const lib=read('workspace-applications.mjs');
 assert.ok(lib.includes("if(choice.newest){button.className='primary';button.id='resume-newest';}"));
 const app=read('workspace-app.mjs');
 // the box lists every stored session (no longer leaving out the cards' records), still hidden while the tab holds runs
 // after rounds 26–30 (amendment A1) Not now closes the box instead of hiding it: a collapsed flag
 assert.ok(app.includes(" if(runs.length)return null;\n const list=recoveryList(),latest=list.find(e=>e.kind==='latest');"));
 assert.ok(app.includes("collapsed:resumeCollapsed"));
 // the record just restored is left out until this tab's own record is written; the rest stay listed
 assert.ok(app.includes("distinctRecords(notebookRecoveryRecord,earlierRecords).filter(e=>e.index!==restoredIndex)"));
 assert.ok(app.includes("const restored=restoredIndex!==null;restoredIndex=null;if(notebookStore.movedEarlier()||first||restored)renderEarlierSessions();"));
 // X7: "(already in this tab)" names the tab's runs
 assert.ok(app.includes("const tab=!inTab?null:kind==='optical'?multiView.runs().map(r=>runTitle(r.number,r.label||'')):runs.map(r=>runTitle(r.number,r.label||''));"));
});
