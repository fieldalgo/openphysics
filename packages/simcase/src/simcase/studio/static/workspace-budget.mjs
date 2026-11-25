// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
// The run-retention budget (design "Keeping more runs", sections 3.2 and 7), shared by the optical
// model's fields (workspace-retention.mjs) and the heated model's maps
// (workspace-multiphysics-session.mjs). This module imports nothing, so both can use it.
//
// The budget is the 16 MiB session less 16 KiB kept for the inputs: 16,760,832 bytes, "16.8 MB".
// When a field or a map arrives, those kept are, while the session text with them is within the
// budget: 1. the selected run's (kept even when it alone is over the budget); 2. the runs' whose
// field or maps arrived (`first`), when not selected; 3. the pinned runs', newest first (the largest
// run number first); 4. the other runs', newest first. One that does not fit is skipped and the next
// older one tried.
export const MAX_SESSION_BYTES=16*1024*1024;
export const FIELD_HEADROOM_BYTES=16*1024;
export const FIELD_BUDGET_BYTES=MAX_SESSION_BYTES-FIELD_HEADROOM_BYTES;
/** A size in MB with one decimal ("16.8 MB"), as every limit of run retention is said. */
export const mbText=bytes=>`${(bytes/1e6).toFixed(1)} MB`;
const newestFirst=(a,b)=>b.number-a.number;

/** The runs (each with a field or maps) in the order they are kept: the selected run's, the jobs of
 * `first`, then pinned newest first, then the others newest first. */
export function budgetOrder(runs,selected,first=[]){
 const chosen=runs.filter(r=>r.job===selected);
 for(const job of first){const r=runs.find(x=>x.job===job);if(r&&!chosen.includes(r))chosen.push(r);}
 const rest=runs.filter(r=>!chosen.includes(r));
 return [...chosen,...rest.filter(r=>r.pinned).sort(newestFirst),...rest.filter(r=>!r.pinned).sort(newestFirst)];
}
/** The ordered runs the budget keeps: {kept, letGo, total}. base: the session bytes without any of
 * them; bytes(run): the bytes a run's field or maps add (cached record sums). The first run, when it
 * is the selected one, is kept even alone over the budget. */
export function budgetChoose(ordered,{base,bytes,selected,budget=FIELD_BUDGET_BYTES}){
 let total=base;const kept=[],letGo=[];
 ordered.forEach((r,i)=>{const b=bytes(r);
  if(total+b<=budget||(i===0&&r.job===selected)){kept.push(r);total+=b;}else letGo.push(r);});
 return {kept,letGo,total};
}

// ---- Recompute (section 4.4; the heated model's maps, section 7) -------------------------------
/** The tolerance a recomputed value must meet: relative 1e-12, or absolute 1e-15 for a value whose
 * magnitude is below 1e-3 (both the stored and the recomputed value). */
export const RECOMPUTE_RELATIVE=1e-12,RECOMPUTE_ABSOLUTE=1e-15,RECOMPUTE_SMALL=1e-3;
export function sameValue(stored,fresh){
 if(stored===null||fresh===null)return stored===fresh;
 if(!Number.isFinite(stored)||!Number.isFinite(fresh))return false;
 const d=Math.abs(fresh-stored);
 return Math.max(Math.abs(stored),Math.abs(fresh))<RECOMPUTE_SMALL?d<=RECOMPUTE_ABSOLUTE:d<=RECOMPUTE_RELATIVE*Math.abs(stored);
}
/** Two values as a refusal writes them: enough digits that they differ (n_eff and n_g to at least 8
 * decimals, other quantities to at least 9 significant digits). */
export function valuePair(name,a,b){
 if(a===null||b===null)return [String(a),String(b)];
 const fixed=/n_eff|n_g/.test(name)&&Math.abs(a)>=1e-3;
 for(let d=fixed?8:9;d<=17;d++){const x=fixed?a.toFixed(d):a.toPrecision(d),y=fixed?b.toFixed(d):b.toPrecision(d);if(x!==y||d===17)return [x,y];}
 return [String(a),String(b)];
}
