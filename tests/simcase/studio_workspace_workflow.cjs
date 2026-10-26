// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
const {test,before}=require('node:test');const assert=require('node:assert/strict');let opticalWorkflow;
before(async()=>({opticalWorkflow}=await import('../../packages/simcase/src/simcase/studio/static/workspace-workflow.mjs')));
const input=()=>({model:{width:500,height:220},setup:{materials:{Core:'Silicon',Oxide:'Silica'}}});
test('mesh preview is optional and an earlier result is never labeled current after an input edit',()=>{
 const doc=input(),run={signature:JSON.stringify(doc)};
 let steps=opticalWorkflow({input:doc,runs:[run]});assert.equal(steps[2].detail,'Optional preview');assert.equal(steps[3].detail,'Ready to run');assert.equal(steps[4].detail,'Current input result');
 doc.model.height=300;steps=opticalWorkflow({input:doc,runs:[run],mesh:run});assert.equal(steps[2].detail,'Preview earlier inputs');assert.equal(steps[4].detail,'Earlier inputs only');assert.equal(steps[3].detail,'Ready to run');
});
test('invalid drafts, detached jobs and offline service block readiness without hiding completed results',()=>{
 const doc=input(),runs=[{signature:JSON.stringify(doc)}];
 assert.equal(opticalWorkflow({input:doc,invalid:true})[3].detail,'Correct input draft');
 assert.equal(opticalWorkflow({input:doc,pending:true})[3].detail,'Resume or detach job');
 assert.equal(opticalWorkflow({input:doc,pending:true,busy:true})[3].state,'busy');
 const steps=opticalWorkflow({input:doc,block:'offline',runs});assert.equal(steps[3].detail,'Unavailable');assert.equal(steps[4].detail,'Current input result');
 doc.setup.materials.Core='Platinum';assert.equal(opticalWorkflow({input:doc})[1].state,'attention');
});
