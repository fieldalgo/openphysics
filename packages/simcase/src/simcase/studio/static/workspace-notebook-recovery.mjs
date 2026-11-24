// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
import {MAX_SESSION_BYTES,parseSession} from './workspace-notebook.mjs';
import {validateSavedFile} from './workspace-persistence.mjs';
import {validateProjectName} from './workspace-project-file.mjs';

export function readNotebookRecovery(record){
 if(record==null)return null;
 if(record.version!==1||typeof record.savedAt!=='string'||!Number.isFinite(Date.parse(record.savedAt))||typeof record.session!=='string')throw new Error('Invalid notebook recovery record.');
 // savedFile (optional): the last session file this notebook was saved to; a malformed one is ignored.
 // openedFile (optional): the session file the notebook was opened from, by name, for the recovery
 // lists; a malformed one is ignored. Neither is part of the session.
 // openedCurrent (optional; optical and multiphysics records): true when the inputs and runs were still those of openedFile.
 // page (optional, optical): the page the notebook showed, which a restore opens again.
 // project (optional; optical and multiphysics records): {name, from} of the tab's project when it
 // has a name, so a restore names the project when no savedFile.projectName does; a malformed one is ignored.
 // All are browser-only, beside the session; a record without them (or with another value) reads as before.
 return {savedAt:record.savedAt,session:parseSession(record.session,{recovered:true}),savedFile:validateSavedFile(record.savedFile),openedFile:openedFileName(record.openedFile),
  openedCurrent:openedFileName(record.openedFile)&&typeof record.openedCurrent==='boolean'?record.openedCurrent:null,page:recordPage(record.page),project:recordProject(record.project)};
}
/** The project of a recovery record: {name, from} with a name a project may have (validateProjectName,
 * stored trimmed) and from 'file' or 'user' (where the name came from), else null. */
export function recordProject(value){
 if(value==null||typeof value!=='object'||Array.isArray(value)||!['file','user'].includes(value.from)||typeof value.name!=='string')return null;
 try{if(validateProjectName(value.name)!==value.name)return null;}catch{return null;}
 return {name:value.name,from:value.from};
}
// The pages a recovery record may name; any other value is ignored.
export const RECORD_PAGES=Object.freeze(['Model','Results','Compare']);
export const recordPage=page=>RECORD_PAGES.includes(page)?page:null;
/** The page a restored notebook opens: the page its record names when its runs allow it (Compare
 * needs two runs, Results one), else the rule for a record without one (and for a session file,
 * which names no page): Compare for two runs or more, Results for one, else Model. */
export function restorePage(page,runCount){
 const named=recordPage(page);
 if(named==='Compare'&&runCount>1||named==='Results'&&runCount>0||named==='Model')return named;
 return runCount>1?'Compare':runCount?'Results':'Model';
}
// any letters (a Korean file name included), no path separators or control characters
export const openedFileName=name=>typeof name==='string'&&/^[^\u0000-\u001f\u007f/\\]{1,200}\.json$/u.test(name)&&!/^\.\.?$/.test(name)?name:null;
// What makes two stored sessions the same: the model or inputs and the runs. The view (the page,
// the field view), the selected run, the Compare choice and each run's origin (computed here,
// opened from a file or recovered) and digest (it covers the origin) are left out: a tab click, a selected run, an open or a
// recovery changes them, but not the session. A text that does not parse is compared as it is.
export function sessionKey(text){
 if(typeof text!=='string')return null;
 try{const doc=JSON.parse(text.replace(/^\uFEFF/,''));if(doc&&typeof doc==='object'&&!Array.isArray(doc)){
  delete doc.view;delete doc.selected;delete doc.comparison;
  // each run's digest too (versions 9 to 12): it covers the origin, and the rest of the run is compared
  if(Array.isArray(doc.runs))doc.runs=doc.runs.map(run=>{if(run&&typeof run==='object'&&!Array.isArray(run)){const {origin,digest,...rest}=run;return rest;}return run;});
  return JSON.stringify(doc);}}catch{}
 return text;
}
// The session file a record names: the file it was last sent to, else the file it was opened from.
export const recordFile=record=>validateSavedFile(record?.savedFile)?.name||openedFileName(record?.openedFile)||null;
// One session in a recovery list: the newest record of each session (sessionKey). records: the latest
// record (null when none) and the earlier ones, as stored; returns {record, index, file} newest first,
// index being the record's place among the earlier sessions (-1 for the latest), so two
// entries never hold the same session. file: the session file of the newest record of the session
// that names one (a merged older record can name the file the newest does not).
export function distinctRecords(latest,earlier=[]){
 const all=[...(latest?[{record:latest,index:-1}]:[]),...earlier.map((record,index)=>({record,index}))].filter(e=>e.record&&typeof e.record.session==='string');
 all.sort((a,b)=>(Date.parse(b.record.savedAt)||0)-(Date.parse(a.record.savedAt)||0)||a.index-b.index);
 const kept=new Map();
 for(const e of all){const key=sessionKey(e.record.session),first=kept.get(key);
  if(!first){kept.set(key,{...e,file:recordFile(e.record)});continue;}
  if(!first.file)first.file=recordFile(e.record);}
 return [...kept.values()];
}

// After a project save (round 16): every stored record whose session is one of the sessions just
// written (sessionKey) names the project file, so the Library card of a model that was not shown
// names the newest file too. Its revision is kept (the record's session is unchanged), so no tab
// reads this as another tab's change. Returns {latest, earlier, changed}.
export function relinkRecords(latest,earlier,sessions,savedFile){
 const keys=new Set(sessions.map(sessionKey)),file=validateSavedFile(savedFile);let changed=false;
 const relink=record=>{if(!file||!record||typeof record.session!=='string'||!keys.has(sessionKey(record.session)))return record;changed=true;return {...record,savedFile:file};};
 const list=Array.isArray(earlier)?earlier.map(relink):earlier;
 return {latest:relink(latest),earlier:list,changed};
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
 // relinkRecords in one transaction; a record another tab wrote meanwhile is relinked as it is now
 const relink=(sessions,savedFile)=>new Promise((resolve,reject)=>{
  if(!factory){reject(new Error('Browser database unavailable.'));return;}
  const opening=factory.open('openphysics-studio-notebook',1);
  opening.onupgradeneeded=()=>{const db=opening.result;if(!db.objectStoreNames.contains('snapshots'))db.createObjectStore('snapshots');};
  opening.onerror=()=>reject(opening.error||new Error('Cannot open browser database.'));
  opening.onblocked=()=>reject(new Error('Browser database upgrade is blocked by another tab.'));
  opening.onsuccess=()=>{
   const db=opening.result;let tx,result=false;
   try{tx=db.transaction('snapshots','readwrite');const snapshots=tx.objectStore('snapshots'),latest=snapshots.get('latest'),earlier=snapshots.get('earlier');
    earlier.onsuccess=()=>{const out=relinkRecords(latest.result??null,earlier.result,sessions,savedFile);result=out.changed;
     if(out.changed){if(out.latest)snapshots.put(out.latest,'latest');if(Array.isArray(out.earlier))snapshots.put(out.earlier,'earlier');}};
   }catch(error){db.close();reject(error);return;}
   tx.oncomplete=()=>{db.close();resolve(result);};tx.onabort=()=>{db.close();reject(tx.error||new Error('Browser recovery transaction aborted.'));};tx.onerror=()=>{};
  };
 });
 return {load:()=>transact('readonly'),loadEarlier,adopt,save:record=>transact('readwrite',record),movedEarlier,keepPrevious,relink};
}

// Coalesce rapid edits and serialize writes so an older completion cannot win.
export class NotebookAutosave {
 constructor(store,{onState=()=>{},delay=700,setTimer=(fn,ms)=>setTimeout(fn,ms),clearTimer=id=>clearTimeout(id)}={}){
  this.store=store;this.onState=onState;this.delay=delay;this.setTimer=setTimer;this.clearTimer=clearTimer;this.timer=null;this.desired=null;this.writing=false;this.savedStamp=null;this.failedStamp=null;
 }
 // extra: optional {savedFile, openedFile, openedCurrent, page, project} written beside the session in the record.
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
   const record={version:1,savedAt:new Date().toISOString(),session,...(capture.extra?.savedFile?{savedFile:capture.extra.savedFile}:{}),...(openedFileName(capture.extra?.openedFile)?{openedFile:capture.extra.openedFile,...(typeof capture.extra.openedCurrent==='boolean'?{openedCurrent:capture.extra.openedCurrent}:{})}:{}),...(recordPage(capture.extra?.page)?{page:capture.extra.page}:{}),...(recordProject(capture.extra?.project)?{project:recordProject(capture.extra.project)}:{})};const committed=await this.store.save(record);this.savedStamp=capture.stamp;this.failedStamp=null;this.onState({phase:'saved',record:committed||record,note:typeof capture.makeText.note==='string'?capture.makeText.note:'',dropped:Array.isArray(capture.makeText.dropped)?[...capture.makeText.dropped]:[]});
  // a write refused for space (QuotaExceededError) is named, so the page can say why (round 17, U6)
  }catch(error){this.failedStamp=capture.stamp;this.onState({phase:'error',code:error?.code??(error?.name==='QuotaExceededError'?'recovery-quota':undefined),message:error?.name==='QuotaExceededError'?'This browser’s storage is full, so the session cannot be kept for recovery. File › Save keeps it in a file.':error.message});}
  finally{this.writing=false;if(this.desired?.stamp!==capture.stamp)await this.flush();}
 }
 async replaceReviewed(record,stamp,makeText,extra={}){
  if(this.writing)throw new Error('Recovery storage is busy. Wait for it to finish, then review again.');
  this.store.adopt(record);this.savedStamp=null;this.desired=null;
  this.schedule(stamp,makeText,extra);await this.flush();
 }
 // Round 20 follow-up: settle before a restore reads the stored record, so the record it adopts is
 // the one in storage, not one this tab's own save replaces a moment later (restoring both models read the
 // latest record, waited for the server's model check, and this tab's pending save committed
 // meanwhile: every later save then read as another tab's change). A save waiting for its timer is
 // written now (the state the timer would have written); a write in flight is waited for. Resolves
 // once no write is in flight and none is pending, or the pending one failed (the failure stays).
 async settle(){
  for(;;){
   if(this.writing){await new Promise(resolve=>this.setTimer(resolve,25));continue;}
   if(this.timer!==null||(this.desired&&this.desired.stamp!==this.savedStamp&&this.desired.stamp!==this.failedStamp)){await this.flush();continue;}
   return;
  }
 }
 retry(){this.failedStamp=null;return this.flush();}
 get pending(){return this.writing||!!this.desired&&this.desired.stamp!==this.savedStamp;}
}
