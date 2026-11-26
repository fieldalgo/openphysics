// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
// Round 21: usability fixes of the optical and heated models. Plain text comparison only: no
// RegExp is built from a dynamic string.
const test=require('node:test');const assert=require('node:assert/strict');
const fs=require('node:fs');const path=require('node:path');
const STATIC='../../packages/simcase/src/simcase/studio/static/';
const read=name=>fs.readFileSync(path.join(__dirname,STATIC,name),'utf8');

const shape={type:'rect',name:'Core',material:'Silicon',x:-350,y:0,w:700,h:300};
const run=(n,extra={})=>({job:String(n).padStart(8,'0'),number:n,label:'',pinned:false,settings:{mode_count:4},input:{model:{shapes:[shape]}},...extra});

test('W2: the runs the next result drops, and the words before, during and after the run',async()=>{
 const W=await import(STATIC+'workspace-workflow.mjs'),N=await import(STATIC+'workspace-notebook.mjs');
 const five=[1,2,3,4,5].map(n=>run(n));
 assert.deepEqual(W.droppedBy(five),[]);
 const six=[run(1,{pinned:true}),run(2),run(3),run(4),run(5),run(6)];
 assert.deepEqual(W.droppedBy(six).map(r=>r.number),[2]);
 // the run droppedBy names is the one appendRun drops (the optical limit, 20 runs)
 const twenty=[run(1,{pinned:true}),...Array.from({length:19},(_,i)=>run(i+2))];
 assert.deepEqual(W.droppedBy(twenty,N.RUN_LIMIT).map(r=>r.number),[2]);
 const next=N.appendRun(twenty,run(21));assert.deepEqual(twenty.filter(r=>!next.includes(r)).map(r=>r.number),[2]);
 assert.deepEqual(W.droppedBy(six.map(r=>({...r,pinned:true}))),[]);
 // before the run (unchanged), while it computes, after the result
 assert.equal(W.dropWarningText(W.droppedBy(six)[0]),'If you run: drops Run 2 (closed · 4 modes · 700 × 300 nm) · pin it to keep it');
 assert.equal(W.dropWhileRunningText(W.droppedBy(six)),'When this run finishes, Run 2 (closed · 4 modes · 700 × 300 nm) is dropped');
 assert.equal(W.droppedAfterText([run(2)]),'Run 2 (closed · 4 modes · 700 × 300 nm) was dropped');
 assert.equal(W.dropWhileRunningText([run(2,{label:'Design A'})]),'When this run finishes, Run 2 · Design A (closed · 4 modes · 700 × 300 nm) is dropped');
 // two runs (a list the words also take), and the heated model's names
 assert.equal(W.dropWhileRunningText([run(1),run(3)]),'When this run finishes, Run 1 (closed · 4 modes · 700 × 300 nm) and Run 3 (closed · 4 modes · 700 × 300 nm) are dropped');
 assert.equal(W.droppedAfterText([run(1),run(3)]),'Run 1 (closed · 4 modes · 700 × 300 nm) and Run 3 (closed · 4 modes · 700 × 300 nm) were dropped');
 const heated=r=>`Run ${r.number} (run at 05:31 AM)`;
 assert.equal(W.dropWarningText(run(3),heated),'If you run: drops Run 3 (run at 05:31 AM) · pin it to keep it');
 assert.equal(W.dropWhileRunningText([run(3)],heated),'When this run finishes, Run 3 (run at 05:31 AM) is dropped');
 assert.equal(W.droppedAfterText([run(3)],heated),'Run 3 (run at 05:31 AM) was dropped');
});

test('W2: Keep Run N swaps with the oldest other unpinned run; none, no button; never seven runs',async()=>{
 const W=await import(STATIC+'workspace-workflow.mjs'),N=await import(STATIC+'workspace-notebook.mjs');
 // the optical limit: 20 runs and a 21st result
 const twenty=[run(1,{pinned:true}),run(2),run(3,{pinned:true}),...Array.from({length:17},(_,i)=>run(i+4))],seventh=run(7),newest=run(21);
 const next=N.appendRun(twenty,newest),dropped=twenty.filter(r=>!next.includes(r));
 assert.deepEqual(dropped.map(r=>r.number),[2]);
 const other=W.swapCandidate(next,newest);assert.equal(other.number,4);
 assert.equal(W.keepInsteadLabel(dropped[0],other),'Keep Run 2, drop Run 4 (closed · 4 modes · 700 × 300 nm) instead');
 assert.equal(W.keepInsteadLabel({...dropped[0],label:'Design A'},other),'Keep Run 2 · Design A, drop Run 4 (closed · 4 modes · 700 × 300 nm) instead');
 const swapped=W.swapDropped(next,dropped[0],other);
 assert.deepEqual(swapped.map(r=>r.number),[1,2,3,...Array.from({length:17},(_,i)=>i+5)]);assert.equal(swapped.length,20);
 assert.equal(W.keptInsteadText(dropped[0],other),'Run 2 (closed · 4 modes · 700 × 300 nm) is back; Run 4 (closed · 4 modes · 700 × 300 nm) was dropped instead.');
 const heated=r=>`Run ${r.number} (run at 05:31 AM)`;
 assert.equal(W.keepInsteadLabel(dropped[0],other,heated),'Keep Run 2, drop Run 4 (run at 05:31 AM) instead');
 assert.equal(W.keptInsteadText(dropped[0],other,heated),'Run 2 (run at 05:31 AM) is back; Run 4 (run at 05:31 AM) was dropped instead.');
 // no other unpinned run besides the new result: no swap
 const pinned=[run(1),...Array.from({length:19},(_,i)=>run(i+2,{pinned:true}))];
 const after=N.appendRun(pinned,newest);assert.equal(W.swapCandidate(after,newest),null);
 // the heated list keeps 20 too (run retention, H1)
 const M=await import(STATIC+'workspace-multiphysics-session.mjs');
 const heatedTwenty=Array.from({length:20},(_,i)=>run(i+1)),heatedNext=M.appendMultiphysicsRun(heatedTwenty,newest);
 assert.equal(W.swapDropped(heatedNext,heatedTwenty[0],W.swapCandidate(heatedNext,newest)).length,20);
});

test('W2: Run study starts at once; the swap is offered, checked when pressed and stale after the next run',()=>{
 const app=read('workspace-app.mjs'),view=read('workspace-multiphysics-view.mjs');
 // no question before the run: validation follows the input checks
 assert.ok(app.includes(" try{rejectInvalidInput();}catch(e){notice(e.message);return;}\n // round 21 (W2): no question before the run; a swap offered after the last drop ends here\n dropSwap=null;\n const operation=++jobOperation;"));
 // the line during the run, and Pin enabled then
 assert.ok(app.includes("const text=running?dropWhileRunningText(list):dropWarningText(list.length>1?list:run);"));
 // the offer: one run dropped and another unpinned run besides the new result
 assert.ok(app.includes("{const other=dropped.length===1?swapCandidate(runs,solverRun):null;dropSwap=other?{kept:dropped[0],other,newest:solverRun,list:runs}:null;}"));
 assert.ok(app.includes("if(state.phase==='done')announceResult(state.message,swapAction());"));
 // a stale button (the next run started, the list replaced, the other run pinned or gone) does nothing and is removed
 assert.ok(app.includes("const fresh=offer===dropSwap&&runs===offer.list&&runs.includes(offer.newest)&&!runs.includes(offer.kept)&&swapCandidate(runs,offer.newest)===offer.other&&!solverBusy&&!pendingJob;"));
 assert.ok(app.includes("dropSwap=null;if(!fresh){button?.remove();return;}"));
 // the heated model: the same, with its own names
 assert.ok(view.includes("const dropName=r=>`${runTitle(r)} (run at ${runTime(r)})`;"));
 assert.ok(view.includes("starting=true;if(!alone){stopAsked=false;dropSwap=null;}refreshRun();"));
 // round 22 (V4): the dropped words say why no swap is offered when every other earlier run is pinned
 assert.ok(view.includes("(droppedWords?' '+droppedWords:''),swapAction());"));
 assert.ok(view.includes("const fresh=offer===dropSwap&&runs===offer.list&&runs.includes(offer.newest)&&!runs.includes(offer.kept)&&swapCandidate(runs,offer.newest)===offer.other&&!job&&!starting;"));
 assert.ok(read('workspace.html').includes('<span id="mp-run-drop" class="run-drop mp-run-drop" hidden><span id="mp-run-drop-text" class="run-drop-text"></span><button type="button" id="mp-run-drop-pin" class="message-action"></button></span>'));
});

test('W3: run labels name the mode count when not 2 and n_g when the group index was computed',async()=>{
 const C=await import(STATIC+'workspace-compare.mjs'),N=await import(STATIC+'workspace-notebook.mjs');
 assert.equal(C.STUDY_DEFAULT_MODES,N.DEFAULT_MODE_COUNT);
 const core={type:'rect',name:'Core',material:'Silicon',x:-250,y:0,w:500,h:220},substrate={type:'rect',name:'Substrate',material:'Silicon',x:-1500,y:-700,w:3000,h:700};
 const model={shapes:[core,substrate],wavelength:1550},open={boundary:'PML',pml:{thickness:'1000 nm'}};
 // P05's two runs: the same design, one with the group index
 assert.equal(C.runDesign({input:{model},settings:{...open,mode_count:2}}),'open (PML 1 µm) · Core 500 × 220 + Substrate 3000 × 700 nm · Silicon');
 assert.equal(C.runDesign({input:{model},settings:{...open,mode_count:2},group_index:[4.1,4.0]}),'open (PML 1 µm) · n_g · Core 500 × 220 + Substrate 3000 × 700 nm · Silicon');
 assert.equal(C.runDesign({input:{model},settings:{...open,mode_count:4},group_index:[4.1,4.0,3.9,3.8]}),'open (PML 1 µm) · 4 modes · n_g · Core 500 × 220 + Substrate 3000 × 700 nm · Silicon');
 assert.equal(C.runDesign({input:{model:{shapes:[core]}},settings:{mode_count:1}}),'closed · 1 mode · 500 × 220 nm · Silicon');
 // after the boundary tag of a closed-window search (slice C2)
 assert.equal(C.runDesign({input:{model:{shapes:[core]}},settings:{mode_count:4,search_target:2.46},group_index:[1,1,1,1]}),'closed near 2.46 · 4 modes · n_g · 500 × 220 nm · Silicon');
 // a run without settings (an earlier file) or without the group index keeps its words
 assert.equal(C.runDesign({input:{model:{shapes:[core]}}}),'closed · 500 × 220 nm · Silicon');
 // the headings of Compare carry the same words
 assert.equal(C.runHeading({label:'',input:{model},settings:{mode_count:4},group_index:[1,1,1,1]},7),'Run 7 · closed · 4 modes · n_g · Core 500 × 220 + Substrate 3000 × 700 nm · Silicon · λ 1550 nm');
 assert.equal(C.fieldHeading('B',{label:'',input:{model},settings:{mode_count:3}},7),'B · Run 7 · closed · 3 modes · Core 500 × 220 + Substrate 3000 × 700 nm · Silicon · λ 1550 nm');
 // the run list and the pickers use runDesign before the wavelength and time; the full label is the picker's title
 const app=read('workspace-app.mjs');
 assert.ok(app.includes('${runDesign(run)} · λ ${run.input.model.wavelength} nm · ${runTime(run)}'));
 assert.ok(app.includes("o.textContent=runLabel(r);o.title=o.textContent;"));
});

test('W4: the pair offer does not list the other model again; an older entry names no other runs',async()=>{
 const A=await import(STATIC+'workspace-applications.mjs');const t=x=>x;
 const file='both-models.json';
 // P03/P04: the newest offer restores the pair; the heated record of the same file and time is not listed again
 const optical={runs:6,model:'Optical waveguide',names:[],savedAt:'2026-11-24T11:40:00Z',file,fileCurrent:false,
  pair:{model:'Heated silicon waveguide',runs:2,savedAt:'2026-11-24T11:33:00Z'},also:[{model:'Heated silicon waveguide',names:['Run 1','Run 2'],runs:2,inTab:false}]};
 const heated={runs:2,model:'Heated silicon waveguide',names:['Run 1','Run 2'],savedAt:'2026-11-24T11:33:00Z',file,fileCurrent:false,index:0,
  also:[{model:'Optical waveguide',names:['Run 1','Run 2','Run 3','Run 4','Run 5','Run 6'],runs:6,inTab:false}]};
 const older={runs:1,model:'Optical waveguide',names:['Run 1'],savedAt:'2026-11-24T11:20:00Z',file,fileCurrent:false,index:1,
  also:[{model:'Heated silicon waveguide',names:['Run 1','Run 2'],runs:2,inTab:false}]};
 const choices=A.resumeChoices(optical,[heated,older],t);
 // after rounds 26–30: the pair's second record is listed neither as the other piece of work nor as
 // an earlier copy; the older optical record is an earlier copy
 assert.equal(choices.newest.label,'Restore newest from this browser: Optical waveguide (6 runs) and Heated silicon waveguide (2 runs)');
 assert.equal(choices.other,null);
 assert.deepEqual(choices.earlier.map(c=>[c.label,c.detail]),[['Restore Optical waveguide · 1 run · Run 1','Older copy · kept in this browser 2026-11-24T11:20:00Z · last linked to both-models.json']]);
 // a heated record of another time or file is a different record: it stays, without "also in this project"
 const other={...heated,savedAt:'2026-11-24T11:10:00Z'};
 assert.equal(A.resumeChoices(optical,[other],t).earlier[0].label,'Restore Heated silicon waveguide · 2 runs · Run 1, Run 2');
 // without the pair (the tab holds runs of one model) the other entry stays, and an older one drops "also"
 const {pair,...single}=optical;
 const unpaired=A.resumeChoices(single,[heated],t);
 assert.equal(unpaired.other.label,'Restore from this browser: Heated silicon waveguide · 2 runs · Run 1, Run 2');
 assert.equal(unpaired.other.detail,'Older · kept in this browser 2026-11-24T11:33:00Z · newer than both-models.json as opened');
 // "(restored separately)" is shown nowhere
 for(const c of [choices,unpaired])for(const x of [c.newest,c.other,...c.earlier].filter(Boolean))assert.ok(!(x.label+x.detail).includes('restored separately'),x.label);
 // cards are unchanged: an older card still names the project's other model
 assert.ok(A.cardResumeChoice(heated,'Heated silicon waveguide',t,{older:true}).label.includes(' · also in this project: Optical waveguide · '));
 // the caller carries the other record's save time with the pair
 assert.ok(read('workspace-app.mjs').includes("pair:{model:o.model,runs:o.runs,savedAt:o.record.savedAt,fileCurrent:o.record.fileCurrent}"));
});

test('W5: the drop line is hidden beside "No need to run" and returns when the inputs differ from every run',()=>{
 const app=read('workspace-app.mjs'),view=read('workspace-multiphysics-view.mjs');
 // the same test as the "No need to run" offer (offerMatchingRun): a run of these exact inputs
 assert.ok(app.includes("const sig=signature(),run=runs.findLast(r=>r.signature===sig);if(!run)return;"));
 assert.ok(app.includes("const matched=!running&&!numericDrafts.invalid&&runs.some(r=>r.signature===signature());"));
 assert.ok(app.includes("const host=$('run-drop'),run=matched?null:list[0]||null;host.hidden=!run;"));
 // during a run the while-line shows whatever the inputs
 assert.ok(app.includes("const text=running?dropWhileRunningText(list):"));
 // the heated model: a kept run of the current model
 assert.ok(view.includes("const matched=!running&&runs.some(x=>runFreshness(x,doc)==='current'),r=active&&!matched?list[0]||null:null;"));
});
