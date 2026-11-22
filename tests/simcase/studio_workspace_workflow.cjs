// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
const {test,before}=require('node:test');const assert=require('node:assert/strict');let opticalWorkflow,inputsDifferText,opticalInputParts;
before(async()=>({opticalWorkflow,inputsDifferText,opticalInputParts}=await import('../../packages/simcase/src/simcase/studio/static/workspace-workflow.mjs')));
const input=()=>({model:{shapes:[{name:'Core',type:'rect',material:'Silicon',x:-250,y:0,w:500,h:220}]},setup:{materials:{Core:'Silicon',Oxide:'Silica'}}});
test('mesh preview is optional and an earlier result is never labeled current after an input edit',()=>{
 const doc=input(),run={signature:JSON.stringify(doc)};
 let steps=opticalWorkflow({input:doc,runs:[run]});assert.equal(steps[2].detail,'Optional preview');assert.equal(steps[3].detail,'Run complete');assert.equal(steps[4].detail,'Result for these inputs');
 doc.model.shapes=[{...doc.model.shapes[0],h:300}];assert.equal(opticalWorkflow({input:doc})[0].detail,'500 × 300 nm · Silicon');steps=opticalWorkflow({input:doc,runs:[run],mesh:run});assert.equal(steps[2].detail,'Inputs changed since preview');assert.equal(steps[4].detail,'Current inputs differ from this run');assert.equal(steps[3].detail,'Ready to run');
});
test('invalid drafts, detached jobs and offline service block readiness without hiding completed results',()=>{
 const doc=input(),runs=[{signature:JSON.stringify(doc)}];
 assert.equal(opticalWorkflow({input:doc,invalid:true})[3].detail,'Correct input draft');
 assert.equal(opticalWorkflow({input:doc,pending:true})[3].detail,'Resume or detach job');
 assert.equal(opticalWorkflow({input:doc,pending:true,resumeBlocked:true})[3].detail,'Detach unavailable job');
 assert.equal(opticalWorkflow({input:doc,pending:true,busy:true})[3].state,'busy');
 const steps=opticalWorkflow({input:doc,block:'offline',runs});assert.equal(steps[3].detail,'Unavailable');assert.equal(steps[4].detail,'Result for these inputs');
 assert.equal(opticalWorkflow({input:doc})[1].detail,'Silicon in silica');doc.model.shapes=[{...doc.model.shapes[0],material:'Air'}];assert.equal(opticalWorkflow({input:doc})[1].state,'attention');doc.model.shapes=[{...doc.model.shapes[0],material:''}];assert.equal(opticalWorkflow({input:doc})[1].state,'attention');
});
test('the Study step leads with the wavelength of the optical inputs',()=>{
 const doc=input();doc.model.wavelength=1550;
 assert.equal(opticalWorkflow({input:doc})[3].detail,'λ 1550 nm · Ready to run');
 // the step bar shows the wavelength as its own control, which opens the wavelength field
 assert.equal(opticalWorkflow({input:doc})[3].wavelength,'λ 1550 nm');assert.equal(opticalWorkflow({input:doc})[3].summary,'Ready to run');
 assert.equal(opticalWorkflow({input:doc,busy:true})[3].detail,'λ 1550 nm · Computing');
 // the state alone, for panels that show the wavelength in a row of its own
 assert.equal(opticalWorkflow({input:doc})[3].summary,'Ready to run');
 doc.model.wavelength=1310.5;assert.equal(opticalWorkflow({input:doc,block:'offline'})[3].detail,'λ 1310.5 nm · Unavailable');
});
test('after a run of the current inputs the Study step says the run is complete, until an edit',()=>{
 const doc=input();doc.model.wavelength=1550;const run={signature:JSON.stringify(doc)};
 assert.equal(opticalWorkflow({input:doc,runs:[run]})[3].detail,'λ 1550 nm · Run complete');
 assert.equal(opticalWorkflow({input:doc,runs:[]})[4].detail,'No run yet');
 // a busy or invalid editor outranks a completed run
 assert.equal(opticalWorkflow({input:doc,runs:[run],busy:true})[3].summary,'Computing');
 assert.equal(opticalWorkflow({input:doc,runs:[run],invalid:true})[3].summary,'Correct input draft');
 doc.model.wavelength=1551;assert.equal(opticalWorkflow({input:doc,runs:[run]})[3].detail,'λ 1551 nm · Ready to run');
});
test('the dock heading and the footer name the same optical run: none, current, then inputs changed',async()=>{
 const W=await import('../../packages/simcase/src/simcase/studio/static/workspace-workflow.mjs');
 const doc=input();doc.model.wavelength=1550;
 let f=W.opticalFreshness(doc,[]);assert.deepEqual(f,{state:'none',run:null});
 // before any run: today's words
 assert.equal(W.opticalSequenceHeading(f),'Nothing is computed until you press Run');
 assert.equal(W.opticalReadyStatus(f),'Optical adapter ready · explicit Run required');
 const first={signature:JSON.stringify(doc)};f=W.opticalFreshness(doc,[first]);
 assert.deepEqual(f,{state:'current',run:1});
 assert.equal(W.opticalSequenceHeading(f),'Run 1 · solved from the current inputs');
 assert.equal(W.opticalReadyStatus(f),'Run 1 · solved from the current inputs · press Run to solve again');
 // an edit: both name the latest run as the one the inputs changed since
 const edited=input();edited.model.wavelength=1551;const other={signature:JSON.stringify({x:1})};
 f=W.opticalFreshness(edited,[first,other]);assert.deepEqual(f,{state:'stale',run:2});
 assert.equal(W.opticalSequenceHeading(f),'Inputs changed since run 2 · press Run to update');
 assert.equal(W.opticalReadyStatus(f),'Inputs changed since run 2 · press Run to update');
 // back to the inputs of run 1: that run is named, as the Results step says it is current
 f=W.opticalFreshness(doc,[first,other]);assert.deepEqual(f,{state:'current',run:1});
 for(const state of [W.opticalFreshness(doc,[]),W.opticalFreshness(doc,[first]),W.opticalFreshness(edited,[first])]){
  const steps=opticalWorkflow({input:state.state==='stale'?edited:doc,runs:state.state==='none'?[]:[first]});
  // no mixed state: the Results step is current exactly when the heading names a current run
  assert.equal(steps[4].state==='ready',state.state==='current');
 }
});
test('a current optical run read from a file or recovered says so, not that it was solved here',async()=>{
 const W=await import('../../packages/simcase/src/simcase/studio/static/workspace-workflow.mjs');
 const doc=input(),sig=JSON.stringify(doc);
 let f=W.opticalFreshness(doc,[{signature:sig,origin:'imported'}]);
 assert.deepEqual(f,{state:'current',run:1,origin:'imported'});
 assert.equal(W.opticalSequenceHeading(f),'Run 1 · read from file, not recomputed');
 assert.equal(W.opticalReadyStatus(f),'Run 1 · read from file, not recomputed · press Run to compute it here');
 f=W.opticalFreshness(doc,[{signature:sig,origin:'recovered'}]);
 assert.equal(W.opticalSequenceHeading(f),'Run 1 · recovered from this browser, not recomputed');
 // a later run made in this tab with the same inputs keeps today's words
 f=W.opticalFreshness(doc,[{signature:sig,origin:'imported'},{signature:sig,origin:'local'}]);
 assert.deepEqual(f,{state:'current',run:2});
 assert.equal(W.opticalSequenceHeading(f),'Run 2 · solved from the current inputs');
 // freshness is unchanged: an edit names the latest run as before
 assert.deepEqual(W.opticalFreshness({x:1},[{signature:sig,origin:'imported'}]),{state:'stale',run:1});
});
test('the Results step describes the run being viewed, in neutral words that name both inputs',()=>{
 const older=input();older.model.wavelength=1550;older.model.coreMesh=30;older.model.shapes=[{...older.model.shapes[0],w:600,h:300}];
 const newer=structuredClone(older);newer.model.shapes=[{...newer.model.shapes[0],w:700}];
 const runs=[{signature:JSON.stringify(older),input:older},{signature:JSON.stringify(newer),input:newer}];
 // a file opened with two runs: the inputs are the newer run's, the older one is viewed
 let steps=opticalWorkflow({input:newer,runs,viewed:runs[0]});
 assert.deepEqual([steps[4].state,steps[4].detail],['attention','Current inputs differ from this run']);
 assert.equal(steps[3].summary,'Run complete');
 steps=opticalWorkflow({input:newer,runs,viewed:runs[1]});assert.deepEqual([steps[4].state,steps[4].detail],['ready','Result for these inputs']);
 // the words name only the parts that differ, this run first
 assert.equal(inputsDifferText(opticalInputParts(older),opticalInputParts(newer)),'Current inputs differ from this run: this run 600 × 300 nm · Silicon, current 700 × 300 nm · Silicon');
 const other=structuredClone(newer);other.model.wavelength=1310;other.model.coreMesh=40;
 assert.equal(inputsDifferText(opticalInputParts(newer),opticalInputParts(other)),'Current inputs differ from this run: this run λ 1550 nm · core mesh 30 nm, current λ 1310 nm · core mesh 40 nm');
 assert.equal(inputsDifferText(['a'],['a']),'Current inputs differ from this run in other settings');
 for(const text of [steps[4].detail,inputsDifferText(['a'],['b'])])assert.doesNotMatch(text,/edit/i);
});
