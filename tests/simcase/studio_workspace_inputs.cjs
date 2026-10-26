// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0

const {before}=require('node:test');
let parseNumeric,NumericDrafts;
before(async()=>{
({parseNumeric,NumericDrafts}=await import('../../packages/simcase/src/simcase/studio/static/workspace-inputs.mjs'));
});
const test=require('node:test');const assert=require('node:assert/strict');

test('physical bounds, decimals and scientific notation share one parser',()=>{
 for(const [key,raw,value] of [['width','300',300],['width','900',900],['width','550.5',550.5],['voltage','0',0],['voltage','1e-1',.1],['temperature','2000',2000]])assert.deepEqual(parseNumeric(key,raw),{ok:true,value});
});
test('empty, nonfinite, ambiguous and out-of-range input yields actionable unit errors',()=>{
 for(const raw of ['', ' ','abc','Infinity','NaN','0x200','500nm','299.9','900.1','1e999']){const r=parseNumeric('width',raw);assert.equal(r.ok,false);assert.match(r.message,/300–900 nm/);}
 assert.equal(parseNumeric('temperature','-1').ok,false);assert.equal(parseNumeric('voltage','10.01').ok,false);
});
test('invalid drafts survive navigation reads, block actions and cannot alter accepted values',()=>{
 const d=new NumericDrafts();let accepted=500;const r=d.update('width','999');if(r.ok)accepted=r.value;
 assert.equal(accepted,500);assert.equal(d.get('width').raw,'999');const visible=d.issues;visible[0].raw='500';
 assert.equal(d.get('width').raw,'999');assert.throws(()=>d.assertValid());
 const fixed=d.update('width','550');assert.equal(fixed.value,550);assert.equal(d.invalid,false);d.assertValid();
});
test('multiple pending fields clear independently or explicitly together',()=>{
 const d=new NumericDrafts();d.update('width','');d.update('temperature','-1');d.clear('width');assert.equal(d.issues.length,1);
 d.clear();assert.equal(d.invalid,false);assert.throws(()=>parseNumeric('unsupported','1'));
});
