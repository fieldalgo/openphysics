// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
// Keeping more runs: the field budget of the tab (workspace-retention.mjs). Pre-registered:
// K2 (the tab path: every earlier fixture opened, nothing changed, then saved and kept for recovery,
// is written byte for byte, never as version 13), K6 (a seeded random sequence of at least 2000 steps:
// numbers increase, are never reused, the next is the largest + 1), K7 (after every step the Save
// text equals the recovery text, byte for byte, no Save question, and the runs with fields in the tab
// are those with `field` in the text), K8 (fields change only when a field arrives; the fields kept
// are the order's choice; the cached sum is the written length) and K9 (the words of section 5 and
// 4.1, exactly). Also the two cases where the tab holds more than a file: a selected run alone over
// the budget (section 3.4) and inputs grown by more than the 16 KiB kept for them (the named
// exception of the decision on the budget). The engine's T18 runs (K1) are measured by
// tools/studio_run_retention.mjs k1.
const test=require('node:test');const assert=require('node:assert/strict');
const fs=require('node:fs');const path=require('node:path');
const STATIC='../../packages/simcase/src/simcase/studio/static/';
const FIX=path.join(__dirname,'studio_session_fixtures');
const fixture=name=>fs.readFileSync(path.join(FIX,name),'utf8');
let N,P,W,X,R,PF,C,Q;
test.before(async()=>{
 N=await import(STATIC+'workspace-notebook.mjs');P=await import(STATIC+'workspace-project.mjs');W=await import(STATIC+'workspace-workflow.mjs');
 X=await import(STATIC+'workspace-retention.mjs');R=await import(STATIC+'workspace-notebook-recovery.mjs');PF=await import(STATIC+'workspace-project-file.mjs');
 C=await import('./studio_session_fixtures/closed_sessions.mjs');Q=await import('./studio_session_fixtures/numbered_sessions.mjs');
});
const VIEW={mode:0,component:'magnitude',window:'Core region'};
const bytes=text=>Buffer.byteLength(text,'utf8');
const setup={materials:{Core:'Silicon',Oxide:'Silica',Heater:''},temperature:293.15,cooling:'',fixed:'',terminal:''};
const inputs=(shapes=null)=>{const i=P.snapshot({width:500,voltage:1,electric:false,heat:false,structure:false,optics:true,wavelength:1550,coreMesh:30},setup);if(shapes)i.model.shapes=shapes;return i;};
// a field of t triangles and k modes (a strip of triangles 10 nm apart), so runs differ in size
const field=(k,t)=>{const X0=[],T=[];for(let i=0;i<=t;i++)X0.push([i*1e-8,0],[i*1e-8,1e-8]);for(let i=0;i<t;i++)T.push([2*i,2*i+2,2*i+1]);
 const mode=m=>T.map((_,i)=>[1+i*1e-3,0.25*m+i*1e-4,1e-3*(m+1)]);return {node_coordinates:X0,triangles:T,real:Array.from({length:k},(_,m)=>mode(m)),imag:Array.from({length:k},(_,m)=>T.map(()=>[0,1e-9*m,0]))};};
const job=i=>i.toString(16).padStart(8,'0');
// the result of job i: always the same run (k modes and t triangles from i)
const result=i=>{const k=1+i%4,t=8+(i*37)%32;
 return N.validateRun({job:job(i),completedAt:new Date(Date.UTC(2026,10,25,0,0,i%60,i)).toISOString(),settings:N.opticalSettings(1550,30,k),input:inputs(),
  effective_index:Array.from({length:k},(_,m)=>2.9-0.17*m),field:field(k,t),origin:'local',serverVersion:'0.0.0',
  te_polarization_fraction:Array.from({length:k},(_,m)=>0.9-0.1*m),effective_area:Array.from({length:k},(_,m)=>2e-13*(m+1))});};
// the session limit of these runs (each field 1 to 18 kB): a smaller limit, the same rule
const LIMIT=90000,BUDGET=LIMIT-16*1024;

// what the page does with its runs (workspace-app.mjs), on the modules' functions
function tab(input=inputs(),BUDGET=LIMIT-16*1024){
 const t={runs:[],used:0,selected:null,comparison:[null,null],dropSwap:null,fieldSwap:null,given:new Map(),input,arrivals:0};
 const numbered=runs=>{for(const r of runs)t.given.set(r.number,t.given.get(r.number)??r.job);};
 t.text=()=>N.sessionText(t.input,t.runs,t.selected,t.comparison,VIEW);
 // applyFieldBudget: the order's choice within the budget, checked against the full texts
 t.arrive=(first=[])=>{
  t.arrivals++;X.forgetHeldFields(t.runs);t.fieldSwap=null;
  const order=X.fieldOrder(t.runs,t.selected,first),keep=new Set(),expected=new Set();
  if(bytes(t.text())>BUDGET)order.forEach((r,i)=>{const trial=new Set([...keep,r.job]),b=bytes(N.sessionText(t.input,t.runs,t.selected,t.comparison,VIEW,{keep:trial}));if(b<=BUDGET||(i===0&&r.job===t.selected)){keep.add(r.job);expected.add(r.job);}});
  else for(const r of order)expected.add(r.job);
  const out=X.chooseFields(t.input,t.runs,t.selected,t.comparison,VIEW,{first,budget:BUDGET});
  const plain=out.letGo.filter(r=>!r.pinned);for(const r of out.letGo)X.letGoField(r);
  assert.deepEqual(new Set(t.runs.filter(r=>r.field).map(r=>r.job)),expected,'K8: the fields kept are the order\'s choice');
  if(!out.fits)assert.equal(out.total,bytes(t.text()),'K8: the cached sum is the written length');
  const other=X.fieldSwapCandidate(t.runs,plain,t.selected);if(other)t.fieldSwap={back:plain[0],other,list:t.runs};
  return out;
 };
 t.result=i=>{
  const completed=result(i),prior=t.runs.find(r=>r.job===completed.job);if(prior)completed.number=prior.number;
  const used=W.numberRuns([completed],t.used);let appended;
  try{appended=N.appendRun(t.runs,completed,N.RUN_LIMIT);}catch{return 'all pinned';}
  t.used=used;const next=prior?W.inNumberOrder(appended):appended,dropped=t.runs.filter(r=>!next.includes(r)&&r.job!==completed.job);
  t.runs=next;numbered([completed]);t.selected=completed.job;t.comparison=[t.comparison[1]&&t.runs.some(r=>r.job===t.comparison[1])?t.comparison[1]:completed.job,completed.job];
  const other=dropped.length===1?W.swapCandidate(t.runs,completed):null;t.dropSwap=other?{kept:dropped[0],other,list:t.runs}:null;
  t.arrive();return prior?'result again':dropped.length?'result drop':'result';
 };
 // the run kept comes back with its field: a field arrives, first after the selected run's
 t.swapBack=()=>{const o=t.dropSwap;if(!o||t.runs!==o.list||!t.runs.includes(o.other))return 'no swap';t.runs=W.swapDropped(t.runs,o.kept,o.other);t.dropSwap=null;t.fieldSwap=null;t.arrive([o.kept.job]);return 'swap';};
 t.fieldsBack=()=>{const o=t.fieldSwap;if(!o||t.runs!==o.list||!X.heldField(o.back)||!o.other.field||o.other.job===t.selected)return 'no field swap';
  const before=bytes(t.text());X.letGoField(o.other);X.takeBackField(o.back);X.forgetHeldFields(t.runs);t.fieldSwap=null;
  assert.ok(bytes(t.text())<=Math.max(before,BUDGET),'a field swap stays within the budget');return 'field swap';};
 // Recompute Run N's fields (R3): the same result again for a run without its field; its values match,
 // the field is attached to the same run (no number, no run), and the budget applies (it arrived)
 t.recompute=k=>{const without=t.runs.filter(r=>!r.field);if(!without.length)return 'no recompute';const r=without[k%without.length];
  const fresh=result(parseInt(r.job,16)),count=t.runs.length,numbers=t.runs.map(x=>x.number).join(),used=t.used;
  assert.equal(X.recomputeMismatch(r,fresh),null,'the values match');X.attachField(r,fresh.field);t.arrive([r.job]);
  assert.equal(t.runs.length,count);assert.equal(t.runs.map(x=>x.number).join(),numbers);assert.equal(t.used,used,'a recompute takes no number');
  return 'recompute';};
 t.pin=(k,on)=>{const r=t.runs[k%Math.max(1,t.runs.length)];if(!r)return 'no run';r.pinned=on;t.dropSwap=null;return on?'pin':'unpin';};
 t.select=k=>{const r=t.runs[k%Math.max(1,t.runs.length)];if(!r)return 'no run';t.selected=r.job;return 'select';};
 t.rename=(k,label)=>{const r=t.runs[k%Math.max(1,t.runs.length)];if(!r)return 'no run';r.label=label;return 'rename';};
 t.compare=(a,b)=>{if(!t.runs.length)return 'no run';t.comparison=[t.runs[a%t.runs.length].job,t.runs[b%t.runs.length].job];return 'compare';};
 // File › Open and Restore: the stored numbers (versions 12 and 13), then the budget (completeLoad)
 const load=session=>{for(const r of session.runs){const n=r.number;delete r.number;r.number=n;}t.runs=session.runs;t.used=W.numberRuns(t.runs);t.selected=session.selected;t.comparison=[...session.comparison];t.dropSwap=null;t.arrive();};
 t.open=()=>{load(N.parseSession(t.text()));return 'open';};
 t.restore=()=>{const make=N.captureSession(t.input,t.runs,t.selected,t.comparison,VIEW,{limit:LIMIT});load(R.readNotebookRecovery({version:1,savedAt:'2026-11-25T10:00:00.000Z',session:make()}).session);return 'restore';};
 // Add runs from file: another tab's runs, numbered after this tab's largest, the last one selected
 t.import=(ids,numbers)=>{
  const other=ids.map((i,k)=>Object.assign(result(i),{number:numbers[k]}));let text;
  try{text=N.sessionText(t.input,other,null,[null,null],VIEW);}catch{return 'not written';}
  const session=N.parseSession(text);let merged;try{merged=N.mergeRuns(t.runs,session.runs,N.RUN_LIMIT);}catch{return 'refused';}
  const next=merged.runs;t.used=W.numberRuns(next,Math.max(t.used,...t.runs.map(r=>r.number||0)));t.runs=next;t.dropSwap=null;
  numbered(next.filter(r=>merged.added.includes(r.job)));t.selected=next.findLast(r=>merged.added.includes(r.job)||merged.reused.includes(r.job))?.job??t.selected;
  if(!t.runs.some(r=>r.job===t.comparison[0]))t.comparison=[t.selected,t.selected];if(!t.runs.some(r=>r.job===t.comparison[1]))t.comparison=[t.comparison[0],t.selected];
  t.arrive();return 'import';
 };
 return t;
}
// a deterministic generator (mulberry32)
const random=seed=>()=>{seed|=0;seed=seed+0x6D2B79F5|0;let t=Math.imul(seed^seed>>>15,1|seed);t=t+Math.imul(t^t>>>7,61|t)^t;return((t^t>>>14)>>>0)/4294967296;};

test('K6, K7 and K8: a seeded random sequence of 2000 steps',()=>{
 const rand=random(20261125),t=tab(),seen={},arriving=new Set(['result','result again','result drop','swap','recompute','import','open','restore']);let pool=0;
 for(let step=0;step<2000;step++){
  const x=rand(),before=new Map(t.runs.map(r=>[r.job,r.field])),pick=()=>Math.floor(rand()*20);let what;
  if(x<0.36)what=t.result(rand()<0.1&&t.runs.length?parseInt(t.runs[Math.floor(rand()*t.runs.length)].job,16):++pool);
  else if(x<0.44)what=t.pin(pick(),true);
  else if(x<0.52)what=t.pin(pick(),false);
  else if(x<0.57)what=t.swapBack();
  else if(x<0.64)what=t.fieldsBack();
  else if(x<0.68)what=t.select(pick());
  else if(x<0.70)what=t.rename(pick(),rand()<0.5?'':'Design '+step);
  else if(x<0.72)what=t.compare(pick(),pick());
  else if(x<0.80){const n=1+Math.floor(rand()*4),ids=Array.from({length:n},()=>rand()<0.3&&t.runs.length?parseInt(t.runs[Math.floor(rand()*t.runs.length)].job,16):++pool);
   const unique=[...new Set(ids)],start=1+Math.floor(rand()*30);what=t.import(unique,unique.map((_,k)=>start+k*(1+Math.floor(rand()*3))));}
  else if(x<0.84)what='save';
  else if(x<0.88)what=t.recompute(pick());
  else if(x<0.94)what=t.open();
  else what=t.restore();
  seen[what]=(seen[what]||0)+1;
  // K8: a field changes only when a field arrives (a result, the 20-run swap bringing a run back with
  // its field, a recompute, an import, an open or a restore) or by Keep Run N's fields; selecting, pinning,
  // naming, comparing and saving change none
  if(!arriving.has(what)&&what!=='field swap')for(const r of t.runs)assert.equal(r.field,before.get(r.job),`step ${step} (${what}): Run ${r.number}'s field is unchanged`);
  // K6
  const numbers=t.runs.map(r=>r.number);
  assert.ok(numbers.every(Number.isSafeInteger),`step ${step} (${what}): every run is numbered`);
  assert.ok(numbers.every((n,i)=>i===0||n>numbers[i-1]),`step ${step} (${what}): ${numbers} increase`);
  for(const r of t.runs)assert.equal(t.given.get(r.number),r.job,`step ${step} (${what}): number ${r.number} is one job's`);
  assert.equal(t.used,Math.max(0,...numbers),`step ${step} (${what}): next = largest + 1`);
  assert.ok(t.runs.length<=N.RUN_LIMIT);
  // K7: the Save text (no question: it fits) equals the recovery text; the runs with fields in the tab
  // are the runs with `field` in the text
  if(!t.runs.length)continue;
  const save=N.writeOpticalSession(t.input,t.runs,t.selected,t.comparison,VIEW,{limit:LIMIT});
  assert.equal(save.ok,true,`step ${step} (${what}): Save asks nothing`);
  const recovery=N.captureSession(t.input,t.runs,t.selected,t.comparison,VIEW,{limit:LIMIT}),text=recovery();
  assert.equal(text,save.text,`step ${step} (${what}): recovery equals Save`);assert.deepEqual(recovery.dropped,[]);
  const doc=JSON.parse(save.text);assert.deepEqual(doc.runs.map(r=>Object.hasOwn(r,'field')),t.runs.map(r=>!!r.field),`step ${step} (${what}): the tab's fields are the file's`);
  // within the budget right after a field arrives; a name or a pin since then may add a few bytes,
  // which the headroom kept for the inputs holds (Save asked nothing above: within the limit)
  if(arriving.has(what))assert.ok(bytes(save.text)<=BUDGET,`step ${step} (${what}): within the budget`);
  assert.ok(bytes(save.text)<=LIMIT,`step ${step} (${what}): within the limit`);
  assert.equal(doc.version===13,t.runs.length>6,`step ${step} (${what}): version 13 exactly above six runs`);
 }
 for(const kind of ['result','result again','result drop','pin','unpin','swap','field swap','recompute','select','rename','compare','import','save','open','restore'])assert.ok(seen[kind]>0,kind+' '+JSON.stringify(seen));
 assert.ok(t.arrivals>700,JSON.stringify(seen));
});

test('K2: the tab path rewrites every earlier fixture byte for byte (opened, nothing changed, saved and kept for recovery)',()=>{
 const golden=JSON.parse(fixture('sessions-rewritten-13f07f4.json'));
 const texts={...Object.fromEntries(['empty','one','three'].map(s=>[`optical-v7-${s}.json`,fixture(`optical-v7-${s}.json`)])),
  ...Object.fromEntries(['empty','one','three'].map(s=>[`optical-v6-${s}.json`,fixture(`optical-v6-${s}.json`)])),
  'optical-v12-numbers.json':fixture('optical-v12-numbers.json'),'numbered_sessions.mjs':Q.numberedSession(N,P,FIX),
  ...Object.fromEntries(Object.entries(golden))};
 for(const [name,text] of Object.entries(texts)){
  const s=N.parseSession(text),t=tab(s.input);
  const load=()=>{for(const r of s.runs){const n=r.number;delete r.number;r.number=n;}t.runs=s.runs;t.used=W.numberRuns(t.runs);t.selected=s.selected;t.comparison=[...s.comparison];t.arrive();};
  load();
  const expected=N.sessionText(N.parseSession(text).input,N.parseSession(text).runs,s.selected,s.comparison,s.view);
  assert.ok(t.runs.every(r=>r.field||!JSON.parse(text).runs.find(x=>x.job===r.job)||!('field' in JSON.parse(text).runs.find(x=>x.job===r.job))),name+': no field let go');
  const save=N.writeOpticalSession(s.input,t.runs,s.selected,s.comparison,s.view);
  assert.equal(save.ok,true,name);assert.equal(save.text,expected,name+': Save');
  if(t.runs.length)assert.equal(N.captureSession(s.input,t.runs,s.selected,s.comparison,s.view)(),expected,name+': recovery');
  assert.notEqual(JSON.parse(save.text).version,13,name);
 }
 // (the multiphysics session and the project file do not take this path: studio_run_retention_format.cjs, K2)
});

test('K9: the words of section 5 and 4.1, exactly',()=>{
 const shape={type:'rect',name:'Core',material:'Silicon',x:-350,y:0,w:700,h:300};
 const run=(n,extra={})=>({job:job(n),number:n,label:'',pinned:false,settings:{mode_count:4},input:{model:{shapes:[shape]}},...extra});
 const three=run(3),five=run(5),six=run(6),named=run(3,{label:'Design A'});
 // before the run, while it computes, after the result: one, two and three runs, and a named run
 assert.equal(X.keepsValuesText([three]),'If you run: Run 3 (closed · 4 modes · 700 × 300 nm) keeps its values, not its fields');
 assert.equal(X.keepsValuesText([three,five]),'If you run: Run 3 (closed · 4 modes · 700 × 300 nm) and Run 5 (closed · 4 modes · 700 × 300 nm) keep their values, not their fields');
 assert.equal(X.keepsValuesText([three,five,six]),'If you run: Run 3 (closed · 4 modes · 700 × 300 nm), Run 5 (closed · 4 modes · 700 × 300 nm) and Run 6 (closed · 4 modes · 700 × 300 nm) keep their values, not their fields');
 assert.equal(X.keepsValuesText([named]),'If you run: Run 3 · Design A (closed · 4 modes · 700 × 300 nm) keeps its values, not its fields');
 assert.equal(X.keepsValuesWhileRunningText([three]),'When this run finishes, Run 3 (closed · 4 modes · 700 × 300 nm) keeps its values, not its fields');
 assert.equal(X.keepsValuesWhileRunningText([three,five]),'When this run finishes, Run 3 (closed · 4 modes · 700 × 300 nm) and Run 5 (closed · 4 modes · 700 × 300 nm) keep their values, not their fields');
 assert.equal(X.fieldsNotKeptAfterText([three]),'Run 3 (closed · 4 modes · 700 × 300 nm) keeps its values; its fields were not kept (16.8 MB limit).');
 assert.equal(X.fieldsNotKeptAfterText([three,five]),'Run 3 (closed · 4 modes · 700 × 300 nm) and Run 5 (closed · 4 modes · 700 × 300 nm) keep their values; their fields were not kept (16.8 MB limit).');
 assert.equal(X.fieldsNotKeptAfterText([named]),'Run 3 · Design A (closed · 4 modes · 700 × 300 nm) keeps its values; its fields were not kept (16.8 MB limit).');
 // the swap after the result, and once done
 assert.equal(X.keepFieldsInsteadLabel(three,run(4)),"Keep Run 3's fields, not Run 4's (closed · 4 modes · 700 × 300 nm)");
 assert.equal(X.fieldsBackText(three,run(4)),"Run 3's fields are back; Run 4 (closed · 4 modes · 700 × 300 nm) keeps its values, not its fields.");
 // a pinned run's fields (section 3.3)
 assert.equal(X.pinnedFieldsText([run(2,{pinned:true})],17.4e6),"Run 2 (pinned) keeps its values; its fields were not kept: the selected and pinned runs' fields are 17.4 MB, over the 16.8 MB limit. Unpin a run to keep the newer fields first.");
 assert.equal(X.pinnedFieldsText([run(1,{pinned:true}),run(2,{pinned:true})],17.4e6),"Run 1 (pinned) and Run 2 (pinned) keep their values; their fields were not kept: the selected and pinned runs' fields are 17.4 MB, over the 16.8 MB limit. Unpin a run to keep the newer fields first.");
 // the 20-run drop (today's words with 20), the tree, the run list and its note
 assert.equal(W.droppedRunText(three),'Run 3 (closed · 4 modes · 700 × 300 nm) was dropped: up to 20 runs are kept; pin a run to keep it.');
 assert.equal(W.dropWarningText(three),'If you run: drops Run 3 (closed · 4 modes · 700 × 300 nm) · pin it to keep it');
 assert.equal(N.runsNodeLabel(9),'Runs · 9 of 20');
 assert.equal(X.VALUES_ONLY,' · values only');
 assert.equal(N.RUNS_KEPT_TEXT,"Up to 20 runs are kept with their values. Fields are kept up to 16.8 MB. When a result or a recompute arrives, Studio keeps the selected run's fields first, then pinned runs', then the newest. Selecting a run does not bring its fields back; Recompute does.");
 // Results (4.1), its export title, and Compare (4.2)
 assert.equal(X.fieldsNotKeptResultsText(run(4)),"Run 4's fields are not kept; its n_eff, TE fractions and effective areas are kept. Fields are kept up to 16.8 MB. When a result or a recompute arrives, Studio keeps the selected run's fields first, then pinned runs', then the newest. Selecting a run does not bring its fields back; Recompute does.");
 assert.equal(X.fieldsNotKeptResultsText(run(4),true),"Run 4's fields were not kept in the session file. Its n_eff, TE fractions and effective areas are kept.");
 assert.equal(X.recomputeLabel(run(4)),"Recompute Run 4's fields");
 assert.equal(X.recomputeEstimate(run(4,{duration:118000})),' · about 2 min');assert.equal(X.recomputeEstimate(run(4)),'');
 assert.equal(X.recomputeFirstText(run(4)),"Recompute Run 4's fields first");
 assert.equal(X.compareNoFieldsText(run(4)),"Run 4's fields are not kept, so its modes are listed by number and not plotted.");
 // the budget and its words: 16 MiB less 16 KiB, said as 16.8 MB
 assert.equal(X.FIELD_BUDGET_BYTES,16760832);assert.equal(X.BUDGET_TEXT,'16.8 MB');assert.equal(X.mbText(N.MAX_SESSION_BYTES),'16.8 MB');
 // the page uses them
 const app=fs.readFileSync(path.join(__dirname,STATIC,'workspace-app.mjs'),'utf8');
 assert.ok(app.includes("limit.textContent=RUNS_KEPT_TEXT+' Pinned runs stay; when a 21st run arrives, the oldest unpinned run is replaced. File › Save keeps every run in one file; Export this run writes one run to its own file.';"));
 assert.ok(app.includes("const runItemText=run=>(run.pinned?'Pinned · ':'')+runLabel(run)+(run.field?'':VALUES_ONLY);"));
 assert.ok(app.includes("none.textContent=fieldsNotKeptResultsText(solverRun,solverRun.origin==='imported'&&!fieldLetGoHere(solverRun));"));
 assert.ok(app.includes("exportPng.disabled=ui.page!=='Results'||!solverRun.field;if(!solverRun.field)exportPng.title=recomputeFirstText(solverRun);"));
});

test('the order: the selected run, the run whose field arrived, the pinned runs newest first, then the others newest first',()=>{
 const runs=[1,2,3,4,5,6].map(n=>Object.assign(result(n),{number:n}));runs[1].pinned=true;runs[3].pinned=true;
 assert.deepEqual(X.fieldOrder(runs,runs[2].job).map(r=>r.number),[3,4,2,6,5,1]);
 assert.deepEqual(X.fieldOrder(runs,runs[2].job,[runs[0].job]).map(r=>r.number),[3,1,4,2,6,5]);
 // a run without a field is not in the order; a field that does not fit is skipped, the next older tried
 X.letGoField(runs[4]);assert.deepEqual(X.fieldOrder(runs,runs[5].job).map(r=>r.number),[6,4,2,3,1]);
 const size=r=>({1:10,2:10,3:60,4:10,6:30})[r.number];
 const out=X.chooseFields(inputs(),runs,runs[5].job,[null,null],VIEW,{budget:N.sessionBytesWithoutFields(inputs(),runs,runs[5].job,[null,null],VIEW)+70,bytes:size});
 assert.deepEqual(out.kept.map(r=>r.number),[6,4,2,1]);assert.deepEqual(out.letGo.map(r=>r.number),[3]);
});

test('a pin puts a run\'s field first but does not keep it: the oldest pinned run\'s field goes, and the words name it',()=>{
 const runs=[1,2,3,4].map(n=>Object.assign(result(n+100),{number:n,pinned:n<4}));
 const base=N.sessionBytesWithoutFields(inputs(),runs,runs[3].job,[null,null],VIEW),size=()=>40;
 const out=X.chooseFields(inputs(),runs,runs[3].job,[null,null],VIEW,{budget:base+100,bytes:size});
 assert.deepEqual(out.kept.map(r=>r.number),[4,3]);assert.deepEqual(out.letGo.map(r=>r.number),[2,1]);
 assert.equal(X.selectedAndPinnedBytes(runs,runs[3].job,base,size),base+160);
});

test('the swap: Keep Run N\'s fields lets the oldest unpinned, unselected run with a field at least as large go instead',()=>{
 const runs=[1,2,3,4,5].map(n=>Object.assign(result(n+200),{number:n}));const sizes=runs.map(r=>N.runFieldBytes(r));
 X.letGoField(runs[0]);
 const other=X.fieldSwapCandidate(runs,[runs[0]],runs[4].job);
 assert.ok(other&&other!==runs[4]&&N.runFieldBytes(other)>=sizes[0]&&runs.find(r=>r.field&&r!==runs[4]&&N.runFieldBytes(r)>=sizes[0])===other);
 // a run's field back is the same field, with the same record bytes as before it went
 const record=N.sessionText(inputs(),[Object.assign(result(201),{number:1})],null,[null,null],VIEW);
 X.letGoField(other);assert.ok(X.takeBackField(runs[0]));assert.equal(N.sessionText(inputs(),[runs[0]],null,[null,null],VIEW),record);
 // none for a pinned run, two runs, or a run whose field is no longer held
 runs[1].pinned=true;assert.equal(X.fieldSwapCandidate(runs,[runs[1]],runs[4].job),null);
 assert.equal(X.fieldSwapCandidate(runs,[runs[0],runs[2]],runs[4].job),null);
 X.letGoField(runs[2]);X.forgetHeldFields(runs);assert.equal(X.fieldSwapCandidate(runs,[runs[2]],runs[4].job),null);
});

test('the estimate before the run: the newest run of the same geometry, boundary and Modes to find; none, nothing said',()=>{
 const t=tab();for(let i=1;i<=8;i++)t.result(i);
 const like=t.runs.at(-1),next=X.runFieldSizeKey(like);
 const list=N.sessionBytesWithoutFields(t.input,t.runs,t.selected,t.comparison,VIEW);assert.ok(list>0);
 const predicted=X.predictedLetGo(t.input,t.runs,t.selected,t.comparison,VIEW,next,{budget:BUDGET});
 // the next result of the same inputs: the prediction is what the result then lets go
 const before=new Set(t.runs.filter(r=>r.field).map(r=>r.job));t.result(8+4*20);
 const gone=t.runs.filter(r=>before.has(r.job)&&!r.field).map(r=>r.job);
 assert.deepEqual(predicted.map(r=>r.job),gone);
 assert.deepEqual(X.predictedLetGo(t.input,t.runs,t.selected,t.comparison,VIEW,X.fieldSizeKey({shapes:[],coreMesh:30,boundary:null,modeCount:2})),[]);
});

test('section 3.4: a selected run alone over the budget keeps its field in the tab; Save and recovery refuse as before',()=>{
 const small=Object.assign(result(300),{number:1}),big=Object.assign(result(303),{number:2});
 const runs=[small,big],limit=N.sessionBytesWithoutFields(inputs(),runs,big.job,[null,null],VIEW)+N.runFieldBytes(big)-1000,budget=limit-X.FIELD_HEADROOM_BYTES;assert.ok(N.runFieldBytes(big)>N.runFieldBytes(small));
 const out=X.chooseFields(inputs(),runs,big.job,[null,null],VIEW,{budget});
 assert.deepEqual(out.kept.map(r=>r.number),[2]);assert.deepEqual(out.letGo.map(r=>r.number),[1]);X.letGoField(small);
 const save=N.writeOpticalSession(inputs(),runs,big.job,[null,null],VIEW,{limit});
 assert.equal(save.ok,false);assert.match(save.refusal,/^The selected run \(Run 2\) is /);
 assert.throws(()=>N.captureSession(inputs(),runs,big.job,[null,null],VIEW,{limit})(),{code:'recovery-over-limit'});
 // the whole Save path once another run is selected (no field arrives, so the tab still holds Run 2's
 // field): Save asks the question; Cancel writes nothing; Keep writes the reduced file, which opens
 const asked=N.writeOpticalSession(inputs(),runs,small.job,[null,null],VIEW,{limit});
 assert.equal(asked.ok,false,JSON.stringify({...asked,text:undefined}));assert.ok(asked.reduced&&asked.refusal===null,JSON.stringify({...asked,text:undefined}));assert.equal(asked.text,undefined,'Cancel: nothing to write');
 assert.match(N.opticalOverflowQuestion(asked.bytes),/^Session is .*; the limit is 16 MiB\. Keep the fields of the selected and pinned runs only\? The other runs keep n_eff, the TE fractions and the effective areas, but not their fields\.$/);
 const kept=N.writeOpticalSession(inputs(),runs,small.job,[null,null],VIEW,{limit,keepSelected:true});
 assert.equal(kept.ok,true);assert.ok(bytes(kept.text)<=limit);assert.deepEqual(kept.notKept,[1,2]);
 const opened=N.parseSession(kept.text);assert.deepEqual(opened.runs.map(r=>[r.number,!!r.field]),[[1,false],[2,false]]);
});

test('the named exception: a text grown by more than the headroom after the last arrival is over the limit; Save asks, recovery fills',()=>{
 // The inputs of a design are bounded (8 shapes, 8 Joule shapes, 6 materials), so the real 16 KiB is
 // not reached by edits; this tab keeps 1000 bytes and grows its text by naming runs (a name changes
 // no field), which takes the same path.
 const headroom=1000,L=50000,t=tab(inputs(),L-headroom);for(let i=1;i<=9;i++)t.result(i+400);
 const kept=t.runs.filter(r=>r.field).length;assert.ok(kept>1&&kept<t.runs.length,`${kept} of ${t.runs.length} fields kept, ${bytes(t.text())} bytes`);
 const before=bytes(t.text());assert.ok(before<=L-headroom);
 for(const r of t.runs)r.label='Ω'.repeat(80);
 assert.equal(t.runs.filter(r=>r.field).length,kept,'naming lets no field go');
 const after=bytes(t.text());assert.ok(after-before>headroom);
 const save=N.writeOpticalSession(t.input,t.runs,t.selected,t.comparison,VIEW,{limit:L});
 if(after<=L)assert.fail('the names keep the text within the limit: '+after);
 assert.equal(save.ok,false);assert.ok(save.reduced&&save.refusal===null,'Save asks the question in this case only');assert.equal(save.text,undefined,'Cancel: nothing to write');
 assert.match(N.opticalOverflowQuestion(save.bytes),/^Session is .*; the limit is 16 MiB\. Keep the fields of the selected and pinned runs only\?/);
 // Keep: the file with the fields of the selected and pinned runs only, within the limit; it opens
 const keep=N.writeOpticalSession(t.input,t.runs,t.selected,t.comparison,VIEW,{limit:L,keepSelected:true});
 assert.equal(keep.ok,true);assert.ok(bytes(keep.text)<=L);
 const opened=N.parseSession(keep.text);assert.deepEqual(opened.runs.map(r=>!!r.field),t.runs.map(r=>!!r.field&&(r.pinned||r.job===t.selected)));
 assert.deepEqual(opened.runs.map(r=>r.label),t.runs.map(r=>r.label));
 const recovery=N.captureSession(t.input,t.runs,t.selected,t.comparison,VIEW,{limit:L}),text=recovery();
 assert.ok(bytes(text)<=L);assert.ok(recovery.dropped.length>0,'recovery leaves some fields out, newest first, as before');
 // the next arrival chooses the fields within the budget again
 t.result(500);assert.ok(bytes(t.text())<=L-headroom);assert.equal(N.writeOpticalSession(t.input,t.runs,t.selected,t.comparison,VIEW,{limit:L}).ok,true);
});

test('the values-only runs the browser stages add: what this Studio writes, fourteen pinned runs without fields',async()=>{
 const V=await import('./studio_session_fixtures/values_only_sessions.mjs'),text=fixture('optical-values-only-14.json');
 assert.equal(text,V.valuesOnlySession(N,P));
 const s=N.parseSession(text);
 assert.equal(JSON.parse(text).version,13);assert.equal(s.runs.length,14);
 assert.ok(s.runs.every(r=>r.field===null&&r.pinned===true));
 // added to a tab of six runs, they take numbers 7 to 20 and add no field
 const t=tab();for(let i=1;i<=6;i++)t.result(i+600);
 const merged=N.mergeRuns(t.runs,s.runs,N.RUN_LIMIT);W.numberRuns(merged.runs,6);
 assert.equal(merged.runs.length,20);assert.deepEqual(merged.evicted,[]);
 assert.deepEqual(merged.runs.slice(6).map(r=>r.number),Array.from({length:14},(_,i)=>i+7));
 assert.equal(N.runFieldBytes(merged.runs.at(-1)),0);
});

test('regression (the seeded sequence, step 441): the 20-run swap brings the kept run back with its field, which arrives',()=>{
 // Run 1 pinned keeps its field ahead of the others; unpinned (no field changes), the 21st result
 // drops it with its field; Keep Run 1, drop Run 2 instead puts it back, and the budget lets other
 // fields go (without the arrival the text was over the budget)
 const t=tab();t.result(700);t.pin(0,true);for(let i=1;i<20;i++)t.result(700+i);
 assert.equal(t.runs.length,20);assert.ok(t.runs[0].field,'Run 1 kept its field');
 t.pin(0,false);t.result(720);
 assert.equal(t.dropSwap?.kept.number,1);assert.ok(t.dropSwap.kept.field);
 const before=t.runs.filter(r=>r.field).length;
 assert.equal(t.swapBack(),'swap');
 assert.ok(t.runs.some(r=>r.number===1&&r.field),'Run 1 back with its field');
 assert.ok(bytes(t.text())<=LIMIT-16*1024,'within the budget');
 assert.ok(t.runs.filter(r=>r.field).length<=before+1);
});
