// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0

// optical-shapes-v10: Search near n_eff in a closed window (design "Search near n_eff for
// closed-window runs", slice C1). With a target t and every edge closed, the optical document's
// em1 gets target_effective_index t after its other keys: the engine then returns the mode_count
// eigenvalues nearest t (Re > 0, no threshold), listed by descending Re n_eff. Without a target the
// document is the optical-shapes-v8 or -v9 one, byte for byte. No engine change.
import {maxIndex,defaultTarget,TARGET_FLOOR} from './workspace-open-boundary.mjs';

export const CLOSED_TARGET_ADAPTER='optical-shapes-v10';
// The query a workspace request with a closed-window target carries (capabilities v10).
export const CLOSED_TARGET_QUERY='workspace_capabilities=10';
export {defaultTarget};

/** A closed-window Search near n_eff, checked: a number kept to 3 decimals, above 1.45 and below
 * the design's largest index at 1550 nm (the open boundary's bounds). */
export function checkClosedTarget(t,shapes){
 const nmax=maxIndex(shapes);
 if(typeof t!=='number'||!Number.isFinite(t)||Math.round(t*1000)/1000!==t||!(t>TARGET_FLOOR&&t<nmax))throw new Error(`Search near n_eff must lie between ${TARGET_FLOOR} and ${nmax} (3 decimals).`);
 return t;
}

/** The optical-shapes-v10 document: the closed document `doc` with target_effective_index t
 * (checked) after the other em1 keys. */
export function applyClosedTarget(doc,t){
 const em=doc.physics.em1;
 return {...doc,physics:{em1:{...em,target_effective_index:t}}};
}

// ---- The page's words and a new result (slice C2) ----------------------------------------------
// The guided threshold of a closed run: a closed search lists only the modes above it (A1).
export const CLOSED_FLOOR=TARGET_FLOOR;
// The edge note's shortcut (Q2, Q5): Search near the default target with 4 modes.
export const SHORTCUT_MODE_COUNT=4;
/** A target as the page's words write it: its shortest decimal (2.46, 2.85, 1.995). */
export const shortTarget=t=>String(Number(t));
/** "Set search near 2.46 · 4 modes": the edge note's shortcut (round 22, V5: "Set", as it runs nothing). */
export const shortcutText=t=>`Set search near ${shortTarget(t)} · ${SHORTCUT_MODE_COUNT} modes`;
/** The end of the shortcut's message (round 22, V5): it sets the inputs; Run study computes. */
export const SHORTCUT_RUN_TEXT='Press Run study to compute.';
/** "Found 3 of 4 modes near n_eff 2.46, above n = 1.45": the run line of every closed targeted run. */
export const closedFoundText=(found,asked,t)=>`Found ${found} of ${asked} modes near n_eff ${shortTarget(t)}, above n = ${CLOSED_FLOOR}`;
/** The table note of a closed targeted run that left modes out ('' when none): the engine returns
 * the mode_count modes nearest the target, so asked - found of them are at or below 1.45. */
export const leftOutText=(found,asked)=>{const n=asked-found;return n<=0?'':n===1?'1 mode at or below n = 1.45 was left out.':`${n} modes at or below n = 1.45 were left out.`;};
/** "closed near 2.46": the tag of a closed targeted run in the run list, the pickers and the status line. */
export const closedTargetTag=t=>`closed near ${shortTarget(t)}`;
/** The run plan's boundary words: "Closed window · near n_eff 2.46". */
export const closedPlanText=t=>`Closed window · near n_eff ${shortTarget(t)}`;
/** The help of Modes to return in Physics › Optical modes (Q9: closed and open values differ; round
 * 22, V1: one choice of two radios and the field, the meanings of the box off and on unchanged). */
export const CLOSED_SEARCH_LEGEND='Modes to return';
export const HIGHEST_LABEL='Highest n_eff above 1.45';
export const NEAREST_LABEL='Nearest to n_eff';
export const NEAR_FIELD_LABEL='n_eff to search near';
export const CLOSED_SEARCH_HELP='Highest n_eff above 1.45: the modes of highest n_eff. Nearest to n_eff: the modes nearest the index in the field, listed by n_eff, highest first; modes at or below 1.45 are left out. Typing an index selects Nearest to n_eff. Closed and open values differ: refine the mesh before a close comparison.';
/** The message of the choice or the field. */
export const closedSearchNotice=t=>t==null?'Modes to return: highest n_eff above 1.45. The next run returns the modes of highest n_eff.':`Modes to return: nearest to n_eff ${Number(t).toFixed(3)} in the closed window. The next run returns the modes nearest it.`;

/** The modes of a new closed targeted result that Studio keeps: Re n_eff above 1.45, in the engine's
 * order. {keep (the engine's indices), re, data (the result with the vector samples of the kept
 * modes only)}. Throws when no mode is kept. */
export function closedResultValues(result,re,t){
 const keep=re.map((x,i)=>x>CLOSED_FLOOR?i:-1).filter(i=>i>=0);
 if(!keep.length)throw new Error(`No mode above n = ${CLOSED_FLOOR} was found near n_eff ${shortTarget(t)}. Move Search near n_eff.`);
 const vf=result.vector_fields?.[0],pick=a=>Array.isArray(a)?keep.map(i=>a[i]):a;
 const data=vf?{...result,vector_fields:[{...vf,real:pick(vf.real),imag:pick(vf.imag)},...result.vector_fields.slice(1)]}:result;
 return {keep,re:keep.map(i=>re[i]),data};
}
