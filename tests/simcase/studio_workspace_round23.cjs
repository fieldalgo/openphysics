// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
// Round 23: usability fixes of the optical model (E1 to E6, pre-registered P1 to P6).
// Plain text comparison only: no RegExp is built from a dynamic string.
const test=require('node:test');const assert=require('node:assert/strict');
const fs=require('node:fs');const path=require('node:path');
const STATIC='../../packages/simcase/src/simcase/studio/static/';
const read=name=>fs.readFileSync(path.join(__dirname,STATIC,name),'utf8');
const body=(text,from,to)=>{const a=text.indexOf(from),b=text.indexOf(to,a+from.length);assert.ok(a>=0&&b>a,from);return text.slice(a,b);};

const CORE={name:'Core',type:'rect',material:'Silicon',x:-250,y:0,w:500,h:220};
const SUBSTRATE={name:'Substrate',type:'rect',material:'Silicon',x:-1500,y:-1200,w:3000,h:700};
test('P1 (E1): the plan line row says the short form; Optical modes keeps the full sentence',async()=>{
 const M=await import(STATIC+'workspace-modes.mjs');
 const t18=M.edgeSlabRisk([CORE,SUBSTRATE]);
 assert.equal(M.edgeSlabShortText(t18),'Substrate touches the window edge: in a closed window its slab modes come first.');
 assert.equal(M.edgeSlabShortText({edge:'Wafer',core:'Rib'}),'Wafer touches the window edge: in a closed window its slab modes come first.');
 assert.equal(M.edgeSlabWarningText(t18),"Substrate touches the window edge and its index is as high as Core's: in a closed window its slab modes come first.");
 const app=read('workspace-app.mjs'),row=body(app,'function refreshEdgeWarning(){','\n}');
 // the row: the short words, the full sentence as its title, both buttons
 assert.ok(row.includes("const text=edgeSlabShortText(risk),key=text+'\\n'+defaultTarget(state.shapes);"));
 assert.ok(row.includes("$('run-edge-text').textContent=text;$('run-edge-text').title=edgeSlabWarningText(risk);"));
 assert.ok(row.includes("host.append(...edgeWarningButtons('run-edge'));"));
 // the panel: the full sentence
 assert.ok(app.includes('<p class="validation-warning" id="closed-edge-warning-text">${escapeHtml(edgeSlabWarningText(risk))}</p>'));
});

test('P1 (E1): the row wraps and is never cut: no line clamp, no ellipsis, the box grows',()=>{
 const css=read('workspace.css'),rule=sel=>{const a=css.indexOf(sel+'{');assert.ok(a>=0,sel);return css.slice(a,css.indexOf('}',a));};
 assert.equal(rule('.run-edge'),'.run-edge{display:flex;flex-wrap:wrap;align-items:center;gap:2px 4px;min-width:0;color:#8a4b00');
 const text=rule('.run-edge-text');
 for(const cut of ['line-clamp','overflow:hidden','text-overflow','nowrap'])assert.ok(!text.includes(cut),cut);
 assert.equal(rule('.run-options.edge-warning'),'.run-options.edge-warning{height:auto;min-height:50px;overflow:visible');
 // on a phone the box fits the screen beside Run study (it was 460 px wide in a 390 px window)
 assert.ok(css.includes('@media(max-width:600px){.run-options{width:280px}}'));
 // nothing else clamps or cuts the row's words
 assert.ok(!css.includes('.run-edge-text{-webkit-line-clamp')&&!css.includes('.dropping .run-edge-text'));
});
