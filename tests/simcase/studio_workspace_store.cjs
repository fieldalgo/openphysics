// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0

const {before}=require('node:test');
let WorkspaceStore;
let snapshot;
before(async()=>{
({WorkspaceStore}=await import('../../packages/simcase/src/simcase/studio/static/workspace-store.mjs'));
({snapshot}=await import('../../packages/simcase/src/simcase/studio/static/workspace-project.mjs'));
});
const test=require('node:test');
const assert=require('node:assert/strict');


const input=()=>snapshot({width:500,voltage:1,electric:false,heat:false,structure:false,optics:true},{materials:{Core:'Silicon',Oxide:'Silica',Heater:''},temperature:293.15,cooling:'',fixed:'',terminal:''});
const edit=(s,width)=>{const d=s.document;d.model.width=width;return d;};
test('navigation-equivalent input does not change revision or dirty state',()=>{
 const s=new WorkspaceStore(input());s.markSaved();s.record({...s.document,selection:'Materials'});
 assert.equal(s.revision,0);assert.equal(s.dirty,false);assert.equal(s.canUndo,false);
});
test('grouped edits have monotonic revisions but undo to the saved document in one step',()=>{
 const s=new WorkspaceStore(input());s.markSaved();s.record(edit(s,600),'width');s.record(edit(s,700),'width');
 assert.equal(s.revision,2);assert.equal(s.dirty,true);s.undo();assert.equal(s.revision,3);assert.equal(s.dirty,false);
 s.redo();assert.equal(s.revision,4);assert.equal(s.document.model.width,700);
});
test('run-input restore is undoable and does not mark unsaved input as saved',()=>{
 const s=new WorkspaceStore(input());s.markSaved();s.replace(edit(s,700));assert.equal(s.dirty,true);
 s.undo();assert.equal(s.dirty,false);s.redo();assert.equal(s.dirty,true);
 s.replace(input(),{saved:true});assert.equal(s.dirty,false);s.undo();assert.equal(s.dirty,true);
});
test('session replacement clears undo; invalid replacement cannot change document or saved baseline',()=>{
 const s=new WorkspaceStore(input());s.record(edit(s,700));s.replace(edit(s,800),{saved:true,resetHistory:true});
 assert.equal(s.canUndo,false);assert.equal(s.canRedo,false);assert.equal(s.dirty,false);
 const before=s.capture();assert.throws(()=>s.replace(edit(s,-1),{saved:true,resetHistory:true}));
 assert.deepEqual(s.capture(),before);assert.equal(s.dirty,false);
});
test('captured inputs are isolated and new edits after undo discard redo',()=>{
 const s=new WorkspaceStore(input()),captured=s.capture();s.record(edit(s,700));s.undo();s.record(edit(s,600));
 assert.equal(s.canRedo,false);assert.equal(captured.input.model.width,500);captured.input.model.width=900;
 assert.equal(s.document.model.width,600);
});
