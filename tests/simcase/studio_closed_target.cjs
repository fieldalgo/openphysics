// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
// Search near n_eff for closed-window runs (optical-shapes-v10), the document builder (slice C1):
// K1, every closed document of main 13f07f4's builder is written byte for byte without a target
// (studio_session_fixtures/optical-documents-closed-13f07f4.json, made by closed_documents.mjs
// from that commit's static folder); with a target, em1 gains target_effective_index after its
// other keys and nothing else changes; the target's checks; an open boundary keeps its own target.
const test=require('node:test');const assert=require('node:assert/strict');
const fs=require('node:fs');const path=require('node:path');
const STATIC='../../packages/simcase/src/simcase/studio/static/';
const FIXTURES=path.join(__dirname,'studio_session_fixtures');
let O,C,F;
test.before(async()=>{
 O=await import(STATIC+'workspace-optical.mjs');C=await import(STATIC+'workspace-closed-target.mjs');
 F=await import('./studio_session_fixtures/closed_documents.mjs');
});
const golden=()=>JSON.parse(fs.readFileSync(path.join(FIXTURES,'optical-documents-closed-13f07f4.json'),'utf8'));

test('K1: without a target every closed document is the one main 13f07f4 wrote, byte for byte',()=>{
 const g=golden(),states=F.closedStates();
 assert.equal(states.length,24);assert.deepEqual(Object.keys(g),states.map(([label])=>label));
 for(const [label,state] of states){
  assert.equal(JSON.stringify(O.opticalDocument(state,F.SETUP)),g[label],label);
  // an absent and a null target are the same: no target
  assert.equal(JSON.stringify(O.opticalDocument({...state,searchTarget:null},F.SETUP)),g[label],label+' (null target)');
 }
 // the template documents are the optical-shapes-v7 and -v8 fixtures
 for(const [label,name] of [['template · 2 modes','optical-document-template-v7.json'],['template · 1 modes','optical-document-template-v8-1.json'],['template · 8 modes','optical-document-template-v8-8.json']])
  assert.equal(g[label],fs.readFileSync(path.join(FIXTURES,name),'utf8').trim(),name);
});

test('optical-shapes-v10: a closed target is target_effective_index after the other em1 keys, nothing else changes',()=>{
 assert.equal(C.CLOSED_TARGET_ADAPTER,'optical-shapes-v10');assert.equal(C.CLOSED_TARGET_QUERY,'workspace_capabilities=10');
 const g=golden();
 for(const [label,state] of F.closedStates()){
  const doc=O.opticalDocument({...state,searchTarget:2.46},F.SETUP),plain=JSON.parse(g[label]);
  assert.deepEqual(Object.keys(doc.physics.em1),[...Object.keys(plain.physics.em1),'target_effective_index'],label);
  assert.equal(doc.physics.em1.target_effective_index,2.46);
  delete doc.physics.em1.target_effective_index;assert.equal(JSON.stringify(doc),g[label],label);
 }
 // the text the page sends: the target as written, after boundary
 const doc=O.opticalDocument({...F.closedStates()[2][1],searchTarget:2.85},F.SETUP);
 assert.ok(JSON.stringify(doc).includes('"boundary":{"left":"pec","right":"pec","top":"pec","bottom":"pec"},"target_effective_index":2.85}'));
});

test('the closed target is checked: a number to 3 decimals above 1.45 and below the design\'s n_max',()=>{
 const state={...F.closedStates()[0][1]},bad=/Search near n_eff must lie between 1\.45 and 3\.4777 \(3 decimals\)\.$/;
 for(const t of [1.45,1.2,3.4777,4,'2.46',true,Number.NaN,2.4605])assert.throws(()=>O.opticalDocument({...state,searchTarget:t},F.SETUP),bad,String(t));
 for(const t of [1.451,2.46,3.477])assert.equal(O.opticalDocument({...state,searchTarget:t},F.SETUP).physics.em1.target_effective_index,t);
 // silicon nitride: n_max 1.9963
 assert.throws(()=>O.opticalDocument({...state,searchTarget:2},{materials:{Core:'Silicon nitride',Oxide:'Silica',Heater:''}}),/between 1\.45 and 1\.9963/);
 assert.equal(C.defaultTarget([F.STRIP,F.SUBSTRATE]),2.46);
});

test('an open boundary keeps its own target: searchTarget is not read with an open edge',()=>{
 const state={...F.closedStates()[2][1],openBoundary:{edges:{left:'open',right:'open',bottom:'open',top:'open'}}};
 assert.equal(JSON.stringify(O.opticalDocument({...state,searchTarget:2.85},F.SETUP)),JSON.stringify(O.opticalDocument(state,F.SETUP)));
});
