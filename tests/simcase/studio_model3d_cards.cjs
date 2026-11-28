// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
// The Library's 3D group with two cards (E2-UI): card 1 "Via in a layer stack" (boxes and layers)
// and card 2 "Copper via through a slab" (a cylinder in a meshloom builder shape), each with its
// asset, session file name and project card id; a document is matched to its card by its name.
const test=require('node:test');const assert=require('node:assert/strict');
const fs=require('node:fs');const path=require('node:path');
const STATIC='../../packages/simcase/src/simcase/studio/static/';
const STATIC_DIR=path.join(__dirname,'..','..','packages','simcase','src','simcase','studio','static');
let M,PF,S;
test.before(async()=>{M=await import(STATIC+'workspace-model3d.mjs');S=await import(STATIC+'workspace-model3d-session.mjs');PF=await import(STATIC+'workspace-project-file.mjs');});
const asset=name=>JSON.parse(fs.readFileSync(path.join(STATIC_DIR,name),'utf8'));

test('the 3D group holds two cards, in order, each with its asset and session file name',()=>{
 assert.deepEqual(M.CARDS3D.map(c=>[c.id,c.title,c.asset,c.sessionFile]),[
  ['layer-stack-3d','Via in a layer stack (3D heat)','/model3d-assets/model3d-layer-stack-3d.json','via-in-a-layer-stack-3d.json'],
  ['via-slab-3d','Copper via through a slab (3D heat)','/model3d-assets/model3d-via-slab-3d.json','copper-via-through-a-slab-3d.json']]);
 assert.equal(M.CARDS3D[0],M.CARD3D,'card 1 is the card of before');
 assert.deepEqual(M.CARDS3D.map(c=>c.status),['3D steady heat (experimental)','3D steady heat (experimental)']);
 assert.equal(M.CARDS3D[1].note,'Round via: one cylinder through the slab, in a meshloom builder shape');
 assert.equal(M.CARD3D.note,'Square via: a box through the oxide, in a layer stack');
});

test("each card's document is its asset, named by the card's title",()=>{
 assert.equal(asset('model3d-layer-stack-3d.json').name,M.CARDS3D[0].title);
 assert.equal(asset('model3d-via-slab-3d.json').name,M.CARDS3D[1].title);
 assert.equal(M.card3dOf(asset('model3d-via-slab-3d.json')).id,'via-slab-3d');
 assert.equal(M.card3dOf(asset('model3d-layer-stack-3d.json')).id,'layer-stack-3d');
 assert.equal(M.card3dOf({...asset('model3d-via-slab-3d.json'),name:'My via'}),null,'a renamed document is no card');
 assert.equal(M.card3dOf({openphysics:'0.3'}),null);
});

test('the project file knows card 2',()=>{
 assert.ok(PF.CARDS.includes('via-slab-3d'));
 // a project with card 2's model reads back with its card
 const entry=PF.projectEntry({id:'m3',kind:'model3d',title:M.CARDS3D[1].title,card:'via-slab-3d',text:S.writeModel3dSession(asset('model3d-via-slab-3d.json'))});
 const out=PF.writeProject({name:'p',savedAt:'2026-11-28T06:00:00.000Z',studio:'0.0.2',active:'m3',entries:[entry]});assert.equal(out.ok,true);
 const read=PF.readProject(out.text);
 assert.deepEqual(read.models.map(m=>[m.kind,m.card,m.title]),[['model3d','via-slab-3d','Copper via through a slab (3D heat)']]);
});
