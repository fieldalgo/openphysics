// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
// The session files of design "Stable run numbers and the project name after recovery".
//
// numberedSession(N, P, folder): the version 12 session of K2, six runs numbered 3, 5, 6, 7, 8 and 9
// (Run 3 pinned; Run 5 an open run, Run 6 a closed-window search run, Run 8 without fields), written
// by this Studio: optical-v12-numbers.json. Its runs were read from a file (origin "imported"), as
// every run of a file read again is, so the file read and written again is its own bytes. Written again with
//   node numbered_sessions.mjs write <static folder URL>/ <fixtures folder> > optical-v12-numbers.json
//
// readWith(staticUrl, folder): what a Studio reads from it (K3) and from version 11 recovery records
// with and without the browser-only `project` (K9). Run once with the static folder of main fc654fe
// (before session version 12) to write refusals-v12-fc654fe.json:
//   git worktree add <tmp> fc654fe
//   node numbered_sessions.mjs read file://<tmp>/packages/simcase/src/simcase/studio/static/ <fixtures folder> > refusals-v12-fc654fe.json
import fs from 'node:fs';import path from 'node:path';

export const NUMBERS=Object.freeze([3,5,6,7,8,9]);
const VIEW={mode:0,component:'magnitude',window:'Core region'};
const field=k=>({node_coordinates:[[0,0],[1e-6,0],[0,1e-6],[1e-6,1e-6]],triangles:[[0,1,2],[1,3,2]],
 real:Array.from({length:k},(_,m)=>[[1,0.25*m,-0],[0.5,-0.125,1e-3*(m+1)]]),imag:Array.from({length:k},(_,m)=>[[0,1e-9*m,0],[-2e-3,0,0]])});
export function numberedRuns(N,P,folder){
 const setup={materials:{Core:'Silicon',Oxide:'Silica',Heater:''},temperature:293.15,cooling:'',fixed:'',terminal:''};
 const input=P.snapshot({width:500,voltage:1,electric:false,heat:false,structure:false,optics:true,wavelength:1550,coreMesh:30},setup);
 const open=N.parseSession(fs.readFileSync(path.join(folder,'optical-v10-open-f8ece10.json'),'utf8'));
 const base=(job,k,asked,extra={})=>({job,completedAt:`2026-11-24T0${job.at(-1)}:00:00.000Z`,settings:N.opticalSettings(1550,30,asked),input,
  effective_index:Array.from({length:k},(_,m)=>2.9-0.17*m),field:field(k),origin:'imported',serverVersion:'0.0.0',
  te_polarization_fraction:Array.from({length:k},(_,m)=>0.9-0.1*m),effective_area:Array.from({length:k},(_,m)=>2e-13*(m+1)),...extra});
 const records=[
  base('00000003',2,2,{pinned:true,label:'Reference'}),
  open.runs.find(r=>r.job==='2bed94e2'),
  base('00000006',2,4,{settings:N.closedTargetSettings(N.opticalSettings(1550,30,4),2.46)}),
  base('00000007',3,8),
  base('00000008',2,2,{field:null}),
  base('00000009',1,1,{label:'Narrow'}),
 ];
 return {input:open.input,runs:records.map((r,i)=>Object.assign(N.validateRun(r),{number:NUMBERS[i]}))};
}
export function numberedSession(N,P,folder){
 const {input,runs}=numberedRuns(N,P,folder);
 return N.sessionText(input,runs,runs[3].job,[runs[0].job,runs[3].job],VIEW);
}
const message=f=>{try{f();return null;}catch(e){return e.message;}};
// what the Studio at staticUrl reads: the K2 file alone, in a project and in a recovery record; and
// a version 11 recovery record with and without `project` (K9)
export async function readWith(staticUrl,folder){
 const load=name=>import(staticUrl+name);
 const N=await load('workspace-notebook.mjs'),P=await load('workspace-project.mjs'),PF=await load('workspace-project-file.mjs'),R=await load('workspace-notebook-recovery.mjs');
 const text=fs.readFileSync(path.join(folder,'optical-v12-numbers.json'),'utf8');
 const project=PF.writeProject({name:'both-models',savedAt:'2026-11-24T10:00:00.000Z',studio:'0.0.0',active:'m1',entries:[PF.projectEntry({id:'m1',kind:'workspace',title:'Optical waveguide',card:'optical',text})]}).text;
 const record=session=>({version:1,savedAt:'2026-11-24T10:00:00.000Z',session});
 // the page reads the latest record before it adopts it (workspace-app.mjs, loadNotebookRecovery):
 // a record it cannot read is not adopted, so the store refuses this tab's next save
 const store=R.indexedNotebookStore({open(){throw new Error('no database');}});
 try{R.readNotebookRecovery(record(text));store.adopt(record(text));}catch{}
 const adopted=await store.save(record(text)).then(()=>true,e=>e.message!=='Read browser recovery before saving.');
 // the same six runs written by that Studio (version 11 at fc654fe: a closed-window search run), in a
 // record with and without project
 const {input,runs}=numberedRuns(N,P,folder),v11=N.sessionText(input,runs,null,[null,null],VIEW);
 const plain=R.readNotebookRecovery(record(v11)),named=R.readNotebookRecovery({...record(v11),project:{name:'both-models',from:'file'}});
 const dump=x=>JSON.stringify(x,(k,v)=>Array.isArray(v)&&v.length>64?`[${v.length} values]`:v);
 return {
  session:message(()=>N.parseSession(text)),
  project:message(()=>PF.readProject(project)),
  recovery:message(()=>R.readNotebookRecovery(record(text))),
  adopted,
  'version 11 record':{version:JSON.parse(v11).version,'equal with and without project':dump(plain)===dump(named)&&Object.keys(plain).join()===Object.keys(named).join(),keys:Object.keys(plain)},
 };
}
if(process.argv[2]==='write'){
 const N=await import(process.argv[3]+'workspace-notebook.mjs'),P=await import(process.argv[3]+'workspace-project.mjs');
 process.stdout.write(numberedSession(N,P,process.argv[4]));
}else if(process.argv[2]==='read'){
 process.stdout.write(JSON.stringify(await readWith(process.argv[3],process.argv[4]),null,1)+'\n');
}
