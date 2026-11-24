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

const CORE={name:'Core',type:'rect',material:'Silicon',x:-250,y:0,w:500,h:220};
const SUBSTRATE={name:'Substrate',type:'rect',material:'Silicon',x:-1500,y:-1200,w:3000,h:700};
test('P2 (V2): the slab warning before a run: T18 warns; the core-only template and a lower-index edge slab do not',async()=>{
 const M=await import(STATIC+'workspace-modes.mjs');
 // T18: 500 × 220 core over a 3000 × 700 silicon substrate spanning the window
 const t18=M.edgeSlabRisk([CORE,SUBSTRATE]);assert.deepEqual(t18,{edge:'Substrate',core:'Core'});
 assert.equal(M.edgeSlabWarningText(t18),"Substrate touches the window edge and its index is as high as Core's: in a closed window its slab modes come first.");
 // the real shape names, in any order
 assert.equal(M.edgeSlabWarningText(M.edgeSlabRisk([{...SUBSTRATE,name:'Wafer'},{...CORE,name:'Rib'}])),"Wafer touches the window edge and its index is as high as Rib's: in a closed window its slab modes come first.");
 // the core-only template: no warning; a silica slab touching the edge: no warning
 assert.equal(M.edgeSlabRisk([CORE]),null);
 assert.equal(M.edgeSlabRisk([CORE,{...SUBSTRATE,name:'Oxide slab',material:'Silica'}]),null);
 // lower than the core (silicon nitride under silicon) no, higher (silicon under silicon nitride) yes
 assert.equal(M.edgeSlabRisk([CORE,{...SUBSTRATE,material:'Silicon nitride'}]),null);
 assert.deepEqual(M.edgeSlabRisk([{...CORE,material:'Silicon nitride'},SUBSTRATE]),{edge:'Substrate',core:'Core'});
 // every shape on the edge (no core away from it): no warning; the highest of each group is compared
 // (the first of equal ones is named), and a higher core away from the edge clears it
 assert.equal(M.edgeSlabRisk([SUBSTRATE]),null);
 assert.deepEqual(M.edgeSlabRisk([{...CORE,material:'Silicon nitride'},{...CORE,name:'Core 2',x:300,w:100,material:'Silicon nitride'},{...SUBSTRATE,material:'Silica'},{...SUBSTRATE,name:'Top',y:1000,h:200,material:'Gallium arsenide'}]),{edge:'Top',core:'Core'});
 assert.equal(M.edgeSlabRisk([{...CORE,material:'Silicon nitride'},{...CORE,name:'Core 2',x:300,w:100},{...SUBSTRATE,name:'Top',y:1000,h:200,material:'Gallium arsenide'}]),null);
 // a shape short of the window edge does not touch it
 assert.equal(M.edgeSlabRisk([CORE,{...SUBSTRATE,x:-1499,w:2998,y:-1199}]),null);
});

test('P2 (V2): shown in the plan line and Optical modes, with both buttons, only for a closed window with Highest',()=>{
 const app=read('workspace-app.mjs');
 assert.ok(app.includes('const edgeWarning=()=>isOptical()&&applicationChosen()&&!state.openBoundary&&state.searchTarget==null?edgeSlabRisk(state.shapes):null;'));
 // the buttons: the edge note's shortcut with the same target estimate (defaultTarget) and Use Open boundary
 const buttons=body(app,'function edgeWarningButtons(prefix){','\n}');
 assert.ok(buttons.includes('const near=defaultTarget(state.shapes)'));
 assert.ok(buttons.includes('search.textContent=shortcutText(near);search.onclick=()=>useClosedSearch(near);'));
 assert.ok(buttons.includes("open.textContent='Use Open boundary';open.onclick=()=>{if(!state.openBoundary)setOuterBoundary(true);};"));
 // the plan line's row and the panel's warning
 assert.ok(app.includes(' refreshDropWarning();refreshEdgeWarning();'));
 assert.ok(app.includes("host.append(...edgeWarningButtons('run-edge'));"));
 assert.ok(app.includes("$('closed-edge-actions')?.append(...edgeWarningButtons('closed-edge'));"));
 assert.ok(app.includes('<p class="validation-warning" id="closed-edge-warning-text">${escapeHtml(edgeSlabWarningText(risk))}</p>'));
 // no solve: the check reads the shapes only; the result-side edge note is unchanged
 assert.ok(!body(app,'const edgeWarning=','\n').includes('runs'));
 assert.ok(app.includes("b.id='edge-search-near';b.textContent=shortcutText(near);b.onclick=()=>useClosedSearch(near);"));
});
