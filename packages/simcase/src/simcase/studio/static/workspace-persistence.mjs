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
// {name, savedAt, current, projectName?}; current means the notebook still matched that file;
// projectName, that the file is a project file (File › Save) of that project name.
export function validateSavedFile(value){
 if(value==null)return null;
 if(typeof value!=='object'||typeof value.name!=='string'||!/^[A-Za-z0-9._ ()-]{1,200}\.json$/.test(value.name)||typeof value.savedAt!=='string'||!Number.isFinite(Date.parse(value.savedAt))||typeof value.current!=='boolean')return null;
 // projectName (optional, round 16): the file is a project file of that name; a malformed one is ignored
 const project=typeof value.projectName==='string'&&/^[^\u0000-\u001f\u007f]{1,80}$/u.test(value.projectName)&&value.projectName.trim()===value.projectName?{projectName:value.projectName}:{};
 return {name:value.name,savedAt:value.savedAt,current:value.current,...project};
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
// round 17 (U6): a recovery that cannot be kept says why and what to do: over 16 MiB (the session, or
// in the optical model its selected and pinned runs with their fields) or the browser's storage full
const RECOVERY=Object.freeze({kept:'kept for recovery in this browser',updating:'updating browser recovery',unavailable:'browser recovery unavailable',conflict:'browser recovery changed in another tab',overLimit:'browser recovery unavailable: session over 16 MiB · File › Save keeps your work',quota:'browser recovery unavailable: this browser’s storage is full · File › Save keeps your work'});
const PROBLEMS=['unavailable','conflict','overLimit','quota'];
// Round 18 (X4): the Messages line when browser recovery turns off, beside the header's words; null
// for a state that is not one of the two.
export const RECOVERY_OFF=Object.freeze({overLimit:'Browser recovery is off: this session is over 16 MiB. File › Save keeps your work.',quota:'Browser recovery is off: this browser’s storage is full. File › Save keeps your work.'});
export const recoveryOffText=state=>RECOVERY_OFF[state]||null;
// Round 23 (E2): keptFields:3,5 is an optical session's: over 16 MiB, recovery keeps the fields of the
// selected and pinned runs and as many others as fit, newest first, so the fields of the runs named
// are not in it: "kept for recovery in this browser without the fields of Run 3 and Run 5" (no "File
// › Save keeps them": over the limit Save asks which fields to keep).
const runList=numbers=>{const w=numbers.map(n=>'Run '+n);return w.length<3?w.join(' and '):w.slice(0,-1).join(', ')+' and '+w.at(-1);};
const recoveryWords=recovery=>{const m=/^kept:(\d+)$/.exec(recovery||''),f=/^keptFields:(\d+(?:,\d+)*)$/.exec(recovery||'');return m?`${RECOVERY.kept} without the maps of ${plural(+m[1],'run')} · File › Save keeps them`:f?`${RECOVERY.kept} without the fields of ${runList(f[1].split(','))}`:RECOVERY[recovery];};
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
// The title text (tooltip) of the indicator on the download path: the browser, not Studio, names
// a downloaded file, and may have added " (1)" (round 14). '' elsewhere.
export const DOWNLOAD_NAME_HINT='Your browser may have added “ (1)” to the file name.';
export function persistenceHint(state){
 return /· downloaded |· changed since downloaded/.test(titleOf(state,()=>''))?DOWNLOAD_NAME_HINT:'';
}
// The word after "changed since" for the current file, by how it became current: the save dialog
// wrote it (saved), a download (downloaded), File › Open (opened) or a browser restore (restored).
const SINCE=Object.freeze({picker:'saved',download:'downloaded',opened:'opened',recovered:'restored'});
function titleOf({invalid=false,clean=true,fresh=false,runsUnsaved=false,saved=null,loaded=null,recovery=null,file:current=null,fileHow=null},when=t=>new Date(t).toLocaleTimeString([],{hour:'2-digit',minute:'2-digit'})){
 if(invalid)return 'Invalid input draft · last valid inputs '+(clean?'unchanged':'unsaved');
 // A browser copy that fails or changed in another tab is said in every state with runs.
 const problem=runsUnsaved||saved||loaded?.current?(PROBLEMS.includes(recovery)?' · '+RECOVERY[recovery]:''):'';
 if(loaded?.current&&loaded.kind==='opened')return `Opened ${loaded.name}`+problem;
 if(loaded?.current&&loaded.kind==='recovered'){
  // a record whose file link still matched says so: the same as the file, not "not saved to a file"
  const same=saved?.current?saved.name:!saved&&loaded.file&&loaded.fileCurrent?loaded.file:null;
  if(same)return `Recovered from this browser · same as file ${same}`+problem;
  // the last session file is history: the session came from browser recovery, not from that file
  return 'Recovered from this browser'+(saved?` (last sent to a file: ${saved.name} at ${when(saved.savedAt)}; changed since)`:loaded.file?` (opened from ${loaded.file}; changed since)`:runsUnsaved?' · not saved to a file':'')+problem;
 }
 // the current file's name first, then its state: "x.json · saved 03:42" when the browser's save
 // dialog wrote it (written), "x.json · downloaded 03:42" when the browser was handed a download,
 // which Studio cannot see it keep under that name (round 14)
 if(saved?.current)return `${saved.name} · ${saved.written?'saved':'downloaded'} ${when(saved.savedAt)}`+problem;
 const browser=recoveryWords(recovery)||'not in browser recovery yet';
 // current: the model's current file (saved to, or opened), whose name File › Save uses again
 if(current){const since=SINCE[fileHow]||(saved?.name===current?(saved.written?'saved':'downloaded'):'opened');
  return `${current} · changed since ${since}`+(runsUnsaved?' · '+browser:problem);}
 const file=saved?`${saved.name} (${when(saved.savedAt)})`:loaded?.file||null;
 if(runsUnsaved)return (file?`Changed since session file ${file}`:'Not saved to a file')+' · '+browser;
 // fresh: a model just chosen and not yet edited, saved or opened.
 if(fresh)return 'New model · not saved';
 return clean?'No unsaved input changes':'Unsaved inputs';
}
// The title bar's project line (P3): the project's name, then its project file and that file's
// state in the round-14 words. "Changed" counts the inputs, study settings, runs, names, pins and
// comparisons of every model and the project name; the view and the selected run do not (the
// caller compares). state: {name (null: untitled), models (how many), file: {name, how, savedAt}
// or null, current, recovery}. how: 'picker' (saved), 'download' (downloaded) or 'opened'.
//   "Heater study · heater-study.json · saved 13:15"
//   "Heater study · heater-study.json · changed since downloaded 13:15 · kept for recovery in this browser"
//   "Untitled project · not saved to a file · kept for recovery in this browser"
export const UNTITLED_PROJECT='Untitled project';
// recovered (round 16): a browser restore of a record that matched its project file, saved at that time
const PROJECT_WORD=Object.freeze({picker:'saved',download:'downloaded',opened:'opened',recovered:'saved'});
// Round 19 (Y3): copyOf, the file a browser-restored record was opened from when the record names
// no project file or name: "Untitled project · recovered from a copy of both-models.json · not
// saved to a file · kept for recovery in this browser" (the name is not guessed from the file).
// recovered: the project name came back from a browser-recovery record (no project file), {opened:
// the file the record still matched, or null; changed: the file the record was opened from and no
// longer matched (openedCurrent false), or null}, until the next change: "both-models · recovered
// from this browser · not saved to a file · kept for recovery in this browser", or "… · as opened
// from both-models.json · …". Round 23 (E5, HQ decision 2026-11-24-openphysics-studio-round23-choices,
// changing the v12 design's K7 words): a record that no longer matched its file reads "both-models ·
// recovered from this browser · changed since both-models.json, not saved · kept for recovery in
// this browser" (it read "not saved to a file", as if no file had ever held the project).
// Round 24 (B2, coordinator decision on the round-24 findings): fromFile, the file a recovered record
// was opened from (matched or not), kept after the next change: while the project has a name and no
// project file, every later header reads "both-models · changed since both-models.json, not saved ·
// updating browser recovery" (it read "not saved to a file" beside the status bar's "Changed since
// session file both-models.json"). A project no file held keeps "not saved to a file".
export function projectTitle({name=null,models=0,file=null,current=false,recovery=null,copyOf=null,recovered=null,fromFile=null},when=t=>new Date(t).toLocaleTimeString([],{hour:'2-digit',minute:'2-digit'})){
 const title=name||UNTITLED_PROJECT;
 if(!models)return `${title} · no model chosen`;
 const browser=recoveryWords(recovery)||'not in browser recovery yet';
 if(!file&&name&&recovered)return `${title} · recovered from this browser · ${recovered.opened?`as opened from ${recovered.opened}`:recovered.changed?`changed since ${recovered.changed}, not saved`:'not saved to a file'} · ${browser}`;
 if(!file&&name&&fromFile)return `${title} · changed since ${fromFile}, not saved · ${browser}`;
 if(!file)return `${title} · ${copyOf?`recovered from a copy of ${copyOf} · `:''}not saved to a file · ${browser}`;
 const word=PROJECT_WORD[file.how]||'opened',at=file.how!=='opened'&&file.savedAt?' '+when(file.savedAt):'';
 if(current)return `${title} · ${file.name} · ${word}${at}`+(PROBLEMS.includes(recovery)?' · '+RECOVERY[recovery]:'');
 return `${title} · ${file.name} · changed since ${word}${at} · ${browser}`;
}
/** The project name a browser restore brings back from its record's `project` ({name, from}), when
 * no savedFile.projectName names one and the project has no file: {name, nameFrom, recovered:
 * {opened, changed, savedAt}} (opened: the file the record was opened from while it still matched it;
 * changed: that file when the record no longer matched it), or
 * null when nothing changes. The second restore of a pair keeps the name of the newer record.
 * state: the project now ({name, nameFrom, file, recovered}). */
export function recoveredProjectName(state,record,{savedFile=null,openedFile=null,openedCurrent=null,savedAt=null}={}){
 if(!record||savedFile?.projectName||state.file)return null;
 const at=t=>Date.parse(t)||0,earlier=state.recovered&&state.name&&at(state.recovered.savedAt)>at(savedAt);
 if(earlier)return {name:state.name,nameFrom:state.nameFrom,recovered:{...state.recovered}};
 return {name:record.name,nameFrom:record.from,recovered:{opened:openedFile&&openedCurrent===true?openedFile:null,changed:openedFile&&openedCurrent===false?openedFile:null,savedAt}};
}
// Round 18 (X8): the heated model's status bar while the project has a project file speaks about
// the model within that project, in the header's words, so the two never contradict each other:
//   "Heated silicon waveguide · in project waveguide-AB.json · not saved since it joined" (the
//   model is not in the file's model list), "… · in project heater-study.json · saved 13:15", or
//   "… · in project heater-study.json · changed since saved 13:15 · kept for recovery in this
//   browser". inFile: the file's model list holds this model (null when the file does not say);
//   current: the project equals the file; recovery: browser recovery's state, said as the header
//   says it (only a problem when current).
export function modelInProjectTitle({title,file,inFile=null,current=false,recovery=null},when=t=>new Date(t).toLocaleTimeString([],{hour:'2-digit',minute:'2-digit'})){
 const head=`${title} · in project ${file.name}`,browser=recoveryWords(recovery)||'not in browser recovery yet';
 if(inFile===false)return `${head} · not saved since it joined · ${browser}`;
 const word=PROJECT_WORD[file.how]||'opened',at=file.how!=='opened'&&file.savedAt?' '+when(file.savedAt):'';
 return current?`${head} · ${word}${at}`+(PROBLEMS.includes(recovery)?' · '+RECOVERY[recovery]:''):`${head} · changed since ${word}${at} · ${browser}`;
}
/** The project line's title text: the "(1)" note on the download path, '' elsewhere. */
export const projectHint=file=>file?.how==='download'?DOWNLOAD_NAME_HINT:'';
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
// The confirmation before a file replaces the project (File › Open of a project, session or model
// file) while some of its models have runs in no file, or null when nothing is at stake. Switching
// models inside a project asks nothing: every model stays in the tab. name: the project's name
// (null: untitled); models: [{title, runs}] the models with runs no file holds.
export function projectLeaveText({name=null,models=[]}){
 const atStake=models.filter(m=>m.runs>0);if(!atStake.length)return null;const one=atStake.length===1&&atStake[0].runs===1;
 const list=atStake.map(m=>`${m.title} (${plural(m.runs,'run')})`),words=list.length<2?list[0]:list.slice(0,-1).join(', ')+' and '+list.at(-1);
 return {title:`Replace ${name||UNTITLED_PROJECT}?`,
  description:`${words} ${atStake.length===1?'has':'have'} ${one?'a run':'runs'} in no file. Save project first to keep ${one?'it':'them'}.`,
  save:{kind:'project',label:'Save project, then open'},leave:'Open without saving',stay:'Cancel'};
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
