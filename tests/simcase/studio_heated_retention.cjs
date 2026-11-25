// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
// Run retention of the heated model (design "Keeping more runs", section 7; slice H1): the checks of
// the pre-registration that need no engine run. HK2 (version 8 written byte for byte), HK3 (version
// 15 read and written), HK4 (what main ddb09a1 reads of it), HK6 to HK8 (a seeded sequence of 2000
// steps: no run number reused, the tab equal to the file and recovery, maps let go only when maps
// arrive, in the order of 3.2), HK9 (the words), HK13 (recovery fills newest first) and HK14 (Open
// and Restore are arrivals). HK1 needs engine results: tests/simcase/studio_heated_retention_engine.cjs.
const {before}=require('node:test');const test=require('node:test');const assert=require('node:assert/strict');
const {readFileSync}=require('node:fs');const {join}=require('node:path');
const S='../../packages/simcase/src/simcase/studio/static/';
const FIX=join(__dirname,'studio_session_fixtures');
const fixture=name=>readFileSync(join(FIX,name),'utf8');
const read=name=>readFileSync(join(__dirname,S,name),'utf8');
let M,N,MP,PF,R,B,W,X,H;
before(async()=>{M=await import(S+'workspace-multiphysics-session.mjs');N=await import(S+'workspace-notebook.mjs');MP=await import(S+'workspace-multiphysics.mjs');
 PF=await import(S+'workspace-project-file.mjs');R=await import(S+'workspace-notebook-recovery.mjs');B=await import(S+'workspace-budget.mjs');W=await import(S+'workspace-multiphysics-retention.mjs');
 X=await import(S+'workspace-retention.mjs');H=await import('./studio_session_fixtures/heated_sessions.mjs');});
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
const withMaps=runs=>runs.filter(r=>r.maps!=='not kept').map(r=>r.number).sort((a,b)=>a-b);
// the reference of 3.2, from the session text written in full for each trial (not the cached sums)
function reference(state,budget,first=[]){
 const order=B.budgetOrder(state.runs.filter(r=>r.maps!=='not kept'),state.selected,first),keep=new Set();
 if(bytesOf(M.sessionText(state))<=budget)return order.map(r=>r.number).sort((a,b)=>a-b);
 order.forEach((r,i)=>{const trial=new Set([...keep,r.job]);if(bytesOf(M.sessionText(state,trial))<=budget||(i===0&&r.job===state.selected))keep.add(r.job);});
 return state.runs.filter(r=>keep.has(r.job)).map(r=>r.number).sort((a,b)=>a-b);
}

test('HK2: every version 8 session of main ddb09a1 is read and written byte for byte, by Save, recovery and the project entry',()=>{
 const texts={...JSON.parse(fixture('multiphysics-v8-ddb09a1.json')),fixture:fixture('multiphysics-v8.json')};
 assert.deepEqual(Object.keys(texts),['empty','one','two','six','fixture']);
 for(const [name,text] of Object.entries(texts)){
  const session=N.parseSession(text),state=stateOfSession(session);
  assert.equal(JSON.parse(text).version,8,name);
  assert.equal(M.writeMultiphysicsSession(state).text,text,name+': Save');
  assert.equal(M.recoveryText(state).text,text,name+': recovery');
  // an open is an arrival: a file within the budget keeps every map (HK14)
  assert.deepEqual(M.keepMapsAtArrival(state).letGo,[],name);assert.equal(M.writeMultiphysicsSession(state).text,text,name+': after the arrival');
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

// ---- HK6 to HK8: a seeded sequence of 2000 steps ---------------------------------------------
function rng(seed){let s=seed>>>0;return ()=>{s=(s*1664525+1013904223)>>>0;return s/2**32;};}
test('HK6–HK8: 2000 seeded steps: no number reused, the tab equal to the file and recovery, maps let go only at arrivals and in the order of 3.2',()=>{
 const random=rng(20261125),pick=list=>list[Math.floor(random()*list.length)];
 const budget=90000;
 let runs=[],selected=null,top=0,used=new Set(),steps=0,arrivals=0,letGo=0,kinds={};
 const state=()=>stateOf(runs,selected);
 const arrive=(first=[])=>{const before=state();const want=reference(before,budget,first);const out=M.keepMapsAtArrival(before,{budget,first});arrivals++;letGo+=out.letGo.length;
  assert.deepEqual(withMaps(runs),want,`step ${steps}: the order of 3.2`);
  const text=M.writeMultiphysicsSession(state()).text;
  if(out.total!==null)assert.equal(out.total,bytesOf(text),`step ${steps}: the cached sum is the written length`);
  if(!(out.kept.length===1&&out.kept[0].job===selected&&out.total>budget))assert.ok(bytesOf(text)<=budget,`step ${steps}: within the budget`);
  return out;};
 for(steps=0;steps<2000;steps++){
  const before=JSON.stringify(withMaps(runs)),op=pick(runs.length?['result','result','result','pin','unpin','rename','select','reopen','show']:['result']);kinds[op]=(kinds[op]||0)+1;
  let arrival=true;
  if(op==='result'){
   const n=pick([3,10,40,120,400]),run=runOf(++top,n,{seed:top});
   assert.ok(!used.has(run.number),`step ${steps}: number ${run.number} reused`);used.add(run.number);
   try{runs=M.appendMultiphysicsRun(runs,run);}catch(e){assert.equal(e.message,'All 20 runs are pinned. Unpin a run before running again.');top--;used.delete(run.number);arrival=false;}
   if(arrival){selected=run.job;arrive();}
  }else if(op==='pin'){pick(runs).pinned=true;arrival=false;}
  else if(op==='unpin'){pick(runs).pinned=false;arrival=false;}
  else if(op==='rename'){const r=pick(runs);r.label=random()<0.5?'':'name '+steps;if(r.label)r.pinned=true;arrival=false;}
  else if(op==='select'||op==='show'){selected=pick(runs).job;arrival=false;}
  else if(op==='reopen'){
   // Save, then Open: the file's runs replace the tab's, an arrival
   const text=M.writeMultiphysicsSession(state()).text,session=N.parseSession(text);
   runs=session.runs;selected=session.selected;arrive();
   if(bytesOf(text)<=budget)assert.equal(M.writeMultiphysicsSession(state()).text,text,`step ${steps}: an opened file within the budget is its own bytes`);
  }
  // HK8: nothing but an arrival lets maps go
  if(!arrival)assert.equal(JSON.stringify(withMaps(runs)),before,`step ${steps} (${op}): maps changed without an arrival`);
  // HK6: at most 20 runs, numbers increasing in the list and never above the highest given
  assert.ok(runs.length<=20);assert.deepEqual(runs.map(r=>r.number),[...runs.map(r=>r.number)].sort((a,b)=>a-b));
  // HK7: the tab = the file = recovery (which runs keep their maps)
  const text=M.writeMultiphysicsSession(state()).text,file=JSON.parse(text),rec=JSON.parse(M.recoveryText(state()).text);
  assert.deepEqual(file.runs.map(r=>r.maps),runs.map(r=>r.maps),`step ${steps}: tab and file`);
  assert.deepEqual(rec.runs.map(r=>r.maps),runs.map(r=>r.maps),`step ${steps}: tab and recovery`);
  assert.equal(file.version,runs.length>6?15:8);
 }
 assert.ok(arrivals>600&&letGo>100&&kinds.reopen>50,JSON.stringify({arrivals,letGo,kinds}));
 assert.ok(top>=20);
});

test('HK8: the selected run keeps its maps alone over the budget, and Save then gives today\'s refusal',()=>{
 const big=runOf(3,400),small=runOf(4,10,{pinned:true});
 const runs=[big,small],state=stateOf(runs,big.job),budget=M.mapBytes(big)-1000;
 const out=M.keepMapsAtArrival(state,{budget});
 assert.deepEqual(out.kept.map(r=>r.number),[3]);assert.deepEqual(out.letGo.map(r=>r.number),[4]);
 const limit=M.mapBytes(big);
 assert.equal(M.writeMultiphysicsSession(state,{limit}).refusal,`Run 3 alone is ${M.sizeText(M.writeMultiphysicsSession(stateOf([big],big.job),{limit:Infinity}).bytes)}, over the 16 MiB session limit. Unpin it or keep it in a smaller-mesh model.`);
 // the selected and pinned order: a pinned run is let go with the pinned words
 const pinned=runOf(5,200,{pinned:true}),newest=runOf(6,200),st=stateOf([pinned,newest],newest.job),b2=M.sessionBytesWithoutMaps(st)+M.mapBytes(newest)+10;
 assert.deepEqual(M.chooseMaps(st,{budget:b2}).letGo.map(r=>r.number),[5]);
});

test('HK9: the words (S1–S14)',()=>{
 const name=r=>`Run ${r.number} (run at 14:0${r.number})`,r3={number:3,label:''},r5={number:5,label:''},r4={number:4,label:''},r2={number:2,label:''};
 assert.equal(W.mapsKeepValuesText([r3],name),'If you run: Run 3 (run at 14:03) keeps its values, not its maps');
 assert.equal(W.mapsKeepValuesText([r3,r5],name),'If you run: Run 3 (run at 14:03) and Run 5 (run at 14:05) keep their values, not their maps');
 assert.equal(W.MAPS_MAY_GO_TEXT,"If you run: older runs' maps may not be kept (16.8 MB limit) · pin a run to keep its maps first");
 assert.equal(W.mapsKeepValuesWhileRunningText([r3],name),'When this run finishes, Run 3 (run at 14:03) keeps its values, not its maps');
 assert.equal(W.mapsKeepValuesWhileRunningText([r3,r5],name),'When this run finishes, Run 3 (run at 14:03) and Run 5 (run at 14:05) keep their values, not their maps');
 assert.equal(W.mapsNotKeptAfterText([r3],name),'Run 3 (run at 14:03) keeps its values; its maps were not kept (16.8 MB limit).');
 assert.equal(W.mapsNotKeptAfterText([r3,r5],name),'Run 3 (run at 14:03) and Run 5 (run at 14:05) keep their values; their maps were not kept (16.8 MB limit).');
 assert.equal(W.keepMapsInsteadLabel(r3,r4,()=>'14:05'),"Keep Run 3's maps, not Run 4's (run at 14:05)");
 assert.equal(W.mapsBackText(r3,r4,()=>'Run 4 (run at 14:05)'),"Run 3's maps are back; Run 4 (run at 14:05) keeps its values, not its maps.");
 assert.equal(W.pinnedMapsText([r2],17.4e6),"Run 2 (pinned) keeps its values; its maps were not kept: the selected and pinned runs' maps are 17.4 MB, over the 16.8 MB limit. Unpin a run to keep the newer maps first.");
 assert.equal(W.MP_RUNS_KEPT_TEXT,"Up to 20 runs are kept with their values. Maps are kept up to 16.8 MB. When a result or a recompute arrives, Studio keeps the selected run's maps first, then pinned runs', then the newest. Selecting a run does not bring its maps back; Recompute does. Pinned runs stay; when a 21st run arrives, the oldest unpinned run is replaced. File › Save keeps every run in one file.");
 assert.equal(W.mpRunsNodeLabel(9),'Runs · 9 of 20');
 assert.equal(W.ALL_PINNED_TEXT,'All 20 runs are pinned. Unpin a run under Results › Runs before running again.');
 assert.equal(W.UNPINNED_TEXT,'Run unpinned: once 20 runs are kept, a new run replaces the oldest unpinned one. Press Enter in Run name to pin it again.');
 assert.equal(W.mapsNotKeptResultsText(r4),"Run 4's maps are not kept; its n_eff, coupling check and iteration history are kept. Maps are kept up to 16.8 MB. When a result or a recompute arrives, Studio keeps the selected run's maps first, then pinned runs', then the newest. Selecting a run does not bring its maps back; Recompute does.");
 assert.equal(M.MAPS_NOT_KEPT,'Maps not kept in this file: n_eff, the coupling check and the iteration history are.');
 assert.equal(M.multiphysicsRunName({number:2,label:'',pinned:false}),'Run 2');
 // the view uses them (and keeps no literal copy of the old six-run note)
 const view=read('workspace-multiphysics-view.mjs');
 for(const name of ['MP_RUNS_KEPT_TEXT','mpRunsNodeLabel(runs.length)','ALL_PINNED_TEXT','UNPINNED_TEXT','mapsKeepValuesText(list,dropName)','mapsKeepValuesWhileRunningText(list,dropName)','MAPS_MAY_GO_TEXT','mapsNotKeptAfterText(plain,dropName)','pinnedMapsText(pinned,pinnedBytes)',
  'keepMapsInsteadLabel(maps.back,maps.other,runTime)','mapsBackText(offer.back,offer.other,dropName)','mapsNotKeptResultsText(run)'])
  assert.ok(view.includes(name),name);
 assert.doesNotMatch(view,/Up to six runs are kept|All six runs|once six runs/);
 // an open or restore is an arrival: its words follow the open notice (HK14)
 assert.ok(view.includes("+(mapWords?' '+mapWords:''),'',swapAction());"));
});

test('HK13: recovery of a session over the limit keeps maps newest first, not only the selected and pinned runs\'',()=>{
 const runs=[runOf(1,200,{pinned:true}),runOf(2,200),runOf(3,200),runOf(4,200),runOf(5,200)],state=stateOf(runs,runs[2].job);
 const each=M.mapBytes(runs[0]),limit=M.sessionBytesWithoutMaps(state)+3*each+100;
 const out=M.recoveryText(state,limit),rec=JSON.parse(out.text);
 // selected 3, pinned 1, then the newest: 5
 assert.deepEqual(rec.runs.map(r=>r.maps),['kept','not kept','kept','not kept','kept']);assert.deepEqual(out.notKept,[2,4]);
 assert.ok(bytesOf(out.text)<=limit);
 // the previous rule kept the selected and pinned only
 assert.deepEqual(JSON.parse(M.writeMultiphysicsSession(state,{keepSelected:true,limit}).text).runs.map(r=>r.maps),['kept','not kept','kept','not kept','not kept']);
 // the selected run alone over the limit: nothing new is written
 assert.throws(()=>M.recoveryText(state,M.sessionBytesWithoutMaps(state)+each-1),{message:'browser recovery unavailable: session over 16 MiB'});
});

test('HK14: Open and Restore are arrivals: a file over the budget opens with the order of 3.2 applied',()=>{
 const runs=[1,2,3,4,5,6].map(n=>runOf(n,300,{pinned:n===2})),text=M.writeMultiphysicsSession(stateOf(runs,runs[3].job)).text,session=N.parseSession(text),state=stateOfSession(session);
 const budget=M.sessionBytesWithoutMaps(state)+3*M.mapBytes(state.runs[0])+500;
 const want=reference(state,budget),out=M.keepMapsAtArrival(state,{budget});
 assert.deepEqual(withMaps(state.runs),want);assert.deepEqual(want,[2,4,6]);assert.deepEqual(out.letGo.map(r=>r.number),[5,3,1]);
 // the runs let go in the tab say so in Results; a run read without maps keeps the file's words
 assert.equal(M.mapsLetGoHere(state.runs[0]),true);
 const fromFile=N.parseSession(M.writeMultiphysicsSession(state).text).runs[0];assert.equal(fromFile.maps,'not kept');assert.equal(M.mapsLetGoHere(fromFile),false);
 // the swap: the let-go run's maps come back for another unpinned run's of the same size
 const two=[runOf(1,300,{seed:1}),runOf(2,300,{seed:1}),runOf(3,300,{seed:1})],st=stateOf(two,two[2].job),b=M.sessionBytesWithoutMaps(st)+2*M.mapBytes(two[0])+500;
 const chosen=M.keepMapsAtArrival(st,{budget:b});assert.deepEqual(chosen.letGo.map(r=>r.number),[1]);
 const other=M.mapSwapCandidate(st.runs,chosen.letGo,st.selected);assert.equal(other.number,2);
 M.letGoMaps(other);assert.equal(M.takeBackMaps(two[0]),true);assert.deepEqual(withMaps(two),[1,3]);
});

test('the run list keeps 20 runs: pinned runs stay, a 21st run replaces the oldest unpinned one',()=>{
 const runs=Array.from({length:20},(_,i)=>runOf(i+1,3,{pinned:i===0}));
 const next=M.appendMultiphysicsRun(runs,runOf(21,3));assert.equal(next.length,20);assert.deepEqual(next.map(r=>r.number).slice(0,3),[1,3,4]);
 assert.throws(()=>M.appendMultiphysicsRun(runs.map(r=>({...r,pinned:true})),runOf(21,3)),{message:'All 20 runs are pinned. Unpin a run before running again.'});
 assert.equal(M.MULTIPHYSICS_RUN_LIMIT,20);assert.equal(M.PREVIOUS_MULTIPHYSICS_RUN_LIMIT,6);
});

test('HK15 (shared core): the optical order and choice are the budget module\'s, with the same constants',()=>{
 assert.equal(N.FIELD_BUDGET_BYTES,B.FIELD_BUDGET_BYTES);assert.equal(N.FIELD_BUDGET_BYTES,16760832);assert.equal(N.mbText,B.mbText);assert.equal(N.MAX_SESSION_BYTES,B.MAX_SESSION_BYTES);
 const runs=[{job:'a',number:1,pinned:true,field:1},{job:'b',number:2,field:1},{job:'c',number:3,field:null},{job:'d',number:4,field:1}];
 assert.deepEqual(X.fieldOrder(runs,'b').map(r=>r.job),['b','a','d']);assert.deepEqual(X.fieldOrder(runs,'b',['d']).map(r=>r.job),['b','d','a']);
 assert.ok(read('workspace-retention.mjs').includes("budgetChoose(fieldOrder(runs,selected,first),{base,bytes,selected,budget})"));
});
