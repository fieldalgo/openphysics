// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
// The words of the heated model's run retention (design "Keeping more runs", section 7): the optical
// words (workspace-retention.mjs) with "maps" for "fields" and the heated model's run names, "Run 3
// (run at 14:02)". The budget and the order are the optical ones (workspace-budget.mjs); the maps a
// run adds are counted from its cached record texts (workspace-multiphysics-session.mjs).
import {FIELD_BUDGET_BYTES,mbText} from './workspace-budget.mjs';
import {MULTIPHYSICS_RUN_LIMIT,chooseMaps,mapBytes,appendMultiphysicsRun,compactMapBytesOf,holdsCompactMaps} from './workspace-multiphysics-session.mjs';
import {canonicalJson} from './workspace-multiphysics.mjs';
import {aboutText} from './workspace-workflow.mjs';

export const MAP_BUDGET_TEXT=mbText(FIELD_BUDGET_BYTES);
const listWords=words=>words.length<3?words.join(' and '):words.slice(0,-1).join(', ')+' and '+words.at(-1);
const title=run=>`Run ${run.number}${run.label?' · '+run.label:''}`;
/** When maps move, as the run list and Results say it. */
export const MAPS_MOVE_TEXT=`Maps are kept up to ${MAP_BUDGET_TEXT}. When a result or a recompute arrives, Studio keeps the selected run's maps first, then pinned runs', then the newest. Selecting a run does not bring its maps back; Recompute does.`;
/** The note under the run list (it replaces "Up to six runs are kept. …"). */
export const MP_RUNS_KEPT_TEXT=`Up to ${MULTIPHYSICS_RUN_LIMIT} runs are kept with their values. ${MAPS_MOVE_TEXT} Pinned runs stay; when a ${MULTIPHYSICS_RUN_LIMIT+1}st run arrives, the oldest unpinned run is replaced. File › Save keeps every run in one file.`;
export const mpRunsNodeLabel=count=>`Runs · ${count} of ${MULTIPHYSICS_RUN_LIMIT}`;
// Compact maps (session version 17), in the words of the optical compact fields (round 27, D1: no
// Messages sentence when maps become compact).
/** The sentence after the note under the run list, while the tab holds compact maps. */
export const MP_COMPACT_NOTE='When maps would not all fit, they are kept at single precision.';
/** Results, under the maps of a run whose maps are compact. */
export const MP_COMPACT_RESULTS_TEXT='Maps at single precision (float32). The values above are the engine\'s.';
/** The note under the run list: MP_RUNS_KEPT_TEXT, then MP_COMPACT_NOTE while the tab holds compact maps. */
export const mpRunsKeptNote=runs=>holdsCompactMaps(runs)?`${MP_RUNS_KEPT_TEXT} ${MP_COMPACT_NOTE}`:MP_RUNS_KEPT_TEXT;
export const ALL_PINNED_TEXT=`All ${MULTIPHYSICS_RUN_LIMIT} runs are pinned. Unpin a run under Results › Runs before running again.`;
export const UNPINNED_TEXT=`Run unpinned: once ${MULTIPHYSICS_RUN_LIMIT} runs are kept, a new run replaces the oldest unpinned one. Press Enter in Run name to pin it again.`;
const keeps=(list,name)=>`${listWords(list.map(name))} ${list.length>1?'keep their values, not their maps':'keeps its values, not its maps'}`;
/** Before the run: "If you run: Run 3 (run at 14:02) keeps its values, not its maps". */
export const mapsKeepValuesText=(list,name)=>`If you run: ${keeps(list,name)}`;
/** While the run computes. */
export const mapsKeepValuesWhileRunningText=(list,name)=>`When this run finishes, ${keeps(list,name)}`;
/** Before the run, with no estimate, when the room left is less than the smallest map kept. */
export const MAPS_MAY_GO_TEXT=`If you run: older runs' maps may not be kept (${MAP_BUDGET_TEXT} limit) · pin a run to keep its maps first`;
/** After the result: "Run 3 (run at 14:02) keeps its values; its maps were not kept (16.8 MB limit)." */
export const mapsNotKeptAfterText=(list,name)=>`${listWords(list.map(name))} ${list.length>1?'keep their values; their maps were not kept':'keeps its values; its maps were not kept'} (${MAP_BUDGET_TEXT} limit).`;
/** The swap: "Keep Run 3's maps, not Run 4's (run at 14:05)". when(run): the run's time. */
export const keepMapsInsteadLabel=(back,other,when)=>`Keep ${title(back)}'s maps, not ${title(other)}'s (run at ${when(other)})`;
export const mapsBackText=(back,other,name)=>`${title(back)}'s maps are back; ${name(other)} keeps its values, not its maps.`;
/** A pinned run's maps went: "Run 2 (pinned) keeps its values; its maps were not kept: …". */
export function pinnedMapsText(list,bytes){
 const names=listWords(list.map(r=>`${title(r)} (pinned)`));
 return `${names} ${list.length>1?'keep their values; their maps were not kept':'keeps its values; its maps were not kept'}: the selected and pinned runs' maps are ${mbText(bytes)}, over the ${MAP_BUDGET_TEXT} limit. Unpin a run to keep the newer maps first.`;
}
/** Results, a run whose maps this tab let go (a run read without maps says MAPS_NOT_KEPT). */
export const mapsNotKeptResultsText=run=>`${title(run)}'s maps are not kept; its n_eff, coupling check and iteration history are kept. ${MAPS_MOVE_TEXT}`;
export const recomputeMapsLabel=run=>`Recompute ${title(run)}'s maps`;
export const recomputeMapsEstimate=run=>Number.isFinite(run.duration)?` · about ${aboutText(run.duration)}`:'';
export const recomputingMapsText=run=>`Recomputing ${title(run)}'s maps${recomputeMapsEstimate(run)}`;
export const recomputeStoppedText=run=>`Recompute of ${title(run)}'s maps stopped; ${title(run)} is unchanged.`;
export const recomputedMapsText=run=>`${title(run)}'s maps recomputed from its stored model; its values match.`;
/** "Run 4's maps were not recomputed: <what>. Run 4 is unchanged; Run study makes a new run from the
 * current model.", with "(stored by Studio 0.9.3; this is 0.9.4)" after <what> when they differ. */
export function notRecomputedMapsText(run,what,{stored=null,current=null}={}){
 const t=title(run),versions=stored&&current&&stored!==current?` (stored by Studio ${stored}; this is ${current})`:'';
 return `${t}'s maps were not recomputed: ${what}${versions}. ${t} is unchanged; Run study makes a new run from the current model.`;
}
export const cannotRecomputeMapsText=(run,words)=>`${title(run)}'s maps cannot be recomputed: ${words}`;
/** "No need to run" for a run of the current model without its maps. */
export const mapsValuesAgainText=run=>`No need to run: ${title(run)} already has these values; its maps are not kept. Run study adds a copy with the same values`;

// ---- before the run: the estimate ---------------------------------------------------------------
/** What a run's map size depends on: the geometry, the mesh, the materials, the physics (names and
 * types) and the couplings. */
export const mapSizeKey=doc=>canonicalJson([doc?.geometry??null,doc?.mesh??null,doc?.materials??null,
 Object.entries(doc?.physics??{}).map(([n,p])=>[n,p?.type??null]),doc?.couplings??null]);
/** The runs whose maps the next result would let go, from the map bytes of the newest run with maps
 * of the same key ([] with none). state: the session state; next: the next run's document. The
 * 20-run drop is applied first (a run it drops is named by the drop words). Compact maps (version 17):
 * when the arrival would make the tab's maps compact (compactMaps), their compact bytes count. */
export function predictedMapsLetGo(state,next){
 const key=mapSizeKey(next),like=state.runs.findLast(r=>r.maps!=='not kept'&&mapSizeKey(r.doc)===key);if(!like)return [];
 const top=Math.max(0,...state.runs.map(r=>r.number||0)),phantom={...like,job:'mp-ffffffffffff',pinned:false,label:'',number:top+1};
 let after;try{after=appendMultiphysicsRun(state.runs,phantom);}catch{return [];}
 const bytes=mapBytes(like),size=r=>r===phantom?bytes:mapBytes(r),trial={...state,runs:after,selected:phantom.job};
 const compact=!holdsCompactMaps(after)&&!chooseMaps(trial,{bytes:size}).fits,arrival=compact?r=>compactMapBytesOf(r===phantom?like:r)??size(r):size;
 const {letGo}=chooseMaps(trial,{bytes:arrival});
 return letGo.filter(r=>r.job!==phantom.job);
}
/** Whether "older runs' maps may not be kept" is shown: no run with maps of the next key, some map
 * kept, and the room left in the budget less than the smallest kept map. */
export function unestimatedMapRisk(state,next){
 const key=mapSizeKey(next);if(state.runs.some(r=>r.maps!=='not kept'&&mapSizeKey(r.doc)===key))return false;
 const {kept,total}=chooseMaps(state);if(!kept.length)return false;
 return FIELD_BUDGET_BYTES-total<Math.min(...kept.map(mapBytes));
}
