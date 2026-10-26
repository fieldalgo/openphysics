// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0

const {before}=require('node:test');
let snapshot,parseProject;
before(async()=>{
({snapshot,parseProject}=await import('../../packages/simcase/src/simcase/studio/static/workspace-project.mjs'));
});
const test=require('node:test');
const assert=require('node:assert/strict');

const model={width:700,voltage:2.5,electric:true,heat:true,structure:true,optics:true};
const setup={materials:{Core:'Silicon',Oxide:'Silica',Heater:'Platinum'},temperature:310,cooling:'Oxide bottom: fixed temperature',fixed:'Left end fixed',terminal:'Heater start / heater end'};
test('input round trip preserves configured model without importing results or arbitrary markup',()=>{
  const doc=snapshot(model,setup);doc.results={fake:true};doc.setup.body='<script>bad</script>';
  const loaded=parseProject(JSON.stringify(doc));
  assert.deepEqual(loaded.model,model);assert.deepEqual(loaded.setup,setup);assert.equal(loaded.results,undefined);
  loaded.setup.materials.Core='Silica';assert.equal(setup.materials.Core,'Silicon');
});
test('unsupported schema, units and invalid material labels are rejected',()=>{
  for(const edit of [d=>d.version=2,d=>d.units.width='m',d=>d.setup.materials.Heater='<img src=x>',d=>delete d.setup.terminal]){
    const doc=snapshot(model,setup);edit(doc);assert.throws(()=>parseProject(JSON.stringify(doc)));
  }
});
test('invalid numeric and dependency inputs cannot replace valid values',()=>{
  for(const edit of [d=>d.model.width=-1,d=>d.model.voltage='2',d=>d.setup.temperature=null,d=>d.model.electric=false]){
    const doc=snapshot(model,setup);edit(doc);assert.throws(()=>parseProject(JSON.stringify(doc)));
  }assert.equal(model.width,700);
});
test('malformed and oversized files are rejected',()=>{
  assert.throws(()=>parseProject('{'));assert.throws(()=>parseProject(' '.repeat(65537)));assert.throws(()=>parseProject('null'));
});
