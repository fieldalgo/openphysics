// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
// Round 37 (agent proxy round 37 on main 6501231): D3, Compare offers the closed core search. In T18
// three of five agents pressed "Run as set" in the "Slab modes first" dialog; their closed run held
// only substrate slab modes, and Compare against the open run said "No matched modes" with the note
// "A · Run 2: its modes are mostly in Substrate, which touches the window edge; the core mode was not
// found." and no way on. Beside that note Compare now offers the run's shortcut, "Set search near
// 2.46 · 4 modes" (shortcutText of defaultTarget for the run's geometry): it makes that run's inputs
// current (useRunInputs), applies the shortcut (useClosedSearch) and opens Model, running nothing.
// No button for a run with a core mode, an open run, or when Compare matched the modes. The matching,
// Compare's other text, values, file formats and the dialog are unchanged. Plain text comparison
// only: no RegExp is built from a dynamic string.
const test=require('node:test');const assert=require('node:assert/strict');
const fs=require('node:fs');const path=require('node:path');
const STATIC='../../packages/simcase/src/simcase/studio/static/';
const read=name=>fs.readFileSync(path.join(__dirname,STATIC,name),'utf8');
let N,P,M,C,O;
test.before(async()=>{
 N=await import(STATIC+'workspace-notebook.mjs');P=await import(STATIC+'workspace-project.mjs');
 M=await import(STATIC+'workspace-modes.mjs');C=await import(STATIC+'workspace-closed-target.mjs');O=await import(STATIC+'workspace-open-boundary.mjs');
});
const setup=()=>({materials:{Core:'Silicon',Oxide:'Silica',Heater:''},temperature:293.15,cooling:'',fixed:'',terminal:''});
const CORE={name:'Core',type:'rect',material:'Silicon',x:-250,y:0,w:500,h:220};
const SUBSTRATE={name:'Substrate',type:'rect',material:'Silicon',x:-1500,y:-1200,w:3000,h:700};
const input=shapes=>P.snapshot({width:500,voltage:1,electric:false,heat:false,structure:false,optics:true,wavelength:1550,coreMesh:30,...(shapes?{shapes}:{})},setup());
// two triangles, one in the core and one in the substrate; inCore: per mode, whether its |E|² is in the core
const twoTriangles=inCore=>({node_coordinates:[[-2e-7,1e-8],[2e-7,1e-8],[0,2e-7],[-1.4e-6,-1.1e-6],[1.4e-6,-1.1e-6],[0,-6e-7]],triangles:[[0,1,2],[3,4,5]],
 real:inCore.map(c=>c?[[1,0,0],[0.1,0,0]]:[[0,0,0],[1,0,0]]),imag:inCore.map(()=>[[0,0,0],[0,0,0]])});
const closedRun=(job,re,inCore,{target=2.46,shapes=[CORE,SUBSTRATE]}={})=>N.validateRun({job,completedAt:'2026-11-27T01:00:00.000Z',
 settings:target===null?N.opticalSettings(1550,30,re.length):N.closedTargetSettings(N.opticalSettings(1550,30,re.length),target),input:input(shapes),
 effective_index:re,field:twoTriangles(inCore),origin:'local',serverVersion:'0.0.0',te_polarization_fraction:re.map(()=>0.99),effective_area:re.map(()=>1e-13)});

test('D3: the closed run as set, its modes in the substrate and no core mode, gets the shortcut of its geometry',()=>{
 const asSet=closedRun('0000000b',[2.6,2.5],[false,false],{target:null});
 // the note Compare shows for it (round 22, V3), unchanged
 assert.equal(M.firstModeEdgeShape(asSet),'Substrate');assert.deepEqual(M.coreNotes(asSet),[]);
 assert.equal(M.noMatchEdgeText('A','Run 2','Substrate'),'A · Run 2: its modes are mostly in Substrate, which touches the window edge; the core mode was not found.');
 // the target is the edge warning's and the dialog's estimate (defaultTarget) for the run's geometry
 assert.equal(O.defaultTarget([CORE,SUBSTRATE]),2.46);
 assert.equal(M.noMatchCoreSearch(asSet),2.46);
 assert.equal(C.shortcutText(M.noMatchCoreSearch(asSet)),'Set search near 2.46 · 4 modes');
 // the dialog's buttons are unchanged
 assert.deepEqual(C.slabQuestionButtons(2.46),['Set search near 2.46 · 4 modes and run','Run as set','Cancel']);
});

test('D3: no shortcut for a run with a core mode, an open run, or a run without the edge note',()=>{
 // the shortcut's closed run: its core mode at mode 3
 const near=closedRun('0000000a',[2.6,2.5,2.43931663,2.40],[false,false,true,false]);
 assert.equal(M.firstModeEdgeShape(near),'Substrate');assert.equal(M.coreNotes(near).length,1);
 assert.equal(M.noMatchCoreSearch(near),null);
 // a run whose mode 1 is in the core: no edge note on mode 1
 assert.equal(M.noMatchCoreSearch(closedRun('0000000c',[2.44,2.40],[true,false],{target:null})),null);
 // the core-only Design A/B geometry: no shape touches the window edge
 assert.equal(M.noMatchCoreSearch(closedRun('0000000d',[2.44,1.77],[true,true],{target:null,shapes:[CORE]})),null);
 // an open run
 const asSet=closedRun('0000000e',[2.6,2.5],[false,false],{target:null});
 assert.equal(M.noMatchCoreSearch({...asSet,settings:{boundary:'PML',pml:{thickness:'1000 nm',open_edges:['left','right','bottom','top'],target:'2.46'}}}),null);
 // a run without fields
 assert.equal(M.noMatchCoreSearch({...asSet,field:null}),null);
});

test('D3: Compare puts the button beside the note; it reuses Use this run\'s inputs and the shortcut and opens Model',()=>{
 const app=read('workspace-app.mjs');
 // the note and its link (round 22, V3), unchanged
 assert.ok(app.includes("if(!chosen&&!match.disabled&&!match.error)[['A',a],['B',b]].forEach(([side,run],i)=>{if(i&&a.job===b.job)return;const shape=firstModeEdgeShape(run);if(!shape)return;"));
 assert.ok(app.includes("reason.textContent=noMatchEdgeText(side,runNumberTitle(run),shape);"));
 // the button: the shortcut's target for the run's geometry; round 38 (D4) moved it onto a line above
 // the plots, its label naming the run (studio_round38.cjs)
 assert.ok(app.includes("const near=noMatchCoreSearch(run);"));
 assert.ok(app.includes("search.id='compare-core-search-'+side.toLowerCase();search.textContent=runShortcutText(runNumber(run),near);search.onclick=()=>useRunClosedSearch(run,near);"));
 // pressing it: Use this run's inputs, then the shortcut, on the Model page; nothing runs
 assert.ok(app.includes("function useRunClosedSearch(run,t){if(!useRunInputs(run))return;ui.page='Model';render();useClosedSearch(t);}"));
 const body=app.slice(app.indexOf('function useRunClosedSearch('),app.indexOf('\n',app.indexOf('function useRunClosedSearch(')));
 for(const word of ['startRun','runStudy','submit','pressRun'])assert.ok(!body.includes(word),word);
 // Use this run's inputs and the shortcut are the existing functions
 assert.ok(app.includes("function useClosedSearch(t){if(state.openBoundary||(state.searchTarget===t&&state.modeCount===SHORTCUT_MODE_COUNT))return;shortcutModes.set(state.modeCount,SHORTCUT_MODE_COUNT,t);state.searchTarget=t;state.modeCount=SHORTCUT_MODE_COUNT;render();notice(`${closedSearchNotice(t)} Modes to find set to ${SHORTCUT_MODE_COUNT}. ${SHORTCUT_RUN_TEXT}`);offerMatchingRun();}"));
 assert.ok(app.includes(" restoreEdit(doc,null);state.searchTarget=runTarget;inputsChangedSinceResult();render();notice(text);\n return true;\n}"));
});
