// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
const {test,before}=require('node:test');const assert=require('node:assert/strict');
let snapshot,parseProject,opticalDocument,sectionSvg,opticalSection,createSession,parseSession,opticalSettings,OPTICAL_SETTINGS;
before(async()=>{
 ({snapshot,parseProject}=await import('../../packages/simcase/src/simcase/studio/static/workspace-project.mjs'));
 ({opticalDocument}=await import('../../packages/simcase/src/simcase/studio/static/workspace-optical.mjs'));
 ({sectionSvg,opticalSection}=await import('../../packages/simcase/src/simcase/studio/static/workspace-section.mjs'));
 ({createSession,parseSession,opticalSettings,OPTICAL_SETTINGS}=await import('../../packages/simcase/src/simcase/studio/static/workspace-notebook.mjs'));
});
const model=()=>({width:500,height:300,voltage:1,electric:false,heat:false,structure:false,optics:true});
const setup=()=>({materials:{Core:'Silicon',Oxide:'Silica',Heater:''},temperature:293.15,cooling:'',fixed:'',terminal:''});
const run=input=>({job:'abcdef12',completedAt:'2026-10-26T00:00:00Z',input,settings:opticalSettings(input.model.height),neff:[2.5,1.8],field:{nodes:[[0,0],[1,0],[0,1]],triangles:[[0,1,2]],real:[[[1,0,0]],[[0,1,0]]],imag:[[[0,0,0]],[[0,0,0]]]},origin:'local'});
test('legacy projects migrate to explicit 220 nm; v2 requires bounded height and nm units',()=>{
 const legacy=snapshot(model(),setup());legacy.version=1;delete legacy.model.height;delete legacy.units.height;delete legacy.model.wavelength;delete legacy.model.coreMesh;
 const migrated=parseProject(JSON.stringify(legacy));assert.equal(migrated.version,3);assert.equal(migrated.model.height,220);
 for(const change of [d=>delete d.model.height,d=>d.model.height=99,d=>d.model.height=501,d=>d.model.height=null,d=>d.units.height='um']){const d=snapshot(model(),setup());change(d);assert.throws(()=>parseProject(JSON.stringify(d)));}
 legacy.model.height=300;assert.throws(()=>parseProject(JSON.stringify(legacy)));
});
test('height drives submitted shape, grading centre, physical preview and dimension labels',()=>{
 for(const height of [100,300.5,500]){const m={...model(),height},d=opticalDocument(m,setup()),c=opticalSection(m.width,height).core;
 assert.equal(d.geometry.shapes[0].h,height/1000);assert.equal(d.mesh.grading.center[1],height/2000);
 assert.ok(Math.abs(c.height-height/10)<1e-12);assert.ok(Math.abs(c.y+c.height-175)<1e-12);
 assert.ok(sectionSvg(500,'Core',null,'Bodies',height).includes('500 × '+height+' nm'));
 }
});
test('sessions retain each captured height and reject mismatched result provenance',()=>{
 const input=snapshot(model(),setup()),r=run(input);const session=createSession(input,[r],r.job,[r.job,r.job]);
 assert.equal(session.version,3);const restored=parseSession(JSON.stringify(session));assert.equal(restored.runs[0].input.model.height,300);assert.equal(restored.runs[0].settings.height_nm,300);
 session.runs[0].settings.height_nm=220;assert.throws(()=>parseSession(JSON.stringify(session)));
 const legacy=snapshot(model(),setup());legacy.version=1;delete legacy.model.height;delete legacy.units.height;delete legacy.model.wavelength;delete legacy.model.coreMesh;
 const old=run(input);old.input=legacy;old.settings=OPTICAL_SETTINGS;
 const oldSession={...session,version:1,input:legacy,runs:[old]};const imported=parseSession(JSON.stringify(oldSession));assert.equal(imported.runs[0].input.model.height,220);assert.equal(imported.runs[0].settings.adapter,'optical-fixed-v1');
});
