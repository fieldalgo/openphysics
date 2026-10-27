// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
const {test,before}=require('node:test');const assert=require('node:assert/strict');
const base='../../packages/simcase/src/simcase/studio/static/';
let snapshot,parseProject,opticalDocument,opticalStudy,createSession,parseSession,opticalSettings,runTableCsv,parseNumeric,OPTICAL_SETTINGS;
before(async()=>{
 ({snapshot,parseProject}=await import(base+'workspace-project.mjs'));
 ({opticalDocument,opticalStudy}=await import(base+'workspace-optical.mjs'));
 ({createSession,parseSession,opticalSettings,runTableCsv,OPTICAL_SETTINGS}=await import(base+'workspace-notebook.mjs'));
 ({parseNumeric}=await import(base+'workspace-inputs.mjs'));
});
const model=(extra={})=>({width:500,height:220,wavelength:1510,coreMesh:25,voltage:1,electric:false,heat:false,structure:false,optics:true,...extra});
const setup=()=>({materials:{Core:'Silicon',Oxide:'Silica',Heater:''},temperature:293.15,cooling:'',fixed:'',terminal:''});
const field={nodes:[[0,0],[1,0],[0,1]],triangles:[[0,1,2]],real:[[[1,0,0]],[[0,1,0]]],imag:[[[0,0,0]],[[0,0,0]]]};
const run=(input,settings=opticalSettings(input.model.wavelength,input.model.coreMesh))=>({job:'abcdef12',completedAt:'2026-10-26T00:00:00Z',input,settings,neff:[2.5,1.8],field,origin:'local'});

test('wavelength and core mesh size drive the submitted solver document',()=>{
 for(const [wavelength,coreMesh] of [[1400,20],[1512.5,33.3],[1700,60]]){
  const d=opticalDocument(model({wavelength,coreMesh}),setup());
  assert.equal(d.physics.em1.wavelength,wavelength/1000);
  assert.equal(d.geometry.shapes[0].mesh_size,coreMesh/1000);assert.equal(d.mesh.grading.near,coreMesh/1000);
  assert.equal(d.physics.em1.num_modes,2);assert.equal(d.mesh.grading.far,0.16);assert.deepEqual(d.geometry.domain,{xmin:-1.5,xmax:1.5,ymin:-1.2,ymax:1.2});
 }
 const legacy=opticalDocument({width:500,height:220,electric:false,heat:false,structure:false,optics:true},setup());
 assert.equal(legacy.physics.em1.wavelength,1.55);assert.equal(legacy.geometry.shapes[0].mesh_size,0.03);
 for(const [w,m] of [[1399,30],[1701,30],[1550,19],[1550,61],[NaN,30],[1550,Infinity]])assert.throws(()=>opticalStudy(w,m));
});
test('numeric drafts report the editable ranges with units',()=>{
 assert.deepEqual(parseNumeric('wavelength','1600'),{ok:true,value:1600});assert.deepEqual(parseNumeric('coreMesh','20'),{ok:true,value:20});
 assert.match(parseNumeric('wavelength','1300').message,/1400–1700 nm/);assert.match(parseNumeric('coreMesh','10').message,/20–60 nm/);
});
test('projects carry wavelength and core mesh since version 3; earlier versions migrate to 1550 nm / 30 nm',()=>{
 const doc=snapshot(model({wavelength:1625,coreMesh:40}),setup());
 assert.equal(doc.version,4);assert.equal(doc.units.wavelength,'nm');assert.equal(doc.units.core_mesh,'nm');
 const loaded=parseProject(JSON.stringify(doc));assert.equal(loaded.model.wavelength,1625);assert.equal(loaded.model.coreMesh,40);
 const v2=JSON.parse(JSON.stringify(doc));v2.version=2;for(const k of ['wavelength','coreMesh','shapes'])delete v2.model[k];for(const k of ['wavelength','core_mesh','shapes'])delete v2.units[k];
 const migrated=parseProject(JSON.stringify(v2));assert.equal(migrated.version,4);assert.equal(migrated.model.wavelength,1550);assert.equal(migrated.model.coreMesh,30);
 v2.model.wavelength=1600;assert.throws(()=>parseProject(JSON.stringify(v2)));
 for(const change of [d=>delete d.model.wavelength,d=>d.model.wavelength=1399,d=>d.model.wavelength=1701,d=>d.model.wavelength='1600',d=>d.model.coreMesh=19,d=>d.model.coreMesh=61,d=>d.model.coreMesh=null,d=>d.units.wavelength='um',d=>delete d.units.core_mesh]){
  const d=snapshot(model(),setup());change(d);assert.throws(()=>parseProject(JSON.stringify(d)));
 }
});
test('runs keep the captured wavelength and core mesh; mismatched provenance is rejected',()=>{
 const input=snapshot(model({wavelength:1600,coreMesh:45}),setup()),r=run(input);
 assert.equal(r.settings.adapter,'optical-shapes-v5');assert.equal(r.settings.height_nm,undefined);assert.equal(r.settings.wavelength_nm,1600);assert.equal(r.settings.core_mesh_nm,45);
 const session=createSession(input,[r],r.job,[r.job,null]);assert.equal(session.version,4);
 const restored=parseSession(JSON.stringify(session));assert.equal(restored.runs[0].input.model.wavelength,1600);assert.equal(restored.runs[0].settings.core_mesh_nm,45);
 for(const change of [d=>d.runs[0].settings.wavelength_nm=1550,d=>d.runs[0].settings.core_mesh_nm=30,d=>d.runs[0].input.model.wavelength=1650,d=>d.runs[0].settings.adapter='optical-rectangle-v2']){
  const d=JSON.parse(JSON.stringify(session));change(d);assert.throws(()=>parseSession(JSON.stringify(d)));
 }
 const csv=runTableCsv(restored.runs);assert.ok(csv.split('\n')[0].includes('"wavelength_nm","core_mesh_nm"'));assert.ok(csv.includes('"1600","45"'));
});
test('results from earlier adapters import at their fixed 1550 nm / 30 nm settings',()=>{
 const legacy=snapshot(model(),setup());legacy.version=2;for(const k of ['wavelength','coreMesh','shapes'])delete legacy.model[k];for(const k of ['wavelength','core_mesh','shapes'])delete legacy.units[k];
 const v2settings={...OPTICAL_SETTINGS,adapter:'optical-rectangle-v2',height_nm:220};
 const session={format:'openphysics-studio-session',version:2,input:legacy,runs:[run(legacy,v2settings)],selected:'abcdef12',comparison:['abcdef12',null]};
 const imported=parseSession(JSON.stringify(session));assert.equal(imported.runs[0].input.model.wavelength,1550);assert.equal(imported.runs[0].input.model.coreMesh,30);assert.equal(imported.runs[0].settings.adapter,'optical-rectangle-v2');
 const v3input=snapshot(model({wavelength:1600}),setup());session.runs=[run(v3input,v2settings)];assert.throws(()=>parseSession(JSON.stringify(session)));
 const v3settings={...OPTICAL_SETTINGS,adapter:'optical-rectangle-v3',height_nm:220,wavelength_nm:1600,core_mesh_nm:25};session.runs=[run(v3input,v3settings)];
 assert.equal(parseSession(JSON.stringify(session)).runs[0].settings.adapter,'optical-rectangle-v3');
});
