// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
// The session files of K1 and K9 (design "Search near n_eff for closed-window runs"): each session
// fixture below, read and written again, {name: the written text}. Run once with the static folder
// of main 13f07f4 (before session version 11) to write sessions-rewritten-13f07f4.json:
//   node closed_sessions.mjs <static folder URL>/ <fixtures folder> > sessions-rewritten-13f07f4.json
// tests/simcase/studio_closed_target_page.cjs writes the same files with this Studio.
import fs from 'node:fs';import path from 'node:path';
export const SESSIONS=['optical-v7-one.json','optical-v7-three.json','optical-v6-three.json','optical-v10-open-f8ece10.json','optical-v10-open-full-083e151.json'];
// a version 9 session of synthetic runs: 3 of 8 modes with the engine's values, and 1 mode of 1
export function synthetic(N,P){
 const setup={materials:{Core:'Silicon',Oxide:'Silica',Heater:''},temperature:293.15,cooling:'',fixed:'',terminal:''};
 const input=P.snapshot({width:500,voltage:1,electric:false,heat:false,structure:false,optics:true,wavelength:1550,coreMesh:30},setup);
 const field=k=>({node_coordinates:[[0,0],[1e-6,0],[0,1e-6],[1e-6,1e-6]],triangles:[[0,1,2],[1,3,2]],
  real:Array.from({length:k},(_,m)=>[[1,0.25*m,-0],[0.5,-0.125,1e-3*(m+1)]]),imag:Array.from({length:k},(_,m)=>[[0,1e-9*m,0],[-2e-3,0,0]])});
 const run=(job,k,asked)=>N.validateRun({job,completedAt:'2026-11-22T01:00:00.000Z',settings:N.opticalSettings(1550,30,asked),input,
  effective_index:Array.from({length:k},(_,m)=>2.9-0.17*m),field:field(k),origin:'local',serverVersion:'0.0.0',
  te_polarization_fraction:Array.from({length:k},(_,m)=>0.9-0.1*m),effective_area:Array.from({length:k},(_,m)=>2e-13*(m+1))});
 const runs=[run('0000000a',3,8),run('0000000b',1,1)];
 return N.sessionText(input,runs,runs[0].job,[runs[0].job,runs[1].job],{mode:0,component:'magnitude',window:'Core region'});
}
export function rewrite(N,folder,P){
 const out={'synthetic version 9':synthetic(N,P)};
 for(const name of SESSIONS){
  const s=N.parseSession(fs.readFileSync(path.join(folder,name),'utf8'));
  out[name]=N.sessionText(s.input,s.runs,s.selected,s.comparison,s.view);
 }
 return out;
}
if(process.argv[2]){
 const N=await import(process.argv[2]+'workspace-notebook.mjs'),P=await import(process.argv[2]+'workspace-project.mjs');
 process.stdout.write(JSON.stringify(rewrite(N,process.argv[3],P),null,1)+'\n');
}
