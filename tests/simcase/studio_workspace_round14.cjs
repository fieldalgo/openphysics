// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
// Round 14: the run banner's place and the Compare badge.
const test=require('node:test');const assert=require('node:assert/strict');
const fs=require('node:fs');const path=require('node:path');
const STATIC='../../packages/simcase/src/simcase/studio/static/';
const read=name=>fs.readFileSync(path.join(__dirname,STATIC,name),'utf8');
test('Q6: the run banner is inside the workspace, positioned out of the layout',()=>{
 const html=read('workspace.html'),css=read('workspace.css');
 const workspace=html.indexOf('<section class="workspace">'),panel=html.indexOf('<section id="job-panel"'),end=html.indexOf('</main>');
 assert.ok(workspace>0&&panel>workspace&&panel<end,'#job-panel is inside .workspace');
 assert.match(css,/\.workspace\{position:relative\}/);
 assert.match(css,/#job-panel\{position:absolute;top:0;right:0;[^}]*height:34px;/);
});
test('Q8: the Compare side is a badge after a hidden separator',()=>{
 const app=read('workspace-app.mjs'),css=read('workspace.css');
 assert.match(app,/sep\.className='compare-side-sep';sep\.textContent=' · ';const tag=document\.createElement\('span'\);tag\.className='compare-side';tag\.textContent=`Compare \$\{side\}`;b\.append\(sep,tag\);/);
 assert.match(css,/\.compare-side\{display:inline-block;[^}]*border:1px solid/);
 assert.match(css,/\.compare-side-sep\{position:absolute;width:1px;height:1px;overflow:hidden;clip-path:inset\(50%\)/);
});
