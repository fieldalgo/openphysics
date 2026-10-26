// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
import {MAX_SESSION_BYTES,parseSession} from './workspace-notebook.mjs';

export function readNotebookRecovery(record){
 if(record==null)return null;
 if(record.version!==1||typeof record.savedAt!=='string'||!Number.isFinite(Date.parse(record.savedAt))||typeof record.session!=='string')throw new Error('Invalid notebook recovery record.');
 return {savedAt:record.savedAt,session:parseSession(record.session,{recovered:true})};
}

export function indexedNotebookStore(factory=globalThis.indexedDB){
 const transact=(mode,record)=>new Promise((resolve,reject)=>{
  if(!factory){reject(new Error('Browser database unavailable.'));return;}
  let settled=false;const opening=factory.open('openphysics-studio-notebook',1);
  opening.onupgradeneeded=()=>{const db=opening.result;if(!db.objectStoreNames.contains('snapshots'))db.createObjectStore('snapshots');};
  opening.onerror=()=>{settled=true;reject(opening.error||new Error('Cannot open browser database.'));};
  opening.onblocked=()=>{settled=true;reject(new Error('Browser database upgrade is blocked by another tab.'));};
  opening.onsuccess=()=>{
   const db=opening.result;if(settled){db.close();return;}
   let tx,request;
   try{tx=db.transaction('snapshots',mode);request=mode==='readonly'?tx.objectStore('snapshots').get('latest'):tx.objectStore('snapshots').put(record,'latest');}
   catch(error){db.close();reject(error);return;}
   tx.oncomplete=()=>{db.close();resolve(mode==='readonly'?request.result:record);};
   tx.onabort=()=>{db.close();reject(tx.error||new Error('Browser recovery transaction aborted.'));};
   tx.onerror=()=>{}; // Abort is the final failure event; the prior record remains atomic.
  };
 });
 return {load:()=>transact('readonly'),save:record=>transact('readwrite',record)};
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
   const record={version:1,savedAt:new Date().toISOString(),session};await this.store.save(record);this.savedStamp=capture.stamp;this.failedStamp=null;this.onState({phase:'saved',record});
  }catch(error){this.failedStamp=capture.stamp;this.onState({phase:'error',message:error.message});}
  finally{this.writing=false;if(this.desired?.stamp!==capture.stamp)await this.flush();}
 }
 retry(){this.failedStamp=null;return this.flush();}
 get pending(){return this.writing||!!this.desired&&this.desired.stamp!==this.savedStamp;}
}
