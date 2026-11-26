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
// index_change within the pre-registered bounds.
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
 test('HK5: a recomputed heated run matches its stored values and gets its maps back',async()=>{
  const T=await import(path.join(__dirname,'../../tools/studio_heated_retention.mjs'));
  const report=await T.hk5(RESULTS);
  assert.deepEqual(report.failures,[]);
  for(const [name,c] of Object.entries(report.cases))console.log(name,JSON.stringify(c.maps));
 });
}
