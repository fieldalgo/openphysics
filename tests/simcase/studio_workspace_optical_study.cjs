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
const field={node_coordinates:[[0,0],[1e-6,0],[0,1e-6]],triangles:[[0,1,2]],real:[[[1,0,0]],[[0,1,0]]],imag:[[[0,0,0]],[[0,0,0]]]};
const run=(input,settings=opticalSettings(input.model.wavelength,input.model.coreMesh))=>({job:'abcdef12',completedAt:'2026-10-26T00:00:00Z',input,settings,effective_index:[2.5,1.8],field,origin:'local'});

test('wavelength and core mesh size drive the submitted solver document',()=>{
 for(const [wavelength,coreMesh] of [[1400,20],[1512.5,33.3],[1700,60]]){
  const d=opticalDocument(model({wavelength,coreMesh}),setup());          // quantity strings, as typed
  assert.equal(d.physics.em1.vacuum_wavelength,wavelength+' nm');
  assert.equal(d.geometry.shapes[0].element_size,coreMesh+' nm');assert.equal(d.mesh.grading.near,coreMesh+' nm');
  assert.equal(d.physics.em1.mode_count,2);assert.equal(d.mesh.grading.far,'160 nm');assert.equal(d.mesh.element_size,'250 nm');
  assert.equal(d.mesh.grading.refinement_distance,'1000 nm');assert.deepEqual(d.geometry.domain,{xmin:-1500,xmax:1500,ymin:-1200,ymax:1200});
 }
 const legacy=opticalDocument({width:500,height:220,electric:false,heat:false,structure:false,optics:true},setup());
 assert.equal(legacy.physics.em1.vacuum_wavelength,'1550 nm');assert.equal(legacy.geometry.shapes[0].element_size,'30 nm');
 for(const [w,m] of [[1399,30],[1701,30],[1550,19],[1550,61],[NaN,30],[1550,Infinity]])assert.throws(()=>opticalStudy(w,m));
});
test('numeric drafts report the editable ranges with units',()=>{
 assert.deepEqual(parseNumeric('wavelength','1600'),{ok:true,value:1600});assert.deepEqual(parseNumeric('coreMesh','20'),{ok:true,value:20});
 assert.match(parseNumeric('wavelength','1300').message,/1400–1700 nm/);assert.match(parseNumeric('coreMesh','10').message,/20–60 nm/);
});
test('projects carry wavelength and core mesh since version 3; earlier versions migrate to 1550 nm / 30 nm',()=>{
 const doc=snapshot(model({wavelength:1625,coreMesh:40}),setup());
 assert.equal(doc.version,5);assert.equal(doc.units.wavelength,'nm');assert.equal(doc.units.core_mesh,'nm');
 const loaded=parseProject(JSON.stringify(doc));assert.equal(loaded.model.wavelength,1625);assert.equal(loaded.model.coreMesh,40);
 const v2=JSON.parse(JSON.stringify(doc));v2.version=2;for(const k of ['wavelength','coreMesh','shapes','thermal'])delete v2.model[k];for(const k of ['wavelength','core_mesh','shapes','thermal_length'])delete v2.units[k];
 const migrated=parseProject(JSON.stringify(v2));assert.equal(migrated.version,5);assert.equal(migrated.model.wavelength,1550);assert.equal(migrated.model.coreMesh,30);
 v2.model.wavelength=1600;assert.throws(()=>parseProject(JSON.stringify(v2)));
 for(const change of [d=>delete d.model.wavelength,d=>d.model.wavelength=1399,d=>d.model.wavelength=1701,d=>d.model.wavelength='1600',d=>d.model.coreMesh=19,d=>d.model.coreMesh=61,d=>d.model.coreMesh=null,d=>d.units.wavelength='um',d=>delete d.units.core_mesh]){
  const d=snapshot(model(),setup());change(d);assert.throws(()=>parseProject(JSON.stringify(d)));
 }
});
test('runs keep the captured wavelength and core mesh; mismatched provenance is rejected',()=>{
 const input=snapshot(model({wavelength:1600,coreMesh:45}),setup()),r=run(input);
 assert.equal(r.settings.adapter,'optical-shapes-v7');assert.equal(r.settings.height_nm,undefined);assert.equal(r.settings.vacuum_wavelength,'1600 nm');assert.equal(r.settings.core_element_size,'45 nm');
 const session=createSession(input,[r],r.job,[r.job,null]);assert.equal(session.version,6);
 const restored=parseSession(JSON.stringify(session));assert.equal(restored.runs[0].input.model.wavelength,1600);assert.equal(restored.runs[0].settings.core_element_size,'45 nm');
 for(const change of [d=>d.runs[0].settings.vacuum_wavelength='1550 nm',d=>d.runs[0].settings.core_element_size='30 nm',d=>d.runs[0].settings.vacuum_wavelength=1600,d=>d.runs[0].input.model.wavelength=1650,d=>d.runs[0].settings.adapter='optical-rectangle-v2']){
  const d=JSON.parse(JSON.stringify(session));change(d);assert.throws(()=>parseSession(JSON.stringify(d)));
 }
 const csv=runTableCsv(restored.runs);assert.ok(csv.split('\n')[0].includes('"wavelength_nm","core_mesh_nm"'));assert.ok(csv.includes('"1600","45"'));
});
test('sessions with results of earlier adapters are refused by name (saved before the units and naming batch)',()=>{
 const legacy=snapshot(model(),setup());legacy.version=2;for(const k of ['wavelength','coreMesh','shapes','thermal'])delete legacy.model[k];for(const k of ['wavelength','core_mesh','shapes','thermal_length'])delete legacy.units[k];
 const v2settings={adapter:'optical-rectangle-v2',height_nm:220,wavelength_nm:1550,core_mesh_nm:30,window_um:[-1.5,1.5,-1.2,1.2],boundary:'PEC',candidates:2,solver_version:'not reported'};
 const session={format:'openphysics-studio-session',version:2,input:legacy,runs:[{...run(legacy,v2settings),neff:[2.5,1.8]}],selected:'abcdef12',comparison:['abcdef12',null]};
 assert.throws(()=>parseSession(JSON.stringify(session)),/version 2\) was saved before the units and naming batch/);
 assert.equal(OPTICAL_SETTINGS.adapter,'optical-shapes-v7');
});
