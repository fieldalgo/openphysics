// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
// Round 26, C3: after Download again, the project header says so, with the time of that download and
// the name the question said the browser may give it, until the next Save As or Open. The save
// dialog's path (a picker file) and a first download keep their words.
// Plain text comparison only: no RegExp is built from a dynamic string.
const test=require('node:test');const assert=require('node:assert/strict');
const fs=require('node:fs');const path=require('node:path');
const STATIC='../../packages/simcase/src/simcase/studio/static/';
const read=name=>fs.readFileSync(path.join(__dirname,STATIC,name),'utf8');
const when=()=>'11:45 AM';

test('C3: the header after Download again, current and changed since',async()=>{
 const P=await import(STATIC+'workspace-persistence.mjs'),F=await import(STATIC+'workspace-files.mjs');
 const file={...F.rememberFile({name:'design-a-ng.json',how:'download',scope:'s'}),savedAt:'2026-11-25T11:45:00.000Z',again:true};
 const state={name:'design-a-ng',models:1,file,recovery:'kept'};
 assert.equal(P.projectTitle({...state,current:true},when),'design-a-ng · design-a-ng.json · downloaded again 11:45 AM (your browser may have named it design-a-ng (1).json)');
 assert.equal(P.projectTitle({...state,current:false},when),'design-a-ng · design-a-ng.json · changed since downloaded again 11:45 AM (your browser may have named it design-a-ng (1).json) · kept for recovery in this browser');
 // the name is the one the question gave
 assert.ok(F.downloadAgainQuestion('design-a-ng.json').includes('may name the new one '+F.downloadAgainName('design-a-ng.json')+'.'));
 assert.equal(F.downloadAgainName('Heater study.JSON'),'Heater study (1).JSON');
 // the heated model's status bar uses the header's words (round 18, X8)
 assert.equal(P.modelInProjectTitle({title:'Heated silicon waveguide',file,inFile:true,current:true,recovery:'kept'},when),'Heated silicon waveguide · in project design-a-ng.json · downloaded again 11:45 AM (your browser may have named it design-a-ng (1).json)');
});

test('C3: a first download, a picker file and an opened file keep their words',async()=>{
 const P=await import(STATIC+'workspace-persistence.mjs'),F=await import(STATIC+'workspace-files.mjs');
 const at={savedAt:'2026-11-25T11:45:00.000Z'};
 const title=(how,extra={})=>P.projectTitle({name:'design-a-ng',models:1,file:{...F.rememberFile({name:'design-a-ng.json',how,handle:how==='picker'?{}:null,scope:'s'}),...at,...extra},current:true,recovery:'kept'},when);
 assert.equal(title('download'),'design-a-ng · design-a-ng.json · downloaded 11:45 AM');
 assert.equal(title('picker'),'design-a-ng · design-a-ng.json · saved 11:45 AM');
 // the flag belongs to a download only: the save dialog's path is unchanged
 assert.equal(title('picker',{again:true}),'design-a-ng · design-a-ng.json · saved 11:45 AM');
 assert.equal(title('opened'),'design-a-ng · design-a-ng.json · opened');
 // a new file record (Save As, Open, a first download) carries no flag
 assert.equal('again' in F.rememberFile({name:'design-a-ng.json',how:'download',scope:'s'}),false);
});

test('C3: the page marks the project file after Download again only, not after Save As…',()=>{
 const app=read('workspace-app.mjs');
 const mark="downloadFile(new Blob([makeText(chosen.name)],{type:'application/json'}),chosen.name);keep(chosen.name,'download');\n   // round 26 (C3): Download again is said in the header (its time and the name the question gave)\n   // until the next Save As or Open, which keep a new file record\n   if(!chosen.saveAs&&project.file?.scope===scope)project.file.again=true;";
 assert.equal(app.split(mark).length-1,1);
 // the time is that download's: saveProject sets the file's savedAt once the file is written
 assert.ok(app.includes("project.name=name;if(project.nameFrom!=='user')project.nameFrom='file';if(project.file)project.file.savedAt=savedAt;"));
 // the native save path (the picker) keeps a new record, so it never says "again"
 assert.ok(app.includes("if(result.status==='saved'){keep(result.name,'picker',result.handle);return {written:true,name:result.name,via:'picker',after:''};}"));
});
