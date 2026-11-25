// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
// Keeping more runs (optical session version 13), the format. Pre-registered:
// K2 (every earlier optical fixture, the multiphysics session and the project file are read and
// written again byte for byte, and none is written as version 13), K3 (a version 13 round trip of
// nine runs numbered 2 and 4 to 11, a 21-run file refused, and the version 12 reader's number
// refusals on version 13) and K4 (main 3f16709, the last Studio before version 13, refuses the file by
// name alone, in a project and in a recovery record, and does not adopt that record:
// studio_session_fixtures/refusals-v13-3f16709.json, written by retained_sessions.mjs from that
// commit's static folder). The tab's part (the field budget) is in studio_run_retention_fields.cjs.
const test=require('node:test');const assert=require('node:assert/strict');
const fs=require('node:fs');const path=require('node:path');
const STATIC='../../packages/simcase/src/simcase/studio/static/';
const FIX=path.join(__dirname,'studio_session_fixtures');
const fixture=name=>fs.readFileSync(path.join(FIX,name),'utf8');
let N,P,S,PF,R,G,C,Q;
test.before(async()=>{
 N=await import(STATIC+'workspace-notebook.mjs');P=await import(STATIC+'workspace-project.mjs');S=await import(STATIC+'workspace-multiphysics-session.mjs');
 PF=await import(STATIC+'workspace-project-file.mjs');R=await import(STATIC+'workspace-notebook-recovery.mjs');
 G=await import('./studio_session_fixtures/retained_sessions.mjs');C=await import('./studio_session_fixtures/closed_sessions.mjs');
 Q=await import('./studio_session_fixtures/numbered_sessions.mjs');
});
const VIEW={mode:0,component:'magnitude',window:'Core region'};
const rewrite=text=>{const s=N.parseSession(text);return N.sessionText(s.input,s.runs,s.selected,s.comparison,s.view);};
// a session text edited, with each run's digest computed again unless keepDigest
const edit=(text,f,{keepDigest=false}={})=>{const d=JSON.parse(text);f(d);if(!keepDigest)for(const r of d.runs){delete r.digest;r.digest=S.recordDigest(r);}return S.sessionJson(d);};
const V13='optical-v13-nine-runs.json';
const message='This session file is version 13, newer than this Studio reads (versions 6–12). Open it in a newer Studio.';

test('K2: every earlier optical fixture, the multiphysics session and the project file are written again byte for byte; none as version 13',()=>{
 const versions=[];
 const same=(text,name,expected=text)=>{const once=rewrite(text);assert.equal(once,expected,name);const v=JSON.parse(once).version;versions.push(v);assert.notEqual(v,13,name);assert.ok(JSON.parse(once).runs.length<=6,name);};
 // versions 6 and 7: a version 6 file is written as the version 7 file of the same state (as today)
 for(const state of ['empty','one','three']){
  const seven=fixture(`optical-v7-${state}.json`),once=rewrite(seven);
  same(once,`optical-v7-${state}.json written once`);same(fixture(`optical-v6-${state}.json`),`optical-v6-${state}.json`,once);
 }
 // the texts main 13f07f4 wrote (versions 9, 7 and 10) and the version 10 files of f8ece10 and 083e151
 const golden=JSON.parse(fixture('sessions-rewritten-13f07f4.json'));
 // the synthetic version 9 session holds runs of this tab (origin "local"): it is written from them again,
 // and that text is its own bytes once read (a file read takes origin "imported", as today)
 for(const [name,text] of Object.entries(golden)){if(name==='synthetic version 9'){same(rewrite(text),name+' written once');continue;}same(text,name);same(fixture(name),name+' from its file',text);}
 // the sessions of closed_sessions.mjs (the synthetic version 9 session; version 11 with a closed-window
 // search run) and of numbered_sessions.mjs (version 12, its fixture)
 assert.equal(C.synthetic(N,P),golden['synthetic version 9']);
 const v9=N.parseSession(C.synthetic(N,P)),target=N.validateRun({...v9.runs[0],job:'0000000c',settings:N.closedTargetSettings(v9.runs[0].settings,2.46)});
 const eleven=N.sessionText(v9.input,[...v9.runs,target],v9.selected,v9.comparison,v9.view);assert.equal(JSON.parse(eleven).version,11);same(eleven,'version 11');
 const twelve=fixture('optical-v12-numbers.json');assert.equal(Q.numberedSession(N,P,FIX),twelve);same(twelve,'optical-v12-numbers.json');
 assert.deepEqual([...new Set(versions)].sort((a,b)=>a-b),[7,9,10,11,12]);
 // the multiphysics session (version 8) and the project file (version 1), unchanged
 const mp=N.parseSession(fixture('multiphysics-v8.json'));
 assert.equal(S.writeMultiphysicsSession({document:mp.document,runs:mp.runs,baselines:mp.baselines,selected:mp.selected,view:mp.view}).text,fixture('multiphysics-v8.json'));
 const project=fixture('project-v1.json'),read=PF.readProject(project),doc=JSON.parse(project);
 const again=PF.writeProject({name:doc.name,savedAt:doc.savedAt,studio:doc.studio,active:doc.active,entries:doc.models.map((m,i)=>PF.projectEntry({id:m.id,kind:m.kind,title:m.title,card:m.card,text:read.models[i].text}))});
 assert.equal(again.text,project);
 // the run counts: six or fewer runs are written as before, whatever their numbers
 for(const n of [0,1,6])assert.notEqual(N.sessionVersion(Array.from({length:n},(_,i)=>({...v9.runs[0],number:i+2})),VIEW),13,n+' runs');
});

test('K3: a version 13 session of nine runs numbered 2 and 4 to 11 is read and written again byte for byte',()=>{
 const text=fixture(V13),doc=JSON.parse(text);
 assert.equal(text,G.retainedSession(N,P,FIX),'the fixture is what this Studio writes');
 assert.equal(doc.version,13);assert.deepEqual(doc.runs.map(r=>r.number),[2,4,5,6,7,8,9,10,11]);
 // the records are those of version 12: number after job, the same keys and top-level keys
 for(const r of doc.runs){assert.deepEqual(Object.keys(r).slice(0,3),['job','number','completedAt']);assert.equal(r.digest,S.recordDigest(r));}
 assert.deepEqual(Object.keys(doc),['format','version','application','input','runs','selected','comparison','view']);
 // Run 4 pinned, an open run, a closed-window search run and five runs without fields
 assert.deepEqual(doc.runs.map(r=>r.pinned),[false,true,false,false,false,false,false,false,false]);
 assert.deepEqual(doc.runs.map(r=>r.settings.adapter),['optical-shapes-v8','optical-shapes-v8','optical-shapes-v9','optical-shapes-v10','optical-shapes-v8','optical-shapes-v8','optical-shapes-v8','optical-shapes-v8','optical-shapes-v8']);
 assert.deepEqual(doc.runs.map(r=>Object.hasOwn(r,'field')),[true,true,false,true,false,false,false,false,true]);
 // write, parse, write: the same bytes; in a project and in a recovery record the same runs
 const s=N.parseSession(text);assert.deepEqual(s.runs.map(r=>r.number),[2,4,5,6,7,8,9,10,11]);
 assert.equal(N.sessionText(s.input,s.runs,s.selected,s.comparison,s.view),text);assert.equal(rewrite(rewrite(text)),text);
 const project=PF.writeProject({name:'both-models',savedAt:'2026-11-25T10:00:00.000Z',studio:'0.0.0',active:'m1',entries:[PF.projectEntry({id:'m1',kind:'workspace',title:'Optical waveguide',card:'optical',text})]}).text;
 assert.deepEqual(PF.readProject(project).models[0].session.runs.map(r=>r.number),[2,4,5,6,7,8,9,10,11]);
 assert.deepEqual(PF.KIND_VERSIONS.workspace,N.OPTICAL_SESSION_VERSIONS);assert.ok(N.OPTICAL_SESSION_VERSIONS.includes(13));
 const rec=R.readNotebookRecovery({version:1,savedAt:'2026-11-25T10:00:00.000Z',session:text});
 assert.deepEqual(rec.session.runs.map(r=>r.number),[2,4,5,6,7,8,9,10,11]);assert.ok(rec.session.runs.every(r=>r.origin==='recovered'));
 // the same runs numbered by their place are still version 13 (more than six runs)
 const placed=s.runs.map((r,i)=>Object.assign(N.validateRun(r),{number:i+1}));assert.equal(N.sessionVersion(placed,VIEW),13);
 // twenty runs are version 13; a 21-run file is refused before its runs are read
 const run=s.runs[1],many=n=>Array.from({length:n},(_,i)=>Object.assign(N.validateRun({...run,job:(0x100+i).toString(16).padStart(8,'0'),pinned:false}),{number:i+1}));
 const twenty=N.sessionText(s.input,many(20),null,[null,null],VIEW);assert.equal(JSON.parse(twenty).version,13);assert.equal(rewrite(twenty),twenty);
 assert.equal(N.parseSession(twenty).runs.length,20);
 const twentyOne=edit(twenty,d=>{d.runs.push({...d.runs[19],job:'000001ff',number:21});});
 assert.throws(()=>N.parseSession(twentyOne),{message:'Unsupported session format or run count.'});
 // a version 13 file of six or fewer runs (for example edited by hand) is read; a version 12 file of
 // more than six runs is refused as before
 const six=edit(twenty,d=>{d.runs=d.runs.slice(0,6);});assert.equal(N.parseSession(six).runs.length,6);
 const empty=edit(twenty,d=>{d.runs=[];});assert.equal(N.parseSession(empty).runs.length,0);
 assert.throws(()=>N.parseSession(edit(text,d=>{d.version=12;})),{message:'Unsupported session format or run count.'});
 // Add runs from file takes up to 20 runs
 assert.equal(N.mergeRuns([],many(20)).runs.length,20);
 assert.throws(()=>N.mergeRuns([{...many(1)[0],job:'0000ffff',pinned:true}],many(20)),{message:'Imported runs and pinned references exceed 20 slots. Unpin a reference or import a selected-run file.'});
});

test('K3: the version 12 reader\'s refusals hold for version 13',()=>{
 const text=fixture(V13),refused=(t,m)=>assert.throws(()=>N.parseSession(t),{message:m});
 // a number edited after the save: the run's digest refuses it
 refused(edit(text,d=>{d.runs[1].number=3;},{keepDigest:true}),'Run 2 changed after it was saved (its check value does not match).');
 // removed (by position), with or without its digest computed again
 refused(edit(text,d=>{delete d.runs[1].number;}),'Run 2: missing number.');
 refused(edit(text,d=>{delete d.runs[1].number;},{keepDigest:true}),'Run 2: missing number.');
 // not a safe integer of at least 1
 for(const n of [0,-1,1.5,'5',null,2**53,true])refused(edit(text,d=>{d.runs[1].number=n;}),'Run 2: invalid run number.');
 // out of order, and the same number twice
 refused(edit(text,d=>{d.runs[1].number=12;}),'Run 3 is numbered 5, not after Run 2\'s 12.');
 refused(edit(text,d=>{d.runs[2].number=4;}),'Two runs have the same number 4.');
 refused(edit(text,d=>{d.runs[8].number=2;}),'Two runs have the same number 2.');
 refused(edit(text,d=>{d.runs[4].number=12;}),'Run 6 is numbered 8, not after Run 5\'s 12.');
 // after these checks validateRun names the stored number
 refused(edit(text,d=>{d.runs[3].settings.search_target=1.45;}),'Run 6: invalid search target. Search near n_eff must lie between 1.45 and 3.4777 (3 decimals).');
 refused(edit(text,d=>{d.runs[4].effective_index.reverse();}),'Run 7: its effective indices are not ranked by Re n_eff.');
 // an unknown run key, as in version 12; versions 9 to 11 hold no number
 refused(edit(text,d=>{d.runs[0].duration=12;}),'Run 1: unknown key "duration".');
 refused(edit(text,d=>{d.version=11;d.runs=d.runs.slice(0,6);}),'Run 1: unknown key "number".');
 // what a version 13 reader refuses is not written
 const s=N.parseSession(text),back=s.runs.map((r,i)=>Object.assign(N.validateRun(r),{number:i===1?1:r.number}));
 assert.throws(()=>N.sessionText(s.input,back,null,[null,null],VIEW),{message:'Run numbers must be whole numbers of at least 1, increasing in list order.'});
 // a version newer than 13 is refused by name
 refused(edit(text,d=>{d.version=14;}),'This session file is version 14, newer than this Studio reads (versions 6–13). Open it in a newer Studio.');
});

test('K4: main 3f16709 refuses version 13 by name, alone, in a project and in a recovery record, and does not adopt the record',()=>{
 const golden=JSON.parse(fixture('refusals-v13-3f16709.json'));
 assert.deepEqual(golden,{session:message,project:'Optical waveguide: '+message,recovery:message,adopted:false});
});
