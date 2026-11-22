// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
import {designSummary,shapesBlock} from './workspace-shapes.mjs';
import {originText} from './workspace-multiphysics.mjs';

// The words for a result whose inputs are not the current ones (optical, heat, Joule heating):
// neutral, since an opened file or another selected run differs without any edit, and naming
// both sides of each part that differs. runParts and currentParts: the same parts, in order,
// as text (for example the geometry, the wavelength and the core mesh).
export const SAME_INPUTS='Result for the current inputs';
export function inputsDifferText(runParts,currentParts){
 const differ=runParts.map((part,i)=>part!==currentParts[i]?i:-1).filter(i=>i>=0);
 if(!differ.length)return 'Current inputs differ from this run in other settings';
 return `Current inputs differ from this run: this run ${differ.map(i=>runParts[i]).join(' · ')}, current ${differ.map(i=>currentParts[i]).join(' · ')}`;
}
// The parts of an optical input the words above compare.
export const opticalInputParts=input=>[designSummary(input.model),`λ ${input.model.wavelength} nm`,`core mesh ${input.model.coreMesh} nm`];
// Readiness describes the current editor and retained artifacts, not accuracy.
// viewed: the run Results shows (the selected run); the Results step describes that run, so the
// step bar, the result and its settings agree. Without it, the newest run of these inputs.
export function opticalWorkflow({input,invalid=false,block='',busy=false,pending=false,resumeBlocked=false,mesh=null,runs=[],viewed}){
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
  viewed?{id:'Results',state:viewed.signature===signature?'ready':'attention',detail:viewed.signature===signature?'Result for these inputs':'Current inputs differ from this run'}
  :{id:'Results',state:currentRun?'ready':runs.length?'attention':'empty',detail:currentRun?'Result for these inputs':runs.length?'Inputs changed since this result':'No run yet'}
 ];
}
// The last-run state of the optical inputs, in the words of the multiphysics model. A run is
// numbered by its place in the run list (oldest = 1). 'current': a run solved these exact
// inputs; 'stale': runs exist but none of these inputs; 'none' before any run. origin: where the
// current run came from when it was not computed in this tab ('imported' or 'recovered').
export function opticalFreshness(input,runs=[]){
 const signature=JSON.stringify(input),index=runs.findLastIndex(run=>run.signature===signature);
 const origin=runs[index]?.origin;
 if(index>=0)return origin==='imported'||origin==='recovered'?{state:'current',run:index+1,origin}:{state:'current',run:index+1};
 return runs.length?{state:'stale',run:runs.length}:{state:'none',run:null};
}
// The dock heading and the ready footer for that state: both name the same run.
export function opticalSequenceHeading({state,run,origin}){
 if(state==='current'&&originText(origin))return `Run ${run} · ${originText(origin)}`;
 if(state==='current')return `Run ${run} · solved from the current inputs`;
 if(state==='stale')return `Inputs changed since run ${run} · press Run to update`;
 return 'Nothing is computed until you press Run';
}
export function opticalReadyStatus({state,run,origin}){
 if(state==='current'&&originText(origin))return `Run ${run} · ${originText(origin)} · press Run to compute it here`;
 if(state==='current')return `Run ${run} · solved from the current inputs · press Run to solve again`;
 if(state==='stale')return `Inputs changed since run ${run} · press Run to update`;
 return 'Optical adapter ready · explicit Run required';
}
