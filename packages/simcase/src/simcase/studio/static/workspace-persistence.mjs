// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
import {designSummary} from './workspace-shapes.mjs';

// A session file name from the application and the local date-time, e.g.
// optical-waveguide-session-2026-11-21-1305.json (.json, so Open accepts it).
export function sessionFileName(application,date=new Date()){
 if(!/^[a-z][a-z-]{0,39}$/.test(application))throw new Error('Invalid application name.');
 const p=n=>String(n).padStart(2,'0');
 return `${application}-session-${date.getFullYear()}-${p(date.getMonth()+1)}-${p(date.getDate())}-${p(date.getHours())}${p(date.getMinutes())}.json`;
}
// The last session file this notebook was saved to, as browser recovery keeps it:
// {name, savedAt, current}; current means the notebook still matched that file.
export function validateSavedFile(value){
 if(value==null)return null;
 if(typeof value!=='object'||typeof value.name!=='string'||!/^[A-Za-z0-9._ ()-]{1,200}\.json$/.test(value.name)||typeof value.savedAt!=='string'||!Number.isFinite(Date.parse(value.savedAt))||typeof value.current!=='boolean')return null;
 return {name:value.name,savedAt:value.savedAt,current:value.current};
}
// The one save indicator: the title bar shows it and the footer repeats it, so the two never
// disagree. file: the name of the model's current file (File › Save downloads or writes it
// again), or null; with one the indicator names it and its state, and "Unsaved inputs" is said only
// when there is no name. saved: {name, savedAt, current, written} (the last session file this notebook was sent
// to; written when the browser's save dialog wrote it, File › Save As, rather than a download)
// or null; loaded: {kind: 'opened' | 'recovered', name, current} (the session file opened, or
// browser recovery) or null; current means nothing changed since. recovery: the browser copy
// of the completed runs, 'kept' | 'updating' | 'unavailable' | 'conflict', or null before any.
// A download is handed to the browser, which Studio cannot see keep it, so the indicator then
// names the file the session was sent to and never claims it was saved; "Saved to" only after
// the save dialog's write finished. No revision
// counter: it counts input changes in this tab only and would differ after a restore.
// overLimit and kept:N are a multiphysics session's (version 8): over 16 MiB, recovery keeps the
// maps of the selected and pinned runs only, and writes nothing when even that is over the limit.
const RECOVERY=Object.freeze({kept:'kept for recovery in this browser',updating:'updating browser recovery',unavailable:'browser recovery unavailable',conflict:'browser recovery changed in another tab',overLimit:'browser recovery unavailable: session over 16 MiB'});
const recoveryWords=recovery=>{const m=/^kept:(\d+)$/.exec(recovery||'');return m?`${RECOVERY.kept} without the maps of ${plural(+m[1],'run')} · File › Save keeps them`:RECOVERY[recovery];};
// A file Studio handed to the browser: it went to the browser's Downloads; whether it reached
// the disk is the browser's to say, so no title claims it was saved.
export const sentToDownloads=(kind,name)=>`${kind} file ${name} sent to your browser's Downloads`;
// viewed: {run, name} when the run Results or Compare shows has other inputs than the current ones
// and no input was edited: the title says so in a few words, so it agrees with the step bar and the
// dock ("current inputs differ from this run") without reading as unsaved edits. The caller passes
// it on Results and Compare only: on the Model tab the title describes the current inputs alone.
export function persistenceTitle(state,when){
 const base=titleOf(state,when),v=state.viewed;
 return v&&!state.invalid?`${base} · viewing Run ${v.run}${v.name?' · '+v.name:''} (other inputs)`:base;
}
// loaded.file: the session file a notebook was opened from (or that its recovery record names as
// opened), and loaded.fileCurrent whether the inputs and runs were still that file's. "Current"
// counts the model inputs and the runs only: a selected run, a page or a field view is not a change.
function titleOf({invalid=false,clean=true,fresh=false,runsUnsaved=false,saved=null,loaded=null,recovery=null,file:current=null},when=t=>new Date(t).toLocaleTimeString([],{hour:'2-digit',minute:'2-digit'})){
 if(invalid)return 'Invalid input draft · last valid inputs '+(clean?'unchanged':'unsaved');
 // A browser copy that fails or changed in another tab is said in every state with runs.
 const problem=runsUnsaved||saved||loaded?.current?(['unavailable','conflict','overLimit'].includes(recovery)?' · '+RECOVERY[recovery]:''):'';
 if(loaded?.current&&loaded.kind==='opened')return `Opened ${loaded.name}`+problem;
 if(loaded?.current&&loaded.kind==='recovered'){
  // a record whose file link still matched says so: the same as the file, not "not saved to a file"
  const same=saved?.current?saved.name:!saved&&loaded.file&&loaded.fileCurrent?loaded.file:null;
  if(same)return `Recovered from this browser · same as file ${same}`+problem;
  // the last session file is history: the session came from browser recovery, not from that file
  return 'Recovered from this browser'+(saved?` (last sent to a file: ${saved.name} at ${when(saved.savedAt)}; changed since)`:loaded.file?` (opened from ${loaded.file}; changed since)`:runsUnsaved?' · not saved to a file':'')+problem;
 }
 // the current file's name first, then its state: "x.json · saved 03:42", with " (download)" when
 // the browser was handed a download (written: the browser's save dialog wrote it, File › Save As)
 if(saved?.current)return `${saved.name} · saved ${when(saved.savedAt)}${saved.written?'':' (download)'}`+problem;
 const browser=recoveryWords(recovery)||'not in browser recovery yet';
 // current: the model's current file (saved to, or opened), whose name File › Save uses again
 if(current){const since=saved?.name===current?'saved':'opened';
  return `${current} · changed since ${since}`+(runsUnsaved?' · '+browser:problem);}
 const file=saved?`${saved.name} (${when(saved.savedAt)})`:loaded?.file||null;
 if(runsUnsaved)return (file?`Changed since session file ${file}`:'Not saved to a file')+' · '+browser;
 // fresh: a model just chosen and not yet edited, saved or opened.
 if(fresh)return 'New model · not saved';
 return clean?'No unsaved input changes':'Unsaved inputs';
}
const PHYSICS=[['electric','Electric'],['heat','Heat'],['structure','Mechanics'],['optics','Optical']];
// The physics a model holds; chosen=false is the start state, before any model is chosen.
export function physicsList(model,chosen=true){
 if(!chosen)return 'No model chosen';
 return PHYSICS.filter(([key])=>model[key]).map(([,name])=>name).join(' + ')||'None';
}
// Whether a workspace holds nothing an open would lose: default inputs (whatever
// physics was chosen) and no results.
export function untouchedWorkspace(input,defaults,{results=0}={}){
 if(results>0)return false;
 const strip=doc=>{const {electric,heat,structure,optics,...model}=doc.model;return JSON.stringify({model,setup:doc.setup});};
 return strip(input)===strip(defaults);
}
const plural=(n,word)=>`${n} ${word}${n===1?'':'s'}`;
export function runName(run){return (run.label||designSummary(run.input.model))+(run.pinned?' (pinned)':'');}
// The confirmation for opening or recovering a session over a workspace with something in it.
// session: the parsed session; current: {runs, unsaved}; source: 'file' or 'browser'.
export function sessionLoadText(session,{runs:currentRuns=0,unsaved=false}={},source='file'){
 const back=session.runs,byJob=job=>back.find(r=>r.job===job);
 const [a,b]=session.comparison.map(byJob);
 const comparison=a&&b&&a.job!==b.job?`A ${runName(a)} · B ${runName(b)}`:'None';
 const returns=back.length?`${plural(back.length,'run')} with ${back.length===1?'its name and pin':'their names and pins'}${comparison==='None'?'':' and the comparison'}`:'No completed runs';
 const replaced='the current inputs'+(currentRuns?` and ${plural(currentRuns,'run')} in this tab`:'');
 return {
  title:source==='file'?'Open saved session?':'Recover saved session?',
  description:`Brings back ${returns.charAt(0).toLowerCase()+returns.slice(1)}. Replaces ${replaced}; input undo starts at the opened session.`+(currentRuns&&unsaved?' Save session first to keep the current runs.':''),
  button:source==='file'?'Open session':'Recover session',
  runs:back.length?back.map(runName).join('; '):'None',
  comparison
 };
}

// The confirmation before leaving a model whose runs only this tab holds, or null when nothing
// is at stake. from 'multiphysics': runs is the number of its runs no session file holds (they are
// in browser recovery too, but leaving discards them from the tab). from 'optical': runs not in a
// session file (they stay in this tab, hidden while target is open, but no file holds them).
// Both offer Save session.
export function leaveConfirmText({from,runs=0,saved=false,target='the other model'}){
 if(from==='multiphysics'&&runs>0)return {title:'Leave this model?',
  description:`${plural(runs,'run')} ${runs===1?'is':'are'} only in this tab and in browser recovery. Save session first to keep ${runs===1?'it':'them'} in a file.`,
  save:{kind:'session',label:'Save session'},leave:'Leave',stay:'Cancel'};
 if(from==='optical'&&runs>0&&!saved){const one=runs===1;return {title:`Open ${target}?`,
  description:`${plural(runs,'optical run')} ${one?'is':'are'} in no file. ${one?'It stays':'They stay'} in this tab while ${target} is open and ${one?'comes':'come'} back with the optical model, but closing the tab can lose ${one?'it':'them'}. Save session keeps ${one?'it':'them'} in a file.`,
  save:{kind:'session',label:'Save session, then continue'},leave:'Continue without saving',stay:'Keep this model'};}
 return null;
}
// The Messages line when another model opens over optical runs: where those runs are, in words
// that stay true. text: one short line; more: the rest, shown behind More. This tab holds them
// until it is closed or reloaded; file: the session file that holds them as they are, recovery:
// browser recovery holds them. After a reload only those hold them, so more says how to get them
// back from each. {text: '', more: ''} when there are no optical runs.
export function opticalRunsStayText({runs=0,file=null,recovery=false}){
 if(!runs)return {text:'',more:''};
 const one=runs===1,them=one?'it':'them';
 const text=`Optical waveguide ${one?'run stays':'runs stay'} in this tab · Library › Optical waveguide returns to ${them}`;
 const back=[...(recovery?['Library › Optical waveguide › Restore from this browser (browser recovery, which keeps the four newest sessions)']:[]),...(file?[`Open session with ${file}`]:[])];
 const more=`This tab holds ${plural(runs,'run')} until it is closed or reloaded.`+(back.length?` After that, ${back.join(' or ')} brings ${them} back.`:` After that, no file or browser recovery holds ${them}.`);
 return {text,more};
}
