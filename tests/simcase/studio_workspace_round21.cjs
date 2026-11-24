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
 // the run droppedBy names is the one appendRun drops
 const next=N.appendRun(six,run(7));assert.deepEqual(six.filter(r=>!next.includes(r)).map(r=>r.number),[2]);
 assert.deepEqual(W.droppedBy(six.map(r=>({...r,pinned:true}))),[]);
 // before the run (unchanged), while it computes, after the result
 assert.equal(W.dropWarningText(W.droppedBy(six)[0]),'If you run: drops Run 2 (700 × 300 nm · 4 modes) · pin it to keep it');
 assert.equal(W.dropWhileRunningText(W.droppedBy(six)),'When this run finishes, Run 2 (700 × 300 nm · 4 modes) is dropped');
 assert.equal(W.droppedAfterText([run(2)]),'Run 2 (700 × 300 nm · 4 modes) was dropped');
 assert.equal(W.dropWhileRunningText([run(2,{label:'Design A'})]),'When this run finishes, Run 2 · Design A (700 × 300 nm · 4 modes) is dropped');
 // two runs (a list the words also take), and the heated model's names
 assert.equal(W.dropWhileRunningText([run(1),run(3)]),'When this run finishes, Run 1 (700 × 300 nm · 4 modes) and Run 3 (700 × 300 nm · 4 modes) are dropped');
 assert.equal(W.droppedAfterText([run(1),run(3)]),'Run 1 (700 × 300 nm · 4 modes) and Run 3 (700 × 300 nm · 4 modes) were dropped');
 const heated=r=>`Run ${r.number} (run at 05:31 AM)`;
 assert.equal(W.dropWarningText(run(3),heated),'If you run: drops Run 3 (run at 05:31 AM) · pin it to keep it');
 assert.equal(W.dropWhileRunningText([run(3)],heated),'When this run finishes, Run 3 (run at 05:31 AM) is dropped');
 assert.equal(W.droppedAfterText([run(3)],heated),'Run 3 (run at 05:31 AM) was dropped');
});

test('W2: Keep Run N swaps with the oldest other unpinned run; none, no button; never seven runs',async()=>{
 const W=await import(STATIC+'workspace-workflow.mjs'),N=await import(STATIC+'workspace-notebook.mjs');
 const six=[run(1,{pinned:true}),run(2),run(3,{pinned:true}),run(4),run(5),run(6)],seventh=run(7);
 const next=N.appendRun(six,seventh),dropped=six.filter(r=>!next.includes(r));
 assert.deepEqual(dropped.map(r=>r.number),[2]);
 const other=W.swapCandidate(next,seventh);assert.equal(other.number,4);
 assert.equal(W.keepInsteadLabel(dropped[0],other),'Keep Run 2, drop Run 4 (700 × 300 nm · 4 modes) instead');
 assert.equal(W.keepInsteadLabel({...dropped[0],label:'Design A'},other),'Keep Run 2 · Design A, drop Run 4 (700 × 300 nm · 4 modes) instead');
 const swapped=W.swapDropped(next,dropped[0],other);
 assert.deepEqual(swapped.map(r=>r.number),[1,2,3,5,6,7]);assert.equal(swapped.length,6);
 assert.equal(W.keptInsteadText(dropped[0],other),'Run 2 (700 × 300 nm · 4 modes) is back; Run 4 (700 × 300 nm · 4 modes) was dropped instead.');
 const heated=r=>`Run ${r.number} (run at 05:31 AM)`;
 assert.equal(W.keepInsteadLabel(dropped[0],other,heated),'Keep Run 2, drop Run 4 (run at 05:31 AM) instead');
 assert.equal(W.keptInsteadText(dropped[0],other,heated),'Run 2 (run at 05:31 AM) is back; Run 4 (run at 05:31 AM) was dropped instead.');
 // no other unpinned run besides the new result: no swap
 const pinned=[run(1),run(2,{pinned:true}),run(3,{pinned:true}),run(4,{pinned:true}),run(5,{pinned:true}),run(6,{pinned:true})];
 const after=N.appendRun(pinned,seventh);assert.equal(W.swapCandidate(after,seventh),null);
 // the heated list keeps six too
 const M=await import(STATIC+'workspace-multiphysics-session.mjs');
 const heatedSix=[1,2,3,4,5,6].map(n=>run(n)),heatedNext=M.appendMultiphysicsRun(heatedSix,seventh);
 assert.equal(W.swapDropped(heatedNext,heatedSix[0],W.swapCandidate(heatedNext,seventh)).length,6);
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
 assert.ok(view.includes("(dropped.length?' '+droppedAfterText(dropped,dropName):''),swapAction());"));
 assert.ok(view.includes("const fresh=offer===dropSwap&&runs===offer.list&&runs.includes(offer.newest)&&!runs.includes(offer.kept)&&swapCandidate(runs,offer.newest)===offer.other&&!job&&!starting;"));
 assert.ok(read('workspace.html').includes('<span id="mp-run-drop" class="run-drop mp-run-drop" hidden><span id="mp-run-drop-text" class="run-drop-text"></span><button type="button" id="mp-run-drop-pin" class="message-action"></button></span>'));
});
