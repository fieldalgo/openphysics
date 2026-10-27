// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
const {test,before}=require('node:test');const assert=require('node:assert/strict');
let H,snapshot,parseProject;
before(async()=>{H=await import('../../packages/simcase/src/simcase/studio/static/workspace-heat.mjs');({snapshot,parseProject}=await import('../../packages/simcase/src/simcase/studio/static/workspace-project.mjs'));});
const plate=(sides={},extra={})=>({...H.DEFAULT_THERMAL,...extra,sides:{...H.DEFAULT_THERMAL.sides,...sides}});
const limits={max_nodes:10201,max_triangles:20000};
test('heat inputs are finite, positive where physical, and one condition per side',()=>{
 assert.deepEqual(H.validateThermal(H.DEFAULT_THERMAL).sides.left,{type:'temperature',temperature:280});
 for(const bad of [plate({},{width:0}),plate({},{height:-1}),plate({},{conductivity:0}),plate({},{source:NaN}),plate({},{nx:1.5}),plate({},{ny:0}),plate({left:{type:'radiation'}}),plate({left:{type:'temperature',temperature:-1}}),plate({top:{type:'convection',h:-1,ambient:300}}),plate({top:{type:'convection',h:5}}),plate({right:{type:'flux',flux:'5'}}),{...H.DEFAULT_THERMAL,sides:{left:{type:'insulated'}}}])
  assert.throws(()=>H.validateThermal(bad));
 assert.deepEqual(H.validateThermal(plate({left:{type:'temperature',temperature:300,extra:1}})).sides.left,{type:'temperature',temperature:300});
});
test('readiness follows the public contract: an anchor, matching corners and server mesh limits',()=>{
 assert.equal(H.thermalBlock(H.validateThermal(H.DEFAULT_THERMAL),limits),'');
 const ins={type:'insulated'};
 assert.match(H.thermalBlock(H.validateThermal(plate({left:ins,right:{type:'flux',flux:100}}))),/undetermined/);
 assert.match(H.thermalBlock(H.validateThermal(plate({left:ins,right:ins,top:{type:'convection',h:0,ambient:300}}))),/undetermined/);
 assert.equal(H.thermalBlock(H.validateThermal(plate({left:ins,right:ins,top:{type:'convection',h:5,ambient:300}}))),'');
 assert.match(H.thermalBlock(H.validateThermal(plate({bottom:{type:'temperature',temperature:300}}))),/left and bottom/);
 assert.equal(H.thermalBlock(H.validateThermal(plate({bottom:{type:'temperature',temperature:280},right:{type:'temperature',temperature:280}}))),'');
 assert.match(H.thermalBlock(H.validateThermal(plate({},{nx:200,ny:100})),limits),/20301 nodes and 40000 triangles/);
 assert.equal(H.thermalBlock(H.validateThermal(plate({},{nx:100,ny:100})),limits),'');
});
test('the solver document uses mm and K and adds natural-condition keys only when used',()=>{
 const d=H.heatDocument(H.DEFAULT_THERMAL);
 assert.deepEqual(d,{openphysics:'0.2',name:'Workspace steady heat',units:{length:'mm',temperature:'K'},geometry:{domain:{xmin:0,xmax:30,ymin:0,ymax:20}},materials:{},
  physics:{heat1:{type:'thermal.steady2d',conductivity_w_mk:12.5,heat_source_w_m3:0,dirichlet_temperature_k:{left:280,right:315}}},mesh:{subdivisions:[32,16]},study:{type:'single'},results:{save_fields:true,plots:false}});
 const mixed=H.heatDocument(plate({left:{type:'flux',flux:-500},top:{type:'convection',h:10,ambient:290}},{source:1e5})).physics.heat1;
 assert.deepEqual(mixed.dirichlet_temperature_k,{right:315});assert.deepEqual(mixed.outward_flux_w_m2,{left:-500});assert.deepEqual(mixed.convection,{top:{h_w_m2k:10,ambient_temperature_k:290}});
 assert.equal(H.sideText({type:'convection',h:10,ambient:290}),'h = 10 W/(m²·K), T∞ = 290 K');assert.equal(H.thermalSummary(H.DEFAULT_THERMAL),'30 × 20 mm · k 12.5 W/(m·K)');
});
test('projects store the heat plate from version 5; heat alone is a valid application',()=>{
 const state={width:500,voltage:1,electric:false,heat:true,structure:false,optics:false,thermal:plate({top:{type:'convection',h:10,ambient:290}},{width:40})};
 const setup={materials:{Core:'Silicon',Oxide:'Silica',Heater:''},temperature:293.15,cooling:'',fixed:'',terminal:''};
 const doc=snapshot(state,setup);assert.equal(doc.version,5);assert.equal(doc.units.thermal_length,'mm');
 const loaded=parseProject(JSON.stringify(doc));assert.equal(loaded.model.thermal.width,40);assert.deepEqual(loaded.model.thermal.sides.top,{type:'convection',h:10,ambient:290});
 const v4=JSON.parse(JSON.stringify(doc));v4.version=4;delete v4.units.thermal_length;assert.throws(()=>parseProject(JSON.stringify(v4)),/version 5/);delete v4.model.thermal;assert.equal(parseProject(JSON.stringify(v4)).model.thermal.width,30);
 for(const change of [d=>d.model.thermal.conductivity=-1,d=>delete d.model.thermal,d=>d.units.thermal_length='m',d=>d.model.optics=true])
 {const d=JSON.parse(JSON.stringify(doc));change(d);assert.throws(()=>parseProject(JSON.stringify(d)));}
});
