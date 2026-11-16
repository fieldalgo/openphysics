// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
// The workspace Joule heating application: inputs, readiness, the solver document, project and
// session version 7 (version 6 still read), the result payload checks, the view model and the run
// controller. The default document is the two-material strip of the region Joule checks; the Python
// test test_studio_joule_regions.py runs the same document (WORKSPACE_DEFAULT) through Studio.
const {test,before}=require('node:test');const assert=require('node:assert/strict');
let J,P,N;
before(async()=>{J=await import('../../packages/simcase/src/simcase/studio/static/workspace-joule.mjs');
 P=await import('../../packages/simcase/src/simcase/studio/static/workspace-project.mjs');
 N=await import('../../packages/simcase/src/simcase/studio/static/workspace-notebook.mjs');});
const clone=x=>JSON.parse(JSON.stringify(x));
const inputs=(change=()=>{})=>{const j=clone(J.DEFAULT_JOULE);change(j);return j;};
const state={width:500,voltage:1,electric:true,heat:true,structure:false,optics:false};
const setup={materials:{Core:'Silicon',Oxide:'Silica',Heater:''},temperature:293.15,cooling:'',fixed:'',terminal:''};

test('the default document is the two-material strip, in mm with its units',()=>{
 assert.deepEqual(J.jouleDocument(J.DEFAULT_JOULE),{openphysics:'0.3',name:'Workspace Joule heating',
  geometry:{version:1,components:{xs:{dimension:'2d',length_unit:'mm',depth:null,domain:{xmin:0,xmax:2,ymin:0,ymax:1},
   background:{material:'A'},features:[{name:'b',type:'rect',x:1,y:0,w:1,h:1,material:'B'}]}}},
  materials:{A:{electrical_conductivity:{model:'linear_resistivity',reference_conductivity:'2000 S/m',reference_temperature:'300 K',resistivity_temperature_coefficient:'0.004 1/K',valid:{temperature:['250 K','600 K']}},thermal_conductivity:'1.5 W/(m K)'},
   B:{electrical_conductivity:{model:'linear_resistivity',reference_conductivity:'500 S/m',reference_temperature:'300 K',resistivity_temperature_coefficient:'-0.003 1/K',valid:{temperature:['250 K','600 K']}},thermal_conductivity:'0.25 W/(m K)'}},
  physics:{j:{type:'joule.temperature2d',prescribed_electric_potential:{left:'0.2 V',right:'0 V'},prescribed_temperature:{left:'300 K',right:'320 K'},
   initial_temperature:'300 K',iteration:{relaxation_factor:0.5,temperature_tolerance:'1e-9 K',relative_tolerance:1e-10,iteration_limit:100}}},
  mesh:{element_size:'0.125 mm'},study:{type:'single'},results:{save_fields:true,plots:false}});
 assert.equal(J.jouleBlock(J.validateJoule(J.DEFAULT_JOULE)),'');
});
test('constant materials give joule.steady2d without iteration keys; natural conditions appear only when used',()=>{
 const j=inputs(j=>{for(const m of j.materials)m.sigma={model:'constant',value:1000};j.sides.top.electric={type:'current',current:-5};
  j.sides.bottom.thermal={type:'convection',h:10,ambient:295};j.sides.top.thermal={type:'flux',flux:250};
  j.shapes.push({name:'disc',type:'circle',material:'A',cx:0.5,cy:0.5,r:0.2},{name:'tri',type:'polygon',material:'B',points:[[0.1,0.1],[0.3,0.1],[0.2,0.3]]});});
 const p=J.jouleDocument(j).physics.j;
 assert.equal(p.type,'joule.steady2d');assert.equal('iteration' in p,false);assert.equal('initial_temperature' in p,false);
 assert.deepEqual(p.inward_current_density,{top:'-5 A/m^2'});assert.deepEqual(p.inward_heat_flux,{top:'250 W/m^2'});
 assert.deepEqual(p.convection,{bottom:{heat_transfer_coefficient:'10 W/(m^2 K)',ambient_temperature:'295 K'}});
 const d=J.jouleDocument(j);assert.equal(d.materials.A.electrical_conductivity,'1000 S/m');
 assert.deepEqual(d.geometry.components.xs.features.slice(1),[{name:'disc',type:'circle',cx:0.5,cy:0.5,r:0.2,material:'A'},{name:'tri',type:'polygon',points:[[0.1,0.1],[0.3,0.1],[0.2,0.3]],material:'B'}]);
});
test('only used materials reach the document, so an unused model cannot change the physics',()=>{
 const j=inputs(j=>{j.materials[1].sigma={model:'constant',value:500};j.materials.push({name:'Spare',k:1,sigma:{model:'linear_resistivity',reference_conductivity:1,reference_temperature:300,coefficient:0,tmin:200,tmax:400}});});
 assert.deepEqual(Object.keys(J.jouleDocument(j).materials),['A','B']);
 const steady=inputs(j=>{for(const m of j.materials)m.sigma={model:'constant',value:7};j.materials.push({name:'Spare',k:1,sigma:{model:'linear_resistivity',reference_conductivity:1,reference_temperature:300,coefficient:0,tmin:200,tmax:400}});});
 assert.equal(J.jouleDocument(steady).physics.j.type,'joule.steady2d');assert.deepEqual(Object.keys(J.jouleDocument(steady).materials),['A','B']);
});
test('structural checks refuse bad values, names, ranges and shapes outside the domain, each by its reason',()=>{
 for(const [change,reason] of [[j=>j.width=0,/domain width/],[j=>j.height=NaN,/domain height/],[j=>j.elementSize=2,/element size/],[j=>j.background='C',/background material/],
  [j=>j.materials[0].k=0,/A thermal conductivity/],[j=>j.materials[1].name='A',/names must be different/],
  [j=>{j.materials[0].name='physmatSi';j.background='physmatSi';},/Material 1: name/],[j=>j.materials[0].sigma={model:'constant',value:-1},/A electrical conductivity/],
  [j=>j.materials[0].sigma.tmin=700,/lowest < highest/],[j=>j.materials[0].sigma.tmin=0,/A lowest valid temperature/],
  [j=>j.materials[0].sigma.reference_temperature=700,/reference temperature must lie/],[j=>j.materials[0].sigma.coefficient=-0.01,/resistivity must stay positive/],
  [j=>j.shapes[0].x=1.5,/must stay inside the domain/],[j=>j.shapes[0].name='background',/not be "background"/],[j=>j.shapes[0].name='b c',/Shape 1: name/],
  [j=>j.shapes[0].material='C',/choose one of the defined materials/],[j=>j.shapes.push({...j.shapes[0]}),/Shape names must be different/],
  [j=>j.shapes[0]={name:'p',type:'polygon',material:'A',points:[[0,0],[1,1],[1,0],[0,1]]},/edges 1 and 3 cross/],
  [j=>j.shapes[0]={name:'p',type:'polygon',material:'A',points:[[0,0],[1,0],[1,0],[0,1]]},/vertex is repeated/],
  [j=>j.sides.left.electric={type:'ground'},/electric condition for the left side/],[j=>j.sides.top.thermal={type:'convection',h:-1,ambient:300},/top heat transfer coefficient/],
  [j=>j.iteration.relaxation_factor=0,/relaxation factor/],[j=>j.iteration.iteration_limit=J.MAX_ITERATIONS+1,/iteration limit/],[j=>j.iteration.iteration_limit=1.5,/iteration limit/],
  [j=>j.materials=[],/Define 1–6 materials/]])
  assert.throws(()=>J.validateJoule(inputs(change)),reason);
});
test('readiness: a potential, a temperature level and model ranges that hold every given temperature',()=>{
 const block=change=>J.jouleBlock(J.validateJoule(inputs(change)));
 assert.match(block(j=>{j.sides.left.electric={type:'insulating'};j.sides.right.electric={type:'current',current:1};}),/potential is undetermined/);
 assert.match(block(j=>{j.sides.left.thermal={type:'flux',flux:1};j.sides.right.thermal={type:'convection',h:0,ambient:300};}),/temperature level is undetermined/);
 assert.equal(block(j=>{j.sides.left.thermal={type:'insulated'};j.sides.right.thermal={type:'convection',h:5,ambient:300};}),'');
 assert.match(block(j=>j.iteration.initial_temperature=700),/initial temperature 700 K lies outside the valid range 250…600 K/);
 assert.match(block(j=>j.sides.right.thermal.temperature=200),/right temperature 200 K/);
 assert.match(block(j=>{j.materials[1].sigma.tmin=610;j.materials[1].sigma.tmax=700;j.materials[1].sigma.reference_temperature=650;}),/do not overlap/);
 assert.equal(block(j=>{for(const m of j.materials)m.sigma={model:'constant',value:1};j.iteration.initial_temperature=5000;}),'');
 assert.match(block(j=>j.sides.bottom.thermal={type:'temperature',temperature:310}),/left and bottom sides meet at a corner with two different fixed temperatures/);
 assert.match(block(j=>j.sides.top.electric={type:'potential',potential:0.1}),/left and top sides meet at a corner with two different fixed potentials/);
 assert.equal(block(j=>{j.sides.bottom.thermal={type:'temperature',temperature:300};j.sides.right.thermal={type:'insulated'};}),'');
 assert.match(J.jouleBlock(J.validateJoule(inputs(j=>j.shapes.push({name:'c',type:'circle',material:'A',cx:1,cy:0.5,r:0.1}))),{max_shapes:1}),/allows 1/);
});
test('projects of version 7 round-trip the Joule inputs; version 6 projects load with the defaults',()=>{
 const j=inputs(j=>{j.width=3;j.shapes[0].w=2;j.sides.top.thermal={type:'convection',h:12.5,ambient:290};});
 const doc=P.snapshot({...state,joule:j},setup);
 assert.equal(doc.version,7);assert.equal(doc.units.joule_length,'mm');
 const loaded=P.parseProject(JSON.stringify(doc));assert.deepEqual(loaded.model.joule,J.validateJoule(j));
 assert.deepEqual(P.parseProject(JSON.stringify(loaded)),loaded);
 const v6=clone(doc);v6.version=6;delete v6.units.joule_length;delete v6.model.joule;
 const read=P.parseProject(JSON.stringify(v6));assert.equal(read.version,7);assert.deepEqual(read.model.joule,J.validateJoule(J.DEFAULT_JOULE));
 assert.deepEqual(read.model.thermal,loaded.model.thermal);
 const bad=clone(doc);bad.model.joule.materials[0].k=-1;assert.throws(()=>P.parseProject(JSON.stringify(bad)),/thermal conductivity/);
});
test('sessions of version 7 keep the Joule inputs; version 6 sessions load',()=>{
 const input=P.snapshot({...state,joule:inputs(j=>j.elementSize=0.1)},setup);
 const session=N.createSession(input,[],null,[null,null]);assert.equal(session.version,7);
 assert.equal(N.parseSession(JSON.stringify(session)).input.model.joule.elementSize,0.1);
 const v6=clone(session);v6.version=6;v6.input.version=6;delete v6.input.units.joule_length;delete v6.input.model.joule;
 assert.deepEqual(N.parseSession(JSON.stringify(v6)).input.model.joule,J.validateJoule(J.DEFAULT_JOULE));
 for(const version of [5,8]){const s=clone(session);s.version=version;assert.throws(()=>N.parseSession(JSON.stringify(s)));}
});
const owner={job:'thermal-joule-'+'a'.repeat(32),result_id:'result-'+'a'.repeat(32),client_revision:2,request_seq:3};
function payload(change=()=>{}){
 const p={payload_format:J.PAYLOAD,kind:'joule.temperature2d',...owner,result_format:J.PAIRS['joule.temperature2d'][0],field_layout:J.PAIRS['joule.temperature2d'][1],
  length_unit:'mm',display_length_in_m:1e-3,
  summary:{region_names:['b','background'],iterations:[{iteration_count:1,temperature_change:{value:2,unit:'K'},relative_electrical_conductivity_change:{value:0.1,unit:'1'},maximum_temperature:{value:310,unit:'K'}}],
   balance:{inward_electric_power_per_depth:{value:16.67,unit:'W/m'},joule_power_per_depth:{value:16.67,unit:'W/m'},outward_heat_rate_per_depth:{value:16.67,unit:'W/m'},outward_current_per_depth:{left:{value:-83.3,unit:'A/m'},right:{value:83.3,unit:'A/m'}}}},
  arrays:{node_coordinates:[[0,0],[2e-3,0],[2e-3,1e-3],[0,1e-3]],triangles:[[0,1,2],[0,2,3]],triangle_regions:[1,0],
   electric_potential:[0.2,0,0,0.2],temperature:[300,320,320,300],current_density:[[3,4],[0,1]],heat_flux:[[1,0],[1,0]],joule_power_density:[25,1]}};
 change(p);return p;
}
test('result payloads are checked for ownership, pair and shapes before drawing',()=>{
 assert.equal(J.checkJoulePayload(payload(),owner,'joule.temperature2d').kind,'joule.temperature2d');
 for(const change of [p=>p.payload_format='studio-thermal-steady-regions-v2',p=>p.request_seq=9,p=>p.field_layout=J.PAIRS['joule.steady2d'][1],
  p=>p.arrays.temperature.pop(),p=>p.arrays.triangles[0][2]=4,p=>p.arrays.current_density[1]=[1],p=>p.arrays.triangle_regions[0]=2,
  p=>delete p.arrays.joule_power_density,p=>p.summary.iterations=null,p=>p.display_length_in_m=0])
  assert.throws(()=>J.checkJoulePayload(payload(change),owner,'joule.temperature2d'),/Joule result/);
 assert.throws(()=>J.checkJoulePayload(payload(),owner,'joule.steady2d'),/pair/);
});
test('the view model gives nodal T and V, cell |J| and power, region edges and display lengths',()=>{
 const p=payload(),t=J.jouleViewModel(p,'temperature'),c=J.jouleViewModel(p,'current_magnitude');
 assert.deepEqual(t.nodes[2],[2,1]);assert.equal(t.nodal,true);assert.deepEqual([t.min,t.max,t.unit],[300,320,'K']);
 assert.deepEqual(c.values,[5,1]);assert.equal(c.nodal,false);assert.deepEqual(c.flux,p.arrays.current_density);
 assert.deepEqual(J.jouleViewModel(p,'joule_power_density').values,[25,1]);assert.deepEqual(J.jouleViewModel(p,'heat_flux_magnitude').flux,p.arrays.heat_flux);
 assert.deepEqual(t.regions.edges,[[0,2]]);assert.throws(()=>J.jouleViewModel(p,'qx'));
 assert.deepEqual(J.balanceRows(p.summary).map(r=>r[0]),['Supplied electric power','Joule power','Outward heat','Current out of left','Current out of right']);
 assert.deepEqual(J.iterationRows(p.summary),[[1,2,0.1,310]]);
});
function fakeServer(states){
 const calls=[];const doc=J.jouleDocument(J.DEFAULT_JOULE);
 const request=async(method,url,body)=>{calls.push([method,url,body&&{...body,doc:undefined}]);
  if(url==='/api/joule/validate')return {ok:true,doc,client_revision:body.client_revision,request_seq:body.request_seq};
  if(url==='/api/joule/run')return {kind:'joule.temperature2d',job:owner.job,result_id:owner.result_id,client_revision:body.client_revision,request_seq:body.request_seq};
  if(url.endsWith('/result'))return payload(p=>{p.client_revision=calls[1][2].client_revision;p.request_seq=calls[1][2].request_seq;});
  const status=states.shift();return {job:owner.job,result_id:owner.result_id,...status};};
 return {request,calls,doc};
}
test('the run controller validates, runs, polls and returns a checked payload',async()=>{
 const server=fakeServer([{status:'running'},{status:'done'}]),seen=[];
 const runner=new J.JouleRunner({request:server.request,wait:async()=>{},onState:s=>seen.push(s.phase)});
 const result=await runner.calculate(server.doc);
 assert.equal(result.payload_format,J.PAYLOAD);assert.deepEqual(seen,['validating','running']);assert.equal(runner.busy,false);
 assert.deepEqual(server.calls.map(c=>c[1]),['/api/joule/validate','/api/joule/run','/api/jobs/'+owner.job,'/api/jobs/'+owner.job,'/api/jobs/'+owner.job+'/result']);
});
test('the run controller reports server refusals and job errors with their messages',async()=>{
 const failed=fakeServer([{status:'error',error:{code:'not_converged',message:'the Picard iteration did not converge after 1 iterations: maximum iterations exceeded'}}]);
 await assert.rejects(new J.JouleRunner({request:failed.request,wait:async()=>{}}).calculate(failed.doc),/did not converge after 1 iterations/);
 const refused={request:async()=>({ok:false,error:{message:'E-OUTSIDE-VALID at physics.j.initial_temperature'}})};
 await assert.rejects(new J.JouleRunner({request:refused.request,wait:async()=>{}}).calculate(J.jouleDocument(J.DEFAULT_JOULE)),/E-OUTSIDE-VALID/);
 const stale=fakeServer([{status:'running'}]);const runner=new J.JouleRunner({request:stale.request,wait:async()=>{runner.stop();}});
 assert.equal(await runner.calculate(stale.doc),null);
});
test('the capability check needs both kinds on the Joule routes',async()=>{
 const block=(extra={})=>({validate:'/api/joule/validate',run:'/api/joule/run',geometry:'regions',run_enabled:true,limits:{max_shapes:64,max_iterations:500},...extra});
 const runner=caps=>new J.JouleRunner({request:async()=>caps});
 assert.deepEqual(await runner({'joule.temperature2d':block(),'joule.steady2d':block()}).capability(),{run_enabled:true,limits:{max_shapes:64,max_iterations:500}});
 assert.equal((await runner({'joule.temperature2d':block({run_enabled:false}),'joule.steady2d':block()}).capability()).run_enabled,false);
 await assert.rejects(runner({'joule.temperature2d':block()}).capability(),/does not run Joule heating/);
});
