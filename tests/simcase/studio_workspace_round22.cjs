// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
// Round 22: usability fixes of the optical and heated models (V1 to V6, pre-registered P1 to P6).
// Plain text comparison only: no RegExp is built from a dynamic string.
const test=require('node:test');const assert=require('node:assert/strict');
const fs=require('node:fs');const path=require('node:path');
const STATIC='../../packages/simcase/src/simcase/studio/static/';
const FIXTURES=path.join(__dirname,'studio_session_fixtures');
const read=name=>fs.readFileSync(path.join(__dirname,STATIC,name),'utf8');
const body=(text,from,to)=>{const a=text.indexOf(from),b=text.indexOf(to,a+from.length);assert.ok(a>=0&&b>a,from);return text.slice(a,b);};

test('P1 (V1): Modes to return: two radios and the field, each with its own name; the field always enabled',async()=>{
 const C=await import(STATIC+'workspace-closed-target.mjs');
 assert.equal(C.CLOSED_SEARCH_LEGEND,'Modes to return');
 assert.equal(C.HIGHEST_LABEL,'Highest n_eff above 1.45');assert.equal(C.NEAREST_LABEL,'Nearest to n_eff');assert.equal(C.NEAR_FIELD_LABEL,'n_eff to search near');
 assert.equal(new Set([C.HIGHEST_LABEL,C.NEAREST_LABEL,C.NEAR_FIELD_LABEL]).size,3);
 const field=body(read('workspace-app.mjs'),'const closedSearchField=()=>{','const bindClosedSearchField=');
 // each radio is named by its own label; the field, outside both labels, by its aria-label; never disabled
 assert.ok(field.includes('<label class="radio-field"><input type="radio" name="closed-search" id="closed-search-highest" value="highest"${near?\'\':\' checked\'}> ${HIGHEST_LABEL}</label>'));
 assert.ok(field.includes('<label class="radio-field"><input type="radio" name="closed-search" id="closed-search-nearest" value="nearest"${near?\' checked\':\'\'}> ${NEAREST_LABEL}</label><input id="closed-target-number"'));
 assert.ok(field.includes('aria-label="${NEAR_FIELD_LABEL}"'));
 assert.ok(!field.includes('disabled'));assert.ok(!field.includes('checkbox'));
 assert.ok(!read('workspace-app.mjs').includes('closed-search-check'));
});

test('P1 (V1): typing in the field selects Nearest to n_eff; Highest is the target off, Nearest the target on',()=>{
 const bind=body(read('workspace-app.mjs'),'const bindClosedSearchField=()=>{','// The group index box');
 assert.ok(bind.includes('field.oninput=()=>{nearest.checked=true;};'));
 assert.ok(bind.includes('field.onchange=take;'));
 assert.ok(bind.includes('highest.onchange=()=>{if(highest.checked&&state.searchTarget!=null)setClosedSearch(null);};'));
 assert.ok(bind.includes('nearest.onchange=()=>{if(nearest.checked)take();};'));
 assert.ok(bind.includes('ui.closedNear=t;if(state.searchTarget===t)return;setClosedSearch(t);'));
 // the one input the document, the signature and the session read is unchanged
 const app=read('workspace-app.mjs');
 assert.ok(app.includes('function setClosedSearch(t){state.searchTarget=t;render();notice(closedSearchNotice(t));offerMatchingRun();}'));
 assert.ok(app.includes('const opticalDocument=()=>buildOpticalDocument({...state,searchTarget:closedTargetNow()},setup);'));
});

test('P1 (V1): Highest writes the K1 documents byte for byte; Nearest 2.46 the targeted ones',async()=>{
 const O=await import(STATIC+'workspace-optical.mjs'),F=await import('./studio_session_fixtures/closed_documents.mjs');
 const golden=JSON.parse(fs.readFileSync(path.join(FIXTURES,'optical-documents-closed-13f07f4.json'),'utf8'));
 const highest=null,nearest=2.46;
 for(const [label,state] of F.closedStates()){
  assert.equal(JSON.stringify(O.opticalDocument({...state,searchTarget:highest},F.SETUP)),golden[label],label);
  const plain=JSON.parse(golden[label]);plain.physics.em1.target_effective_index=2.46;
  assert.equal(JSON.stringify(O.opticalDocument({...state,searchTarget:nearest},F.SETUP)),JSON.stringify(plain),label);
 }
});

test('P5 (V5): Set search near 2.46 · 4 modes; its message ends "Press Run study to compute."; it runs nothing',async()=>{
 const C=await import(STATIC+'workspace-closed-target.mjs'),W=await import(STATIC+'workspace-workflow.mjs');
 assert.equal(C.shortcutText(2.46),'Set search near 2.46 · 4 modes');assert.equal(C.SHORTCUT_RUN_TEXT,'Press Run study to compute.');
 const use=body(read('workspace-app.mjs'),'function useClosedSearch(t){','\n');
 assert.ok(use.includes('notice(`${closedSearchNotice(t)} Modes to find set to ${SHORTCUT_MODE_COUNT}. ${SHORTCUT_RUN_TEXT}`);offerMatchingRun();}'));
 // nothing is submitted: no job, no run
 for(const call of ['runOptical','submit','jobMonitor','api('])assert.ok(!use.includes(call),call);
 assert.equal(`${C.closedSearchNotice(2.46)} Modes to find set to 4. ${C.SHORTCUT_RUN_TEXT}`,'Modes to return: nearest to n_eff 2.460 in the closed window. The next run returns the modes nearest it. Modes to find set to 4. Press Run study to compute.');
 // when a kept run has these inputs, "No need to run" replaces the request (round 20, Z1)
 assert.equal(W.matchingRunMessage('Modes to find set to 4. Press Run study to compute.'),'Modes to find set to 4.');
});
