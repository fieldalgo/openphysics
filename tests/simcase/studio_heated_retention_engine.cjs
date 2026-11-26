// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
// HK1 and HK5 of the heated model's run retention (design "Keeping more runs", section 7) on engine
// results: defined only when STUDIO_HEATED_RETENTION_RESULTS names a folder written by
//   node tools/studio_heated_retention.mjs engine <dir> one-a
//   node tools/studio_heated_retention.mjs engine <dir> one-b --only tpl-p2,tpl4-p2,v012,slab
// HK1: 20 results of each kind and of the template mix keep the session within the budget after every
// result, the maps kept are the order of 3.2 (checked against the session text written in full) and the
// cached sum is the written length; the maps kept at 20 results are recorded with their prediction
// (template 20, template with 4 modes 20, 0.12 µm 10, slab 6, 0.08 µm 5). HK5: a second solve of the
// same document, as Recompute Run N's maps sends it, matches every checked value within 1e-12 relative
// (1e-15 absolute below 1e-3), with the same mesh, and its maps are attached. HQ1 to HQ4 (design
// "Session versions 16 and 17", section 3.4): each case's maps made compact (session version 17) and
// read back are bitwise base + fround(x − base), with node and coupled temperatures, n, k and
// index_change within the pre-registered bounds. HQ5: the Results page of each case with compact maps
// against the server's maps (the range, the colour-bar labels and accessible names identical, colours
// within 1 level, changed on at most 0.1 % of triangles, 5 % of the core T map). HQ6: 20 results through
// the tab's rule with compact maps keep 20, 20, 15 and 17 maps (template, 0.12 µm, 0.08 µm, slab).
const test=require('node:test');const assert=require('node:assert/strict');const path=require('node:path');
const RESULTS=process.env.STUDIO_HEATED_RETENTION_RESULTS;
if(RESULTS){
 test('HK1: 20 heated results of each kind within the budget, in the order of 3.2',async()=>{
  const T=await import(path.join(__dirname,'../../tools/studio_heated_retention.mjs'));
  const report=await T.hk1(RESULTS);
  assert.deepEqual(report.failures,[]);
  for(const [kind,s] of Object.entries(report.sequences))console.log(kind,'maps kept at 20:',s.mapsKeptAt20,'prediction:',s.prediction,'largest session:',s.maxBytes,'20 values-only records:',s.valuesOnlyRecords20);
 });
 test('HQ1–HQ4: compact maps of each engine result: bitwise base + fround(x − base), within the pre-registered bounds',async()=>{
  const T=await import(path.join(__dirname,'../../tools/studio_heated_retention.mjs'));
  const report=await T.hqAccuracy(RESULTS);
  assert.deepEqual(report.failures,[]);
  assert.deepEqual(Object.keys(report.cases),['tpl-p2','tpl4-p2','v012','v008','slab']);
  for(const [name,c] of Object.entries(report.cases)){assert.ok(c.heat1.rangeMinExact&&c.heat1.rangeMaxRule,name);console.log(name,JSON.stringify(c));}
 });
 test('HQ5: the Results page with compact maps: the same range, labels and names; colours within 1 level, on at most 0.1 % (core T 5 %) of triangles',async()=>{
  const T=await import(path.join(__dirname,'../../tools/studio_heated_retention.mjs'));
  const report=await T.hq5(RESULTS);
  assert.deepEqual(report.failures,[]);
 });
 test('HQ6: 20 results through the tab with compact maps keep 20, 20, 15 and 17 maps (template, 0.12 µm, 0.08 µm, slab)',async()=>{
  const T=await import(path.join(__dirname,'../../tools/studio_heated_retention.mjs'));
  const report=await T.hq6(RESULTS);
  assert.deepEqual(report.failures,[]);
  assert.deepEqual(Object.fromEntries(Object.entries(report.sequences).map(([k,s])=>[k,s.mapsKeptAt20])),{template:20,v012:20,v008:15,slab:17});
 });
 test('HK5: a recomputed heated run matches its stored values and gets its maps back',async()=>{
  const T=await import(path.join(__dirname,'../../tools/studio_heated_retention.mjs'));
  const report=await T.hk5(RESULTS);
  assert.deepEqual(report.failures,[]);
  for(const [name,c] of Object.entries(report.cases))console.log(name,JSON.stringify(c.maps));
 });
}
