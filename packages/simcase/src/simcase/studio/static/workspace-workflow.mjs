// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
import {designSummary,shapesBlock,geometryWords} from './workspace-shapes.mjs';
import {inputChanges} from './workspace-inputs.mjs';
import {originText} from './workspace-multiphysics.mjs';
import {studySignature,RUN_LIMIT as OPTICAL_RUN_LIMIT} from './workspace-notebook.mjs';
import {shortTarget,closedPlanText} from './workspace-closed-target.mjs';
import {boundaryTag,studyTag} from './workspace-compare.mjs';

// The words for a result whose inputs are not the current ones (optical, heat, Joule heating):
// neutral, since an opened file or another selected run differs without any edit, and naming
// both sides of each part that differs. runParts and currentParts: the same parts, in order,
// as text (for example the geometry, the wavelength and the core mesh).
export const SAME_INPUTS='Result for the current inputs';
export function inputsDifferText(runParts,currentParts){
 const differ=runParts.map((part,i)=>part!==currentParts[i]?i:-1).filter(i=>i>=0);
 if(!differ.length)return 'Current inputs differ from this run in other settings';
 return `Current inputs differ from this run: this run ${differ.map(i=>runParts[i]).join(' · ')}, current ${differ.map(i=>currentParts[i]).join(' · ')}`;
}
// The line under a result's heading: whether the current inputs are the run's, then the run's
// inputs, each part named once: a part that differs is named with both values, the others after
// "unchanged" ("…, current 700 × 300 nm · Silicon; unchanged: λ 1550 nm · core mesh 30 nm").
export function runInputsLine(runParts,currentParts){
 const same=runParts.filter((part,i)=>part===currentParts[i]);
 if(same.length===runParts.length)return [SAME_INPUTS,...runParts].join(' · ');
 return inputsDifferText(runParts,currentParts)+(same.length?'; unchanged: '+same.join(' · '):'');
}
// The parts of an optical input the words above compare.
export const opticalInputParts=input=>[designSummary(input.model),`λ ${input.model.wavelength} nm`,`core mesh ${input.model.coreMesh} nm`];
// Round 23 (E6): every part of a study that enters studySignature (workspace-notebook.mjs), so the line
// under a result names each input that differs. study: {input, modeCount, groupIndex, pml (the
// settings.pml form {open_edges, target, thickness?}, or null), searchTarget (a closed window's
// Search near n_eff, or null)}. Returns [runParts, currentParts]: the geometry, λ and the core mesh
// always; then, when either side has other than the default, the shape positions (when the shapes
// differ in position only), the boundary with its PML thickness and open edges and its search
// ("closed window · highest n_eff", "closed window · nearest to n_eff 2.46", "open boundary (PML
// 1 µm) on left, right and bottom · search near 2.46"), Modes to find and the group index. Both
// sides always have the same parts, in the same order.
const DEFAULT_STUDY_MODES=2;
const edgeWords=list=>list.length<3?list.join(' and '):list.slice(0,-1).join(', ')+' and '+list.at(-1);
const pmlMicrons=pml=>{const t=typeof pml.thickness==='string'?Number.parseFloat(pml.thickness)/1000:1;return Number.isFinite(t)?t:1;};
export const boundaryWords=(pml,searchTarget=null)=>pml?`open boundary (PML ${pmlMicrons(pml)} µm) on ${edgeWords(pml.open_edges)}`:'closed window';
export const searchWords=(pml,searchTarget=null)=>pml?`search near ${shortTarget(pml.target)}`:searchTarget!=null?`nearest to n_eff ${shortTarget(searchTarget)}`:'highest n_eff';
const where=s=>s.type==='polygon'?s.points.map(p=>`(${p[0]}, ${p[1]})`).join(', '):`(${s.x}, ${s.y})`;
export const positionWords=model=>'at '+model.shapes.map(s=>`${s.name} ${where(s)}`).join(', ')+' nm';
export function studyInputParts(run,now){
 const sides=[run,now],parts=s=>opticalInputParts(s.input);
 const out=sides.map(parts);
 const add=(test,words)=>{if(test)sides.forEach((s,i)=>out[i].push(words(s)));};
 add(out[0][0]===out[1][0]&&positionWords(run.input.model)!==positionWords(now.input.model),s=>positionWords(s.input.model));
 add(sides.some(s=>s.pml||s.searchTarget!=null),s=>boundaryWords(s.pml,s.searchTarget));
 add(sides.some(s=>s.pml||s.searchTarget!=null),s=>searchWords(s.pml,s.searchTarget));
 add(sides.some(s=>s.modeCount!==DEFAULT_STUDY_MODES),s=>`Modes to find ${s.modeCount}`);
 add(sides.some(s=>s.groupIndex===true),s=>s.groupIndex===true?'group index on':'group index off');
 return out;
}
// What the next run computes, in the Study panel: the current inputs, whatever run Results shows.
// "Next run uses 700 × 300 nm · Silicon · λ 1550 nm · core mesh 30 nm · Modes to find 2", with
// " · group index on" when the group index option is on.
// pml: the open boundary of the page (settings.pml form, workspace-open-run.mjs), or null.
// searchTarget: the closed window's Search near n_eff (slice C2), or null: " · search near 2.46".
export const nextRunText=(input,modeCount,groupIndex=false,pml=null,searchTarget=null)=>`Next run uses ${[...opticalInputParts(input),...(Number.isInteger(modeCount)?[`Modes to find ${modeCount}`]:[]),...(groupIndex===true?['group index on']:[]),...(pml?[`open boundary (PML 1 µm) on ${pml.open_edges.length} edge${pml.open_edges.length===1?'':'s'}`,`search near ${pml.target}`]:[]),...(!pml&&searchTarget!=null?[`search near ${shortTarget(searchTarget)}`]:[])].join(' · ')}`;
// What the next optical run does, beside Run study (round 18, X2; round 17 U3 named the slow options
// only): the boundary, the searches of an open boundary, the options that add solves with the solve
// count after the last of them, and how long the last comparable run took (the same boundary kind
// and group-index state). Round 20 (Z5): without such a run the timing part is left out ("no timed
// run in this tab yet" of round 19 raised "what is a timed run?" and read wrong beside open runs).
// last: that run's wall time in ms, or null.
//   "Open boundary · 2 modes · 2 searches · group index on (3 solves) · last such run 3:40"
//   "Closed window · 2 modes"
//   "Closed window · near n_eff 2.46 · 2 modes" (slice C2: searchTarget, a closed window's Search near n_eff)
// Round 23 (E3): with group index on, the time part is an estimate instead (estimate: ms, from
// groupIndexEstimate, or null for none; the page then passes no last): "Open boundary · 2 modes · 2
// searches · group index on (3 solves) · about 3 min".
// Round 28 (G2): after the boundary, Modes to find, as the job label names it ("4 modes", "1 mode"),
// so a mode count a shortcut set is seen before the run: "Open boundary · 4 modes · 2 searches · group
// index on (3 solves) · about 5 min", "Closed window · 2 modes", "Closed window · near n_eff 2.46 · 4 modes".
export function runPlanText({open=false,searches=1,groupIndex=false,pmlCheck=false,modeCount=2,last=null,searchTarget=null,estimate=null}={}){
 const options=[...(groupIndex===true?['group index on']:[]),...(open&&pmlCheck===true?['PML check on']:[])];
 const solves=(groupIndex===true?3:1)+(open&&pmlCheck===true&&Number.isInteger(modeCount)?modeCount:0);
 const time=groupIndex===true&&Number.isFinite(estimate)?[`about ${aboutText(estimate)}`]:Number.isFinite(last)?[`last such run ${durationText(last)}`]:[];
 const modes=Number.isInteger(modeCount)?[modeCount===1?'1 mode':`${modeCount} modes`]:[];
 const parts=[open?'Open boundary':searchTarget!=null?closedPlanText(searchTarget):'Closed window',...modes,...(open?[searches===2?'2 searches':'1 search']:[]),...(options.length?[options.join(' · ')+` (${solves} solves)`]:[]),...time];
 return parts.join(' · ');
}
// Round 23 (E3): the time a run with group index on is likely to take, from the newest run of the tab
// with the same boundary kind (open: a run with a PML) and a wall time measured in this tab: its time
// when it computed the group index too, else 3 times its time (the group index adds the solves at
// λ0 − 1 nm and λ0 + 1 nm). null with no such run (round 20, Z5: no estimate without a measured run).
// On 2026-11-24 the T18 open run took 68 s without and 199 s with group index (2.9 ×).
export function groupIndexEstimate(runs,{open},{isOpen,hasGroup}){
 const last=runs.findLast(r=>Number.isFinite(r.duration)&&isOpen(r)===!!open);
 return last?(hasGroup(last)?last.duration:3*last.duration):null;
}
// "about 40 s" under a minute and a half (to 10 s, at least 10 s), else "about 3 min" (to the minute)
export function aboutText(ms){
 const s=ms/1000;return s<90?`${Math.max(10,Math.round(s/10)*10)} s`:`${Math.round(s/60)} min`;
}
// m:ss of a duration in ms ("3:40"), h:mm:ss from an hour
export function durationText(ms){
 const s=Math.max(0,Math.round(ms/1000)),h=Math.floor(s/3600),m=Math.floor(s%3600/60),r=String(s%60).padStart(2,'0');
 return h?`${h}:${String(m).padStart(2,'0')}:${r}`:`${m}:${r}`;
}
// The newest run of the tab that is comparable with the next one (round 18, X2): the same boundary
// kind (open: a run with a PML) and group-index state, with a wall time measured in this tab
// (opened and recovered runs have none). isOpen and hasGroup say that of a run.
export function lastComparableRun(runs,{open,groupIndex},{isOpen,hasGroup}){
 return runs.findLast(r=>Number.isFinite(r.duration)&&isOpen(r)===!!open&&hasGroup(r)===!!groupIndex)||null;
}
// Readiness describes the current editor and retained artifacts, not accuracy.
// viewed: the run Results shows (the selected run); the Results step describes that run, so the
// step bar, the result and its settings agree. Without it, the newest run of these inputs.
// modeCount: Modes to find of the page; a run is of these inputs when it also found that count.
export function opticalWorkflow({input,invalid=false,block='',busy=false,pending=false,resumeBlocked=false,mesh=null,runs=[],viewed,modeCount,groupIndex=false,pml=null,searchTarget=null}){
 const signature=studySignature(input,modeCount,groupIndex,pml,searchTarget),inputs=JSON.stringify(input);
 const materialBlock=input.setup.materials.Oxide!=='Silica'?'Background must be silica':shapesBlock(input.model.shapes),materialOK=!materialBlock;
 const currentRun=runs.findLast(run=>run.signature===signature);
 // A run of these exact inputs is done; an edit makes the study ready to run again.
 const state=invalid?'Correct input draft':busy?'Computing':pending?(resumeBlocked?'Detach unavailable job':'Resume or detach job'):block?'Unavailable':currentRun?'Run complete':'Ready to run';
 // The wavelength leads the Study step, where it is set for the run; the step bar shows it as its
 // own control (wavelength), which opens the wavelength field.
 const wavelength=input.model.wavelength,study=Number.isFinite(wavelength)?`λ ${wavelength} nm · ${state}`:state;
 return [
  {id:'Geometry',state:invalid?'attention':'ready',detail:invalid?'Correct input draft':designSummary(input.model)},
  {id:'Materials',state:materialOK?'ready':'attention',detail:materialOK?[...new Set(input.model.shapes.map(s=>s.material))].join(', ')+' in silica':'Assign supported materials'},
  {id:'Mesh',state:mesh?.signature===inputs?'ready':mesh?'attention':'optional',detail:mesh?.signature===inputs?'Preview current':mesh?'Inputs changed since preview':'Optional preview'},
  {id:'Study',state:invalid?'attention':busy?'busy':pending||block?'attention':'ready',detail:study,summary:state,wavelength:Number.isFinite(wavelength)?`λ ${wavelength} nm`:null},
  // a run with other inputs than the current ones is information, not a problem: tone 'info'
  viewed?{id:'Results',state:viewed.signature===signature?'ready':'attention',detail:viewed.signature===signature?'Result for these inputs':'Current inputs differ from this run',...(viewed.signature===signature?{}:{tone:'info'})}
  :{id:'Results',state:currentRun?'ready':runs.length?'attention':'empty',detail:currentRun?'Result for these inputs':runs.length?'Current inputs differ from this run':'No run yet',...(!currentRun&&runs.length?{tone:'info'}:{})}
 ];
}
// A run as the dock, the footer and the title name it: its number with its name, "Run 1 · design
// A", or "Run 2" when it has none.
export const runTitle=(number,label)=>`Run ${number}${label?' · '+label:''}`;
// Run numbers (round 17, U2): within a tab a run keeps its number; a new run takes the largest
// number used so far + 1, so dropping the oldest unpinned run renumbers nothing. used: the largest
// number used so far in the tab. Returns the largest number used after numbering the runs of `list`
// that have none, in order.
// Since session version 12 (design "Stable run numbers and the project name after recovery") the
// number is kept in session and project files and in browser recovery whenever it is not the run's
// place in the list, and File › Open, Open project and Restore keep it: there is no stored counter,
// the next run takes the largest number + 1, and the run with the largest number is never dropped
// (appendRun keeps the new run, swapDropped and mergeRuns drop only other runs). A file of an
// earlier version numbers its runs by their place in the file; Studio writes an older version only
// when that numbering is exact, so no message speaks about numbering (round 19's RENUMBERED_TEXT is
// gone: HQ decision 2026-11-24-openphysics-studio-session-v12-k10-amended).
/** The import's words when an imported run takes another number in this tab: "Added Run 2 and
 * Run 4 of design-b.json as Run 9 and Run 10."; '' when every added run keeps its number. added:
 * [{from, to}] in list order. */
export function importNumbersText(added,fileName){
 if(!added.length||added.every(a=>a.from===a.to))return '';
 const list=ns=>{const words=ns.map(n=>'Run '+n);return words.length<3?words.join(' and '):words.slice(0,-1).join(', ')+' and '+words.at(-1);};
 return `Added ${list(added.map(a=>a.from))} of ${fileName} as ${list(added.map(a=>a.to))}.`;
}
export function numberRuns(list,used=0){
 let top=Math.max(used,...list.map(r=>Number.isInteger(r.number)?r.number:0));
 for(const run of list)if(!Number.isInteger(run.number))run.number=++top;
 return top;
}
// The runs in the order of their numbers (a stable order; every run numbered). A job that comes
// back (appendRun moves it to the end) keeps its number, so the tab puts it back at its place: a
// session file holds its runs in increasing number order (version 12).
export const inNumberOrder=list=>list.every(r=>Number.isInteger(r.number))?[...list].sort((a,b)=>a.number-b.number):list;
// A run as the drop words name it: "Run 3 · Design A (…)" when named. Round 23 (E4): with the parts the
// run list's label names (runDesign of workspace-compare.mjs): the boundary (with a closed window's
// search target), Modes to find when not 2, n_g, then the geometry, so the drop line, the dropped
// words, the swap button and the Pin notice name the run as the list does:
//   "Run 4 (closed · n_g · 600 × 300 nm)", "Run 2 (open (PML 1 µm) · 600 × 300 nm)",
//   "Run 3 (closed near 2.46 · 4 modes · Core 500 × 220 + Substrate 3000 × 700 nm)".
export const dropParts=run=>`${boundaryTag(run)}${studyTag(run)} · ${geometryWords(run.input.model)}`;
export const dropName=run=>`${runTitle(run.number,run.label||'')} (${dropParts(run)})`;
// The run the next run would drop (round 18, X3): with six runs kept, the oldest unpinned one (the
// one appendRun drops); null below the limit or with every run pinned.
export function nextDropped(runs,limit=6){return runs.length>=limit?runs.find(r=>!r.pinned)||null:null;}
// Round 21 (W2): the unpinned runs the next result drops, oldest first (appendRun's order): as many
// as the result puts over the limit, at most one while the tab holds six or fewer.
export function droppedBy(runs,limit=6){return runs.filter(r=>!r.pinned).slice(0,Math.max(0,runs.length+1-limit));}
// Runs in the drop words: "Run 3 (…)", "Run 1 (…) and Run 3 (…)". name: how the model names a run.
export const dropRunsWords=(list,name=dropName)=>{const words=list.map(name);return words.length<3?words.join(' and '):words.slice(0,-1).join(', ')+' and '+words.at(-1);};
// Its words beside Run study, before the run.
// Round 20 (Z1): the line is about running, not a run in progress: "If you run: drops Run 3 (…) · pin it
// to keep it". A list of runs (round 21): "If you run: drops Run 1 (…) and Run 3 (…) · pin them to keep them".
export const dropWarningText=(run,name=dropName)=>{const list=Array.isArray(run)?run:[run];
 return `If you run: drops ${dropRunsWords(list,name)} · ${list.length>1?'pin them to keep them':'pin it to keep it'}`;};
// Round 21 (W2): Run study starts at once (round 19's question is gone); while the run computes the
// line says what its result drops: "When this run finishes, Run 3 (…) is dropped".
export const dropWhileRunningText=(list,name=dropName)=>`When this run finishes, ${dropRunsWords(list,name)} ${list.length>1?'are':'is'} dropped`;
// After the result: "Run 3 (…) was dropped" (Messages, after the run's own message).
export const droppedAfterText=(list,name=dropName)=>`${dropRunsWords(list,name)} ${list.length>1?'were':'was'} dropped`;
// Round 22 (V4): Pin Run N on the drop line moves the drop to the next unpinned run, so Messages names
// it: "Run 4 pinned. If you run: drops Run 5 (…) · pin it to keep it" (while a run computes, the line's
// "When this run finishes, Run 5 (…) is dropped"). list: droppedBy after the pin (not empty).
export const pinnedDropText=(pinned,list,running=false,name=dropName)=>`Run ${pinned.number} pinned. ${running?dropWhileRunningText(list,name):dropWarningText(list.length>1?list:list[0],name)}`;
// Round 22 (V4): a result dropped a run and every other earlier run is pinned, so no swap can be
// offered: the dropped words say so.
export const droppedNoSwapText=(list,name=dropName)=>`${droppedAfterText(list,name)}; every other earlier run is pinned, so no other run can be dropped instead`;
// The swap Messages offers after a drop (one run dropped, another unpinned run besides the new
// result): "Keep Run 3 (…), drop Run 4 (…) instead", and what it says once done.
export const keepInsteadLabel=(kept,other,name=dropName)=>`Keep ${runTitle(kept.number,kept.label||'')}, drop ${name(other)} instead`;
export const keptInsteadText=(kept,other,name=dropName)=>`${name(kept)} is back; ${name(other)} was dropped instead.`;
// The run the swap drops instead: the oldest unpinned run other than the new result, or null.
export const swapCandidate=(runs,newest)=>runs.find(r=>!r.pinned&&r!==newest&&r.job!==newest?.job)||null;
// The list after the swap: the kept run back at its place (by run number) and the other run out.
export function swapDropped(runs,kept,other){
 const next=runs.filter(r=>r!==other),at=next.findIndex(r=>Number.isInteger(r.number)&&r.number>kept.number);
 next.splice(at<0?next.length:at,0,kept);return next;
}
/** The message when the optical run limit dropped a run: "Run 3 (closed · 4 modes · 700 × 300 nm) was
 * dropped: up to 20 runs are kept; pin a run to keep it." A named run reads "Run 3 · Design A (…)". */
export function droppedRunText(run){
 return `${dropName(run)} was dropped: up to ${OPTICAL_RUN_LIMIT} runs are kept; pin a run to keep it.`;
}
// The run state the dock heading and the footer describe, in the words of the multiphysics model.
// viewed: the run Results shows (the selected run), which both then describe, so they agree with
// the step bar and the title. 'current': that run (without one, the newest run) solved these exact
// inputs; 'other': the viewed run has other inputs, and has: the number of a run of these inputs,
// if any, with hasName its name (the status line names that run as the source of the current inputs,
// round 18 X11); 'stale': runs exist but none is viewed and none has these inputs; 'none' before any
// run. origin: where the run came from when it was not computed in this tab ('imported' or
// 'recovered'). name: the run's name (absent when it has none). For 'other', geometry and
// currentGeometry: the two geometries in words, and changes: what differs, from the run to the
// current inputs (inputChanges), which names them when the geometry is the same (round 14).
export function opticalFreshness(input,runs=[],viewed=null,modeCount,groupIndex=false,pml=null,searchTarget=null){
 const signature=studySignature(input,modeCount,groupIndex,pml,searchTarget),own=runs.findLastIndex(run=>run.signature===signature),seen=viewed?runs.indexOf(viewed):-1;
 // a run's number in the tab (round 17, U2), else its place in the list
 const number=i=>Number.isInteger(runs[i]?.number)?runs[i].number:i+1;
 const index=seen>=0?seen:own,run=runs[index],origin=run?.origin,from=origin==='imported'||origin==='recovered'?{origin}:{},name=run?.label?{name:run.label}:{};
 if(seen>=0&&run.signature!==signature)return {state:'other',run:number(index),...name,...from,...(own>=0?{has:number(own),...(runs[own].label?{hasName:runs[own].label}:{})}:{}),geometry:geometryWords(run.input.model),currentGeometry:geometryWords(input.model),changes:inputChanges(run.input,input)};
 if(index>=0)return {state:'current',run:number(index),...name,...from};
 return runs.length?{state:'stale',run:number(runs.length-1)}:{state:'none',run:null};
}
// The viewed run and the current inputs, both named (round 14): "Run 1 · Design A 600 × 300 nm ·
// current inputs 700 × 300 nm"; with the same geometry, at most two changes ("· current inputs
// differ: Wavelength 1550 → 1310 nm"), and the plain words when no listed setting differs.
export function otherInputsText({run,name='',geometry,currentGeometry,changes=[]}){
 const viewed=geometry?`Run ${run} · ${name?name+' ':''}${geometry}`:runTitle(run,name);
 if(geometry&&currentGeometry&&geometry!==currentGeometry)return `${viewed} · current inputs ${currentGeometry}`;
 if(changes.length)return `${viewed} · current inputs differ: ${changes.slice(0,2).join(' · ')}${changes.length>2?' …':''}`;
 return `${viewed} · current inputs differ from this run`;
}
// The dock heading and the ready footer for that state: both name the same run.
export function opticalSequenceHeading({state,run,name='',origin,...other}){
 const title=runTitle(run,name);
 if(state==='current'&&originText(origin))return `${title} · ${originText(origin)}`;
 if(state==='current')return `${title} · solved from the current inputs`;
 if(state==='other')return otherInputsText({run,name,...other});
 if(state==='stale')return `Inputs changed since run ${run} · press Run to update`;
 return 'Nothing is computed until you press Run';
}
export const HAS_RESULTS_INPUTS='has the results of the current inputs';
// Round 20 (Z1): an edit that leaves the inputs equal to a run's says only that no run is needed:
// the edit's own sentence stays and its request to run ("Run explicitly to compute new results.",
// or the line that the inputs changed since the last result) is taken off before the "No need to
// run" sentence is added. A message without such a request is returned as it is.
// round 22 (V5): the closed-window shortcut's request, Press Run study to compute., too
export const RUN_REQUESTS=Object.freeze(['Run explicitly to compute new results.','Inputs changed since the last result. Run again to compute the new inputs.','Press Run study to compute.']);
export function matchingRunMessage(message){
 let text=String(message||'');
 for(const request of RUN_REQUESTS)if(text.endsWith(request)){text=text.slice(0,text.length-request.length).trimEnd();break;}
 return text;
}
export function opticalReadyStatus({state,run,name='',origin,has,hasName='',...other}){
 const title=runTitle(run,name);
 // round 20 (Z1): a run read from file or recovered that has these results says so, without asking for a run
 if(state==='current'&&originText(origin))return `${title} · ${originText(origin)} · ${HAS_RESULTS_INPUTS}`;
 if(state==='current')return `${title} · solved from the current inputs · press Run to solve again`;
 if(state==='other')return otherInputsText({run,name,...other})+' · '+(has?`current inputs from ${runTitle(has,hasName)}`:'press Run to compute them');
 if(state==='stale')return `Inputs changed since run ${run} · press Run to update`;
 return 'Optical adapter ready · explicit Run required';
}
