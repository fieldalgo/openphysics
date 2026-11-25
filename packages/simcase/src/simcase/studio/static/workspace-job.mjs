// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
import {parseProject,validateOpenChoice} from './workspace-project.mjs';
import {hasOpenEdge,lowerTarget} from './workspace-open-boundary.mjs';
import {checkClosedTarget} from './workspace-closed-target.mjs';
import {searchesText} from './workspace-open-run.mjs';
import {opticalBlock} from './workspace-optical.mjs';
import {DEFAULT_MODE_COUNT,checkModeCount} from './workspace-notebook.mjs';
export const PENDING_JOB_KEY='openphysics.studio.pending-optical.v1';
export function validatePending(record){
 if(record?.version!==1||typeof record.job!=='string'||!/^[a-f0-9]{8}$/.test(record.job))throw new Error('Invalid pending job.');
 if(typeof record.serverInstance!=='string'||!/^[a-f0-9]{32}$/.test(record.serverInstance))throw new Error('Invalid pending server instance.');
 if(typeof record.serverVersion!=='string'||!/^\d[0-9A-Za-z.+-]{0,63}$/.test(record.serverVersion))throw new Error('Invalid pending server version.');
 if(typeof record.startedAt!=='string'||!Number.isFinite(Date.parse(record.startedAt)))throw new Error('Invalid pending timestamp.');
 if(!Number.isSafeInteger(record.revision)||record.revision<0)throw new Error('Invalid pending revision.');
 const input=parseProject(JSON.stringify(record.input));const block=opticalBlock(input.model,input.setup);if(block)throw new Error(block);
 // the mode count the job asked for (a record written before mode counts could change asked for 2)
 let modeCount=DEFAULT_MODE_COUNT;if(record.modeCount!==undefined){try{modeCount=checkModeCount(record.modeCount);}catch{throw new Error('Invalid pending mode count.');}}
 // an open boundary (slice P2): the choice the job was run with ({edges, target}, the target as
 // sent); pmlCheck: the PML check follows the job; checkOf: this job is the PML check of that run
 const extra={};
 if(record.openBoundary!==undefined){let ob;try{ob=validateOpenChoice(record.openBoundary,input.model.shapes);}catch{throw new Error('Invalid pending open boundary.');}if(!hasOpenEdge(ob)||ob.target===undefined)throw new Error('Invalid pending open boundary.');extra.openBoundary=ob;}
 // a closed-window search (slice C2): the job's Search near n_eff, never with an open boundary
 if(record.searchTarget!==undefined){if(extra.openBoundary)throw new Error('Invalid pending search target.');try{extra.searchTarget=checkClosedTarget(record.searchTarget,input.model.shapes);}catch{throw new Error('Invalid pending search target.');}}
 if(record.pmlCheck!==undefined){if(record.pmlCheck!==true||!extra.openBoundary)throw new Error('Invalid pending PML check.');extra.pmlCheck=true;}
 if(record.checkOf!==undefined){
  const n=record.checkCount,i=record.checkIndex;
  if(typeof record.checkOf!=='string'||!/^[a-f0-9]{8}$/.test(record.checkOf)||!extra.openBoundary||extra.pmlCheck||!Number.isInteger(n)||n<1||n>8||!Number.isInteger(i)||i<0||i>=n)throw new Error('Invalid pending PML check.');
  Object.assign(extra,{checkOf:record.checkOf,checkIndex:i,checkCount:n});
 }else if(record.checkIndex!==undefined||record.checkCount!==undefined)throw new Error('Invalid pending PML check.');
 // run retention (Recompute Run N's fields): this job recomputes the fields of the run of job `job`
 // and number `number`; its result attaches them to that run and never makes a run
 if(record.recompute!==undefined){
  const r=record.recompute;
  if(r===null||typeof r!=='object'||typeof r.job!=='string'||!/^[a-f0-9]{8}$/.test(r.job)||!Number.isSafeInteger(r.number)||r.number<1||extra.checkOf||extra.pmlCheck)throw new Error('Invalid pending recompute.');
  extra.recompute={job:r.job,number:r.number};
 }
 return {version:1,job:record.job,serverInstance:record.serverInstance,serverVersion:record.serverVersion,startedAt:record.startedAt,revision:record.revision,input,...(modeCount===DEFAULT_MODE_COUNT?{}:{modeCount}),...extra};
}
export function readPending(storage){const raw=storage.getItem(PENDING_JOB_KEY);if(!raw)return null;if(new TextEncoder().encode(raw).length>70000)throw new Error('Pending record is too large.');return validatePending(JSON.parse(raw));}
export function storePending(storage,record){if(record===null)storage.removeItem(PENDING_JOB_KEY);else storage.setItem(PENDING_JOB_KEY,JSON.stringify(validatePending(record)));}
// The time since a job started, as m:ss (0:05, 3:07, 12:40).
export function elapsedText(ms){const s=Math.max(0,Math.floor(ms/1000));return Math.floor(s/60)+':'+String(s%60).padStart(2,'0');}
// What a pending job solves, from the record alone (round 16): "Open boundary · 2 modes · searches
// near 2.46 and 1.95 · PML check (up to 2 more solves)" (slice T2; "search near 2.460" below a
// target of 1.466), "PML check · mode 1 of 2", "2 modes". The step the job is at comes from the
// server (stepText).
export function jobWhat(pending){
 if(pending.checkOf)return `PML check · mode ${pending.checkIndex+1} of ${pending.checkCount}`;
 const n=pending.modeCount??DEFAULT_MODE_COUNT,modes=n===1?'1 mode':n+' modes';
 if(!pending.openBoundary)return modes;
 const t=pending.openBoundary.target,low=lowerTarget(t),searches=low===null?`search near ${t.toFixed(3)}`:`searches near ${searchesText(t,low)}`;
 return `Open boundary · ${modes} · ${searches}`+(pending.pmlCheck?` · PML check (up to ${n===1?'1 more solve':n+' more solves'})`:'');
}
// The step of a running job (job progress, round 25 A5): the words of the server's step, the latest
// search_started event of simcase.run's on_event, "solve 2 of 3 (group index) · search 1 of 2";
// "solve 1 of 3" with one search per solve, "search 2 of 2" with one solve. '' for a job of one step
// in all (a closed run without group index, an open run of one search, a PML check job), for no step
// (an older server) and for a step of another shape. Studio sends single studies, so a point has no
// words. No percent: the searches of a solve take different times.
export function stepText(step){
 if(step===null||typeof step!=='object'||Array.isArray(step)||step.event!=='search_started')return '';
 const counts=['point','points','solve','solves','search','searches'];
 if(!counts.every(k=>Number.isSafeInteger(step[k])&&step[k]>=1)||step.point>step.points||step.solve>step.solves||step.search>step.searches)return '';
 if(!['study_point','group_index'].includes(step.solve_kind))return '';
 const solve=step.solves>1?`solve ${step.solve} of ${step.solves}`+(step.solve_kind==='group_index'?' (group index)':''):'';
 const search=step.searches>1?`search ${step.search} of ${step.searches}`:'';
 return [solve,search].filter(Boolean).join(' · ');
}
/** Messages while the server does not answer: the job panel's words without the time. */
export const NO_ANSWER_LIVE=' · no answer from the server; still checking';
// Stopping this client detaches polling. It never claims to stop server computation.
// While the server answers that the job is running, the monitor keeps waiting, however long the
// job takes (round 16). limitMs bounds only the time without an answer: a status request that
// fails (no connection, a server error) is tried again every 700 ms, and once no request has been
// answered for limitMs the monitor detaches; Resume checks the job again. A missing job (404) or a
// changed server (409) ends at once, as a failed solver does.
// A running state has message (the job panel's words, with the time: time · step · what), parts
// ({lead, rest}: the time and what the job solves, with any no-answer words, which the page shows in
// spans of their own around the step, so the step is never cut), live (Messages, the one live region:
// "Computing job … · what · step", without the time, so it changes only at the start, when the step
// changes, when the server stops or starts answering again, and at the end) and step (stepText of the
// last answer).
export class OpticalJobMonitor {
 constructor({api,onState=()=>{},onResult=()=>{},wait=ms=>new Promise(r=>setTimeout(r,ms)),now=()=>Date.now(),limitMs=180000}){Object.assign(this,{api,onState,onResult,wait,now,limitMs});this.generation=0;this.busy=false;}
 stop(){this.generation++;this.busy=false;this.onState({phase:'detached',message:'Stopped waiting. Server computation may continue; resume to retrieve its result.'});}
 async follow(record,instance){
  if(this.busy)throw new Error('Already watching a job.');
  const pending=validatePending(record);if(instance!==pending.serverInstance)throw Object.assign(new Error('The server restarted or changed. Detach this job before starting another calculation.'),{status:409});
  const token=++this.generation;this.busy=true;let answered=this.now(),silent=false,step='';
  const active=()=>token===this.generation,what=jobWhat(pending);
  try{
   while(active()){
    const quiet=silent?` · no answer from the server for ${elapsedText(this.now()-answered)}; still checking`:'',at=step?' · '+step:'';
    const lead='Computing job '+pending.job+' · '+elapsedText(this.now()-Date.parse(pending.startedAt)),rest=what+quiet;
    this.onState({phase:'running',message:lead+at+' · '+rest,parts:{lead,rest},
     live:'Computing job '+pending.job+' · '+what+at+(silent?NO_ANSWER_LIVE:''),step,pending});
    let job;
    try{job=await this.api('/api/jobs/'+pending.job+'?workspace_instance='+pending.serverInstance);}
    catch(error){
     if(!active())return;if([404,409].includes(error.status))throw error;
     silent=true;if(this.now()-answered>=this.limitMs){this.onState({phase:'detached',message:'The server has not answered for three minutes. Resume to check this job again.',pending});return;}
     await this.wait(700);continue;
    }
    if(!active())return;answered=this.now();silent=false;step=stepText(job.step);
    if(job.status==='error')throw Object.assign(new Error(typeof job.error==='string'?job.error:'Solver failed.'),{code:'solver-failed'});
    if(job.status==='done'){
     this.onState({phase:'loading',message:'Loading the result of this run…',title:'Job '+pending.job,pending});
     const result=await this.api('/api/jobs/'+pending.job+'/result?workspace_instance='+pending.serverInstance);if(!active())return;
     await this.onResult(result,pending);if(!active())return;
     this.onState({phase:'done',message:'Optical run complete. The result keeps the inputs it was run with.',pending});return;
    }
    if(job.status!=='running')throw new Error('Unsupported job status.');
    await this.wait(700);
   }
  }catch(error){if(active()){const canResume=![404,409].includes(error.status)&&error.code!=='solver-failed';this.onState({phase:'error',canResume,message:error.message+' No new result stored. '+(canResume?'Resume to retry retrieving this job.':'Detach this job before starting another calculation.'),pending});}}
  finally{if(active())this.busy=false;}
 }
}
