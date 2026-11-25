// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
// Job progress (round 25 A5, slice S3): the job panel names the step of a running optical job from the
// server's step (the latest search_started event of simcase.run's on_event), and Messages, the one
// live region, carries the same words without the time, so it changes only at the start, at each step,
// when the server stops or starts answering, and at the end (pre-registered J8 and the Node part of
// J10; the browser part is the OB template run of tools/studio_browser/studio_workspace_browser.mjs).
const {test,before}=require('node:test');const assert=require('node:assert/strict');
const fs=require('node:fs');const path=require('node:path');
const STATIC='../../packages/simcase/src/simcase/studio/static/';
let OpticalJobMonitor,stepText,NO_ANSWER_LIVE,snapshot;
before(async()=>{({OpticalJobMonitor,stepText,NO_ANSWER_LIVE}=await import(STATIC+'workspace-job.mjs'));({snapshot}=await import(STATIC+'workspace-project.mjs'));});
const record=extra=>({version:1,job:'1234abcd',serverInstance:'a'.repeat(32),serverVersion:'0.1.0',revision:3,startedAt:'2026-10-26T12:00:00Z',input:snapshot({width:500,height:300,electric:false,heat:false,structure:false,optics:true,voltage:1},{materials:{Core:'Silicon',Oxide:'Silica',Heater:''},temperature:293.15,cooling:'',fixed:'',terminal:''}),...extra});
const OPEN={openBoundary:{edges:{left:'open',right:'open',bottom:'open',top:'open'},target:2.46}};
const event=(solve,search,{solves=3,searches=2,point=1,points=1}={})=>({event:'search_started',point,points,solve,solves,solve_kind:solve===1?'study_point':'group_index',search,searches});

test('the words of every step shape, and none for one step in all or a step of another shape',()=>{
 assert.equal(stepText(event(1,1)),'solve 1 of 3 · search 1 of 2');
 assert.equal(stepText(event(2,1)),'solve 2 of 3 (group index) · search 1 of 2');
 assert.equal(stepText(event(3,2)),'solve 3 of 3 (group index) · search 2 of 2');
 assert.equal(stepText(event(1,1,{searches:1})),'solve 1 of 3');
 assert.equal(stepText(event(2,1,{searches:1})),'solve 2 of 3 (group index)');
 assert.equal(stepText(event(1,2,{solves:1})),'search 2 of 2');
 // one step in all: a closed run without group index, an open run of one search, a PML check job
 assert.equal(stepText(event(1,1,{solves:1,searches:1})),'');
 // a sweep's point has no words (Studio sends single studies)
 assert.equal(stepText(event(1,1,{solves:1,searches:1,point:2,points:5})),'');
 for(const bad of [undefined,null,'search 1',[],{},{...event(1,1),event:'search_finished'},{...event(1,1),solve:4},{...event(1,1),search:0},
  {...event(1,1),solves:'3'},{...event(1,1),solve:1.5},{...event(1,1),solve_kind:'other'},{...event(1,1),point:2}])assert.equal(stepText(bad),'',JSON.stringify(bad));
});

// the six searches of an open run with the group index, as the measured T16-like run made them
// (starts 2.72, 43.51, 73.26, 112.95, 140.87, 180.18 s; done at 207.93 s)
const STARTS=[2.72,43.51,73.26,112.95,140.87,180.18],DONE=207.93,ORDER=[[1,1],[1,2],[2,1],[2,2],[3,1],[3,2]];
const stepAt=s=>{let i=-1;for(let k=0;k<STARTS.length;k++)if(s>=STARTS[k])i=k;return i<0?null:event(...ORDER[i]);};

test('J8, J10: the panel shows the step right after the time; Messages changes at the start and at each of the 6 steps only',async()=>{
 const r=record(OPEN),start=Date.parse(r.startedAt);let t=start;const states=[];
 const m=new OpticalJobMonitor({api:async p=>{const s=(t-start)/1000;if(p.includes('/result?'))return {};return s<DONE?{status:'running',log:[],error:null,step:stepAt(s),has_result:false}:{status:'done',log:[],error:null,step:null,has_result:true};},
  now:()=>t,wait:async ms=>{t+=ms;},onState:s=>states.push(s)});
 await m.follow(r,r.serverInstance);
 const running=states.filter(s=>s.phase==='running');
 assert.ok(running.length>250);
 assert.equal(running[0].message,'Computing job 1234abcd · 0:00 · Open boundary · 2 modes · searches near 2.46 and 1.95');
 // the panel's order (J9 layout): time · step · what, in spans of their own
 const at=running.find(s=>s.message==='Computing job 1234abcd · 1:52 · solve 2 of 3 (group index) · search 1 of 2 · Open boundary · 2 modes · searches near 2.46 and 1.95');
 assert.ok(at);assert.deepEqual([at.parts,at.step],[{lead:'Computing job 1234abcd · 1:52',rest:'Open boundary · 2 modes · searches near 2.46 and 1.95'},'solve 2 of 3 (group index) · search 1 of 2']);
 // Messages: the panel's words without the time, so its text changes 1 (start) + 6 (steps) times
 const lives=running.map(s=>s.live),changes=lives.filter((l,i)=>i===0||l!==lives[i-1]);
 assert.deepEqual(changes,['','solve 1 of 3 · search 1 of 2','solve 1 of 3 · search 2 of 2','solve 2 of 3 (group index) · search 1 of 2','solve 2 of 3 (group index) · search 2 of 2',
  'solve 3 of 3 (group index) · search 1 of 2','solve 3 of 3 (group index) · search 2 of 2'].map(w=>'Computing job 1234abcd · Open boundary · 2 modes · searches near 2.46 and 1.95'+(w?' · '+w:'')));
 assert.ok(lives.every(l=>!/\d:\d\d/.test(l)),'the time never reaches the live words');
 assert.equal(states.at(-1).phase,'done');
});

test('J10: a silence of the server changes Messages twice, without the time',async()=>{
 const r=record(OPEN),start=Date.parse(r.startedAt);let t=start;const states=[];
 const m=new OpticalJobMonitor({api:async p=>{const s=(t-start)/1000;if(p.includes('/result?'))return {};if(s>=50&&s<70)throw Error('network');return s<DONE?{status:'running',step:stepAt(s)}:{status:'done',step:null};},
  now:()=>t,wait:async ms=>{t+=ms;},onState:s=>states.push(s)});
 await m.follow(r,r.serverInstance);
 const lives=states.filter(s=>s.phase==='running').map(s=>s.live),changes=lives.filter((l,i)=>i===0||l!==lives[i-1]);
 assert.equal(changes.length,1+6+2);
 assert.ok(changes.includes('Computing job 1234abcd · Open boundary · 2 modes · searches near 2.46 and 1.95 · solve 1 of 3 · search 2 of 2'+NO_ANSWER_LIVE));
 assert.equal(NO_ANSWER_LIVE,' · no answer from the server; still checking');
 // the panel keeps the time of the silence
 assert.ok(states.some(s=>/^Computing job 1234abcd · 0:5\d · solve 1 of 3 · search 2 of 2 · Open boundary · 2 modes · searches near 2\.46 and 1\.95 · no answer from the server for 0:\d\d; still checking$/.test(s.message||'')));
});

test('J8: an older server sends no step: the words are those before job progress',async()=>{
 const r=record(OPEN),start=Date.parse(r.startedAt);let t=start;const states=[];
 const m=new OpticalJobMonitor({api:async p=>p.includes('/result?')?{}:{status:t-start<200000?'running':'done'},now:()=>t,wait:async ms=>{t+=ms;},onState:s=>states.push(s)});
 await m.follow(r,r.serverInstance);
 const running=states.filter(s=>s.phase==='running');
 assert.ok(running.some(s=>s.message==='Computing job 1234abcd · 3:07 · Open boundary · 2 modes · searches near 2.46 and 1.95'));
 assert.ok(running.every(s=>s.step===''&&s.live==='Computing job 1234abcd · Open boundary · 2 modes · searches near 2.46 and 1.95'));
});

test('a job of one step in all (a closed run, a PML check job) keeps the words it had',async()=>{
 const r=record({...OPEN,checkOf:'abcdef12',checkIndex:0,checkCount:2}),start=Date.parse(r.startedAt);let t=start;const states=[];
 const m=new OpticalJobMonitor({api:async p=>p.includes('/result?')?{}:{status:t-start<5000?'running':'done',step:event(1,1,{solves:1,searches:1})},now:()=>t,wait:async ms=>{t+=ms;},onState:s=>states.push(s)});
 await m.follow(r,r.serverInstance);
 assert.ok(states.filter(s=>s.phase==='running').every(s=>/^Computing job 1234abcd · \d:\d\d · PML check · mode 1 of 2$/.test(s.message)&&s.live==='Computing job 1234abcd · PML check · mode 1 of 2'));
});

test('the page: Messages is written only when its words change; a recompute names the step after its words; the step has a span of its own',()=>{
 const app=fs.readFileSync(path.join(__dirname,STATIC,'workspace-app.mjs'),'utf8'),html=fs.readFileSync(path.join(__dirname,STATIC,'workspace.html'),'utf8'),css=fs.readFileSync(path.join(__dirname,STATIC,'workspace.css'),'utf8');
 assert.ok(html.includes('<span id="job-message"></span><span id="job-step"></span><span id="job-what"></span><span id="job-storage" role="status"></span>'));
 assert.ok(!/id="job-(step|what)"[^>]*(role|aria-live)=/.test(html),'the step is not a second live region');
 assert.ok(css.includes('#job-panel.has-step>#job-message,#job-panel>#job-step{flex:none;overflow:visible}'));
 assert.ok(css.includes('@media(max-width:660px),(min-width:1001px) and (max-width:1279px){'));
 assert.ok(app.includes("else if(state.live===undefined)notice(state.message);else if($('file-status').textContent!==state.live)notice(state.live);"));
 assert.ok(app.includes("const lead=recomputingText({...run,number:runNumber(run)}),text=lead+(state.phase==='running'&&state.step?' · '+state.step:'');state={...state,message:text,parts:{lead,rest:''},...(state.phase==='running'?{live:text}:{})};"));
 // the job panel keeps the words with the time; the run-plan line keeps the B5 estimate alone
 assert.ok(app.includes("$('job-message').textContent=state.message;"));
 assert.ok(!/about \$\{[^}]*\}[^;]*state\.step/.test(app));
});
