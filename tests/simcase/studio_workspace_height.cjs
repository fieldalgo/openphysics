// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
const {test,before}=require('node:test');const assert=require('node:assert/strict');
let snapshot,parseProject,opticalDocument,sectionSvg,createSession,parseSession,opticalSettings,OPTICAL_SETTINGS;
before(async()=>{
 ({snapshot,parseProject}=await import('../../packages/simcase/src/simcase/studio/static/workspace-project.mjs'));
 ({opticalDocument}=await import('../../packages/simcase/src/simcase/studio/static/workspace-optical.mjs'));
 ({sectionSvg}=await import('../../packages/simcase/src/simcase/studio/static/workspace-section.mjs'));
 ({createSession,parseSession,opticalSettings,OPTICAL_SETTINGS}=await import('../../packages/simcase/src/simcase/studio/static/workspace-notebook.mjs'));
});
const model=()=>({width:500,height:300,voltage:1,electric:false,heat:false,structure:false,optics:true});
const setup=()=>({materials:{Core:'Silicon',Oxide:'Silica',Heater:''},temperature:293.15,cooling:'',fixed:'',terminal:''});
const field={node_coordinates:[[0,0],[1e-6,0],[0,1e-6]],triangles:[[0,1,2]],real:[[[1,0,0]],[[0,1,0]]],imag:[[[0,0,0]],[[0,0,0]]]};
const run=(input,settings)=>({job:'abcdef12',completedAt:'2026-10-26T00:00:00Z',input,settings,effective_index:[2.5,1.8],field,origin:'local'});
const legacyV1=()=>{const d=snapshot(model(),setup());d.version=1;for(const k of ['height','wavelength','coreMesh','shapes','thermal'])delete d.model[k];for(const k of ['height','wavelength','core_mesh','shapes','thermal_length'])delete d.units[k];return d;};
test('earlier projects migrate their centred core to one rectangle; later fields need their version',()=>{
 const migrated=parseProject(JSON.stringify(legacyV1()));assert.equal(migrated.version,5);assert.equal(migrated.model.height,220);
 assert.deepEqual(migrated.model.shapes,[{name:'Core',type:'rect',material:'Silicon',x:-250,y:0,w:500,h:220}]);
 for(const change of [d=>delete d.model.height,d=>d.model.height=99,d=>d.model.height=501,d=>d.model.height=null,d=>d.units.height='um',d=>delete d.units.shapes]){const d=snapshot(model(),setup());change(d);assert.throws(()=>parseProject(JSON.stringify(d)));}
 const v1=legacyV1();v1.model.height=300;assert.throws(()=>parseProject(JSON.stringify(v1)));
 const v3=snapshot(model(),setup());v3.version=3;delete v3.model.thermal;assert.throws(()=>parseProject(JSON.stringify(v3)),/Shapes require project version 4/);
 const unassigned=legacyV1();unassigned.setup.materials.Core='Platinum';assert.equal(parseProject(JSON.stringify(unassigned)).model.shapes[0].material,'');
});
test('a migrated core is submitted as its four corners with the grading centre at mid-height',()=>{
 for(const height of [100,300.5,500]){
  const d=opticalDocument({...model(),height},setup()),s=d.geometry.shapes[0];         // format 0.3, in nm
  assert.equal(d.geometry.length_unit,'nm');
  assert.deepEqual(s,{name:'s1',material:'physmat:Si',element_size:'30 nm',type:'polygon',points:[[-250,0],[250,0],[250,height],[-250,height]]});
  assert.deepEqual(d.mesh.grading.position,['0 nm',`${height/2} nm`]);
  const shapes=snapshot({...model(),height},setup()).model.shapes;
  assert.ok(sectionSvg(shapes).includes(`points="275,175 325,175 325,${175-height/10} 275,${175-height/10}"`));
 }
});
test('runs of earlier adapters are refused with their sessions; a current run keeps its settings',()=>{
 const input=snapshot(model(),setup());
 // session format 6 holds runs of the current adapter only: an earlier adapter's settings are refused
 const v2={...OPTICAL_SETTINGS,adapter:'optical-rectangle-v2',height_nm:300};
 assert.throws(()=>createSession(input,[run(input,v2)],'abcdef12',['abcdef12','abcdef12']),/Unsupported run settings/);
 const current=run(input,opticalSettings()),session=createSession(input,[current],'abcdef12',['abcdef12',null]);
 assert.equal(session.version,6);
 const restored=parseSession(JSON.stringify(session));assert.equal(restored.runs[0].settings.adapter,'optical-shapes-v7');
 for(const change of [d=>d.runs[0].settings.vacuum_wavelength='1600 nm',d=>d.runs[0].settings.adapter='optical-shapes-v5',d=>d.runs[0].settings.height_nm=220]){
  const d=JSON.parse(JSON.stringify(session));change(d);assert.throws(()=>parseSession(JSON.stringify(d)));
 }
 // sessions saved before the units and naming batch (versions 1-5) are refused by name
 for(const version of [1,2,3,4,5])assert.throws(()=>parseSession(JSON.stringify({...session,version})),/saved before the units and naming batch/);
});
