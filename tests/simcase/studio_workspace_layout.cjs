// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0

const {before}=require('node:test');
let readLayout,clampWidth,keyWidth,DEFAULT_LAYOUT;
before(async()=>{
({readLayout,clampWidth,keyWidth,DEFAULT_LAYOUT}=await import('../../packages/simcase/src/simcase/studio/static/workspace-layout.mjs'));
});
const test=require('node:test');const assert=require('node:assert/strict');

test('saved layout roundtrip and width limits preserve a usable center viewport',()=>{
 assert.deepEqual(readLayout(JSON.stringify({version:1,tree:240,inspector:320})),{tree:240,inspector:320});
 assert.deepEqual(readLayout('{"version":1,"tree":99999,"inspector":-1}'),{tree:300,inspector:220});
 assert.ok(1001-clampWidth('tree',999)-clampWidth('inspector',999)>=300);
});
test('corrupt, missing, nonnumeric and unknown layouts safely restore independent defaults',()=>{
 for(const text of [null,'{','null','{}','{"version":2}','{"version":1,"tree":"240","inspector":280}'])assert.deepEqual(readLayout(text),DEFAULT_LAYOUT);
 const d=readLayout('{}');d.tree=300;assert.equal(DEFAULT_LAYOUT.tree,220);
 assert.throws(()=>clampWidth('tree',NaN));assert.throws(()=>clampWidth('other',200));
});
test('keyboard moves the separator physically, clamps, and supports limits and larger steps',()=>{
 assert.equal(keyWidth('tree',220,'ArrowRight'),230);assert.equal(keyWidth('inspector',280,'ArrowRight'),270);
 assert.equal(keyWidth('tree',220,'ArrowLeft',true),180);assert.equal(keyWidth('tree',160,'ArrowLeft'),160);
 assert.equal(keyWidth('inspector',280,'Home'),220);assert.equal(keyWidth('inspector',280,'End'),380);
 assert.equal(keyWidth('tree',220,'Tab'),null);
});
