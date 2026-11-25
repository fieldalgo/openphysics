// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
// The session files of the heated model's run retention (design "Keeping more runs", section 7,
// slice H1; multiphysics session version 15).
//
// heatedV8Sessions(M, MP): sessions of 0, 1, 2 and 6 runs of small multiphysics runs (maps kept and
// not kept, a without-heater result, names and pins, -0), as states for a Studio's writer. Written by
// main ddb09a1 (the last Studio before version 15) to multiphysics-v8-ddb09a1.json, which HK2 reads:
//   git worktree add <tmp> ddb09a1
//   node heated_sessions.mjs write-v8 file://<tmp>/packages/simcase/src/simcase/studio/static/ > multiphysics-v8-ddb09a1.json
//
// thirteenRuns(M, dir): the version 15 session of HK3, runs 2 and 4 to 15 of real template results
// (tools/studio_heated_retention.mjs engine; heater powers 1e14 to 9e14, Modes to find 2 and 4), runs
// 4, 6, 8, 10 and 12 without their maps, Run 5 named and pinned; written by this Studio:
//   node heated_sessions.mjs write-v15 <static folder URL>/ <engine results folder> > multiphysics-v15-thirteen-runs.json
//
// readWith(staticUrl, folder): what a Studio reads of that file alone, in a project file and in a
// browser recovery record, and whether its store adopts the record (HK4). Run once with main ddb09a1:
//   node heated_sessions.mjs read file://<tmp>/packages/simcase/src/simcase/studio/static/ <fixtures folder> > refusals-v15-ddb09a1.json
import fs from 'node:fs';import path from 'node:path';

const VIEW={page:'Results',selection:'results:modes1',index_map:'change',baseline_option:true};
const documentOf=(power='2e14 W/m^3')=>({openphysics:'0.3/multiphysics.1',name:'Heated silicon waveguide',
 geometry:{version:1,components:{xs:{dimension:'2d',length_unit:'um',depth:null,domain:{xmin:-3,xmax:3,ymin:-2,ymax:2.5},background:{material:'physmat:SiO2'},
  features:[{name:'core',type:'rect',x:-0.25,y:0,w:0.5,h:0.22,material:'physmat:Si'}]}}},
 materials:{},mesh:{element_size:'0.25 um'},
 physics:{heat1:{type:'thermal.steady2d',prescribed_temperature:{bottom:'300 K'},heat_source_density:{core:power}},modes1:{type:'em.modes2d',formulation:'scalar',vacuum_wavelength:'1550 nm',mode_count:1}},
 couplings:{heat1_to_modes1:{from:'heat1.temperature',to:'modes1.temperature',transfer:'same_mesh'}}});
const resultOf=(T,neff)=>{
 const tri=[[0,1,2],[1,3,2]],mean=tri.map(t=>(T[t[0]]+T[t[1]]+T[t[2]])/3);
 return {result:'multiphysics-run-v1',name:'Heated silicon waveguide',solve_order:[['heat1'],['modes1']],
  couplings:{heat1_to_modes1:{from:'heat1.temperature',to:'modes1.temperature',quantity:'temperature',unit:'K',transfer:'same_mesh',location:'node',mesh_signature:'match',max_abs_difference:{value:0,unit:'K'},conservation_residual:null}},
  loops:[],timing:{heat1:0.1,modes1:0.2},diagnostics:[],
  mesh:{node_coordinates:[[0,0],[1e-6,0],[0,1e-6],[1e-6,1e-6]],field_units:{node_coordinates:'m'},triangles:tri,regions:[0,1],region_names:['background','core']},
  physics:{heat1:{type:'thermal.steady2d',temperature:{unit:'K',location:'node',values:T},range:{min:Math.min(...T),max:Math.max(...T),unit:'K'},summary:{}},
   modes1:{type:'em.modes2d',effective_index:{unit:'1',values:[[neff]]},vacuum_wavelength:{unit:'m',values:[1.55e-6]},summary:{},
    coupled:{temperature:{unit:'K',location:'element',values:mean},refractive_index:{location:'element',n:[3.4757,1.444],k:null},index_change:[1.8e-5,-0]}}}};
};
const hex=n=>'mp-'+n.toString(16).padStart(12,'0');
function runOf(M,n,{label='',pinned=false,valuesOnly=false}={}){
 const T=[300,300+n/2,302.25+n*1e-3,-0],power=`${n}e14 W/m^3`;
 const run={job:hex(0x3f2a9c1d7e00+n),number:n,label,pinned,completedAt:`2026-11-22T10:${String(10+n).padStart(2,'0')}:03.120Z`,serverVersion:'0.0.2',doc:documentOf(power),
  events:[{event:'physics_started',physics:'heat1'}],order:[['heat1'],['modes1']],result:resultOf(T,2.4456501286415855+n*1e-5),maps:'kept',origin:'imported'};
 if(!valuesOnly)return run;
 // a run read from a file without its maps: the record's result and counts
 const record=M.sessionRun(run,false);return {...run,maps:'not kept',counts:record.counts,result:record.result};
}
const baselineOf=(MP,doc)=>({job:'mp-77a01b2c3d4e',completedAt:'2026-11-22T10:15:04.300Z',document:MP.uncoupledDocument(doc,'modes1'),
 result:{type:'em.modes2d',effective_index:{unit:'1',values:[[2.443499265702046]]},vacuum_wavelength:{unit:'m',values:[1.55e-6]},summary:{}}});
export function heatedV8Sessions(M,MP){
 const state=(runs,{baseline=true,selected=runs.at(-1)?.job??null}={})=>{const doc=runs.at(-1)?.doc??documentOf();
  return {document:doc,runs,baselines:baseline?{modes1:baselineOf(MP,doc)}:{},selected,view:selected?VIEW:{...VIEW,page:'Model',selection:'model'}};};
 return {
  empty:state([],{baseline:false}),
  one:state([runOf(M,1,{label:'Heater 10 mW',pinned:true})]),
  two:state([runOf(M,1,{valuesOnly:true}),runOf(M,2,{label:'Reference',pinned:true})]),
  six:state([1,2,3,4,5,6].map(n=>runOf(M,n,{pinned:n===2||n===5,label:n===5?'kept 5':'',valuesOnly:n===1||n===4})),{selected:hex(0x3f2a9c1d7e00+3)}),
 };
}
export async function thirteenRuns(M,dir){
 const numbers=[2,...Array.from({length:12},(_,i)=>i+4)],runs=[];
 for(const [i,number] of numbers.entries()){
  const name=(i%2?'tpl4-p':'tpl-p')+(1+i%9),{document,events}=JSON.parse(fs.readFileSync(path.join(dir,name+'.document.json'),'utf8'));
  const result=JSON.parse(fs.readFileSync(path.join(dir,name+'.one-a.result.json'),'utf8'));
  let run={job:hex(0xc0ffee000000+number),number,label:number===5?'Heater 5e14':'',pinned:number===5,completedAt:new Date(Date.UTC(2026,10,25,2,number)).toISOString(),serverVersion:'0.0.2',
   doc:document,events,order:result.solve_order,result,maps:'kept',origin:'imported'};
  if([4,6,8,10,12].includes(number)){const record=M.sessionRun(run,false);run={...run,maps:'not kept',counts:record.counts,result:record.result};}
  runs.push(run);
 }
 return {document:runs.at(-1).doc,runs,baselines:{},selected:runs.at(-1).job,view:{...VIEW,baseline_option:false}};
}
const message=f=>{try{f();return null;}catch(e){return e.message;}};
export async function readWith(staticUrl,folder){
 const load=name=>import(staticUrl+name);
 const N=await load('workspace-notebook.mjs'),PF=await load('workspace-project-file.mjs'),R=await load('workspace-notebook-recovery.mjs');
 const text=fs.readFileSync(path.join(folder,'multiphysics-v15-thirteen-runs.json'),'utf8');
 const project=PF.writeProject({name:'heated',savedAt:'2026-11-25T10:00:00.000Z',studio:'0.0.0',active:'m1',entries:[PF.projectEntry({id:'m1',kind:'multiphysics',title:'Heated silicon waveguide',card:'heated-waveguide',text})]}).text;
 const record=session=>({version:1,savedAt:'2026-11-25T10:00:00.000Z',session});
 const store=R.indexedNotebookStore({open(){throw new Error('no database');}});
 try{R.readNotebookRecovery(record(text));store.adopt(record(text));}catch{}
 const adopted=await store.save(record(text)).then(()=>true,e=>e.message!=='Read browser recovery before saving.');
 return {session:message(()=>N.parseSession(text)),project:message(()=>PF.readProject(project)),recovery:message(()=>R.readNotebookRecovery(record(text))),adopted};
}
if(process.argv[2]==='write-v8'){
 const M=await import(process.argv[3]+'workspace-multiphysics-session.mjs'),MP=await import(process.argv[3]+'workspace-multiphysics.mjs');
 const out={};for(const [name,state] of Object.entries(heatedV8Sessions(M,MP)))out[name]=M.writeMultiphysicsSession(state).text;
 process.stdout.write(JSON.stringify(out,null,1)+'\n');
}else if(process.argv[2]==='write-v15'){
 const M=await import(process.argv[3]+'workspace-multiphysics-session.mjs');
 process.stdout.write(M.writeMultiphysicsSession(await thirteenRuns(M,process.argv[4])).text);
}else if(process.argv[2]==='read'){
 process.stdout.write(JSON.stringify(await readWith(process.argv[3],process.argv[4]),null,1)+'\n');
}
