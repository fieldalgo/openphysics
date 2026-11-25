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
import {FIELD_HEADROOM_BYTES,FIELD_BUDGET_BYTES,mbText,RUNS_KEPT_TEXT,FIELDS_MOVE_TEXT,RUN_LIMIT,PREVIOUS_RUN_LIMIT,sessionText,sessionBytesWithoutFields,runFieldBytes,withoutField,appendRun,fitsVersion7,runModeCount,runSearchTarget,compactRunField} from './workspace-notebook.mjs';
import {isCompactField,compactBytesOf} from './workspace-field-encoding.mjs';
import {dropName,dropParts,runTitle,aboutText} from './workspace-workflow.mjs';
import {withStudy,projectStudy,projectBoundary} from './workspace-project.mjs';
import {opticalDocument,withGroupIndex} from './workspace-optical.mjs';
import {runChoice} from './workspace-open-run.mjs';
import {groupIndexStep} from './workspace-modes.mjs';
import {budgetOrder,budgetChoose,RECOMPUTE_RELATIVE,RECOMPUTE_ABSOLUTE,RECOMPUTE_SMALL,sameValue,valuePair} from './workspace-budget.mjs';

export {FIELD_HEADROOM_BYTES,FIELD_BUDGET_BYTES,mbText};
export const BUDGET_TEXT=mbText(FIELD_BUDGET_BYTES);
const utf8Bytes=text=>new TextEncoder().encode(text).length;

/** The runs with fields in the order their fields are kept (see the top of this file). first: the
 * jobs whose fields arrived and are not the selected run's. */
export const fieldOrder=(runs,selected,first=[])=>budgetOrder(runs.filter(r=>r.field),selected,first);

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
 // the selected run keeps its field even alone over the budget (section 3.4: Save then refuses)
 const {kept,letGo,total}=budgetChoose(fieldOrder(runs,selected,first),{base,bytes,selected,budget});
 return {kept,letGo,total,base,fits:false};
}

// ---- compact fields (design "Compact field encoding") -----------------------------------------
// While every field fits as text, nothing changes. At the first arrival where the fields would not
// all fit as text, every field in the tab is made compact (float32 samples; workspace-notebook.mjs
// compactRunField) and the order above is applied with the compact sizes. Once the tab holds a
// compact field, every field that arrives is made compact too; the tab never converts back. A field
// whose samples are beyond single precision (only a synthetic or hand-edited file holds one) stays
// as text, at its text size. File › Open and Restore (loaded) bring a whole session: its fields are
// kept as the file holds them unless they would not all fit as text, so an opened file saved again
// is its own bytes.
/** The runs whose fields were made compact now (in place), and whether this was the tab's first
 * conversion. */
export function compactFields(input,runs,selected,comparison,view,{budget=FIELD_BUDGET_BYTES,bytes=runFieldBytes,first=[],loaded=false}={}){
 const text=runs.filter(r=>r.field&&!isCompactField(r.field));
 if(!text.length)return {converted:[],started:false};
 const already=runs.some(r=>isCompactField(r.field));
 if((!already||loaded)&&chooseFields(input,runs,selected,comparison,view,{first,budget,bytes}).fits)return {converted:[],started:false};
 const converted=[];
 for(const r of text){try{compactRunField(r);converted.push(r);}catch{/* beyond single precision: kept as text */}}
 return {converted,started:!already&&converted.length>0};
}
/** The fields the budget keeps at an arrival (chooseFields), after compactFields: {...out, converted, started}. */
export function chooseFieldsAtArrival(input,runs,selected,comparison,view,options={}){
 const {converted,started}=compactFields(input,runs,selected,comparison,view,options);
 return {...chooseFields(input,runs,selected,comparison,view,options),converted,started};
}
/** Messages, at the tab's first conversion (once per tab). */
// (round 26: in the words of what the reader gains and what still opens; the session version is in
// the docs, not here)
export const COMPACT_TEXT=`More field plots now fit in ${mbText(FIELD_BUDGET_BYTES)}: Studio keeps them at single precision from now on. n_eff, TE fractions and effective areas are unchanged. Files saved from now on open in this Studio or later; files you already have still open.`;
/** The sentence after the note under the run list. */
export const COMPACT_NOTE='When fields would not all fit, they are kept at single precision.';
/** Results, under the field view of a run whose field is compact. */
export const COMPACT_RESULTS_TEXT='Field at single precision (float32). The values above are the engine\'s.';
/** Export this run, after "with the run's inputs and fields" for a compact run. */
export const COMPACT_EXPORT_TEXT=' (fields at single precision)';
/** The Export this run notice of a compact run: today's words with COMPACT_EXPORT_TEXT after "fields". */
export const compactExportNotice=words=>words.replace("with the run's inputs and fields","with the run's inputs and fields"+COMPACT_EXPORT_TEXT);
/** The note under the run list of a tab holding a compact field: COMPACT_NOTE after the retention note. */
export const compactRunListNote=note=>note.replace(RUNS_KEPT_TEXT,RUNS_KEPT_TEXT+' '+COMPACT_NOTE);
export {isCompactField};

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
/** Results, a run without its fields (section 4.1). fromFile: read from a session file without them.
 * Round 25 (A1): a field let go in this tab says when fields move and that selecting the run does not
 * bring them back (FIELDS_MOVE_TEXT, the run list's note). */
export const fieldsNotKeptResultsText=(run,fromFile=false)=>{const t=runTitle(run.number,run.label||'');
 return fromFile?`${t}'s fields were not kept in the session file. Its n_eff, TE fractions and effective areas are kept.`
  :`${t}'s fields are not kept; its n_eff, TE fractions and effective areas are kept. ${FIELDS_MOVE_TEXT}`;};
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
 const v={...view,mode:0};
 const {letGo}=chooseFields(input,after,phantom.job,comparison,v,{budget,bytes:arrivalSizes(input,after,phantom.job,comparison,v,{budget,bytes:size})});
 return letGo.filter(r=>r!==phantom);
}
/** The field sizes the next arrival applies the order with (chooseFieldsAtArrival): in a tab holding
 * no compact field whose fields would not all fit as text, every field single precision holds is made
 * compact first (compactFields), so its compact bytes count; otherwise bytes. size(run) gives a run's
 * field bytes as it is now (a phantom result: its like-run's); its compact bytes are those of its field. */
export function arrivalSizes(input,runs,selected,comparison,view,{budget=FIELD_BUDGET_BYTES,bytes=runFieldBytes}={}){
 if(runs.some(r=>isCompactField(r.field))||chooseFields(input,runs,selected,comparison,view,{budget,bytes}).fits)return bytes;
 return r=>compactBytesOf(r.field)??bytes(r);
}

/** Round 25 (A1): before the run, with no run of the same geometry, boundary and Modes to find (no
 * estimate, predictedLetGo gives []), the box beside Run study says that older fields may go when the
 * room left in the budget is less than the smallest field kept now. It names no run. */
export const FIELDS_MAY_GO_TEXT=`If you run: older runs' fields may not be kept (${BUDGET_TEXT} limit) · pin a run to keep its fields first`;
/** Whether that line is shown: no run of the next run's key (next: fieldSizeKey) has a field, some
 * field is kept, and budget less the session bytes with the kept fields (chooseFields' total) is less
 * than the smallest kept field's bytes. */
export function unestimatedFieldRisk(input,runs,selected,comparison,view,next,{budget=FIELD_BUDGET_BYTES,bytes=runFieldBytes}={}){
 if(runs.some(r=>r.field&&runFieldSizeKey(r)===next))return false;
 const risk=size=>{const {kept,total}=chooseFields(input,runs,selected,comparison,view,{budget,bytes:size});
  return kept.length>0&&budget-total<Math.min(...kept.map(size));};
 if(!risk(bytes))return false;
 // the arrival rule: in a tab holding no compact field, an arrival that would not fit as text makes
 // every field compact first, so the room left and the smallest field are counted at compact sizes
 if(runs.some(r=>isCompactField(r.field)))return true;
 return risk(r=>compactBytesOf(r.field)??bytes(r));
}

// ---- Recompute Run N's fields (section 4.4) ---------------------------------------------------
/** The tolerance a recomputed value must meet: relative 1e-12, or absolute 1e-15 for a value whose
 * magnitude is below 1e-3 (both the stored and the recomputed value). */
export {RECOMPUTE_RELATIVE,RECOMPUTE_ABSOLUTE,RECOMPUTE_SMALL,sameValue};
// the values a run stores, by name and mode, in the order the check names them
function storedValues(run){
 const k=run.effective_index.length,out=[];
 const each=(name,list)=>{for(let i=0;i<k;i++)out.push({name,mode:i+1,value:list?list[i]??null:null});};
 each('n_eff',run.effective_index);
 if(run.effective_index_im)each('Im n_eff',run.effective_index_im);
 if(run.te_polarization_fraction)each('TE fraction',run.te_polarization_fraction);
 if(run.effective_area)each('effective area',run.effective_area);
 if(run.group_index)each('n_g',run.group_index);
 if(run.group_index_im)each('Im n_g',run.group_index_im);
 // the open boundary's candidates (each with its n_eff, real and imaginary parts)
 for(const c of run.open_boundary?.candidates??[]){out.push({name:'candidate '+c.candidate+' n_eff',mode:null,value:c.effective_index.re});out.push({name:'candidate '+c.candidate+' Im n_eff',mode:null,value:c.effective_index.im});}
 return out;
}
/** The first stored value the recomputed run does not reproduce: {name, mode, stored, fresh}, or
 * null when every value matches (the same modes, keys and candidates, each within the tolerance).
 * The values compared are those the run stores: Re and Im n_eff of every mode, the TE fractions and
 * effective areas, n_g when present and the open boundary's candidates when present. */
export function recomputeMismatch(run,fresh){
 const a=storedValues(run),b=storedValues(fresh);
 for(let i=0;i<Math.max(a.length,b.length);i++){
  const s=a[i],f=b[i];
  if(!s||!f||s.name!==f.name||s.mode!==f.mode)return {name:(s||f).name,mode:(s||f).mode,stored:s?s.value:null,fresh:f?f.value:null,missing:true};
  if(!sameValue(s.value,f.value))return {name:s.name,mode:s.mode,stored:s.value,fresh:f.value};
 }
 return null;
}
// two values as the refusal writes them (workspace-budget.mjs, shared with the heated model's maps)
const twoValues=valuePair;
export const recomputingText=run=>`Recomputing ${runTitle(run.number,run.label||'')}'s fields${recomputeEstimate(run)}`;
export const recomputedText=run=>`${runTitle(run.number,run.label||'')}'s fields recomputed from its stored inputs; its values match.`;
/** "Run 4's fields were not recomputed: mode 1 n_eff came out 2.43931671, stored 2.43931663. Run 4 is
 * unchanged. Use this run's inputs and Run study to make a new run." With a stored and a current
 * Studio version that differ, "(stored by Studio 0.9.3; this is 0.9.4)" follows the values. */
export function notRecomputedText(run,m,{stored=null,current=null}={}){
 const t=runTitle(run.number,run.label||''),[came,was]=twoValues(m.name,m.fresh,m.stored);
 const what=m.missing?`${m.mode?`mode ${m.mode} `:''}${m.name} is not in the recomputed result`:`${m.mode?`mode ${m.mode} `:''}${m.name} came out ${came}, stored ${was}`;
 const versions=stored&&current&&stored!==current?` (stored by Studio ${stored}; this is ${current})`:'';
 return `${t}'s fields were not recomputed: ${what}${versions}. ${t} is unchanged. Use this run's inputs and Run study to make a new run.`;
}
/** A recompute the server refused (its document no longer passes): "Run 4's fields cannot be
 * recomputed: " and the server's words. */
export const cannotRecomputeText=(run,words)=>`${runTitle(run.number,run.label||'')}'s fields cannot be recomputed: ${words}`;
/** "No need to run" for a run of these inputs without its fields (section 4.3). */
export const valuesAgainText=run=>`No need to run: ${runTitle(run.number,run.label||'')} already has these values; its fields are not kept. Run study adds a copy with the same values`;
/** The document Recompute Run N's fields sends: the one the run was computed with, built from its
 * stored inputs and settings as Use this run's inputs sets them (Modes to find, the group index with
 * its step, the outer boundary, the closed window's Search near n_eff), then the page's builder. */
export function recomputeDocument(run){
 const doc=withStudy(run.input,{modeCount:runModeCount(run),groupIndex:run.group_index_method!==undefined,openBoundary:runChoice(run)});
 const state={...doc.model,...projectStudy(doc),openBoundary:projectBoundary(doc),searchTarget:runSearchTarget(run)};
 const built=opticalDocument(state,doc.setup);
 const step=run.group_index_method!==undefined?groupIndexStep(run.group_index_method):null;
 return step?withGroupIndex(built,step):built;
}
