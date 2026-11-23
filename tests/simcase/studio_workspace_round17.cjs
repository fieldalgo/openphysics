// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
// Round 17: run numbers that never change within a tab, and the message naming a run the limit
// dropped. Plain text comparison only: no RegExp is built from a dynamic string.
const test=require('node:test');const assert=require('node:assert/strict');
const fs=require('node:fs');const path=require('node:path');
const STATIC='../../packages/simcase/src/simcase/studio/static/';
const read=name=>fs.readFileSync(path.join(__dirname,STATIC,name),'utf8');
let W,N,P;
test.before(async()=>{W=await import(STATIC+'workspace-workflow.mjs');N=await import(STATIC+'workspace-notebook.mjs');P=await import(STATIC+'workspace-project.mjs');});

const input=()=>P.snapshot({width:700,voltage:1,electric:false,heat:false,structure:false,optics:true},{materials:{Core:'Silicon',Oxide:'Silica',Heater:''},temperature:293.15,cooling:'',fixed:'',terminal:''});
const run=(job,extra={})=>({job,completedAt:'2026-11-23T00:00:00.000Z',settings:N.opticalSettings(),input:input(),effective_index:[2.4,1.7],
 field:{node_coordinates:[[0,0],[1e-6,0],[0,1e-6]],triangles:[[0,1,2]],real:[[[1,0,0]],[[0,1,0]]],imag:[[[0,0,0]],[[0,0,0]]]},origin:'local',...extra});
const job=i=>i.toString(16).padStart(8,'0');
// a field of 200 triangles, so that a run written without it is smaller
const bigField=()=>{const n=200,X=[],T=[];for(let i=0;i<n;i++){X.push([i*1e-8,0],[i*1e-8,1e-8]);}for(let i=0;i<n-1;i++)T.push([2*i,2*i+2,2*i+1]);T.push([0,2,3]);
 const mode=k=>T.map((_,i)=>[k?0:1+i*1e-3,k?1+i*1e-3:0,0]);return {node_coordinates:X,triangles:T,real:[mode(0),mode(1)],imag:[T.map(()=>[0,0,0]),T.map(()=>[0,0,0])]};};

test('U2: the limit drops the oldest unpinned run and renumbers nothing; the next number is the largest used + 1',()=>{
 let runs=[],used=0;const dropped=[];
 for(let i=0;i<8;i++){const r=run(job(i));used=W.numberRuns([r],used);const next=N.appendRun(runs,r);dropped.push(...runs.filter(x=>!next.includes(x)));runs=next;}
 assert.deepEqual(runs.map(r=>r.number),[3,4,5,6,7,8]);
 assert.deepEqual(dropped.map(r=>r.number),[1,2]);
 assert.equal(used,8);
 // the same job again keeps its number (appendRun replaces it in place of the old record)
 const again=run(job(5));again.number=runs.find(r=>r.job===job(5)).number;used=W.numberRuns([again],used);runs=N.appendRun(runs,again);
 assert.deepEqual(runs.map(r=>r.number),[3,4,5,7,8,6]);assert.equal(used,8);
 // a run added after a pinned one keeps counting from the largest
 runs[0].pinned=true;const ninth=run(job(9));used=W.numberRuns([ninth],used);const next=N.appendRun(runs,ninth);
 assert.equal(ninth.number,9);assert.deepEqual(runs.filter(x=>!next.includes(x)).map(r=>r.number),[4]);
});
test('U2: a file opened numbers its runs from 1; runs added from a file continue from the largest',()=>{
 const opened=[run(job(1)),run(job(2)),run(job(3))];assert.equal(W.numberRuns(opened),3);assert.deepEqual(opened.map(r=>r.number),[1,2,3]);
 const added=[run(job(7)),run(job(8))];assert.equal(W.numberRuns([...opened.slice(1),...added],5),7);assert.deepEqual(added.map(r=>r.number),[6,7]);
});
test('U2: the message of a dropped run names its number, name, geometry and modes',()=>{
 const r=run(job(3),{number:3});
 assert.equal(W.droppedRunText(r),'Run 3 (700 × 220 nm · 2 modes) was dropped: up to six runs are kept; pin a run to keep it.');
 assert.equal(W.droppedRunText({...r,label:'Design A'}),'Run 3 · Design A (700 × 220 nm · 2 modes) was dropped: up to six runs are kept; pin a run to keep it.');
});
test('U2: the number is not written to files; the save names a run by its number',()=>{
 const a=run(job(1),{number:4,field:bigField()}),b=run(job(2),{number:7,field:bigField()}),view={mode:0,component:'magnitude',window:'Core region'};
 const full=N.writeOpticalSession(input(),[a,b],a.job,[a.job,b.job],view);
 assert.equal(full.ok,true);assert.equal(JSON.parse(full.text).runs.some(r=>Object.hasOwn(r,'number')),false);
 // over the limit: the fields of the selected run only; the run left without them is named by its number
 const limit=full.bytes-1,out=N.writeOpticalSession(input(),[a,b],a.job,[a.job,b.job],view,{keepSelected:true,limit});
 assert.equal(out.ok,true);assert.deepEqual(out.notKept,[7]);
 const plain=N.writeOpticalSession(input(),[{...a,number:undefined},{...b,number:undefined}],a.job,[a.job,b.job],view,{keepSelected:true,limit});
 assert.equal(plain.text,out.text);assert.deepEqual(plain.notKept,[2]);
 const refused=N.writeOpticalSession(input(),[{...a,pinned:true},b],a.job,[a.job,b.job],view,{keepSelected:true,limit:100});
 assert.equal(refused.ok,false);assert.ok(refused.refusal.startsWith('The selected and pinned runs (Run 4) are '),refused.refusal);
});
test('U2: the status line and the freshness words use the run number, not the list place',()=>{
 const runs=[run(job(4),{number:4}),run(job(5),{number:5})];
 runs.forEach(r=>{r.signature='x'+r.job;});
 const f=W.opticalFreshness(input(),runs,runs[1],2);assert.equal(f.run,5);
 assert.equal(W.opticalFreshness(input(),runs,null,2).run,5);
 const app=read('workspace-app.mjs');
 assert.ok(app.includes("function runNumber(run){return runs.includes(run)&&Number.isInteger(run.number)?run.number:null;}"));
});
