// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
// Round 24: usability fixes of the optical model (B2 to B6, pre-registered P1 to P5).
// Plain text comparison only: no RegExp is built from a dynamic string.
const test=require('node:test');const assert=require('node:assert/strict');
const fs=require('node:fs');const path=require('node:path');
const STATIC='../../packages/simcase/src/simcase/studio/static/';
const read=name=>fs.readFileSync(path.join(__dirname,STATIC,name),'utf8');
const body=(text,from,to)=>{const a=text.indexOf(from),b=text.indexOf(to,a+from.length);assert.ok(a>=0&&b>a,from);return text.slice(a,b);};

test('P1 (B2): after a change, a project that came from a file says "changed since <file>, not saved" in every recovery state',async()=>{
 const PS=await import(STATIC+'workspace-persistence.mjs'),when=()=>'10:15';
 const changed=recovery=>PS.projectTitle({name:'both-models',models:2,recovery,fromFile:'both-models.json'},when);
 assert.equal(changed('updating'),'both-models · changed since both-models.json, not saved · updating browser recovery');
 assert.equal(changed('kept'),'both-models · changed since both-models.json, not saved · kept for recovery in this browser');
 assert.equal(changed('keptFields:6'),'both-models · changed since both-models.json, not saved · kept for recovery in this browser without the fields of Run 6');
 assert.equal(changed(null),'both-models · changed since both-models.json, not saved · not in browser recovery yet');
 // right after the restore (the recovered words lead, as before: E5 and Q4)
 assert.equal(PS.projectTitle({name:'both-models',models:2,recovery:'kept',recovered:{opened:null,changed:'both-models.json'},fromFile:'both-models.json'},when),'both-models · recovered from this browser · changed since both-models.json, not saved · kept for recovery in this browser');
 assert.equal(PS.projectTitle({name:'both-models',models:2,recovery:'kept',recovered:{opened:'both-models.json',changed:null},fromFile:'both-models.json'},when),'both-models · recovered from this browser · as opened from both-models.json · kept for recovery in this browser');
 // a project no file held keeps "not saved to a file"
 assert.equal(PS.projectTitle({name:'both-models',models:2,recovery:'updating'},when),'both-models · not saved to a file · updating browser recovery');
 assert.equal(PS.projectTitle({models:1,recovery:'kept'},when),'Untitled project · not saved to a file · kept for recovery in this browser');
 // a project file of its own: its words, as before (opened, then changed)
 assert.equal(PS.projectTitle({name:'both-models',models:2,file:{name:'both-models.json',how:'opened'},current:false,recovery:'updating',fromFile:'other.json'},when),'both-models · both-models.json · changed since opened · updating browser recovery');
 assert.equal(PS.projectTitle({name:'both-models',models:2,file:{name:'both-models.json',how:'opened'},current:true,recovery:'kept'},when),'both-models · both-models.json · opened');
});

test('P1 (B2): the page keeps the file a recovered record came from until a new project',()=>{
 const app=read('workspace-app.mjs');
 assert.ok(app.includes('const project={name:null,nameFrom:null,ids:{},next:1,file:null,stamp:null,scope:0,copyOf:null,recovered:null,fromFile:null};'));
 assert.ok(body(app,'function resetProject(','\n}').includes('file:null,fromFile:null,stamp:null,scope:project.scope+1,copyOf:null,recovered:null});'));
 assert.ok(body(app,'function restoreProjectName(','\n}').includes('project.fromFile=next.recovered.opened||next.recovered.changed||null;'));
 assert.ok(body(app,'function projectLine(){','\n}').includes('return projectTitle({name:project.name,fromFile:project.fromFile,models:'));
});
