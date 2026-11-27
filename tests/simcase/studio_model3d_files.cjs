// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
// The 3D model in files (slice B of the Studio 3D view): the model3d session (F2, application
// "model3d", version 1) and the project file version 2 (F1, kind "model3d", card "layer-stack-3d").
// W11 without runs, file part: the document digest is equal after Save and Open for the project and
// the session, and a project without a 3D model is written as version 1, byte for byte as before.
const test=require('node:test');const assert=require('node:assert/strict');
const {createHash}=require('node:crypto');const fs=require('node:fs');const path=require('node:path');
const STATIC='../../packages/simcase/src/simcase/studio/static/';
const STATIC_DIR=path.join(__dirname,'..','..','packages','simcase','src','simcase','studio','static');
const FIXTURES=path.join(__dirname,'studio_session_fixtures');
const fixture=name=>fs.readFileSync(path.join(FIXTURES,name),'utf8');
let PF,N,M,S;
test.before(async()=>{
 PF=await import(STATIC+'workspace-project-file.mjs');N=await import(STATIC+'workspace-notebook.mjs');
 M=await import(STATIC+'workspace-model3d-session.mjs');S=await import(STATIC+'workspace-multiphysics-session.mjs');
});
const card=()=>JSON.parse(fs.readFileSync(path.join(STATIC_DIR,'model3d-layer-stack-3d.json'),'utf8'));
const sha=text=>createHash('sha256').update(text,'utf8').digest('hex');
const v1=()=>fixture('project-v1.json');
// the fixture's two entries, as a second Save writes them
const v1Entries=()=>PF.readProject(v1()).models.map(m=>PF.projectEntry({id:m.id,kind:m.kind,title:m.title,card:m.card,text:m.text}));
const model3dEntry=(doc=card(),id='m3')=>PF.projectEntry({id,kind:'model3d',title:'Via in a layer stack (3D heat)',card:'layer-stack-3d',text:M.writeModel3dSession(doc)});
const project=(entries,active='m3')=>({name:'Heater study',savedAt:'2026-11-27T21:00:00.000Z',studio:'0.0.2',active,entries});

test('F2: a model3d session holds the document, version 1, and reads back unchanged',()=>{
 const doc=card(),text=M.writeModel3dSession(doc,{camera:'iso'});
 const raw=JSON.parse(text);
 assert.deepEqual(Object.keys(raw),['format','version','application','document','view']);
 assert.deepEqual([raw.format,raw.version,raw.application],['openphysics-studio-session',1,'model3d']);
 const read=N.parseSession(text);
 assert.equal(read.application,'model3d');assert.equal(read.version,1);
 assert.deepEqual(read.document,doc);assert.deepEqual(read.view,{camera:'iso'});assert.deepEqual(read.runs,[]);
 // W11: the document digest is equal after Save and Open
 assert.equal(M.documentDigest(read.document),M.documentDigest(doc));
 assert.equal(M.writeModel3dSession(read.document,read.view),text,'a second save writes the same bytes');
 assert.equal(M.writeModel3dSession(doc).includes('"view"'),false,'no view key without a view');
});

test('F2: a model3d session is checked by name; other version 1 files keep their refusal',()=>{
 const good=JSON.parse(M.writeModel3dSession(card()));
 const refused=(doc,message)=>assert.throws(()=>N.parseSession(JSON.stringify(doc)),{message});
 refused({...good,version:2},'This model3d session is version 2, newer than this Studio reads (version 1). Open it in a newer Studio.');
 refused({...good,version:0},'Unsupported model3d session version.');
 refused({...good,runs:[]},'Unknown key "runs" in the model3d session.');
 refused({...good,document:[]},'The model3d session holds no document.');
 refused({...good,document:{...good.document,openphysics:'0.2'}},'The model3d session holds a document that is not format 0.3.');
 const flat=JSON.parse(JSON.stringify(good));delete flat.document.geometry.version;
 refused(flat,'The model3d session holds a document without a version 1 geometry block.');
 refused({...good,view:[1]},'The model3d session has an invalid view.');
 // a version 1 file of before the units batch (no application) is refused with its own words, as before
 assert.throws(()=>N.parseSession('{"format":"openphysics-studio-session","version":1,"runs":[]}'),
  {message:'This session (version 1) was saved before the units and naming batch; its results are not read. Re-run the design and save a new session.'});
 // the 16 MiB limit is unchanged
 const big=card();big.name='x'.repeat(16*1024*1024);
 assert.throws(()=>M.writeModel3dSession(big),{message:/over the 16 MiB session limit/});
 assert.throws(()=>N.parseSession(JSON.stringify({...good,document:big})),{message:'Session exceeds 16 MiB.'});
});

test('F1: a project with a 3D model is version 2 and reads back with the document unchanged',()=>{
 const entries=[...v1Entries(),model3dEntry()];
 const out=PF.writeProject(project(entries));assert.equal(out.ok,true);
 assert.ok(out.text.startsWith('{"format":"openphysics-studio-project","version":2,"name":"Heater study",'));
 const read=PF.readProject(out.text);
 assert.deepEqual(read.models.map(m=>[m.id,m.kind,m.card]),[['m1','workspace','optical'],['m2','multiphysics','heated-waveguide'],['m3','model3d','layer-stack-3d']]);
 const m3=read.models[2];
 assert.equal(m3.session.application,'model3d');assert.deepEqual(m3.session.document,card());
 // W11: the document digest after Open equals the one saved, and a second Save writes the same bytes
 assert.equal(M.documentDigest(m3.session.document),M.documentDigest(card()));
 const again=PF.writeProject(project(read.models.map(m=>PF.projectEntry({id:m.id,kind:m.kind,title:m.title,card:m.card,text:m.text}))));
 assert.equal(again.text,out.text);
 // a project of the 3D model alone
 const alone=PF.writeProject(project([model3dEntry()]));assert.equal(JSON.parse(alone.text).version,2);
 assert.equal(PF.readProject(alone.text).models[0].kind,'model3d');
});

test('W11: a project without a 3D model is written as version 1, byte for byte',()=>{
 const read=PF.readProject(v1());
 const again=PF.writeProject({name:read.name,savedAt:read.savedAt,studio:read.studio,active:read.active,entries:v1Entries()});
 assert.equal(again.text,v1(),'the committed version 1 fixture');
 assert.equal(sha(again.text),sha(v1()));
});

test('F1: the reader refuses a 3D model where version 2 does not allow it, by name',()=>{
 const two=PF.writeProject(project([...v1Entries(),model3dEntry()])).text;
 const refused=(text,message)=>assert.throws(()=>PF.readProject(text),{message});
 const mutate=(text,f)=>{const doc=JSON.parse(text);f(doc);return S.sessionJson(doc);};
 // version 1 knows no model3d kind: its refusal as before
 refused(mutate(two,d=>{d.version=1;}),'Via in a layer stack (3D heat) is of an unknown kind.');
 refused(mutate(two,d=>{d.models.push({...d.models[2],id:'m4'});}),'A project file holds at most one model3d model.');
 refused(mutate(two,d=>{d.version=3;}),'This project file is version 3, newer than this Studio reads (version 2). Open it in a newer Studio.');
 refused(mutate(two,d=>{d.models[2].card='layer-stack';}),'Via in a layer stack (3D heat) names an unknown Library card.');
 // the kind against the session
 const optical=JSON.parse(two).models[0].session;
 refused(mutate(two,d=>{d.models[2].session=optical;d.models[2].bytes=d.models[0].bytes;d.models[2].digest=d.models[0].digest;}),
  'Via in a layer stack (3D heat) is a model3d model, but its session is of version 9 (an optical session).');
 refused(mutate(two,d=>{d.models.splice(1,1);d.models[1].kind='multiphysics';d.models[1].card='heated-waveguide';}),
  'Via in a layer stack (3D heat) is a multiphysics model, but its session is a model3d session.');
 assert.ok(PF.CARDS.includes('layer-stack-3d'));
 assert.deepEqual([...PF.KINDS],['workspace','multiphysics','model3d']);
});
