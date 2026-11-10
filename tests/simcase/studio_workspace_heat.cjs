// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
const {test,before}=require('node:test');const assert=require('node:assert/strict');
let H,snapshot,parseProject;
before(async()=>{H=await import('../../packages/simcase/src/simcase/studio/static/workspace-heat.mjs');({snapshot,parseProject}=await import('../../packages/simcase/src/simcase/studio/static/workspace-project.mjs'));});
const plate=(sides={},extra={})=>({...H.DEFAULT_THERMAL,...extra,sides:{...H.DEFAULT_THERMAL.sides,...sides}});
const limits={max_nodes:10201,max_triangles:20000};
test('heat inputs are finite, positive where physical, and one condition per side',()=>{
 assert.deepEqual(H.validateThermal(H.DEFAULT_THERMAL).sides.left,{type:'temperature',temperature:280});
 for(const bad of [plate({},{width:0}),plate({},{height:-1}),plate({},{conductivity:0}),plate({},{source:NaN}),plate({},{nx:1.5}),plate({},{ny:0}),plate({left:{type:'radiation'}}),plate({left:{type:'temperature',temperature:-1}}),plate({top:{type:'convection',h:-1,ambient:300}}),plate({top:{type:'convection',h:5}}),plate({right:{type:'flux',inward_heat_flux:'5'}}),plate({right:{type:'flux',flux:5}}),{...H.DEFAULT_THERMAL,sides:{left:{type:'insulated'}}}])
  assert.throws(()=>H.validateThermal(bad));
 assert.deepEqual(H.validateThermal(plate({left:{type:'temperature',temperature:300,extra:1}})).sides.left,{type:'temperature',temperature:300});
});
test('readiness follows the public contract: an anchor, matching corners and server mesh limits',()=>{
 assert.equal(H.thermalBlock(H.validateThermal(H.DEFAULT_THERMAL),limits),'');
 const ins={type:'insulated'};
 assert.match(H.thermalBlock(H.validateThermal(plate({left:ins,right:{type:'flux',inward_heat_flux:100}}))),/undetermined/);
 assert.match(H.thermalBlock(H.validateThermal(plate({left:ins,right:ins,top:{type:'convection',h:0,ambient:300}}))),/undetermined/);
 assert.equal(H.thermalBlock(H.validateThermal(plate({left:ins,right:ins,top:{type:'convection',h:5,ambient:300}}))),'');
 assert.match(H.thermalBlock(H.validateThermal(plate({bottom:{type:'temperature',temperature:300}}))),/left and bottom/);
 assert.equal(H.thermalBlock(H.validateThermal(plate({bottom:{type:'temperature',temperature:280},right:{type:'temperature',temperature:280}}))),'');
 assert.match(H.thermalBlock(H.validateThermal(plate({},{nx:200,ny:100})),limits),/20301 nodes and 40000 triangles/);
 assert.equal(H.thermalBlock(H.validateThermal(plate({},{nx:100,ny:100})),limits),'');
});
test('the solver document uses mm and K and adds natural-condition keys only when used',()=>{
 const d=H.heatDocument(H.DEFAULT_THERMAL);
 // format 0.3: each value carries its unit; the form keeps the inward heat flux, as the document does
 assert.deepEqual(d,{openphysics:'0.3',name:'Workspace steady heat',geometry:{length_unit:'mm',depth:null,domain:{xmin:0,xmax:30,ymin:0,ymax:20}},materials:{},
  physics:{heat1:{type:'thermal.steady2d',thermal_conductivity:'12.5 W/(m K)',heat_source_density:'0 W/m^3',prescribed_temperature:{left:'280 K',right:'315 K'}}},mesh:{subdivision_count:[32,16]},study:{type:'single'},results:{save_fields:true,plots:false}});
 const mixed=H.heatDocument(plate({left:{type:'flux',inward_heat_flux:500},top:{type:'convection',h:10,ambient:290}},{source:1e5})).physics.heat1;
 assert.deepEqual(mixed.prescribed_temperature,{right:'315 K'});assert.deepEqual(mixed.inward_heat_flux,{left:'500 W/m^2'});
 assert.deepEqual(mixed.convection,{top:{heat_transfer_coefficient:'10 W/(m^2 K)',ambient_temperature:'290 K'}});
 assert.equal(H.heatDocument(plate({left:{type:'flux',inward_heat_flux:0}})).physics.heat1.inward_heat_flux.left,'0 W/m^2');
 assert.equal(H.sideText({type:'flux',inward_heat_flux:500}),'inward q = 500 W/m²');
 assert.equal(H.sideText({type:'convection',h:10,ambient:290}),'h = 10 W/(m²·K), T∞ = 290 K');assert.equal(H.thermalSummary(H.DEFAULT_THERMAL),'30 × 20 mm · k 12.5 W/(m·K)');
});
test('projects (version 6) store the heat plate with the inward heat flux; heat alone is a valid application',()=>{
 const state={width:500,voltage:1,electric:false,heat:true,structure:false,optics:false,thermal:plate({top:{type:'convection',h:10,ambient:290}},{width:40})};
 const setup={materials:{Core:'Silicon',Oxide:'Silica',Heater:''},temperature:293.15,cooling:'',fixed:'',terminal:''};
 const doc=snapshot(state,setup);assert.equal(doc.version,6);assert.equal(doc.units.thermal_length,'mm');
 const loaded=parseProject(JSON.stringify(doc));assert.equal(loaded.model.thermal.width,40);assert.deepEqual(loaded.model.thermal.sides.top,{type:'convection',h:10,ambient:290});
 const flux=snapshot({...state,thermal:plate({left:{type:'flux',inward_heat_flux:250}})},setup);
 assert.deepEqual(parseProject(JSON.stringify(flux)).model.thermal.sides.left,{type:'flux',inward_heat_flux:250});
 // a project of version 5 stored the outward flux under "flux": it is refused by name, never read with the other sign
 const v5=JSON.parse(JSON.stringify(flux));v5.version=5;v5.model.thermal.sides.left={type:'flux',flux:-250};
 assert.throws(()=>parseProject(JSON.stringify(v5)),/version 5\) was saved before the units and naming batch/);
 v5.version=6;assert.throws(()=>parseProject(JSON.stringify(v5)),/inward heat flux/);
 for(const change of [d=>d.model.thermal.conductivity=-1,d=>delete d.model.thermal,d=>d.units.thermal_length='m',d=>d.model.optics=true])
 {const d=JSON.parse(JSON.stringify(doc));change(d);assert.throws(()=>parseProject(JSON.stringify(d)));}
});
