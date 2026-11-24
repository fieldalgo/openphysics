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

test('X1: an edit back to a run\'s inputs says "No need to run" with Show Run N; Run study is not blocked',async()=>{
 const M=await import(STATIC+'workspace-multiphysics.mjs');
 assert.equal(M.matchesAgainText(5,''),'No need to run: Run 5 already has these results. Run study adds a copy with the same values');
 const app=read('workspace-app.mjs');
 // after every input edit that changed the inputs, once the change or click that commits it has said
 // its own message (typing fires input before change), and after Undo and Redo
 assert.ok(app.includes("if(edits.signature!==before){checkpointRecovery();inputsChangedSinceResult();offerDue=true;}"));
 assert.ok(app.includes("document.addEventListener('change',()=>{trackEdit();edits.endGroup();if(offerDue)setTimeout(offerMatchingRun,0);});"));
 assert.ok(app.includes("document.addEventListener('click',()=>{trackEdit();edits.endGroup();if(offerDue)setTimeout(offerMatchingRun,0);});"));
 assert.ok(app.includes("restoreEdit(edits.undo(),'Undo');offerMatchingRun();")&&app.includes("restoreEdit(edits.redo(),'Redo');offerMatchingRun();"));
 // the run's whole study signature, the newest such run; one offer on the line
 assert.ok(app.includes("const sig=signature(),run=runs.findLast(r=>r.signature===sig);if(!run)return;"));
 assert.ok(app.includes("host.querySelector('#match-offer')?.remove();"));
 assert.ok(app.includes("show.textContent=`Show Run ${runNumber(run)}`;show.dataset.showRun=String(runNumber(run));"));
 assert.ok(app.includes("notice(`${runNumberTitle(run)} shown under Results; the inputs are unchanged.`)"));
 // Run study's disabled state does not look at a matching run
 const line=app.split('\n').find(l=>l.includes("$('run-optical').disabled="));
 assert.ok(line&&!line.includes('signature'),line);
});

test('X2: beside Run study, what the next run does and how long the last comparable run took',async()=>{
 const W=await import(STATIC+'workspace-workflow.mjs');
 assert.equal(W.runPlanText({open:true,searches:2,groupIndex:true,modeCount:2,last:220000}),'Open boundary · 2 searches · group index on (3 solves) · last such run 3:40');
 assert.equal(W.runPlanText({modeCount:2,last:12400}),'Closed window · last such run 0:12');
 assert.equal(W.runPlanText({modeCount:2}),'Closed window · no earlier run');
 // the PML check belongs to an open boundary only
 assert.equal(W.runPlanText({pmlCheck:true,modeCount:4}),'Closed window · no earlier run');
 assert.equal(W.runPlanText({open:true,searches:1,pmlCheck:true,modeCount:4,last:3725000}),'Open boundary · 1 search · PML check on (5 solves) · last such run 1:02:05');
 // comparable: the same boundary kind and group-index state, with a wall time measured in this tab
 const isOpen=r=>r.open,hasGroup=r=>r.g,runs=[{id:1,open:true,g:true,duration:200000},{id:2,open:true,g:false,duration:30000},{id:3,open:true,g:true},{id:4,open:false,g:true,duration:9000}];
 assert.equal(W.lastComparableRun(runs,{open:true,groupIndex:true},{isOpen,hasGroup}).id,1);
 assert.equal(W.lastComparableRun(runs,{open:true,groupIndex:false},{isOpen,hasGroup}).id,2);
 assert.equal(W.lastComparableRun(runs,{open:false,groupIndex:false},{isOpen,hasGroup}),null);
 // the wall time stays in this tab: no file holds it
 const N=await import(STATIC+'workspace-notebook.mjs'),P=await import(STATIC+'workspace-project.mjs');
 const input=P.snapshot({width:700,voltage:1,electric:false,heat:false,structure:false,optics:true},{materials:{Core:'Silicon',Oxide:'Silica',Heater:''},temperature:293.15,cooling:'',fixed:'',terminal:''});
 const run={job:'0000000a',completedAt:'2026-11-24T00:00:00.000Z',settings:N.opticalSettings(),input,effective_index:[2.4,1.7],field:{node_coordinates:[[0,0],[1e-6,0],[0,1e-6]],triangles:[[0,1,2]],real:[[[1,0,0]],[[0,1,0]]],imag:[[[0,0,0]],[[0,0,0]]]},origin:'local',number:1,duration:220000};
 const out=N.writeOpticalSession(input,[run],run.job,[run.job,run.job],{mode:0,component:'magnitude',window:'Core region'});
 assert.equal(out.ok,true);assert.equal(out.text.includes('duration'),false);assert.equal(out.text.includes('220000'),false);
 const app=read('workspace-app.mjs');
 assert.ok(app.includes("{const started=Date.parse(pending.startedAt);if(Number.isFinite(started))completed.duration=Date.now()-started;}"));
 assert.ok(app.includes("const last=lastComparableRun(runs,plan,{isOpen:isOpenRun,hasGroup:hasGroupIndex}),text=runPlanText({...plan,last:last?.duration??null});"));
 // Open boundary chosen while the group index is on: one warning in Messages
 assert.ok(app.includes("const GROUP_INDEX_OPEN_WARNING='Group index is on: open-boundary runs with it take about three times as long.';"));
 assert.ok(app.includes("if(open&&state.groupIndex===true){const warn=document.createElement('span');warn.className='message-warning';"));
 // a box of fixed size: the ribbon does not move when the words change
 const css=read('workspace.css');
 assert.ok(css.includes('.run-options{align-self:center;display:flex;flex-direction:column;justify-content:center;gap:2px;flex:none;box-sizing:border-box;width:460px;height:50px;overflow:hidden;'));
 assert.ok(css.includes('.message-warning{'));
});

test('X3: before the run, the run the six-run limit would drop, with Pin Run N; the limit is unchanged',async()=>{
 const W=await import(STATIC+'workspace-workflow.mjs'),N=await import(STATIC+'workspace-notebook.mjs');
 const shape={name:'Core',type:'rect',material:'Silicon',x:-350,y:0,w:700,h:300};
 const run=(n,extra={})=>({job:String(n).padStart(8,'0'),number:n,settings:{mode_count:4},input:{model:{shapes:[shape]}},...extra});
 const five=[1,2,3,4,5].map(n=>run(n));
 assert.equal(W.nextDropped(five),null);
 const six=[run(1,{pinned:true}),run(2,{pinned:true}),run(3),run(4),run(5),run(6)];
 assert.equal(W.nextDropped(six).number,3);
 assert.equal(W.dropWarningText(W.nextDropped(six)),'Running drops Run 3 (700 × 300 nm · 4 modes) · pin it to keep it');
 assert.equal(W.dropWarningText(run(3,{label:'Design A'})),'Running drops Run 3 · Design A (700 × 300 nm · 4 modes) · pin it to keep it');
 assert.equal(W.nextDropped(six.map(r=>({...r,pinned:true}))),null);
 // the run it names is the one appendRun drops
 const next=N.appendRun(six,run(7));assert.deepEqual(six.filter(r=>!next.includes(r)).map(r=>r.number),[3]);
 // the words after the drop are unchanged
 assert.equal(W.droppedRunText(run(3)),'Run 3 (700 × 300 nm · 4 modes) was dropped: up to six runs are kept; pin a run to keep it.');
 const app=read('workspace-app.mjs');
 assert.ok(app.includes("pin.onclick=()=>{if(!runs.includes(run)||run.pinned)return;run.pinned=true;render();notice(pinNotice(run));};"));
 assert.ok(app.includes("pin.disabled=solverBusy||!!pendingJob;"));
 assert.ok(read('workspace.html').includes('<span id="run-drop" class="run-drop" hidden><span id="run-drop-text" class="run-drop-text"></span><button type="button" id="run-drop-pin" class="message-action"></button></span>'));
});

test('X9: under a closed run\'s edge note, Use Open boundary and Find M modes set the input and run nothing',()=>{
 const app=read('workspace-app.mjs');
 // M = the run's Modes to find + 2, at most the maximum (8)
 assert.ok(app.includes("const find=Math.min(runModeCount(run)+2,MODE_COUNT_RANGE[1])"));
 assert.ok(app.includes("b.textContent='Use Open boundary';b.onclick=()=>{if(!state.openBoundary)setOuterBoundary(true);};"));
 assert.ok(app.includes("b.textContent=`Find ${find} modes`;b.onclick=()=>{if(state.modeCount>=find)return;state.modeCount=find;render();notice(editNoticeText('modeCount',find,{afterResult:resultNotice}));};"));
 // each is left out when the current inputs already have it; the note's own text is unchanged
 assert.ok(app.includes("if(!state.openBoundary){const b=document.createElement('button')")&&app.includes("if(state.modeCount<find){const b=document.createElement('button')"));
 assert.ok(app.includes("tr.className='edge-note-row edge-actions-row'"));
 // the radio and the button share one route, with the boundary message (and the X2 warning)
 assert.ok(app.includes("const open=radio.value==='open'&&radio.checked;if(open===!!state.openBoundary)return;setOuterBoundary(open);});"));
 // neither runs anything
 const body=app.slice(app.indexOf('// round 18 (X9): in a row under the last edge note'),app.indexOf("const help=document.createElement('p');help.className='table-note';help.textContent=`Polarization:"));
 assert.ok(!body.includes('runOptical')&&!body.includes("$('run-optical').click"),body);
});

test('X7: a restore offer whose project file holds the other model too lists it with its runs',async()=>{
 const A=await import(STATIC+'workspace-applications.mjs');
 const file='design-ab.json',also=[{model:'Heated silicon waveguide',names:['Run 1'],runs:1,inTab:false}];
 assert.equal(A.cardResumeChoice({runs:2,names:['Run 1 · Design A','Run 2 · Design B'],file,fileCurrent:true,fileSavedAt:'S',savedAt:'T',also},'Optical waveguide',()=>'9:24 PM').label,
  'Restore from this browser · Optical waveguide · Run 1 · Design A, Run 2 · Design B · same as file design-ab.json, saved 9:24 PM · also in this project: Heated silicon waveguide · Run 1 (restored separately)');
 assert.equal(A.sessionLine({model:'Heated silicon waveguide',runs:1,names:['Run 1'],file,also:[{model:'Optical waveguide',names:[],runs:2,inTab:true}]}),
  'Heated silicon waveguide · 1 run · Run 1 · file design-ab.json · also in this project: Optical waveguide · 2 runs (already in this tab)');
 // without another model the words are as before
 assert.equal(A.cardResumeChoice({runs:1,names:['Run 1'],savedAt:'T'},'Optical waveguide',()=>'2:25 PM').label,'Restore from this browser · Optical waveguide · Run 1 · 2:25 PM');
 const app=read('workspace-app.mjs');
 assert.ok(app.includes("const also=name?projectAlso(recovered,name):[];"));
 assert.ok(app.includes("(e.file||e.recovered.savedFile?.name||e.recovered.openedFile)===name"));
});
