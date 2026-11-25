// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
// Round 27 (HQ decision 2026-11-25-openphysics-studio-round27-choices): D2, the slab question before
// a closed run whose window would list slab modes first. (D1 is checked in studio_field_encoding_tab.cjs.)
// Plain text comparison only: no RegExp is built from a dynamic string.
const test=require('node:test');const assert=require('node:assert/strict');
const fs=require('node:fs');const path=require('node:path');
const STATIC='../../packages/simcase/src/simcase/studio/static/';
const read=name=>fs.readFileSync(path.join(__dirname,STATIC,name),'utf8');

// the T18 strip on a substrate: Core (Silicon) away from the edges, Substrate (Silicon) touching them
const CORE={type:'rect',name:'Core',material:'Silicon',x:-250,y:0,w:500,h:220};
const SUBSTRATE={type:'rect',name:'Substrate',material:'Silicon',x:-1500,y:-1200,w:3000,h:700};

test('D2: the question, its words and buttons are the warning\'s own names and target',async()=>{
 const C=await import(STATIC+'workspace-closed-target.mjs'),M=await import(STATIC+'workspace-modes.mjs');
 const risk=M.edgeSlabRisk([CORE,SUBSTRATE]);assert.deepEqual(risk,{edge:'Substrate',core:'Core'});
 assert.equal(C.slabQuestionText(risk),'Substrate touches the window edge, so a closed-window run returns its slab modes first. Search near the core instead?');
 const t=C.defaultTarget([CORE,SUBSTRATE]);
 assert.deepEqual(C.slabQuestionButtons(t),[`Set search near ${C.shortTarget(t)} · 4 modes and run`,'Run as set','Cancel']);
 // the first button is the warning's shortcut with " and run"
 assert.equal(C.slabQuestionButtons(t)[0],C.shortcutText(t)+' and run');
 assert.equal(C.slabQuestionButtons(2.46)[0],'Set search near 2.46 · 4 modes and run');
});

test('D2: asked only under the warning\'s conditions, once, and again only after a change',async()=>{
 const C=await import(STATIC+'workspace-closed-target.mjs'),M=await import(STATIC+'workspace-modes.mjs');
 const shapes=[CORE,SUBSTRATE],risk=M.edgeSlabRisk(shapes),key=s=>C.slabQuestionKey(s);
 const q=C.slabQuestionMemory(),highest={shapes,openBoundary:null,searchTarget:null};
 // no warning (no risk: the page's edgeWarning is null for an open boundary or Nearest to n_eff): never
 assert.equal(q.due(null,key(highest)),false);
 assert.equal(M.edgeSlabRisk([CORE]),null);
 assert.equal(M.edgeSlabRisk([CORE,{...SUBSTRATE,material:'Silica'}]),null);
 // the warning: asked; once answered, not again for the same state, re-rendered or not
 assert.equal(q.due(risk,key(highest)),true);q.asked(key(highest));
 for(let i=0;i<3;i++){q.seen(key(highest));assert.equal(q.due(risk,key(highest)),false);}
 // the geometry changes: asked again
 const wider={...highest,shapes:[CORE,{...SUBSTRATE,w:2900}]};q.seen(key(wider));
 assert.equal(q.due(M.edgeSlabRisk(wider.shapes),key(wider)),true);
 // a change and back asks again (the boundary, then Modes to return)
 q.asked(key(highest));q.seen(key(highest));assert.equal(q.due(risk,key(highest)),false);
 q.seen(key({...highest,openBoundary:{edges:['bottom']}}));q.seen(key(highest));assert.equal(q.due(risk,key(highest)),true);
 q.asked(key(highest));q.seen(key({...highest,searchTarget:2.46}));q.seen(key(highest));assert.equal(q.due(risk,key(highest)),true);
 // the key holds the geometry, the boundary and Modes to return, nothing else
 assert.equal(key(highest),JSON.stringify([shapes,null,null]));
});

test('D2: the page asks before the run, and Run as set runs exactly the same code path',()=>{
 const app=read('workspace-app.mjs');
 // the dialog: a <dialog> (role dialog) named and described, focus to the first button, Escape = Cancel
 assert.ok(app.includes("slabDialog.id='slab-question';slabDialog.setAttribute('aria-labelledby','slab-question-title');slabDialog.setAttribute('aria-describedby','slab-question-text');"));
 assert.ok(app.includes("slabDialog.showModal();$('slab-question-search').focus();"));
 assert.ok(app.includes("slabDialog.oncancel=event=>{event.preventDefault();slabAnswer?.(null);};"));
 // the question comes after the guards and before anything of the run; Cancel returns, the first
 // button sets the warning's shortcut (useClosedSearch), Run as set changes nothing
 const ask=" const risk=edgeWarning(),key=slabKeyNow();\n if(slabQuestion.due(risk,key)){\n  const near=defaultTarget(state.shapes);slabQuestion.asked(key);\n  const answer=await askSlabQuestion(risk,near);\n  if(!answer)return;\n  if(answer==='search')useClosedSearch(near);\n  if(solverBusy||pendingJob||opticalBlock()||retentionBlock())return;\n }\n try{rejectInvalidInput();}catch(e){notice(e.message);return;}\n // round 21 (W2): no question before the run;";
 assert.equal(app.split(ask).length-1,1);
 const at=app.indexOf(ask),run=app.indexOf('const operation=++jobOperation;',at);
 assert.ok(at>0&&run>at&&app.lastIndexOf("$('run-optical').onclick=async()=>{",at)>0);
 // every render forgets the answer once the state changed
 assert.ok(app.includes("function refreshEdgeWarning(){\n slabQuestion.seen(slabKeyNow());"));
 // the warning and its buttons stay
 assert.ok(app.includes("host.append(...edgeWarningButtons('run-edge'));"));
});

