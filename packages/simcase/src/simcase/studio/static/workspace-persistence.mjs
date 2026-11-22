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
// disagree. saved: {name, savedAt, current} (the last session file this notebook was sent to)
// or null; loaded: {kind: 'opened' | 'recovered', name, current} (the session file opened, or
// browser recovery) or null; current means nothing changed since. recovery: the browser copy
// of the completed runs, 'kept' | 'updating' | 'unavailable' | 'conflict', or null before any.
// Studio hands the file to the browser's downloads and cannot know it was kept, so the
// indicator names the file the session was sent to and never claims it was saved. No revision
// counter: it counts input changes in this tab only and would differ after a restore.
const RECOVERY=Object.freeze({kept:'kept for recovery in this browser',updating:'updating browser recovery',unavailable:'browser recovery unavailable',conflict:'browser recovery changed in another tab'});
export function persistenceTitle({invalid=false,clean=true,runsUnsaved=false,saved=null,loaded=null,recovery=null},when=t=>new Date(t).toLocaleTimeString([],{hour:'2-digit',minute:'2-digit'})){
 if(invalid)return 'Invalid input draft · last valid inputs '+(clean?'unchanged':'unsaved');
 // A browser copy that fails or changed in another tab is said in every state with runs.
 const problem=runsUnsaved||saved||loaded?.current?(recovery==='unavailable'||recovery==='conflict'?' · '+RECOVERY[recovery]:''):'';
 if(loaded?.current&&loaded.kind==='opened')return `Opened ${loaded.name}`+problem;
 if(loaded?.current&&loaded.kind==='recovered')return 'Recovered from this browser'+(saved?` · ${saved.current?'last session file':'changed since session file'} ${saved.name} (${when(saved.savedAt)})`:runsUnsaved?' · not saved to a file':'')+problem;
 if(saved?.current)return `Sent to session file ${saved.name} · ${when(saved.savedAt)}`+problem;
 const browser=RECOVERY[recovery]||'not in browser recovery yet';
 if(runsUnsaved)return (saved?`Changed since session file ${saved.name} (${when(saved.savedAt)})`:'Not saved to a file')+' · '+browser;
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
