// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
// Card 2's expected heat rate (the design's card text): Q = ΔT/L · (k_v·πr² + k_s·(A − πr²)) from the
// document, shown beside the run's own "Heat rate through z0" only when the parallel formula
// applies (one cylinder through the whole slab height, fixed temperatures on exactly z0 and z1, no
// heat source); otherwise no line, and no other number.
const test=require('node:test');const assert=require('node:assert/strict');
const fs=require('node:fs');const path=require('node:path');
const STATIC='../../packages/simcase/src/simcase/studio/static/';
const STATIC_DIR=path.join(__dirname,'..','..','packages','simcase','src','simcase','studio','static');
let M;
test.before(async()=>{M=await import(STATIC+'workspace-model3d.mjs');});
const card2=()=>JSON.parse(fs.readFileSync(path.join(STATIC_DIR,'model3d-via-slab-3d.json'),'utf8'));
const card1=()=>JSON.parse(fs.readFileSync(path.join(STATIC_DIR,'model3d-layer-stack-3d.json'),'utf8'));
const heat=d=>d.physics.heat;
// a run's values as the run route answers them on card 2 (W6-UI)
const VALUES={heat_rate_by_selection:{z0:{value:-31.751473524515216,unit:'W'},z1:{value:31.75147352461867,unit:'W'}},
 total_source:{value:0,unit:'W'},balance_residual:{value:-1.03e-10,unit:'W'},relative_balance_residual:{value:1.63e-12,unit:'1'},
 temperature_min:{value:300,unit:'K',position_m:[-1,-1,0],region:'background'},temperature_max:{value:301,unit:'K',position_m:[-1,-1,1],region:'background'}};
const line=rows=>rows.find(r=>r[0]==='Expected heat rate');

test('card 2: Expected heat rate 31.99 W (parallel formula), beside Heat rate through z0',()=>{
 const e=M.expectedHeatRate(card2());
 const q=1/1*(100*Math.PI*0.3**2+1*(4-Math.PI*0.3**2));
 assert.equal(e.value,q);
 assert.equal(e.text,'Expected heat rate 31.99 W (parallel formula)');
 const rows=M.valuesRows(VALUES,'m',{expected:e});
 assert.deepEqual(rows.map(r=>r[0]),['Temperature, max (whole model)','Temperature, min (whole model)','Heat rate through z0','Expected heat rate','Heat rate through z1','Total heat source','Energy balance residual']);
 assert.equal(line(rows).join(' '),'Expected heat rate 31.99 W (parallel formula)');
 assert.equal(rows[2][1],'-31.7515 W','the run\'s own value is unchanged');
 assert.deepEqual(M.valuesRows(VALUES,'m'),M.valuesRows(VALUES,'m',{expected:null}),'no expectation: the rows of before');
});

test('the value follows the document: a new copper k, quantities in other units, the temperatures',()=>{
 const d=card2();d.materials.copper.thermal_conductivity='200 W/(m K)';
 assert.equal(M.expectedHeatRate(d).text,'Expected heat rate 60.27 W (parallel formula)');
 const t=card2();heat(t).prescribed_temperature={z0:'300 K',z1:'310 K'};
 assert.equal(M.expectedHeatRate(t).text,'Expected heat rate 319.9 W (parallel formula)');
 const r=card2();r.geometry.components.c.features[0].r=0.5;
 assert.equal(M.expectedHeatRate(r).value,1*(100*Math.PI*0.25+1*(4-Math.PI*0.25)));
});

test('no line when the parallel formula does not apply',()=>{
 const source=card2();heat(source).heat_source_density={copper:'1e6 W/m^3'};
 assert.equal(M.expectedHeatRate(source),null,'a heat source');
 const z1=card2();delete heat(z1).prescribed_temperature.z1;
 assert.equal(M.expectedHeatRate(z1),null,'z1 removed');
 const extra=card2();heat(extra).prescribed_temperature['via.top']='300 K';
 assert.equal(M.expectedHeatRate(extra),null,'a fixed temperature beside z0 and z1');
 const short=card2();short.geometry.components.c.features[0].zmax=0.5;
 assert.equal(M.expectedHeatRate(short),null,'a cylinder not through the slab');
 const two=card2();two.geometry.components.c.features.push({...two.geometry.components.c.features[0],name:'via_2',cx:0.6});
 assert.equal(M.expectedHeatRate(two),null,'two cylinders');
 const expr=card2();expr.geometry.components.c.features[0].r='rv';expr.geometry.parameters={rv:{value:'0.3 m'}};
 assert.equal(M.expectedHeatRate(expr),null,'a value the server evaluates (a parameter) is not guessed');
 const noK=card2();delete noK.materials.copper.thermal_conductivity;
 assert.equal(M.expectedHeatRate(noK),null,'a material without k');
 assert.equal(M.expectedHeatRate(card1()),null,'card 1');
 const none=card2();delete none.physics;
 assert.equal(M.expectedHeatRate(none),null,'no heat physics');
});
