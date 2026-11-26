// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
// Round 31 (agent proxy round 31 on main 6b1455b): K1, the Library restore box names one way back;
// K2, the question before an open-boundary run whose group index was carried over; K3, the Compare
// pickers' visible labels Run A and Run B.
// Plain text comparison only: no RegExp is built from a dynamic string.
const test=require('node:test');const assert=require('node:assert/strict');
const fs=require('node:fs');const path=require('node:path');
const STATIC='../../packages/simcase/src/simcase/studio/static/';
const read=name=>fs.readFileSync(path.join(__dirname,STATIC,name),'utf8');
const when=t=>t;

test('K1: the box note and the newest detail name no second way back',async()=>{
 const A=await import(STATIC+'workspace-applications.mjs');
 assert.equal(A.RESUME_NOTE,'Restore brings back completed runs kept in this browser, without recomputing.');
 const base={runs:1,model:'Optical waveguide',names:['Run 1'],savedAt:'T',file:'heater-study.json'};
 assert.equal(A.resumeDetail({...base,fileCurrent:true,fileSavedAt:'F'},when),'Kept in this browser T · same as heater-study.json, saved F');
 assert.equal(A.resumeDetail({...base,fileCurrent:true},when),'Kept in this browser T · same as heater-study.json as opened');
 // no string of the newest offer (1–6), single or pair, names Open file…
 const pair=c=>({model:'Heated silicon waveguide',runs:1,savedAt:'T',fileCurrent:c});
 for(const file of [null,'heater-study.json'])for(const fileCurrent of [true,false,null])for(const fileSavedAt of ['F',undefined])for(const p of [undefined,pair(true),pair(false)]){
  const d=A.resumeDetail({...base,file,fileCurrent,fileSavedAt,pair:p},when);assert.ok(!d.includes('Open file'),d);
  const c=A.resumeChoices({...base,file,fileCurrent,fileSavedAt,pair:p},[],when);assert.ok(!c.newest.detail.includes('Open file'),c.newest.detail);
 }
 // the box keeps its structure: the earlier-copies and #resume-other details are unchanged
 const lib=read('workspace-applications.mjs');
 assert.ok(!lib.includes('Open file… at the top opens a project file instead.'));
 const older={runs:2,model:'Optical waveguide',names:['Run 1','Run 2'],savedAt:'8:30',file:'both-models.json',fileCurrent:true,fileSavedAt:'8:31'};
 const box=A.resumeChoices({runs:1,model:'Heated silicon waveguide',names:['Run 1'],savedAt:'8:32'},[{...older,index:0}],when);
 assert.equal(box.other.detail,'Older · kept in this browser 8:30 · same as both-models.json, saved 8:31 · Open file… gives the same runs');
});
