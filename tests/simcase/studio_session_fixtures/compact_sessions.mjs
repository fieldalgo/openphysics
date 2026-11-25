// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
// The session files of design "Compact field encoding" (optical session version 14).
//
// compactSession(N, P, E, folder): the version 14 session of F3, three runs numbered 3, 5 and 8,
// written by this Studio: optical-v14-compact.json.
//   Run 3  an open run with its engine field (a0000004 of optical-v10-open-full-083e151.json: 776
//          triangles, 422 nodes, 2 modes), kept compact;
//   Run 5  a closed run of 2 modes (pinned, named "Reference") whose small field holds -0, values
//          that round to single precision and 5 nodes (so the coordinates' base64 is padded), kept
//          compact;
//   Run 8  a closed run kept as text (nested numbers), as a run imported before the conversion is.
// The compact runs store the TE fractions and effective areas they showed before (computed from the
// float64 field where the run held none). Its runs were read from a file (origin "imported"), so the
// file read and written again is its own bytes. Written again with
//   node compact_sessions.mjs write <static folder URL>/ <fixtures folder> > optical-v14-compact.json
//
// readWith(staticUrl, folder): what a Studio reads from it alone, in a project file and in a browser
// recovery record (F4), and whether it adopts that record. Run once with the static folder of main
// 499a0d3 (the last Studio before session version 14) to write refusals-v14-499a0d3.json:
//   git worktree add <tmp> 499a0d3
//   node compact_sessions.mjs read file://<tmp>/packages/simcase/src/simcase/studio/static/ <fixtures folder> > refusals-v14-499a0d3.json
import fs from 'node:fs';import path from 'node:path';

export const NUMBERS=Object.freeze([3,5,8]);
const VIEW={mode:0,component:'magnitude',window:'Core region'};
// 5 nodes, 3 triangles, 2 modes: -0, 0.1 (not a float32), 1e-9, a value at float32's rounding midpoint
const smallField=()=>({node_coordinates:[[0,0],[1e-6,0],[0,1e-6],[1e-6,1e-6],[5e-7,1.5e-6]],triangles:[[0,1,2],[1,3,2],[2,3,4]],
 real:[[[1,0.1,-0],[0.5,-0.125,1e-3],[0.3,0.2,0.1]],[[0.25,1,1e-9],[-0.7,0.6,0],[1+2**-24,0.4,-0.05]]],
 imag:[[[0,1e-9,0],[-2e-3,0,0],[0.01,-0.02,0.03]],[[0,0,-0],[1/3,2/3,0],[0.001,0,0.999]]]});
const textField=()=>({node_coordinates:[[0,0],[1e-6,0],[0,1e-6],[1e-6,1e-6]],triangles:[[0,1,2],[1,3,2]],
 real:[[[1,0,-0],[0.5,-0.125,1e-3]],[[1,0.25,-0],[0.5,-0.125,2e-3]]],imag:[[[0,0,0],[-2e-3,0,0]],[[0,1e-9,0],[-2e-3,0,0]]]});
export function compactRuns(N,P,folder){
 const setup={materials:{Core:'Silicon',Oxide:'Silica',Heater:''},temperature:293.15,cooling:'',fixed:'',terminal:''};
 const input=P.snapshot({width:500,voltage:1,electric:false,heat:false,structure:false,optics:true,wavelength:1550,coreMesh:30},setup);
 const open=N.parseSession(fs.readFileSync(path.join(folder,'optical-v10-open-full-083e151.json'),'utf8')).runs.find(r=>r.job==='a0000004');
 const base=(job,hour,extra={})=>({job,completedAt:`2026-11-25T${String(hour).padStart(2,'0')}:00:00.000Z`,settings:N.opticalSettings(1550,30,2),input,
  effective_index:[2.9,2.73],field:textField(),origin:'imported',serverVersion:'0.0.0',te_polarization_fraction:[0.9,0.8],effective_area:[2e-13,4e-13],...extra});
 const runs=[open,base('00000005',5,{pinned:true,label:'Reference',field:smallField()}),base('00000008',8)].map(r=>N.validateRun(r));
 for(const i of [0,1])N.compactRunField(runs[i]);
 return {input:N.parseSession(fs.readFileSync(path.join(folder,'optical-v10-open-full-083e151.json'),'utf8')).input,runs:runs.map((r,i)=>Object.assign(r,{number:NUMBERS[i]}))};
}
export function compactSession(N,P,folder){
 const {input,runs}=compactRuns(N,P,folder);
 return N.sessionText(input,runs,runs[1].job,[runs[0].job,runs[1].job],VIEW);
}
const message=f=>{try{f();return null;}catch(e){return e.message;}};
// what the Studio at staticUrl reads: the F3 file alone, in a project and in a recovery record, and
// whether the store adopts that record (as retained_sessions.mjs reads the version 13 file)
export async function readWith(staticUrl,folder){
 const load=name=>import(staticUrl+name);
 const N=await load('workspace-notebook.mjs'),PF=await load('workspace-project-file.mjs'),R=await load('workspace-notebook-recovery.mjs');
 const text=fs.readFileSync(path.join(folder,'optical-v14-compact.json'),'utf8');
 const project=PF.writeProject({name:'both-models',savedAt:'2026-11-25T10:00:00.000Z',studio:'0.0.0',active:'m1',entries:[PF.projectEntry({id:'m1',kind:'workspace',title:'Optical waveguide',card:'optical',text})]}).text;
 const record=session=>({version:1,savedAt:'2026-11-25T10:00:00.000Z',session});
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
 process.stdout.write(compactSession(N,P,process.argv[4]));
}else if(process.argv[2]==='read'){
 process.stdout.write(JSON.stringify(await readWith(process.argv[3],process.argv[4]),null,1)+'\n');
}
