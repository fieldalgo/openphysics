// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
import {parseProject} from './workspace-project.mjs';
import {opticalBlock} from './workspace-optical.mjs';
export const PENDING_JOB_KEY='openphysics.studio.pending-optical.v1';
export function validatePending(record){
 if(record?.version!==1||typeof record.job!=='string'||!/^[a-f0-9]{8}$/.test(record.job))throw new Error('Invalid pending job.');
 if(typeof record.serverInstance!=='string'||!/^[a-f0-9]{32}$/.test(record.serverInstance))throw new Error('Invalid pending server instance.');
 if(typeof record.serverVersion!=='string'||!/^\d[0-9A-Za-z.+-]{0,63}$/.test(record.serverVersion))throw new Error('Invalid pending server version.');
 if(typeof record.startedAt!=='string'||!Number.isFinite(Date.parse(record.startedAt)))throw new Error('Invalid pending timestamp.');
 if(!Number.isSafeInteger(record.revision)||record.revision<0)throw new Error('Invalid pending revision.');
 const input=parseProject(JSON.stringify(record.input));const block=opticalBlock(input.model,input.setup);if(block)throw new Error(block);
 return {version:1,job:record.job,serverInstance:record.serverInstance,serverVersion:record.serverVersion,startedAt:record.startedAt,revision:record.revision,input};
}
export function readPending(storage){const raw=storage.getItem(PENDING_JOB_KEY);if(!raw)return null;if(new TextEncoder().encode(raw).length>70000)throw new Error('Pending record is too large.');return validatePending(JSON.parse(raw));}
export function storePending(storage,record){if(record===null)storage.removeItem(PENDING_JOB_KEY);else storage.setItem(PENDING_JOB_KEY,JSON.stringify(validatePending(record)));}
// Stopping this client detaches polling. It never claims to stop server computation.
export class OpticalJobMonitor {
 constructor({api,onState=()=>{},onResult=()=>{},wait=ms=>new Promise(r=>setTimeout(r,ms)),now=()=>Date.now(),limitMs=180000}){Object.assign(this,{api,onState,onResult,wait,now,limitMs});this.generation=0;this.busy=false;}
 stop(){this.generation++;this.busy=false;this.onState({phase:'detached',message:'Stopped waiting. Server computation may continue; resume to retrieve its result.'});}
 async follow(record,instance){
  if(this.busy)throw new Error('Already watching a job.');
  const pending=validatePending(record);if(instance!==pending.serverInstance)throw new Error('The server restarted or changed. This job cannot be resumed on this server.');
  const token=++this.generation;this.busy=true;const deadline=this.now()+this.limitMs;
  const active=()=>token===this.generation;
  try{
   while(active()){
    this.onState({phase:'running',message:'Computing job '+pending.job+' · elapsed '+Math.max(0,Math.floor((this.now()-Date.parse(pending.startedAt))/1000))+' s',pending});
    const job=await this.api('/api/jobs/'+pending.job+'?workspace_instance='+pending.serverInstance);if(!active())return;
    if(job.status==='error')throw new Error(typeof job.error==='string'?job.error:'Solver failed.');
    if(job.status==='done'){
     this.onState({phase:'loading',message:'Loading completed result '+pending.job,pending});
     const result=await this.api('/api/jobs/'+pending.job+'/result?workspace_instance='+pending.serverInstance);if(!active())return;
     await this.onResult(result,pending);if(!active())return;
     this.onState({phase:'done',message:'Optical computation complete. Result retains its input snapshot.',pending});return;
    }
    if(job.status!=='running')throw new Error('Unsupported job status.');
    if(this.now()>=deadline){this.onState({phase:'detached',message:'Stopped waiting after three minutes. Resume to check this job again.',pending});return;}
    await this.wait(700);
   }
  }catch(error){if(active())this.onState({phase:'error',message:error.message+' No new result stored. You can retry this job.',pending});}
  finally{if(active())this.busy=false;}
 }
}
