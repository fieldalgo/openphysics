// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
// Study settings with the inputs (inputs file version 8): Modes to find (model.modeCount, written
// only when not 2) and the group index option (model.groupIndex, written only when on). With the
// defaults the inputs file is version 7, byte for byte as before, and so is a session written from
// it; an input of version 8 is held by an optical session of version 9 only. The fixture
// inputs-v7-optical.json is the file the writer before version 8 (main at ef15b75) wrote for the
// Optical waveguide template; B1 pins its bytes.
const test=require('node:test');const assert=require('node:assert/strict');
const fs=require('node:fs');const path=require('node:path');const crypto=require('node:crypto');
const STATIC='../../packages/simcase/src/simcase/studio/static/';
const FIXTURES=path.join(__dirname,'studio_session_fixtures');
const fixture=name=>fs.readFileSync(path.join(FIXTURES,name),'utf8');
let P,N,A,H,J;
test.before(async()=>{
 P=await import(STATIC+'workspace-project.mjs');N=await import(STATIC+'workspace-notebook.mjs');A=await import(STATIC+'workspace-applications.mjs');
 H=await import(STATIC+'workspace-heat.mjs');J=await import(STATIC+'workspace-joule.mjs');
});
// the state and setup of the page after the Optical waveguide card (workspace-app.mjs)
const page=()=>{
 const state={height:220,width:500,wavelength:1550,coreMesh:30,modeCount:2,groupIndex:false,shapes:[{name:'Core',type:'rect',material:'Silicon',x:-250,y:0,w:500,h:220}],thermal:H.validateThermal(H.DEFAULT_THERMAL),joule:J.validateJoule(J.DEFAULT_JOULE),voltage:1,heat:true,structure:true,optics:true};
 Object.assign(state,A.templatePhysics('optical'));
 return {state,setup:{materials:{Core:'Silicon',Oxide:'Silica',Heater:''},cooling:'',temperature:293.15,fixed:'',terminal:''}};
};
// the inputs file as Save inputs only writes it
const fileText=({modeCount=2,groupIndex=false}={})=>{const {state,setup}=page();state.modeCount=modeCount;state.groupIndex=groupIndex;return JSON.stringify(P.withStudy(P.snapshot(state,setup),{modeCount,groupIndex}),null,2)+'\n';};
const sha=text=>crypto.createHash('sha256').update(text).digest('hex');

test('B1: 2 modes and the box off write the version 7 inputs file of before, byte for byte',()=>{
 const text=fileText();
 assert.equal(text,fixture('inputs-v7-optical.json'));
 assert.equal(Buffer.byteLength(text),3340);
 assert.equal(sha(text),'a7e21917051dfd8cae0009ffa446ab8cf8b34679b042a95589595bdf426780cc');
 // page state with the defaults in it is still version 7
 const {state,setup}=page();assert.equal(JSON.stringify(P.snapshot(state,setup),null,2)+'\n',text);
 // reading it gives the defaults and writes it again unchanged (opening never rewrites it)
 const read=P.parseProject(text);assert.equal(read.version,7);assert.deepEqual(P.projectStudy(read),{modeCount:2,groupIndex:false});
 assert.equal(JSON.stringify(read,null,2)+'\n',text);
});

test('R1-R3: Modes to find and the box give version 8, which round-trips bit for bit',()=>{
 for(const [study,expected] of [[{modeCount:4},{modeCount:4}],[{groupIndex:true},{groupIndex:true}],[{modeCount:8,groupIndex:true},{modeCount:8,groupIndex:true}],[{modeCount:1},{modeCount:1}]]){
  const text=fileText(study),doc=JSON.parse(text);
  assert.equal(doc.version,8,text);
  const {modeCount,groupIndex,...rest}=doc.model;
  assert.deepEqual({...(modeCount===undefined?{}:{modeCount}),...(groupIndex===undefined?{}:{groupIndex})},expected);
  // the only difference from version 7: the version and the keys after model.joule
  assert.equal(JSON.stringify({...doc,version:7,model:rest},null,2)+'\n',fixture('inputs-v7-optical.json'));
  assert.deepEqual(Object.keys(doc.model).slice(-Object.keys(expected).length),Object.keys(expected));
  const read=P.parseProject(text);
  assert.deepEqual(P.projectStudy(read),{modeCount:2,groupIndex:false,...study});
  assert.equal(JSON.stringify(read,null,2)+'\n',text);
  // the run's inputs: version 7 again, the same bytes as before
  assert.equal(JSON.stringify(P.withoutStudy(read),null,2)+'\n',fixture('inputs-v7-optical.json'));
 }
});

test('version 8 is read with checked study settings; versions 6 and 7 ignore them',()=>{
 const doc=JSON.parse(fileText({modeCount:4}));
 for(const bad of [0,9,2.5,'4',null])assert.throws(()=>P.parseProject(JSON.stringify({...doc,model:{...doc.model,modeCount:bad}})),{message:'Invalid Modes to find (a whole number from 1 to 8).'},String(bad));
 for(const bad of ['true',1,null])assert.throws(()=>P.parseProject(JSON.stringify({...doc,model:{...doc.model,groupIndex:bad}})),{message:'Invalid group index option.'},String(bad));
 // a version 8 file with the default values reads as version 7 inputs
 const plain=P.parseProject(JSON.stringify({...doc,model:{...doc.model,modeCount:2,groupIndex:false}}));
 assert.equal(JSON.stringify(plain,null,2)+'\n',fixture('inputs-v7-optical.json'));
 // a version 7 file is read as before: keys it did not define are not read
 const seven=P.parseProject(JSON.stringify({...doc,version:7}));
 assert.equal(seven.version,7);assert.deepEqual(P.projectStudy(seven),{modeCount:2,groupIndex:false});
});

test('F1: a version newer than the reader reads is refused with the existing message',()=>{
 const doc=JSON.parse(fileText({modeCount:4}));
 for(const version of [9,10])assert.throws(()=>P.parseProject(JSON.stringify({...doc,version})),{message:'Unsupported project format or version.'});
});

const v8Input=()=>P.parseProject(fileText({modeCount:3,groupIndex:true}));
const v7Input=()=>P.parseProject(fileText());
const view={mode:0,component:'magnitude',window:'Core region'};

test('B2 and S-b: sessions of version 7 inputs stay version 7, byte for byte; version 8 inputs need version 9',()=>{
 for(const name of ['empty','one','three']){
  const st=JSON.parse(fixture(`state-${name}.json`));
  assert.equal(N.sessionText(st.input,st.runs,st.selected,st.comparison,st.view),fixture(`optical-v7-${name}.json`),name);
  // the same runs with study settings in the input: version 9, whose input is the inputs file
  const input=P.withStudy(st.input,{modeCount:4});
  const doc=JSON.parse(N.sessionText(input,st.runs,st.selected,st.comparison,st.view));
  assert.equal(doc.version,9,name);assert.deepEqual(doc.input,input,name);
 }
 assert.equal(N.sessionVersion([],view,null,v7Input()),7);assert.equal(N.sessionVersion([],view,null,v8Input()),9);
});

test('S-a: a version 9 session with a version 8 input round-trips bit for bit and keeps its study settings',()=>{
 const text=N.sessionText(v8Input(),[],null,[null,null],view);
 const read=N.parseSession(text);
 assert.equal(read.input.version,8);assert.deepEqual(P.projectStudy(read.input),{modeCount:3,groupIndex:true});
 assert.equal(N.sessionText(read.input,read.runs,read.selected,read.comparison,read.view),text);
});

test('a run version 9 cannot hold names the study setting that asked for version 9',()=>{
 // a run read from a version 7 file whose second index is not above 1.45 stays in a version 7
 // session; with Modes to find 3 the session needs version 9, and the refusal says why
 const st=JSON.parse(fixture('state-one.json')),r={...st.runs[0],effective_index:[st.runs[0].effective_index[0],1.40]};
 assert.equal(JSON.parse(N.sessionText(st.input,[r],r.job,[r.job,r.job],view)).version,7);
 assert.throws(()=>N.sessionText(P.withStudy(st.input,{modeCount:3}),[r],r.job,[r.job,r.job],view),{message:/^Run 1: its effective indices are not ranked by Re n_eff above n = 1\.45, so a version 9 session cannot hold it \(the current Modes to find or group index option is saved in version 9 only; set 2 modes and the option off to save as version 7\)\. Remove the run or save it in a session of its own\.$/});
});

test('S-c: a version 7 session does not hold a version 8 input, and a run keeps version 7 inputs',()=>{
 const doc=JSON.parse(fixture('optical-v7-empty.json'));doc.input=v8Input();
 assert.throws(()=>N.parseSession(JSON.stringify(doc)),{message:'A version 7 session holds an input file of version 6 or 7.'});
 const st=JSON.parse(fixture('state-one.json'));
 assert.throws(()=>N.validateRun({...st.runs[0],input:P.withStudy(st.runs[0].input,{modeCount:4})},true),{message:'Unsupported run settings or input mismatch.'});
});
