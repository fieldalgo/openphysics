// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
// Compact field encoding, the conversion in the tab (slice E2). Pre-registered:
// F2 (no conversion while the fields fit: studio_session_fixtures/fit_sequence.mjs, 2000 seeded steps;
// the Save and recovery texts equal those of main 499a0d3, sequence-fit-499a0d3.json), F1 through the
// tab path, F11 (tab = file = recovery with the conversion: a seeded 2000-step sequence whose fields do
// not all fit; Save = recovery at every step; one conversion, at the first arrival that does not fit
// as text, and its sentence once), F6 (accuracy of what Studio computes from a compact field: the
// fixture fields here, the five T18 results too with STUDIO_RETENTION_RESULTS), F8 (the profile CSV)
// and F14's module part (K12 in a compact tab). F9 and F12 are measured by
// tools/studio_field_encoding.mjs f9; F14's engine part by tools/studio_field_encoding.mjs f14.
const test=require('node:test');const assert=require('node:assert/strict');
const fs=require('node:fs');const path=require('node:path');
const STATIC='../../packages/simcase/src/simcase/studio/static/';
const FIX=path.join(__dirname,'studio_session_fixtures');
const fixture=name=>fs.readFileSync(path.join(FIX,name),'utf8');
let N,P,W,X,R,E,F,M,MA,PR,PB,RR,OR,FS,PROJECT;
test.before(async()=>{
 N=await import(STATIC+'workspace-notebook.mjs');P=await import(STATIC+'workspace-project.mjs');W=await import(STATIC+'workspace-workflow.mjs');
 X=await import(STATIC+'workspace-retention.mjs');R=await import(STATIC+'workspace-notebook-recovery.mjs');E=await import(STATIC+'workspace-field-encoding.mjs');
 F=await import(STATIC+'workspace-field.mjs');M=await import(STATIC+'workspace-modes.mjs');MA=await import(STATIC+'workspace-match.mjs');
 PR=await import(STATIC+'workspace-profile.mjs');PB=await import(STATIC+'workspace-probe.mjs');RR=await import(STATIC+'workspace-result-run.mjs');OR=await import(STATIC+'workspace-open-run.mjs');PROJECT=await import(STATIC+'workspace-project-file.mjs');
 FS=await import('./studio_session_fixtures/fit_sequence.mjs');
});
const VIEW={mode:0,component:'magnitude',window:'Core region'};
const bytes=text=>Buffer.byteLength(text,'utf8');
const setup={materials:{Core:'Silicon',Oxide:'Silica',Heater:''},temperature:293.15,cooling:'',fixed:'',terminal:''};
const inputs=()=>P.snapshot({width:500,voltage:1,electric:false,heat:false,structure:false,optics:true,wavelength:1550,coreMesh:30},setup);
const field=(k,t)=>{const X0=[],T0=[];for(let i=0;i<=t;i++)X0.push([i*1e-8,0],[i*1e-8,1e-8]);for(let i=0;i<t;i++)T0.push([2*i,2*i+2,2*i+1]);
 const mode=m=>T0.map((_,i)=>[1+i*1e-3,0.25*m+i*1e-4,1e-3*(m+1)]);return {node_coordinates:X0,triangles:T0,real:Array.from({length:k},(_,m)=>mode(m)),imag:Array.from({length:k},(_,m)=>T0.map(()=>[0,1e-9*m,0.1]))};};
const job=i=>i.toString(16).padStart(8,'0');
// the result of job i: always the same run (k modes and t triangles from i), each field 2 to 25 kB as text
const result=i=>{const k=1+i%4,t=8+(i*37)%32;
 return N.validateRun({job:job(i),completedAt:new Date(Date.UTC(2026,10,25,0,0,i%60,i)).toISOString(),settings:N.opticalSettings(1550,30,k),input:inputs(),
  effective_index:Array.from({length:k},(_,m)=>2.9-0.17*m),field:field(k,t),origin:'local',serverVersion:'0.0.0',
  te_polarization_fraction:Array.from({length:k},(_,m)=>0.9-0.1*m),effective_area:Array.from({length:k},(_,m)=>2e-13*(m+1))});};
const LIMIT=90000,BUDGET=LIMIT-16*1024;

test('F2: no conversion while the fields fit (2000 seeded steps); the Save and recovery texts are those of main 499a0d3',async()=>{
 const golden=JSON.parse(fixture('sequence-fit-499a0d3.json'));
 const now=await FS.fitSequence(new URL(STATIC,'file://'+__dirname+'/').href);
 assert.equal(now.compact,false);assert.equal(golden.compact,false);
 assert.ok(now.versions.every(v=>v!==14),JSON.stringify(now.versions));
 assert.deepEqual(now.checkpoints,golden.checkpoints);assert.equal(now.chain,golden.chain);
 assert.ok(now.seen.result>500&&now.seen.import>50&&now.seen.open>50&&now.seen.restore>50&&now.seen.swap>10,JSON.stringify(now.seen));
});

// what the page does with its runs (workspace-app.mjs applyFieldBudget, with the conversion)
function tab(input=inputs()){
 const t={runs:[],used:0,selected:null,comparison:[null,null],dropSwap:null,fieldSwap:null,given:new Map(),input,arrivals:0,conversions:[],said:0,saidFlag:false};
 const numbered=runs=>{for(const r of runs)t.given.set(r.number,t.given.get(r.number)??r.job);};
 t.text=()=>N.sessionText(t.input,t.runs,t.selected,t.comparison,VIEW);
 t.arrive=(first=[],{loaded=false}={})=>{
  t.arrivals++;X.forgetHeldFields(t.runs);t.fieldSwap=null;
  const wasCompact=t.runs.some(r=>E.isCompactField(r.field)),fitsAsText=X.chooseFields(t.input,t.runs,t.selected,t.comparison,VIEW,{first,budget:BUDGET}).fits;
  const out=X.chooseFieldsAtArrival(t.input,t.runs,t.selected,t.comparison,VIEW,{first,budget:BUDGET,loaded});
  // F11: the conversion happens at an arrival that does not fit as text, in a tab that is not compact
  if(out.started){assert.ok(!wasCompact&&!fitsAsText,'the conversion starts at an arrival that does not fit as text');t.conversions.push(t.arrivals);if(!t.saidFlag){t.said++;t.saidFlag=true;}}
  if(!wasCompact&&fitsAsText)assert.equal(out.converted.length,0,'no conversion while the fields fit');
  // a compact tab holds no text field after an arrival
  if((wasCompact&&!loaded)||out.started)assert.ok(t.runs.every(r=>!r.field||E.isCompactField(r.field)),'every field is compact');
  // K8 with the compact sizes: the order's choice, the cached sum the written length
  const order=X.fieldOrder(t.runs,t.selected,first),keep=new Set(),expected=new Set();
  if(bytes(t.text())>BUDGET)order.forEach((r,i)=>{const trial=new Set([...keep,r.job]),b=bytes(N.sessionText(t.input,t.runs,t.selected,t.comparison,VIEW,{keep:trial}));if(b<=BUDGET||(i===0&&r.job===t.selected)){keep.add(r.job);expected.add(r.job);}});
  else for(const r of order)expected.add(r.job);
  const plain=out.letGo.filter(r=>!r.pinned);for(const r of out.letGo)X.letGoField(r);
  assert.deepEqual(new Set(t.runs.filter(r=>r.field).map(r=>r.job)),expected,'the fields kept are the order\'s choice');
  if(!out.fits)assert.equal(out.total,bytes(t.text()),'the cached sum is the written length');
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
 t.swapBack=()=>{const o=t.dropSwap;if(!o||t.runs!==o.list||!t.runs.includes(o.other))return 'no swap';t.runs=W.swapDropped(t.runs,o.kept,o.other);t.dropSwap=null;t.fieldSwap=null;t.arrive([o.kept.job]);return 'swap';};
 t.fieldsBack=()=>{const o=t.fieldSwap;if(!o||t.runs!==o.list||!X.heldField(o.back)||!o.other.field||o.other.job===t.selected)return 'no field swap';
  // the held field (Keep Run N's fields): let go after the conversion, so it is held compact and comes back compact
  const compactTab=t.runs.some(r=>E.isCompactField(r.field));
  const before=bytes(t.text());X.letGoField(o.other);X.takeBackField(o.back);X.forgetHeldFields(t.runs);t.fieldSwap=null;
  if(compactTab)assert.ok(E.isCompactField(o.back.field),'the field brought back is compact');t.heldBack=(t.heldBack||0)+(compactTab?1:0);
  assert.ok(bytes(t.text())<=Math.max(before,BUDGET),'a field swap stays within the budget');return 'field swap';};
 // Recompute Run N's fields: the same result again (float64); attached, then the arrival makes it compact
 t.recompute=k=>{const without=t.runs.filter(r=>!r.field);if(!without.length)return 'no recompute';const r=without[k%without.length];
  const fresh=result(parseInt(r.job,16));assert.equal(X.recomputeMismatch(r,fresh),null,'the values match');
  const compactBefore=t.runs.some(x=>E.isCompactField(x.field));X.attachField(r,fresh.field);t.arrive([r.job]);
  if(compactBefore&&r.field){assert.ok(E.isCompactField(r.field),'a recomputed field in a compact tab is compact');
   assert.deepEqual({...E.compactRecord(r.field)},E.encodeField(fresh.field),'its strings are those of the same result');}
  return 'recompute';};
 t.pin=(k,on)=>{const r=t.runs[k%Math.max(1,t.runs.length)];if(!r)return 'no run';r.pinned=on;t.dropSwap=null;return on?'pin':'unpin';};
 t.select=k=>{const r=t.runs[k%Math.max(1,t.runs.length)];if(!r)return 'no run';t.selected=r.job;return 'select';};
 t.rename=(k,label)=>{const r=t.runs[k%Math.max(1,t.runs.length)];if(!r)return 'no run';r.label=label;return 'rename';};
 t.compare=(a,b)=>{if(!t.runs.length)return 'no run';t.comparison=[t.runs[a%t.runs.length].job,t.runs[b%t.runs.length].job];return 'compare';};
 const load=session=>{for(const r of session.runs){const n=r.number;delete r.number;r.number=n;}t.runs=session.runs;t.used=W.numberRuns(t.runs);t.selected=session.selected;t.comparison=[...session.comparison];t.dropSwap=null;t.arrive([],{loaded:true});};
 t.open=()=>{load(N.parseSession(t.text()));return 'open';};
 t.restore=()=>{const make=N.captureSession(t.input,t.runs,t.selected,t.comparison,VIEW,{limit:LIMIT});load(R.readNotebookRecovery({version:1,savedAt:'2026-11-25T10:00:00.000Z',session:make()}).session);return 'restore';};
 t.import=(ids,numbers)=>{
  const other=ids.map((i,k)=>Object.assign(result(i),{number:numbers[k]}));let text;
  try{text=N.sessionText(t.input,other,null,[null,null],VIEW);}catch{return 'not written';}
  const session=N.parseSession(text);let merged;try{merged=N.mergeRuns(t.runs,session.runs,N.RUN_LIMIT);}catch(e){assert.fail('an import of the same results is not a conflict: '+e.message);}
  const next=merged.runs;t.used=W.numberRuns(next,Math.max(t.used,...t.runs.map(r=>r.number||0)));t.runs=next;t.dropSwap=null;
  numbered(next.filter(r=>merged.added.includes(r.job)));t.selected=next.findLast(r=>merged.added.includes(r.job)||merged.reused.includes(r.job))?.job??t.selected;
  if(!t.runs.some(r=>r.job===t.comparison[0]))t.comparison=[t.selected,t.selected];if(!t.runs.some(r=>r.job===t.comparison[1]))t.comparison=[t.comparison[0],t.selected];
  t.arrive();return 'import';
 };
 return t;
}
const random=seed=>()=>{seed|=0;seed=seed+0x6D2B79F5|0;let t=Math.imul(seed^seed>>>15,1|seed);t=t+Math.imul(t^t>>>7,61|t)^t;return((t^t>>>14)>>>0)/4294967296;};

test('F11: tab = file = recovery with the conversion (2000 seeded steps); one conversion, at the first arrival that does not fit as text',()=>{
 const rand=random(20261127),t=tab(),seen={},arriving=new Set(['result','result again','result drop','swap','recompute','import','open','restore']);let pool=0,firstUnfit=null;
 for(let step=0;step<2000;step++){
  const x=rand(),before=new Map(t.runs.map(r=>[r.job,r.field])),pick=()=>Math.floor(rand()*20),arrivals=t.arrivals;let what;
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
  if(firstUnfit===null&&t.conversions.length)firstUnfit=step;
  if(!arriving.has(what)&&what!=='field swap')for(const r of t.runs)assert.equal(r.field,before.get(r.job),`step ${step} (${what}): Run ${r.number}'s field is unchanged`);
  const numbers=t.runs.map(r=>r.number);
  assert.ok(numbers.every((n,i)=>i===0||n>numbers[i-1]),`step ${step} (${what}): ${numbers} increase`);
  for(const r of t.runs)assert.equal(t.given.get(r.number),r.job,`step ${step} (${what}): number ${r.number} is one job's`);
  assert.equal(t.used,Math.max(0,...numbers),`step ${step} (${what}): next = largest + 1`);
  if(!t.runs.length)continue;
  // Save = captureSession = recovery, and the tab's fields are the file's
  const save=N.writeOpticalSession(t.input,t.runs,t.selected,t.comparison,VIEW,{limit:LIMIT});
  assert.equal(save.ok,true,`step ${step} (${what}): Save asks nothing`);
  const text=N.captureSession(t.input,t.runs,t.selected,t.comparison,VIEW,{limit:LIMIT})();
  assert.equal(text,save.text,`step ${step} (${what}): recovery equals Save`);
  const doc=JSON.parse(save.text);
  assert.deepEqual(doc.runs.map(r=>Object.hasOwn(r,'field')),t.runs.map(r=>!!r.field),`step ${step} (${what}): the tab's fields are the file's`);
  assert.deepEqual(doc.runs.map(r=>r.field?.encoding??null),t.runs.map(r=>r.field?E.compactRecord(r.field)?.encoding??null:null),`step ${step} (${what}): compact in the tab, compact in the file`);
  assert.equal(doc.version===14,t.runs.some(r=>E.isCompactField(r.field)),`step ${step} (${what}): version 14 exactly with a compact field`);
  if(arriving.has(what))assert.ok(bytes(save.text)<=BUDGET,`step ${step} (${what}): within the budget`);
  // what a file holds is what the tab holds: the samples read back are the tab's
  if(what==='open'||what==='restore'){const back=N.parseSession(save.text);back.runs.forEach((r,i)=>{if(r.field)assert.deepEqual(r.field.real,t.runs[i].field.real,`step ${step}: Run ${r.number}'s samples`);});}
  if(t.arrivals===arrivals)continue;
 }
 assert.ok(t.heldBack>0,'Keep Run N\'s fields in a compact tab');
 assert.equal(t.conversions.length,1,'one conversion: '+t.conversions);assert.equal(t.said,1,'its sentence once');
 assert.ok(firstUnfit>0,'the conversion is not at the first step');
 for(const kind of ['result','result drop','pin','unpin','swap','field swap','recompute','import','save','open','restore'])assert.ok(seen[kind]>0,kind+' '+JSON.stringify(seen));
});

test('F1 (tab path): every earlier fixture opened, nothing changed, saved and kept for recovery is its own bytes; no conversion',()=>{
 const golden=JSON.parse(fixture('sessions-rewritten-13f07f4.json'));
 const texts={...Object.fromEntries(['empty','one','three'].flatMap(s=>[[`optical-v7-${s}.json`,fixture(`optical-v7-${s}.json`)],[`optical-v6-${s}.json`,fixture(`optical-v6-${s}.json`)]])),
  'optical-v12-numbers.json':fixture('optical-v12-numbers.json'),'optical-v13-nine-runs.json':fixture('optical-v13-nine-runs.json'),'optical-values-only-14.json':fixture('optical-values-only-14.json'),
  'optical-v14-compact.json':fixture('optical-v14-compact.json'),...golden};
 for(const [name,text] of Object.entries(texts)){
  const s=N.parseSession(text),expected=N.sessionText(s.input,s.runs,s.selected,s.comparison,s.view);
  // the page keeps each run's stored number on its own runs (completeLoad), then the fields arrive
  for(const r of s.runs){const n=r.number;delete r.number;r.number=n;}
  const out=X.chooseFieldsAtArrival(s.input,s.runs,s.selected,s.comparison,s.view,{loaded:true});for(const r of out.letGo)X.letGoField(r);
  assert.deepEqual(out.converted,[],name+': no field made compact');assert.equal(out.started,false,name);
  const save=N.writeOpticalSession(s.input,s.runs,s.selected,s.comparison,s.view);
  assert.equal(save.text,expected,name+': Save');
  if(s.runs.length)assert.equal(N.captureSession(s.input,s.runs,s.selected,s.comparison,s.view)(),expected,name+': recovery');
  assert.equal(JSON.parse(save.text).version===14,name==='optical-v14-compact.json',name);
 }
 // the version 14 fixture: a text run arriving in a compact tab is made compact at the next arrival
 const s=N.parseSession(fixture('optical-v14-compact.json')),out=X.chooseFieldsAtArrival(s.input,s.runs,s.selected,s.comparison,s.view,{loaded:true});
 assert.deepEqual(out.converted,[]);
 for(const r of s.runs){const n=r.number;delete r.number;r.number=n;}
 const imported=N.mergeRuns(s.runs,[N.validateRun({...result(77)})]);imported.runs.at(-1).number=9;const after=X.chooseFieldsAtArrival(s.input,imported.runs,s.selected,s.comparison,s.view);
 assert.deepEqual(after.converted.map(r=>r.job),[s.runs[2].job,job(77)]);assert.equal(after.started,false,'a tab opened compact: no sentence');
});

test('named case: a field single precision cannot hold stays as text (project-v1.json\'s synthetic runs); the other fields are made compact; the text round-trips',()=>{
 // the encoder refuses a sample beyond float32: an overflow, or a nonzero sample that would become 0 or a subnormal
 for(const x of [1e39,-3.5e38,1e-39,-5e-324,1e-46])assert.throws(()=>E.encodeField({node_coordinates:[[0,0],[1,0],[0,1]],triangles:[[0,1,2]],real:[[[1,x,0]]],imag:[[[0,0,0]]]}),{message:'A field sample is beyond single precision.'},String(x));
 // an exact zero (and -0) and the smallest normal float32 are held
 assert.doesNotThrow(()=>E.encodeField({node_coordinates:[[0,0],[1,0],[0,1]],triangles:[[0,1,2]],real:[[[0,-0,2**-126]]],imag:[[[-(2**-126),3.4e38,0]]]}));
 // project-v1.json's runs hold 1e308 and 5e-324: they stay text beside a run that goes compact
 const s=N.parseSession(PROJECT.readProject(fixture('project-v1.json')).models.find(m=>m.kind==='workspace').text);
 for(const r of s.runs){const n=r.number;delete r.number;r.number=n;}
 // (their synthetic samples give TE fractions and areas that are not numbers, so the budget of a tab
 // holding them is not computed, as before: here they arrive into a tab already compact)
 const compactRun=N.compactRunField(Object.assign(N.validateRun(result(4)),{number:3})),fresh=Object.assign(N.validateRun(result(5)),{number:4}),runs=[...s.runs,compactRun,fresh];
 const out=X.compactFields(s.input,runs,fresh.job,[null,null],VIEW,{budget:1});
 assert.equal(out.started,false);assert.deepEqual(out.converted,[fresh]);
 assert.deepEqual(runs.map(r=>E.isCompactField(r.field)),[false,false,true,true]);
 // the text fields are written as before; the file is version 14 and round-trips byte for byte
 const text=N.sessionText(s.input,runs,fresh.job,[null,null],VIEW),doc=JSON.parse(text);
 assert.equal(doc.version,14);assert.deepEqual(doc.runs.map(r=>r.field.encoding??'text'),['text','text','f32-base64-v1','f32-base64-v1']);
 const original=JSON.parse(PROJECT.readProject(fixture('project-v1.json')).models.find(m=>m.kind==='workspace').text).runs;
 assert.deepEqual(doc.runs.slice(0,2).map(r=>S_JSON(r.field)),original.map(r=>S_JSON(r.field)),'the text fields are their own numbers');
 const back=N.parseSession(text),once=N.sessionText(back.input,back.runs,back.selected,back.comparison,back.view),again=N.parseSession(once);
 assert.equal(N.sessionText(again.input,again.runs,again.selected,again.comparison,again.view),once);
 // a tab holding them: no extra words (the conversion sentence is the only one), and their Results line is today's
 const app=fs.readFileSync(path.join(__dirname,STATIC,'workspace-app.mjs'),'utf8');
 assert.ok(app.includes("if(isCompactField(solverRun.field)){const line=document.createElement('p');line.id='field-precision';"),'the single-precision line is for a compact field only');
});

test('named case: optical-v14-compact.json opened with its text run and saved, untouched, is its own bytes',()=>{
 const text=fixture('optical-v14-compact.json'),s=N.parseSession(text);
 for(const r of s.runs){const n=r.number;delete r.number;r.number=n;}
 const out=X.chooseFieldsAtArrival(s.input,s.runs,s.selected,s.comparison,s.view,{loaded:true});
 assert.deepEqual(out.converted,[]);assert.equal(out.started,false);assert.deepEqual(out.letGo,[]);
 assert.ok(!E.isCompactField(s.runs[2].field),'Run 8 stays text');
 assert.equal(N.writeOpticalSession(s.input,s.runs,s.selected,s.comparison,s.view).text,text);
 assert.equal(N.captureSession(s.input,s.runs,s.selected,s.comparison,s.view)(),text);
 // a result arriving into this compact tab is made compact, and so is the text run beside it
 const fresh=Object.assign(N.validateRun(result(9)),{number:9}),runs=[...s.runs,fresh];
 const after=X.chooseFieldsAtArrival(s.input,runs,fresh.job,s.comparison,s.view);
 assert.deepEqual(after.converted.map(r=>r.number),[8,9]);assert.equal(after.started,false,'no sentence: the tab was compact');
});

test('the words of section 5, exactly, and where the page uses them',()=>{
 assert.equal(X.COMPACT_TEXT,'Fields are now kept at single precision (float32), so more of them fit in 16.8 MB. n_eff, TE fractions and effective areas are unchanged. Files saved from now on need this Studio or later (session version 14).');
 assert.equal(X.COMPACT_NOTE,'When fields would not all fit, they are kept at single precision.');
 assert.equal(X.COMPACT_RESULTS_TEXT,"Field at single precision (float32). The values above are the engine's.");
 assert.equal(X.COMPACT_EXPORT_TEXT,' (fields at single precision)');
 // "single precision" and "float32" once each in the Messages sentence
 assert.equal(X.COMPACT_TEXT.split('single precision').length,2);assert.equal(X.COMPACT_TEXT.split('float32').length,2);
 const app=fs.readFileSync(path.join(__dirname,STATIC,'workspace-app.mjs'),'utf8');
 assert.ok(app.includes("const compactWords=out.started&&!compactSaid?COMPACT_TEXT:'';"));
 assert.ok(app.includes("line.id='field-precision';line.className='input-hint';line.textContent=COMPACT_RESULTS_TEXT;"));
 assert.ok(app.includes('notice(isCompactField(solverRun.field)?compactExportNotice(words):words);'));
 assert.ok(app.includes("if(runs.some(r=>isCompactField(r.field)))limit.textContent=compactRunListNote(limit.textContent);"));
 // the combined strings for a compact run and a compact tab
 assert.equal(X.compactExportNotice("Run file studio-run-0000000d.json sent to the browser's downloads, with the run's inputs and fields. Add runs from file adds it to a session. The current design is unchanged."),
  "Run file studio-run-0000000d.json sent to the browser's downloads, with the run's inputs and fields (fields at single precision). Add runs from file adds it to a session. The current design is unchanged.");
 assert.equal(X.compactExportNotice("Run file studio-run-0000000d.json sent to the browser's downloads, with the run's inputs and fields (on the physical window only, PML excluded). Add runs from file adds it to a session. The current design is unchanged."),
  "Run file studio-run-0000000d.json sent to the browser's downloads, with the run's inputs and fields (fields at single precision) (on the physical window only, PML excluded). Add runs from file adds it to a session. The current design is unchanged.");
 assert.equal(X.compactRunListNote(N.RUNS_KEPT_TEXT+' Pinned runs stay; when a 21st run arrives, the oldest unpinned run is replaced. File › Save keeps every run in one file; Export this run writes one run to its own file.'),
  "Up to 20 runs are kept with their values. Fields are kept up to 16.8 MB: the selected and pinned runs' first, then the newest. A run without its fields can recompute them. When fields would not all fit, they are kept at single precision. Pinned runs stay; when a 21st run arrives, the oldest unpinned run is replaced. File › Save keeps every run in one file; Export this run writes one run to its own file.");
 // the field view's help keeps "Not absolute power."
 assert.ok(app.includes('Not absolute power.'));
});

test('F14 (module part, K12 in a compact tab): a recompute whose values differ attaches nothing; the compact run is unchanged',()=>{
 const s=N.parseSession(fixture('optical-v14-compact.json')),run=s.runs[1];Object.assign(run,{number:5});
 const before=N.sessionText(s.input,s.runs,s.selected,s.comparison,s.view,{keep:new Set()});
 X.letGoField(run);
 const fresh=N.validateRun({...run,field:{node_coordinates:[[0,0],[1e-6,0],[0,1e-6],[1e-6,1e-6],[5e-7,1.5e-6]],triangles:[[0,1,2],[1,3,2],[2,3,4]],real:[[[1,0,0],[1,0,0],[1,0,0]],[[1,0,0],[1,0,0],[1,0,0]]],imag:[[[0,0,0],[0,0,0],[0,0,0]],[[0,0,0],[0,0,0],[0,0,0]]]},effective_index:run.effective_index.map((x,i)=>i===0?x*(1+1e-9):x),te_polarization_fraction:run.te_polarization_fraction,effective_area:run.effective_area});
 const m=X.recomputeMismatch(run,fresh);assert.equal(m.name,'n_eff');assert.equal(m.mode,1);
 assert.equal(X.notRecomputedText(run,m),"Run 5 · Reference's fields were not recomputed: mode 1 n_eff came out 2.900000003, stored 2.900000000. Run 5 · Reference is unchanged. Use this run's inputs and Run study to make a new run.");
 // nothing attached: the run's record (without its field) is as it was
 assert.equal(run.field,null);
 assert.equal(N.sessionText(s.input,s.runs,s.selected,s.comparison,s.view,{keep:new Set()}),before);
 // Keep Run N's fields brings the compact field back, its record unchanged
 assert.ok(X.takeBackField(run));assert.ok(E.isCompactField(run.field));
 assert.equal(N.sessionText(s.input,s.runs,s.selected,s.comparison,s.view),fixture('optical-v14-compact.json'));
});

// ---- F6 and F8: accuracy -----------------------------------------------------------------
// a run of the fixture field or of an engine result, as text and its compact copy (the same job)
function pairOf(run){
 const copy=N.validateRun({...run});Object.assign(copy,{number:run.number??1});
 const compact=N.validateRun({...run});Object.assign(compact,{number:run.number??1});N.compactRunField(compact);
 return [copy,compact];
}
const S_JSON=x=>JSON.stringify(x);
const COMPONENTS=['magnitude','Ex','Ey','Ez'];
const PROBE_TEXTS=[];
// two probe values whose 6-digit texts are one unit apart in the last shown digit, with |Δ| ≤ 1e-6
function oneUnit(a,b){
 if(Math.abs(a-b)>1e-6)return false;
 const ta=a.toPrecision(6),tb=b.toPrecision(6),parse=t=>{const [m,e='0']=t.split('e');const digits=m.replace('-','').replace('.','');const point=m.includes('.')?m.split('.')[1].length:0;return {n:BigInt(digits)*(m.startsWith('-')?-1n:1n),scale:point-Number(e)};};
 const pa=parse(ta),pb=parse(tb);if(pa.scale!==pb.scale)return Math.abs(a-b)<=1e-6&&Number(ta)!==Number(tb)&&Math.abs(Number(ta)-Number(tb))<=Math.max(Math.abs(Number(ta)),Math.abs(Number(tb)))*1.000001e-5;
 const d=pa.n-pb.n;return d===1n||d===-1n;
}
function accuracy(text,compact,label){
 const a=text.field,b=compact.field,k=a.real.length,report={sample:0,te:0,area:0,view:0,probe:0,probeTexts:0,probeTextsDiffer:[],probeTextsBad:[]};
 // each sample within 2^-24 relative (round to nearest, -0 kept); coordinates and triangles identical
 assert.deepEqual(b.node_coordinates,a.node_coordinates,label);assert.deepEqual(b.triangles,a.triangles,label);assert.deepEqual(b.nodes,a.nodes,label);
 for(const part of ['real','imag'])a[part].forEach((m,i)=>m.forEach((v,t)=>v.forEach((x,c)=>{const y=b[part][i][t][c];
  assert.ok(Math.abs(y-x)<=2**-24*Math.abs(x),`${label} ${part} ${i} ${t} ${c}`);if(Object.is(x,-0))assert.ok(Object.is(y,-0));if(x!==0)report.sample=Math.max(report.sample,Math.abs(y-x)/Math.abs(x));})));
 // TE fraction and A_eff by Studio's formulas from the field (on the physical window for an open run)
 const bounds=OR.isOpenRun(text)?F.physicalBounds(text.open_boundary):null;
 const win=bounds?M.physicalWindow(a,bounds):null;
 for(let i=0;i<k;i++){
  const ta=M.teFraction(a,i,win),tb=M.teFraction(b,i,win),aa=M.effectiveArea(a,i,win),ab=M.effectiveArea(b,i,win);
  report.te=Math.max(report.te,Math.abs(tb-ta)/Math.abs(ta||1));report.area=Math.max(report.area,Math.abs(ab-aa)/Math.abs(aa));
  for(const component of COMPONENTS){const va=F.fieldScalars(a,i,component).values,vb=F.fieldScalars(b,i,component).values;va.forEach((v,j)=>{report.view=Math.max(report.view,Math.abs(vb[j]-v));});}
  // the probe at three points: the value and its text
  const va=F.fieldScalars(a,i).values,vb=F.fieldScalars(b,i).values;
  for(const [x,y] of [[0,0.11],[0.12,0.05],[-0.3,0.15],[0.5,0.5]]){const pa=PB.probeField(a,va,x,y),pb=PB.probeField(b,vb,x,y);
   assert.equal(!!pa,!!pb,label);if(pa){report.probe=Math.max(report.probe,Math.abs(pb.value-pa.value));assert.equal(pb.index,pa.index);report.probeTexts++;
    if(pb.value.toPrecision(6)!==pa.value.toPrecision(6)){report.probeTextsDiffer.push(`mode ${i+1} at (${x}, ${y}): ${pa.value} "${pa.value.toPrecision(6)}" vs ${pb.value} "${pb.value.toPrecision(6)}"`);if(!oneUnit(pa.value,pb.value))report.probeTextsBad.push(`mode ${i+1} at (${x}, ${y})`);}}}
  // every triangle's probe text (the value the probe shows anywhere in that triangle)
  va.forEach((v,j)=>{report.probeTexts++;if(v.toPrecision(6)!==vb[j].toPrecision(6)){report.probeTextsDiffer.push(`mode ${i+1} triangle ${j+1}: ${v} vs ${vb[j]}`);if(!oneUnit(v,vb[j]))report.probeTextsBad.push(`mode ${i+1} triangle ${j+1}`);}});
 }
 assert.ok(report.te<=1e-6&&report.area<=1e-6,`${label} TE and A_eff: ${JSON.stringify(report)}`);
 assert.ok(report.view<=1e-6&&report.probe<=1e-6,`${label} field view and probe: ${JSON.stringify(report)}`);
 // F6, the probe text (re-registered after the result, ruling 2026-11-25 "F6 after the result"): identical, or
 // one unit apart in the last shown digit while |Δ| ≤ 1e-6; the count that differs is recorded
 PROBE_TEXTS.push({label,checked:report.probeTexts,differ:report.probeTextsDiffer.length,first:report.probeTextsDiffer.slice(0,3)});
 assert.deepEqual(report.probeTextsBad,[],`${label}: a probe text more than one unit apart`);
 // core and edge notes: the same texts
 assert.deepEqual(M.coreNotes(compact).map(n=>n.text),M.coreNotes(text).map(n=>n.text),label);
 assert.deepEqual(M.edgeNotes(compact).map(n=>n.text),M.edgeNotes(text).map(n=>n.text),label);
 // the stored values (n_eff, TE, A_eff, n_g, candidates): the record without its field is unchanged
 assert.equal(N.sessionText(text.input,[compact],null,[null,null],VIEW,{keep:new Set()}),N.sessionText(text.input,[text],null,[null,null],VIEW,{keep:new Set()}),label);
 return report;
}
function profiles(text,compact,label){
 // F8: the profile through the core (x and y): the same rows and columns; relative_amplitude [1] within 1e-6
 for(const [axis,coordinate] of [['x',0.11],['y',0]]){
  const csv=run=>PR.profileCsv([{run,mode:0,segments:PR.lineProfile(run.field,F.fieldScalars(run.field,0).values,axis,coordinate)}],axis,coordinate,0,'magnitude').trim().split('\n').map(r=>r.split(','));
  const A=csv(text),B=csv(compact);assert.equal(B.length,A.length,label);assert.ok(A.length>1,label+' a profile through the core');
  A.forEach((row,i)=>{assert.deepEqual(B[i].slice(0,-1),row.slice(0,-1),`${label} ${axis} row ${i}`);if(i)assert.ok(Math.abs(Number(B[i].at(-1))-Number(row.at(-1)))<=1e-6,`${label} ${axis} row ${i} amplitude`);});
 }
}

test('F6 and F8: what Studio computes from the fixture fields at single precision (open a0000004, and the closed nine-run fields)',()=>{
 const open=N.parseSession(fixture('optical-v10-open-full-083e151.json')),runs=[open.runs[0],...N.parseSession(fixture('optical-v13-nine-runs.json')).runs.filter(r=>r.field)];
 for(const run of runs){const [text,compact]=pairOf(run);accuracy(text,compact,`Run ${run.job}`);}
 const [text,compact]=pairOf(open.runs[0]);profiles(text,compact,'a0000004');
 // Compare: the overlaps of the open run with itself compact, and the same pairs and texts
 const a=MA.opticalMatch(text,text),b=MA.opticalMatch(compact,compact);
 assert.deepEqual(MA.compareMatchRows(b).map(r=>r.text),MA.compareMatchRows(a).map(r=>r.text));
 console.log('F6 probe texts (fixture fields), measured:',JSON.stringify(PROBE_TEXTS.map(({label,checked,differ})=>({label,checked,differ}))));
});

const RESULTS=process.env.STUDIO_RETENTION_RESULTS;
test('F6 and F8: the five T18 results',{skip:!RESULTS&&'needs tools/studio_run_retention.mjs engine results (STUDIO_RETENTION_RESULTS)'},async()=>{
 const T18=await import(path.join(__dirname,'../../tools/studio_run_retention.mjs'));
 const runs={};
 for(const [i,name] of ['t18closed2','t18closed4','t18near','t16','t18open'].entries()){
  const res=JSON.parse(fs.readFileSync(path.join(RESULTS,`${name}.one-a.result.json`),'utf8'));
  runs[name]=Object.assign(RR.runOfResult(res,await T18.pendingOf(name,(0xe0000000+i).toString(16)),{completedAt:new Date(Date.UTC(2026,10,25,0,i)).toISOString()}),{number:i+1});
 }
 const pairs={},reports={};
 for(const [name,run] of Object.entries(runs)){pairs[name]=pairOf(run);reports[name]=accuracy(...pairs[name],name);profiles(...pairs[name],name);}
 // Compare, every entry: the pairs of F6, overlaps within 1e-6, the same accepted flags and the same Δn_eff and overlap texts
 for(const [x,y] of [['t18closed2','t16'],['t16','t18open'],['t18closed2','t18closed4'],['t18near','t18closed4']]){
  const a=MA.opticalMatch(pairs[x][0],pairs[y][0]),b=MA.opticalMatch(pairs[x][1],pairs[y][1]);
  assert.equal(b.pairs.length,a.pairs.length,`${x} ~ ${y}`);
  a.pairs.forEach((p,i)=>{const q=b.pairs[i];assert.equal(q.accepted,p.accepted,`${x} ~ ${y} pair ${i}`);assert.ok(Math.abs(q.eta-p.eta)<=1e-6,`${x} ~ ${y} pair ${i}: ${q.eta} vs ${p.eta}`);assert.equal(MA.matchText(q),MA.matchText(p));});
  assert.deepEqual(MA.compareMatchRows(b).map(r=>r.text),MA.compareMatchRows(a).map(r=>r.text),`${x} ~ ${y} rows`);
  assert.deepEqual(b.pairs.map(p=>[p.a,p.b]),a.pairs.map(p=>[p.a,p.b]),`${x} ~ ${y} the same pairs`);
 }
 console.log(JSON.stringify(reports,(k,v)=>k==='probeTextsDiffer'?v.length:v));
 console.log('F6 probe texts (T18):',JSON.stringify(PROBE_TEXTS.filter(p=>p.label.startsWith('t'))));

});
