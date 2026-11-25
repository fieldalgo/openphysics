// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
// Round 25: usability fixes of the optical model (A1 to A4, pre-registered P1 to P4).
// Plain text comparison only: no RegExp is built from a dynamic string.
const test=require('node:test');const assert=require('node:assert/strict');
const fs=require('node:fs');const path=require('node:path');
const STATIC='../../packages/simcase/src/simcase/studio/static/';
const read=name=>fs.readFileSync(path.join(__dirname,STATIC,name),'utf8');

test('P3 (A3): a named pair read from a file is kept because it is named, so the newest-pair offer appears',async()=>{
 const C=await import(STATIC+'workspace-compare.mjs');
 const runs=[1,2,3].map(n=>({job:'j'+n,number:n,...(n<3?{label:'Design '+'AB'[n-1]}:{})}));
 const named=['j1','j2'];
 // read from a file: the named pair is not the default one, yet not picked by hand
 assert.equal(C.pairChosen(runs,named),false);
 // an unnamed pair that is not the default, or a pair with one named run: picked, as before
 const plain=[1,2,3].map(n=>({job:'j'+n,number:n,label:''}));
 assert.equal(C.pairChosen(plain,['j1','j2']),true);
 assert.equal(C.pairChosen([{job:'j1',label:'Design A'},{job:'j2',label:''},{job:'j3',label:''}],['j1','j2']),true);
 // the default pair is never picked; one named run on both sides is not a named pair
 assert.equal(C.pairChosen(runs,['j2','j3']),false);
 assert.equal(C.pairChosen(runs,['j1','j1']),true);
 // one new run after the file: the pair stays (named) and Compare offers the two newest
 const after=[...runs,{job:'j4',number:4,label:''}],picked=C.pairChosen(runs,named);
 assert.deepEqual(C.comparisonAfterRun(after,named,picked),named);
 assert.deepEqual(C.newestPairOffer(after,named,picked),['j3','j4']);
 // the page reads a file's pair through pairChosen, unchanged in shape
 assert.ok(read('workspace-app.mjs').includes('compareIds=[...session.comparison];comparePicked=pairChosen(runs,compareIds);'));
});

// ---- P1 (A1): the words say when fields move; a warning before a run with no size estimate ----
const VIEW={mode:0,component:'magnitude',window:'Core region'};
const setup={materials:{Core:'Silicon',Oxide:'Silica',Heater:''},temperature:293.15,cooling:'',fixed:'',terminal:''};
async function retention(){
 const N=await import(STATIC+'workspace-notebook.mjs'),P=await import(STATIC+'workspace-project.mjs'),X=await import(STATIC+'workspace-retention.mjs');
 const inputs=()=>P.snapshot({width:500,voltage:1,electric:false,heat:false,structure:false,optics:true,wavelength:1550,coreMesh:30},setup);
 const field=(k,t)=>{const X0=[],T=[];for(let i=0;i<=t;i++)X0.push([i*1e-8,0],[i*1e-8,1e-8]);for(let i=0;i<t;i++)T.push([2*i,2*i+2,2*i+1]);
  const mode=m=>T.map((_,i)=>[1+i*1e-3,0.25*m+i*1e-4,1e-3*(m+1)]);return {node_coordinates:X0,triangles:T,real:Array.from({length:k},(_,m)=>mode(m)),imag:Array.from({length:k},(_,m)=>T.map(()=>[0,1e-9*m,0]))};};
 const run=(i,k=2)=>Object.assign(N.validateRun({job:i.toString(16).padStart(8,'0'),completedAt:new Date(Date.UTC(2026,10,25,0,0,i)).toISOString(),settings:N.opticalSettings(1550,30,k),input:inputs(),
  effective_index:Array.from({length:k},(_,m)=>2.9-0.17*m),field:field(k,12),origin:'local',serverVersion:'0.0.0'}),{number:i});
 return {N,X,inputs,run};
}

test('P1 (A1): the run list note and Results say when fields move, exactly',async()=>{
 const {N,X}=await retention();
 assert.equal(N.RUNS_KEPT_TEXT,"Up to 20 runs are kept with their values. Fields are kept up to 16.8 MB. When a result or a recompute arrives, Studio keeps the selected run's fields first, then pinned runs', then the newest. Selecting a run does not bring its fields back; Recompute does.");
 const four={number:4,label:''};
 assert.equal(X.fieldsNotKeptResultsText(four),"Run 4's fields are not kept; its n_eff, TE fractions and effective areas are kept. Fields are kept up to 16.8 MB. When a result or a recompute arrives, Studio keeps the selected run's fields first, then pinned runs', then the newest. Selecting a run does not bring its fields back; Recompute does.");
 // a run read from a file without its fields keeps its words
 assert.equal(X.fieldsNotKeptResultsText(four,true),"Run 4's fields were not kept in the session file. Its n_eff, TE fractions and effective areas are kept.");
 assert.equal(X.FIELDS_MAY_GO_TEXT,"If you run: older runs' fields may not be kept (16.8 MB limit) · pin a run to keep its fields first");
 // the run list keeps the rest of its note
 assert.ok(read('workspace-app.mjs').includes("limit.textContent=RUNS_KEPT_TEXT+' Pinned runs stay; when a 21st run arrives, the oldest unpinned run is replaced. File › Save keeps every run in one file; Export this run writes one run to its own file.';"));
});

test('P1 (A1): with no run of the same key, the line shows only when the room left is less than the smallest kept field',async()=>{
 const {N,X,inputs,run}=await retention();
 const runs=[run(1),run(2),run(3)],sel=runs[2].job,cmp=[runs[1].job,runs[2].job],input=inputs();
 const size=r=>({1:300,2:200,3:500})[r.number];
 const base=N.sessionBytesWithoutFields(input,runs,sel,cmp,VIEW),total=base+1000;
 const other=X.fieldSizeKey({shapes:[{type:'rect',name:'Core',material:'Silicon',x:-100,y:0,w:200,h:300}],coreMesh:30,boundary:null,modeCount:8});
 const risk=budget=>X.unestimatedFieldRisk(input,runs,sel,cmp,VIEW,other,{budget,bytes:size});
 // every field kept: room left = budget - total; the smallest kept field is 200 bytes
 assert.equal(risk(total+199),true);
 assert.equal(risk(total+200),false,'room equal to the smallest field: no line');
 assert.equal(risk(total+5000),false);
 // a field let go: the kept ones count (budget base+800 keeps Run 3 and Run 2, smallest 200; room 100)
 assert.equal(risk(base+800),true);
 // a run of the same key gives an estimate: the named line, not this one
 assert.equal(X.unestimatedFieldRisk(input,runs,sel,cmp,VIEW,X.runFieldSizeKey(runs[0]),{budget:total+1,bytes:size}),false);
 // no field kept: nothing to say
 const bare=[run(5)];X.letGoField(bare[0]);
 assert.equal(X.unestimatedFieldRisk(input,bare,bare[0].job,[bare[0].job,bare[0].job],VIEW,other,{budget:1,bytes:size}),false);
 // the page: shown before a run only, with no Pin button (it names no run)
 const app=read('workspace-app.mjs');
 assert.ok(app.includes("if(!running)risk=unestimatedFieldRisk(inputsFile(),runs,solverRun?.job||null,compareIds,currentView(),next);"));
 assert.ok(app.includes("if(!list.length&&fieldWarning.risk&&!running){$('run-drop').hidden=false;$('run-options').classList.add('dropping');$('run-drop-text').textContent=FIELDS_MAY_GO_TEXT;$('run-drop-text').title=FIELDS_MAY_GO_TEXT;$('run-drop-pin').hidden=true;return;}"));
});
