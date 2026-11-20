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
test('the ribbon opens Installed physics, which stays in the status bar on every page',()=>{
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
