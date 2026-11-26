// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
// The session files of design "Session versions 16 and 17" (optical session version 16: run time on
// open-boundary runs, amendment A1).
//
// timedSession(N, P, RES, RR, dir): the version 16 session of RT1, RT6 and T18-G1, three T18 runs of
// real results (tools/studio_run_retention.mjs cases, solved by a local `python -m simcase.studio.server`
// single threaded and followed as the page follows a job: startedAt after POST /api/run returns, a
// status poll every 700 ms, then the result read and its run built), written without their fields:
//   Run 3  t18closed2  closed window, 2 modes: its wall time stays in the tab (no time keys)
//   Run 4  t18open     open on all four edges, group index on: duration and timings
//   Run 5  t16         open on all four edges, 2 modes: duration and timings (T18-G1's d5)
// The durations are the wall times measured on 2026-11-26 (MEASURED); timings are the results' own.
// Its runs are marked read from a file (origin "imported"), as compact_sessions.mjs does.
// The inputs are t16's (group index off). Written again with
//   node timed_sessions.mjs write <static folder URL>/ <results folder> > optical-v16-times.json
// where the results folder holds <case>.result.json of each case.
//
// readWith(staticUrl, folder): what a Studio reads of that file alone, in a project file and in a
// browser recovery record, and whether its store adopts the record (RT5). Run once with the static
// folder of the merge base (the last Studio before session version 16) to write refusals-v16-<sha>.json:
//   git worktree add <tmp> <sha>
//   node timed_sessions.mjs read file://<tmp>/packages/simcase/src/simcase/studio/static/ <fixtures folder> > refusals-v16-<sha>.json
import fs from 'node:fs';import path from 'node:path';

export const NUMBERS=Object.freeze([3,4,5]);
export const CASES=Object.freeze(['t18closed2','t18open','t16']);
/** The wall time of each run as the page measured it (ms), 2026-11-26, this container, single threaded. */
export const MEASURED=Object.freeze({t18closed2:1824,t18open:179242,t16:61552});
const VIEW={mode:0,component:'magnitude',window:'Core region'};
const JOBS=Object.freeze({t18closed2:'c1600003',t18open:'c1600004',t16:'c1600005'});
export async function timedRuns(N,RES,RR,dir){
 const runs=[];
 for(const [i,name] of CASES.entries()){
  const result=JSON.parse(fs.readFileSync(path.join(dir,name+'.result.json'),'utf8'));
  const run=RES.runOfResult(result,await RR.pendingOf(name,JOBS[name]),{completedAt:new Date(Date.UTC(2026,10,26,9,10+i)).toISOString()});
  // a run read from a file (origin "imported"), so the file read and written again is its own bytes
  run.duration=MEASURED[name];run.number=NUMBERS[i];run.origin='imported';
  runs.push(run);
 }
 return runs;
}
export async function timedSession(N,P,RES,RR,dir){
 const runs=await timedRuns(N,RES,RR,dir),input=await RR.inputsOf('t16',runs[2]);
 return N.sessionText(input,runs,runs[2].job,[runs[1].job,runs[2].job],VIEW,{keep:new Set()});
}
const message=f=>{try{f();return null;}catch(e){return e.message;}};
// what the Studio at staticUrl reads: the file alone, in a project and in a recovery record, and
// whether the store adopts that record (as compact_sessions.mjs reads the version 14 file)
export async function readWith(staticUrl,folder){
 const load=name=>import(staticUrl+name);
 const N=await load('workspace-notebook.mjs'),PF=await load('workspace-project-file.mjs'),R=await load('workspace-notebook-recovery.mjs');
 const text=fs.readFileSync(path.join(folder,'optical-v16-times.json'),'utf8');
 const project=PF.writeProject({name:'timed',savedAt:'2026-11-26T10:00:00.000Z',studio:'0.0.0',active:'m1',entries:[PF.projectEntry({id:'m1',kind:'workspace',title:'Optical waveguide',card:'optical',text})]}).text;
 const record=session=>({version:1,savedAt:'2026-11-26T10:00:00.000Z',session});
 const store=R.indexedNotebookStore({open(){throw new Error('no database');}});
 try{R.readNotebookRecovery(record(text));store.adopt(record(text));}catch{}
 const adopted=await store.save(record(text)).then(()=>true,e=>e.message!=='Read browser recovery before saving.');
 return {
  session:message(()=>N.parseSession(text)),
  project:message(()=>PF.readProject(project)),
  recovery:message(()=>R.readNotebookRecovery(record(text))),
  adopted,
 };
}
if(process.argv[2]==='write'){
 const base=process.argv[3];
 const N=await import(base+'workspace-notebook.mjs'),P=await import(base+'workspace-project.mjs'),RES=await import(base+'workspace-result-run.mjs');
 const RR=await import(new URL('../../../tools/studio_run_retention.mjs',import.meta.url).href);
 process.stdout.write(await timedSession(N,P,RES,RR,process.argv[4]));
}else if(process.argv[2]==='read'){
 process.stdout.write(JSON.stringify(await readWith(process.argv[3],process.argv[4]),null,1)+'\n');
}
