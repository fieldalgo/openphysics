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
// navigator.webdriver false: a browser people use (C1(f) below covers an automated one)
const fakeWindow=(pick)=>({isSecureContext:true,navigator:{webdriver:false},calls:[],showSaveFilePicker(options){this.calls.push(options);return pick(options);}});

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
test('an automated browser (navigator.webdriver) never calls the picker and asks for a name',async()=>{
 assert.equal(F.pickerAvailable({isSecureContext:true,navigator:{webdriver:true},showSaveFilePicker(){}}),false);
 let called=0;const win={isSecureContext:true,navigator:{webdriver:true},showSaveFilePicker(){called++;throw new Error('must not be called');}};
 assert.deepEqual(await F.saveToFile('x',{suggestedName:'a.json',win}),{status:'unavailable',error:null});
 assert.equal(called,0);
});
test('Save As calls the picker with one JSON type and the id (no startIn before a file is chosen), and writes the bytes',async()=>{
 const file=fakeFile('chosen.json','old'),win=fakeWindow(async()=>file.handle);
 const r=await F.saveToFile('{"a":1}\n',{suggestedName:'optical-waveguide-session-2026-11-23-0105.json',win});
 assert.equal(r.status,'saved');assert.equal(r.name,'chosen.json');assert.equal(file.content,'{"a":1}\n');
 assert.equal(win.calls.length,1);
 assert.deepEqual(win.calls[0],{suggestedName:'optical-waveguide-session-2026-11-23-0105.json',types:[{description:'OpenPhysics session file (JSON)',accept:{'application/json':['.json']}}],id:'openphysics-project'});
 // round 13 (F3): no startIn key at all, so the id alone restores the folder last picked under it
 assert.equal('startIn' in win.calls[0],false);
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
test('the save indicator names the file, and says "downloaded" unless the save dialog wrote it',async()=>{
 const P=await import(STATIC+'workspace-persistence.mjs');
 const when=()=>'10:15',saved={name:'chosen.json',savedAt:'2026-11-23T10:15:00Z',current:true};
 assert.equal(P.persistenceTitle({saved:{...saved,written:true}},when),'chosen.json · saved 10:15');
 assert.equal(P.persistenceTitle({saved},when),'chosen.json · downloaded 10:15');
});
test('a failed write to a file just chosen does not claim the file is unchanged',async()=>{
 const file=fakeFile('picked.json','OLD');file.failNext=new DOMException('Disk full','QuotaExceededError');
 const r=await F.saveToFile('NEW',{suggestedName:'picked.json',win:fakeWindow(async()=>file.handle)});
 assert.equal(r.status,'failed');assert.equal(r.fresh,true);
 assert.equal(F.notWrittenNotice(r,{saveAs:true}),'Session not saved: picked.json could not be written (Disk full); the browser may have left it empty.');
});

// round 13 (O1): one current file name per model, set by Save As, the Save name dialog or File ›
// Open, dropped when the scope (the open model, and every open, switch and reset) moves on
test('the current file is remembered for its model and dropped on another scope',()=>{
 const a=F.rememberFile({name:'design-a-ng.json',how:'download',scope:'optical-waveguide:3'});
 assert.deepEqual(a,{name:'design-a-ng.json',handle:null,how:'download',scope:'optical-waveguide:3'});
 assert.equal(F.currentFileFor(a,'optical-waveguide:3'),a);
 // an open, a model switch or Reset design moves the scope on: no name any more
 assert.equal(F.currentFileFor(a,'optical-waveguide:4'),null);
 assert.equal(F.currentFileFor(a,'multiphysics:3'),null);
 assert.equal(F.currentFileFor(null,'optical-waveguide:3'),null);
 // a name the name dialog would not accept is not remembered; a handle is kept for the picker only
 assert.equal(F.rememberFile({name:'a/b.json',how:'download',scope:'s'}),null);
 assert.equal(F.rememberFile({name:'a.json',how:'other',scope:'s'}),null);
 assert.equal(F.rememberFile({name:'a.json',how:'opened',handle:{},scope:'s'}).handle,null);
 const h={};assert.equal(F.rememberFile({name:'a.json',how:'picker',handle:h,scope:'s'}).handle,h);
 // round 14 (Q3): a restored record that still matched its file makes it current, without a handle:
 // Save downloads under it at once and Save As suggests it
 const back=F.rememberFile({name:'waveguide-designs-A-B.json',how:'recovered',handle:{},scope:'s'});
 assert.deepEqual([back.how,back.handle],['recovered',null]);
 assert.equal(F.saveRoute(back),'download');assert.equal(F.saveRoute(back,{saveAs:true}),'ask');
 assert.equal(F.suggestedSaveName(back,'optical-waveguide-session.json'),'waveguide-designs-A-B.json');
 assert.equal(F.LATER_SAVES_NOTE,'Later saves download again under this name; your browser may add “ (1)”.');
 // the name a save suggests: the current file's, else the model-based one
 assert.equal(F.suggestedSaveName(a,'optical-waveguide-session-2026-11-23-0342.json'),'design-a-ng.json');
 assert.equal(F.suggestedSaveName(null,'optical-waveguide-session-2026-11-23-0342.json'),'optical-waveguide-session-2026-11-23-0342.json');
});
test('Save downloads under a known name without asking; Save As and no name ask; a handle is written',()=>{
 const known=F.rememberFile({name:'design-a-ng.json',how:'download',scope:'s'}),opened=F.rememberFile({name:'o.json',how:'opened',scope:'s'}),picked=F.rememberFile({name:'p.json',how:'picker',handle:{},scope:'s'});
 assert.equal(F.saveRoute(known,{saveAs:false}),'download');
 assert.equal(F.saveRoute(opened,{saveAs:false}),'download');
 assert.equal(F.saveRoute(known,{saveAs:true}),'ask');
 assert.equal(F.saveRoute(null,{saveAs:false}),'ask');
 assert.equal(F.saveRoute(picked,{saveAs:false}),'write');
 // where the picker works, it is used as before (with the current name suggested)
 assert.equal(F.saveRoute(known,{saveAs:false,picker:true}),'picker');
 assert.equal(F.saveRoute(null,{saveAs:true,picker:true}),'picker');
 assert.equal(F.saveRoute(picked,{saveAs:true,picker:true}),'picker');
 assert.equal(F.downloadAgainNote('design-a-ng.json'),'A download cannot replace the earlier file, so your browser may add a number such as “ (1)” to its name.');
});
test('saveToFile: a known name without a picker is downloaded as is; the picker is offered it as the name',async()=>{
 const known={name:'design-a-ng.json',handle:null};
 assert.deepEqual(await F.saveToFile('x',{suggestedName:'design-a-ng.json',target:known,win:{isSecureContext:true}}),{status:'known',name:'design-a-ng.json'});
 assert.deepEqual(await F.saveToFile('x',{suggestedName:'design-a-ng.json',target:known,saveAs:true,win:{isSecureContext:true}}),{status:'unavailable',error:null});
 const file=fakeFile('design-a-ng.json'),win=fakeWindow(async()=>file.handle);
 await F.saveToFile('x',{suggestedName:'design-a-ng.json',target:known,win});
 assert.equal(win.calls.length,1);assert.equal(win.calls[0].suggestedName,'design-a-ng.json');assert.equal('startIn' in win.calls[0],false);
 assert.deepEqual(F.pickerOptions('a.json',file.handle).startIn,file.handle);
});
test('the header names the current file and its state; "Unsaved inputs" only without a name',async()=>{
 const P=await import(STATIC+'workspace-persistence.mjs'),when=()=>'03:42';
 const saved={name:'design-a-ng.json',savedAt:'2026-11-23T03:42:00Z',current:true};
 assert.equal(P.persistenceTitle({saved,file:'design-a-ng.json'},when),'design-a-ng.json · downloaded 03:42');
 assert.equal(P.persistenceTitle({saved:{...saved,written:true},file:'design-a-ng.json'},when),'design-a-ng.json · saved 03:42');
 assert.equal(P.persistenceTitle({saved:{...saved,current:false},clean:false,file:'design-a-ng.json'},when),'design-a-ng.json · changed since downloaded');
 assert.equal(P.persistenceTitle({saved:{...saved,current:false},runsUnsaved:true,recovery:'kept',file:'design-a-ng.json'},when),'design-a-ng.json · changed since downloaded · kept for recovery in this browser');
 // round 14 (Q1, Q3): the word after "changed since" follows how the file became current
 const changed={saved:{...saved,current:false},clean:false,file:'design-a-ng.json'};
 assert.equal(P.persistenceTitle({...changed,fileHow:'download'},when),'design-a-ng.json · changed since downloaded');
 assert.equal(P.persistenceTitle({...changed,saved:{...changed.saved,written:true},fileHow:'picker'},when),'design-a-ng.json · changed since saved');
 assert.equal(P.persistenceTitle({...changed,fileHow:'recovered'},when),'design-a-ng.json · changed since restored');
 assert.equal(P.persistenceTitle({clean:false,file:'x.json',fileHow:'opened'},when),'x.json · changed since opened');
 // the title text on the download path only
 assert.equal(P.DOWNLOAD_NAME_HINT,'Your browser may have added “ (1)” to the file name.');
 assert.equal(P.persistenceHint({saved,file:'design-a-ng.json',fileHow:'download'}),P.DOWNLOAD_NAME_HINT);
 assert.equal(P.persistenceHint({...changed,fileHow:'download'}),P.DOWNLOAD_NAME_HINT);
 assert.equal(P.persistenceHint({saved:{...saved,written:true},file:'design-a-ng.json',fileHow:'picker'}),'');
 assert.equal(P.persistenceHint({clean:false,file:'x.json',fileHow:'opened'}),'');
 assert.equal(P.persistenceHint({clean:false}),'');
 const opened={kind:'opened',name:'design-a-ng.json',current:true,file:'design-a-ng.json',fileCurrent:true};
 assert.equal(P.persistenceTitle({loaded:opened,file:'design-a-ng.json'},when),'Opened design-a-ng.json');
 assert.equal(P.persistenceTitle({loaded:{...opened,current:false},clean:false,file:'design-a-ng.json'},when),'design-a-ng.json · changed since opened');
 // no name (never saved, or dropped by a reset or another model): the words as before
 assert.equal(P.persistenceTitle({clean:false},when),'Unsaved inputs');
 assert.equal(P.persistenceTitle({fresh:true},when),'New model · not saved');
});
test('P3: the text may be made from the name chosen (a project names itself after its file), with the project file type',async()=>{
 const file=fakeFile('design-a-ng.json'),win=fakeWindow(()=>Promise.resolve(file.handle)),made=[];
 const text=name=>{made.push(name);return '{"name":'+JSON.stringify(name)+'}';};
 const saved=await F.saveToFile(text,{suggestedName:'untitled-project.json',saveAs:true,win,description:F.PROJECT_PICKER_DESCRIPTION});
 assert.deepEqual(saved,{status:'saved',handle:file.handle,name:'design-a-ng.json'});assert.deepEqual(made,['design-a-ng.json']);
 assert.equal(file.content,'{"name":"design-a-ng.json"}');
 assert.deepEqual(win.calls[0].types,[{description:'OpenPhysics project file (JSON)',accept:{'application/json':['.json']}}]);
 // written again through the kept handle: made again with the kept name, no dialog
 const again=await F.saveToFile(text,{suggestedName:'x.json',target:{name:'design-a-ng.json',handle:file.handle,how:'picker'},win});
 assert.equal(again.status,'saved');assert.equal(win.calls.length,1);assert.deepEqual(made,['design-a-ng.json','design-a-ng.json']);
 // a text that cannot be made (a project over the limit) is a failed write: the kept file is whole
 const refused=await F.saveToFile(()=>{throw new Error('The project is 71 MB, over the 64 MiB limit.');},{suggestedName:'x.json',target:{name:'design-a-ng.json',handle:file.handle,how:'picker'},win});
 assert.equal(refused.status,'failed');assert.equal(file.content,'{"name":"design-a-ng.json"}');
 assert.equal(F.notWrittenNotice(refused,{saveAs:false,kind:'Project'}),'Project not saved: design-a-ng.json could not be written (The project is 71 MB, over the 64 MiB limit.); the file is unchanged.');
 assert.equal(F.notWrittenNotice({status:'other'},{saveAs:false,kind:'Project'}),'Project not saved: nothing was written.');
});
