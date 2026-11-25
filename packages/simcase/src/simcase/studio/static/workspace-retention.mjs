// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
// Run retention (design "Keeping more runs"): the optical model keeps the values of up to 20 runs
// (RUN_LIMIT) and their fields within one budget, shared by the tab, File › Save, the project entry
// and browser recovery, so what the tab shows is what a file or a restore brings back.
//
// The budget is the 16 MiB session less 16 KiB kept for the inputs (FIELD_BUDGET_BYTES, 16,760,832
// bytes): the inputs, the comparison and the view are in the session text too and change between
// arrivals, so a tab filled to the budget still fits the 16 MiB session after some edits. When a
// field arrives (a new result, a recomputed field, Add runs from file, Open or Restore), the fields
// kept are, while the session text with them is within the budget:
//   1. the selected run's (kept even when it alone is over the budget: section 3.4);
//   2. the run whose field arrived (a recompute, or Keep Run N's fields), when it is not selected;
//   3. the pinned runs', newest first (the largest run number first);
//   4. the other runs', newest first;
// a field that does not fit is skipped and the next older one is tried. Selecting, pinning,
// unpinning, naming or comparing runs removes no field. A run without its field keeps n_eff, the
// TE fractions, the effective areas, n_g and the open-boundary candidates (its values).
import {FIELD_HEADROOM_BYTES,FIELD_BUDGET_BYTES,mbText,RUNS_KEPT_TEXT,RUN_LIMIT,PREVIOUS_RUN_LIMIT,sessionText,sessionBytesWithoutFields,runFieldBytes,withoutField,appendRun,fitsVersion7} from './workspace-notebook.mjs';
import {dropName,dropParts,runTitle,aboutText} from './workspace-workflow.mjs';

export {FIELD_HEADROOM_BYTES,FIELD_BUDGET_BYTES,mbText};
export const BUDGET_TEXT=mbText(FIELD_BUDGET_BYTES);
const utf8Bytes=text=>new TextEncoder().encode(text).length;
const newestFirst=(a,b)=>b.number-a.number;

/** The runs with fields in the order their fields are kept (see the top of this file). first: the
 * jobs whose fields arrived and are not the selected run's. */
export function fieldOrder(runs,selected,first=[]){
 const withField=runs.filter(r=>r.field);
 const chosen=withField.filter(r=>r.job===selected);
 for(const job of first){const r=withField.find(x=>x.job===job);if(r&&!chosen.includes(r))chosen.push(r);}
 const rest=withField.filter(r=>!chosen.includes(r));
 return [...chosen,...rest.filter(r=>r.pinned).sort(newestFirst),...rest.filter(r=>!r.pinned).sort(newestFirst)];
}

/** The fields the budget keeps: {kept, letGo, total, base, fits}. kept and letGo: runs with fields;
 * total: the bytes of the session text with the kept fields (base: with none). fits: every field is
 * kept (the text with all of them is within the budget). bytes(run): a run's field bytes. */
export function chooseFields(input,runs,selected,comparison,view,{first=[],budget=FIELD_BUDGET_BYTES,bytes=runFieldBytes}={}){
 const withField=runs.filter(r=>r.field);
 if(!withField.length)return {kept:[],letGo:[],total:null,base:null,fits:true};
 const base=sessionBytesWithoutFields(input,runs,selected,comparison,view);
 const sum=withField.reduce((t,r)=>t+bytes(r),base);
 // the text of every field may be of version 7 (smaller than the sum, which counts version 9 records)
 const seven=runs.length<=PREVIOUS_RUN_LIMIT&&runs.every(fitsVersion7);
 if(sum<=budget||(seven&&utf8Bytes(sessionText(input,runs,selected,comparison,view))<=budget))return {kept:withField,letGo:[],total:sum,base,fits:true};
 let total=base;const kept=[],letGo=[];
 fieldOrder(runs,selected,first).forEach((r,i)=>{const b=bytes(r);
  // the selected run keeps its field even alone over the budget (section 3.4: Save then refuses)
  if(total+b<=budget||(i===0&&r.job===selected)){kept.push(r);total+=b;}else letGo.push(r);});
 return {kept,letGo,total,base,fits:false};
}

/** The bytes of the session text with the fields of the selected and pinned runs only (the words
 * when a pinned run's field goes, section 3.3). */
export function selectedAndPinnedBytes(runs,selected,base,bytes=runFieldBytes){
 return runs.filter(r=>r.field&&(r.pinned||r.job===selected)).reduce((t,r)=>t+bytes(r),base);
}

// The values a run without its field shows (written by withoutField, the way a session writes the
// run), and the ones it had before, so that Keep Run N's fields puts them back as they were.
const RELEASED=Symbol('released field'),LET_GO=Symbol('field let go in this tab');
/** Whether this tab let the run's field go (else a run without fields came so from a file or record). */
export const fieldLetGoHere=run=>!run.field&&run[LET_GO]===true;
/** The run's field let go in the tab: field null with the TE fractions and areas it shows (in place:
 * the run stays the same object, with its number, name and pin). */
export function letGoField(run){
 const shown=withoutField(run),bytes=runFieldBytes(run);
 Object.defineProperty(run,RELEASED,{value:{field:run.field,bytes,te:run.te_polarization_fraction,area:run.effective_area,settings:run.settings},enumerable:false,configurable:true,writable:true});
 Object.defineProperty(run,LET_GO,{value:true,enumerable:false,configurable:true,writable:true});
 run.field=null;run.settings=shown.settings;run.te_polarization_fraction=shown.te_polarization_fraction;run.effective_area=shown.effective_area;
 return run;
}
/** Whether a run's let-go field is still held for Keep Run N's fields. */
export const heldField=run=>!run.field&&!!run[RELEASED];
/** The run's let-go field back (Keep Run N's fields), as it was. */
export function takeBackField(run){
 const held=run[RELEASED];if(!held||run.field)return false;
 run.field=held.field;run.settings=held.settings;
 if(held.te===undefined)delete run.te_polarization_fraction;else run.te_polarization_fraction=held.te;
 if(held.area===undefined)delete run.effective_area;else run.effective_area=held.area;
 delete run[RELEASED];return true;
}
/** The held fields are dropped (at the next arrival the swap is stale, and memory is freed). */
export function forgetHeldFields(runs){for(const r of runs)if(r[RELEASED])delete r[RELEASED];}
/** A recomputed field attached to its run: the field, and the values as they were before the field
 * was let go when this tab let it go (else as the run stores them). */
export function attachField(run,field){
 const held=run[RELEASED];
 if(held){run.settings=held.settings;if(held.te===undefined)delete run.te_polarization_fraction;else run.te_polarization_fraction=held.te;
  if(held.area===undefined)delete run.effective_area;else run.effective_area=held.area;delete run[RELEASED];}
 run.field=field;return run;
}

/** The run Keep Run N's fields lets go instead of the one let go (letGo: one unpinned run): the oldest
 * unpinned, unselected run with a field at least as large, or null. */
export function fieldSwapCandidate(runs,letGo,selected,bytes=runFieldBytes){
 if(letGo.length!==1||letGo[0].pinned||!heldField(letGo[0]))return null;
 const need=letGo[0][RELEASED].bytes;
 return runs.find(r=>r!==letGo[0]&&r.field&&!r.pinned&&r.job!==selected&&bytes(r)>=need)||null;
}

// ---- the words (section 5 and 4.1) ------------------------------------------------------------
const listWords=words=>words.length<3?words.join(' and '):words.slice(0,-1).join(', ')+' and '+words.at(-1);
/** The note under the run list: section 5's first sentences (they replace "Up to six runs are kept."). */
export const RUNS_KEPT_NOTE=RUNS_KEPT_TEXT;
/** The run list's mark of a run without its fields. */
export const VALUES_ONLY=' · values only';
/** Before the run (the box beside Run study): "If you run: Run 3 (…) keeps its values, not its
 * fields"; two or more: "… and Run 5 (…) keep their values, not their fields". */
export const keepsValuesText=(list,name=dropName)=>`If you run: ${listWords(list.map(name))} ${list.length>1?'keep their values, not their fields':'keeps its values, not its fields'}`;
/** While the run computes: "When this run finishes, Run 3 (…) keeps its values, not its fields". */
export const keepsValuesWhileRunningText=(list,name=dropName)=>`When this run finishes, ${listWords(list.map(name))} ${list.length>1?'keep their values, not their fields':'keeps its values, not its fields'}`;
/** After the result (Messages): "Run 3 (…) keeps its values; its fields were not kept (16.8 MB limit)." */
export const fieldsNotKeptAfterText=(list,name=dropName)=>`${listWords(list.map(name))} ${list.length>1?'keep their values; their fields were not kept':'keeps its values; its fields were not kept'} (${BUDGET_TEXT} limit).`;
/** The swap after the result: "Keep Run 3's fields, not Run 4's (…)". */
export const keepFieldsInsteadLabel=(back,other)=>`Keep ${runTitle(back.number,back.label||'')}'s fields, not ${runTitle(other.number,other.label||'')}'s (${dropParts(other)})`;
/** Once swapped: "Run 3's fields are back; Run 4 (…) keeps its values, not its fields." */
export const fieldsBackText=(back,other,name=dropName)=>`${runTitle(back.number,back.label||'')}'s fields are back; ${name(other)} keeps its values, not its fields.`;
/** A pinned run's fields went (section 3.3): "Run 2 (pinned) keeps its values; its fields were not
 * kept: the selected and pinned runs' fields are 17.4 MB, over the 16.8 MB limit. Unpin a run to
 * keep the newer fields first." bytes: the session with the selected and pinned runs' fields. */
export function pinnedFieldsText(list,bytes){
 const names=listWords(list.map(r=>`${runTitle(r.number,r.label||'')} (pinned)`));
 return `${names} ${list.length>1?'keep their values; their fields were not kept':'keeps its values; its fields were not kept'}: the selected and pinned runs' fields are ${mbText(bytes)}, over the ${BUDGET_TEXT} limit. Unpin a run to keep the newer fields first.`;
}
/** Results, a run without its fields (section 4.1). fromFile: read from a session file without them. */
export const fieldsNotKeptResultsText=(run,fromFile=false)=>{const t=runTitle(run.number,run.label||'');
 return fromFile?`${t}'s fields were not kept in the session file. Its n_eff, TE fractions and effective areas are kept.`
  :`${t}'s fields are not kept: up to ${BUDGET_TEXT} of fields are kept, for the selected and pinned runs first, then the newest. Its n_eff, TE fractions and effective areas are kept.`;};
/** The button that recomputes a run's fields (R3) and its estimate: " · about 2 min" from the run's
 * wall time in this tab; none for a run opened or restored (it has no time). */
export const recomputeLabel=run=>`Recompute ${runTitle(run.number,run.label||'')}'s fields`;
export const recomputeEstimate=run=>Number.isFinite(run.duration)?` · about ${aboutText(run.duration)}`:'';
/** The title of a field export of a run without its fields. */
export const recomputeFirstText=run=>`${recomputeLabel(run)} first`;
/** Compare, a run without its fields (section 4.2). */
export const compareNoFieldsText=run=>`${runTitle(run.number,run.label||'')}'s fields are not kept, so its modes are listed by number and not plotted.`;
/** The header of Compare's values table when a run has no fields: modes by number, not by overlap. */
export const COMPARE_BY_NUMBER='Modes listed by number, not matched by overlap';

// ---- before the run: the estimate (section 5) ------------------------------------------------
/** What a run's field size depends on: its geometry (shapes and core mesh), its boundary (closed, or
 * the open edges and PML) and Modes to find. */
export const fieldSizeKey=({shapes,coreMesh,boundary,modeCount})=>JSON.stringify([shapes,coreMesh,boundary??null,modeCount]);
// (the PML of Studio's open boundary is always 1 µm thick: its open edges name it)
export const runFieldSizeKey=run=>fieldSizeKey({shapes:run.input.model.shapes,coreMesh:run.input.model.coreMesh,
 boundary:run.settings.pml?.open_edges??null,modeCount:run.settings.mode_count});
/** The runs whose fields the next result would let go, from the field bytes of the newest run of the
 * same geometry, boundary and Modes to find ([] with no such run: nothing is said before the run,
 * section 5 and Q6). next: the key of the next run (fieldSizeKey). The 20-run drop is applied first
 * (a run it drops is named by the drop words, not here). */
export function predictedLetGo(input,runs,selected,comparison,view,next,{budget=FIELD_BUDGET_BYTES,bytes=runFieldBytes}={}){
 const like=runs.findLast(r=>r.field&&runFieldSizeKey(r)===next);if(!like)return [];
 // the next result as a run of this list: like's record, a new job and the next number, selected
 const top=Math.max(0,...runs.map(r=>r.number||0)),phantom=Object.assign({...like,job:'ffffffff',pinned:false,label:''},{number:top+1});
 let after;try{after=appendRun(runs,phantom,RUN_LIMIT);}catch{return [];}
 const size=r=>r===phantom?bytes(like):bytes(r);
 // (the view's mode is the next result's first: the selected run then has at least one mode)
 const {letGo}=chooseFields(input,after,phantom.job,comparison,{...view,mode:0},{budget,bytes:size});
 return letGo.filter(r=>r!==phantom);
}
