// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
// File › Save and Save As (workspace-files.mjs): the name dialog's file names, model file names,
// and the save picker at its boundary (window.showSaveFilePicker stubbed): the options it is
// called with, a handle written again without a dialog, a cancel, a write that fails (the old
// content stays whole, as Chromium replaces a file only on close) and a picker that throws.
const test=require('node:test');const assert=require('node:assert/strict');
const STATIC='../../packages/simcase/src/simcase/studio/static/';
let F;
test.before(async()=>{F=await import(STATIC+'workspace-files.mjs');});

// A file handle whose content changes only when a writable is closed, as in Chromium.
function fakeFile(name,content=''){
 const file={name,content,writes:0,aborts:0,failNext:null};
 file.handle={name,kind:'file',createWritable:async()=>{let pending='';return {
  write:async text=>{if(file.failNext){const e=file.failNext;file.failNext=null;throw e;}pending+=text;},
  close:async()=>{file.content=pending;file.writes++;},abort:async()=>{file.aborts++;}};}};
 return file;
}
const fakeWindow=(pick)=>({isSecureContext:true,calls:[],showSaveFilePicker(options){this.calls.push(options);return pick(options);}});

test('sanitizeFileName keeps letters, digits, spaces and . _ - ( ) and adds .json',()=>{
 assert.equal(F.sanitizeFileName('my run/<x>?'),'my runx.json');
 assert.equal(F.sanitizeFileName('Waveguide (2).JSON'),'Waveguide (2).json');
 assert.equal(F.sanitizeFileName('  a   b  '),'a b.json');
 assert.equal(F.sanitizeFileName('résumé'),'rsum.json');
 assert.equal(F.sanitizeFileName('..hidden'),'hidden.json');
 assert.equal(F.sanitizeFileName(''),'session.json');
 assert.equal(F.sanitizeFileName('.json','x.json'),'x.json');
 assert.equal(F.sanitizeFileName('??','fallback.json'),'fallback.json');
 assert.equal(F.sanitizeFileName('optical-waveguide-session-2026-11-23-0105.json'),'optical-waveguide-session-2026-11-23-0105.json');
 const long=F.sanitizeFileName('a'.repeat(300));assert.ok(long.length<=200&&long.endsWith('.json'));
 // every name it returns is one browser recovery keeps (workspace-persistence.mjs validateSavedFile)
 for(const name of ['my run/<x>?','Waveguide (2).JSON','a'.repeat(300),'..hidden'])assert.match(F.sanitizeFileName(name),/^[A-Za-z0-9._ ()-]{1,200}\.json$/);
});
test('model files are named after the model',()=>{
 assert.equal(F.modelFileName('optical-waveguide'),'optical-waveguide.json');
 assert.equal(F.modelFileName('Heated silicon waveguide'),'heated-silicon-waveguide.json');
 assert.equal(F.modelFileName('Joule heating'),'joule-heating.json');
 assert.equal(F.modelFileName('…'),'model.json');
});
test('the picker is used only in a secure context that has it',()=>{
 assert.equal(F.pickerAvailable({isSecureContext:true,showSaveFilePicker(){}}),true);
 assert.equal(F.pickerAvailable({isSecureContext:false,showSaveFilePicker(){}}),false);
 assert.equal(F.pickerAvailable({isSecureContext:true}),false);
});
test('Save As calls the picker with one JSON type, the id and Documents, and writes the bytes',async()=>{
 const file=fakeFile('chosen.json','old'),win=fakeWindow(async()=>file.handle);
 const r=await F.saveToFile('{"a":1}\n',{suggestedName:'optical-waveguide-session-2026-11-23-0105.json',win});
 assert.equal(r.status,'saved');assert.equal(r.name,'chosen.json');assert.equal(file.content,'{"a":1}\n');
 assert.equal(win.calls.length,1);
 assert.deepEqual(win.calls[0],{suggestedName:'optical-waveguide-session-2026-11-23-0105.json',types:[{description:'OpenPhysics session file (JSON)',accept:{'application/json':['.json']}}],id:'openphysics-project',startIn:'documents'});
 // Save: the same handle again, no dialog
 const again=await F.saveToFile('{"a":2}\n',{suggestedName:'x.json',target:{handle:r.handle,name:r.name},win});
 assert.equal(again.status,'saved');assert.equal(win.calls.length,1);assert.equal(file.content,'{"a":2}\n');assert.equal(file.writes,2);
 // Save As again starts in the current file
 await F.saveToFile('{"a":3}\n',{suggestedName:'chosen.json',target:{handle:r.handle,name:r.name},saveAs:true,win});
 assert.equal(win.calls.length,2);assert.equal(win.calls[1].startIn,file.handle);
});
test('a cancel writes nothing and says so',async()=>{
 const win=fakeWindow(async()=>{throw new DOMException('The user aborted a request.','AbortError');});
 const r=await F.saveToFile('x',{suggestedName:'a.json',win});
 assert.deepEqual(r,{status:'cancelled'});
 assert.equal(F.notWrittenNotice(r,{saveAs:true}),'Save As cancelled; nothing was written.');
 assert.equal(F.notWrittenNotice(r,{saveAs:false}),'Save cancelled; nothing was written.');
});
test('a failed write is aborted and leaves the old content whole',async()=>{
 const file=fakeFile('kept.json','OLD CONTENT');file.failNext=new DOMException('Disk full','QuotaExceededError');
 const r=await F.saveToFile('NEW',{suggestedName:'kept.json',target:{handle:file.handle,name:'kept.json'}});
 assert.equal(r.status,'failed');assert.equal(file.content,'OLD CONTENT');assert.equal(file.aborts,1);assert.equal(file.writes,0);
 assert.equal(F.notWrittenNotice(r,{saveAs:false}),'Session not saved: kept.json could not be written (Disk full); the file is unchanged.');
});
test('a picker that throws other than a cancel, or none at all, asks for a name instead',async()=>{
 const denied=fakeWindow(async()=>{throw new DOMException('Not allowed','NotAllowedError');});
 assert.deepEqual(await F.saveToFile('x',{suggestedName:'a.json',win:denied}),{status:'unavailable',error:'Not allowed'});
 const sync=fakeWindow(()=>{throw new DOMException('Must be handling a user gesture','SecurityError');});
 assert.equal((await F.saveToFile('x',{suggestedName:'a.json',win:sync})).status,'unavailable');
 assert.deepEqual(await F.saveToFile('x',{suggestedName:'a.json',win:{isSecureContext:true}}),{status:'unavailable',error:null});
});
test('the picker is called before anything is awaited (inside the click)',()=>{
 const file=fakeFile('a.json');let called=false;const win=fakeWindow(async()=>{called=true;return file.handle;});
 F.saveToFile('x',{suggestedName:'a.json',win});assert.equal(called,true);
});
test('the save indicator says "Saved to" only after the save dialog wrote the file',async()=>{
 const P=await import(STATIC+'workspace-persistence.mjs');
 const when=()=>'10:15',saved={name:'chosen.json',savedAt:'2026-11-23T10:15:00Z',current:true};
 assert.equal(P.persistenceTitle({saved:{...saved,written:true}},when),'Saved to chosen.json · 10:15');
 assert.equal(P.persistenceTitle({saved},when),"Session file chosen.json sent to your browser's Downloads · 10:15");
});
