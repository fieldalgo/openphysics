// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
// The values-only runs the browser stages add before they reach the 20-run limit (design "Keeping
// more runs"): fourteen closed-window runs of a design no stage computes (a 640 × 210 nm core,
// 1510 nm, core mesh 52 nm), two modes each, numbered 1 to 14, pinned, without fields (n_eff, the
// TE fractions and the effective areas only), so Add runs from file adds no field bytes, the stage's
// own runs stay the oldest and the only unpinned ones (the limit drops and swaps the same runs as at
// six runs). Written by this Studio as optical-values-only-14.json:
//   node values_only_sessions.mjs <static folder URL>/ > optical-values-only-14.json
export const COUNT=14;
export function valuesOnlySession(N,P){
 const setup={materials:{Core:'Silicon',Oxide:'Silica',Heater:''},temperature:293.15,cooling:'',fixed:'',terminal:''};
 const input=P.snapshot({width:640,height:210,voltage:1,electric:false,heat:false,structure:false,optics:true,wavelength:1510,coreMesh:52},setup);
 input.model.shapes=[{name:'Core',type:'rect',material:'Silicon',x:-320,y:0,w:640,h:210}];
 const runs=Array.from({length:COUNT},(_,i)=>Object.assign(N.validateRun({job:(0xc0000001+i).toString(16),completedAt:new Date(Date.UTC(2026,10,25,9,i)).toISOString(),
  settings:N.opticalSettings(1510,52,2),input:P.validateProject(input),effective_index:[2.61-0.001*i,1.93-0.001*i],field:null,origin:'imported',pinned:true,serverVersion:'0.0.0',
  te_polarization_fraction:[0.97,0.04],effective_area:[1.6e-13,2.9e-13]}),{number:i+1}));
 return N.sessionText(P.validateProject(input),runs,runs.at(-1).job,[runs[0].job,runs.at(-1).job],{mode:0,component:'magnitude',window:'Core region'});
}
if(process.argv[2]){
 const N=await import(process.argv[2]+'workspace-notebook.mjs'),P=await import(process.argv[2]+'workspace-project.mjs');
 process.stdout.write(valuesOnlySession(N,P));
}
