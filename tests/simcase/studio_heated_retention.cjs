// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
// Run retention of the heated model (design "Keeping more runs", section 7; slice H1): the checks of
// the pre-registration that need no engine run. HK2 (version 8 written byte for byte), HK3 (version
// 15 read and written) and HK4 (what main ddb09a1 reads of it).
const {before}=require('node:test');const test=require('node:test');const assert=require('node:assert/strict');
const {readFileSync}=require('node:fs');const {join}=require('node:path');
const S='../../packages/simcase/src/simcase/studio/static/';
const FIX=join(__dirname,'studio_session_fixtures');
const fixture=name=>readFileSync(join(FIX,name),'utf8');
const read=name=>readFileSync(join(__dirname,S,name),'utf8');
let M,N,MP,PF,R,H;
before(async()=>{M=await import(S+'workspace-multiphysics-session.mjs');N=await import(S+'workspace-notebook.mjs');MP=await import(S+'workspace-multiphysics.mjs');
 PF=await import(S+'workspace-project-file.mjs');R=await import(S+'workspace-notebook-recovery.mjs');H=await import('./studio_session_fixtures/heated_sessions.mjs');});
const bytesOf=text=>Buffer.byteLength(text,'utf8');
const stateOfSession=s=>({document:s.document,runs:s.runs,baselines:s.baselines,selected:s.selected,view:s.view});
const VIEW={page:'Results',selection:'results:modes1',index_map:'change',baseline_option:false};

// ---- runs of a chosen size, as the server replies (a strip of n × 2 nodes) ----------------------
const doc=(power='2e14 W/m^3')=>({openphysics:'0.3/multiphysics.1',name:'Heated silicon waveguide',
 geometry:{version:1,components:{xs:{dimension:'2d',length_unit:'um',depth:null,domain:{xmin:-3,xmax:3,ymin:-2,ymax:2.5},background:{material:'physmat:SiO2'},features:[{name:'core',type:'rect',x:-0.25,y:0,w:0.5,h:0.22,material:'physmat:Si'}]}}},
 materials:{},mesh:{element_size:'0.25 um'},
 physics:{heat1:{type:'thermal.steady2d',prescribed_temperature:{bottom:'300 K'},heat_source_density:{core:power}},modes1:{type:'em.modes2d',formulation:'scalar',vacuum_wavelength:'1550 nm',mode_count:1}},
 couplings:{heat1_to_modes1:{from:'heat1.temperature',to:'modes1.temperature',transfer:'same_mesh'}}});
function resultOf(n,seed=1){
 const P=[],T=[],temp=[];
 for(let i=0;i<n;i++){P.push([i*1e-7,0],[i*1e-7,1e-7]);temp.push(300+((seed*7919+i*31)%997)/97,300+((seed*104729+i*17)%991)/89);}
 for(let i=0;i+1<n;i++)T.push([2*i,2*i+2,2*i+1],[2*i+1,2*i+2,2*i+3]);
 const mean=T.map(t=>(temp[t[0]]+temp[t[1]]+temp[t[2]])/3);
 return {result:'multiphysics-run-v1',name:'Heated silicon waveguide',solve_order:[['heat1'],['modes1']],
  couplings:{heat1_to_modes1:{from:'heat1.temperature',to:'modes1.temperature',quantity:'temperature',unit:'K',transfer:'same_mesh',location:'node',mesh_signature:'match',max_abs_difference:{value:0,unit:'K'},conservation_residual:null}},
  loops:[],timing:{heat1:0.1,modes1:0.2},diagnostics:[],
  mesh:{node_coordinates:P,field_units:{node_coordinates:'m'},triangles:T,regions:T.map((t,i)=>i%2),region_names:['background','core']},
  physics:{heat1:{type:'thermal.steady2d',temperature:{unit:'K',location:'node',values:temp},range:{min:Math.min(...temp),max:Math.max(...temp),unit:'K'},summary:{}},
   modes1:{type:'em.modes2d',effective_index:{unit:'1',values:[[2.44+seed*1e-6]]},vacuum_wavelength:{unit:'m',values:[1.55e-6]},summary:{},
    coupled:{temperature:{unit:'K',location:'element',values:mean},refractive_index:{location:'element',n:mean.map(v=>3.47+v*1e-5),k:null},index_change:mean.map(v=>(v-300)*1.8e-4)}}}};
}
const hex=n=>'mp-'+n.toString(16).padStart(12,'0');
const runOf=(number,n,{seed=number,pinned=false,label=''}={})=>({job:hex(0x500000000000+number),number,label,pinned,completedAt:new Date(Date.UTC(2026,10,25,0,0,number)).toISOString(),serverVersion:'0.0.2',
 doc:doc(`${number}e14 W/m^3`),events:[{event:'physics_started',physics:'heat1'}],order:[['heat1'],['modes1']],result:resultOf(n,seed),maps:'kept',origin:'local'});
const stateOf=(runs,selected=runs.at(-1)?.job??null)=>({document:doc(),runs,baselines:{},selected,view:VIEW});
test('HK2: every version 8 session of main ddb09a1 is read and written byte for byte, by Save, recovery and the project entry',()=>{
 const texts={...JSON.parse(fixture('multiphysics-v8-ddb09a1.json')),fixture:fixture('multiphysics-v8.json')};
 assert.deepEqual(Object.keys(texts),['empty','one','two','six','fixture']);
 for(const [name,text] of Object.entries(texts)){
  const session=N.parseSession(text),state=stateOfSession(session);
  assert.equal(JSON.parse(text).version,8,name);
  assert.equal(M.writeMultiphysicsSession(state).text,text,name+': Save');
  assert.equal(M.recoveryText(state).text,text,name+': recovery');
  const project=PF.writeProject({name:'p',savedAt:'2026-11-25T10:00:00.000Z',studio:'0.0.0',active:'m1',entries:[PF.projectEntry({id:'m1',kind:'multiphysics',title:'Heated silicon waveguide',card:'heated-waveguide',text})]}).text;
  assert.equal(PF.readProject(project).models[0].text,text,name+': project entry');
 }
 // the writer's version: 8 up to six runs
 assert.equal(N.parseSession(texts.six).runs.length,6);
});

test('HK3: version 15 holds 7 to 20 runs, is read and written byte for byte, and keeps every check of version 8',()=>{
 const text=fixture('multiphysics-v15-thirteen-runs.json'),session=N.parseSession(text),doc15=JSON.parse(text);
 assert.equal(doc15.version,15);assert.deepEqual(session.runs.map(r=>r.number),[2,4,5,6,7,8,9,10,11,12,13,14,15]);
 assert.deepEqual(session.runs.filter(r=>r.maps==='not kept').map(r=>r.number),[4,6,8,10,12]);
 assert.equal(M.writeMultiphysicsSession(stateOfSession(session)).text,text);assert.equal(M.recoveryText(stateOfSession(session)).text,text);
 const project=PF.writeProject({name:'p',savedAt:'2026-11-25T10:00:00.000Z',studio:'0.0.0',active:'m1',entries:[PF.projectEntry({id:'m1',kind:'multiphysics',title:'Heated silicon waveguide',card:'heated-waveguide',text})]}).text;
 assert.equal(PF.readProject(project).models[0].session.runs.length,13);
 assert.deepEqual([...PF.KIND_VERSIONS.multiphysics],[8,15]);
 // 7 and 20 runs: version 15, written and read again byte for byte; six runs: version 8
 for(const count of [6,7,20]){
  const runs=Array.from({length:count},(_,i)=>runOf(i+1,3+i%4)),t=M.writeMultiphysicsSession(stateOf(runs)).text;
  assert.equal(JSON.parse(t).version,count>6?15:8,`${count} runs`);
  assert.equal(M.writeMultiphysicsSession(stateOfSession(N.parseSession(t))).text,t,`${count} runs again`);
 }
 const edit=(t,f)=>{const d=JSON.parse(t);f(d);return M.sessionJson(d);};
 const twenty=M.writeMultiphysicsSession(stateOf(Array.from({length:20},(_,i)=>runOf(i+1,3)))).text;
 const refused=(t,message)=>assert.throws(()=>N.parseSession(t),{message});
 // 21 runs, and a version 8 file of seven runs
 refused(edit(twenty,d=>{const r=structuredClone(d.runs[0]);r.job=hex(0x5000000000ff);r.number=21;r.digest=M.recordDigest(r);d.runs.push(r);}),'Unsupported session format or run count.');
 refused(edit(twenty,d=>{d.version=8;d.runs=d.runs.slice(0,7);d.selected=d.runs[6].job;}),'Unsupported session format or run count.');
 // a version 15 file of six runs or fewer (edited by hand) is read and written as version 8
 const six=edit(twenty,d=>{d.runs=d.runs.slice(0,6);d.selected=d.runs[5].job;});
 assert.equal(JSON.parse(M.writeMultiphysicsSession(stateOfSession(N.parseSession(six))).text).version,8);
 // the version 8 checks refuse a damaged version 15 file with the same sentences
 refused(edit(text,d=>{d.runs[3].label='changed';}),'Run 6 changed after it was saved (its check value does not match).');
 refused(edit(text,d=>{delete d.runs[1].counts;d.runs[1].digest=M.recordDigest(d.runs[1]);}),'Run 4 keeps no maps and no node and triangle counts.');
 refused(text.replace('"location":"node","values":[305.53260544712396,','"location":"node","values":[NaN,'),'Session is not valid JSON.');
 refused(edit(text,d=>{d.runs[0].result.mesh.triangles[0][0]=99999;d.runs[0].digest=M.recordDigest(d.runs[0]);}),"Run 2's stored maps are not well formed: triangle 0 names node 99999, outside 0–1725.");
 refused(edit(text,d=>{d.application='optical';}),'This session file holds a “optical” model, which this Studio does not read.');
 // above 15 by name
 refused(edit(text,d=>{d.version=16;}),'This session file is version 16, newer than this Studio reads (versions 6–15). Open it in a newer Studio.');
 assert.equal(N.HIGHEST_SESSION_VERSION,M.RUNS_MULTIPHYSICS_VERSION);
});

test('HK4: main ddb09a1 refuses a version 15 file by name, alone, in a project and in a recovery record, and does not adopt the record',async()=>{
 const golden=JSON.parse(fixture('refusals-v15-ddb09a1.json'));
 assert.deepEqual(golden,{session:'This session file is version 15, newer than this Studio reads (versions 6–14). Open it in a newer Studio.',
  project:'Heated silicon waveguide: This session file is version 15, newer than this Studio reads (versions 6–14). Open it in a newer Studio.',
  recovery:'This session file is version 15, newer than this Studio reads (versions 6–14). Open it in a newer Studio.',adopted:false});
 // this Studio reads all three
 const now=await H.readWith(new URL(S,'file://'+__dirname+'/').href,FIX);
 assert.deepEqual(now,{session:null,project:null,recovery:null,adopted:true});
});

test('the run list keeps 20 runs: pinned runs stay, a 21st run replaces the oldest unpinned one',()=>{
 const runs=Array.from({length:20},(_,i)=>runOf(i+1,3,{pinned:i===0}));
 const next=M.appendMultiphysicsRun(runs,runOf(21,3));assert.equal(next.length,20);assert.deepEqual(next.map(r=>r.number).slice(0,3),[1,3,4]);
 assert.throws(()=>M.appendMultiphysicsRun(runs.map(r=>({...r,pinned:true})),runOf(21,3)),{message:'All 20 runs are pinned. Unpin a run before running again.'});
 assert.equal(M.MULTIPHYSICS_RUN_LIMIT,20);assert.equal(M.PREVIOUS_MULTIPHYSICS_RUN_LIMIT,6);
});
