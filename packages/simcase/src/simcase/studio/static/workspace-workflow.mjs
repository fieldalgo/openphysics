// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
import {designSummary,shapesBlock} from './workspace-shapes.mjs';

// Readiness describes the current editor and retained artifacts, not accuracy.
export function opticalWorkflow({input,invalid=false,block='',busy=false,pending=false,resumeBlocked=false,mesh=null,runs=[]}){
 const signature=JSON.stringify(input);
 const materialBlock=input.setup.materials.Oxide!=='Silica'?'Background must be silica':shapesBlock(input.model.shapes),materialOK=!materialBlock;
 const currentRun=runs.findLast(run=>run.signature===signature);
 // A run of these exact inputs is done; an edit makes the study ready to run again.
 const state=invalid?'Correct input draft':busy?'Computing':pending?(resumeBlocked?'Detach unavailable job':'Resume or detach job'):block?'Unavailable':currentRun?'Run complete':'Ready to run';
 // The wavelength leads the Study step, where it is set for the run; the step bar shows it as its
 // own control (wavelength), which opens the wavelength field.
 const wavelength=input.model.wavelength,study=Number.isFinite(wavelength)?`λ ${wavelength} nm · ${state}`:state;
 return [
  {id:'Geometry',state:invalid?'attention':'ready',detail:invalid?'Correct input draft':designSummary(input.model)},
  {id:'Materials',state:materialOK?'ready':'attention',detail:materialOK?[...new Set(input.model.shapes.map(s=>s.material))].join(', ')+' in silica':'Assign supported materials'},
  {id:'Mesh',state:mesh?.signature===signature?'ready':mesh?'attention':'optional',detail:mesh?.signature===signature?'Preview current':mesh?'Inputs changed since preview':'Optional preview'},
  {id:'Study',state:invalid?'attention':busy?'busy':pending||block?'attention':'ready',detail:study,summary:state,wavelength:Number.isFinite(wavelength)?`λ ${wavelength} nm`:null},
  {id:'Results',state:currentRun?'ready':runs.length?'attention':'empty',detail:currentRun?'Result for these inputs':runs.length?'Inputs changed since this result':'No run yet'}
 ];
}
// The last-run state of the optical inputs, in the words of the multiphysics model. A run is
// numbered by its place in the run list (oldest = 1). 'current': a run solved these exact
// inputs; 'stale': runs exist but none of these inputs; 'none' before any run.
export function opticalFreshness(input,runs=[]){
 const signature=JSON.stringify(input),index=runs.findLastIndex(run=>run.signature===signature);
 if(index>=0)return {state:'current',run:index+1};
 return runs.length?{state:'stale',run:runs.length}:{state:'none',run:null};
}
// The dock heading and the ready footer for that state: both name the same run.
export function opticalSequenceHeading({state,run}){
 if(state==='current')return `Run ${run} · solved from the current inputs`;
 if(state==='stale')return `Inputs changed since run ${run} · press Run to update`;
 return 'Nothing is computed until you press Run';
}
export function opticalReadyStatus({state,run}){
 if(state==='current')return `Run ${run} · solved from the current inputs · press Run to solve again`;
 if(state==='stale')return `Inputs changed since run ${run} · press Run to update`;
 return 'Optical adapter ready · explicit Run required';
}
