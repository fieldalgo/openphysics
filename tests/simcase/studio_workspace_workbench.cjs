// Copyright 2026 Yongha Kim (FieldAlgo); SPDX-License-Identifier: Apache-2.0
// The workbench places every application's commands and panels: Run Joule in the ribbon's
// Compute group, Installed physics in the status bar (also opened from the ribbon) and the
// Joule solver log in the study dock.
const test=require('node:test');const assert=require('node:assert/strict');
const fs=require('node:fs');const path=require('node:path');
const html=fs.readFileSync(path.join(__dirname,'../../packages/simcase/src/simcase/studio/static/workspace.html'),'utf8');
const group=label=>{const end=html.indexOf(`<span class="ribbon-label">${label}</span>`);assert.ok(end>0,label);return html.slice(html.lastIndexOf('<div class="ribbon-group',end),end);};
test('every run command sits in the ribbon Compute group',()=>{
 const compute=group('Compute');
 for(const id of ['run-optical','run-heat','run-joule'])assert.match(compute,new RegExp(`<button id="${id}"`));
 assert.equal(html.match(/id="run-joule"/g).length,1);
});
test('the ribbon names Installed physics, whose panel is in the status bar outside the main panes',()=>{
 assert.match(group('Physics'),/<button id="open-installed-physics" aria-controls="installed-physics" aria-expanded="false"/);
 const footer=html.slice(html.indexOf('<footer'),html.indexOf('</footer>'));
 assert.match(footer,/<details id="installed-physics"><summary>Installed physics<\/summary>/);
 assert.match(footer,/<div id="provider-list">/);
 assert.ok(!html.slice(html.indexOf('<main'),html.indexOf('</main>')).includes('installed-physics'));
});
test('the study dock holds the sequence, the solver log and messages in that order',()=>{
 const dock=html.slice(html.indexOf('<section class="bottom"'),html.indexOf('</section>',html.indexOf('<section class="bottom"')));
 const at=id=>dock.indexOf(id);
 assert.ok(at('id="sequence"')>0&&at('id="solver-log"')>at('id="sequence"')&&at('id="file-status"')>at('id="solver-log"'));
 assert.match(dock,/<details id="solver-log" class="dock-log" hidden>/);
});
// Minimal <details> stand-ins: setting `open` queues a toggle event, as browsers do.
class Panel{constructor(){this.listeners={};this._open=false;this.summaryNode={focused:0,focus(options){this.focused++;this.options=options;}};}
 get open(){return this._open;}set open(v){if(v===this._open)return;this._open=v;(this.listeners.toggle||[]).forEach(f=>f());}
 addEventListener(type,fn){(this.listeners[type]??=[]).push(fn);}querySelector(){return this.summaryNode;}
 key(key){(this.listeners.keydown||[]).forEach(f=>f({key}));}}
const opener=()=>({attrs:{},setAttribute(k,v){this.attrs[k]=v;},onclick:null});
test('the ribbon opener toggles Installed physics, mirrors aria-expanded and keeps one status panel open',async()=>{
 const {installStatusPanels}=await import('../../packages/simcase/src/simcase/studio/static/workspace-layout.mjs');
 const physics=new Panel(),tools=new Panel(),button=opener();installStatusPanels([physics,tools],button);
 button.onclick();assert.equal(physics.open,true);assert.equal(button.attrs['aria-expanded'],'true');
 assert.equal(physics.summaryNode.focused,1);assert.deepEqual(physics.summaryNode.options,{preventScroll:true});
 tools.open=true;assert.equal(physics.open,false);assert.equal(button.attrs['aria-expanded'],'false');
 button.onclick();assert.equal(tools.open,false);assert.equal(physics.open,true);
 button.onclick();assert.equal(physics.open,false);assert.equal(button.attrs['aria-expanded'],'false');
});
test('Escape closes either status panel and returns focus to its summary; other keys do nothing',async()=>{
 const {installStatusPanels}=await import('../../packages/simcase/src/simcase/studio/static/workspace-layout.mjs');
 const physics=new Panel(),tools=new Panel();installStatusPanels([physics,tools],null);
 for(const panel of [physics,tools]){panel.open=true;panel.key('Enter');assert.equal(panel.open,true);
  panel.key('Escape');assert.equal(panel.open,false);assert.equal(panel.summaryNode.focused,1);
  panel.key('Escape');assert.equal(panel.summaryNode.focused,1);}
});
