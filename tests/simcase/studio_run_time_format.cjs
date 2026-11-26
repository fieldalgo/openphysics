// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
// Run time on open-boundary runs (optical session version 16; design "Session versions 16 and 17",
// slice S1, amendment A1). Pre-registered: RT1 (a version 16 round trip of runs with duration and
// timings: the same bytes and the same plan line, estimate and comparable run; 1, 6, 7 and 20 runs,
// and with compact fields), RT2 (every committed fixture is written again byte for byte, none as
// version 16, its runs without a time), RT3 (a resumed open run keeps timings only and is written as
// version 16; a version 14 file plus a new closed run stays version 14 byte for byte, plus a new open
// run it is version 16 with the old records and digests unchanged), RT4 (damaged times are refused by
// name), RT5 (the merge base, the last Studio before version 16, refuses the file by name:
// studio_session_fixtures/refusals-v16-c0dbc09.json, written by timed_sessions.mjs from that commit's
// static folder), RT6 (browser recovery keeps the times; T18-G1 holds after Restore), RT7 (a closed
// run computed by this Studio carries neither key in a file) and T18-G1 (the Compute label with group
// index on after File › Open of the version 16 file: "… · about ${aboutText(3·d5)}").
const test=require('node:test');const assert=require('node:assert/strict');
const fs=require('node:fs');const path=require('node:path');
const STATIC='../../packages/simcase/src/simcase/studio/static/';
const FIX=path.join(__dirname,'studio_session_fixtures');
const fixture=name=>fs.readFileSync(path.join(FIX,name),'utf8');
const read=name=>fs.readFileSync(path.join(__dirname,STATIC,name),'utf8');
let N,P,S,PF,R,E,W,X,OB,OR,RES,T;
test.before(async()=>{
 N=await import(STATIC+'workspace-notebook.mjs');P=await import(STATIC+'workspace-project.mjs');S=await import(STATIC+'workspace-multiphysics-session.mjs');
 PF=await import(STATIC+'workspace-project-file.mjs');R=await import(STATIC+'workspace-notebook-recovery.mjs');E=await import(STATIC+'workspace-field-encoding.mjs');
 W=await import(STATIC+'workspace-workflow.mjs');X=await import(STATIC+'workspace-retention.mjs');OB=await import(STATIC+'workspace-open-boundary.mjs');
 OR=await import(STATIC+'workspace-open-run.mjs');RES=await import(STATIC+'workspace-result-run.mjs');T=await import('./studio_session_fixtures/timed_sessions.mjs');
});
const VIEW={mode:0,component:'magnitude',window:'Core region'};
const V16='optical-v16-times.json';
const message='This session file is version 16, newer than this Studio reads (versions 6–15). Open it in a newer Studio.';
const rewrite=text=>{const s=N.parseSession(text);return N.sessionText(s.input,s.runs,s.selected,s.comparison,s.view);};
const edit=(text,f,{keepDigest=false}={})=>{const d=JSON.parse(text);f(d);if(!keepDigest)for(const r of d.runs){delete r.digest;r.digest=S.recordDigest(r);}return S.sessionJson(d);};
const refused=(t,m)=>assert.throws(()=>N.parseSession(t),{message:m});
const kinds=()=>({isOpen:OR.isOpenRun,hasGroup:r=>r.group_index_method!==undefined});
// the Compute label of the T18 open inputs (two searches), with group index on or off, from runs
function plan(runs,groupIndex){
 const shapes=JSON.parse(fixture(V16)).input.model.shapes,edges={left:'open',right:'open',bottom:'open',top:'open'};
 const searches=OB.lowerTarget(OR.effectiveTarget({edges},shapes))!==null?2:1,p={open:true,searches,groupIndex,pmlCheck:false,modeCount:2};
 const last=W.lastComparableRun(runs,p,kinds()),estimate=groupIndex?W.groupIndexEstimate(runs,p,kinds()):null;
 return W.runPlanText({...p,last:groupIndex?null:last?W.runTime(last):null,estimate});
}
// the times a run holds, as a file writes them
const times=r=>({duration:r.duration,timings:r.timings});
// an open run with its field (a0000004 of the version 10 fixture) as a run of this tab with a time
function openRun(i,{duration=60000+i,timings={mesh:2.5,solve:70+i/1000}}={}){
 const base=N.parseSession(fixture('optical-v10-open-full-083e151.json')).runs.find(r=>r.job==='a0000004');
 const run=N.validateRun({...base,job:(0xd000+i).toString(16).padStart(8,'0'),completedAt:new Date(Date.UTC(2026,10,26,0,i)).toISOString(),...(duration===null?{}:{duration}),...(timings===null?{}:{timings})});
 return Object.assign(run,{number:i+1});
}

test('T18-G1: after File › Open of the version 16 file, group index on reads "about ${aboutText(3·d5)}"; off, "last such run m:ss" of Run 5',()=>{
 const text=fixture(V16),d=JSON.parse(text),s=N.parseSession(text);
 assert.equal(d.version,16);assert.deepEqual(d.runs.map(r=>r.number),[3,4,5]);
 // Run 5: open, no group index, its duration d5 and timings; Run 3 (closed) holds neither key
 const run5=d.runs[2],d5=run5.duration;
 assert.ok(run5.settings.pml&&run5.group_index_method===undefined&&Number.isSafeInteger(d5)&&N.isRunTimings(run5.timings));
 assert.ok(!('duration' in d.runs[0])&&!('timings' in d.runs[0]));
 assert.ok(d.runs[1].group_index_method!==undefined&&Number.isSafeInteger(d.runs[1].duration));
 const expected=`Open boundary · 2 modes · 2 searches · group index on (3 solves) · about ${W.aboutText(3*d5)}`;
 assert.equal(plan(s.runs,true),expected);
 assert.equal(plan(s.runs,false),`Open boundary · 2 modes · 2 searches · last such run ${W.durationText(d5)}`);
 console.log('T18-G1 d5',d5,'ms:',JSON.stringify(plan(s.runs,true)));
 // before Save: the runs of the tab that computed them (the generator's runs) read the same
 // after Open project: the project entry's session
 const project=PF.writeProject({name:'timed',savedAt:'2026-11-26T10:00:00.000Z',studio:'0.0.0',active:'m1',entries:[PF.projectEntry({id:'m1',kind:'workspace',title:'Optical waveguide',card:'optical',text})]}).text;
 assert.equal(plan(PF.readProject(project).models[0].session.runs,true),expected);
 // the estimate is the newest open run's time: d5 alone, so a resumed Run 5 (timings only) reads its compute time
 const resumed=s.runs.map(r=>r.number===5||r.job===run5.job?Object.assign({...r},{duration:undefined}):r);
 assert.equal(plan(resumed,true),`Open boundary · 2 modes · 2 searches · group index on (3 solves) · about ${W.aboutText(3*Math.round(1000*(run5.timings.mesh+run5.timings.solve)))}`);
});

test('RT1: runs with duration and timings round-trip byte for byte, with the same plan line, estimate and comparable run; 1, 6, 7 and 20 runs, and compact fields',()=>{
 const text=fixture(V16);
 assert.equal(rewrite(text),text);assert.equal(rewrite(rewrite(text)),text);
 const s=N.parseSession(text),d=JSON.parse(text);
 d.runs.forEach((r,i)=>assert.deepEqual(times(s.runs[i]),{duration:r.duration,timings:r.timings},`Run ${r.number}`));
 const again=N.parseSession(rewrite(text));
 for(const g of [true,false])assert.equal(plan(again.runs,g),plan(s.runs,g));
 const k=kinds();for(const open of [true,false])assert.equal(W.groupIndexEstimate(again.runs,{open},k),W.groupIndexEstimate(s.runs,{open},k));
 assert.equal(W.lastComparableRun(again.runs,{open:true,groupIndex:false},k).job,W.lastComparableRun(s.runs,{open:true,groupIndex:false},k).job);
 assert.equal(X.recomputeEstimate(again.runs[2]),` · about ${W.aboutText(d.runs[2].duration)}`);
 const input=s.input;
 for(const count of [1,6,7,20])for(const compact of [false,true]){
  const runs=Array.from({length:count},(_,i)=>openRun(i));if(compact)runs.forEach(N.compactRunField);
  const t=N.sessionText(input,runs,runs.at(-1).job,[null,null],VIEW),back=N.parseSession(t);
  assert.equal(JSON.parse(t).version,16,`${count} runs`);
  assert.equal(N.sessionText(back.input,back.runs,back.selected,back.comparison,back.view),t,`${count} runs${compact?' compact':''} again`);
  back.runs.forEach((r,i)=>assert.deepEqual(times(r),times(runs[i])));
  if(compact)assert.ok(back.runs.every(r=>E.isCompactField(r.field)));
  for(const g of [true,false])assert.equal(plan(back.runs,g),plan(runs,g));
 }
 // the record's keys in their order: RUN_KEYS_12 with duration and timings before digest
 const keys=JSON.parse(N.sessionText(input,[openRun(0)],null,[null,null],VIEW)).runs[0];
 assert.deepEqual(Object.keys(keys).slice(-3),['duration','timings','digest']);
 assert.ok(PF.KIND_VERSIONS.workspace.includes(16));assert.equal(N.sessionRunLimit(16),20);
});

test('RT2: every committed fixture is read and written again byte for byte, none as version 16, its runs without a time',()=>{
 const versions=[];
 const same=(text,name,expected=text)=>{const once=rewrite(text);assert.equal(once,expected,name);versions.push(JSON.parse(once).version);
  assert.ok(N.parseSession(text).runs.every(r=>W.runTime(r)===null),name);assert.ok(!/"(?:duration|timings)"/.test(once),name);};
 for(const state of ['empty','one','three']){const once=rewrite(fixture(`optical-v7-${state}.json`));same(once,`v7 ${state}`);same(fixture(`optical-v6-${state}.json`),`v6 ${state}`,once);}
 const golden=JSON.parse(fixture('sessions-rewritten-13f07f4.json'));
 for(const [name,text] of Object.entries(golden)){if(name==='synthetic version 9'){same(rewrite(text),name);continue;}same(text,name);same(fixture(name),name+' from its file',text);}
 for(const name of ['optical-v12-numbers.json','optical-v13-nine-runs.json','optical-v14-compact.json','optical-values-only-14.json'])same(fixture(name),name);
 assert.ok(!versions.includes(16));assert.deepEqual([...new Set(versions)].sort((a,b)=>a-b),[7,9,10,12,13,14]);
 // the project file and the multiphysics sessions
 const project=fixture('project-v1.json'),readP=PF.readProject(project),doc=JSON.parse(project);
 assert.equal(PF.writeProject({name:doc.name,savedAt:doc.savedAt,studio:doc.studio,active:doc.active,entries:doc.models.map((m,i)=>PF.projectEntry({id:m.id,kind:m.kind,title:m.title,card:m.card,text:readP.models[i].text}))}).text,project);
 for(const name of ['multiphysics-v8.json','multiphysics-v15-thirteen-runs.json']){const mp=N.parseSession(fixture(name));
  assert.equal(S.writeMultiphysicsSession({document:mp.document,runs:mp.runs,baselines:mp.baselines,selected:mp.selected,view:mp.view}).text,fixture(name),name);}
});

test('RT3: a resumed open run keeps timings only and is written as version 16; a version 14 file plus a new closed run stays version 14, plus a new open run it is version 16 with the old records unchanged',()=>{
 // the page: a job followed again with Resume keeps no wall time, and a wall time out of 1 ms to 7 days none either
 const app=read('workspace-app.mjs');
 assert.ok(app.includes('if(resumedJobs.has(pending.job)||!isRunDuration(completed.duration))delete completed.duration;resumedJobs.delete(pending.job);'));
 assert.ok(app.includes('jobOperation++;const resumed=pendingJob;resumedJobs.add(resumed.job);try{await jobMonitor.follow(resumed,connection.instance);'));
 assert.equal(app.split('resumedJobs.add(').length,2);
 const s=N.parseSession(fixture(V16)),run5=s.runs[2];
 const resumed=N.validateRun({...run5,duration:undefined});delete resumed.duration;Object.assign(resumed,{number:5});
 assert.equal(resumed.duration,undefined);assert.ok(N.isRunTimings(resumed.timings));
 const t=N.sessionText(s.input,[resumed],resumed.job,[null,null],VIEW),d=JSON.parse(t);
 assert.equal(d.version,16);assert.ok(!('duration' in d.runs[0]));assert.deepEqual(d.runs[0].timings,run5.timings);
 assert.equal(W.runTime(N.parseSession(t).runs[0]),Math.round(1000*(run5.timings.mesh+run5.timings.solve)));
 // a version 14 file and one new closed run of this tab (measured): version 14, its old runs byte for byte
 const v14=fixture('optical-v14-compact.json'),old=N.parseSession(v14),records=JSON.parse(v14).runs;
 const closed=Object.assign(N.validateRun({...old.runs[2],job:'0000000e',origin:'local',duration:2400}),{number:9});
 assert.equal(closed.duration,2400);assert.equal(closed.timings,undefined);
 const withClosed=JSON.parse(N.sessionText(old.input,[...old.runs,closed],old.selected,old.comparison,old.view));
 assert.equal(withClosed.version,14);
 records.forEach((r,i)=>assert.equal(S.sessionJson(withClosed.runs[i]),S.sessionJson(r),`Run ${r.number}`));
 assert.ok(!('duration' in withClosed.runs[3])&&!('timings' in withClosed.runs[3]));
 // plus one new open run: version 16, the old runs' records and digests unchanged
 const open=Object.assign(openRun(9),{number:10});
 const withOpen=JSON.parse(N.sessionText(old.input,[...old.runs,open],old.selected,old.comparison,old.view));
 assert.equal(withOpen.version,16);
 records.forEach((r,i)=>{assert.equal(S.sessionJson(withOpen.runs[i]),S.sessionJson(r),`Run ${r.number}`);assert.equal(withOpen.runs[i].digest,r.digest);});
 assert.deepEqual({duration:withOpen.runs[3].duration,timings:withOpen.runs[3].timings},times(open));
});

test('RT4: damaged times are refused by name; a hand edit without a new digest by the check-value sentence',()=>{
 const text=fixture(V16),run5=d=>d.runs[2];
 for(const bad of [0,-1,1.5,6.1e8,'73666',null])refused(edit(text,d=>{run5(d).duration=bad;}),'Run 5: invalid run time.');
 for(const bad of [{mesh:1,solve:2,total:3},{mesh:1},{mesh:-0.001,solve:2},{solve:2,mesh:1},{mesh:1,solve:'2'},{mesh:1,solve:6.1e5},[1,2],null])refused(edit(text,d=>{run5(d).timings=bad;}),'Run 5: invalid run time.');
 // a closed run never holds a time in a file
 refused(edit(text,d=>{d.runs[0].duration=1824;}),'Run 3: invalid run time.');
 refused(edit(text,d=>{d.runs[0].timings={mesh:0.64,solve:0.761};}),'Run 3: invalid run time.');
 // an edit of a time that keeps the old digest (the digest and key refusals name a run by its place
 // in the file, as for every version of 9 and later: Run 5 is the third)
 refused(edit(text,d=>{run5(d).duration+=1000;},{keepDigest:true}),'Run 3 changed after it was saved (its check value does not match).');
 refused(edit(text,d=>{run5(d).timings.solve=1;},{keepDigest:true}),'Run 3 changed after it was saved (its check value does not match).');
 // version 14 and earlier hold no time key: the version 13 reader's refusal stands
 refused(edit(text,d=>{d.version=14;}),'Run 2: unknown key "duration".');
 // another key, and 21 runs
 refused(edit(text,d=>{run5(d).wall=1;}),'Run 3: unknown key "wall".');
 const twenty=N.sessionText(N.parseSession(text).input,Array.from({length:20},(_,i)=>openRun(i)),null,[null,null],VIEW);
 refused(edit(twenty,d=>{d.runs.push({...d.runs[0],job:'000000ff',number:21});}),'Unsupported session format or run count.');
 // above 16 by name
 refused(edit(text,d=>{d.version=18;}),'This session file is version 18, newer than this Studio reads (versions 6–17). Open it in a newer Studio.');
});

test('RT5: the merge base c0dbc09 refuses version 16 by name, alone, in a project and in a recovery record, and does not adopt the record',async()=>{
 const golden=JSON.parse(fixture('refusals-v16-c0dbc09.json'));
 assert.deepEqual(golden,{session:message,project:'Optical waveguide: '+message,recovery:message,adopted:false});
 const now=await T.readWith(new URL(STATIC,'file://'+__dirname+'/').href,FIX);
 assert.deepEqual(now,{session:null,project:null,recovery:null,adopted:true});
});

test('RT6: a browser recovery record of a version 16 session restores the times; T18-G1 holds after Restore',()=>{
 const text=fixture(V16),s=N.parseSession(text);
 const restored=R.readNotebookRecovery({version:1,savedAt:'2026-11-26T10:00:00.000Z',session:text}).session;
 restored.runs.forEach((r,i)=>{assert.deepEqual(times(r),times(s.runs[i]));assert.equal(r.origin,'recovered');});
 assert.equal(plan(restored.runs,true),plan(s.runs,true));
 // the record the tab writes again (captureSession) is the file, byte for byte
 const make=N.captureSession(restored.input,restored.runs,restored.selected,restored.comparison,restored.view);
 assert.equal(N.parseSession(make()).runs.map(r=>JSON.stringify(times(r))).join(),s.runs.map(r=>JSON.stringify(times(r))).join());
});

test('RT7: a closed run computed by this Studio carries neither key in a file; its wall time stays in the tab',()=>{
 const text=fixture(V16),d=JSON.parse(text),s=N.parseSession(text),closed=s.runs[0];
 assert.equal(closed.settings.pml,undefined);assert.equal(closed.timings,undefined);
 // runOfResult keeps timings for an open run only (an open and a closed result of the same server)
 const closedResult={timings:{mesh:0.64,solve:0.76}};
 assert.equal(N.resultTimings(closedResult.timings).mesh,0.64);assert.equal(N.resultTimings({mesh:1}),null);assert.equal(N.resultTimings({mesh:0.0004,solve:1.23456}).solve,1.235);
 assert.ok(read('workspace-result-run.mjs').includes('...(open&&resultTimings(result.timings)?{timings:resultTimings(result.timings)}:{}),'));
 // a closed run of this tab with a wall time: kept in the tab, written without it, version unchanged
 const timed=Object.assign(N.validateRun({...closed,duration:1824,origin:'local'}),{number:3});
 assert.equal(timed.duration,1824);
 const alone=JSON.parse(N.sessionText(s.input,[timed],timed.job,[null,null],VIEW));
 assert.notEqual(alone.version,16);assert.ok(!('duration' in alone.runs[0])&&!('timings' in alone.runs[0]));
 assert.ok(!('duration' in d.runs[0])&&!('timings' in d.runs[0]));
 // the closed run's estimate in this tab is unchanged (round 18 and 23)
 assert.equal(W.groupIndexEstimate([timed],{open:false},kinds()),3*1824);
});
