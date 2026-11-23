// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
// Round 12: the page tabs as an ARIA tablist with Library first, the group index words (the box's
// note, the tick message, the n_g header hint) and the baseline option's time.
const test=require('node:test');const assert=require('node:assert/strict');
const fs=require('node:fs');const path=require('node:path');
const STATIC='../../packages/simcase/src/simcase/studio/static/';
const html=fs.readFileSync(path.join(__dirname,STATIC,'workspace.html'),'utf8');
let T,M;
test.before(async()=>{T=await import(STATIC+'workspace-tabs.mjs');M=await import(STATIC+'workspace-modes.mjs');});

test('the page tabs are a tablist: Library, Model, Connections, Results, Compare, one tab stop',()=>{
 const list=/<div role="tablist" aria-label="Pages" class="page-tabs">(.*?)<\/div>/.exec(html);
 assert.ok(list,'a tablist inside the page navigation');
 const tabs=[...list[1].matchAll(/<button role="tab" data-page="(\w+)" aria-selected="(true|false)" tabindex="(-?\d)">([^<]+)<\/button>/g)].map(m=>[m[1],m[2],m[3],m[4]]);
 assert.deepEqual(tabs,[['Applications','true','0','Library'],['Model','false','-1','Model'],['Connections','false','-1','Connections'],['Results','false','-1','Results'],['Compare','false','-1','Compare']]);
 assert.doesNotMatch(html,/>Models</);
});
test('Left, Right, Home and End move between the tabs and wrap at the ends',()=>{
 assert.equal(T.tabKeyTarget('ArrowRight',0,5),1);assert.equal(T.tabKeyTarget('ArrowRight',4,5),0);
 assert.equal(T.tabKeyTarget('ArrowLeft',0,5),4);assert.equal(T.tabKeyTarget('ArrowLeft',3,5),2);
 assert.equal(T.tabKeyTarget('Home',3,5),0);assert.equal(T.tabKeyTarget('End',1,5),4);
 for(const key of ['ArrowUp','ArrowDown','Enter',' ','Tab'])assert.equal(T.tabKeyTarget(key,2,5),null,key);
});
test('markPageTabs selects the shown page’s tab and makes it the one tab stop',()=>{
 const tab=page=>({dataset:{page},attrs:{},tabIndex:0,setAttribute(k,v){this.attrs[k]=v;}});
 const tabs=['Applications','Model','Compare'].map(tab),nav={querySelectorAll:()=>tabs};
 T.markPageTabs(nav,'Model');
 assert.deepEqual(tabs.map(t=>[t.attrs['aria-selected'],t.tabIndex]),[['false',-1],['true',0],['false',-1]]);
});
test('the group index words: plain note, a message each way, a visible hint when n_g is off',()=>{
 assert.equal(M.GROUP_INDEX_NOTE,'Also solves at λ ± 1 nm and takes n_g from the change (about 3× slower). Off: one solve, no n_g.');
 assert.equal(M.groupIndexNotice(true),'Group index on: the next run also solves at λ ± 1 nm and gives n_g (about 3× slower).');
 assert.equal(M.groupIndexNotice(false),'Group index off: the next run is one solve, without n_g.');
 assert.equal(M.GROUP_INDEX_HINT,'Off · turn on in Study or Optical modes');
 assert.equal(M.hasGroupIndex({group_index:[1.9,null]}),true);assert.equal(M.hasGroupIndex({}),false);assert.equal(M.hasGroupIndex(null),false);
 // the cell help is unchanged
 assert.equal(M.GROUP_INDEX_OFF_HELP,'Turn on Also compute group index in Study');
});
test('Also solve without heater says its extra time in words',()=>{
 assert.match(html,/<span id="run-baseline-time">\(about 1 s more\)<\/span>/);assert.doesNotMatch(html,/~1 s/);
});
