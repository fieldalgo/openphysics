// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
const {test,before}=require('node:test');const assert=require('node:assert/strict');let opticalWorkflow,inputsDifferText,opticalInputParts,nextRunText;
before(async()=>({opticalWorkflow,inputsDifferText,opticalInputParts,nextRunText}=await import('../../packages/simcase/src/simcase/studio/static/workspace-workflow.mjs')));
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
 // round 10: that is information, not a problem: the step carries the neutral tone
 assert.equal(steps[4].tone,'info');
 assert.equal(opticalWorkflow({input:input(),runs}).at(4).tone,'info');
 steps=opticalWorkflow({input:newer,runs,viewed:runs[1]});assert.deepEqual([steps[4].state,steps[4].detail],['ready','Result for these inputs']);
 assert.equal(steps[4].tone,undefined);
 // the words name only the parts that differ, this run first
 assert.equal(inputsDifferText(opticalInputParts(older),opticalInputParts(newer)),'Current inputs differ from this run: this run 600 × 300 nm · Silicon, current 700 × 300 nm · Silicon');
 const other=structuredClone(newer);other.model.wavelength=1310;other.model.coreMesh=40;
 assert.equal(inputsDifferText(opticalInputParts(newer),opticalInputParts(other)),'Current inputs differ from this run: this run λ 1550 nm · core mesh 30 nm, current λ 1310 nm · core mesh 40 nm');
 assert.equal(inputsDifferText(['a'],['a']),'Current inputs differ from this run in other settings');
 for(const text of [steps[4].detail,inputsDifferText(['a'],['b'])])assert.doesNotMatch(text,/edit/i);
});
test('round 9 (J4): the line under a result names each difference once, then what is unchanged',async()=>{
 const W=await import('../../packages/simcase/src/simcase/studio/static/workspace-workflow.mjs');
 const older=input();older.model.wavelength=1550;older.model.coreMesh=30;older.model.shapes=[{...older.model.shapes[0],w:600,h:300}];
 const newer=structuredClone(older);newer.model.shapes=[{...newer.model.shapes[0],w:700}];
 const line=W.runInputsLine(W.opticalInputParts(older),W.opticalInputParts(newer));
 assert.equal(line,'Current inputs differ from this run: this run 600 × 300 nm · Silicon, current 700 × 300 nm · Silicon; unchanged: λ 1550 nm · core mesh 30 nm');
 for(const part of ['600 × 300 nm','700 × 300 nm','λ 1550 nm','core mesh 30 nm'])assert.equal(line.split(part).length,2,part);
 assert.equal(W.runInputsLine(W.opticalInputParts(older),W.opticalInputParts(older)),'Result for the current inputs · 600 × 300 nm · Silicon · λ 1550 nm · core mesh 30 nm');
 assert.equal(W.runInputsLine(['a','b'],['c','d']),'Current inputs differ from this run: this run a · b, current c · d');
});
test('round 9 (J5): the dock heading and the footer describe the run being viewed, named with its number',async()=>{
 const W=await import('../../packages/simcase/src/simcase/studio/static/workspace-workflow.mjs');
 const older=input(),newer=input();newer.model.shapes=[{...newer.model.shapes[0],w:700}];
 const runs=[{signature:JSON.stringify(older),input:older,label:'Design A',origin:'recovered'},{signature:JSON.stringify(newer),input:newer,label:'Design B',origin:'recovered'}];
 // Design A (run 1) viewed, the inputs are Design B's (run 2); since round 14 (Q7) both geometries are named
 let f=W.opticalFreshness(newer,runs,runs[0]);
 assert.deepEqual(f,{state:'other',run:1,name:'Design A',origin:'recovered',has:2,hasName:'Design B',geometry:'500 × 220 nm',currentGeometry:'700 × 220 nm',changes:['Width 500 → 700 nm']});
 assert.equal(W.opticalSequenceHeading(f),'Run 1 · Design A 500 × 220 nm · current inputs 700 × 220 nm');
 assert.equal(W.opticalReadyStatus(f),'Run 1 · Design A 500 × 220 nm · current inputs 700 × 220 nm · current inputs from Run 2 · Design B');
 // the step bar says the same of the same run
 assert.equal(W.opticalWorkflow({input:newer,runs,viewed:runs[0]})[4].detail,'Current inputs differ from this run');
 // Design B viewed: it is the current inputs' run, recovered
 f=W.opticalFreshness(newer,runs,runs[1]);
 assert.equal(W.opticalSequenceHeading(f),'Run 2 · Design B · recovered from this browser, not recomputed');
 assert.equal(W.opticalReadyStatus(f),'Run 2 · Design B · recovered from this browser, not recomputed · press Run to compute it here');
 // an edit no run has: the viewed run differs and Run computes the inputs
 const edited=input();edited.model.shapes=[{...edited.model.shapes[0],w:800}];
 f=W.opticalFreshness(edited,runs,runs[1]);
 assert.equal(W.opticalReadyStatus(f),'Run 2 · Design B 700 × 220 nm · current inputs 800 × 220 nm · press Run to compute them');
 // the same geometry: the changes are named instead, at most two
 const other=structuredClone(newer);other.model.wavelength=1310;newer.model.wavelength=1550;
 f=W.opticalFreshness(other,runs,runs[1]);
 assert.equal(W.opticalSequenceHeading(f),'Run 2 · Design B 700 × 220 nm · current inputs differ: Wavelength 1550 → 1310 nm');
 other.model.coreMesh=25;newer.model.coreMesh=30;other.model.shapes[0].material='Silicon nitride';
 assert.equal(W.opticalSequenceHeading(W.opticalFreshness(other,runs,runs[1])),'Run 2 · Design B 700 × 220 nm · current inputs differ: Wavelength 1550 → 1310 nm · Core mesh size 30 → 25 nm …');
 // an unnamed run: its number and geometry; nothing listed differs: the plain words
 assert.equal(W.otherInputsText({run:1,geometry:'500 × 220 nm',currentGeometry:'700 × 220 nm'}),'Run 1 · 500 × 220 nm · current inputs 700 × 220 nm');
 assert.equal(W.otherInputsText({run:1,name:'A',geometry:'500 × 220 nm',currentGeometry:'500 × 220 nm',changes:[]}),'Run 1 · A 500 × 220 nm · current inputs differ from this run');
 // an unnamed run reads as before; without a viewed run the newest run of these inputs is described
 assert.equal(W.opticalSequenceHeading(W.opticalFreshness(older,[{signature:JSON.stringify(older)}],null)),'Run 1 · solved from the current inputs');
 assert.equal(W.runTitle(1,'Design A'),'Run 1 · Design A');assert.equal(W.runTitle(2,''),'Run 2');
});
test('round 11: the Study panel names the inputs the next run uses, whatever run is viewed',()=>{
 const doc=input();doc.model.wavelength=1550;doc.model.coreMesh=30;doc.model.shapes=[{...doc.model.shapes[0],w:700,h:300}];
 assert.equal(nextRunText(doc,2),'Next run uses 700 × 300 nm · Silicon · λ 1550 nm · core mesh 30 nm · Modes to find 2');
 assert.equal(nextRunText(doc),'Next run uses 700 × 300 nm · Silicon · λ 1550 nm · core mesh 30 nm');
 // the same parts the inputs words compare
 assert.ok(nextRunText(doc,2).startsWith('Next run uses '+opticalInputParts(doc).join(' · ')));
 // round 12: the group index option is named when it is on
 assert.equal(nextRunText(doc,2,true),'Next run uses 700 × 300 nm · Silicon · λ 1550 nm · core mesh 30 nm · Modes to find 2 · group index on');
 assert.equal(nextRunText(doc,2,false),nextRunText(doc,2));
});
test('round 14 (Q2, Q7): the geometry alone, in words',async()=>{
 const S=await import('../../packages/simcase/src/simcase/studio/static/workspace-shapes.mjs');
 const m=shapes=>({shapes});
 assert.equal(S.geometryWords(m([{type:'rect',w:650,h:300}])),'650 × 300 nm');
 assert.equal(S.geometryWords(m([{type:'rect',w:600.5,h:300}])),'600.5 × 300 nm');
 assert.equal(S.geometryWords(m([{type:'circle',r:300}])),'r 300 nm circle');
 assert.equal(S.geometryWords(m([{type:'polygon',points:[[0,0],[1,0],[1,1],[0,1],[0,2]]}])),'5-vertex polygon');
 // round 17 (U14, pre-registered; was '2 shapes'): several shapes by name and size, as the run list names them
 assert.equal(S.geometryWords(m([{name:'Core',type:'rect',w:1,h:1},{name:'Rod',type:'circle',r:1}])),'Core 1 × 1 + Rod r 1 nm');
});
