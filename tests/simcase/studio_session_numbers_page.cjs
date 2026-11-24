// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
// Stable run numbers and the project name after recovery, the page's part. Pre-registered: K6 (a
// seeded random sequence of at least 2000 steps: numbers strictly increasing in list order, no
// number given to two jobs, next = largest used + 1), K7 (the four header lines, and a pair restore
// whose records differ in name keeps the newer name) and K10 as amended (no numbering sentence for a
// version 7, 11 or 12 file). The format's part (K1-K3, K9) is in studio_session_numbers.cjs; the browser
// flows (K4, K5) are stages of tools/studio_browser/studio_project_browser.mjs.
const test=require('node:test');const assert=require('node:assert/strict');
const fs=require('node:fs');const path=require('node:path');
const STATIC='../../packages/simcase/src/simcase/studio/static/';
const FIX=path.join(__dirname,'studio_session_fixtures');
const fixture=name=>fs.readFileSync(path.join(FIX,name),'utf8');
const read=name=>fs.readFileSync(path.join(__dirname,STATIC,name),'utf8');
let N,P,W,PS,R,C;
test.before(async()=>{
 N=await import(STATIC+'workspace-notebook.mjs');P=await import(STATIC+'workspace-project.mjs');W=await import(STATIC+'workspace-workflow.mjs');
 PS=await import(STATIC+'workspace-persistence.mjs');R=await import(STATIC+'workspace-notebook-recovery.mjs');C=await import('./studio_session_fixtures/closed_sessions.mjs');
});
const VIEW={mode:0,component:'magnitude',window:'Core region'};

// a deterministic generator (mulberry32)
const random=seed=>()=>{seed|=0;seed=seed+0x6D2B79F5|0;let t=Math.imul(seed^seed>>>15,1|seed);t=t+Math.imul(t^t>>>7,61|t)^t;return((t^t>>>14)>>>0)/4294967296;};
// what the page does with its runs (workspace-app.mjs), on the modules' functions
function tab(base){
 const job=i=>i.toString(16).padStart(8,'0');
 // the result of job i is always the same run (a second tab that ran it holds the same result)
 const result=i=>N.validateRun({...base,job:job(i),completedAt:new Date(Date.UTC(2026,10,24,0,0,i)).toISOString()});
 const t={runs:[],used:0,swap:null,given:new Map()};
 const numbered=runs=>{for(const r of runs)t.given.set(r.number,t.given.get(r.number)??r.job);};
 t.result=i=>{ // a new result (the same job again keeps its number, at its place)
  const completed=result(i),prior=t.runs.find(r=>r.job===completed.job);if(prior)completed.number=prior.number;
  const used=W.numberRuns([completed],t.used);let appended;
  try{appended=N.appendRun(t.runs,completed);}catch{return 'all pinned';}
  t.used=used;const next=prior?W.inNumberOrder(appended):appended,dropped=t.runs.filter(r=>!next.includes(r)&&r.job!==completed.job);
  t.runs=next;numbered([completed]);
  const other=dropped.length===1?W.swapCandidate(t.runs,completed):null;t.swap=other?{kept:dropped[0],other}:null;
  // the same job again: its number and its place (inNumberOrder)
  if(prior){assert.equal(completed.number,prior.number);assert.equal(t.runs.findIndex(r=>r.job===completed.job),t.runs.findIndex(r=>r.number>=completed.number));return 'result again';}
  return 'result';
 };
 t.swapBack=()=>{if(!t.swap||!t.runs.includes(t.swap.other))return 'no swap';t.runs=W.swapDropped(t.runs,t.swap.kept,t.swap.other);t.swap=null;return 'swap';};
 t.pin=(k,on)=>{const r=t.runs[k%Math.max(1,t.runs.length)];if(!r)return 'no run';t.runs=t.runs.map(x=>x===r?{...x,pinned:on}:x);t.swap=null;return on?'pin':'unpin';};
 t.text=()=>N.sessionText(P.snapshot({width:500,voltage:1,electric:false,heat:false,structure:false,optics:true,wavelength:1550,coreMesh:30},{materials:{Core:'Silicon',Oxide:'Silica',Heater:''},temperature:293.15,cooling:'',fixed:'',terminal:''}),t.runs,t.runs.at(-1)?.job??null,[null,null],VIEW);
 // File › Open and Restore: the stored numbers (version 12) or 1..n (completeLoad)
 const load=session=>{for(const r of session.runs){const n=r.number;delete r.number;r.number=n;}t.runs=session.runs;t.used=W.numberRuns(t.runs);t.swap=null;};
 t.open=()=>{load(N.parseSession(t.text()));return 'open';};
 t.restore=()=>{const make=N.captureSession(N.parseSession(t.text()).input,t.runs,t.runs.at(-1)?.job??null,[null,null],VIEW);load(R.readNotebookRecovery({version:1,savedAt:'2026-11-24T10:00:00.000Z',session:make()}).session);return 'restore';};
 // Add runs from file: another tab's runs (jobs a..b), numbered after this tab's largest
 t.import=(ids,numbers)=>{
  const other=ids.map((i,k)=>Object.assign(result(i),{number:numbers[k]}));let text;
  try{text=N.sessionText(N.parseSession(t.text()).input,other,null,[null,null],VIEW);}catch{return 'not written';}
  const session=N.parseSession(text);let merged;try{merged=N.mergeRuns(t.runs,session.runs);}catch{return 'refused';}
  const next=merged.runs;t.used=W.numberRuns(next,Math.max(t.used,...t.runs.map(r=>r.number||0)));t.runs=next;t.swap=null;
  numbered(next.filter(r=>merged.added.includes(r.job)));return 'import';
 };
 return t;
}

test('K6: a seeded random sequence of 2400 steps keeps the numbers increasing, never reused, and the next one the largest + 1',()=>{
 const base=N.parseSession(C.synthetic(N,P)).runs[1],rand=random(20261124),t=tab(base),seen={};let pool=0;
 for(let step=0;step<2400;step++){
  const x=rand();let what;
  if(x<0.34)what=t.result(rand()<0.12&&t.runs.length?parseInt(t.runs[Math.floor(rand()*t.runs.length)].job,16):++pool);
  else if(x<0.44)what=t.pin(Math.floor(rand()*6),true);
  else if(x<0.56)what=t.pin(Math.floor(rand()*6),false);
  else if(x<0.64)what=t.swapBack();
  else if(x<0.76){const n=1+Math.floor(rand()*3),ids=Array.from({length:n},()=>rand()<0.3&&t.runs.length?parseInt(t.runs[Math.floor(rand()*t.runs.length)].job,16):++pool);
   const unique=[...new Set(ids)],start=1+Math.floor(rand()*20);what=t.import(unique,unique.map((_,k)=>start+k*(1+Math.floor(rand()*3))));}
  else if(x<0.84){const text=t.text(),v=JSON.parse(text).version;what='save v'+v;
   assert.equal(v===12,t.runs.some((r,i)=>r.number!==i+1),`step ${step}: version 12 exactly when a run is off its place`);}
  else if(x<0.92)what=t.open();
  else what=t.restore();
  seen[what]=(seen[what]||0)+1;
  const numbers=t.runs.map(r=>r.number);
  assert.ok(numbers.every(Number.isSafeInteger),`step ${step} (${what}): every run is numbered`);
  assert.ok(numbers.every((n,i)=>i===0||n>numbers[i-1]),`step ${step} (${what}): ${numbers} increase`);
  for(const r of t.runs)assert.equal(t.given.get(r.number),r.job,`step ${step} (${what}): number ${r.number} is one job's`);
  assert.equal(t.used,Math.max(0,...numbers),`step ${step} (${what}): the largest number is kept, so next = largest + 1`);
 }
 // every kind of step happened
 for(const kind of ['result','result again','pin','unpin','swap','import','open','restore','save v12'])assert.ok(seen[kind]>0,kind+' '+JSON.stringify(seen));
 assert.ok(Object.keys(seen).some(k=>/^save v(7|9)$/.test(k)),JSON.stringify(seen));
});

test('K7: the header after a restore names the recovered project; a pair restore keeps the newer name',()=>{
 const when=()=>'10:15';
 // a name, the record no longer matching the file it was opened from
 assert.equal(PS.projectTitle({name:'both-models',models:2,recovery:'kept',recovered:{opened:null}},when),'both-models · recovered from this browser · not saved to a file · kept for recovery in this browser');
 // a name, the record still matching the project file it was opened from (Q4)
 assert.equal(PS.projectTitle({name:'both-models',models:2,recovery:'kept',recovered:{opened:'both-models.json'}},when),'both-models · recovered from this browser · as opened from both-models.json · kept for recovery in this browser');
 // savedFile.projectName: as before (the project file, saved at its time)
 assert.equal(PS.projectTitle({name:'both-models',models:2,file:{name:'both-models.json',how:'recovered',savedAt:'T'},current:true,recovery:'kept'},when),'both-models · both-models.json · saved 10:15');
 // an older record without a name: as before
 assert.equal(PS.projectTitle({models:1,recovery:'kept'},when),'Untitled project · not saved to a file · kept for recovery in this browser');
 assert.equal(PS.projectTitle({models:1,recovery:'kept',copyOf:'both-models.json'},when),'Untitled project · recovered from a copy of both-models.json · not saved to a file · kept for recovery in this browser');
 // after the next change: the ordinary line
 assert.equal(PS.projectTitle({name:'both-models',models:2,recovery:'kept'},when),'both-models · not saved to a file · kept for recovery in this browser');
 // the name of a record, unless savedFile.projectName names one or the project has a file
 const empty={name:null,nameFrom:null,file:null,recovered:null};
 assert.deepEqual(PS.recoveredProjectName(empty,{name:'both-models',from:'file'},{openedFile:'both-models.json',openedCurrent:true,savedAt:'2026-11-24T10:00:00.000Z'}),{name:'both-models',nameFrom:'file',recovered:{opened:'both-models.json',savedAt:'2026-11-24T10:00:00.000Z'}});
 assert.deepEqual(PS.recoveredProjectName(empty,{name:'both-models',from:'file'},{openedFile:'both-models.json',openedCurrent:false,savedAt:'2026-11-24T10:00:00.000Z'}).recovered.opened,null);
 assert.equal(PS.recoveredProjectName(empty,{name:'a',from:'user'},{savedFile:{name:'a.json',savedAt:'T',current:true,projectName:'a'}}),null);
 assert.equal(PS.recoveredProjectName({...empty,file:{name:'x.json'}},{name:'a',from:'user'}),null);
 assert.equal(PS.recoveredProjectName(empty,null),null);
 // a pair: the newer record's name wins, whichever restores first
 const older={name:'design-a',from:'user'},newer={name:'design-b',from:'user'},t0='2026-11-24T09:00:00.000Z',t1='2026-11-24T10:00:00.000Z';
 const first=PS.recoveredProjectName(empty,newer,{savedAt:t1}),second=PS.recoveredProjectName({...empty,...first},older,{savedAt:t0});
 assert.equal(first.name,'design-b');assert.equal(second.name,'design-b');
 const a=PS.recoveredProjectName(empty,older,{savedAt:t0}),b=PS.recoveredProjectName({...empty,...a},newer,{savedAt:t1});
 assert.equal(a.name,'design-a');assert.equal(b.name,'design-b');assert.equal(b.recovered.savedAt,t1);
 // the page: the record's project is restored after restoreProjectFile, and the line holds until the next change
 const app=read('workspace-app.mjs');
 assert.ok(app.includes("restoreProjectName(pending.recordProject,{savedFile:file,openedFile:pending.openedFile,openedCurrent:pending.openedCurrent,savedAt:pending.recordSavedAt});"));
 assert.ok(app.includes("restoreProjectName(recordProject,{savedFile,openedFile,openedCurrent,savedAt:recordSavedAt});"));
 assert.ok(app.includes("const recovered=!file&&project.recovered&&project.recovered.stamp===projectStamp()?{opened:project.recovered.opened}:null;"));
 // both models' records write the project's name
 assert.ok(app.includes("page:pageForRecord(),project:recordProjectNow()});const changed"));
 assert.ok(app.includes("openedCurrent:rec.openedCurrent,project:recordProjectNow()});"));
});

test('K10 (amended before implementation, HQ decision 2026-11-24-openphysics-studio-session-v12-k10-amended): no numbering sentence for a version 7, 11 or 12 file; each run shows its place or its stored number',()=>{
 assert.equal(W.RENUMBERED_TEXT,undefined);assert.equal(W.renumberedText,undefined);assert.equal(W.renumberedRuns,undefined);
 // a version 7 file with runs and a version 11 file of runs 1..n: each run at its place
 assert.deepEqual(N.parseSession(fixture('optical-v7-three.json')).runs.map(r=>r.number),[1,2,3]);
 const v9=N.parseSession(C.synthetic(N,P)),target=N.validateRun({...v9.runs[0],job:'0000000c',settings:N.closedTargetSettings(v9.runs[0].settings,2.46)});
 const elevenText=N.sessionText(v9.input,[...v9.runs,target],v9.selected,v9.comparison,v9.view);
 assert.equal(JSON.parse(elevenText).version,11);assert.deepEqual(N.parseSession(elevenText).runs.map(r=>r.number),[1,2,3]);
 // a version 12 file: the stored numbers
 assert.deepEqual(N.parseSession(fixture('optical-v12-numbers.json')).runs.map(r=>r.number),[3,5,6,7,8,9]);
 // the open, project-open, restore and pair-restore messages say nothing about numbering
 const app=read('workspace-app.mjs');
 assert.ok(!/numbered from 1|RENUMBERED_TEXT|renumberedText|renumberedRuns/.test(app));
 assert.ok(app.includes("'File › Save keeps it in a file; input undo starts here.')));"));
 assert.ok(app.includes("Results were read from the file, not recomputed; nothing was run.`);"));
 assert.ok(app.includes("from this browser, not recomputed.`);};"));
});

test('the open keeps the stored numbers; an import numbers its runs after the tab\'s largest and says so',()=>{
 const app=read('workspace-app.mjs');
 assert.ok(app.includes("runs=session.runs;for(const r of runs){const n=r.number;delete r.number;if(Number.isInteger(n))r.number=n;}runNumbersUsed=numberRuns(runs);"));
 assert.ok(!app.includes("for(const r of runs)delete r.number;"));
 assert.equal(W.importNumbersText([{from:2,to:9},{from:4,to:10}],'design-b.json'),'Added Run 2 and Run 4 of design-b.json as Run 9 and Run 10.');
 assert.equal(W.importNumbersText([{from:1,to:7},{from:2,to:8},{from:5,to:9}],'b.json'),'Added Run 1, Run 2 and Run 5 of b.json as Run 7, Run 8 and Run 9.');
 assert.equal(W.importNumbersText([{from:9,to:9}],'b.json'),'');assert.equal(W.importNumbersText([],'b.json'),'');
 assert.ok(app.includes("imported fields were not recomputed.'+(renumbered?' '+renumbered:'')+dropped.map(r=>' '+droppedRunText(r)).join(''));"));
 // a job that comes back keeps its number and its place
 const runs=[3,5,8].map(n=>({number:n}));const back=[runs[0],runs[2],runs[1]];
 assert.deepEqual(W.inNumberOrder(back).map(r=>r.number),[3,5,8]);
 assert.ok(app.includes("next=prior?inNumberOrder(appended):appended"));
});
