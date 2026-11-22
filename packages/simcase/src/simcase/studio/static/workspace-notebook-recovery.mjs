// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
import {MAX_SESSION_BYTES,parseSession} from './workspace-notebook.mjs';
import {validateSavedFile} from './workspace-persistence.mjs';

export function readNotebookRecovery(record){
 if(record==null)return null;
 if(record.version!==1||typeof record.savedAt!=='string'||!Number.isFinite(Date.parse(record.savedAt))||typeof record.session!=='string')throw new Error('Invalid notebook recovery record.');
 // savedFile (optional): the last session file this notebook was saved to; a malformed one is ignored.
 // openedFile (optional): the session file the notebook was opened from, by name, for the recovery
 // lists; a malformed one is ignored. Neither is part of the session.
 return {savedAt:record.savedAt,session:parseSession(record.session,{recovered:true}),savedFile:validateSavedFile(record.savedFile),openedFile:openedFileName(record.openedFile)};
}
// any letters (a Korean file name included), no path separators or control characters
export const openedFileName=name=>typeof name==='string'&&/^[^\u0000-\u001f\u007f/\\]{1,200}\.json$/u.test(name)&&!/^\.\.?$/.test(name)?name:null;
// What makes two stored sessions the same: the session text without its view (the page, the
// selection, the field view), which a tab click or a selected run changes but the model and its
// runs do not. A text that does not parse is compared as it is.
export function sessionKey(text){
 if(typeof text!=='string')return null;
 try{const doc=JSON.parse(text.replace(/^\uFEFF/,''));if(doc&&typeof doc==='object'&&!Array.isArray(doc)){delete doc.view;return JSON.stringify(doc);}}catch{}
 return text;
}
// One session in a recovery list: the newest record of each session (sessionKey). records: the latest
// record (null when none) and the earlier ones, as stored; returns {record, index} newest first,
// index being the record's place among the earlier sessions (-1 for the latest), so two
// entries never hold the same session.
export function distinctRecords(latest,earlier=[]){
 const all=[...(latest?[{record:latest,index:-1}]:[]),...earlier.map((record,index)=>({record,index}))].filter(e=>e.record&&typeof e.record.session==='string');
 all.sort((a,b)=>(Date.parse(b.record.savedAt)||0)-(Date.parse(a.record.savedAt)||0)||a.index-b.index);
 const seen=new Set();
 return all.filter(e=>{const key=sessionKey(e.record.session);if(seen.has(key))return false;seen.add(key);return true;});
}

// A legacy record has no revision; include its payload to detect same-time writes.
export function recoveryRevision(record){return record==null?null:record.revision??record.savedAt+'\0'+record.session;}
// How many earlier sessions the store keeps. The first save after a page adopts a
// record moves that record here instead of dropping it, so a session the user did
// not recover (for example after missing the prompt) survives the next session.
export const EARLIER_SESSIONS=3;
export function indexedNotebookStore(factory=globalThis.indexedDB){
 let expected,epoch=0,wroteSinceAdopt=false,movedOnLastSave=false;
 // kept: the page continues this very record (it recovered the latest session), so its
 // next save replaces it instead of keeping it as an earlier session
 const adopt=(record,{kept=false}={})=>{expected=recoveryRevision(record);epoch++;wroteSinceAdopt=kept;};
 const transact=(mode,record,key='latest')=>new Promise((resolve,reject)=>{
  if(!factory){reject(new Error('Browser database unavailable.'));return;}
  if(mode==='readwrite'&&expected===undefined){reject(new Error('Read browser recovery before saving.'));return;}
  const baseline=expected,startedEpoch=epoch,keepPrevious=!wroteSinceAdopt;let moved=false;
  const saved=mode==='readwrite'?{...record,revision:Array.from(globalThis.crypto.getRandomValues(new Uint32Array(4)),n=>n.toString(16).padStart(8,'0')).join('')}:null;
  let settled=false;const opening=factory.open('openphysics-studio-notebook',1);
  opening.onupgradeneeded=()=>{const db=opening.result;if(!db.objectStoreNames.contains('snapshots'))db.createObjectStore('snapshots');};
  opening.onerror=()=>{settled=true;reject(opening.error||new Error('Cannot open browser database.'));};
  opening.onblocked=()=>{settled=true;reject(new Error('Browser database upgrade is blocked by another tab.'));};
  opening.onsuccess=()=>{
   const db=opening.result;if(settled){db.close();return;}
   let tx,request,failure;
   try{
    tx=db.transaction('snapshots',mode);const snapshots=tx.objectStore('snapshots');request=snapshots.get(key);
    if(mode==='readwrite')request.onsuccess=()=>{
     if(recoveryRevision(request.result)!==baseline){
      failure=Object.assign(new Error('Another tab changed browser recovery. Save this session to a file, then recover the latest browser session before continuing automatic recovery.'),{code:'recovery-conflict'});tx.abort();return;
     }
     if(!keepPrevious||request.result==null){snapshots.put(saved,'latest');return;}
     const earlier=snapshots.get('earlier');
     earlier.onsuccess=()=>{
      // when the stored record is kept as an earlier session (the first save of a page, or after a
      // move between models), a session is kept once (sessionKey): an earlier copy of the session
      // written now is dropped, and a latest record of the same session is replaced, not kept (an unchanged model saved again, for
      // example after the tab moved between models and back, or a file opened twice)
      const savedKey=sessionKey(saved.session),latestKey=sessionKey(request.result.session),stored=Array.isArray(earlier.result)?earlier.result:[];
      const keep=latestKey!==savedKey&&recoveryRevision(stored[0])!==recoveryRevision(request.result);
      // the record moved in front stands for its session, so an older copy of it goes too
      const list=stored.filter(r=>{const key=sessionKey(r?.session);return key!==savedKey&&!(keep&&key===latestKey);});
      if(keep||list.length!==stored.length){snapshots.put((keep?[request.result,...list]:list).slice(0,EARLIER_SESSIONS),'earlier');moved=true;}
      snapshots.put(saved,'latest');
     };
    };
   }catch(error){db.close();reject(error);return;}
   tx.oncomplete=()=>{db.close();if(mode==='readwrite'){movedOnLastSave=moved;if(epoch===startedEpoch){expected=recoveryRevision(saved);wroteSinceAdopt=true;}}resolve(mode==='readonly'?request.result:saved);};
   tx.onabort=()=>{db.close();reject(failure||tx.error||new Error('Browser recovery transaction aborted.'));};
   tx.onerror=()=>{}; // Abort is the final failure event; the prior record remains atomic.
  };
 });
 const loadEarlier=async()=>{const list=await transact('readonly',null,'earlier');return Array.isArray(list)?list:[];};
 // whether the last committed save moved a record to the earlier sessions
 const movedEarlier=()=>movedOnLastSave;
 // keepPrevious: the next save keeps the stored record as an earlier session (the tab moved
 // between an optical and a multiphysics model, so its next record is another session)
 const keepPrevious=()=>{wroteSinceAdopt=false;};
 return {load:()=>transact('readonly'),loadEarlier,adopt,save:record=>transact('readwrite',record),movedEarlier,keepPrevious};
}

// Coalesce rapid edits and serialize writes so an older completion cannot win.
export class NotebookAutosave {
 constructor(store,{onState=()=>{},delay=700,setTimer=(fn,ms)=>setTimeout(fn,ms),clearTimer=id=>clearTimeout(id)}={}){
  this.store=store;this.onState=onState;this.delay=delay;this.setTimer=setTimer;this.clearTimer=clearTimer;this.timer=null;this.desired=null;this.writing=false;this.savedStamp=null;this.failedStamp=null;
 }
 // extra: optional {savedFile, openedFile} written beside the session in the record.
 schedule(stamp,makeText,extra={}){
  if(this.desired?.stamp===stamp)return;
  this.desired={stamp,makeText,extra};this.failedStamp=null;
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
   const record={version:1,savedAt:new Date().toISOString(),session,...(capture.extra?.savedFile?{savedFile:capture.extra.savedFile}:{}),...(openedFileName(capture.extra?.openedFile)?{openedFile:capture.extra.openedFile}:{})};const committed=await this.store.save(record);this.savedStamp=capture.stamp;this.failedStamp=null;this.onState({phase:'saved',record:committed||record});
  }catch(error){this.failedStamp=capture.stamp;this.onState({phase:'error',code:error.code,message:error.message});}
  finally{this.writing=false;if(this.desired?.stamp!==capture.stamp)await this.flush();}
 }
 async replaceReviewed(record,stamp,makeText,extra={}){
  if(this.writing)throw new Error('Recovery storage is busy. Wait for it to finish, then review again.');
  this.store.adopt(record);this.savedStamp=null;this.desired=null;
  this.schedule(stamp,makeText,extra);await this.flush();
 }
 retry(){this.failedStamp=null;return this.flush();}
 get pending(){return this.writing||!!this.desired&&this.desired.stamp!==this.savedStamp;}
}
