// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
// Round 14: the optical model tree's Results group (Runs · N of M and Compare), its run limit
// agreeing with the run list's note, the run banner's place, and the Compare badge.
const test=require('node:test');const assert=require('node:assert/strict');
const fs=require('node:fs');const path=require('node:path');
const STATIC='../../packages/simcase/src/simcase/studio/static/';
const read=name=>fs.readFileSync(path.join(__dirname,STATIC,name),'utf8');
let T,N;
test.before(async()=>{T=await import(STATIC+'workspace-tree.mjs');N=await import(STATIC+'workspace-notebook.mjs');});
const items=html=>[...html.matchAll(/<button type="button"([^>]*)>(.*?)<\/button>/g)].map(([,attrs,inner])=>({
 node:/data-node="([^"]*)"/.exec(attrs)?.[1]||null,group:/data-tree-group="([^"]*)"/.exec(attrs)?.[1]||null,
 role:/role="([^"]*)"/.exec(attrs)?.[1],level:+/aria-level="(\d)"/.exec(attrs)?.[1],
 selected:/aria-selected="([^"]*)"/.exec(attrs)?.[1]||null,expanded:/aria-expanded="([^"]*)"/.exec(attrs)?.[1]||null,
 tabindex:/tabindex="(-?\d)"/.exec(attrs)?.[1],name:inner.slice(inner.lastIndexOf('</span>')+'</span>'.length)}));
test('Q9: the Results group exists only with runs; Compare only with two',()=>{
 assert.equal(T.resultsGroup({runs:0,page:'Model',runsLabel:N.runsNodeLabel(0)}),'');
 const one=items(T.resultsGroup({runs:1,shownRun:1,page:'Model',runsLabel:N.runsNodeLabel(1)}));
 assert.deepEqual(one.map(i=>[i.role,i.level,i.name]),[['treeitem',1,'Results · run 1'],['treeitem',2,'Runs · 1 of 20']]);
 const two=items(T.resultsGroup({runs:2,shownRun:1,page:'Model',runsLabel:N.runsNodeLabel(2)}));
 assert.deepEqual(two.map(i=>[i.role,i.level,i.name,i.node||i.group]),[['treeitem',1,'Results · run 1','Results'],['treeitem',2,'Runs · 2 of 20','results:runs'],['treeitem',2,'Compare','results:compare']]);
 // roving tabindex: every item starts at -1, bindTree sets the one tab stop
 assert.ok(two.every(i=>i.tabindex==='-1'));
 assert.equal(two[0].expanded,'true');
 assert.equal(items(T.resultsGroup({runs:2,shownRun:2,page:'Model',expanded:false,runsLabel:'x'}))[0].expanded,'false');
});
test('Q9: the node of the page shown is the selected one',()=>{
 const sel=page=>items(T.resultsGroup({runs:3,shownRun:2,page,runsLabel:N.runsNodeLabel(3)})).filter(i=>i.selected==='true').map(i=>i.node);
 assert.deepEqual(sel('Results'),['results:runs']);assert.deepEqual(sel('Compare'),['results:compare']);
 assert.deepEqual(sel('Model'),[]);assert.deepEqual(sel('Connections'),[]);
 assert.match(T.resultsGroup({runs:3,shownRun:2,page:'Results',runsLabel:'r'}),/Results · run 2/);
});
test('Q9: "Runs · N of M" and "Up to six runs are kept" both come from RUN_LIMIT',()=>{
 // run retention: the limit is 20, written in digits
 assert.equal(N.RUN_LIMIT,20);assert.equal(N.RUNS_KEPT_TEXT,'Up to 20 runs are kept.');
 assert.equal(N.runsNodeLabel(2),`Runs · 2 of ${N.RUN_LIMIT}`);
 const app=read('workspace-app.mjs');
 assert.match(app,/limit\.textContent=RUNS_KEPT_TEXT\+' Pinned runs stay;/);
 assert.doesNotMatch(app,/Up to six runs are kept/,'no literal copy of the limit in the optical run list');
 assert.match(app,/runsLabel:runsNodeLabel\(runs\.length\)/);
});
// round 15 (R2) moved the banner into the document-tab row, after the view title: it covers no heading
test('Q6: the run banner is in the document-tab row, after the view title, and the row keeps its height',()=>{
 const html=read('workspace.html'),css=read('workspace.css');
 const tab=html.indexOf('<div class="document-tab">'),title=html.indexOf('<strong id="view-title">'),panel=html.indexOf('<section id="job-panel"'),detail=html.indexOf('<span id="view-detail">'),end=html.indexOf('</div>',detail);
 assert.ok(tab>0&&title>tab&&panel>title&&detail>panel&&end>detail,'#job-panel is between #view-title and #view-detail in .document-tab');
 assert.match(css,/\.document-tab\{display:flex;[^}]*height:34px;/);
 assert.doesNotMatch(css,/#job-panel\{[^}]*position:absolute/);
 assert.match(css,/#job-panel\{[^}]*height:26px;/);
});
test('Q8: the Compare side is a badge after a hidden separator',()=>{
 const app=read('workspace-app.mjs'),css=read('workspace.css');
 assert.match(app,/sep\.className='compare-side-sep';sep\.textContent=' · ';const tag=document\.createElement\('span'\);tag\.className='compare-side';tag\.textContent=`Compare \$\{side\}`;b\.append\(sep,tag\);/);
 assert.match(css,/\.compare-side\{display:inline-block;[^}]*border:1px solid/);
 assert.match(css,/\.compare-side-sep\{position:absolute;width:1px;height:1px;overflow:hidden;clip-path:inset\(50%\)/);
});
