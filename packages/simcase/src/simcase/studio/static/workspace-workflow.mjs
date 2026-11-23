// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
import {designSummary,shapesBlock,geometryWords} from './workspace-shapes.mjs';
import {inputChanges} from './workspace-inputs.mjs';
import {originText} from './workspace-multiphysics.mjs';
import {studySignature} from './workspace-notebook.mjs';

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
// The line under a result's heading: whether the current inputs are the run's, then the run's
// inputs, each part named once: a part that differs is named with both values, the others after
// "unchanged" ("…, current 700 × 300 nm · Silicon; unchanged: λ 1550 nm · core mesh 30 nm").
export function runInputsLine(runParts,currentParts){
 const same=runParts.filter((part,i)=>part===currentParts[i]);
 if(same.length===runParts.length)return [SAME_INPUTS,...runParts].join(' · ');
 return inputsDifferText(runParts,currentParts)+(same.length?'; unchanged: '+same.join(' · '):'');
}
// The parts of an optical input the words above compare.
export const opticalInputParts=input=>[designSummary(input.model),`λ ${input.model.wavelength} nm`,`core mesh ${input.model.coreMesh} nm`];
// What the next run computes, in the Study panel: the current inputs, whatever run Results shows.
// "Next run uses 700 × 300 nm · Silicon · λ 1550 nm · core mesh 30 nm · Modes to find 2", with
// " · group index on" when the group index option is on.
export const nextRunText=(input,modeCount,groupIndex=false)=>`Next run uses ${[...opticalInputParts(input),...(Number.isInteger(modeCount)?[`Modes to find ${modeCount}`]:[]),...(groupIndex===true?['group index on']:[])].join(' · ')}`;
// Readiness describes the current editor and retained artifacts, not accuracy.
// viewed: the run Results shows (the selected run); the Results step describes that run, so the
// step bar, the result and its settings agree. Without it, the newest run of these inputs.
// modeCount: Modes to find of the page; a run is of these inputs when it also found that count.
export function opticalWorkflow({input,invalid=false,block='',busy=false,pending=false,resumeBlocked=false,mesh=null,runs=[],viewed,modeCount,groupIndex=false}){
 const signature=studySignature(input,modeCount,groupIndex),inputs=JSON.stringify(input);
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
  {id:'Mesh',state:mesh?.signature===inputs?'ready':mesh?'attention':'optional',detail:mesh?.signature===inputs?'Preview current':mesh?'Inputs changed since preview':'Optional preview'},
  {id:'Study',state:invalid?'attention':busy?'busy':pending||block?'attention':'ready',detail:study,summary:state,wavelength:Number.isFinite(wavelength)?`λ ${wavelength} nm`:null},
  // a run with other inputs than the current ones is information, not a problem: tone 'info'
  viewed?{id:'Results',state:viewed.signature===signature?'ready':'attention',detail:viewed.signature===signature?'Result for these inputs':'Current inputs differ from this run',...(viewed.signature===signature?{}:{tone:'info'})}
  :{id:'Results',state:currentRun?'ready':runs.length?'attention':'empty',detail:currentRun?'Result for these inputs':runs.length?'Current inputs differ from this run':'No run yet',...(!currentRun&&runs.length?{tone:'info'}:{})}
 ];
}
// A run as the dock, the footer and the title name it: its number (its place in the run list,
// oldest = 1) with its name, "Run 1 · design A", or "Run 2" when it has none.
export const runTitle=(number,label)=>`Run ${number}${label?' · '+label:''}`;
// The run state the dock heading and the footer describe, in the words of the multiphysics model.
// viewed: the run Results shows (the selected run), which both then describe, so they agree with
// the step bar and the title. 'current': that run (without one, the newest run) solved these exact
// inputs; 'other': the viewed run has other inputs, and has: the number of a run of these inputs,
// if any; 'stale': runs exist but none is viewed and none has these inputs; 'none' before any
// run. origin: where the run came from when it was not computed in this tab ('imported' or
// 'recovered'). name: the run's name (absent when it has none). For 'other', geometry and
// currentGeometry: the two geometries in words, and changes: what differs, from the run to the
// current inputs (inputChanges), which names them when the geometry is the same (round 14).
export function opticalFreshness(input,runs=[],viewed=null,modeCount,groupIndex=false){
 const signature=studySignature(input,modeCount,groupIndex),own=runs.findLastIndex(run=>run.signature===signature),seen=viewed?runs.indexOf(viewed):-1;
 const index=seen>=0?seen:own,run=runs[index],origin=run?.origin,from=origin==='imported'||origin==='recovered'?{origin}:{},name=run?.label?{name:run.label}:{};
 if(seen>=0&&run.signature!==signature)return {state:'other',run:index+1,...name,...from,...(own>=0?{has:own+1}:{}),geometry:geometryWords(run.input.model),currentGeometry:geometryWords(input.model),changes:inputChanges(run.input,input)};
 if(index>=0)return {state:'current',run:index+1,...name,...from};
 return runs.length?{state:'stale',run:runs.length}:{state:'none',run:null};
}
// The viewed run and the current inputs, both named (round 14): "Run 1 · Design A 600 × 300 nm ·
// current inputs 700 × 300 nm"; with the same geometry, at most two changes ("· current inputs
// differ: Wavelength 1550 → 1310 nm"), and the plain words when no listed setting differs.
export function otherInputsText({run,name='',geometry,currentGeometry,changes=[]}){
 const viewed=geometry?`Run ${run} · ${name?name+' ':''}${geometry}`:runTitle(run,name);
 if(geometry&&currentGeometry&&geometry!==currentGeometry)return `${viewed} · current inputs ${currentGeometry}`;
 if(changes.length)return `${viewed} · current inputs differ: ${changes.slice(0,2).join(' · ')}${changes.length>2?' …':''}`;
 return `${viewed} · current inputs differ from this run`;
}
// The dock heading and the ready footer for that state: both name the same run.
export function opticalSequenceHeading({state,run,name='',origin,...other}){
 const title=runTitle(run,name);
 if(state==='current'&&originText(origin))return `${title} · ${originText(origin)}`;
 if(state==='current')return `${title} · solved from the current inputs`;
 if(state==='other')return otherInputsText({run,name,...other});
 if(state==='stale')return `Inputs changed since run ${run} · press Run to update`;
 return 'Nothing is computed until you press Run';
}
export function opticalReadyStatus({state,run,name='',origin,has,...other}){
 const title=runTitle(run,name);
 if(state==='current'&&originText(origin))return `${title} · ${originText(origin)} · press Run to compute it here`;
 if(state==='current')return `${title} · solved from the current inputs · press Run to solve again`;
 if(state==='other')return otherInputsText({run,name,...other})+' · '+(has?`Run ${has} has them`:'press Run to compute them');
 if(state==='stale')return `Inputs changed since run ${run} · press Run to update`;
 return 'Optical adapter ready · explicit Run required';
}
