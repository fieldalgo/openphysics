// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
import {MAX_SESSION_BYTES,parseSession} from './workspace-notebook.mjs';

export function readNotebookRecovery(record){
 if(record==null)return null;
 if(record.version!==1||typeof record.savedAt!=='string'||!Number.isFinite(Date.parse(record.savedAt))||typeof record.session!=='string')throw new Error('Invalid notebook recovery record.');
 return {savedAt:record.savedAt,session:parseSession(record.session,{recovered:true})};
}

// A legacy record has no revision; include its payload to detect same-time writes.
export function recoveryRevision(record){return record==null?null:record.revision??record.savedAt+'\0'+record.session;}
export function indexedNotebookStore(factory=globalThis.indexedDB){
 let expected,epoch=0;
 const adopt=record=>{expected=recoveryRevision(record);epoch++;};
 const transact=(mode,record)=>new Promise((resolve,reject)=>{
  if(!factory){reject(new Error('Browser database unavailable.'));return;}
  if(mode==='readwrite'&&expected===undefined){reject(new Error('Read browser recovery before saving.'));return;}
  const baseline=expected,startedEpoch=epoch;
  const saved=mode==='readwrite'?{...record,revision:Array.from(globalThis.crypto.getRandomValues(new Uint32Array(4)),n=>n.toString(16).padStart(8,'0')).join('')}:null;
  let settled=false;const opening=factory.open('openphysics-studio-notebook',1);
  opening.onupgradeneeded=()=>{const db=opening.result;if(!db.objectStoreNames.contains('snapshots'))db.createObjectStore('snapshots');};
  opening.onerror=()=>{settled=true;reject(opening.error||new Error('Cannot open browser database.'));};
  opening.onblocked=()=>{settled=true;reject(new Error('Browser database upgrade is blocked by another tab.'));};
  opening.onsuccess=()=>{
   const db=opening.result;if(settled){db.close();return;}
   let tx,request,failure;
   try{
    tx=db.transaction('snapshots',mode);const snapshots=tx.objectStore('snapshots');request=snapshots.get('latest');
    if(mode==='readwrite')request.onsuccess=()=>{
     if(recoveryRevision(request.result)!==baseline){
      failure=Object.assign(new Error('Another tab changed browser recovery. Save this session to a file, then recover the latest browser session before continuing automatic recovery.'),{code:'recovery-conflict'});tx.abort();return;
     }
     snapshots.put(saved,'latest');
    };
   }catch(error){db.close();reject(error);return;}
   tx.oncomplete=()=>{db.close();if(mode==='readwrite'&&epoch===startedEpoch)expected=recoveryRevision(saved);resolve(mode==='readonly'?request.result:saved);};
   tx.onabort=()=>{db.close();reject(failure||tx.error||new Error('Browser recovery transaction aborted.'));};
   tx.onerror=()=>{}; // Abort is the final failure event; the prior record remains atomic.
  };
 });
 return {load:()=>transact('readonly'),adopt,save:record=>transact('readwrite',record)};
}

// Coalesce rapid edits and serialize writes so an older completion cannot win.
export class NotebookAutosave {
 constructor(store,{onState=()=>{},delay=700,setTimer=(fn,ms)=>setTimeout(fn,ms),clearTimer=id=>clearTimeout(id)}={}){
  this.store=store;this.onState=onState;this.delay=delay;this.setTimer=setTimer;this.clearTimer=clearTimer;this.timer=null;this.desired=null;this.writing=false;this.savedStamp=null;this.failedStamp=null;
 }
 schedule(stamp,makeText){
  if(this.desired?.stamp===stamp)return;
  this.desired={stamp,makeText};this.failedStamp=null;
  if(this.timer!==null)this.clearTimer(this.timer);
  this.timer=null;
  if(this.writing)return;
  if(stamp===this.savedStamp){this.onState({phase:'current'});return;}
  this.onState({phase:'pending'});this.timer=this.setTimer(()=>{this.timer=null;this.flush();},this.delay);
 }
 async flush(){
  if(this.timer!==null){this.clearTimer(this.timer);this.timer=null;}
  if(this.writing||!this.desired||this.desired.stamp===this.savedStamp)return;
  const capture=this.desired;this.writing=true;this.onState({phase:'saving'});
  try{
   const session=capture.makeText();if(typeof session!=='string'||new TextEncoder().encode(session).length>MAX_SESSION_BYTES)throw new Error('Recovery snapshot exceeds 16 MiB. Save selected runs to files.');
   const record={version:1,savedAt:new Date().toISOString(),session};const committed=await this.store.save(record);this.savedStamp=capture.stamp;this.failedStamp=null;this.onState({phase:'saved',record:committed||record});
  }catch(error){this.failedStamp=capture.stamp;this.onState({phase:'error',code:error.code,message:error.message});}
  finally{this.writing=false;if(this.desired?.stamp!==capture.stamp)await this.flush();}
 }
 async replaceReviewed(record,stamp,makeText){
  if(this.writing)throw new Error('Recovery storage is busy. Wait for it to finish, then review again.');
  this.store.adopt(record);this.savedStamp=null;this.desired=null;
  this.schedule(stamp,makeText);await this.flush();
 }
 retry(){this.failedStamp=null;return this.flush();}
 get pending(){return this.writing||!!this.desired&&this.desired.stamp!==this.savedStamp;}
}
