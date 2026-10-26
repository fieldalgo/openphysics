// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0

const {before}=require('node:test');
let EditHistory;
before(async()=>{
({EditHistory}=await import('../../packages/simcase/src/simcase/studio/static/workspace-history.mjs'));
});
const test=require('node:test');
const assert=require('node:assert/strict');

test('continuous edits form one step and navigation adds no history',()=>{
 const h=new EditHistory({width:500});h.record({width:600},'width');h.record({width:700},'width');h.endGroup();h.record({width:700});assert.equal(h.index,1);assert.deepEqual(h.undo(),{width:500});assert.deepEqual(h.redo(),{width:700});
});
test('new edit after undo clears redo and snapshots are isolated',()=>{
 const input={material:'Si'};const h=new EditHistory(input);input.material='Pt';h.record(input);h.undo();h.record({material:'SiO2'});assert.equal(h.canRedo,false);const result=h.undo();result.material='invalid';assert.deepEqual(h.redo(),{material:'SiO2'});
});
test('history is bounded while retaining undoable edits',()=>{
 const h=new EditHistory({n:0},2);for(let n=1;n<5;n++)h.record({n});assert.equal(h.items.length,3);assert.deepEqual(h.undo(),{n:3});assert.deepEqual(h.undo(),{n:2});assert.equal(h.canUndo,false);
});
