// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
// The session files of design "Keeping more runs" (optical session version 13).
//
// retainedSession(N, P, folder): the version 13 session of K3, nine runs numbered 2 and 4 to 11 (Run 4
// pinned; Run 5 an open run, Run 6 a closed-window search run; Runs 5, 7, 8, 9 and 10 without
// fields), written by this Studio: optical-v13-nine-runs.json. Its runs were read from a file (origin
// "imported"), as every run of a file read again is, so the file read and written again is its own
// bytes. Written again with
//   node retained_sessions.mjs write <static folder URL>/ <fixtures folder> > optical-v13-nine-runs.json
//
// readWith(staticUrl, folder): what a Studio reads from it alone, in a project file and in a browser
// recovery record (K4), and whether it adopts that record. Run once with the static folder of main
// 3f16709 (the last Studio before session version 13) to write refusals-v13-3f16709.json:
//   git worktree add <tmp> 3f16709
//   node retained_sessions.mjs read file://<tmp>/packages/simcase/src/simcase/studio/static/ <fixtures folder> > refusals-v13-3f16709.json
import fs from 'node:fs';import path from 'node:path';

export const NUMBERS=Object.freeze([2,4,5,6,7,8,9,10,11]);
const VIEW={mode:0,component:'magnitude',window:'Core region'};
const field=k=>({node_coordinates:[[0,0],[1e-6,0],[0,1e-6],[1e-6,1e-6]],triangles:[[0,1,2],[1,3,2]],
 real:Array.from({length:k},(_,m)=>[[1,0.25*m,-0],[0.5,-0.125,1e-3*(m+1)]]),imag:Array.from({length:k},(_,m)=>[[0,1e-9*m,0],[-2e-3,0,0]])});
export function retainedRuns(N,P,folder){
 const setup={materials:{Core:'Silicon',Oxide:'Silica',Heater:''},temperature:293.15,cooling:'',fixed:'',terminal:''};
 const input=P.snapshot({width:500,voltage:1,electric:false,heat:false,structure:false,optics:true,wavelength:1550,coreMesh:30},setup);
 const open=N.parseSession(fs.readFileSync(path.join(folder,'optical-v10-open-f8ece10.json'),'utf8'));
 const base=(job,hour,k,asked,extra={})=>({job,completedAt:`2026-11-25T${String(hour).padStart(2,'0')}:00:00.000Z`,settings:N.opticalSettings(1550,30,asked),input,
  effective_index:Array.from({length:k},(_,m)=>2.9-0.17*m),field:field(k),origin:'imported',serverVersion:'0.0.0',
  te_polarization_fraction:Array.from({length:k},(_,m)=>0.9-0.1*m),effective_area:Array.from({length:k},(_,m)=>2e-13*(m+1)),...extra});
 const records=[
  base('00000002',2,2,2),
  base('00000004',4,2,2,{pinned:true,label:'Reference'}),
  open.runs.find(r=>r.job==='2bed94e2'),
  base('00000006',6,2,4,{settings:N.closedTargetSettings(N.opticalSettings(1550,30,4),2.46)}),
  base('00000007',7,3,8,{field:null}),
  base('00000008',8,2,2,{field:null}),
  base('00000009',9,1,1,{label:'Narrow',field:null}),
  base('0000000a',10,2,2,{field:null}),
  base('0000000b',11,2,4),
 ];
 return {input:open.input,runs:records.map((r,i)=>Object.assign(N.validateRun(r),{number:NUMBERS[i]}))};
}
export function retainedSession(N,P,folder){
 const {input,runs}=retainedRuns(N,P,folder);
 return N.sessionText(input,runs,runs[8].job,[runs[1].job,runs[8].job],VIEW);
}
const message=f=>{try{f();return null;}catch(e){return e.message;}};
// what the Studio at staticUrl reads: the K3 file alone, in a project and in a recovery record, and
// whether the store adopts that record (as numbered_sessions.mjs reads the version 12 file)
export async function readWith(staticUrl,folder){
 const load=name=>import(staticUrl+name);
 const N=await load('workspace-notebook.mjs'),PF=await load('workspace-project-file.mjs'),R=await load('workspace-notebook-recovery.mjs');
 const text=fs.readFileSync(path.join(folder,'optical-v13-nine-runs.json'),'utf8');
 const project=PF.writeProject({name:'both-models',savedAt:'2026-11-25T10:00:00.000Z',studio:'0.0.0',active:'m1',entries:[PF.projectEntry({id:'m1',kind:'workspace',title:'Optical waveguide',card:'optical',text})]}).text;
 const record=session=>({version:1,savedAt:'2026-11-25T10:00:00.000Z',session});
 // the page reads the latest record before it adopts it (workspace-app.mjs, loadNotebookRecovery):
 // a record it cannot read is not adopted, so the store refuses this tab's next save
 const store=R.indexedNotebookStore({open(){throw new Error('no database');}});
 try{R.readNotebookRecovery(record(text));store.adopt(record(text));}catch{}
 const adopted=await store.save(record(text)).then(()=>true,e=>e.message!=='Read browser recovery before saving.');
 return {
  session:message(()=>N.parseSession(text)),
  project:message(()=>PF.readProject(project)),
  recovery:message(()=>R.readNotebookRecovery(record(text))),
  adopted,
 };
}
if(process.argv[2]==='write'){
 const N=await import(process.argv[3]+'workspace-notebook.mjs'),P=await import(process.argv[3]+'workspace-project.mjs');
 process.stdout.write(retainedSession(N,P,process.argv[4]));
}else if(process.argv[2]==='read'){
 process.stdout.write(JSON.stringify(await readWith(process.argv[3],process.argv[4]),null,1)+'\n');
}
