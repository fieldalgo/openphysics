// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
// Keeping more runs: Recompute Run N's fields (section 4.4). Pre-registered: K9 (the words of 4.3
// and 4.4, exactly), K12 (a stored value perturbed by 1e-9 relative, as if from another build: nothing
// attached, the run's bytes unchanged, the refusal sentence with the mode and both values) and the
// recompute part of K6 (a recompute never takes a number or makes a run: studio_run_retention_fields.cjs
// runs the seeded sequence with recomputes). K5 (the engine's recomputed fields of the T18 and T16
// runs) is measured by tools/studio_run_retention.mjs k5.
const test=require('node:test');const assert=require('node:assert/strict');
const fs=require('node:fs');const path=require('node:path');
const STATIC='../../packages/simcase/src/simcase/studio/static/';
const FIX=path.join(__dirname,'studio_session_fixtures');
const fixture=name=>fs.readFileSync(path.join(FIX,name),'utf8');
let N,P,X,O,J,R;
test.before(async()=>{
 N=await import(STATIC+'workspace-notebook.mjs');P=await import(STATIC+'workspace-project.mjs');X=await import(STATIC+'workspace-retention.mjs');
 O=await import(STATIC+'workspace-optical.mjs');J=await import(STATIC+'workspace-job.mjs');R=await import(STATIC+'workspace-open-run.mjs');
});
const VIEW={mode:0,component:'magnitude',window:'Core region'};
const setup={materials:{Core:'Silicon',Oxide:'Silica',Heater:''},temperature:293.15,cooling:'',fixed:'',terminal:''};
const inputs=()=>P.snapshot({width:500,voltage:1,electric:false,heat:false,structure:false,optics:true,wavelength:1550,coreMesh:30},setup);
const field=k=>({node_coordinates:[[0,0],[1e-6,0],[0,1e-6],[1e-6,1e-6]],triangles:[[0,1,2],[1,3,2]],
 real:Array.from({length:k},(_,m)=>[[1,0.25*m,-0],[0.5,-0.125,1e-3*(m+1)]]),imag:Array.from({length:k},(_,m)=>[[0,1e-9*m,0],[-2e-3,0,0]])});
const run=(extra={})=>Object.assign(N.validateRun({job:'0000000d',completedAt:'2026-11-25T04:00:00.000Z',settings:N.opticalSettings(1550,30,2),input:inputs(),
 effective_index:[2.43931663,1.93],field:field(2),origin:'local',serverVersion:'0.9.3',te_polarization_fraction:[0.98,0.03],effective_area:[1.9e-13,4.1e-13],label:'',pinned:false,...extra}),{number:4});

test('K9: the words of 4.3 and 4.4, exactly',()=>{
 const r=run();
 assert.equal(X.recomputingText({...r,number:4,duration:118000}),"Recomputing Run 4's fields · about 2 min");
 assert.equal(X.recomputingText({...r,number:4}),"Recomputing Run 4's fields");
 assert.equal(X.recomputedText(r),"Run 4's fields recomputed from its stored inputs; its values match.");
 assert.equal(X.notRecomputedText(r,{name:'n_eff',mode:1,stored:2.43931663,fresh:2.43931671}),"Run 4's fields were not recomputed: mode 1 n_eff came out 2.43931671, stored 2.43931663. Run 4 is unchanged. Use this run's inputs and Run study to make a new run.");
 assert.equal(X.notRecomputedText(r,{name:'n_eff',mode:1,stored:2.43931663,fresh:2.43931671},{stored:'0.9.3',current:'0.9.4'}),"Run 4's fields were not recomputed: mode 1 n_eff came out 2.43931671, stored 2.43931663 (stored by Studio 0.9.3; this is 0.9.4). Run 4 is unchanged. Use this run's inputs and Run study to make a new run.");
 assert.equal(X.notRecomputedText(r,{name:'n_eff',mode:1,stored:2.43931663,fresh:2.43931671},{stored:'0.9.3',current:'0.9.3'}),"Run 4's fields were not recomputed: mode 1 n_eff came out 2.43931671, stored 2.43931663. Run 4 is unchanged. Use this run's inputs and Run study to make a new run.");
 assert.equal(X.cannotRecomputeText(r,'Unsupported study: the closed window search needs capabilities v10.'),"Run 4's fields cannot be recomputed: Unsupported study: the closed window search needs capabilities v10.");
 assert.equal(X.valuesAgainText(r),"No need to run: Run 4 already has these values; its fields are not kept. Run study adds a copy with the same values");
 assert.equal(X.recomputeLabel({...r,label:'Design A'}),"Recompute Run 4 · Design A's fields");
 // the page uses them
 const app=fs.readFileSync(path.join(__dirname,STATIC,'workspace-app.mjs'),'utf8');
 assert.ok(app.includes("offer.append((host.textContent?' ':'')+(run.field?matchesAgainText(runNumber(run),run.label||''):valuesAgainText({...run,number:runNumber(run)}))+'. ',show);"));
});

test('the tolerance: 1e-12 relative, 1e-15 absolute below 1e-3',()=>{
 assert.ok(X.sameValue(2.4,2.4*(1+9e-13)));assert.ok(!X.sameValue(2.4,2.4*(1+2e-12)));
 assert.ok(X.sameValue(2e-4,2e-4+9e-16));assert.ok(!X.sameValue(2e-4,2e-4+2e-15));
 assert.ok(X.sameValue(null,null));assert.ok(!X.sameValue(null,1));assert.ok(!X.sameValue(1,NaN));
 // every value a run stores is compared, in order: n_eff, Im n_eff, TE fraction, effective area, n_g
 const a=run(),b=run();assert.equal(X.recomputeMismatch(a,b),null);
 const c=run({te_polarization_fraction:[0.98,0.0300001]});assert.deepEqual(X.recomputeMismatch(a,c),{name:'TE fraction',mode:2,stored:0.03,fresh:0.0300001});
 const d=run({group_index:[4.1,null],group_index_method:'central_difference 1 nm phase-continuation'}),e=run({group_index:[4.1,4.0],group_index_method:'central_difference 1 nm phase-continuation'});
 assert.deepEqual(X.recomputeMismatch(d,e),{name:'n_g',mode:2,stored:null,fresh:4});
 // a value the recomputed run does not have
 assert.equal(X.recomputeMismatch(d,a).missing,true);
});

test('K12: a stored value perturbed by 1e-9 relative: nothing attached, the run unchanged, the sentence with the mode and both values',()=>{
 const stored=run(),fresh=run();
 // the stored n_eff of mode 1 as another build might have written it
 const perturbed=Object.assign(N.validateRun({...stored,effective_index:[2.43931663*(1+1e-9),1.93],field:stored.field}),{number:4});
 X.letGoField(perturbed);
 const before=N.sessionText(inputs(),[perturbed],null,[null,null],VIEW);
 const m=X.recomputeMismatch(perturbed,fresh);
 assert.deepEqual({name:m.name,mode:m.mode},{name:'n_eff',mode:1});
 assert.equal(X.notRecomputedText(perturbed,m),"Run 4's fields were not recomputed: mode 1 n_eff came out 2.43931663, stored 2.43931663. Run 4 is unchanged. Use this run's inputs and Run study to make a new run.".replace('came out 2.43931663, stored 2.43931663','came out 2.4393166300, stored 2.4393166324'));
 // the page attaches nothing on a mismatch: the run's record is the same bytes
 assert.equal(perturbed.field,null);assert.equal(N.sessionText(inputs(),[perturbed],null,[null,null],VIEW),before);
});

test('a match attaches the field to the same run: its job, number, name, pin, time, origin; the values as before',()=>{
 const stored=run({label:'Design A',pinned:true}),fresh=run(),record=N.sessionText(inputs(),[stored],null,[null,null],VIEW);
 X.letGoField(stored);X.forgetHeldFields([stored]);
 assert.equal(X.recomputeMismatch(stored,fresh),null);
 X.attachField(stored,fresh.field);
 assert.deepEqual([stored.job,stored.number,stored.label,stored.pinned,stored.completedAt,stored.origin],['0000000d',4,'Design A',true,'2026-11-25T04:00:00.000Z','local']);
 assert.equal(stored.field,fresh.field);
 // the record with the field again: the same bytes as before it went (the engine's values were kept)
 assert.equal(N.sessionText(inputs(),[stored],null,[null,null],VIEW),record);
});

test('the document Recompute sends: the one the run was computed with, from its stored inputs and settings',()=>{
 const strip={name:'Core',type:'rect',material:'Silicon',x:-250,y:0,w:500,h:220},substrate={name:'Substrate',type:'rect',material:'Silicon',x:-1500,y:-1200,w:3000,h:700};
 const ALL={left:'open',right:'open',bottom:'open',top:'open'};
 const cases=[{shapes:[strip],modeCount:2},{shapes:[strip,substrate],modeCount:4},{shapes:[strip,substrate],modeCount:4,searchTarget:2.46},{shapes:[strip,substrate],modeCount:2,open:ALL},{shapes:[strip,substrate],modeCount:2,open:ALL,groupIndex:true},{shapes:[strip],modeCount:3,groupIndex:true}];
 for(const c of cases){
  const state={electric:false,heat:false,structure:false,optics:true,wavelength:1550,coreMesh:30,modeCount:c.modeCount,shapes:c.shapes,...(c.groupIndex?{groupIndex:true}:{}),...(c.open?{openBoundary:{edges:c.open}}:{}),...(c.searchTarget!=null?{searchTarget:c.searchTarget}:{})};
  const doc=O.opticalDocument(state,setup);
  // the run the page keeps of that document's result (its settings as the result handler writes them)
  const input=P.validateProject({...inputs(),model:{...inputs().model,shapes:c.shapes}});
  const closed=N.opticalSettings(1550,30,c.modeCount),ob=c.open?R.builderBoundary({edges:c.open},c.shapes):null;
  const settings=ob?R.openSettings(closed,{edges:ob.edges,target:ob.target},c.shapes):c.searchTarget!=null?N.closedTargetSettings(closed,c.searchTarget):closed;
  const stub={settings,input,effective_index:[2.6],...(c.groupIndex?{group_index:[4.2],group_index_method:'central_difference 1 nm phase-continuation'}:{})};
  assert.equal(JSON.stringify(X.recomputeDocument(stub)),JSON.stringify(doc),JSON.stringify(c));
 }
});

test('the pending job of a recompute keeps the run it recomputes, so a resumed job attaches its field (and makes no run)',()=>{
 const record={version:1,job:'0abc1234',input:inputs(),revision:3,serverVersion:'0.9.4',serverInstance:'0'.repeat(32),startedAt:'2026-11-25T05:00:00.000Z',recompute:{job:'0000000d',number:4}};
 assert.deepEqual(J.validatePending(record).recompute,{job:'0000000d',number:4});
 for(const bad of [{job:'x',number:4},{job:'0000000d',number:0},{job:'0000000d'},'0000000d'])assert.throws(()=>J.validatePending({...record,recompute:bad}),{message:'Invalid pending recompute.'});
 assert.equal(J.validatePending({...record,recompute:undefined}).recompute,undefined);
});
