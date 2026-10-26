// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0

// Readiness describes the current editor and retained artifacts, not accuracy.
export function opticalWorkflow({input,invalid=false,block='',busy=false,pending=false,resumeBlocked=false,mesh=null,runs=[]}){
 const signature=JSON.stringify(input);
 const materialOK=['Silicon','Silicon nitride'].includes(input.setup.materials.Core)&&input.setup.materials.Oxide==='Silica';
 const currentRun=runs.findLast(run=>run.signature===signature);
 const study=invalid?'Correct input draft':busy?'Computing':pending?(resumeBlocked?'Detach unavailable job':'Resume or detach job'):block?'Unavailable':'Ready to run';
 return [
  {id:'Geometry',state:invalid?'attention':'ready',detail:invalid?'Correct input draft':`${input.model.width} × ${input.model.height} nm`},
  {id:'Materials',state:materialOK?'ready':'attention',detail:materialOK?input.setup.materials.Core:'Assign supported materials'},
  {id:'Mesh',state:mesh?.signature===signature?'ready':mesh?'attention':'optional',detail:mesh?.signature===signature?'Preview current':mesh?'Preview earlier inputs':'Optional preview'},
  {id:'Study',state:invalid?'attention':busy?'busy':pending||block?'attention':'ready',detail:study},
  {id:'Results',state:currentRun?'ready':runs.length?'attention':'empty',detail:currentRun?'Current input result':runs.length?'Earlier inputs only':'No completed run'}
 ];
}
