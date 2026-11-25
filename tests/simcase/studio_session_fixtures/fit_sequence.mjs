// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
// Design "Compact field encoding", F2 (blind): no conversion while the fields fit. A seeded sequence of
// 2000 steps (results, the 20-run drop and its swap, pins, names, selections, comparisons, Add runs
// from file, saves, File › Open and Restore) of runs whose fields always fit the budget (each field 1
// to 18 kB, 20 runs at most), as run retention's K6 sequence takes them on the page's functions.
// After every step it records the Save text and the browser-recovery text.
//
// fitSequence(staticUrl) runs it on the Studio at staticUrl and returns the SHA-256 chain of those
// texts, a checkpoint every 100 steps, the session versions written and whether any text holds a
// compact field. Run once with the static folder of main 499a0d3 (the last Studio before session
// version 14) to write sequence-fit-499a0d3.json:
//   git worktree add <tmp> 499a0d3
//   node fit_sequence.mjs file://<tmp>/packages/simcase/src/simcase/studio/static/ > sequence-fit-499a0d3.json
import {createHash} from 'node:crypto';

const VIEW={mode:0,component:'magnitude',window:'Core region'};
const random=seed=>()=>{seed|=0;seed=seed+0x6D2B79F5|0;let t=Math.imul(seed^seed>>>15,1|seed);t=t+Math.imul(t^t>>>7,61|t)^t;return((t^t>>>14)>>>0)/4294967296;};

export async function fitSequence(staticUrl,{seed=20261126,steps=2000}={}){
 const load=name=>import(staticUrl+name);
 const N=await load('workspace-notebook.mjs'),P=await load('workspace-project.mjs'),W=await load('workspace-workflow.mjs'),X=await load('workspace-retention.mjs'),R=await load('workspace-notebook-recovery.mjs');
 const setup={materials:{Core:'Silicon',Oxide:'Silica',Heater:''},temperature:293.15,cooling:'',fixed:'',terminal:''};
 const input=P.snapshot({width:500,voltage:1,electric:false,heat:false,structure:false,optics:true,wavelength:1550,coreMesh:30},setup);
 const field=(k,t)=>{const X0=[],T=[];for(let i=0;i<=t;i++)X0.push([i*1e-8,0],[i*1e-8,1e-8]);for(let i=0;i<t;i++)T.push([2*i,2*i+2,2*i+1]);
  const mode=m=>T.map((_,i)=>[1+i*1e-3,0.25*m+i*1e-4,1e-3*(m+1)]);return {node_coordinates:X0,triangles:T,real:Array.from({length:k},(_,m)=>mode(m)),imag:Array.from({length:k},(_,m)=>T.map(()=>[0,1e-9*m,0]))};};
 const job=i=>i.toString(16).padStart(8,'0');
 const result=i=>{const k=1+i%4,t=8+(i*37)%32;
  return N.validateRun({job:job(i),completedAt:new Date(Date.UTC(2026,10,25,0,0,i%60,i)).toISOString(),settings:N.opticalSettings(1550,30,k),input,
   effective_index:Array.from({length:k},(_,m)=>2.9-0.17*m),field:field(k,t),origin:'local',serverVersion:'0.0.0',
   te_polarization_fraction:Array.from({length:k},(_,m)=>0.9-0.1*m),effective_area:Array.from({length:k},(_,m)=>2e-13*(m+1))});};
 // the page's arrival (applyFieldBudget): this Studio's chooseFieldsAtArrival, or chooseFields before it
 const choose=X.chooseFieldsAtArrival??X.chooseFields;
 const t={runs:[],used:0,selected:null,comparison:[null,null],dropSwap:null};
 const text=()=>N.sessionText(input,t.runs,t.selected,t.comparison,VIEW);
 const arrive=(first=[])=>{X.forgetHeldFields(t.runs);const out=choose(input,t.runs,t.selected,t.comparison,VIEW,{first});for(const r of out.letGo)X.letGoField(r);return out;};
 const op={
  result:i=>{const completed=result(i),prior=t.runs.find(r=>r.job===completed.job);if(prior)completed.number=prior.number;
   const used=W.numberRuns([completed],t.used);let appended;try{appended=N.appendRun(t.runs,completed,N.RUN_LIMIT);}catch{return 'all pinned';}
   t.used=used;const next=prior?W.inNumberOrder(appended):appended,dropped=t.runs.filter(r=>!next.includes(r)&&r.job!==completed.job);
   t.runs=next;t.selected=completed.job;t.comparison=[t.comparison[1]&&t.runs.some(r=>r.job===t.comparison[1])?t.comparison[1]:completed.job,completed.job];
   const other=dropped.length===1?W.swapCandidate(t.runs,completed):null;t.dropSwap=other?{kept:dropped[0],other,list:t.runs}:null;arrive();return 'result';},
  swapBack:()=>{const o=t.dropSwap;if(!o||t.runs!==o.list||!t.runs.includes(o.other))return 'no swap';t.runs=W.swapDropped(t.runs,o.kept,o.other);t.dropSwap=null;arrive([o.kept.job]);return 'swap';},
  pin:(k,on)=>{const r=t.runs[k%Math.max(1,t.runs.length)];if(!r)return 'no run';r.pinned=on;t.dropSwap=null;return 'pin';},
  select:k=>{const r=t.runs[k%Math.max(1,t.runs.length)];if(!r)return 'no run';t.selected=r.job;return 'select';},
  rename:(k,label)=>{const r=t.runs[k%Math.max(1,t.runs.length)];if(!r)return 'no run';r.label=label;return 'rename';},
  compare:(a,b)=>{if(!t.runs.length)return 'no run';t.comparison=[t.runs[a%t.runs.length].job,t.runs[b%t.runs.length].job];return 'compare';},
  load:session=>{for(const r of session.runs){const n=r.number;delete r.number;r.number=n;}t.runs=session.runs;t.used=W.numberRuns(t.runs);t.selected=session.selected;t.comparison=[...session.comparison];t.dropSwap=null;arrive();},
  open:()=>{if(!t.runs.length)return 'no run';op.load(N.parseSession(text()));return 'open';},
  restore:()=>{if(!t.runs.length)return 'no run';op.load(R.readNotebookRecovery({version:1,savedAt:'2026-11-25T10:00:00.000Z',session:N.captureSession(input,t.runs,t.selected,t.comparison,VIEW)()}).session);return 'restore';},
  import:(ids,numbers)=>{const other=ids.map((i,k)=>Object.assign(result(i),{number:numbers[k]}));let s;
   try{s=N.parseSession(N.sessionText(input,other,null,[null,null],VIEW));}catch{return 'not written';}
   let merged;try{merged=N.mergeRuns(t.runs,s.runs,N.RUN_LIMIT);}catch{return 'refused';}
   const next=merged.runs;t.used=W.numberRuns(next,Math.max(t.used,...t.runs.map(r=>r.number||0)));t.runs=next;t.dropSwap=null;
   t.selected=next.findLast(r=>merged.added.includes(r.job)||merged.reused.includes(r.job))?.job??t.selected;
   if(!t.runs.some(r=>r.job===t.comparison[0]))t.comparison=[t.selected,t.selected];if(!t.runs.some(r=>r.job===t.comparison[1]))t.comparison=[t.comparison[0],t.selected];
   arrive();return 'import';},
 };
 const rand=random(seed),chain=createHash('sha256'),checkpoints=[],versions=new Set(),seen={};let pool=0,compact=false;
 for(let step=0;step<steps;step++){
  const x=rand(),pick=()=>Math.floor(rand()*20);let what;
  if(x<0.4)what=op.result(rand()<0.1&&t.runs.length?parseInt(t.runs[Math.floor(rand()*t.runs.length)].job,16):++pool);
  else if(x<0.48)what=op.pin(pick(),true);
  else if(x<0.56)what=op.pin(pick(),false);
  else if(x<0.62)what=op.swapBack();
  else if(x<0.67)what=op.select(pick());
  else if(x<0.70)what=op.rename(pick(),rand()<0.5?'':'Design '+step);
  else if(x<0.73)what=op.compare(pick(),pick());
  else if(x<0.82){const n=1+Math.floor(rand()*4),ids=Array.from({length:n},()=>rand()<0.3&&t.runs.length?parseInt(t.runs[Math.floor(rand()*t.runs.length)].job,16):++pool);
   const unique=[...new Set(ids)],start=1+Math.floor(rand()*30);what=op.import(unique,unique.map((_,k)=>start+k*(1+Math.floor(rand()*3))));}
  else if(x<0.88)what='save';
  else if(x<0.94)what=op.open();
  else what=op.restore();
  seen[what]=(seen[what]||0)+1;
  if(t.runs.length){
   const save=N.writeOpticalSession(input,t.runs,t.selected,t.comparison,VIEW).text,recovery=N.captureSession(input,t.runs,t.selected,t.comparison,VIEW)();
   chain.update(save+'\u0000'+recovery+'\u0000');versions.add(JSON.parse(save).version);if(/"encoding"/.test(save)||/"encoding"/.test(recovery))compact=true;
  }
  if((step+1)%100===0)checkpoints.push(chain.copy().digest('hex'));
 }
 return {steps,seed,chain:chain.digest('hex'),checkpoints,versions:[...versions].sort((a,b)=>a-b),compact,seen};
}
if(process.argv[2])process.stdout.write(JSON.stringify(await fitSequence(process.argv[2]),null,1)+'\n');
