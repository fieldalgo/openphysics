// Copyright 2026 Yongha Kim (FieldAlgo); SPDX-License-Identifier: Apache-2.0
// The multiphysics model's pure functions (workspace-multiphysics.mjs): names, the envelope,
// port compatibility, couplings, diagnostics in words, the Connections layout, loops, progress
// and results. The cycle cases use test-local relay kinds; no installed kind forms a cycle.
const test=require('node:test');const assert=require('node:assert/strict');
const mp=import('../../packages/simcase/src/simcase/studio/static/workspace-multiphysics.mjs');
const out=(name,quantity,unit,location)=>({name,direction:'output',quantity,unit,location});
const inp=(name,quantity,unit,location,combine='single')=>({name,direction:'input',quantity,unit,location,combine});
// the built-in ports as /api/multiphysics/capabilities lists them, and test-local relays
const CAPS={providers:[{name:'openphysics-fem',version:'0',status:'available',error:null,types:[
 {type:'thermal.steady2d',label:'Heat transfer',field:'heat',addable:true,prefix:'heat',entry:{type:'thermal.steady2d',prescribed_temperature:{bottom:'300 K'}},ports:[out('temperature','temperature','K','node'),out('heat_flux','heat_flux','W/m^2','element')]},
 {type:'em.modes2d',label:'Optical modes',field:'electromagnetics',addable:true,prefix:'modes',entry:{type:'em.modes2d',vacuum_wavelength:'1550 nm',mode_count:1},ports:[out('effective_index','effective_index','1','scalar'),inp('temperature','temperature','K','element')]},
 {type:'joule.steady2d',label:'joule.steady2d',field:'electric',addable:false,reason:'solves its own coupling; start it from its template on the start page',ports:[out('joule_power_density','joule_power_density','W/m^3','element')]}]},
 {name:'broken',version:null,status:'unavailable',error:'ImportError: no module',types:[]},
 {name:'test-relays',version:'1',status:'available',error:null,types:[
 {type:'test.relay',label:'Relay',field:'heat',addable:true,prefix:'relay',entry:{type:'test.relay'},ports:[inp('x','temperature','K','node','sum'),out('y','temperature','K','node')]},
 {type:'test.relaymk',label:'Relay mK',field:'heat',addable:true,prefix:'mk',entry:{type:'test.relaymk'},ports:[inp('x','temperature','mK','node','sum'),out('y','temperature','mK','node')]},
 {type:'test.power',label:'Power',field:'heat',addable:true,prefix:'power',entry:{type:'test.power'},ports:[out('q','heat_source_density','W/m^3','element')]}]}]};
const heated=()=>({openphysics:'0.3/multiphysics.1',name:'Heated silicon waveguide',geometry:{version:1,components:{xs:{dimension:'2d',length_unit:'um',depth:null,domain:{xmin:-3,xmax:3,ymin:-2,ymax:2.5},background:{material:'physmat:SiO2'},
 features:[{name:'core',type:'rect',x:-0.25,y:0,w:0.5,h:0.22,material:'physmat:Si'},{name:'heater',type:'rect',x:-1,y:1.32,w:2,h:0.1,material:'heater'}]}}},
 materials:{heater:{refractive_index:1.5,thermal_conductivity:'100 W/(m K)',thermo_optic_coefficient:'0 1/K',reference_temperature:'300 K'}},
 physics:{heat1:{type:'thermal.steady2d',prescribed_temperature:{bottom:'300 K'}},modes1:{type:'em.modes2d',vacuum_wavelength:'1550 nm',mode_count:1}},
 couplings:{heat1_to_modes1:{from:'heat1.temperature',to:'modes1.temperature',transfer:'same_mesh'}},mesh:{element_size:'0.25 um'}});
const relays=(couplings,loops)=>({openphysics:'0.3/multiphysics.1',physics:{a:{type:'test.relay'},b:{type:'test.relay'},c:{type:'test.relay'}},couplings,...(loops?{study:{type:'single',loops}}:{})});
const cycleProposal={physics:['a','b'],method:'fixed_point',tolerance:{port:'a.y',norm:'max_abs',value:'1e-6 K'},max_iterations:30,relaxation:0.5};

test('physics and couplings are named in words; the file names stay in the file',async()=>{
 const m=await mp;
 assert.equal(m.physicsLabel('heat1'),'Heat 1');assert.equal(m.physicsLabel('modes12'),'Modes 12');assert.equal(m.physicsLabel('heat_2'),'Heat 2');assert.equal(m.physicsLabel('a'),'a');
 assert.equal(m.couplingTitle(heated(),'heat1_to_modes1'),'Heat 1 temperature → Modes 1 temperature');
 assert.equal(m.quantityWords('joule_power_density'),'Joule heat');assert.equal(m.unitText('W/m^3'),'W/m³');
 assert.deepEqual(m.materialUses(heated()).map(u=>u.label),['Silicon (core)','Heater','Silica (background)']);
});
test('the envelope follows the couplings and kinds: one physics is format 0.3, a second makes it multiphysics',async()=>{
 const m=await mp,c=m.kindCatalog(CAPS);
 const one=m.removePhysics(m.removeCoupling(heated(),'heat1_to_modes1'),'heat1');
 assert.equal(one.openphysics,'0.3');assert.equal(one.couplings,undefined);
 const added=m.addPhysics(one,c.types.get('thermal.steady2d'));
 assert.equal(added.name,'heat1');assert.equal(added.becameMultiphysics,true);assert.equal(added.doc.openphysics,'0.3/multiphysics.1');
 assert.equal(m.addPhysics(added.doc,c.types.get('thermal.steady2d')).name,'heat2');
 assert.throws(()=>m.addPhysics(one,c.types.get('joule.steady2d')),/solves its own coupling/);
 // another format is kept as written, so the check refuses it by name; an opened file is not normalized
 assert.equal(m.normalizeEnvelope({...heated(),openphysics:'0.2'}).openphysics,'0.2');
 assert.equal(m.normalizeEnvelope({openphysics:'9',physics:{a:{type:'em.modes2d'}}}).openphysics,'9');
 // two physics of one kind and no coupling: one spelling, format 0.3
 const twoHeat=m.addPhysics(m.removePhysics(added.doc,'modes1'),c.types.get('thermal.steady2d')).doc;
 assert.equal(twoHeat.openphysics,'0.3');
 // a removed physics leaves its coupling for the check to show
 assert.deepEqual(Object.keys(m.removePhysics(heated(),'heat1').couplings),['heat1_to_modes1']);
});
test('the port pickers offer outputs, then only compatible inputs, and say why the others are greyed',async()=>{
 const m=await mp,c=m.kindCatalog(CAPS);
 const doc={...heated(),physics:{...heated().physics,heat2:{type:'thermal.steady2d'},mk1:{type:'test.relaymk'},power1:{type:'test.power'},relay1:{type:'test.relay'}}};
 const sources=m.sourceChoices(doc,c);
 assert.deepEqual(sources.filter(s=>!s.ok).map(s=>[s.spec,s.reason,s.detail]),[['modes1.effective_index','single numbers, not a map','Modes 1 effective index is one value per mode, not a field on the mesh']]);
 // heat flux is listed; no input of this model takes it, and each says why
 assert.ok(m.targetChoices(doc,c,'heat1.heat_flux').every(t=>!t.ok&&t.reason));
 assert.equal(m.pairProblem(doc,c,'heat1.heat_flux','modes1.temperature'),'temperature is not a heat flux');
 const reasons=Object.fromEntries(m.targetChoices(doc,c,'heat2.temperature').map(t=>[t.spec,t.reason]));
 assert.equal(reasons['modes1.temperature'],'Already receives Heat 1 temperature; this input takes one source.');
 assert.equal(reasons['mk1.x'],'unit K, this input expects mK');
 assert.equal(reasons['relay1.x'],null);
 assert.equal(m.pairProblem(doc,c,'relay1.y','relay1.x'),'a physics cannot feed itself');
 assert.equal(m.pairProblem(doc,c,'power1.q','relay1.x'),'temperature is not a heat source density');
 assert.equal(m.pairProblem(doc,c,'power1.q','modes1.temperature'),'temperature is not a heat source density');
 assert.match(m.transferNote(doc,c,'heat1.temperature','modes1.temperature'),/^Same mesh \(both use Mesh 1\) · each triangle gets the mean of its 3 nodes$/);
});
test('Add coupling writes one entry named <from>_to_<to> and refuses an incompatible pair; the obvious coupling is suggested, not added',async()=>{
 const m=await mp,c=m.kindCatalog(CAPS),bare=m.removeCoupling(heated(),'heat1_to_modes1');
 assert.equal(bare.openphysics,'0.3/multiphysics.1');      // two kinds stay multiphysics
 assert.deepEqual(m.suggestedCouplings(bare,c),[{from:'heat1.temperature',to:'modes1.temperature'}]);
 assert.equal(m.suggestionText(m.suggestedCouplings(bare,c)[0]),'Modes 1 can take its temperature from Heat 1. Connect Heat 1 temperature to Modes 1 temperature so the refractive index follows the heater.');
 const {doc,name}=m.addCoupling(bare,c,'heat1.temperature','modes1.temperature');
 assert.equal(name,'heat1_to_modes1');assert.deepEqual(doc.couplings[name],{from:'heat1.temperature',to:'modes1.temperature',transfer:'same_mesh'});
 assert.deepEqual(m.suggestedCouplings(doc,c),[]);
 assert.throws(()=>m.addCoupling(doc,c,'heat1.temperature','modes1.temperature'),/one source/);
 const two=relays({});assert.equal(m.addCoupling(m.addCoupling(two,c,'a.y','b.x').doc,c,'a.y','b.x').name,'a_to_b_2');
});
test('engine diagnostics become the messages of the design, at the node where they are fixed',async()=>{
 const m=await mp,c=m.kindCatalog(CAPS);
 const d=(code,path,message,suggestions=[])=>({code,severity:'error',path,message,suggestions});
 const base=heated();
 const cases=[
  [{...base,couplings:{x:{from:'heat9.temperature',to:'modes1.temperature',transfer:'same_mesh'}}},d('E-CONTRACT','couplings.x.from','"heat9.temperature" names the physics \'heat9\', which this document does not have; physics here: heat1, modes1'),
   'coupling:x','Coupling x names a physics “heat9” that is not in this model. Choose one of Heat 1 and Modes 1, or remove the coupling.','remove-coupling'],
  [{...base,couplings:{x:{from:'heat1.temp',to:'modes1.temperature',transfer:'same_mesh'}}},d('E-CONTRACT','couplings.x.from','heat1 (thermal.steady2d) has no port \'temp\'; its output ports: temperature, heat_flux'),
   'coupling:x','Coupling x: Heat 1 has no output “temp”. Its outputs are temperature and heat flux. Choose one, or remove the coupling.','remove-coupling'],
  [{...base,couplings:{x:{from:'heat1.heat_flux',to:'modes1.temperature',transfer:'same_mesh'}}},d('E-CONTRACT','couplings.x.from','heat1.heat_flux is an output thermal.steady2d saves but does not couple in this release; its coupled outputs: temperature'),
   'coupling:x','Coupling Heat 1 heat flux → Modes 1 temperature: Heat 1 does not send heat flux to couplings in this release. Its coupled outputs are temperature. Choose one, or remove the coupling.','remove-coupling'],
  [{...base,couplings:{x:{...base.couplings.heat1_to_modes1,transfer:'nearest'}}},d('E-CONTRACT','couplings.x.transfer','"nearest" is not a transfer this release reads; write "same_mesh" (the identity on one mesh)'),
   'coupling:x','Coupling x uses transfer “nearest”, which this release does not have. Use “Same mesh”: both physics use Mesh 1.','use-same-mesh'],
  [{...base,mesh:{...base.mesh,grading:{}}},d('E-CONTRACT','couplings.heat1_to_modes1.transfer','same_mesh needs one mesh, but heat1 does not read mesh.grading, which modes1 reads, so heat1 and modes1 would build different meshes; remove mesh.grading (grade the mesh with mesh.controls, which every physics reads)'),
   'mesh','Heat 1 and Modes 1 would build different meshes: mesh grading is read only by Modes 1. Remove mesh grading so both use the same mesh.','remove-mesh-key'],
  [{...base,physics:{...base.physics,heat2:{type:'thermal.steady2d'}},couplings:{...base.couplings,heat2_to_modes1:{from:'heat2.temperature',to:'modes1.temperature',transfer:'same_mesh'}}},d('E-CONTRACT','couplings.heat2_to_modes1.to','modes1.temperature takes one coupling (combine "single"); heat1_to_modes1 already couples into it'),
   'physics:modes1','Modes 1 temperature takes one source but receives two: from Heat 1 and from Heat 2. Remove one of the couplings.',null],
  [relays({x:{from:'a.y',to:'a.x',transfer:'same_mesh'}}),d('E-CONTRACT','couplings.x','couples a to itself; a coupling carries a field from one physics to another'),
   'coupling:x','Coupling x connects a to itself. A physics cannot feed its own input; remove this coupling.','remove-coupling'],
  [{...relays({}),physics:{a:{type:'test.relay'},m:{type:'test.relaymk'}},couplings:{x:{from:'a.y',to:'m.x',transfer:'same_mesh'}}},d('E-COUPLING-PAIR','couplings.x','a.y is in \'K\' and m.x in \'mK\'; a coupling does not convert units, so the two ports give the same unit string'),
   'coupling:x','Coupling a y → m x: units differ. a sends temperature in K; m expects mK. Couplings do not convert units. Connect a temperature output in mK, or remove this coupling.','remove-coupling'],
  [{...relays({}),physics:{p:{type:'test.power'},a:{type:'test.relay'}},couplings:{x:{from:'p.q',to:'a.x',transfer:'same_mesh'}}},d('E-COUPLING-PAIR','couplings.x','p.q carries heat_source_density and a.x takes temperature; the two ports of a coupling carry the same quantity'),
   'coupling:x','Coupling p q → a x: p sends heat source density, but a x takes temperature. Connect an output that sends temperature, or remove this coupling.','remove-coupling'],
  [{...base,materials:{heater:{refractive_index:1.5,thermal_conductivity:'100 W/(m K)'}}},d('E-PROPERTY-MISSING','materials.heater','physics.modes1 takes a coupled temperature, so each optical material needs a thermo-optic model; materials.heater has none'),
   'material:heater','Heater has no thermo-optic data, but Modes 1 takes its temperature from Heat 1, so every optical material needs a thermo-optic coefficient (1/K) and a reference temperature (K). Add them in Materials > Heater.','fill-physmat'],
  [relays({ab:{from:'a.y',to:'b.x',transfer:'same_mesh'},ba:{from:'b.y',to:'a.x',transfer:'same_mesh'}}),d('E-COUPLING-CYCLE','study.loops','a and b form a cycle …',[{value:cycleProposal}]),
   'study','a and b depend on each other. b needs the temperature from a, and a needs the temperature from b. Solve them together with an iteration step: fixed point, stop when a y changes by at most 1e-6 K, up to 30 iterations, relaxation 0.5.','accept-loop'],
 ];
 for(const [doc,diag,node,text,fix] of cases){
  const [message]=m.mapDiagnostics(doc,c,[diag]);
  assert.equal(message.node,node,text);assert.equal(message.text,text);assert.equal(message.fix?.action??null,fix,text);
  assert.equal(message.code,diag.code);assert.equal(message.detail,diag.message);       // the engine's words stay under Details
  assert.doesNotMatch(message.text,/E-[A-Z]|same_mesh|couplings\.[a-z]/);
 }
 // infos are not problems; a repeated diagnostic is shown once; counts land on the node and its group
 const shown=m.mapDiagnostics(base,c,[{code:'I-DEFAULT-BOUNDARY',severity:'info',path:'physics.heat1.inward_heat_flux.left',message:'x'},cases[9][1],cases[9][1]]);
 assert.equal(shown.length,1);assert.deepEqual(m.problemCounts(shown),{'material:heater':1,materials:1});
 assert.equal(m.runBlockText(1,null),'Fix 1 problem in Messages to run');assert.equal(m.runBlockText(3,null),'Fix 3 problems in Messages to run');assert.equal(m.runBlockText(0,null),'');
});
test('the one-click fixes write what the design says: Accept iteration step, Fill from physmat, Use physmat',async()=>{
 const m=await mp,doc=relays({ab:{from:'a.y',to:'b.x',transfer:'same_mesh'},ba:{from:'b.y',to:'a.x',transfer:'same_mesh'}});
 const {doc:next,index}=m.acceptLoop(doc,cycleProposal);
 assert.equal(index,0);assert.deepEqual(next.study,{type:'single',loops:[cycleProposal]});assert.equal(m.loopIndexOf(next,['b','a']),0);
 // accepting twice (a double click on a stale message) adds nothing
 const again=m.acceptLoop(next,cycleProposal);assert.equal(again.already,true);assert.equal(again.doc.study.loops.length,1);
 assert.deepEqual(m.removeLoop(next,0).study,{type:'single'});
 const bare={...heated(),materials:{heater:{refractive_index:1.5,thermal_conductivity:'100 W/(m K)',source:'mine'}}};
 const filled=m.fillThermoOptic(bare,'heater');
 assert.deepEqual(filled.materials.heater,{refractive_index:1.5,thermal_conductivity:'100 W/(m K)',thermo_optic_coefficient:'1.0e-5 1/K',reference_temperature:'300 K',source:'mine; thermo-optic data copied from physmat:SiO2 (physmat)'});
 assert.equal(m.physmatFor({refractive_index:3.48}),'physmat:Si');assert.equal(m.fillText('physmat:Si'),'Fill from physmat:Si (1.8e-4 1/K at 300 K)');
 const swapped=m.usePhysmat(bare,'heater','physmat:SiO2');assert.equal(swapped.geometry.components.xs.features[1].material,'physmat:SiO2');
});
test('the Connections layout puts physics in solve-order columns, boxes cycles and keeps invalid couplings on screen',async()=>{
 const m=await mp,c=m.kindCatalog(CAPS);
 const layout=m.connectionLayout(heated(),c,[['heat1'],['modes1']]);
 assert.deepEqual(layout.nodes.map(n=>[n.name,n.column,n.badge]),[['heat1',0,1],['modes1',1,2]]);
 assert.deepEqual(layout.wires.map(w=>[w.from,w.to,w.color,w.invalid,w.route]),[['heat1--output--temperature','modes1--input--temperature','temperature',false,'curve']]);
 // a cycle without its loop: one column, amber; with its loop: blue and labelled with the step
 const cyc=relays({ab:{from:'a.y',to:'b.x',transfer:'same_mesh'},ba:{from:'b.y',to:'a.x',transfer:'same_mesh'}});
 const open=m.connectionLayout(cyc,c,[['a','b'],['c']]);
 assert.deepEqual(open.boxes,[{members:['a','b'],column:0,accepted:false,loop:-1,label:'Cycle: a and b need an iteration step'}]);
 assert.deepEqual(open.nodes.filter(n=>n.cycle).map(n=>n.badge),[1,1]);
 assert.equal(open.wires.find(w=>w.coupling==='ba').route,'below');
 const accepted=m.connectionLayout(m.acceptLoop(cyc,cycleProposal).doc,c,[['a','b'],['c']]);
 assert.equal(accepted.boxes[0].label,'Iteration step 1 · fixed point · up to 30 · relaxation 0.5');assert.equal(accepted.boxes[0].accepted,true);
 // an invalid coupling is drawn red with its short cause, onto a pin that is not a port; one naming a missing physics is listed
 const bad={...heated(),couplings:{x:{from:'heat1.temp',to:'modes1.temperature',transfer:'same_mesh'},y:{from:'heat9.temperature',to:'modes1.temperature',transfer:'same_mesh'}}};
 const messages=m.mapDiagnostics(bad,c,[{code:'E-CONTRACT',severity:'error',path:'couplings.x.from',message:'no port'},{code:'E-CONTRACT',severity:'error',path:'couplings.y.from',message:'no physics'}]);
 const drawn=m.connectionLayout(bad,c,[['heat1'],['modes1']],messages);
 assert.deepEqual(drawn.wires.map(w=>[w.coupling,w.invalid,w.cause]),[['x',true,'no output temp']]);
 assert.deepEqual(drawn.dangling.map(d=>[d.coupling,d.cause]),[['y','unknown physics']]);
 assert.ok(drawn.nodes[0].pins.find(p=>p.name==='temp'&&p.missing));
 const html=m.renderMultiphysicsGraph(drawn,'coupling:x');
 const ports=[...html.matchAll(/data-port="([^"]+)"/g)].map(x=>x[1]);
 for(const w of drawn.wires){assert.ok(ports.includes(w.from));assert.ok(ports.includes(w.to));}
 assert.match(html,/temperature invalid/);assert.match(html,/data-mark-for="x"/);assert.match(html,/mp-dangling/);
 assert.match(m.renderMultiphysicsGraph(open,null),/mp-cycle open/);assert.match(m.renderMultiphysicsGraph(accepted,null),/mp-cycle accepted/);
 assert.match(m.renderMultiphysicsGraph(layout,null,{heat1:{state:'done',text:'Done in 0.3 s'}}),/mp-state done">Done in 0.3 s/);
 // names are escaped
 assert.doesNotMatch(m.renderMultiphysicsGraph(m.connectionLayout({...heated(),physics:{'<b>':{type:'em.modes2d'}}},c,[]),null),/<b>/);
});
test('progress rows follow the engine events: done, solving, iterations, did not settle, not run',async()=>{
 const m=await mp,doc=heated();
 const ev=[{event:'physics_started',physics:'heat1'},{event:'physics_finished',physics:'heat1',seconds:1.234},{event:'physics_started',physics:'modes1'}];
 assert.deepEqual(m.progressRows([['heat1'],['modes1']],doc,ev,'running').map(r=>[r.label,r.state,r.text]),[['Heat 1','done','Done in 1.2 s'],['Modes 1','solving','Solving…']]);
 assert.deepEqual(m.progressRows([['heat1'],['modes1']],doc,ev.slice(0,2),'running').map(r=>r.state),['done','waiting']);
 assert.deepEqual(m.progressRows([['heat1'],['modes1']],doc,ev,'error',{message:'x',physics:'modes1'}).map(r=>r.state),['done','failed']);
 assert.deepEqual(m.progressRows([['heat1'],['modes1']],doc,ev.slice(0,2),'stopped').map(r=>r.text),['Done in 1.2 s','Not run']);
 const cyc=m.acceptLoop(relays({ab:{from:'a.y',to:'b.x',transfer:'same_mesh'},ba:{from:'b.y',to:'a.x',transfer:'same_mesh'}}),cycleProposal).doc;
 const loopEv=[{event:'loop_started',physics:['a','b']},{event:'loop_iteration',physics:['a','b'],iteration:7,residual:3.1e-4,unit:'K'}];
 const running=m.progressRows([['a','b'],['c']],cyc,loopEv,'running');
 assert.equal(running[0].label,'Iteration step 1 · a ⇄ b');assert.equal(running[0].text,'Iteration 7 of up to 30 · max |Δ| 3.1e-4 K');assert.equal(running[0].residuals.length,1);
 const failed=m.progressRows([['a','b'],['c']],cyc,loopEv,'error',{code:'E-LOOP-DIVERGED',physics:['a','b'],residuals:[0.84],unit:'K'});
 assert.deepEqual(failed.map(r=>[r.state,r.text]),[['did-not-settle','Did not settle in 30 iterations'],['not-run','Not run']]);
 assert.equal(m.failureText({code:'E-LOOP-DIVERGED',physics:['a','b'],residuals:[1,0.84],unit:'K'},cyc),'a ⇄ b did not settle in 30 iterations. The largest change in the last iteration was 0.84 K (target 1e-6 K). No results were kept, because the last iteration is not a solution. Lower the relaxation (for example 0.3) or raise the iteration limit, then run again.');
 assert.equal(m.formatValue(0),'0');assert.equal(m.formatValue(3.1e-4),'3.1e-4');
 assert.equal(m.failureText({message:'boom',physics:'modes1'},doc),'Modes 1 failed, so the run kept no result: boom');
 assert.equal(m.progressRows([['a','b']],cyc,[...loopEv,{event:'loop_finished',physics:['a','b'],iterations:9}],'done')[0].text,'Settled in 9 iterations');
});
test('results: the coupling check in words, the n_eff rows, the uncoupled document',async()=>{
 const m=await mp,doc=heated();
 // two triangles: one in the core (physmat:Si), one in the heater (dn/dT 0)
 const result={solve_order:[['heat1'],['modes1']],mesh:{node_coordinates:[[0,0],[1,0],[0,1],[1,1]],triangles:[[0,1,2],[1,3,2]],regions:[0,1],region_names:['core','heater','background']},
  couplings:{heat1_to_modes1:{from:'heat1.temperature',to:'modes1.temperature',quantity:'temperature',unit:'K',transfer:'same_mesh',location:'node',mesh_signature:'match',max_abs_difference:{value:0,unit:'K'},conservation_residual:null}},
  physics:{heat1:{type:'thermal.steady2d',temperature:{values:[300,301,302,303.5]}},modes1:{type:'em.modes2d',effective_index:{unit:'1',values:[[2.6,2.1]]},coupled:{temperature:{values:[301,302]},refractive_index:{n:[3.48018,1.5],k:null}}}}};
 assert.deepEqual(m.couplingCheckRows(result,doc),[{name:'heat1_to_modes1',title:'Heat 1 temperature → Modes 1 temperature',from:'heat1.temperature',to:'modes1.temperature',
  sent:'4 node temperatures, 300.0–303.5 K',received:'2 triangle means (mean of 3 nodes)',check:'Passed · max |received − sent| = 0 K · same mesh: node values arrived unchanged',passed:true}]);
 const failed=structuredClone(result);failed.couplings.heat1_to_modes1.max_abs_difference.value=1e-9;assert.equal(m.couplingCheckRows(failed,doc)[0].passed,false);
 const power=structuredClone(result);power.couplings.heat1_to_modes1.conservation_residual=2e-16;assert.match(m.couplingCheckRows(power,doc)[0].check,/conservation \|Σ sent − Σ received\| \/ \|Σ sent\| = 2\.0e-16/);
 assert.deepEqual(m.effectiveIndexRows(result.physics.modes1),[{point:0,mode:1,value:2.6},{point:0,mode:2,value:2.1}]);
 assert.deepEqual(m.resultPages(result).map(p=>p.label),['Heat 1','Modes 1','Coupling check']);
 const alone=m.uncoupledDocument(doc,'modes1');
 assert.equal(alone.openphysics,'0.3');assert.deepEqual(Object.keys(alone.physics),['modes1']);assert.equal(alone.couplings,undefined);
 assert.equal(alone.materials.heater.thermo_optic_coefficient,undefined);assert.equal(alone.name,'Heated silicon waveguide · Modes 1 alone');
 assert.deepEqual(alone.mesh,doc.mesh);assert.deepEqual(alone.geometry,doc.geometry);
});
test('the catalog keeps unavailable providers and greys kinds Studio does not add',async()=>{
 const m=await mp,c=m.kindCatalog(CAPS);
 assert.deepEqual(c.providers.map(p=>[p.name,p.status]),[['openphysics-fem','available'],['broken','unavailable'],['test-relays','available']]);
 assert.equal(c.types.get('joule.steady2d').addable,false);assert.equal(c.types.get('em.modes2d').provider,'openphysics-fem');
});
test('a model edit leaves the last run out of date; the same content again is current',async()=>{
 const m=await mp;
 assert.equal(m.runFreshness(null,heated()),'none');
 const run={doc:heated()};assert.equal(m.runFreshness(run,heated()),'current');
 const removed=m.removeCoupling(heated(),'heat1_to_modes1');
 assert.equal(m.runFreshness(run,removed),'stale');
 // the coupling added back: other key order, same content
 const back={...removed,couplings:{heat1_to_modes1:{transfer:'same_mesh',to:'modes1.temperature',from:'heat1.temperature'}}};
 assert.notEqual(JSON.stringify(back),JSON.stringify(heated()));
 assert.equal(m.runFreshness(run,back),'current');
 assert.deepEqual(m.staleRows([{label:'Heat 1',state:'done',text:'Done in 0.5 s'}]),[{label:'Heat 1',state:'stale',text:'Out of date (last run: Done in 0.5 s)'}]);
 assert.equal(m.sequenceHeading('none'),'Nothing is computed until you press Run');
 assert.equal(m.sequenceHeading('stale',2),'Run 2 · the model changed since; press Run to update');
 assert.equal(m.sequenceHeading('current',2),'Run 2 · solved from the current model');
 assert.equal(m.readyStatus('none'),'Model checked · press Run');
 assert.equal(m.readyStatus('stale',1),'Model edited since run 1 · press Run to update');
 assert.equal(m.readyStatus('current',1),'Run 1 matches the model · press Run to solve again');
 assert.equal(m.canonicalJson({b:[{d:1,c:2}],a:null}),'{"a":null,"b":[{"c":2,"d":1}]}');
});
test('the heater-off column is valid by the content of the optical model it solved, not by run order',async()=>{
 const m=await mp,key=m.baselineKey(heated(),'modes1');
 const removed=m.removeCoupling(heated(),'heat1_to_modes1'),back=m.addCoupling(removed,m.kindCatalog(CAPS),'heat1.temperature','modes1.temperature').doc;
 assert.equal(m.baselineKey(back,'modes1'),key);
 // the heat physics and the thermo-optic data are not part of the optical model solved alone
 const hotter=heated();hotter.physics.heat1.prescribed_temperature.bottom='310 K';hotter.materials.heater.thermo_optic_coefficient='1e-5 1/K';
 assert.equal(m.baselineKey(hotter,'modes1'),key);
 const other=heated();other.physics.modes1.vacuum_wavelength='1310 nm';
 assert.notEqual(m.baselineKey(other,'modes1'),key);
 assert.deepEqual(m.baselinePhysics(heated()),['modes1']);assert.deepEqual(m.baselinePhysics(removed),[]);
});
test('Δn_eff is signed in the 8-decimal format of n_eff; the baseline says what the engine solves',async()=>{
 const m=await mp;
 assert.equal(m.shiftText(2.44565013,2.44349927),'+0.00215086');
 assert.equal(m.shiftText(2.44349927,2.44565013),'−0.00215086');
 assert.equal(m.shiftText(1.5,1.5),'+0.00000000');assert.equal(m.shiftText(1,undefined),'—');
 assert.equal(m.sharedReferenceTemperature(heated()),300);
 assert.equal(m.baselineText(heated(),'modes1'),'without heater = Modes 1 alone with no temperature input: every material keeps n₀, its index at T_ref = 300 K.');
 const mixed=heated();mixed.materials.heater.reference_temperature='293 K';
 assert.equal(m.sharedReferenceTemperature(mixed),null);
 assert.equal(m.baselineText(mixed,'modes1'),'without heater = Modes 1 alone with no temperature input: every material keeps its index n₀.');
});
test('an optical temperature input with no source while a heat physics could give one is a warning',async()=>{
 const m=await mp,c=m.kindCatalog(CAPS);
 assert.deepEqual(m.unsourcedInputs(heated(),c),[]);
 const removed=m.removeCoupling(heated(),'heat1_to_modes1');
 assert.deepEqual(m.unsourcedInputs(removed,c).map(w=>[w.physics,w.text]),[['modes1','Temperature input has no source: uses n₀ at T_ref (300 K)']]);
 // the optical model alone has nothing that could give it: no warning
 assert.deepEqual(m.unsourcedInputs(m.removePhysics(removed,'heat1'),c),[]);
 assert.equal(m.unitText('um'),'µm');assert.equal(m.unitText('W/(m^2 K)'),'W/(m² K)');
});
test('each wire is anchored on the ports its coupling joins; every port has its own row',async()=>{
 const m=await mp,c=m.kindCatalog(CAPS);
 const layout=m.connectionLayout(heated(),c,[['heat1'],['modes1']]),html=m.renderMultiphysicsGraph(layout,null);
 // the two outputs of Heat 1 are separate rows of a one-column port list, temperature first
 const heatNode=html.slice(html.indexOf('data-mp-node="heat1"'),html.indexOf('data-mp-node="modes1"'));
 assert.match(heatNode,/<div class="graph-ports mp-ports">/);
 assert.deepEqual([...heatNode.matchAll(/data-port="([^"]+)"/g)].map(x=>x[1]),['heat1--output--temperature','heat1--output--heat_flux']);
 // the drawn ends come from the coupled ports' positions, never a neighbouring port's
 const edges=JSON.parse(html.match(/data-edges='([^']+)'/)[1].replace(/&quot;/g,'"').replace(/&#39;/g,"'").replace(/&amp;/g,'&'));
 const at={'heat1--output--temperature':{x:230,y:60},'heat1--output--heat_flux':{x:230,y:100},'modes1--input--temperature':{x:326,y:60}};
 assert.deepEqual(m.wireEnds(edges,id=>at[id]||null),[{coupling:'heat1_to_modes1',route:'curve',from:{x:230,y:60},to:{x:326,y:60}}]);
 // a port that is not drawn gives no wire rather than one from somewhere else
 assert.deepEqual(m.wireEnds(edges,id=>id==='modes1--input--temperature'?null:at[id]),[null]);
});
test('the model back at the last run says so in one sentence everywhere, without asking for a Run',async()=>{
 const m=await mp;
 assert.equal(m.freshnessAgain('current',false),'current');assert.equal(m.freshnessAgain('current',true),'again');assert.equal(m.freshnessAgain('stale',true),'stale');
 const again='Model matches run 1 again: its results are current. Run makes a new run with the same inputs';
 assert.equal(m.sequenceHeading('again',1),again);assert.equal(m.readyStatus('again',1),again);
 assert.equal(m.editNotice('Coupling Heat 1 temperature → Modes 1 temperature added.','again',1),'Coupling Heat 1 temperature → Modes 1 temperature added. '+again+'.');
 assert.equal(m.editNotice('Value updated.','stale',1),'Value updated. Press Run to compute the new model.');
 assert.equal(m.editNotice('Value updated.','none'),'Value updated. Press Run to compute the new model.');
});
test('the heater-off option stays in the toolbar: disabled with its reason while no temperature coupling exists',async()=>{
 const m=await mp;
 const off=m.baselineOptionState(m.removeCoupling(heated(),'heat1_to_modes1'),{on:true});
 assert.equal(off.available,false);assert.equal(off.disabled,true);assert.equal(off.checked,false);assert.equal(off.reason,'needs a temperature coupling');
 assert.match(off.title,/^Needs a temperature coupling/);
 const on=m.baselineOptionState(heated(),{on:true});
 assert.deepEqual([on.available,on.disabled,on.checked,on.reason],[true,false,true,'']);
 assert.equal(on.title,'After the coupled run, also solve Modes 1 alone with no temperature input (about 1 s), for the n_eff without heater');
 assert.equal(m.baselineOptionState(heated(),{on:true,busy:true}).disabled,true);
 assert.equal(m.baselineOptionState(heated(),{on:false}).checked,false);
});
test('the graphics footer names the geometry unit',async()=>{
 const m=await mp;
 assert.equal(m.lengthsNote(heated()),'Lengths in µm; other values carry their units. Run solves every physics in solve order.');
 assert.match(m.lengthsNote({physics:{}}),/^Lengths in the geometry’s unit \(not set\);/);
});
test('a modes table names candidates with the optical caveat and the mode count it asks for',async()=>{
 const m=await mp;
 assert.equal(m.CANDIDATE_CAVEAT,'Candidates are ranked by effective index and are not matched between designs.');
 assert.equal(m.modeCountText(heated(),'modes1'),'This model asks for 1 mode: Modes 1 › Modes to find');
 const three=heated();three.physics.modes1={...three.physics.modes1,mode_count:3};
 assert.equal(m.modeCountText(three,'modes1'),'This model asks for 3 modes: Modes 1 › Modes to find');
 const unset=heated();delete unset.physics.modes1.mode_count;
 assert.equal(m.modeCountText(unset,'modes1'),'The number of modes is set in Modes 1 › Modes to find');
 // after an edit the note gives the run's count, not the model's
 assert.equal(m.modeCountText(heated(),'modes1',{past:true}),'This run asked for 1 mode: Modes 1 › Modes to find');
});
test('the Messages line says when the without-heater option returns ticked',async()=>{
 const m=await mp,doc=heated(),removed={...doc,couplings:{}};
 assert.equal(m.baselineReturnText(removed,doc,true),' “Also solve without heater” is ticked again.');
 // not chosen, or not coming back from unavailable: nothing to say
 assert.equal(m.baselineReturnText(removed,doc,false),'');
 assert.equal(m.baselineReturnText(doc,doc,true),'');
 assert.equal(m.baselineReturnText(doc,removed,true),'');
});
test('a run read from a file or recovered says where it came from in the heading, footer and step rows',async()=>{
 const m=await mp;
 assert.equal(m.sequenceHeading('current',2,'imported'),'Run 2 · read from file, not recomputed');
 assert.equal(m.sequenceHeading('current',2,'recovered'),'Run 2 · recovered from this browser, not recomputed');
 assert.equal(m.readyStatus('current',2,'imported'),'Run 2 · read from file, not recomputed · press Run to compute it here');
 assert.equal(m.sequenceHeading('current',2,'local'),'Run 2 · solved from the current model');
 assert.equal(m.sequenceHeading('stale',2,'imported'),'Run 2 · the model changed since; press Run to update');
 assert.equal(m.sequenceHeading('again',2,'imported'),m.matchesAgainText(2));
 const rows=[{label:'Heat 1',state:'done',text:'Done in 0.2 s'},{label:'Modes 1',state:'done',text:'Done in 0.9 s'}];
 assert.deepEqual(m.originRows(rows,'imported').map(r=>r.text),['From file','From file']);
 assert.deepEqual(m.originRows(rows,'recovered').map(r=>r.text),['From this browser','From this browser']);
 assert.deepEqual(m.originRows(rows,'local'),rows);
 assert.deepEqual(m.staleRows(m.originRows(rows,'imported')).map(r=>r.text),['Out of date (last run: From file)','Out of date (last run: From file)']);
});
