// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
// Round 29 (agent-proxy pilot, build 2318e5f8): L1, the slab shortcut's mode count is for the closed
// window only; L2, browser-recovery offers say "kept" for the browser copy's time; L3, the number
// the header names after repeated Download again.
// Plain text comparison only: no RegExp is built from a dynamic string.
const test=require('node:test');const assert=require('node:assert/strict');
const fs=require('node:fs');const path=require('node:path');
const STATIC='../../packages/simcase/src/simcase/studio/static/';
const read=name=>fs.readFileSync(path.join(__dirname,STATIC,name),'utf8');

test('L1: Open boundary takes Modes to find back to its count before the shortcut',async()=>{
 const C=await import(STATIC+'workspace-closed-target.mjs');
 const m=C.shortcutModesMemory();
 assert.equal(m.onOpen(4),null);
 // the shortcut took Modes to find from 2 to 4 at 2.46: Open boundary sets 2 back, once
 m.set(2,4,2.46);
 assert.deepEqual(m.onOpen(4),{modeCount:2,text:"Modes to find back to 2: 4 was for the closed window's search near 2.46."});
 assert.equal(m.onOpen(4),null);
 // the real numbers and the short form of t
 m.set(3,4,2.455);assert.deepEqual(m.onOpen(4),{modeCount:3,text:"Modes to find back to 3: 4 was for the closed window's search near 2.455."});
 assert.equal(C.shortcutModesBackText(1,4,2.4),"Modes to find back to 1: 4 was for the closed window's search near "+C.shortTarget(2.4)+'.');
 // nothing when the count before the shortcut was already 4
 m.set(4,4,2.46);assert.equal(m.onOpen(4),null);
 // nothing when Modes to find was changed by hand after the shortcut (cleared, or another value)
 m.set(2,4,2.46);m.clear();assert.equal(m.onOpen(4),null);
 m.set(2,4,2.46);assert.equal(m.onOpen(5),null);assert.equal(m.onOpen(4),null);
});

test('L1: the page keeps the shortcut\'s count, sets it back on Open boundary as an edit of its own, and forgets it on any other change',()=>{
 const app=read('workspace-app.mjs');
 // the shortcut remembers the count it replaced
 assert.ok(app.includes('function useClosedSearch(t){if(state.openBoundary||(state.searchTarget===t&&state.modeCount===SHORTCUT_MODE_COUNT))return;shortcutModes.set(state.modeCount,SHORTCUT_MODE_COUNT,t);state.searchTarget=t;state.modeCount=SHORTCUT_MODE_COUNT;'));
 // Open boundary: the boundary change is recorded first, so Undo gives back 4 with the open boundary
 assert.ok(app.includes("const back=open?shortcutModes.onOpen(state.modeCount):null;if(back){trackEdit();edits.endGroup();state.modeCount=back.modeCount;}"));
 assert.ok(app.includes("if(back)$('file-status').append(' '+back.text);"));
 // Modes to find typed, Undo or Redo, a template and new inputs forget it
 assert.ok(app.includes("if(key==='modeCount')shortcutModes.clear();"));
 assert.ok(app.includes('function restoreEdit(doc,label){\n shortcutModes.clear();'));
 // the run handler, its document and Run as set are unchanged (round 27's asserted block)
 assert.ok(app.includes("  if(answer==='search')useClosedSearch(near);\n  if(solverBusy||pendingJob||opticalBlock()||retentionBlock())return;\n }"));
});

test('L2: the browser copy\'s time is "kept"; a file\'s save time stays "saved"',async()=>{
 const A=await import(STATIC+'workspace-applications.mjs');
 const at=s=>'2026-11-24T05:'+s+':00Z',w=t=>({[at('46')]:'5:46 AM',[at('38')]:'5:38 AM',[at('30')]:'5:30 AM',S:'9:24 PM'})[t]??t;
 const latest={runs:5,savedAt:at('38'),model:'Optical waveguide',names:[],file:'optical-and-heated.json',fileCurrent:false};
 const earlier=[{runs:6,savedAt:at('46'),model:'Optical waveguide',names:[],index:0,file:'optical-and-heated.json',fileCurrent:false},{runs:1,savedAt:at('30'),model:'Heated silicon waveguide',names:['Run 1'],index:1}];
 assert.deepEqual(A.resumeChoices(latest,earlier,w).map(c=>c.label),[
  'Restore newest from this browser: Optical waveguide · 6 runs · file optical-and-heated.json, changed since · kept 5:46 AM',
  'Restore from this browser: Optical waveguide · 5 runs · file optical-and-heated.json, changed since · older · kept 5:38 AM',
  'Restore from this browser: Heated silicon waveguide · 1 run · Run 1 · older · kept 5:30 AM']);
 // a record that is the same as its file names the file's save time: that is a file save
 assert.equal(A.resumeChoices({runs:2,savedAt:at('46'),file:'x.json',fileCurrent:true,fileSavedAt:'S'},[],w)[0].label,'Restore newest from this browser: 2 runs · same as file x.json · saved 9:24 PM');
 // the card offers: an older one says kept; the file's own time keeps saved
 const item={runs:1,names:['Run 1'],savedAt:'T',file:'x.json',fileCurrent:false};
 assert.equal(A.cardResumeChoice(item,'Heated silicon waveguide',()=>'5:38 AM',{older:true}).label,'Restore from this browser · Heated silicon waveguide · Run 1 · older · kept 5:38 AM · file x.json, changed since');
 assert.equal(A.cardResumeChoice(item,'Heated silicon waveguide',()=>'5:30 AM').label,'Restore from this browser · Heated silicon waveguide · Run 1 · 5:30 AM · file x.json, changed since');
 assert.equal(A.cardResumeChoice({...item,fileCurrent:true,fileSavedAt:'S'},'Optical waveguide',()=>'9:24 PM',{older:true}).label,'Restore from this browser · Optical waveguide · Run 1 · older · same as file x.json, saved 9:24 PM');
});

test('L3: the n-th Download again of a name says "(n)"; the first says "(1)" as before',async()=>{
 const P=await import(STATIC+'workspace-persistence.mjs'),F=await import(STATIC+'workspace-files.mjs');
 assert.equal(F.downloadAgainName('design-a-ng.json'),'design-a-ng (1).json');
 assert.equal(F.downloadAgainName('design-a-ng.json',2),'design-a-ng (2).json');
 assert.equal(F.downloadAgainName('Heater study.JSON',3),'Heater study (3).JSON');
 const file=extra=>({...F.rememberFile({name:'design-a-ng.json',how:'download',scope:'s'}),savedAt:'2026-11-25T11:45:00.000Z',again:true,...extra});
 const title=extra=>P.projectTitle({name:'design-a-ng',models:1,file:file(extra),recovery:'kept',current:true},()=>'11:45 AM');
 assert.equal(title({}),'design-a-ng · design-a-ng.json · downloaded again 11:45 AM (your browser may have named it design-a-ng (1).json)');
 assert.equal(title({repeat:1}),'design-a-ng · design-a-ng.json · downloaded again 11:45 AM (your browser may have named it design-a-ng (1).json)');
 assert.equal(title({repeat:2}),'design-a-ng · design-a-ng.json · downloaded again 11:45 AM (your browser may have named it design-a-ng (2).json)');
 // the page counts the repeats of the same name on the download path; Save As keeps a new record
 const app=read('workspace-app.mjs');
 assert.ok(app.includes("if(project.file?.again===true)project.file.repeat=(target.how==='download'&&target.name===chosen.name&&Number.isInteger(target.repeat)?target.repeat:0)+1;"));
});
