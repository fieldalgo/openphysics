// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
// The 3D model's heat (slice D, UI): the Heat transfer (3D) rows and their edits, Run's reasons in
// order, "No need to run", the temperature colours, the values table and the run's progress line.
const test=require('node:test');const assert=require('node:assert/strict');
const fs=require('node:fs');const path=require('node:path');
const STATIC='../../packages/simcase/src/simcase/studio/static/';
const STATIC_DIR=path.join(__dirname,'..','..','packages','simcase','src','simcase','studio','static');
let M,W;
test.before(async()=>{M=await import(STATIC+'workspace-model3d.mjs');const C=await import(STATIC+'model3d-mesh-model.mjs');W={estimateText:C.estimateText,meshBlocked:C.meshBlocked};});
const card=()=>JSON.parse(fs.readFileSync(path.join(STATIC_DIR,'model3d-layer-stack-3d.json'),'utf8'));
const record=()=>JSON.parse(fs.readFileSync(path.join(__dirname,'studio_session_fixtures','model3d-run-record.json'),'utf8'));
const heat=doc=>doc.physics.heat;
const bare=()=>{const d=card();delete d.physics;return d;};

test('Heat transfer (3D): the tree rows after Materials, then Mesh 1, Study 1 and Results with the kept runs',()=>{
 const doc=M.setHeatSource(M.setFixedTemperature(bare(),'z0','300'),'via','1e12');
 const rows=M.treeRows(doc,null,null,W,{runs:[record()]});
 const keys=rows.map(r=>r.key),at=keys.indexOf('materials');
 assert.deepEqual(keys.slice(at),['materials','heat','heat:k','heat:fixed:z0','heat:source:via','heat:insulated','mesh','study','results','run:1']);
 const row=k=>rows.find(r=>r.key===k);
 assert.deepEqual([row('heat').label,row('heat').level],['Heat transfer (3D)',2]);
 assert.deepEqual([row('heat:k').label,row('heat:k').note],['Thermal conductivity','from Materials']);
 assert.deepEqual([row('heat:fixed:z0').label,row('heat:fixed:z0').note,row('heat:fixed:z0').level],['Fixed temperature 1','z0 · 300 K',3]);
 assert.deepEqual([row('heat:source:via').label,row('heat:source:via').note],['Heat source 1','via · 1e12 W/m³']);
 assert.deepEqual([row('heat:insulated').label,row('heat:insulated').note],['Insulated','every other outer face']);
 assert.deepEqual([row('study').label,row('results').label,row('run:1').label,row('run:1').level],['Study 1 · Steady','Results','Run 1 · Temperature (surfaces)',3]);
 // without a heat block: the Heat transfer row says so, and no rows under it
 const none=M.treeRows(bare(),null,null,W,{runs:[]});
 assert.equal(none.find(r=>r.key==='heat').note,'not set: Add a fixed temperature');
 assert.equal(none.some(r=>r.key.startsWith('heat:fixed')),false);
 // the check's run refusal marks Heat transfer (3D)
 const check={features:[],regions:[],display:{faces:[]},mesh:{ok:true,estimate:{tetrahedra:2402,seconds:1.44}},
  run:{ok:false,refused:'Fixed temperature needs an outer face; via.z1 is inside',code:'E-CONTRACT'}};
 assert.deepEqual(M.treeRows(doc,check,null,W,{runs:[]}).filter(r=>r.problem).map(r=>r.key),['heat']);
 // without a heat block the reader's refusal (no thermal.steady3d entry) marks nothing: the note says it
 const noPhysics={...check,run:{ok:false,refused:"Run takes a thermal.steady3d document (one physics entry of type 'thermal.steady3d')",code:null}};
 assert.deepEqual(M.treeRows(bare(),noPhysics,null,W,{runs:[]}).filter(r=>r.problem).map(r=>r.key),[]);
});

test('fixed temperatures, heat sources and conductivities: quantities in range, in the 2D range sentence',()=>{
 let doc=M.setFixedTemperature(bare(),'z0','300');
 assert.deepEqual(heat(doc),{type:'thermal.steady3d',prescribed_temperature:{z0:'300 K'}});
 doc=M.setFixedTemperature(doc,'stack.top.top','310 K');
 assert.deepEqual(heat(doc).prescribed_temperature,{z0:'300 K','stack.top.top':'310 K'});
 assert.throws(()=>M.setFixedTemperature(doc,'z0','0'),{message:'Fixed temperature must be between 1–2000 K.'});
 assert.throws(()=>M.setFixedTemperature(doc,'z0','300 C'),{message:'C is not a temperature unit (K).'});
 doc=M.setHeatSource(doc,'via','1e12 W/m^3');assert.equal(heat(doc).heat_source_density.via,'1e12 W/m^3');
 assert.equal(heat(M.setHeatSource(doc,'via','2e12')).heat_source_density.via,'2e12 W/m^3');
 assert.throws(()=>M.setHeatSource(doc,'via','2e15'),{message:'Heat source must be between -1e15–1e15 W/m³.'});
 doc=M.removeHeatSource(doc,'via');assert.equal('heat_source_density' in heat(doc),false);
 doc=M.removeFixedTemperature(doc,'stack.top.top');assert.deepEqual(heat(doc).prescribed_temperature,{z0:'300 K'});
 assert.equal(M.setConductivity(card(),'Cu','390').materials.Cu.thermal_conductivity,'390 W/(m K)');
 assert.throws(()=>M.setConductivity(card(),'Cu','1e5'),{message:'Thermal conductivity must be between 0.001–10000 W/(m K).'});
 assert.deepEqual(M.editableRegions({display:{regions:[{name:'Si'},{name:'SiO2'},{name:'via'}]}}),['Si','SiO2','via']);
});

test("Run's reasons, in order: a draft, the shape, the mesh, the reader, a run going, the last run's refusal",()=>{
 const ok={features:[],regions:[],display:{faces:[]},mesh:{ok:true,estimate:{}},run:{ok:true}};
 const r=(o)=>M.runReason({check:ok,...o},W);
 assert.equal(r({drafts:1}),'Correct the highlighted field or restore its last valid value first.');
 assert.equal(r({refused:{refused:'x'}}),'Fix 1 problem in Messages to run');
 assert.equal(r({check:{...ok,mesh:{ok:false,refused:'about 2402 tetrahedra; over the limit'}}}),'about 2402 tetrahedra; over the limit');
 assert.equal(r({check:{...ok,run:{ok:false,refused:'Fixed temperature needs an outer face; via.z1 is inside'}}}),'Fixed temperature needs an outer face; via.z1 is inside');
 assert.equal(r({running:true}),'Studio is already running one 3D heat model; wait for it or cancel it.');
 const unanchored="Fixed temperature is missing on the connected group of regions 'via': each connected group of regions needs one (galerkin: each connected component of the mesh needs a Dirichlet node)";
 const doc=card();
 assert.equal(r({doc,failure:{document:doc,message:unanchored}}),unanchored,'the words as the run answered them');
 assert.equal(r({doc:M.setFixedTemperature(doc,'z0','301'),failure:{document:doc,message:unanchored}}),null,'an edit clears it');
 assert.equal(r({}),null);
 assert.equal(M.runReason({check:null},W),'Show a 3d component first.');
});

test('No need to run: exactly when the document equals a kept run\'s, key order aside',()=>{
 const rec=record(),doc=JSON.parse(JSON.stringify(rec.document));
 assert.equal(M.keptRunFor(doc,[rec]),0);
 const reordered=Object.fromEntries(Object.entries(doc).reverse());
 assert.equal(M.keptRunFor(reordered,[rec]),0,'key order does not count');
 assert.equal(M.keptRunFor(M.setFixedTemperature(doc,'z0','301'),[rec]),-1);
 assert.equal(M.keptRunFor(doc,[{...rec,result:'thermal-steady3d-run-v2'}]),-1,'another result format is not these results');
 assert.equal(M.keptRunFor(doc,[record(),rec]),1,'the latest such run');
 assert.equal(M.noNeedText(1),'No need to run: Run 2 already has these results.');
});

test('temperature colours, the values table and the progress line',()=>{
 assert.deepEqual(M.temperatureColor(300,300,310),[0.231,0.298,0.753]);
 assert.deepEqual(M.temperatureColor(310,300,310),[0.706,0.016,0.150]);
 assert.deepEqual(M.temperatureColor(305,300,310),[0.865,0.865,0.865]);
 assert.deepEqual(M.temperatureColor(305,305,305),[0.865,0.865,0.865],'one temperature: the middle colour');
 const rows=M.valuesRows(record().values,'um');
 assert.deepEqual(rows.map(r=>r[0]),['Temperature, max','Temperature, min','Heat rate through z0','Total heat source','Energy balance residual']);
 assert.equal(rows[0][1],'1127.33 K in Si (top) at (179, 0, 610) µm');
 assert.equal(rows[1][1],'300 K in Si at (0, 0, 0) µm');
 assert.equal(rows[2][1],'-4 W');assert.equal(rows[3][1],'4 W');assert.equal(rows[4][1],'-1.35e-13 W (1.69e-14 of the summed heat rates)');
 assert.equal(M.runProgress({status:'running',step:'mesh',elapsed_s:3.2,expected_s:1.4,longer_than_estimate:true}),'Meshing · 0:03 · taking longer than the estimate');
 assert.equal(M.runProgress({status:'running',step:'solve',elapsed_s:61,expected_s:1.4,longer_than_estimate:false}),'Solving · 1:01');
 assert.equal(M.runProgress({status:'cancelled'}),'Run cancelled; nothing kept.');
 assert.equal(M.runProgress({status:'error',error:{message:'boom'}}),'Run failed: boom');
});

test('Use for → Fixed temperature names the face by the latest feature\'s alone name',()=>{
 const ids=['stack','via'];
 assert.equal(M.boundaryNameFor({alone:['stack.oxide.top','stack.top.bottom','via.z1']},ids),'via.z1');
 assert.equal(M.boundaryNameFor({alone:['domain.z1','stack.top.top']},ids),'stack.top.top');
 assert.equal(M.boundaryNameFor({alone:['domain.x0']},ids),'domain.x0');
 assert.equal(M.boundaryNameFor({alone:[]},ids),null);
});
