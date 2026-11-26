// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
// The session files of design "Session versions 16 and 17" (multiphysics session version 17: compact
// heated maps, encoding "f32-offset-base64-v1").
//
// compactRuns(M) / compactHeatedSession(M): the version 17 session of HQ7 and HQ9, three runs of a
// strip result of 12 nodes and 20 triangles in two regions (background and core), numbered 2, 3 and 5:
//   Run 2  maps compact, named "Reference" and pinned: node temperatures over 300 to 305 K, n and
//          index_change per region, k null
//   Run 3  values only (maps not kept), as a run whose maps were let go
//   Run 5  maps compact with k, a -0 in index_change, and a region without triangles (base 0)
// Its runs were read from a file (origin "imported"), so the file read and written again is its own
// bytes. Written again with
//   node compact_heated_sessions.mjs write <static folder URL>/ > multiphysics-v17-compact.json
//
// readWith(staticUrl, folder): what a Studio reads of that file alone, in a project file and in a
// browser recovery record, and whether its store adopts the record (HQ10). Run once with the static
// folder of the merge base (the last Studio before session version 16) to write refusals-v17-<sha>.json:
//   git worktree add <tmp> <sha>
//   node compact_heated_sessions.mjs read file://<tmp>/packages/simcase/src/simcase/studio/static/ <fixtures folder> > refusals-v17-<sha>.json
import fs from 'node:fs';import path from 'node:path';

export const NUMBERS=Object.freeze([2,3,5]);
const VIEW={page:'Results',selection:'results:modes1',index_map:'change',baseline_option:false};
export const documentOf=(power='2e14 W/m^3')=>({openphysics:'0.3/multiphysics.1',name:'Heated silicon waveguide',
 geometry:{version:1,components:{xs:{dimension:'2d',length_unit:'um',depth:null,domain:{xmin:-3,xmax:3,ymin:-2,ymax:2.5},background:{material:'physmat:SiO2'},
  features:[{name:'core',type:'rect',x:-0.25,y:0,w:0.5,h:0.22,material:'physmat:Si'}]}}},
 materials:{},mesh:{element_size:'0.25 um'},
 physics:{heat1:{type:'thermal.steady2d',prescribed_temperature:{bottom:'300 K'},heat_source_density:{core:power}},modes1:{type:'em.modes2d',formulation:'scalar',vacuum_wavelength:'1550 nm',mode_count:1}},
 couplings:{heat1_to_modes1:{from:'heat1.temperature',to:'modes1.temperature',transfer:'same_mesh'}}});
/** A strip of n × 2 nodes and 2(n − 1) triangles, regions in blocks (core in the middle), with smooth
 * temperatures over 300 to 305 K and index maps of the server's form; withK adds an absorption map,
 * names adds region names without triangles. */
export function stripResult(n,{seed=1,withK=false,names=['background','core']}={}){
 const P=[],T=[],temp=[];
 for(let i=0;i<n;i++){P.push([i*1e-7,0],[i*1e-7,1e-7]);temp.push(300+5*Math.sin((i+seed)/n)**2+i*1e-3/3,300+5*Math.sin((i+seed+0.5)/n)**2+1/7);}
 for(let i=0;i+1<n;i++)T.push([2*i,2*i+2,2*i+1],[2*i+1,2*i+2,2*i+3]);
 const R=T.map((_,i)=>i>=T.length/4&&i<3*T.length/4?1:0),mean=T.map(t=>(temp[t[0]]+temp[t[1]]+temp[t[2]])/3);
 const dn=mean.map((v,i)=>R[i]?(v-300)*1.8e-4:0),nIndex=mean.map((v,i)=>(R[i]?3.4757:1.444)+dn[i]);
 if(withK)dn[0]=-0;
 const min=Math.min(...temp),max=Math.max(...temp);
 return {result:'multiphysics-run-v1',name:'Heated silicon waveguide',solve_order:[['heat1'],['modes1']],
  couplings:{heat1_to_modes1:{from:'heat1.temperature',to:'modes1.temperature',quantity:'temperature',unit:'K',transfer:'same_mesh',location:'node',mesh_signature:'match',max_abs_difference:{value:0,unit:'K'},conservation_residual:null}},
  loops:[],timing:{physics:{heat1:{value:0.1,unit:'s'},modes1:{value:0.2,unit:'s'}}},diagnostics:[],
  mesh:{node_coordinates:P,field_units:{node_coordinates:'m'},triangles:T,regions:R,region_names:names},
  physics:{heat1:{type:'thermal.steady2d',temperature:{unit:'K',location:'node',values:temp},range:{min,max,unit:'K'},summary:{}},
   modes1:{type:'em.modes2d',effective_index:{unit:'1',values:[[2.4456501286415855+seed*1e-6]]},vacuum_wavelength:{unit:'m',values:[1.55e-6]},summary:{},
    coupled:{temperature:{unit:'K',location:'element',values:mean},refractive_index:{location:'element',n:nIndex,k:withK?mean.map((v,i)=>R[i]?1e-6+(v-300)*1e-9:0):null},index_change:dn}}}};
}
const hex=n=>'mp-'+n.toString(16).padStart(12,'0');
export function compactRuns(M){
 const run=(number,extra={},options={})=>({job:hex(0x17c0a9000000+number),number,label:'',pinned:false,completedAt:`2026-11-26T10:${String(10+number).padStart(2,'0')}:03.120Z`,serverVersion:'0.0.2',
  doc:documentOf(`${number}e14 W/m^3`),events:[{event:'physics_started',physics:'heat1'}],order:[['heat1'],['modes1']],result:stripResult(6,{seed:number,...options}),maps:'kept',origin:'imported',...extra});
 const runs=[run(2,{label:'Reference',pinned:true}),run(3),run(5,{},{withK:true,names:['background','core','heater']})];
 for(const r of [runs[0],runs[2]])if(!M.compactRunMaps(r))throw new Error(`Run ${r.number}: maps not compact`);
 // Run 3: values only, as a file writes a run without its maps
 const record=M.sessionRun(runs[1],false);Object.assign(runs[1],{maps:'not kept',counts:record.counts,result:record.result});
 return runs;
}
export const compactHeatedState=M=>{const runs=compactRuns(M);return {document:runs.at(-1).doc,runs,baselines:{},selected:runs.at(-1).job,view:VIEW};};
export const compactHeatedSession=M=>M.writeMultiphysicsSession(compactHeatedState(M)).text;
const message=f=>{try{f();return null;}catch(e){return e.message;}};
export async function readWith(staticUrl,folder){
 const load=name=>import(staticUrl+name);
 const N=await load('workspace-notebook.mjs'),PF=await load('workspace-project-file.mjs'),R=await load('workspace-notebook-recovery.mjs');
 const text=fs.readFileSync(path.join(folder,'multiphysics-v17-compact.json'),'utf8');
 const project=PF.writeProject({name:'heated',savedAt:'2026-11-26T10:00:00.000Z',studio:'0.0.0',active:'m1',entries:[PF.projectEntry({id:'m1',kind:'multiphysics',title:'Heated silicon waveguide',card:'heated-waveguide',text})]}).text;
 const record=session=>({version:1,savedAt:'2026-11-26T10:00:00.000Z',session});
 const store=R.indexedNotebookStore({open(){throw new Error('no database');}});
 try{R.readNotebookRecovery(record(text));store.adopt(record(text));}catch{}
 const adopted=await store.save(record(text)).then(()=>true,e=>e.message!=='Read browser recovery before saving.');
 return {session:message(()=>N.parseSession(text)),project:message(()=>PF.readProject(project)),recovery:message(()=>R.readNotebookRecovery(record(text))),adopted};
}
if(process.argv[2]==='write'){
 const M=await import(process.argv[3]+'workspace-multiphysics-session.mjs');
 process.stdout.write(compactHeatedSession(M));
}else if(process.argv[2]==='read'){
 process.stdout.write(JSON.stringify(await readWith(process.argv[3],process.argv[4]),null,1)+'\n');
}
