// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0

const {before}=require('node:test');
let solverApi;
let APPLICATIONS,templatePhysics,resumeChoices,sessionRunNames,CHOOSER_NOTES,CHOOSER_CHOICE,sessionLine,opticalResumeChoice,offerTime;
let opticalBlock,opticalDocument;
before(async()=>{
({solverApi}=await import('../../packages/simcase/src/simcase/studio/static/workspace-api.mjs'));
({APPLICATIONS,templatePhysics,resumeChoices,sessionRunNames,CHOOSER_NOTES,CHOOSER_CHOICE,sessionLine,opticalResumeChoice,offerTime}=await import('../../packages/simcase/src/simcase/studio/static/workspace-applications.mjs'));
({opticalBlock,opticalDocument}=await import('../../packages/simcase/src/simcase/studio/static/workspace-optical.mjs'));
});
const test=require('node:test');
const assert=require('node:assert/strict');




test('API serializes submitted snapshot and parses successful response',async()=>{
 const body={doc:{width:500}};let sent;
 const result=await solverApi('/api/validate',body,async(path,options)=>{
  sent=options;assert.equal(path,'/api/validate');body.doc.width=700;
  return {ok:true,json:async()=>({ok:true})};
 });
 assert.deepEqual(result,{ok:true});assert.equal(sent.method,'POST');
 assert.equal(JSON.parse(sent.body).doc.width,500);assert.equal(sent.signal.aborted,false);
});
test('GET and backend errors preserve the explicit API contract',async()=>{
 await solverApi('/api/jobs/12345678',undefined,async(path,options)=>{
  assert.equal(options.method,'GET');assert.equal(options.body,undefined);
  return {ok:true,json:async()=>({status:'done'})};
 });
 await assert.rejects(solverApi('/api/run',{},async()=>({ok:false,json:async()=>({detail:'Offline'})})),/Offline/);
 await assert.rejects(solverApi('/api/run',{},async()=>({ok:true,json:async()=>{throw Error('HTML');}})),/not JSON/);
 await assert.rejects(solverApi('/api/run',{},async()=>{throw Error('Disconnected');}),/Disconnected/);
});
test('application availability agrees with actual execution gates',async()=>{
 const setup={materials:{Core:'Silicon',Oxide:'Silica'}};
 for(const app of APPLICATIONS){
  const model={width:500,...templatePhysics(app.id)},heat=await import('../../packages/simcase/src/simcase/studio/static/workspace-heat.mjs');
  const heatOnly=model.heat&&!model.electric&&!model.structure&&!model.optics;
  // electric currents and heat alone are the Joule heating application (workspace-joule.mjs)
  const jouleOnly=model.heat&&model.electric&&!model.structure&&!model.optics,joule=await import('../../packages/simcase/src/simcase/studio/static/workspace-joule.mjs');
  const runnable=heatOnly?heat.thermalBlock(heat.validateThermal(heat.DEFAULT_THERMAL))==='':jouleOnly?joule.jouleBlock(joule.validateJoule(joule.DEFAULT_JOULE))==='':opticalBlock(model,setup)==='';
  assert.equal(runnable,app.available,app.id);
  if(heatOnly)assert.equal(heat.heatDocument(heat.DEFAULT_THERMAL).physics.heat1.type,'thermal.steady2d');
  if(jouleOnly)assert.equal(joule.jouleDocument(joule.DEFAULT_JOULE).physics.j.type,'joule.temperature2d');
  if(!app.available)assert.throws(()=>opticalDocument(model,setup));
 }
 const a=templatePhysics('optical');a.heat=true;assert.equal(templatePhysics('optical').heat,false);
 assert.throws(()=>templatePhysics('unimplemented'));
});

test('HTTP failure status reaches job recovery without replacing server detail',async()=>{
 for(const status of [404,409,500])await assert.rejects(solverApi('/api/jobs/12345678',undefined,async()=>({ok:false,status,json:async()=>({detail:'Captured server detail'})})),error=>error.status===status&&error.message==='Captured server detail');
});
test('the landing page offers the latest and earlier browser sessions to resume',()=>{
 const when=t=>t;
 assert.deepEqual(resumeChoices(null,[],when),[]);
 assert.deepEqual(resumeChoices({runs:2,savedAt:'T1'},[{runs:1,savedAt:'T0'}],when),[
  {kind:'latest',label:'Last session in this browser · 2 runs · saved T1'},
  {kind:'earlier',index:0,label:'Earlier session · 1 run · saved T0'}]);
 assert.deepEqual(resumeChoices(null,[{runs:3,savedAt:'T0'}],when).map(c=>c.kind),['earlier']);
});
test('an earlier session choice keeps its storage index when an unreadable record is skipped',()=>{
 const choices=resumeChoices(null,[{runs:1,savedAt:'T0',index:0},{runs:2,savedAt:'T2',index:2}],t=>t);
 assert.deepEqual(choices.map(c=>c.index),[0,2]);
});
test('every recovery entry names its model and its runs',()=>{
 assert.deepEqual(sessionRunNames({runs:[{label:'design A'},{label:''}]}),['Run 1 · design A','Run 2']);
 assert.deepEqual(sessionRunNames({runs:[{number:3,label:''},{number:4,label:'heater 10 mW'}]}),['Run 3','Run 4 · heater 10 mW']);
 assert.deepEqual(resumeChoices({runs:2,savedAt:'T1',model:'Optical waveguide',names:['design A','Run 2']},[{runs:1,savedAt:'T0',model:'Heated silicon waveguide',names:['Run 1'],index:0}],t=>t),[
  {kind:'latest',label:'Last session in this browser · Optical waveguide · 2 runs · design A, Run 2 · saved T1'},
  {kind:'earlier',index:0,label:'Earlier session · Heated silicon waveguide · 1 run · Run 1 · saved T0'}]);
});
test('the Models page says what Save session keeps of each model, and how to leave the coupled one',()=>{
 const [optical,heat,joule,coupled]=CHOOSER_NOTES;
 assert.match(optical,/Save session keeps the inputs, the runs and the comparison\.$/);
 assert.match(heat,/Save session keeps the plate inputs; heat results stay in this tab\.$/);
 assert.match(joule,/Save session keeps the inputs; Joule heating results stay in this tab\.$/);
 assert.match(coupled,/^Heated silicon waveguide: .*Save session keeps the model with its runs, their names and pins, and the without-heater results\.$/);
 assert.ok(CHOOSER_NOTES.every(t=>!/Save model file|results stay in the tab|Existing thermal Studio views/.test(t)));
 assert.match(CHOOSER_CHOICE,/Undo takes the choice back between the optical, steady heat and Joule heating models\. The heated silicon waveguide has its own Undo for its edits: to leave it, choose another model here\.$/);
});
test('no Studio page calls a loaded or recovered result unauthenticated',()=>{
 const fs=require('node:fs'),path=require('node:path'),dir=path.join(__dirname,'../../packages/simcase/src/simcase/studio/static');
 for(const name of fs.readdirSync(dir).filter(n=>/\.(mjs|html|js)$/.test(n)))assert.doesNotMatch(fs.readFileSync(path.join(dir,name),'utf8'),/authenticated/,name);
});
test('a recovery entry names the session file its record came from',()=>{
 assert.equal(sessionLine({model:'Heated silicon waveguide',runs:2,names:['Run 1','Run 2'],file:'heated-silicon-waveguide-session-2026-11-22-1426.json'}),
  'Heated silicon waveguide · 2 runs · Run 1, Run 2 · file heated-silicon-waveguide-session-2026-11-22-1426.json');
 assert.equal(sessionLine({model:'Optical waveguide',runs:1,names:['Run 1'],file:null}),'Optical waveguide · 1 run · Run 1');
});
test('the Optical waveguide card offers the optical session in browser recovery before Start new',()=>{
 assert.deepEqual(opticalResumeChoice({runs:2,names:['design A','design B'],savedAt:'T'},t=>'2:25 PM'),{label:'Resume Optical waveguide · design A, design B · 2:25 PM (this browser)'});
 // the record's session file, when it names one
 assert.deepEqual(opticalResumeChoice({runs:2,names:['Run 1 · design A','Run 2'],file:'optical-waveguide-session-2026-11-22-1425.json',savedAt:'T'},t=>'2:25 PM'),{label:'Resume Optical waveguide · Run 1 · design A, Run 2 · file optical-waveguide-session-2026-11-22-1425.json · 2:25 PM (this browser)'});
 const now=new Date(2026,10,22,15,0),today=new Date(2026,10,22,14,25).toISOString(),before=new Date(2026,10,20,14,25).toISOString();
 assert.doesNotMatch(offerTime(today,now),/2026|20/);assert.match(offerTime(before,now),/20/);
});
