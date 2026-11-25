// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
// Round 26, C1: the line before a run ("If you run: Run 5 (…) keeps its values, not its fields") and
// the line without an estimate follow the arrival rule. The result's arrival (chooseFieldsAtArrival)
// makes every field compact first when the tab holds no compact field and the fields would not all
// fit as text; the prediction did not, so a tab that the next run converts (every field then kept)
// was told a run would lose its fields (agent round 26, P03 at T21: seven runs of the task set, Modes
// to find 2, the like-run an open n_g run). Checked here: the prediction is what the arrival then does.
const test=require('node:test');const assert=require('node:assert/strict');
const fs=require('node:fs');const path=require('node:path');
const STATIC='../../packages/simcase/src/simcase/studio/static/';
const fixture=name=>fs.readFileSync(path.join(__dirname,'studio_session_fixtures',name),'utf8');
let N,X,E;
test.before(async()=>{
 N=await import(STATIC+'workspace-notebook.mjs');X=await import(STATIC+'workspace-retention.mjs');E=await import(STATIC+'workspace-field-encoding.mjs');
});
const VIEW={mode:0,component:'magnitude',window:'Core region'};
const PHANTOM='ffffffff';

// A tab of n runs, each a copy of the open run a0000004 (776 triangles, 2 modes, an open boundary),
// read from the file once; every run gets its own copy, so no two runs share a field object.
let ONE=null;
function tab(n){
 if(!ONE){const s=N.parseSession(fixture('optical-v10-open-full-083e151.json'));ONE={input:s.input,run:s.runs[0]};}
 const runs=Array.from({length:n},(_,i)=>Object.assign(structuredClone(ONE.run),{job:(0xa0000010+i).toString(16),number:i+1,origin:'local'}));
 return {input:ONE.input,runs,selected:runs.at(-1).job,comparison:[runs.at(Math.max(0,n-2)).job,runs.at(-1).job]};
}
const textBytes=t=>N.runFieldBytes(t.runs[0]),compactBytes=t=>E.compactBytesOf(t.runs[0].field);
const base=t=>N.sessionBytesWithoutFields(t.input,t.runs,t.selected,t.comparison,VIEW);
// the session bytes without fields once the next result is in it (its record, selected)
function baseAfter(t){
 const like=t.runs.at(-1),top=Math.max(...t.runs.map(r=>r.number));
 const runs=N.appendRun(t.runs,Object.assign({...like,job:PHANTOM,pinned:false,label:''},{number:top+1}),N.RUN_LIMIT);
 return N.sessionBytesWithoutFields(t.input,runs,PHANTOM,t.comparison,{...VIEW,mode:0});
}
// the next result of the like-run's inputs as the page appends it: like's record, a new job, the next number, selected
function arrive(t,{budget}){
 const like=t.runs.at(-1),top=Math.max(...t.runs.map(r=>r.number));
 const runs=N.appendRun(t.runs,Object.assign({...like,job:PHANTOM,pinned:false,label:''},{number:top+1}),N.RUN_LIMIT);
 return X.chooseFieldsAtArrival(t.input,runs,PHANTOM,t.comparison,{...VIEW,mode:0},{budget});
}
const predict=(t,budget)=>X.predictedLetGo(t.input,t.runs,t.selected,t.comparison,VIEW,X.runFieldSizeKey(t.runs.at(-1)),{budget});
// the prediction as it was (text sizes), to show each case is one the old line got wrong or right
function textPrediction(t,budget){
 const like=t.runs.at(-1),top=Math.max(...t.runs.map(r=>r.number));
 const after=N.appendRun(t.runs,Object.assign({...like,job:PHANTOM,pinned:false,label:''},{number:top+1}),N.RUN_LIMIT);
 return X.chooseFields(t.input,after,PHANTOM,t.comparison,{...VIEW,mode:0},{budget,bytes:r=>r.job===PHANTOM?N.runFieldBytes(like):N.runFieldBytes(r)}).letGo;
}

test('C1 (a): seven text runs whose next result converts the tab: no line, and the arrival keeps every field',()=>{
 const t=tab(7),T=textBytes(t),C=compactBytes(t);assert.ok(C<T/2,`compact ${C} < text ${T}/2`);
 assert.ok(!t.runs.some(r=>E.isCompactField(r.field)));
 // eight fields fit compact but not as text (the phantom result is the eighth)
 const budget=baseAfter(t)+8*C+1000;assert.ok(budget<baseAfter(t)+8*T);
 assert.ok(textPrediction(t,budget).length>0,'the text-size prediction named a run (the round 26 line)');
 assert.deepEqual(predict(t,budget).map(r=>r.number),[],'no line');
 assert.equal(X.keepsValuesText([]).includes('If you run:'),true);
 const out=arrive(tab(7),{budget});
 assert.equal(out.started,true);assert.equal(out.converted.length,8);assert.deepEqual(out.letGo.map(r=>r.number),[]);
});

test('C1 (b): when even compact sizes do not fit, the line stays and names the run the arrival lets go',()=>{
 for(const keep of [6,5,3]){
  const t=tab(7),C=compactBytes(t),budget=baseAfter(t)+keep*C+500;
  const named=predict(t,budget).map(r=>r.number);
  const out=arrive(tab(7),{budget});
  assert.equal(out.started,true);
  assert.deepEqual(named,out.letGo.map(r=>r.number),`keep ${keep}`);
  assert.equal(named.length,8-keep,`keep ${keep}: ${named}`);
  assert.ok(X.keepsValuesText(predict(t,budget)).startsWith(`If you run: Run ${named[0]} (`));
 }
});

test('C1 (c): a tab already compact is predicted as before (the sizes are its own)',()=>{
 const t=tab(7);for(const r of t.runs)N.compactRunField(r);
 const C=compactBytes(t),budget=baseAfter(t)+6*C+500,next=X.runFieldSizeKey(t.runs.at(-1));
 const sizes=X.arrivalSizes(t.input,t.runs,t.selected,t.comparison,VIEW,{budget});
 assert.equal(sizes,N.runFieldBytes,'a compact tab counts runFieldBytes');
 const like=t.runs.at(-1),top=Math.max(...t.runs.map(r=>r.number));
 const after=N.appendRun(t.runs,Object.assign({...like,job:PHANTOM,pinned:false,label:''},{number:top+1}),N.RUN_LIMIT);
 const before=X.chooseFields(t.input,after,PHANTOM,t.comparison,{...VIEW,mode:0},{budget,bytes:r=>r.job===PHANTOM?N.runFieldBytes(like):N.runFieldBytes(r)}).letGo;
 assert.deepEqual(X.predictedLetGo(t.input,t.runs,t.selected,t.comparison,VIEW,next,{budget}).map(r=>r.number),before.map(r=>r.number));
 assert.equal(before.length,2);
 // while the fields fit as text, the sizes are the text sizes (nothing converts)
 const fit=tab(3);assert.equal(X.arrivalSizes(fit.input,fit.runs,fit.selected,fit.comparison,VIEW),N.runFieldBytes);
});

test('C1: a field single precision cannot hold stays text in the prediction too (compactBytesOf null)',()=>{
 const t=tab(2),f=t.runs[0].field;
 assert.equal(E.compactBytesOf(f),E.compactFieldBytes(E.encodeField(f)));
 const big={...f,real:f.real.map((m,i)=>i===0?m.map((v,j)=>j===0?[1e308,v[1],v[2]]:v):m)};
 assert.equal(E.compactBytesOf(big),null);
 const tiny={...f,imag:f.imag.map((m,i)=>i===1?m.map((v,j)=>j===3?[v[0],1e-40,v[2]]:v):m)};
 assert.equal(E.compactBytesOf(tiny),null);
 assert.throws(()=>E.encodeField(big));assert.throws(()=>E.encodeField(tiny));
 // a compact field gives its record's bytes
 N.compactRunField(t.runs[0]);assert.equal(E.compactBytesOf(t.runs[0].field),N.runFieldBytes(t.runs[0]));
});

test('C1: no estimate: the line counts the room left at the sizes the arrival applies',()=>{
 const other=X.fieldSizeKey({shapes:[{type:'rect',name:'Core',material:'Silicon',x:-100,y:0,w:200,h:300}],coreMesh:30,boundary:null,modeCount:8});
 const risk=(t,budget)=>X.unestimatedFieldRisk(t.input,t.runs,t.selected,t.comparison,VIEW,other,{budget});
 // every text field fits, with room for one more compact field but not one more text field: the
 // arrival of a field like these converts the tab, so no line (the text-size count said there was)
 let t=tab(7);const T=textBytes(t),C=compactBytes(t),roomy=base(t)+7*T+Math.floor(T/2);
 assert.ok(T/2>C);
 assert.equal(X.chooseFields(t.input,t.runs,t.selected,t.comparison,VIEW,{budget:roomy}).fits,true);
 assert.ok(roomy-(base(t)+7*T)<T,'at text sizes the room left is less than a field');
 assert.equal(risk(t,roomy),false);
 // not even one more compact field fits: the line stays
 t=tab(7);assert.equal(risk(t,base(t)+7*C+C-1),true);
 // a compact tab: as before, at its own sizes
 t=tab(7);for(const r of t.runs)N.compactRunField(r);
 assert.equal(risk(t,base(t)+7*C+C-1),true);assert.equal(risk(t,base(t)+7*C+C),false);
});

test('C1: over seeded tabs and budgets, the prediction is the arrival',()=>{
 let seed=20261126;const rand=()=>{seed=(seed*1103515245+12345)>>>0;return seed/4294967296;};
 let named=0,converted=0;
 for(let k=0;k<30;k++){
  const n=2+Math.floor(rand()*9),t=tab(n),T=textBytes(t),C=compactBytes(t);
  const pins=t.runs.map(()=>rand()<0.2);t.runs.forEach((r,i)=>{r.pinned=pins[i];});
  const budget=Math.round(baseAfter(t)+(n+1)*(C+(T-C)*rand()*1.3)*rand()*1.4+C);
  const predicted=predict(t,budget).map(r=>r.job);
  const again=tab(n);again.runs.forEach((r,i)=>{r.pinned=pins[i];});
  const out=arrive(again,{budget});
  assert.deepEqual(predicted,out.letGo.map(r=>r.job).filter(j=>j!==PHANTOM),`tab ${k}: ${n} runs, budget ${budget}`);
  if(predicted.length)named++;if(out.started)converted++;
 }
 assert.ok(named>5&&converted>10,`named ${named}, converted ${converted}`);
});
