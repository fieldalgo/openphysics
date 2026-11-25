// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
// Round 23: usability fixes of the optical model (E1 to E6, pre-registered P1 to P6).
// Plain text comparison only: no RegExp is built from a dynamic string.
const test=require('node:test');const assert=require('node:assert/strict');
const fs=require('node:fs');const path=require('node:path');
const STATIC='../../packages/simcase/src/simcase/studio/static/';
const read=name=>fs.readFileSync(path.join(__dirname,STATIC,name),'utf8');
const body=(text,from,to)=>{const a=text.indexOf(from),b=text.indexOf(to,a+from.length);assert.ok(a>=0&&b>a,from);return text.slice(a,b);};

const CORE={name:'Core',type:'rect',material:'Silicon',x:-250,y:0,w:500,h:220};
const SUBSTRATE={name:'Substrate',type:'rect',material:'Silicon',x:-1500,y:-1200,w:3000,h:700};
test('P1 (E1): the plan line row says the short form; Optical modes keeps the full sentence',async()=>{
 const M=await import(STATIC+'workspace-modes.mjs');
 const t18=M.edgeSlabRisk([CORE,SUBSTRATE]);
 assert.equal(M.edgeSlabShortText(t18),'Substrate touches the window edge: in a closed window its slab modes come first.');
 assert.equal(M.edgeSlabShortText({edge:'Wafer',core:'Rib'}),'Wafer touches the window edge: in a closed window its slab modes come first.');
 assert.equal(M.edgeSlabWarningText(t18),"Substrate touches the window edge and its index is as high as Core's: in a closed window its slab modes come first.");
 const app=read('workspace-app.mjs'),row=body(app,'function refreshEdgeWarning(){','\n}');
 // the row: the short words, the full sentence as its title, both buttons
 assert.ok(row.includes("const text=edgeSlabShortText(risk),key=text+'\\n'+defaultTarget(state.shapes);"));
 assert.ok(row.includes("$('run-edge-text').textContent=text;$('run-edge-text').title=edgeSlabWarningText(risk);"));
 assert.ok(row.includes("host.append(...edgeWarningButtons('run-edge'));"));
 // the panel: the full sentence
 assert.ok(app.includes('<p class="validation-warning" id="closed-edge-warning-text">${escapeHtml(edgeSlabWarningText(risk))}</p>'));
});

test('P1 (E1): the row wraps and is never cut: no line clamp, no ellipsis, the box grows',()=>{
 const css=read('workspace.css'),rule=sel=>{const a=css.indexOf(sel+'{');assert.ok(a>=0,sel);return css.slice(a,css.indexOf('}',a));};
 assert.equal(rule('.run-edge'),'.run-edge{display:flex;flex-wrap:wrap;align-items:center;gap:2px 4px;min-width:0;color:#8a4b00');
 const text=rule('.run-edge-text');
 for(const cut of ['line-clamp','overflow:hidden','text-overflow','nowrap'])assert.ok(!text.includes(cut),cut);
 assert.equal(rule('.run-options.edge-warning'),'.run-options.edge-warning{height:auto;min-height:50px;overflow:visible');
 // on a phone the box fits the screen beside Run study (it was 460 px wide in a 390 px window)
 assert.ok(css.includes('@media(max-width:600px){.run-options{width:280px}}'));
 // nothing else clamps or cuts the row's words
 assert.ok(!css.includes('.run-edge-text{-webkit-line-clamp')&&!css.includes('.dropping .run-edge-text'));
});

// E4: three runs as the run list names them (runDesign) and as the drop words name them
const model=shapes=>({wavelength:1550,coreMesh:30,shapes});
const STRIP=[{name:'Core',type:'rect',material:'Silicon',x:-300,y:0,w:600,h:300}];
const E4_RUNS=[
 {number:4,input:{model:model(STRIP)},settings:{boundary:'PEC',mode_count:2},group_index:[4.2,4.1]},
 {number:5,input:{model:model(STRIP)},settings:{boundary:'PML',pml:{thickness:'1000 nm'},mode_count:2}},
 {number:6,input:{model:model([CORE,SUBSTRATE])},settings:{boundary:'PEC',mode_count:4,search_target:2.46}}];
test('P4 (E4): the drop line, the dropped words, the swap button and the Pin notice name a run with the run list\'s parts',async()=>{
 const W=await import(STATIC+'workspace-workflow.mjs'),C=await import(STATIC+'workspace-compare.mjs');
 const [ng,open,near]=E4_RUNS;
 assert.equal(W.dropName(ng),'Run 4 (closed · n_g · 600 × 300 nm)');
 assert.equal(W.dropName(open),'Run 5 (open (PML 1 µm) · 600 × 300 nm)');
 assert.equal(W.dropName(near),'Run 6 (closed near 2.46 · 4 modes · Core 500 × 220 + Substrate 3000 × 700 nm)');
 assert.equal(W.dropName({...ng,label:'Design A'}),'Run 4 · Design A (closed · n_g · 600 × 300 nm)');
 // the same parts, in the same order, as the run list's label (runDesign), without the material
 for(const run of E4_RUNS){const label=C.runDesign(run),parts=W.dropParts(run);
  assert.ok(label.startsWith(parts.slice(0,parts.lastIndexOf(' · '))+' · '),label);
  assert.ok(label.includes(' · '+parts.slice(parts.lastIndexOf(' · ')+3)),label);}
 // each of the four places
 assert.equal(W.dropWarningText(ng),'If you run: drops Run 4 (closed · n_g · 600 × 300 nm) · pin it to keep it');
 assert.equal(W.dropWhileRunningText([open]),'When this run finishes, Run 5 (open (PML 1 µm) · 600 × 300 nm) is dropped');
 assert.equal(W.droppedAfterText([ng]),'Run 4 (closed · n_g · 600 × 300 nm) was dropped');
 assert.equal(W.droppedRunText(near),'Run 6 (closed near 2.46 · 4 modes · Core 500 × 220 + Substrate 3000 × 700 nm) was dropped: up to six runs are kept; pin a run to keep it.');
 assert.equal(W.droppedNoSwapText([open]),'Run 5 (open (PML 1 µm) · 600 × 300 nm) was dropped; every other earlier run is pinned, so no other run can be dropped instead');
 assert.equal(W.keepInsteadLabel(ng,open),'Keep Run 4, drop Run 5 (open (PML 1 µm) · 600 × 300 nm) instead');
 assert.equal(W.keptInsteadText(ng,near),'Run 4 (closed · n_g · 600 × 300 nm) is back; Run 6 (closed near 2.46 · 4 modes · Core 500 × 220 + Substrate 3000 × 700 nm) was dropped instead.');
 assert.equal(W.pinnedDropText({number:3},[ng]),'Run 3 pinned. If you run: drops Run 4 (closed · n_g · 600 × 300 nm) · pin it to keep it');
 assert.equal(W.pinnedDropText({number:3},[open,near],true),'Run 3 pinned. When this run finishes, Run 5 (open (PML 1 µm) · 600 × 300 nm) and Run 6 (closed near 2.46 · 4 modes · Core 500 × 220 + Substrate 3000 × 700 nm) are dropped');
 // the optical page uses the default name everywhere; the heated model keeps its own
 const app=read('workspace-app.mjs');
 assert.ok(app.includes("droppedNote=!dropped.length?'':swapCandidate(runs,solverRun)?droppedAfterText(dropped):droppedNoSwapText(dropped);"));
 assert.ok(app.includes('const next=droppedBy(runs,RUN_LIMIT);notice(next.length?pinnedDropText(run,next,solverBusy||!!pendingJob):pinNotice(run));};'));
 assert.ok(read('workspace-multiphysics-view.mjs').includes("const dropName=r=>`${runTitle(r)} (run at ${runTime(r)})`;"));
});

// E6: the line under a result names every input that enters studySignature when it differs
test('P6 (E6): Current inputs differ names the boundary, the search, n_g and Modes to find; "unchanged:" keeps the rest',async()=>{
 const W=await import(STATIC+'workspace-workflow.mjs');
 const strip={model:model(STRIP)},t18={model:model([CORE,SUBSTRATE])};
 const closed={input:strip,modeCount:2,groupIndex:false,pml:null,searchTarget:null};
 const line=(run,now)=>W.runInputsLine(...W.studyInputParts(run,now));
 // the default study on both sides: the line of round 16, unchanged
 assert.equal(line(closed,{...closed,input:t18}),'Current inputs differ from this run: this run 600 × 300 nm · Silicon, current Core 500 × 220 + Substrate 3000 × 700 nm · Silicon; unchanged: λ 1550 nm · core mesh 30 nm');
 assert.equal(line(closed,closed),'Result for the current inputs · 600 × 300 nm · Silicon · λ 1550 nm · core mesh 30 nm');
 // a closed n_g run against the current open boundary, Highest, 4 modes (round 23's T22 state)
 const open={input:t18,modeCount:4,groupIndex:false,pml:{open_edges:['left','right','bottom'],target:'2.460'},searchTarget:null};
 assert.equal(line({...closed,groupIndex:true},open),'Current inputs differ from this run: this run 600 × 300 nm · Silicon · closed window · highest n_eff · Modes to find 2 · group index on, current Core 500 × 220 + Substrate 3000 × 700 nm · Silicon · open boundary (PML 1 µm) on left, right and bottom · search near 2.46 · Modes to find 4 · group index off; unchanged: λ 1550 nm · core mesh 30 nm');
 // the PML thickness as the run kept it; the open edges named
 assert.equal(W.boundaryWords({open_edges:['bottom'],target:'2.460',thickness:'1000 nm'}),'open boundary (PML 1 µm) on bottom');
 assert.equal(W.boundaryWords({open_edges:['left','right'],target:'2.460',thickness:'500 nm'}),'open boundary (PML 0.5 µm) on left and right');
 // the closed-window search alone differs: named, the rest unchanged
 assert.equal(line({...closed,input:t18},{...closed,input:t18,searchTarget:2.46}),'Current inputs differ from this run: this run highest n_eff, current nearest to n_eff 2.46; unchanged: Core 500 × 220 + Substrate 3000 × 700 nm · Silicon · λ 1550 nm · core mesh 30 nm · closed window');
 // n_g alone, Modes to find alone
 assert.equal(line(closed,{...closed,groupIndex:true}),'Current inputs differ from this run: this run group index off, current group index on; unchanged: 600 × 300 nm · Silicon · λ 1550 nm · core mesh 30 nm');
 assert.equal(line({...closed,modeCount:4},closed),'Current inputs differ from this run: this run Modes to find 4, current Modes to find 2; unchanged: 600 × 300 nm · Silicon · λ 1550 nm · core mesh 30 nm');
 // the open target alone
 assert.equal(line(open,{...open,pml:{...open.pml,target:'2.300'}}),'Current inputs differ from this run: this run search near 2.46, current search near 2.3; unchanged: Core 500 × 220 + Substrate 3000 × 700 nm · Silicon · λ 1550 nm · core mesh 30 nm · open boundary (PML 1 µm) on left, right and bottom · Modes to find 4');
 // a moved shape (the geometry words the same): its position named
 const moved={model:model([{...STRIP[0],x:-200}])};
 assert.equal(line(closed,{...closed,input:moved}),'Current inputs differ from this run: this run at Core (-300, 0) nm, current at Core (-200, 0) nm; unchanged: 600 × 300 nm · Silicon · λ 1550 nm · core mesh 30 nm');
 // the page builds both sides from the run's settings and the page's study
 const app=read('workspace-app.mjs');
 assert.ok(app.includes('const runStudy=run=>({input:run.input,modeCount:runModeCount(run),groupIndex:run.group_index_method!==undefined,pml:isOpenRun(run)?run.settings.pml:null,searchTarget:runSearchTarget(run)});'));
 assert.ok(app.includes('const studyParts=run=>studyInputParts(runStudy(run),{input:current(),modeCount:state.modeCount,groupIndex:state.groupIndex===true,pml:pmlNow(),searchTarget:closedTargetNow()});'));
 assert.ok(app.includes('const [runParts,nowParts]=studyParts(solverRun);'));
});

// E2: a session over the limit. Browser recovery keeps the selected and pinned runs' fields, then as
// many others as fit, newest first (coordinator decision of round 23); the header and Messages name
// the runs whose fields it left out
const FIXTURES=path.join(__dirname,'studio_session_fixtures');
const OPEN_FULL='optical-v10-open-full-083e151.json';
const e2=async()=>{
 const N=await import(STATIC+'workspace-notebook.mjs'),R=await import(STATIC+'workspace-notebook-recovery.mjs'),PS=await import(STATIC+'workspace-persistence.mjs');
 const full=N.parseSession(fs.readFileSync(path.join(FIXTURES,OPEN_FULL),'utf8')),base=full.runs[0];
 const runs=[1,2,3].map(n=>({...base,job:'0000000'+n,number:n,pinned:false}));
 const size=k=>N.writeOpticalSession(full.input,runs.slice(0,k),'00000001',[null,null],full.view).bytes;
 return {N,R,PS,full,runs,one:size(1),two:N.writeOpticalSession(full.input,runs.slice(0,2),'00000001',[null,null],full.view).bytes,three:N.writeOpticalSession(full.input,runs,'00000001',[null,null],full.view).bytes};
};
const fieldsOf=text=>JSON.parse(text).runs.map(r=>!!r.field);
test('P2 (a) (E2): before the decision recovery dropped every field but the selected run\'s, though another fitted, and said nothing',async()=>{
 const {N,full,runs,two,three}=await e2();
 // a limit with room for two runs' fields of three (the stand-in for 16 MiB of a 22 MB session)
 const limit=Math.floor((two+three)/2);
 // round 22's recovery write: keepSelected alone, the selected run's field only
 const old=N.writeOpticalSession(full.input,runs,'00000003',[null,null],full.view,{keepSelected:true,limit});
 assert.equal(old.ok,true);assert.deepEqual(fieldsOf(old.text),[false,false,true]);assert.deepEqual(old.notKept,[1,2]);
 // Run 2's field would have fitted beside it
 const withTwo=N.writeOpticalSession(full.input,runs.slice(1),'00000003',[null,null],full.view).bytes;assert.ok(withTwo<=limit,`${withTwo} <= ${limit}`);
 // and the header had no words for it: "kept" alone
 const PS=await import(STATIC+'workspace-persistence.mjs');
 assert.equal(PS.projectTitle({models:1,recovery:'kept'}),'Untitled project · not saved to a file · kept for recovery in this browser');
});

test('P2 (b) (E2): over the limit recovery keeps the selected and pinned fields, then the newest others that fit, and names the rest',async()=>{
 const {N,R,PS,full,runs,two,three}=await e2();
 const limit=Math.floor((two+three)/2);
 // Run 3 selected: its field, then Run 2's (newest other) fits, Run 1's does not
 const make=N.captureSession(full.input,runs,'00000003',[null,null],full.view,{limit});
 const text=make();assert.ok(new TextEncoder().encode(text).length<=limit);
 assert.deepEqual(fieldsOf(text),[false,true,true]);assert.deepEqual(make.dropped,[1]);
 // Run 1 pinned, Run 3 selected: both kept first; Run 2 newest of the rest does not fit
 const pinned=runs.map(r=>r.number===1?{...r,pinned:true}:r);
 const make2=N.captureSession(full.input,pinned,'00000003',[null,null],full.view,{limit});
 assert.deepEqual(fieldsOf(make2()),[true,false,true]);assert.deepEqual(make2.dropped,[2]);
 // a larger limit keeps every field it can, newest first: all three at the full size
 const all=N.captureSession(full.input,runs,'00000001',[null,null],full.view,{limit:three});all();assert.deepEqual(all.dropped,[]);
 // the saved state carries the numbers; the header names them
 const states=[];const saver=new R.NotebookAutosave({save:async r=>r},{onState:s=>states.push(s),delay:0,setTimer:fn=>{fn();return 1;},clearTimer:()=>{}});
 saver.schedule('over',make);await saver.settle();
 assert.deepEqual(states.find(s=>s.phase==='saved').dropped,[1]);
 assert.equal(PS.projectTitle({models:1,recovery:'keptFields:3,5'}),'Untitled project · not saved to a file · kept for recovery in this browser without the fields of Run 3 and Run 5');
 assert.equal(PS.projectTitle({models:1,recovery:'keptFields:1'}),'Untitled project · not saved to a file · kept for recovery in this browser without the fields of Run 1');
 assert.equal(PS.projectTitle({models:1,recovery:'keptFields:1,2,4'}),'Untitled project · not saved to a file · kept for recovery in this browser without the fields of Run 1, Run 2 and Run 4');
 // File › Save still asks about the selected and pinned runs only (no fill)
 const save=N.writeOpticalSession(full.input,runs,'00000003',[null,null],full.view,{limit});
 assert.equal(save.ok,false);assert.deepEqual(save.reduced.kept,[3]);
 // the Messages line: what Save will offer, what the other runs keep, what recovery leaves out
 assert.equal(N.sessionSizeText({ok:false,bytes:22.0e6,reduced:{bytes:4e6,notKept:[1,2,3,4,5],kept:[6]},refusal:null},[1,2]),
  'Session is now 22.0 MB, over the 16.8 MB limit. Browser recovery keeps every run\'s values; the field plots of Run 1 and Run 2 are not kept. File › Save will ask whether to keep the field plots of the selected and pinned runs only (Run 6).');
 assert.equal(N.sessionSizeText({ok:false,bytes:18.0e6,reduced:{bytes:8e6,notKept:[1,2,3],kept:[4,5,6]},refusal:null},[]),
  'Session is now 18.0 MB, over the 16.8 MB limit. Browser recovery keeps every run\'s values and field plots. File › Save will ask whether to keep the field plots of the selected and pinned runs only (Runs 4, 5 and 6).');
 // the page: the snapshot's numbers, shown while recovery is kept, in the header and the indicator;
 // the line names recovery's runs from the same snapshot
 const app=read('workspace-app.mjs');
 assert.ok(app.includes("const opticalRecoveryShown=()=>recoveryState==='kept'&&!multiView.active()&&opticalRecoveryDropped.length?'keptFields:'+opticalRecoveryDropped.join(','):recoveryState;"));
 assert.ok(app.includes("opticalRecoveryDropped=recoveryKind==='optical'&&Array.isArray(state.dropped)?state.dropped:[];"));
 assert.ok(app.includes('recovery:opticalRecoveryShown(),copyOf:project.copyOf,recovered});'));
 assert.ok(app.includes('persistenceTitle({...saveIndicator,recovery:opticalRecoveryShown()})'));
 assert.ok(app.includes('text=sessionSizeText(writeOpticalSession(inputsFile(),runs,solverRun?.job||null,compareIds,currentView()),left);'));
 // the message wraps
 assert.ok(read('workspace.css').includes('#file-status{color:#7b8798;min-width:0;overflow-wrap:anywhere}'));
});

test('P2 (c) (E2): the record round-trips; a restore keeps the kept fields and names the runs without',async()=>{
 const {N,R,full,runs,two,three}=await e2();
 const limit=Math.floor((two+three)/2),make=N.captureSession(full.input,runs,'00000003',[null,null],full.view,{limit});
 const record={version:1,savedAt:'2026-11-24T21:00:00.000Z',session:make()};
 const back=R.readNotebookRecovery(record).session;
 assert.deepEqual(back.runs.map(r=>[r.number,!!r.field]),[[1,false],[2,true],[3,true]]);
 // the kept fields are the runs' own, value for value
 for(const n of [2,3])assert.deepEqual(JSON.parse(JSON.stringify(back.runs[n-1].field)),JSON.parse(JSON.stringify(runs[n-1].field)));
 // every run keeps its n_eff
 assert.deepEqual(back.runs.map(r=>JSON.stringify(r.effective_index)),runs.map(r=>JSON.stringify(r.effective_index)));
 assert.equal(N.fieldsNotKeptText(back.runs),' Fields not kept for Run 1; their n_eff, TE fractions and effective areas were.');
 assert.equal(N.fieldsNotKeptText(runs),'');
 // written again, the restored session keeps the same fields within the limit
 const again=N.captureSession(back.input,back.runs,back.selected,back.comparison,back.view,{limit});const text=again();
 assert.deepEqual(fieldsOf(text),[false,true,true]);assert.ok(new TextEncoder().encode(text).length<=limit);assert.deepEqual(again.dropped,[]);
 // the page: a browser restore appends it after its message; the Results line says where
 const app=read('workspace-app.mjs');
 assert.ok(app.includes("if(pending.source!=='file'&&pending.session){const missing=fieldsNotKeptText(runs);if(missing)$('file-status').append(missing);}"));
 assert.ok(app.includes("solverRun.origin==='recovered'?'This run’s fields were not kept in browser recovery (over 16 MiB): n_eff, the TE fractions and the effective areas were.'"));
});

test('P2 (d) (E2): below the limit recovery writes the same bytes as before',async()=>{
 const {N,full,runs}=await e2();
 // the limit exactly the full text's size, and the real 16 MiB
 const exact=N.writeOpticalSession(full.input,runs,'00000002',['00000001','00000003'],full.view).bytes;
 for(const limit of [exact,undefined]){
  const make=N.captureSession(full.input,runs,'00000002',['00000001','00000003'],full.view,limit===undefined?{}:{limit});
  const text=make();assert.deepEqual(make.dropped,[]);assert.deepEqual(fieldsOf(text),[true,true,true]);
  // the round-22 write (keepSelected, no fill) of the same runs gives the same text
  assert.equal(text,N.writeOpticalSession(full.input,runs,'00000002',['00000001','00000003'],full.view,{keepSelected:true,...(limit===undefined?{}:{limit})}).text);
 }
});

// E3: the estimate beside Run study with group index on, and Turn off group index
test('P3 (E3): an estimate from the last run with the same boundary: as is with n_g, × 3 without, none without such a run',async()=>{
 const W=await import(STATIC+'workspace-workflow.mjs');
 const kinds={isOpen:r=>r.open===true,hasGroup:r=>r.ng===true};
 const openNg={open:true,ng:true,duration:200000},open={open:true,ng:false,duration:68000},closed={open:false,ng:false,duration:8000},opened={open:true,ng:true};
 // a comparable run with n_g: its time
 assert.equal(W.groupIndexEstimate([closed,open,openNg],{open:true},kinds),200000);
 // the newest comparable run had no n_g: 3 times its time (68 s → 204 s; 199 s measured)
 assert.equal(W.groupIndexEstimate([openNg,closed,open],{open:true},kinds),204000);
 assert.equal(W.groupIndexEstimate([open,openNg,closed],{open:false},kinds),24000);
 // none: no run of the same boundary kind with a time measured in this tab (an opened run has none)
 assert.equal(W.groupIndexEstimate([closed,opened],{open:true},kinds),null);
 assert.equal(W.groupIndexEstimate([],{open:false},kinds),null);
 // the words
 assert.equal(W.runPlanText({open:true,searches:2,groupIndex:true,estimate:204000}),'Open boundary · 2 searches · group index on (3 solves) · about 3 min');
 assert.equal(W.runPlanText({open:true,searches:2,groupIndex:true,estimate:200000}),'Open boundary · 2 searches · group index on (3 solves) · about 3 min');
 assert.equal(W.runPlanText({open:false,groupIndex:true,estimate:24000}),'Closed window · group index on (3 solves) · about 20 s');
 assert.equal(W.runPlanText({open:true,searches:2,groupIndex:true,estimate:null}),'Open boundary · 2 searches · group index on (3 solves)');
 // with group index off: the round-18 words, unchanged
 assert.equal(W.runPlanText({open:true,searches:2,last:68000}),'Open boundary · 2 searches · last such run 1:08');
 assert.deepEqual([5000,24000,85000,95000,204000,239000].map(W.aboutText),['10 s','20 s','90 s','2 min','3 min','4 min']);
});

test('P3 (E3): Turn off group index beside the plan line turns the option off; the option stays an input',()=>{
 const app=read('workspace-app.mjs'),plan=body(app,'function refreshRunOptions(){','\n}');
 assert.ok(plan.includes('estimate=plan.groupIndex?groupIndexEstimate(runs,plan,kinds):null,text=runPlanText({...plan,last:plan.groupIndex?null:last?.duration??null,estimate});'));
 assert.ok(plan.includes('refreshGroupIndexOff(plan.groupIndex);'));
 const off=body(app,'function refreshGroupIndexOff(on){','\n}');
 assert.ok(off.includes("button.textContent='Turn off group index';button.onclick=turnOffGroupIndex;"));
 // shown while the option is on, removed while it is off
 assert.ok(off.includes("let button=$('run-plan-group-off');if(!on){button?.remove();return;}"));
 // the option's own edit, as its check box makes it, with its notice; render() refreshes the plan line
 assert.ok(app.includes('function turnOffGroupIndex(){if(state.groupIndex!==true)return;state.groupIndex=false;render();notice(groupIndexNotice(false));}'));
 assert.ok(app.includes("box.onchange=e=>{state.groupIndex=e.target.checked;render();notice(groupIndexNotice(state.groupIndex));};"));
 // no run resets it: the result handler does not touch the option
 const result=body(app,'},onResult:(result,pending)=>{','\n}});');assert.ok(!result.includes('state.groupIndex'));
 // the heated model has no group index: its line is unchanged
 assert.ok(!read('workspace-multiphysics-view.mjs').includes('groupIndexEstimate'));
});
